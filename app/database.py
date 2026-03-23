"""
pgvector database connection and similarity search logic.
"""
import os
import logging
from typing import List, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor
from pgvector.psycopg2 import register_vector
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://acr_user:acr_pass@localhost:5432/acr_db")


def get_connection():
    """Create and return a new psycopg2 connection with pgvector registered."""
    conn = psycopg2.connect(DATABASE_URL)
    register_vector(conn)
    return conn


def create_schema() -> None:
    """
    Initialize the pgvector schema.
    Creates the vector extension and technical_docs table if they don't exist.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS technical_docs (
                    id          SERIAL PRIMARY KEY,
                    content     TEXT NOT NULL,
                    metadata    JSONB DEFAULT '{}',
                    embedding   VECTOR(768)
                );
            """)
            # IVFFlat index for fast ANN search on large datasets
            cur.execute("""
                CREATE INDEX IF NOT EXISTS technical_docs_embedding_idx
                ON technical_docs
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
            """)
        conn.commit()
        logger.info("Schema created / verified OK.")
    finally:
        conn.close()


def insert_document(content: str, metadata: dict, embedding: List[float]) -> int:
    """
    Insert a document and its embedding into the technical_docs table.
    Returns the new row id.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO technical_docs (content, metadata, embedding)
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (content, psycopg2.extras.Json(metadata), embedding),
            )
            row_id = cur.fetchone()[0]
        conn.commit()
        return row_id
    finally:
        conn.close()


def query_similar_docs(
    embedding: List[float], top_k: int = 5
) -> List[Tuple[str, dict, float]]:
    """
    Perform cosine similarity search against stored embeddings.

    Returns a list of (content, metadata, similarity_score) tuples,
    ordered by descending similarity.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT content, metadata,
                       1 - (embedding <=> %s::vector) AS score
                FROM   technical_docs
                ORDER  BY embedding <=> %s::vector
                LIMIT  %s;
                """,
                (embedding, embedding, top_k),
            )
            rows = cur.fetchall()
        return [(r["content"], r["metadata"], r["score"]) for r in rows]
    finally:
        conn.close()
