"""RAG vector store — per-company Qdrant collections with local FastEmbed embeddings.

Each company gets its own collection ("company_{id}") so data never crosses company
boundaries regardless of how many companies share the same Looper install.

All Qdrant calls are synchronous; use asyncio.to_thread() when calling from async routes.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import DATA_DIR

logger = logging.getLogger("looper.rag")

QDRANT_PATH = DATA_DIR / "qdrant"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"  # 384-dim, ~130 MB one-time download
EMBED_DIM = 384
CHUNK_SIZE = 1000   # characters
CHUNK_OVERLAP = 150

_client = None

SUPPORTED_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx",
    ".html", ".css", ".json", ".yaml", ".yml", ".csv",
    ".sh", ".bat", ".ps1", ".toml", ".ini", ".cfg", ".rst",
}


# ── Client ────────────────────────────────────────────────────────────────────

def _get_client():
    global _client
    if _client is None:
        from qdrant_client import QdrantClient
        QDRANT_PATH.mkdir(parents=True, exist_ok=True)
        _client = QdrantClient(path=str(QDRANT_PATH))
        logger.info("Qdrant embedded client initialised at %s", QDRANT_PATH)
    return _client


def collection_name(company_id: int) -> str:
    return f"company_{company_id}"


def _ensure_collection(client, col: str) -> None:
    """Create the collection if it doesn't exist yet."""
    from qdrant_client import models
    try:
        client.get_collection(col)
    except Exception:
        client.create_collection(
            collection_name=col,
            vectors_config=models.VectorParams(size=EMBED_DIM, distance=models.Distance.COSINE),
        )
        logger.info("Created Qdrant collection %s", col)


# ── Text extraction ───────────────────────────────────────────────────────────

def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract plain text from a file. Raises ValueError for unsupported types."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix in SUPPORTED_EXTENSIONS:
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                return file_bytes.decode(enc)
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Could not decode {filename} as text")
    raise ValueError(
        f"Unsupported file type '{suffix}'. "
        f"Supported: .pdf, {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
    )


# ── Chunking ──────────────────────────────────────────────────────────────────

def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            for boundary in ("\n\n", "\n", " "):
                pos = text.rfind(boundary, start + size // 2, end)
                if pos != -1:
                    end = pos + len(boundary)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    return chunks


# ── Core operations (sync — use asyncio.to_thread from async callers) ─────────

def index_text(
    company_id: int,
    text: str,
    filename: str,
    source_type: str = "text",
    doc_id: str | None = None,
) -> dict[str, Any]:
    """Chunk, embed, and store text in the company's collection.

    Returns {doc_id, chunks_indexed, filename}.
    """
    doc_id = doc_id or str(uuid.uuid4())
    chunks = _chunk_text(text)
    if not chunks:
        raise ValueError("No text content to index")

    from qdrant_client import models as qm

    client = _get_client()
    col = collection_name(company_id)
    _ensure_collection(client, col)
    now = datetime.now(timezone.utc).isoformat()

    points = [
        qm.PointStruct(
            id=str(uuid.uuid4()),
            vector=qm.Document(text=chunk, model=EMBED_MODEL),
            payload={
                "doc_id": doc_id,
                "filename": filename,
                "source_type": source_type,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "company_id": company_id,
                "created_at": now,
                "text": chunk,
            },
        )
        for i, chunk in enumerate(chunks)
    ]

    client.upsert(collection_name=col, points=points)

    logger.info("Indexed '%s' → %d chunks in collection %s", filename, len(chunks), col)
    return {"doc_id": doc_id, "chunks_indexed": len(chunks), "filename": filename}


def index_file(company_id: int, file_bytes: bytes, filename: str) -> dict[str, Any]:
    """Extract text from a file and index it."""
    text = extract_text(file_bytes, filename)
    suffix = Path(filename).suffix.lower()
    source_type = "pdf" if suffix == ".pdf" else "file"
    return index_text(company_id, text, filename, source_type=source_type)


def search(
    company_id: int,
    query: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Semantic search. Returns ranked list of {text, filename, score, doc_id, chunk_index}."""
    from qdrant_client import models as qm

    client = _get_client()
    col = collection_name(company_id)

    try:
        result = client.query_points(
            collection_name=col,
            query=qm.Document(text=query, model=EMBED_MODEL),
            limit=limit,
            with_payload=True,
        )
    except Exception as exc:
        if "doesn't exist" in str(exc).lower() or "not found" in str(exc).lower():
            return []
        raise

    out = []
    for r in result.points:
        payload = r.payload or {}
        out.append({
            "text": payload.get("text", ""),
            "filename": payload.get("filename", ""),
            "doc_id": payload.get("doc_id", ""),
            "chunk_index": payload.get("chunk_index", 0),
            "total_chunks": payload.get("total_chunks", 1),
            "score": round(r.score, 4) if hasattr(r, "score") else None,
            "created_at": payload.get("created_at", ""),
        })
    return out


def delete_document(company_id: int, doc_id: str) -> int:
    """Delete all chunks belonging to a document. Returns number of points deleted."""
    from qdrant_client.models import FieldCondition, Filter, MatchValue
    client = _get_client()
    col = collection_name(company_id)
    try:
        client.delete(
            collection_name=col,
            points_selector=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
        )
        logger.info("Deleted doc_id=%s from collection %s", doc_id, col)
        return 1
    except Exception as exc:
        if "doesn't exist" in str(exc).lower() or "not found" in str(exc).lower():
            return 0
        raise


def list_documents(company_id: int) -> list[dict[str, Any]]:
    """List unique documents (grouped by doc_id) in a company's collection."""
    client = _get_client()
    col = collection_name(company_id)
    try:
        docs: dict[str, dict] = {}
        offset = None
        while True:
            records, next_offset = client.scroll(
                collection_name=col,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for record in records:
                p = record.payload or {}
                did = p.get("doc_id", "")
                if did and did not in docs:
                    docs[did] = {
                        "doc_id": did,
                        "filename": p.get("filename", ""),
                        "source_type": p.get("source_type", ""),
                        "total_chunks": p.get("total_chunks", 1),
                        "created_at": p.get("created_at", ""),
                        "company_id": p.get("company_id", company_id),
                    }
            if next_offset is None:
                break
            offset = next_offset
        return sorted(docs.values(), key=lambda d: d["created_at"], reverse=True)
    except Exception as exc:
        if "doesn't exist" in str(exc).lower() or "not found" in str(exc).lower():
            return []
        raise


def collection_stats(company_id: int) -> dict[str, int]:
    """Return {documents, chunks} counts for a company's collection."""
    docs = list_documents(company_id)
    total_chunks = sum(d.get("total_chunks", 1) for d in docs)
    return {"documents": len(docs), "chunks": total_chunks}


def delete_collection(company_id: int) -> None:
    """Wipe all RAG data for a company."""
    client = _get_client()
    col = collection_name(company_id)
    try:
        client.delete_collection(col)
        logger.info("Deleted RAG collection %s", col)
    except Exception:
        pass


# ── Async wrappers ────────────────────────────────────────────────────────────

async def async_index_text(company_id: int, text: str, filename: str, source_type: str = "text") -> dict:
    return await asyncio.to_thread(index_text, company_id, text, filename, source_type)


async def async_index_file(company_id: int, file_bytes: bytes, filename: str) -> dict:
    return await asyncio.to_thread(index_file, company_id, file_bytes, filename)


async def async_search(company_id: int, query: str, limit: int = 5) -> list[dict]:
    return await asyncio.to_thread(search, company_id, query, limit)


async def async_list_documents(company_id: int) -> list[dict]:
    return await asyncio.to_thread(list_documents, company_id)


async def async_collection_stats(company_id: int) -> dict:
    return await asyncio.to_thread(collection_stats, company_id)
