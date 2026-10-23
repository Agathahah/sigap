"""Phase 1 · Data acquisition: a manifest proves which exact files every result came from.

Run:  make data-manifest   (after make data-download)
      make data-verify     (any time; CI-style check that raw files were not changed)

Why it matters (interview): "How do you know your model was trained on the data you think it was?"
A manifest with SHA-256 checksums, row counts and the licence note is the cheapest lineage there is.
"""

from __future__ import annotations

import hashlib  # noqa: F401
import json
from datetime import UTC, datetime  # noqa: F401
from pathlib import Path


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    """Phase 1 · TODO(Agatha): return the hex SHA-256 of a file, reading it in chunks.

    Read in chunks (1 MB) so a 200 MB CSV never has to fit in memory at once.
    Hint: hashlib.sha256(); h.update(chunk); h.hexdigest().
    Test: tests/test_p1_acquisition.py::test_sha256_matches_hashlib
    """
    raise NotImplementedError("TODO(Agatha) phase 1: sigap.ingest.manifest.sha256_file")


def count_rows(path: Path) -> int:
    """Phase 1 · TODO(Agatha): number of data rows in a CSV (header excluded).

    Count lines without loading the file into pandas. An empty file has 0 rows.
    Test: tests/test_p1_acquisition.py::test_count_rows_excludes_header
    """
    raise NotImplementedError("TODO(Agatha) phase 1: sigap.ingest.manifest.count_rows")


def build_manifest(files: list[Path], source: str, licence: str) -> dict:
    """Phase 1 · TODO(Agatha): describe downloaded files.

    Return:
        {
          "source": source,                 # e.g. "kaggle:sgpjesus/bank-account-fraud-dataset-neurips-2022"
          "licence": licence,               # copied from the dataset page / `make data-licence`
          "created_at": ISO-8601 UTC string,
          "files": [{"name": file name only, "bytes": int, "rows": int, "sha256": str}, ...]  # sorted by name
        }
    Test: tests/test_p1_acquisition.py::test_manifest_fields
    """
    raise NotImplementedError("TODO(Agatha) phase 1: sigap.ingest.manifest.build_manifest")


def verify_manifest(manifest: dict, base_dir: Path) -> list[str]:
    """Phase 1 · TODO(Agatha): compare files on disk with the manifest.

    Return a list of human-readable problems, empty when everything matches:
      - "missing: <name>"           file listed but not on disk
      - "changed: <name>"           checksum differs
    Test: tests/test_p1_acquisition.py::test_verify_detects_change_and_missing
    """
    raise NotImplementedError("TODO(Agatha) phase 1: sigap.ingest.manifest.verify_manifest")


def main() -> None:
    """CLI: `python -m sigap.ingest.manifest build|verify`. Provided, uses your functions above."""
    import argparse

    from sigap import config

    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["build", "verify"])
    ap.add_argument("--licence", default="")
    args = ap.parse_args()
    path = config.RAW / "MANIFEST.json"
    if args.action == "build":
        files = sorted(config.RAW.glob("*.csv"))
        if not files:
            raise SystemExit("No CSV in data/raw. Run `make data-download` first.")
        if not args.licence:
            raise SystemExit('Pass the licence you verified: make data-manifest LICENCE="..."')
        m = build_manifest(files, f"kaggle:{config.KAGGLE_DATASET}", args.licence)
        path.write_text(json.dumps(m, indent=2))
        print(f"Wrote {path} ({len(files)} files)")
    else:
        problems = verify_manifest(json.loads(path.read_text()), config.RAW)
        print("OK: raw files match the manifest" if not problems else "\n".join(problems))
        raise SystemExit(1 if problems else 0)


if __name__ == "__main__":
    main()
