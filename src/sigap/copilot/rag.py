"""Phase 9 · Retrieval over policy documents (pgvector in the same Postgres).

Corpus (docs/policies/, public or fictional material only, never anything confidential):
  - POJK 12/2024 Penerapan Strategi Anti Fraud bagi Lembaga Jasa Keuangan (public PDF from ojk.go.id,
    `make docs-download`)
  - sop_review_pembukaan_rekening.md, the fictional review SOP of Bank Nusa Digital

Pipeline: PDF pages / Markdown sections -> chunk_text -> embeddings with a multilingual sentence-transformers
model that runs on the laptop (no document text leaves it) -> table copilot.policy_chunks
-> retrieve(question, k) by cosine distance -> the agent cites source + page (or section).

Run:  make rag-index
"""

from __future__ import annotations

import hashlib
import os
import re
from functools import lru_cache
from pathlib import Path

from sigap import config

POLICY_DIR = config.ROOT / "docs" / "policies"
EMBED_MODEL = os.getenv("SIGAP_EMBED_MODEL", "intfloat/multilingual-e5-small")
EMBED_DIM = 384  # multilingual-e5-small
SKIP_FILES = {"README.md"}


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 200) -> list[str]:
    """Split text into chunks of at most `max_chars` characters that overlap by `overlap` characters.

    Whitespace is normalized first. A chunk ends at the last ". " inside its window when that full stop lies in
    the second half of the window, so sentences stay whole; the next chunk starts `overlap` characters before
    the end of the previous one. Requires 0 <= overlap < max_chars.
    """
    if not 0 <= overlap < max_chars:
        raise ValueError(f"need 0 <= overlap < max_chars, got overlap={overlap}, max_chars={max_chars}")
    t = " ".join(text.split())
    chunks: list[str] = []
    start, n = 0, len(t)
    while start < n:
        end = min(start + max_chars, n)
        if end < n:
            stop = t.rfind(". ", start, end)
            if stop != -1 and stop + 1 - start > max_chars // 2:
                end = stop + 1
        piece = t[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


def is_pdf(path: Path) -> bool:
    """True when the file starts with the PDF signature (a rejected download often saves an HTML error page)."""
    with path.open("rb") as fh:
        return fh.read(5) == b"%PDF-"


def read_pdf_pages(path: Path) -> list[tuple[int, str]]:
    """(page number from 1, text) for every page that has extractable text."""
    from pypdf import PdfReader

    pages = []
    for i, page in enumerate(PdfReader(str(path)).pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append((i, text))
    return pages


def read_markdown_sections(path: Path) -> list[tuple[int, str]]:
    """(section number from 1, text) split on level-2 headings; text before the first heading is section 1."""
    parts = re.split(r"(?m)^## ", path.read_text(encoding="utf-8"))
    sections = [p if i == 0 else "## " + p for i, p in enumerate(parts)]
    return [(i, s) for i, s in enumerate((s for s in sections if s.strip()), start=1)]


def load_corpus(policy_dir: Path = POLICY_DIR) -> list[dict]:
    """All chunks of all documents: {"id", "source", "page", "chunk_no", "text"}. The id is stable."""
    rows = []
    for path in sorted(policy_dir.iterdir()):
        if path.name in SKIP_FILES or path.suffix.lower() not in {".pdf", ".md"}:
            continue
        if path.suffix.lower() == ".pdf" and not is_pdf(path):
            print(
                f"skipped {path.name}: not a PDF (an error page from a rejected download); see docs/policies/README.md"
            )
            continue
        units = read_pdf_pages(path) if path.suffix.lower() == ".pdf" else read_markdown_sections(path)
        for page, text in units:
            for no, chunk in enumerate(chunk_text(text)):
                key = f"{path.name}|{page}|{no}|{chunk}"
                rows.append(
                    {
                        "id": hashlib.sha1(key.encode("utf-8"), usedforsecurity=False).hexdigest()[:16],
                        "source": path.name,
                        "page": page,
                        "chunk_no": no,
                        "text": chunk,
                    }
                )
    return rows


@lru_cache(maxsize=1)
def _embedder():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBED_MODEL)


def embed(texts: list[str], kind: str) -> list[list[float]]:
    """Normalized embeddings. E5 models expect the prefix "query: " for questions and "passage: " for chunks."""
    prefix = {"query": "query: ", "passage": "passage: "}[kind]
    vectors = _embedder().encode([prefix + t for t in texts], normalize_embeddings=True, batch_size=32)
    return [v.tolist() for v in vectors]


DDL = f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS copilot;
CREATE TABLE IF NOT EXISTS copilot.policy_chunks (
    id        TEXT PRIMARY KEY,
    source    TEXT NOT NULL,
    page      INTEGER NOT NULL,       -- PDF page, or section number for Markdown
    chunk_no  INTEGER NOT NULL,
    text      TEXT NOT NULL,
    embedding vector({EMBED_DIM}) NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_policy_chunks_hnsw ON copilot.policy_chunks
    USING hnsw (embedding vector_cosine_ops);
"""


def _dsn(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def build_index(policy_dir: Path = POLICY_DIR) -> dict[str, int]:
    """Chunk, embed and store every document. Re-running replaces each source's chunks (no duplicates)."""
    import psycopg
    from pgvector.psycopg import register_vector

    rows = load_corpus(policy_dir)
    if not rows:
        raise SystemExit(f"no .pdf or .md documents in {policy_dir} (run make docs-download)")
    vectors = embed([r["text"] for r in rows], "passage")
    counts: dict[str, int] = {}
    with psycopg.connect(_dsn(config.database_url())) as conn:
        conn.execute(DDL)
        register_vector(conn)
        with conn.cursor() as cur:
            sources = sorted({r["source"] for r in rows})
            cur.execute("DELETE FROM copilot.policy_chunks WHERE source = ANY(%s)", (sources,))
            cur.executemany(
                "INSERT INTO copilot.policy_chunks (id, source, page, chunk_no, text, embedding) "
                "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
                [
                    (r["id"], r["source"], r["page"], r["chunk_no"], r["text"], vec)
                    for r, vec in zip(rows, vectors, strict=True)
                ],
            )
        conn.commit()
    for r in rows:
        counts[r["source"]] = counts.get(r["source"], 0) + 1
    return counts


def retrieve(question: str, k: int = 4, url: str | None = None) -> list[dict]:
    """Top-k chunks for a question: [{"source", "page", "text", "distance"}], nearest first (cosine)."""
    import numpy as np
    import psycopg
    from pgvector.psycopg import register_vector

    if not 1 <= k <= 10:
        raise ValueError("k must be between 1 and 10")
    vec = np.array(embed([question], "query")[0], dtype=np.float32)
    with psycopg.connect(_dsn(url or config.database_url())) as conn:
        register_vector(conn)
        rows = conn.execute(
            "SELECT source, page, text, embedding <=> %s AS distance FROM copilot.policy_chunks "
            "ORDER BY embedding <=> %s LIMIT %s",
            (vec, vec, k),
        ).fetchall()
    return [{"source": s, "page": p, "text": t, "distance": round(float(d), 4)} for s, p, t, d in rows]


def main() -> None:
    counts = build_index()
    for source, n in counts.items():
        print(f"{source}: {n} chunks")
    print(f"total {sum(counts.values())} chunks in copilot.policy_chunks (model {EMBED_MODEL})")


if __name__ == "__main__":
    main()
