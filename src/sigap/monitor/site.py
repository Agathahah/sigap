"""Phase 8 · Public monitoring page: a static snapshot of the monthly replay, published with GitHub Pages.

Two steps, so the published page never needs a database:

    make site-data   monitoring views + policy report -> site/data/monitoring.json (monthly aggregates only)
    make site        site/data/monitoring.json -> site/index.html (standard library, inline SVG, no scripts)

Both files are committed. `.github/workflows/pages.yml` publishes the `site/` folder, and a test checks that the
committed page is exactly what the committed snapshot builds, so the page can never drift from its data.
"""

from __future__ import annotations

import csv
import datetime as dt
import html
import json
import sys
from pathlib import Path
from string import Template

from sigap import config

SITE = config.ROOT / "site"
SNAPSHOT = SITE / "data" / "monitoring.json"
PAGE = SITE / "index.html"
REPO_URL = "https://github.com/Agathahah/sigap"
PSI_WATCH = 0.10  # rule of thumb used by ops.v_feature_drift: < 0.10 stable, 0.10-0.25 watch, >= 0.25 alert
TOP_DRIFT = 5
KPI_COLUMNS = (
    "applications",
    "approve_rate",
    "review_rate",
    "decline_rate",
    "reviews_per_day",
    "score_psi",
    "max_feature_psi",
    "recall_at_threshold",
    "fpr",
    "fpr_ratio_age",
    "fraud_rate_labelled",
    "retrain_flag",
)
POLICY_ARMS = {
    "champion_rules": "Rules (champion)",
    "challenger_model": "Model + bands, decline cap 1% (chosen)",
    "challenger_no_decline_cap": "Model + bands, no decline cap",
}


# ---------------------------------------------------------------- snapshot
def _num(v):
    return None if v is None else float(v)


def shape_snapshot(
    kpi_rows: list[dict],
    drift_rows: list[dict],
    policy_rows: list[dict],
    policy_meta: dict,
    business: dict,
    gate: dict,
    ops: dict,
    generated: str,
) -> dict:
    """Pure function: database rows and config -> the JSON snapshot behind the page."""
    months = []
    for r in sorted(kpi_rows, key=lambda r: int(r["month"])):
        if not r.get("applications"):
            continue  # months without a replay (labels only) are not shown on their own
        months.append({"month": int(r["month"]), **{c: _num(r.get(c)) for c in KPI_COLUMNS}})
    shown = {m["month"] for m in months}
    drift = []
    for month in sorted(shown):
        rows = [r for r in drift_rows if int(r["month"]) == month and r["feature"] != "score"]
        rows.sort(key=lambda r: float(r["psi"]), reverse=True)
        drift += [
            {"month": month, "feature": r["feature"], "psi": float(r["psi"]), "status": r["status"]}
            for r in rows[:TOP_DRIFT]
        ]
    policy = []
    for r in policy_rows:
        if r["arm"] not in POLICY_ARMS:
            continue
        n = float(r["n"])
        policy.append(
            {
                "arm": r["arm"],
                "label": POLICY_ARMS[r["arm"]],
                "n": int(n),
                "review_rate": float(r["review_rate"]),
                "decline_rate": float(r["decline"]) / n,
                "fraud_stopped_rate": float(r["fraud_stopped_rate"]),
                "good_declined_per_10k": float(r["good_declined"]) / n * 10_000,
                "cost_per_10k": float(r["cost_per_10k"]),
                "analysts_needed": int(float(r["analysts_needed"])),
            }
        )
    return {
        "generated": generated,
        "variant": config.VARIANT,
        "model_version": policy_meta.get("model_version", ""),
        "thresholds": {
            "review_capacity_per_day": float(business["review_capacity_per_day"]),
            "applications_per_day": float(business.get("applications_per_day", 0)),
            "queue_tolerance": float(ops.get("queue_tolerance", 0.10)),
            "psi_watch": PSI_WATCH,
            "psi_alert": float(ops.get("psi_alert", 0.25)),
            "recall_min": float(gate["min"]["test_tpr_at_5fpr"]),
            "fpr_ratio_age_min": float(gate["min"]["test_fpr_ratio_age"]),
            "max_decline_rate": float(policy_meta.get("max_decline_rate", 0.01)),
        },
        "months": months,
        "drift": drift,
        "policy_period": "months 6-7",
        "policy": policy,
    }


def export_snapshot(dsn: str | None = None, path: Path = SNAPSHOT) -> dict:
    """Read the monitoring views (make replay + make monitor-views first) and write the snapshot."""
    import psycopg
    from psycopg.rows import dict_row

    slug = config.VARIANT.lower().replace(" ", "_")
    url = (dsn or config.database_url()).replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(url, row_factory=dict_row) as conn:
        kpis = conn.execute("SELECT * FROM ops.v_monthly_kpis ORDER BY month").fetchall()
        drift = conn.execute("SELECT month, feature, psi, status FROM ops.v_feature_drift").fetchall()
    with (config.REPORTS / "policy" / f"champion_challenger_{slug}.csv").open(encoding="utf-8") as fh:
        policy_rows = list(csv.DictReader(fh))
    policy_meta = json.loads((config.REPORTS / "policy" / f"{slug}_policy.json").read_text(encoding="utf-8"))
    snap = shape_snapshot(
        kpis,
        drift,
        policy_rows,
        policy_meta,
        config.load_yaml("business"),
        config.load_yaml("gate"),
        config.load_yaml("ops"),
        generated=dt.date.today().isoformat(),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=1) + "\n", encoding="utf-8")
    return snap


# ---------------------------------------------------------------- formatting
def pct(x: float | None, digits: int = 2) -> str:
    return "–" if x is None else f"{x * 100:.{digits}f}%"


def dec(x: float | None, digits: int = 3) -> str:
    return "–" if x is None else f"{x:.{digits}f}"


def rupiah_millions(x: float) -> str:
    return f"Rp {x / 1e6:,.1f} m"


def psi_status(v: float, t: dict) -> str:
    return "alert" if v >= t["psi_alert"] else "watch" if v >= t["psi_watch"] else "stable"


def pill(text: str, kind: str) -> str:
    return f'<span class="pill {kind}">{html.escape(text)}</span>'


# ---------------------------------------------------------------- charts (inline SVG)
W, W_SMALL, H, PAD_L, PAD_R, PAD_T, PAD_B = 560, 380, 220, 44, 12, 22, 34


def _y(v: float, top: float) -> float:
    return PAD_T + (1 - v / top) * (H - PAD_T - PAD_B)


def _grid(top: float, ticks: list[float], fmt, w: int = W) -> str:
    out = []
    for t in ticks:
        y = _y(t, top)
        out.append(f'<line class="grid" x1="{PAD_L}" x2="{w - PAD_R}" y1="{y:.1f}" y2="{y:.1f}"/>')
        out.append(f'<text class="tick" x="{PAD_L - 6}" y="{y + 4:.1f}" text-anchor="end">{fmt(t)}</text>')
    return "".join(out)


def _hline(v: float, top: float, cls: str, w: int = W) -> str:
    y = _y(v, top)
    return f'<line class="{cls}" x1="{PAD_L}" x2="{w - PAD_R}" y1="{y:.1f}" y2="{y:.1f}"/>'


def legend(items: list[tuple[str, str]]) -> str:
    """items: (css class of the swatch, text). Classes: score, feature, bar, limit, limit soft, line."""
    spans = "".join(f'<span><i class="sw {cls}"></i>{html.escape(text)}</span>' for cls, text in items)
    return f'<div class="legend">{spans}</div>'


def _svg(body: str, label: str, w: int = W) -> str:
    return (
        f'<svg viewBox="0 0 {w} {H}" role="img" aria-label="{html.escape(label)}" '
        f'preserveAspectRatio="xMidYMid meet">{body}</svg>'
    )


def chart_reviews(months: list[dict], t: dict) -> str:
    cap = t["review_capacity_per_day"]
    tol = cap * (1 + t["queue_tolerance"])
    vals = [m["reviews_per_day"] or 0 for m in months]
    top = max([*vals, tol]) * 1.15
    step = 100 if top > 300 else 50
    ticks = [i * step for i in range(int(top // step) + 1)]
    n = len(months)
    slot = (W - PAD_L - PAD_R) / max(n, 1)
    bw = min(64, slot * 0.5)
    parts = [_grid(top, ticks, lambda v: f"{v:.0f}")]
    for i, (m, v) in enumerate(zip(months, vals, strict=True)):
        x = PAD_L + slot * i + (slot - bw) / 2
        y = _y(v, top)
        cls = "bar over" if v > cap else "bar"
        parts.append(f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{_y(0, top) - y:.1f}"/>')
        parts.append(f'<text class="val" x="{x + bw / 2:.1f}" y="{y - 6:.1f}" text-anchor="middle">{v:.0f}</text>')
        parts.append(
            f'<text class="tick" x="{x + bw / 2:.1f}" y="{H - 12}" text-anchor="middle">month {m["month"]}</text>'
        )
    parts.append(_hline(cap, top, "limit"))
    parts.append(_hline(tol, top, "limit soft"))
    key = legend(
        [
            ("bar", "within capacity"),
            ("over", "over capacity"),
            ("limit", f"capacity {cap:.0f}/day"),
            ("limit soft", f"alert above {tol:.0f}/day"),
        ]
    )
    return key + _svg("".join(parts), "Reviews per day by month against the review capacity")


def chart_psi(months: list[dict], t: dict) -> str:
    vals = [(m["score_psi"] or 0, m["max_feature_psi"] or 0) for m in months]
    top = max([v for pair in vals for v in pair] + [t["psi_alert"]]) * 1.25
    ticks = [round(i * 0.1, 1) for i in range(int(top / 0.1) + 1)]
    n = len(months)
    slot = (W - PAD_L - PAD_R) / max(n, 1)
    bw = min(34, slot * 0.28)
    parts = [_grid(top, ticks, lambda v: f"{v:.1f}")]
    for i, (m, (s, f)) in enumerate(zip(months, vals, strict=True)):
        x0 = PAD_L + slot * i + slot / 2 - bw - 3
        for j, (v, cls) in enumerate(((s, "bar score"), (f, "bar feature"))):
            x = x0 + j * (bw + 6)
            y = _y(v, top)
            parts.append(
                f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{_y(0, top) - y:.1f}"/>'
            )
            parts.append(f'<text class="val" x="{x + bw / 2:.1f}" y="{y - 6:.1f}" text-anchor="middle">{v:.2f}</text>')
        parts.append(
            f'<text class="tick" x="{PAD_L + slot * i + slot / 2:.1f}" y="{H - 12}" text-anchor="middle">'
            f"month {m['month']}</text>"
        )
    parts.append(_hline(t["psi_alert"], top, "limit"))
    parts.append(_hline(t["psi_watch"], top, "limit soft"))
    key = legend(
        [
            ("score", "model score"),
            ("feature", "largest single feature"),
            ("limit", f"alert {t['psi_alert']:.2f}"),
            ("limit soft", f"watch {t['psi_watch']:.2f}"),
        ]
    )
    return key + _svg("".join(parts), "Score PSI and largest feature PSI by month")


def chart_line(months: list[dict], key: str, limit: float, limit_label: str, label: str) -> str:
    pts = [(m["month"], m[key]) for m in months if m.get(key) is not None]
    top = 1.0
    ticks = [0.0, 0.25, 0.5, 0.75, 1.0]
    parts = [_grid(top, ticks, lambda v: f"{v:.2f}", W_SMALL)]
    parts.append(_hline(limit, top, "limit", W_SMALL))
    if pts:
        n = len(pts)
        slot = (W_SMALL - PAD_L - PAD_R) / n
        xy = [(PAD_L + slot * i + slot / 2, _y(v, top)) for i, (_, v) in enumerate(pts)]
        path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(xy))
        parts.append(f'<path class="line" d="{path}"/>')
        for (month, v), (x, y) in zip(pts, xy, strict=True):
            parts.append(f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="4.5"/>')
            parts.append(f'<text class="val" x="{x:.1f}" y="{y - 10:.1f}" text-anchor="middle">{v:.3f}</text>')
            parts.append(f'<text class="tick" x="{x:.1f}" y="{H - 12}" text-anchor="middle">month {month}</text>')
    key = legend([("line", label), ("limit", limit_label)])
    return key + _svg("".join(parts), label, W_SMALL)


# ---------------------------------------------------------------- page
CSS = """
:root{--bg:#f5f7f6;--panel:#fff;--ink:#14201b;--muted:#56645e;--line:#d8dfdc;--soft:#e9eeec;
--accent:#0d5d56;--approve:#2c7a4c;--review:#a86b12;--decline:#a83c38;--score:#0d5d56;--feature:#7a8f88}
@media (prefers-color-scheme:dark){:root{--bg:#0e1412;--panel:#141c19;--ink:#e3eae7;--muted:#98a7a1;--line:#28332f;
--soft:#1b2420;--accent:#62c4b8;--approve:#63c08a;--review:#e2a64c;--decline:#e57c74;--score:#62c4b8;--feature:#8fa39c;
color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.55 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
padding:32px max(16px,env(safe-area-inset-right,0px)) 64px max(16px,env(safe-area-inset-left,0px))}
main{max-width:980px;margin:0 auto;display:grid;gap:36px}
h1{font-size:clamp(1.7rem,4vw,2.4rem);line-height:1.15;margin:0}
h2{font-size:1.3rem;margin:0}
p{margin:0}
a{color:var(--accent)}
.eyebrow{font:600 .75rem/1 ui-monospace,Menlo,monospace;letter-spacing:.08em;text-transform:uppercase;
color:var(--muted)}
.lede{color:var(--muted);max-width:72ch}
header,section{display:grid;gap:14px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px;display:grid;gap:4px}
.tile .v{font-size:1.6rem;font-weight:650;font-variant-numeric:tabular-nums}
.tile .k{font-size:.85rem;color:var(--muted)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;display:grid;gap:12px;
min-width:0}
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
svg{width:100%;height:auto;display:block}
.grid{stroke:var(--line);stroke-width:1}
.tick{fill:var(--muted);font-size:11px}
.val{fill:var(--ink);font-size:11px;font-weight:600}
.bar{fill:var(--accent)}
.bar.over{fill:var(--review)}
.bar.score{fill:var(--score)}
.bar.feature{fill:var(--feature)}
.limit{stroke:var(--decline);stroke-width:1.5;stroke-dasharray:5 4;fill:none}
.limit.soft{stroke:var(--review)}
.legend i.sw{width:14px;height:10px}
.sw.bar{background:var(--accent)}
.sw.over{background:var(--review)}
.sw.score{background:var(--score)}
.sw.feature{background:var(--feature)}
.legend i.sw.line{background:var(--accent);height:3px;vertical-align:3px}
.legend i.sw.limit{height:0;border-radius:0;border-top:2px dashed var(--decline);vertical-align:3px}
.legend i.sw.limit.soft{border-top-color:var(--review)}
.line{fill:none;stroke:var(--accent);stroke-width:2.5}
.dot{fill:var(--panel);stroke:var(--accent);stroke-width:2.5}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:.85rem;color:var(--muted)}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.tbl{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.92rem}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:middle}
th{font-size:.75rem;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);background:var(--soft)}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.pill{font:600 .72rem/1 ui-monospace,Menlo,monospace;padding:4px 7px;border-radius:5px;white-space:nowrap}
.pill.stable,.pill.ok{background:color-mix(in srgb,var(--approve) 16%,transparent);color:var(--approve)}
.pill.watch,.pill.near{background:color-mix(in srgb,var(--review) 18%,transparent);color:var(--review)}
.pill.alert,.pill.fail{background:color-mix(in srgb,var(--decline) 15%,transparent);color:var(--decline)}
.psibar{display:inline-block;height:8px;border-radius:4px;background:var(--feature);vertical-align:middle;margin-right:8px}
code{font:.88em ui-monospace,Menlo,monospace;background:var(--soft);padding:.1em .35em;border-radius:4px}
.small{font-size:.86rem;color:var(--muted)}
.h3{font-size:1rem}
ul{margin:0;padding-left:1.2em;display:grid;gap:4px}
"""


def _tiles(months: list[dict], t: dict) -> str:
    apps = sum(m["applications"] or 0 for m in months)
    peak = max(months, key=lambda m: m["reviews_per_day"] or 0)
    last = months[-1]
    labelled = [m for m in months if m.get("fpr_ratio_age") is not None]
    ratio_txt, ratio_note = "–", "labels not arrived yet"
    if labelled:
        ratio_txt = dec(labelled[-1]["fpr_ratio_age"], 2)
        ratio_note = f"month {labelled[-1]['month']}; release limit {t['fpr_ratio_age_min']:.2f}"
    tiles = [
        (f"{apps:,.0f}", f"applications replayed (months {months[0]['month']}–{last['month']})"),
        (
            f"{peak['reviews_per_day']:.0f}/day",
            f"peak review load, month {peak['month']}; capacity {t['review_capacity_per_day']:.0f}",
        ),
        (
            dec(last["max_feature_psi"], 3),
            f"largest feature PSI, month {last['month']} ({psi_status(last['max_feature_psi'], t)})",
        ),
        (ratio_txt, f"age FPR ratio, {ratio_note}"),
    ]
    return (
        '<div class="tiles">'
        + "".join(
            f'<div class="tile"><span class="v">{html.escape(v)}</span><span class="k">{html.escape(k)}</span></div>'
            for v, k in tiles
        )
        + "</div>"
    )


def _decision_table(months: list[dict], t: dict) -> str:
    rows = []
    for m in months:
        rpd = m["reviews_per_day"] or 0
        cap = t["review_capacity_per_day"]
        state = pill("over capacity", "near") if rpd > cap else pill("within capacity", "ok")
        rows.append(
            f'<tr><td>{m["month"]}</td><td class="n">{m["applications"]:,.0f}</td>'
            f'<td class="n">{pct(m["approve_rate"])}</td>'
            f'<td class="n">{pct(m["review_rate"])}</td><td class="n">{pct(m["decline_rate"])}</td>'
            f'<td class="n">{rpd:.0f}</td><td>{state}</td></tr>'
        )
    return (
        '<div class="tbl"><table><thead><tr><th>Month</th><th class="n">Applications</th><th class="n">Approve</th>'
        '<th class="n">Review</th><th class="n">Decline</th><th class="n">Reviews/day</th><th>Queue</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _drift_table(drift: list[dict], t: dict) -> str:
    top = max([d["psi"] for d in drift] + [t["psi_alert"]])
    rows = []
    for d in drift:
        width = max(2, 120 * d["psi"] / top)
        rows.append(
            f"<tr><td>{d['month']}</td><td><code>{html.escape(d['feature'])}</code></td>"
            f'<td class="n"><span class="psibar" style="width:{width:.0f}px"></span>{d["psi"]:.3f}</td>'
            f"<td>{pill(d['status'], d['status'])}</td></tr>"
        )
    return (
        '<div class="tbl"><table><thead><tr><th>Month</th><th>Feature</th><th class="n">PSI vs training</th>'
        f"<th>Status</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def _performance_table(months: list[dict], t: dict) -> str:
    rows = []
    for m in months:
        if m.get("recall_at_threshold") is None:
            continue
        r = m["fpr_ratio_age"]
        state = (
            pill("below limit", "fail")
            if r < t["fpr_ratio_age_min"]
            else pill("near limit", "near")
            if r < t["fpr_ratio_age_min"] + 0.10
            else pill("ok", "ok")
        )
        rows.append(
            f"<tr><td>{m['month']}</td><td>month {m['month'] + config.LABEL_LAG_MONTHS}</td>"
            f'<td class="n">{pct(m["fraud_rate_labelled"])}</td><td class="n">{dec(m["recall_at_threshold"])}</td>'
            f'<td class="n">{dec(m["fpr"])}</td><td class="n">{dec(r, 2)}</td><td>{state}</td></tr>'
        )
    return (
        '<div class="tbl"><table><thead><tr><th>Month</th><th>Labels complete in</th><th class="n">Fraud rate</th>'
        '<th class="n">Recall</th><th class="n">FPR</th><th class="n">Age FPR ratio</th><th>Fairness</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _policy_table(policy: list[dict]) -> str:
    rows = "".join(
        f'<tr><td>{html.escape(p["label"])}</td><td class="n">{pct(p["fraud_stopped_rate"], 1)}</td>'
        f'<td class="n">{pct(p["review_rate"])}</td><td class="n">{pct(p["decline_rate"])}</td>'
        f'<td class="n">{p["good_declined_per_10k"]:.0f}</td><td class="n">{rupiah_millions(p["cost_per_10k"])}</td>'
        f'<td class="n">{p["analysts_needed"]}</td></tr>'
        for p in policy
    )
    return (
        '<div class="tbl"><table><thead><tr><th>Policy</th><th class="n">Fraud stopped</th><th class="n">Review</th>'
        '<th class="n">Auto-decline</th><th class="n">Genuine declined / 10k</th>'
        '<th class="n">Cost / 10k (scenario)</th>'
        f'<th class="n">Analysts</th></tr></thead><tbody>{rows}</tbody></table></div>'
    )


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>SIGAP monitoring</title>
<meta name="description" content="Monthly replay of the SIGAP fraud-decision model: review load, drift,
late-label performance and fairness.">
<style>$css</style>
</head>
<body>
<main>
<header>
  <span class="eyebrow">SIGAP · monitoring replay · months $first–$last</span>
  <h1>SIGAP monitoring</h1>
  <p class="lede">How the account-opening fraud model behaved when months $first–$last were replayed as if live:
  review load against the team's capacity, drift against the training months, and recall and fairness once the
  fraud labels arrived two months later. Offline replay on the BAF $variant dataset for a fictional bank, not
  live traffic. Model <code>$model</code>, snapshot of $generated.
  Code and method: <a href="$repo">github.com/Agathahah/sigap</a>.</p>
  $tiles
</header>

<section>
  <h2>Decisions and review load</h2>
  <p class="small">Reviews per day = review rate × $apps_per_day applications a day. A day up to $tolerance over
  capacity is absorbed with overtime; above that an alert goes to the operations lead.</p>
  <div class="card">$chart_reviews$decision_table</div>
</section>

<section>
  <h2>Drift</h2>
  <p class="small">Population Stability Index of the model score and of the 10 most important features, each month
  against the training months. Below $psi_watch stable, $psi_watch–$psi_alert watch, from $psi_alert alert. One
  drifting feature opens an investigation, not a retraining ticket, while the score stays stable.</p>
  <div class="card">$chart_psi</div>
  <div class="card"><h2 class="h3">Most-shifted features each month (top $top_drift)</h2>$drift_table</div>
</section>

<section>
  <h2>Performance when the labels arrived</h2>
  <p class="small">Fraud is confirmed about two months after the application, so each month's recall is only known
  two months later. Release limits: recall at least $recall_min at the 5% FPR threshold, age FPR ratio (applicants
  aged 50+ vs younger) at least $ratio_min.</p>
  <div class="charts">
    <div class="card"><h2 class="h3">Recall at the operating threshold</h2>$chart_recall</div>
    <div class="card"><h2 class="h3">Age FPR ratio</h2>$chart_ratio</div>
  </div>
  <div class="card">$performance_table</div>
</section>

<section>
  <h2>Decision policy, $policy_period</h2>
  <p class="small">Rules against the model with approve/review/decline bands chosen by expected cost under review
  capacity, on $n_policy applications. Costs are scenarios from written assumptions
  (<code>configs/business.yaml</code>), not bank figures. Automatic declines are capped at $decline_cap.</p>
  <div class="card">$policy_table</div>
</section>

<section>
  <h2>Sources</h2>
  <ul class="small">
    <li>Snapshot <a href="data/monitoring.json"><code>data/monitoring.json</code></a>, exported by
    <code>make site-data</code> from the views <code>ops.v_monthly_kpis</code> and <code>ops.v_feature_drift</code>
    and from <code>reports/policy/champion_challenger_*.csv</code>; this page is rebuilt from it by
    <code>make site</code>.</li>
    <li>Method: <a href="$repo/blob/main/docs/06_MONITORING_REPLAY.md">monitoring replay</a>,
    <a href="$repo/blob/main/docs/RUNBOOK.md">runbook</a> (alert and retraining rules),
    <a href="$repo/blob/main/docs/adr/0005-fairness-age-predictive-equality.md">ADR 0005</a> (fairness limit),
    <a href="$repo/blob/main/docs/04_DECISION_POLICY.md">decision policy</a>.</li>
    <li>Data: Bank Account Fraud suite, Jesus et al. (2022), NeurIPS Datasets and Benchmarks, CC BY-NC-SA 4.0.
    Only monthly aggregates are published here.</li>
  </ul>
</section>
</main>
</body>
</html>
"""


def build_page(snap: dict) -> str:
    """The whole page as one HTML string. Deterministic: the same snapshot always gives the same bytes."""
    t, months = snap["thresholds"], snap["months"]
    recall_label = f"release limit {t['recall_min']:.2f}"
    ratio_label = f"limit {t['fpr_ratio_age_min']:.2f}"
    parts = {
        "css": CSS,
        "first": months[0]["month"],
        "last": months[-1]["month"],
        "variant": html.escape(snap["variant"]),
        "model": html.escape(snap["model_version"]),
        "generated": html.escape(snap["generated"]),
        "repo": REPO_URL,
        "tiles": _tiles(months, t),
        "apps_per_day": f"{t['applications_per_day']:,.0f}",
        "tolerance": f"{t['queue_tolerance']:.0%}",
        "chart_reviews": chart_reviews(months, t),
        "decision_table": _decision_table(months, t),
        "psi_watch": f"{t['psi_watch']:.2f}",
        "psi_alert": f"{t['psi_alert']:.2f}",
        "chart_psi": chart_psi(months, t),
        "top_drift": TOP_DRIFT,
        "drift_table": _drift_table(snap["drift"], t),
        "recall_min": f"{t['recall_min']:.2f}",
        "ratio_min": f"{t['fpr_ratio_age_min']:.2f}",
        "chart_recall": chart_line(months, "recall_at_threshold", t["recall_min"], recall_label, "Recall by month"),
        "chart_ratio": chart_line(months, "fpr_ratio_age", t["fpr_ratio_age_min"], ratio_label, "Age FPR ratio"),
        "performance_table": _performance_table(months, t),
        "policy_period": html.escape(snap["policy_period"]),
        "n_policy": f"{snap['policy'][0]['n']:,}" if snap["policy"] else "0",
        "decline_cap": f"{t['max_decline_rate']:.0%}",
        "policy_table": _policy_table(snap["policy"]),
    }
    return Template(TEMPLATE).substitute(parts)


def build(snapshot: Path = SNAPSHOT, page: Path = PAGE) -> Path:
    snap = json.loads(snapshot.read_text(encoding="utf-8"))
    page.write_text(build_page(snap), encoding="utf-8")
    return page


def main(argv: list[str] | None = None) -> None:
    cmd = (argv if argv is not None else sys.argv[1:]) or ["build"]
    if cmd[0] == "export":
        snap = export_snapshot()
        print(f"{SNAPSHOT.relative_to(config.ROOT)}: {len(snap['months'])} months, {len(snap['drift'])} drift rows")
    elif cmd[0] == "build":
        print(f"-> {build().relative_to(config.ROOT)}")
    else:
        raise SystemExit("usage: python -m sigap.monitor.site [export|build]")


if __name__ == "__main__":
    main()
