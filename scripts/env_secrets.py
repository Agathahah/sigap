"""Replace every `change-me` value in .env with a random secret: `make env-secrets`.

Postgres keeps the password it was created with in its Docker volume; editing .env alone would lock SIGAP out.
So the database password is changed first (ALTER ROLE inside the running container), and .env is rewritten only
after that succeeded. SIGAP_DB_URL gets the same new password. No secret is printed.
"""

from __future__ import annotations

import re
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
URL_PASSWORD = re.compile(r"^(postgresql(?:\+psycopg)?://[^:/@]+:)([^@]*)(@.*)$")


def read_env(path: Path) -> list[str]:
    if not path.exists():
        raise SystemExit(".env not found. Run: cp .env.example .env")
    return path.read_text(encoding="utf-8").splitlines()


def parse(lines: list[str]) -> dict[str, str]:
    out = {}
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            out[key.strip()] = value.strip()
    return out


def new_secret() -> str:
    """URL-safe characters only (A-Z a-z 0-9 - _): safe inside a database URL and inside the Makefile include."""
    return secrets.token_urlsafe(24)


def alter_db_password(user: str, db: str, password: str) -> None:
    sql = f"ALTER ROLE \"{user}\" PASSWORD '{password}';\n"
    cmd = ["docker", "compose", "exec", "-T", "postgres", "psql", "-U", user, "-d", db, "-v", "ON_ERROR_STOP=1", "-q"]
    result = subprocess.run(cmd, cwd=ROOT, input=sql, text=True, capture_output=True)  # noqa: S603
    if result.returncode != 0:
        raise SystemExit(f"Could not change the database password (is `make db-up` running?):\n{result.stderr}")


def rotate(lines: list[str], new_values: dict[str, str]) -> list[str]:
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        out.append(f"{key}={new_values[key]}" if key in new_values else line)
    return out


def main() -> int:
    lines = read_env(ENV)
    env = parse(lines)
    weak = [k for k, v in env.items() if "change-me" in v]
    if not weak:
        print(".env has no change-me values. Nothing to do.")
        return 0

    new_values = {k: new_secret() for k in weak if k != "SIGAP_DB_URL"}
    if "POSTGRES_PASSWORD" in new_values or "SIGAP_DB_URL" in weak:
        password = new_values.setdefault("POSTGRES_PASSWORD", env.get("POSTGRES_PASSWORD", ""))
        url = env.get("SIGAP_DB_URL", "")
        m = URL_PASSWORD.match(url)
        if not m:
            raise SystemExit("SIGAP_DB_URL is not of the form postgresql+psycopg://user:password@host:port/db")
        new_values["SIGAP_DB_URL"] = m.group(1) + password + m.group(3)
        alter_db_password(env.get("POSTGRES_USER", "sigap"), env.get("POSTGRES_DB", "sigap"), password)
        print("database password changed inside the container")

    ENV.write_text("\n".join(rotate(lines, new_values)) + "\n", encoding="utf-8")
    print(f".env updated: {', '.join(sorted(new_values))} (values not shown)")
    print("Next: make db-up   (recreates the container with the new .env; data stays in the volume)")
    print("      make doctor  (the .env line and 'Postgres reachable' should both be OK)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
