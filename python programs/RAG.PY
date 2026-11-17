"""
Reference streaming transport for FR-03.1 ("streaming tokens via SSE/WebSockets").

This wraps RAGChatbot (see rag_chatbot.py) in a FastAPI endpoint that streams
Server-Sent Events. Not run automatically in this environment (needs network
access to install dependencies) — provided as the integration reference.

Install:
    pip install fastapi uvicorn

Run:
    uvicorn rag_streaming_server:app --reload

Query:
    curl -N "http://localhost:8000/chat/stream?q=How+does+retrieval+work"

A WebSocket-based alternative is included below the SSE route, since the spec
allows either transport.
"""

from fastapi import FastAPI, WebSocket
from fastapi.responses import StreamingResponse

from rag_chatbot import RAGChatbot, Chunk

app = FastAPI(title="Conversational RAG Chatbox")

# In production: load chunks from your ingestion/indexing pipeline instead of hardcoding.
DEMO_CHUNKS = [
    Chunk(chunk_id="c1", doc_id="doc-1", page=4, section="§2.1",
          text="The hybrid retrieval pipeline combines dense embedding similarity "
               "with sparse keyword search to select the top-k most relevant chunks."),
    Chunk(chunk_id="c2", doc_id="doc-1", page=7, section="§3.3",
          text="Every factual response must include clickable citations that "
               "deep-link the viewer and highlight the exact bounding box on the page."),
    Chunk(chunk_id="c3", doc_id="doc-1", page=9, section="§4.0",
          text="When a user query falls outside the scope of the ingested corpus, "
               "the system returns a standardized fallback notice instead of speculating."),
]

bot = RAGChatbot(DEMO_CHUNKS)


@app.get("/chat/stream")
def chat_stream(q: str):
    """Server-Sent Events endpoint. Each `data:` line is one token/chunk."""

    def event_generator():
        for token in bot.ask_stream(q):
            # SSE frames must be newline-terminated and prefixed with "data: "
            yield f"data: {token}\n\n"
        yield "event: done\ndata: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.websocket("/chat/ws")
async def chat_ws(websocket: WebSocket):
    """WebSocket alternative to the SSE endpoint above."""
    await websocket.accept()
    try:
        while True:
            query = await websocket.receive_text()
            for token in bot.ask_stream(query):
                await websocket.send_text(token)
            await websocket.send_json({"event": "done"})
    except Exception:
        await websocket.close()