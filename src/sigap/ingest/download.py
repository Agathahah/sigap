"""Phase 1 · Data acquisition: download BAF from Kaggle into data/raw.

Before running:
  1. Kaggle account -> Settings -> API -> Create New Token -> ~/.kaggle/kaggle.json (chmod 600).
  2. `make data-licence` and read the licence. Write it in docs/02_DATA_CARD.md. If the licence
     does not allow redistribution, raw rows NEVER go to GitHub (data/ is git-ignored).

Run:  make data-download              (Base.csv only, ~200 MB)
      make data-download FILES="Base.csv,Variant II.csv"
"""

from __future__ import annotations

import argparse
import subprocess
import zipfile
from pathlib import Path

from sigap import config


def kaggle_download_cmd(dataset: str, file_name: str, dest: Path) -> list[str]:
    """Phase 1 · TODO(Agatha): build the Kaggle CLI command (a list of strings, no shell).

    The command must download ONE file of the dataset into `dest`:
        kaggle datasets download -d <dataset> -f <file_name> -p <dest>
    Why a list and not one string: no shell=True, so a file name with a space
    ("Variant I.csv") cannot break or inject into the command.
    Check the CLI on your Mac: `kaggle datasets download --help`.
    Test: tests/test_p1_acquisition.py::test_kaggle_cmd_is_a_safe_list
    """
    raise NotImplementedError("TODO(Agatha) phase 1: sigap.ingest.download.kaggle_download_cmd")


def unzip_if_needed(dest: Path) -> list[Path]:
    """Kaggle may deliver `<file>.zip`. Extract every zip in dest, delete the zip, return CSV paths. Provided."""
    for z in dest.glob("*.zip"):
        with zipfile.ZipFile(z) as zf:
            zf.extractall(dest)
        z.unlink()
    return sorted(dest.glob("*.csv"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", default="Base.csv", help="comma separated, e.g. 'Base.csv,Variant I.csv'")
    args = ap.parse_args()
    config.RAW.mkdir(parents=True, exist_ok=True)
    for name in [f.strip() for f in args.files.split(",") if f.strip()]:
        cmd = kaggle_download_cmd(config.KAGGLE_DATASET, name, config.RAW)
        print("$", " ".join(cmd))
        subprocess.run(cmd, check=True)  # noqa: S603 (no shell, fixed executable)
    for p in unzip_if_needed(config.RAW):
        print(f"{p.name}: {p.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
