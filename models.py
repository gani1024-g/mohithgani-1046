"""
DocuSense AI SQLAlchemy models.
PostgreSQL + pgvector version.
"""

from datetime import datetime
from typing import List, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column("UserID", Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column("Email", String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column("FullName", String(150), nullable=False)
    role: Mapped[str] = mapped_column("Role", String(50), nullable=False, default="USER")
    hashed_password: Mapped[Optional[str]] = mapped_column("PasswordHash", String(255), nullable=True)
    auth_provider: Mapped[str] = mapped_column("AuthProvider", String(50), nullable=False, default="Local")
    created_at: Mapped[datetime] = mapped_column("CreatedAt", DateTime, nullable=False, default=datetime.utcnow)
    last_login_at: Mapped[Optional[datetime]] = mapped_column("LastLoginAt", DateTime, nullable=True)
    # Guest accounts are temporary; registered users keep this as NULL.
    expires_at: Mapped[Optional[datetime]] = mapped_column("ExpiresAt", DateTime, nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column("IsActive", Boolean, nullable=False, default=True)

    documents: Mapped[List["Document"]] = relationship(
        "Document", back_populates="owner", cascade="all, delete-orphan"
    )
    chat_sessions: Mapped[List["ChatSession"]] = relationship(
        "ChatSession", back_populates="user", cascade="all, delete-orphan"
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column("DocumentID", Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        "UserID", Integer, ForeignKey("users.UserID", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column("FileName", String(255), nullable=False)
    original_name: Mapped[str] = mapped_column("OriginalName", String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column("FileSizeBytes", BigInteger, nullable=False)
    page_count: Mapped[int] = mapped_column("PageCount", Integer, nullable=False, default=1)
    chunk_count: Mapped[int] = mapped_column("ChunkCount", Integer, nullable=False, default=0)
    storage_path: Mapped[Optional[str]] = mapped_column("StoragePath", String(500), nullable=True)
    mime_type: Mapped[str] = mapped_column("MimeType", String(100), nullable=False, default="application/pdf")
    status: Mapped[str] = mapped_column("Status", String(50), nullable=False, default="Processing")
    uploaded_at: Mapped[datetime] = mapped_column("UploadedAt", DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        "UpdatedAt", DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    file_data: Mapped[Optional[bytes]] = mapped_column("FileData", LargeBinary, nullable=True)

    owner: Mapped["User"] = relationship("User", back_populates="documents")
    chunks: Mapped[List["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )
    summaries: Mapped[List["DocumentSummary"]] = relationship(
        "DocumentSummary", back_populates="document", cascade="all, delete-orphan"
    )
    chat_sessions: Mapped[List["ChatSession"]] = relationship(
        "ChatSession", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    chunk_id: Mapped[int] = mapped_column("ChunkID", BigInteger, primary_key=True, autoincrement=True)
    doc_id: Mapped[int] = mapped_column(
        "DocumentID", Integer, ForeignKey("documents.DocumentID", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column("ChunkIndex", Integer, nullable=False, default=0)
    page_num: Mapped[int] = mapped_column("PageNumber", Integer, nullable=False, index=True)
    content: Mapped[str] = mapped_column("ChunkText", Text, nullable=False)
    token_count: Mapped[Optional[int]] = mapped_column("TokenCount", Integer, nullable=True)
    embedding_id: Mapped[Optional[str]] = mapped_column("EmbeddingId", String(100), nullable=True)
    embedding: Mapped[List[float]] = mapped_column("Embedding", Vector(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column("CreatedAt", DateTime, nullable=False, default=datetime.utcnow)
    bbox_json: Mapped[Optional[str]] = mapped_column("BBoxJson", Text, nullable=True)

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
    citations: Mapped[List["MessageCitation"]] = relationship(
        "MessageCitation", back_populates="chunk", cascade="all, delete-orphan"
    )


class DocumentSummary(Base):
    __tablename__ = "document_summaries"

    summary_id: Mapped[int] = mapped_column("SummaryID", Integer, primary_key=True, autoincrement=True)
    doc_id: Mapped[int] = mapped_column(
        "DocumentID", Integer, ForeignKey("documents.DocumentID", ondelete="CASCADE"), nullable=False, index=True
    )
    summary_mode: Mapped[str] = mapped_column("SummaryType", String(50), nullable=False, default="Executive")
    summary_text: Mapped[str] = mapped_column("ExecutiveSummary", Text, nullable=False)
    key_takeaways_json: Mapped[Optional[str]] = mapped_column("KeyTakeaways", Text, nullable=True)
    risks_json: Mapped[Optional[str]] = mapped_column("RiskAnalysis", Text, nullable=True)
    multimode_data_json: Mapped[Optional[str]] = mapped_column("MultiModeDataJson", Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column("GeneratedAt", DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        "UpdatedAt", DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    document: Mapped["Document"] = relationship("Document", back_populates="summaries")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    session_id: Mapped[int] = mapped_column("SessionID", Integer, primary_key=True, autoincrement=True)
    doc_id: Mapped[int] = mapped_column(
        "DocumentID", Integer, ForeignKey("documents.DocumentID", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        "UserID", Integer, ForeignKey("users.UserID", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column("Title", String(255), nullable=False, default="New Chat")
    created_at: Mapped[datetime] = mapped_column("CreatedAt", DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        "UpdatedAt", DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    document: Mapped["Document"] = relationship("Document", back_populates="chat_sessions")
    user: Mapped["User"] = relationship("User", back_populates="chat_sessions")
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="session", cascade="all, delete-orphan"
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    message_id: Mapped[int] = mapped_column("MessageID", BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        "SessionID", Integer, ForeignKey("chat_sessions.SessionID", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column("Role", String(30), nullable=False)
    content: Mapped[str] = mapped_column("Content", Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column("CreatedAt", DateTime, nullable=False, default=datetime.utcnow)

    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")
    citations: Mapped[List["MessageCitation"]] = relationship(
        "MessageCitation", back_populates="message", cascade="all, delete-orphan"
    )


class MessageCitation(Base):
    __tablename__ = "message_citations"

    citation_id: Mapped[int] = mapped_column("CitationID", BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(
        "MessageID", BigInteger, ForeignKey("chat_messages.MessageID", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_id: Mapped[int] = mapped_column(
        "ChunkID", BigInteger, ForeignKey("document_chunks.ChunkID", ondelete="CASCADE"), nullable=False, index=True
    )
    citation_order: Mapped[int] = mapped_column("CitationOrder", Integer, nullable=False, default=0)

    message: Mapped["ChatMessage"] = relationship("ChatMessage", back_populates="citations")
    chunk: Mapped["DocumentChunk"] = relationship("DocumentChunk", back_populates="citations")
