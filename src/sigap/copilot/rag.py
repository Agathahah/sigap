"""Phase 9 · Retrieval over policy documents (pgvector in the same Postgres).

Corpus (docs/policies/, downloaded or written by you, never confidential material):
  - POJK 12/2024 Penerapan Strategi Anti Fraud bagi Lembaga Jasa Keuangan (public PDF from ojk.go.id)
  - your own fictional "SOP Review Fraud Pembukaan Rekening" for the fictional bank (what an analyst
    checks in review, escalation rules, SLA). Writing it is part of the business learning.

Pipeline: PDF/MD -> text -> chunk_text -> embeddings (multilingual sentence-transformers model,
runs locally, no data leaves the laptop) -> table policy_chunks(id, source, page, text, embedding vector)
-> retrieve(question, k) by cosine distance -> the agent cites source + page.

Run:  make rag-index
"""

from __future__ import annotations


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 200) -> list[str]:
    """Phase 9 · TODO(Agatha): split text into overlapping chunks.

    - Normalize whitespace first (collapse runs of spaces/newlines to one space, strip).
    - Each chunk has at most max_chars characters; consecutive chunks overlap by `overlap` characters
      (chunk i+1 starts at start_i + max_chars - overlap).
    - Prefer to end a chunk at the last ". " inside the window if it is in the second half of the window
      (keeps sentences whole); then the next chunk starts at (that end - overlap).
    - Empty text -> []. Require 0 <= overlap < max_chars (else ValueError).
    Tests: tests/test_p9_copilot.py::test_chunk_*
    """
    raise NotImplementedError("TODO(Agatha) phase 9: sigap.copilot.rag.chunk_text")


def build_index() -> None:
    """Phase 9 · TODO(Agatha): read docs/policies/*, chunk, embed, upsert into Postgres policy_chunks.

    Use `CREATE EXTENSION IF NOT EXISTS vector;` and an HNSW or IVFFlat index on the embedding column.
    Store source file name and page number for citations. Re-running must not duplicate chunks.
    """
    raise NotImplementedError("TODO(Agatha) phase 9: copilot.rag.build_index")


def retrieve(question: str, k: int = 4) -> list[dict]:
    """Phase 9 · TODO(Agatha): top-k chunks [{"source", "page", "text", "distance"}] for a question."""
    raise NotImplementedError("TODO(Agatha) phase 9: copilot.rag.retrieve")


if __name__ == "__main__":
    build_index()
