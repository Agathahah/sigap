"""Data lineage for raw downloads: checksums, row counts and the licence in one manifest.

Every downstream result can be traced back to the exact raw files it was built from. `verify` fails loudly
when a raw file changes after the manifest was written.

Run:  make data-manifest LICENCE="..."   (after make data-download)
      make data-verify
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    """Hex SHA-256 of a file, read in chunks so large CSVs never sit in memory at once."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def count_rows(path: Path) -> int:
    """Number of data rows in a CSV (header excluded). Streams the file; an empty file has 0 rows."""
    with open(path, "rb") as f:
        lines = sum(1 for _ in f)
    return max(lines - 1, 0)


def build_manifest(files: list[Path], source: str, licence: str) -> dict:
    """Describe raw files: source, licence, creation time and per-file bytes, rows and checksum."""
    entries = [
        {"name": p.name, "bytes": p.stat().st_size, "rows": count_rows(p), "sha256": sha256_file(p)}
        for p in sorted(files, key=lambda p: p.name)
    ]
    return {
        "source": source,
        "licence": licence,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "files": entries,
    }


def verify_manifest(manifest: dict, base_dir: Path) -> list[str]:
    """Problems found when comparing the manifest with files on disk ("missing: x", "changed: x")."""
    problems = []
    for entry in manifest["files"]:
        path = base_dir / entry["name"]
        if not path.exists():
            problems.append(f"missing: {entry['name']}")
        elif sha256_file(path) != entry["sha256"]:
            problems.append(f"changed: {entry['name']}")
    return problems


def main() -> None:
    """CLI: `python -m sigap.ingest.manifest build|verify`."""
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
        path.write_text(json.dumps(m, indent=2), encoding="utf-8")
        for f in m["files"]:
            print(f"{f['name']}: {f['rows']:,} rows, sha256 {f['sha256'][:12]}…")
        print(f"-> {path}")
    else:
        problems = verify_manifest(json.loads(path.read_text(encoding="utf-8")), config.RAW)
        if problems:
            raise SystemExit("Manifest check FAILED:\n  " + "\n  ".join(problems))
        print("OK: raw files match the manifest")


if __name__ == "__main__":
    main()
