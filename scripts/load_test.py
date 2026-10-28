"""Latency of the running API: `make load-test` (start it first with `make serve` or `make docker-run`).

Sends N applications from the last landed month (as the source system sends them, sentinels included) one by one
to /v1/score and prints p50 / p95 / p99 of the round trip, the server-side latency and the error count.
Results go to reports/serve/latency.json; copy the line into docs/RUNBOOK.md with your machine's spec.
Target: p95 < 100 ms for one application.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sigap import config  # noqa: E402

N = int(os.getenv("SIGAP_LOAD_N", "500"))
URL = os.getenv("SIGAP_API_URL", "http://127.0.0.1:8000")


def sample_applications(n: int) -> pd.DataFrame:
    slug = config.VARIANT.lower().replace(" ", "_")
    months = sorted((config.DATA / "landing_valid" / slug).glob("month=*/part.csv"))
    if not months:
        raise SystemExit("no landing_valid files: run `make quality` first")
    df = pd.read_csv(months[-1]).sample(n=n, random_state=7)
    return df


def main() -> int:
    key = os.getenv("SIGAP_API_KEY")
    if not key:
        raise SystemExit("SIGAP_API_KEY is not set (run through make so .env is loaded)")
    apps = sample_applications(N)
    ids = apps.pop(config.ID).tolist()
    payloads = apps.drop(columns=[config.MONTH]).to_dict(orient="records")
    headers = {"X-API-Key": key}
    rtt, server, errors, decisions = [], [], 0, {}
    with httpx.Client(base_url=URL, timeout=5.0) as client:
        client.get("/health").raise_for_status()
        for app_id, body in zip(ids, payloads, strict=True):
            t0 = time.perf_counter()
            r = client.post("/v1/score", json=body, headers={**headers, "X-Application-Id": f"load-{app_id}"})
            rtt.append((time.perf_counter() - t0) * 1000)
            if r.status_code != 200:
                errors += 1
                continue
            out = r.json()
            server.append(out["latency_ms"])
            decisions[out["decision"]] = decisions.get(out["decision"], 0) + 1
    p = np.percentile(rtt, [50, 95, 99])
    s = np.percentile(server, [50, 95, 99]) if server else [float("nan")] * 3
    result = {
        "requests": N,
        "errors": errors,
        "round_trip_ms": {"p50": round(p[0], 1), "p95": round(p[1], 1), "p99": round(p[2], 1)},
        "server_ms": {"p50": round(s[0], 1), "p95": round(s[1], 1), "p99": round(s[2], 1)},
        "decisions": decisions,
        "url": URL,
        "machine": f"{platform.system()} {platform.machine()}, Python {platform.python_version()}",
        "measured_at": time.strftime("%Y-%m-%d %H:%M"),
    }
    out = ROOT / "reports" / "serve"
    out.mkdir(parents=True, exist_ok=True)
    (out / "latency.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"{N} requests to {URL}/v1/score, {errors} errors")
    print(f"round trip  p50 {p[0]:.1f} ms | p95 {p[1]:.1f} ms | p99 {p[2]:.1f} ms")
    print(f"server side p50 {s[0]:.1f} ms | p95 {s[1]:.1f} ms | p99 {s[2]:.1f} ms")
    print(f"decisions: {decisions}")
    print(f"target p95 < 100 ms: {'met' if p[1] < 100 else 'NOT met'} -> {out / 'latency.json'}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
