"""Download BAF files from Kaggle into data/raw.

Requires a Kaggle API token in ~/.kaggle/kaggle.json (chmod 600). The dataset licence is CC BY-NC-SA 4.0,
so raw rows stay out of version control (data/ is git-ignored).

Run:  make data-download              (Base.csv only, ~200 MB)
      make data-download FILES="Base.csv,Variant II.csv"
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from sigap import config


def kaggle_download_cmd(dataset: str, file_name: str, dest: Path) -> list[str]:
    """Kaggle CLI command that downloads one file of a dataset into `dest`.

    Returned as an argument list (no shell), so file names with spaces such as "Variant I.csv" are passed
    safely and cannot be interpreted by a shell.
    """
    return ["kaggle", "datasets", "download", "-d", dataset, "-f", file_name, "-p", str(dest)]


def kaggle_executable() -> str:
    """Path of the Kaggle CLI: the one installed in the project venv, else the one on PATH.

    `make` runs `.venv/bin/python` without activating the venv, so `.venv/bin` is not on PATH and a bare
    "kaggle" would not be found.
    """
    local = Path(sys.executable).with_name("kaggle")
    if local.exists():
        return str(local)
    found = shutil.which("kaggle")
    if found:
        return found
    raise SystemExit("Kaggle CLI not found. Run `make setup` (it installs kaggle into .venv).")


def unzip_if_needed(dest: Path) -> list[Path]:
    """Kaggle may deliver `<file>.zip`: extract every zip in dest, delete the zip, return the CSV paths."""
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
        cmd[0] = kaggle_executable()
        print("$", " ".join(cmd))
        subprocess.run(cmd, check=True)  # noqa: S603 (no shell, fixed executable)
    for p in unzip_if_needed(config.RAW):
        print(f"{p.name}: {p.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
