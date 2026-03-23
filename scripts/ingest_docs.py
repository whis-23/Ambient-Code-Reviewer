"""
RAG Ingestion Script — Ambient Code Reviewer
============================================
Loads Markdown/text documents from the `docs/` directory,
generates embeddings (local sentence-transformers by default),
and upserts them into the pgvector `technical_docs` table.

Usage:
    python -m scripts.ingest_docs [--docs-dir docs/]
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "gemini")
GOOGLE_API_KEY     = os.getenv("GOOGLE_API_KEY", "")

SUPPORTED_EXTENSIONS = {".md", ".txt", ".rst"}


# ─────────────── Embedding ───────────────────────────────── #
def embed_text(text: str) -> list[float]:
    """
    - gemini  → gemini-embedding-001, task_type=retrieval_document (768-dim)  [default]
    - local   → sentence-transformers all-MiniLM-L6-v2 (384-dim padded to 768)
    """
    if EMBEDDING_PROVIDER == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=GOOGLE_API_KEY)
        result = genai.embed_content(
            model="models/gemini-embedding-001",
            content=text[:8000],
            task_type="retrieval_document",   # indexing-time task type
        )
        return result["embedding"]            # 768-dim
    else:  # local fallback
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        vec = model.encode(text[:2048]).tolist()  # 384-dim
        return (vec * 2)[:768]                    # pad to 768


# ─────────────── Chunking ────────────────────────────────── #
def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping word-level chunks."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        start += chunk_size - overlap
    return chunks


# ─────────────── Ingest ──────────────────────────────────── #
def ingest_directory(docs_dir: Path) -> int:
    from app.database import create_schema, insert_document

    create_schema()
    total_inserted = 0

    files = [
        f for f in docs_dir.rglob("*")
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not files:
        logger.warning("No supported files found in %s", docs_dir)
        return 0

    logger.info("Found %d document(s) to ingest.", len(files))

    for doc_path in files:
        content = doc_path.read_text(encoding="utf-8", errors="ignore")
        title   = doc_path.stem.replace("-", " ").replace("_", " ").title()
        chunks  = chunk_text(content)

        logger.info("  ↳ %s → %d chunk(s)", doc_path.name, len(chunks))

        for i, chunk in enumerate(chunks):
            embedding = embed_text(chunk)
            metadata  = {
                "source": str(doc_path),
                "title":  title,
                "chunk":  i,
            }
            row_id = insert_document(content=chunk, metadata=metadata, embedding=embedding)
            logger.debug("    Inserted chunk %d as row #%d", i, row_id)
            total_inserted += 1

    logger.info("✅  Ingestion complete. %d chunk(s) inserted.", total_inserted)
    return total_inserted


# ─────────────── CLI ─────────────────────────────────────── #
def main():
    parser = argparse.ArgumentParser(description="Ingest documentation into pgvector.")
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=Path("docs"),
        help="Directory containing .md/.txt files to ingest (default: docs/)",
    )
    args = parser.parse_args()

    if not args.docs_dir.exists():
        logger.error("docs-dir not found: %s", args.docs_dir)
        sys.exit(1)

    ingest_directory(args.docs_dir)


if __name__ == "__main__":
    main()
