"""Checks before the repository goes public: `python scripts/release_check.py` (also part of `make review P=10`).

Looks only at what git tracks and at the commit history, so local data, models and .env are never read.
Prints one line per check and exits 1 when something must be fixed first.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNER = "Agatha Silalahi <silalahiagatha15@gmail.com>"
FORBIDDEN_FILES = re.compile(
    r"(^|/)(\.env|kaggle\.json|mlflow\.db)$|\.(csv|parquet|joblib|pkl|skops|pdf|xlsx)$|^(data|models|mlruns)/"
)
ALLOWED_FILES = {"data/README.md"}
SECRETS = {
    "Anthropic API key": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    "Meta access token": re.compile(r"EAA[A-Za-z0-9]{30,}"),
    "Gmail app password assignment": re.compile(
        r"(?i)app[_ ]?password\s*[:=]\s*[a-z]{4}\s?[a-z]{4}\s?[a-z]{4}\s?[a-z]{4}"
    ),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "Indonesian phone number": re.compile(r"(?<![\d.])(?:\+62|62|0)8\d{8,11}(?![\d])"),
}
MAX_BYTES = 5_000_000
FICTIONAL = "12345678"  # test fixtures use obviously fake numbers such as 0812-3456-7890


def git(*args: str) -> str:
    cmd = ["git", *args]
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout  # noqa: S603, S607


def checks() -> list[tuple[bool, str, str]]:
    files = [f for f in git("ls-files").splitlines() if f]
    out: list[tuple[bool, str, str]] = []

    bad = [f for f in files if FORBIDDEN_FILES.search(f) and f not in ALLOWED_FILES]
    out.append((not bad, "no data, model files, PDFs or .env tracked", ", ".join(bad[:5])))

    big = [f for f in files if (ROOT / f).is_file() and (ROOT / f).stat().st_size > MAX_BYTES]
    out.append((not big, "no tracked file over 5 MB", ", ".join(big[:5])))

    found = []
    for f in files:
        path = ROOT / f
        if not path.is_file() or path.suffix in {".png", ".jpg", ".ico"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name, pat in SECRETS.items():
            hits = [m for m in pat.findall(text) if FICTIONAL not in re.sub(r"\D", "", m)]
            found += [f"{name} in {f}"] if hits else []
    out.append(
        (
            not found,
            "no keys, tokens or phone numbers in tracked files",
            "; ".join(found[:5]),
        )
    )

    authors = set(git("log", "--format=%an <%ae>").splitlines()) | set(git("log", "--format=%cn <%ce>").splitlines())
    others = sorted(a for a in authors if a and a != OWNER and "GitHub <noreply@github.com>" not in a)
    out.append((not others, f"every commit authored by {OWNER}", ", ".join(others)))

    trailers = [ln for ln in git("log", "--format=%B").splitlines() if ln.lower().startswith("co-authored-by")]
    out.append(
        (
            not trailers,
            "no Co-Authored-By trailers in the history",
            trailers[0] if trailers else "",
        )
    )

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    out.append(
        (
            "in development" not in readme.lower(),
            "README no longer says 'in development'",
            "",
        )
    )
    out.append(
        (
            "production-ready" not in readme.lower(),
            "README makes no 'production-ready' claim",
            "",
        )
    )
    return out


def main() -> int:
    results = checks()
    print("\nSIGAP release check\n")
    for ok, what, detail in results:
        print(f"  {'OK     ' if ok else 'FIX    '}  {what}")
        if not ok and detail:
            print(f"           -> {detail}")
    failed = sum(not ok for ok, _, _ in results)
    print("\n" + ("Ready to make the repository public." if not failed else f"{failed} item(s) to fix first."))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
