"""Environment check. Provided (plumbing, not a phase task).

Checks the TOOLS each phase needs, never your phase code. Run it before starting a phase:

    make doctor            # everything needed up to the current phase (P, default 0)
    make doctor P=3        # tools for phases 0-3 (Java 17, Docker, Postgres, Kaggle, ...)
    make doctor P=3 SPARK=1  # also starts a real SparkSession (slower, ~20 s)

Each line: OK / MISSING / SKIP, the phase that first needs it, and what to do.
Exit code 1 if something needed up to phase P is missing, so you can trust a green run.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS: list[tuple[str, str, float, str]] = []


def run(cmd: list[str], timeout: int = 20) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)  # noqa: S603 (fixed commands)
        return p.returncode, (p.stdout + p.stderr).strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return 127, str(e)


def check(name: str, phase: float, ok: bool | None, fix: str) -> None:
    status = "SKIP" if ok is None else ("OK" if ok else "MISSING")
    RESULTS.append((status, name, phase, "" if ok else fix))


def env_file() -> dict[str, str]:
    f = ROOT / ".env"
    if not f.exists():
        return {}
    out = {}
    for line in f.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def main(max_phase: float, spark: bool) -> int:
    # ---- phase 0: basics
    check(
        "Python 3.12 in .venv",
        0,
        sys.version_info[:2] == (3, 12) and ".venv" in sys.executable,
        "run `make setup` (with conda deactivated) and use .venv/bin/python",
    )
    env = env_file()
    check(".env exists", 0, bool(env), "cp .env.example .env")
    weak = [k for k, v in env.items() if "change-me" in v]
    check(
        ".env has no 'change-me' values",
        0,
        bool(env) and not weak,
        f"replace with secrets.token_urlsafe(24): {', '.join(weak) or '(create .env first)'}",
    )
    code, out = run(["git", "-C", str(ROOT), "config", "user.email"])
    own = code == 0 and "@" in out and "anthropic" not in out and "noreply" not in out
    check(
        f"git identity in repo ({out or 'not set'})",
        0,
        own,
        'git config user.name "Agatha Silalahi" && git config user.email "silalahiagatha15@gmail.com"',
    )
    code, out = run(["gh", "auth", "status"])
    check("GitHub CLI logged in", 0, code == 0, "brew install gh && gh auth login")
    code, out = run(["docker", "info", "--format", "{{.ServerVersion}}"])
    check("Docker Desktop running", 0, code == 0, "open -a Docker, wait until the whale icon is steady")

    # Postgres from the host, with the password in .env (what your Python code will use)
    url = os.getenv("SIGAP_DB_URL") or env.get("SIGAP_DB_URL")
    pg_ok: bool | None = None
    fix = "make db-up; if 'password authentication failed': ALTER USER sigap WITH PASSWORD '<POSTGRES_PASSWORD>'"
    if url:
        try:
            from sqlalchemy import create_engine, text

            with create_engine(url, connect_args={"connect_timeout": 5}).connect() as c:
                pg_ok = c.execute(text("select 1")).scalar() == 1
        except Exception as e:  # noqa: BLE001
            pg_ok, fix = False, f"{type(e).__name__}: {str(e).splitlines()[0][:120]} -> {fix}"
    check("Postgres reachable with SIGAP_DB_URL", 0, pg_ok, fix)

    # ---- phase 1: Kaggle
    kj = Path.home() / ".kaggle" / "kaggle.json"
    check(
        "Kaggle token ~/.kaggle/kaggle.json (chmod 600)",
        1,
        kj.exists() and oct(kj.stat().st_mode)[-3:] == "600",
        "kaggle.com -> Settings -> API -> Create New Token; mv to ~/.kaggle/; chmod 600",
    )

    # ---- phase 3: Java 17 (+ optional Spark start)
    code, out = run(["java", "-version"])
    m = re.search(r'version "(\d+)', out)
    check(
        f"Java 17 for Spark (found {m.group(1) if m else 'none'})",
        3,
        bool(m) and m.group(1) == "17",
        "brew install openjdk@17; in ~/.zshrc: export JAVA_HOME=$(/usr/libexec/java_home -v 17); new terminal",
    )
    if spark:
        try:
            sys.path.insert(0, str(ROOT / "src"))
            from sigap.spark import get_spark

            s = get_spark("doctor", shuffle_partitions=1)
            ok = s.range(10).count() == 10
            s.stop()
            check("SparkSession starts and counts", 3, ok, "")
        except Exception as e:  # noqa: BLE001
            check("SparkSession starts and counts", 3, False, f"{type(e).__name__}: {str(e)[:120]}")
    else:
        check("SparkSession starts (add SPARK=1)", 3, None, "")

    # ---- phase 5: MLflow
    try:
        import mlflow

        check(f"MLflow {mlflow.__version__} importable", 5, True, "")
    except ImportError:
        check("MLflow importable", 5, False, "make setup")
    try:
        import xgboost

        check(f"XGBoost {xgboost.__version__} loads (OpenMP runtime found)", 5, True, "")
    except ImportError:
        check("XGBoost installed", 5, False, "make setup")
    except Exception as e:  # noqa: BLE001 - XGBoostError when libomp is missing on macOS
        hint = "brew install libomp" if "libomp" in str(e) else f"{type(e).__name__}: {str(e)[:120]}"
        check("XGBoost loads (OpenMP runtime found)", 5, False, hint)

    # ---- phase 8b: n8n image
    code, out = run(["docker", "images", "-q", "docker.n8n.io/n8nio/n8n"])
    check("n8n image pulled", 8.5, code == 0 and bool(out), "make n8n-up (pulls the image the first time)")
    wa_ok = bool(env.get("SIGAP_ANALYST_WHATSAPP")) and bool(env.get("SIGAP_WA_PHONE_NUMBER_ID"))
    check(
        "WhatsApp values in .env",
        8.5,
        wa_ok,
        "after Meta setup (guide E8): SIGAP_ANALYST_WHATSAPP, SIGAP_WA_PHONE_NUMBER_ID",
    )

    # ---- phase 9 / 9b
    check("ANTHROPIC_API_KEY in .env", 9, bool(env.get("ANTHROPIC_API_KEY")), "console.anthropic.com -> API Keys")
    try:
        import langgraph  # noqa: F401

        check("langgraph installed (agent tests)", 9, True, "")
    except ImportError:
        check("langgraph installed (agent tests)", 9, False, "make setup (requirements-dev has it)")
    check("ollama installed", 9.5, shutil.which("ollama") is not None, "brew install ollama")

    # ---- report
    label = {0: "0", 1: "1", 3: "3", 5: "5", 8.5: "8b", 9: "9", 9.5: "9b"}
    missing_now = 0
    print(f"\nSIGAP doctor · tools needed up to phase {label.get(max_phase, max_phase)}\n")
    for status, name, phase, fix in RESULTS:
        if phase > max_phase:
            status = "later" if status != "OK" else "OK"
        if status == "MISSING":
            missing_now += 1
        print(f"  {status:<8} [fase {label.get(phase, phase):>2}] {name}")
        if fix and status == "MISSING":
            print(f"           -> {fix}")
    summary = "Semua alat untuk fase ini siap." if not missing_now else f"{missing_now} hal perlu dibereskan dulu."
    print("\n" + summary)
    print("Ingat: doctor hanya mengecek ALAT. Kode fase dicek dengan `make check P=n`.\n")
    return 1 if missing_now else 0


if __name__ == "__main__":
    p = os.getenv("P", "0").lower().replace("8b", "8.5").replace("9b", "9.5")
    sys.exit(main(float(p), os.getenv("SPARK") == "1"))
