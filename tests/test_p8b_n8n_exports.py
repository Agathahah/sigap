"""Phase 8b · n8n workflows are code: exported JSON in n8n/workflows/, safe to publish.

Red until you build the two workflows in n8n and export them (`make n8n-export`).
These checks are what a reviewer would ask before merging automation into a bank repo:
no tokens, no phone numbers, no pinned test data, and the workflow talks to SIGAP only through the ops API.
"""

import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.p8b

WF_DIR = Path(__file__).resolve().parents[1] / "n8n" / "workflows"

SECRET_PATTERNS = {
    "Meta/WhatsApp access token": re.compile(r"EAA[A-Za-z0-9]{30,}"),
    "Anthropic key": re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}"),
    "Bearer token literal": re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}"),
    "Indonesian phone number": re.compile(r"(?<![\d])(?:\+?62|0)8\d{8,11}(?![\d])"),
    "e-mail address": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z.]{2,}"),
}


def _workflows() -> list[tuple[Path, dict]]:
    files = sorted(WF_DIR.glob("*.json"))
    return [(f, json.loads(f.read_text(encoding="utf-8"))) for f in files]


def _walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def test_two_workflows_exported():
    wfs = _workflows()
    assert len(wfs) >= 2, "export alert-router and review-case workflows into n8n/workflows/ (make n8n-export)"
    for f, wf in wfs:
        assert wf.get("nodes") and "connections" in wf, f"{f.name} is not an n8n workflow export"


def test_no_secrets_or_phone_numbers():
    for f, _ in _workflows():
        text = f.read_text(encoding="utf-8")
        for name, pat in SECRET_PATTERNS.items():
            assert not pat.search(text), f"{f.name}: {name} found. Use n8n credentials or {{{{ $env.* }}}}"


def test_api_key_not_inline_and_no_pinned_data():
    for f, wf in _workflows():
        assert not wf.get("pinData"), f"{f.name}: remove pinned test data before exporting"
        for d in _walk(wf):
            if str(d.get("name", "")).lower() == "x-api-key" and d.get("value"):
                assert str(d["value"]).startswith("="), (
                    f"{f.name}: X-API-Key is a literal; use a Header Auth credential"
                )


def test_workflows_use_ops_api_and_a_channel():
    wfs = _workflows()
    texts = [json.dumps(wf) for _, wf in wfs]
    assert any("/v1/ops/alerts" in t for t in texts), "one workflow must read GET /v1/ops/alerts"
    assert any("/decision" in t for t in texts), "one workflow must write POST /v1/ops/cases/{id}/decision"
    types = {n.get("type", "").lower() for _, wf in wfs for n in wf["nodes"]}
    assert any("whatsapp" in t or "gmail" in t or "emailsend" in t for t in types), "no WhatsApp (or email) node"
    assert any("httprequest" in t for t in types), "no HTTP Request node calling the SIGAP API"
    assert not any("postgres" in t for t in types), "n8n must not talk to the warehouse directly (ADR 0007)"


def test_every_message_has_both_channels_behind_one_switch():
    """WhatsApp to +62 is blocked from a non-Indonesian test number (error 130497), so each workflow that sends
    a message has a WhatsApp and an e-mail node behind one IF on $env.SIGAP_ALERT_CHANNEL (ADR 0007)."""
    for f, wf in _workflows():
        types = [n.get("type", "").lower() for n in wf["nodes"]]
        if not any("whatsapp" in t for t in types):
            continue
        assert any("emailsend" in t for t in types), f"{f.name}: WhatsApp node without the e-mail fallback"
        ifs = [n for n in wf["nodes"] if n.get("type") == "n8n-nodes-base.if"]
        assert any("$env.SIGAP_ALERT_CHANNEL" in json.dumps(n["parameters"]) for n in ifs), (
            f"{f.name}: channel must be chosen by $env.SIGAP_ALERT_CHANNEL, not hard-coded"
        )
        for n in wf["nodes"]:
            if n.get("type") == "n8n-nodes-base.emailSend":
                assert "$env.SIGAP_ANALYST_EMAIL" in n["parameters"].get("toEmail", ""), f"{f.name}: {n['name']}"
