"""
Initialize the DocuSense PostgreSQL database.

The PostgreSQL database and the vector extension should already exist before
running this script.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from models import Base

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:YOUR_POSTGRES_PASSWORD@127.0.0.1:5432/grounded_rag",
)


def init_tables() -> None:
    print("Connecting to PostgreSQL...")
    engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

    try:
        with engine.begin() as conn:
            print("Enabling pgvector extension...")
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

            print("Creating application tables...")
            Base.metadata.create_all(conn)

        print("PostgreSQL schema initialized successfully.")
        print("Tables created or already present:")
        for table_name in Base.metadata.tables:
            print(f"  - {table_name}")
    except Exception as exc:
        print(f"Database initialization failed: {exc}")
        raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    init_tables()
