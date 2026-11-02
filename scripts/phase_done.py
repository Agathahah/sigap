"""Mark a phase as finished in tests/PHASES_DONE. Provided (plumbing).

CI runs `pytest -m "<markers>"` with the markers on ONE line joined by " or " (e.g. "p1 or p2 or p8b").
Editing that line by hand is easy to get wrong ("p1p2" breaks CI), so:

    make phase-done P=1      # adds p1
    make phase-done P=8b     # adds p8b

Run it only after `make check P=<n>` is green: from then on CI protects that phase.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

FILE = Path(__file__).resolve().parents[1] / "tests" / "PHASES_DONE"
VALID = re.compile(r"^p(1[01]|[0-9])b?$")


def main(phase: str) -> None:
    marker = phase if phase.startswith("p") else f"p{phase}"
    if not VALID.match(marker):
        sys.exit(f"unknown phase '{phase}': use 1..11, 8b or 9b")
    lines = FILE.read_text(encoding="utf-8").splitlines()
    comments = [ln for ln in lines if ln.lstrip().startswith("#")]
    current = [m for ln in lines if not ln.lstrip().startswith("#") for m in re.findall(r"p\d+b?", ln)]
    if marker in current:
        print(f"{marker} is already in {FILE.name}: {' or '.join(current)}")
        return
    order = lambda m: (int(re.sub(r"\D", "", m)), m.endswith("b"))  # noqa: E731
    markers = sorted(set(current + [marker]), key=order)
    FILE.write_text("\n".join(comments + [" or ".join(markers)]) + "\n", encoding="utf-8")
    print(f"{FILE.name}: {' or '.join(markers)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
