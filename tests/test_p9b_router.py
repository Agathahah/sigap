"""Phase 9b+ · the optional router: classify first, then bind only that category's tools (no LLM, no cost)."""

import json

import pytest

pytest.importorskip("langgraph")

from langchain_core.language_models.chat_models import BaseChatModel  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402
from langchain_core.outputs import ChatGeneration, ChatResult  # noqa: E402
from langchain_core.tools import tool  # noqa: E402

from sigap.copilot.agent import OUT_OF_SCOPE_ANSWER, build_graph, parse_route, text_of  # noqa: E402
from sigap.copilot.budget import CostMeter  # noqa: E402

pytestmark = pytest.mark.p9b

PRICE = {"input_per_mtok": 1.0, "output_per_mtok": 5.0}


class RecordingModel(BaseChatModel):
    """Plays a script shared by every bound copy and records which tools each call could see."""

    script: list
    shared: dict
    bound: list = []

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self.model_copy(update={"bound": [t.name for t in tools]})

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        i = self.shared.setdefault("i", 0)
        self.shared.setdefault("seen_tools", []).append(list(self.bound))
        self.shared["i"] = i + 1
        return ChatResult(generations=[ChatGeneration(message=self.script[min(i, len(self.script) - 1)])])

    @property
    def _llm_type(self) -> str:
        return "recording"


@tool
def query_kpi(metric: str, group_by: str = "month") -> str:
    """KPI (fake)."""
    return json.dumps({"metric": metric, "rows": [{"group": "windows", "rate": 0.0412, "n": 1250}]})


@tool
def search_policy(question: str) -> str:
    """Policy (fake)."""
    return json.dumps({"chunks": [{"source": "sop.md", "page": 5, "text": "SLA 1 hari kerja"}]})


@tool
def get_application(application_id: str) -> str:
    """Application (fake)."""
    return json.dumps({"application_id": application_id})


TOOLS = [query_kpi, search_policy, get_application]


def run(script, question, router=True):
    llm = RecordingModel(script=script, shared={})
    graph = build_graph(llm, TOOLS, CostMeter(daily_budget_usd=10.0), PRICE, max_steps=3, router=router)
    state = graph.invoke({"messages": [HumanMessage(question)]})
    return llm.shared, state  # pydantic copies the dict on construction; the bound copies share llm.shared


def test_parse_route():
    assert parse_route("Label: case.") == "case"
    assert parse_route("POLICY") == "policy"
    assert parse_route("<think>maybe kpi</think> monitoring") == "kpi"  # first label wins; text_of strips think
    assert parse_route("tidak tahu") == "other"


def test_text_of_strips_reasoning():
    assert text_of(AIMessage("<think>hitung 0.09</think>Rate 0.0412.")) == "Rate 0.0412."
    assert text_of(AIMessage("<think>belum selesai")) == ""


def test_router_out_of_scope_answers_without_tools():
    shared, s = run([AIMessage("out_of_scope")], "Siapa presiden Indonesia?")
    assert s["answer"] == OUT_OF_SCOPE_ANSWER and s["route"] == "out_of_scope"
    assert shared["i"] == 1 and s.get("tools_called", []) == []


def test_router_binds_only_the_category_tools():
    call = AIMessage(content="", tool_calls=[{"name": "query_kpi", "args": {"metric": "fraud_rate"}, "id": "t1"}])
    shared, s = run([AIMessage("kpi"), call, AIMessage("Fraud rate windows 0.0412.")], "Fraud rate per device_os?")
    assert s["route"] == "kpi" and s["stopped_reason"] == "ok" and s["tools_called"] == ["query_kpi"]
    assert shared["seen_tools"][0] == [] and shared["seen_tools"][1:] == [["query_kpi"], ["query_kpi"]]


def test_unknown_route_keeps_all_tools_and_router_off_is_unchanged():
    shared, s = run([AIMessage("hmm"), AIMessage("Tidak ada angka.")], "Tolong bantu")
    assert s["route"] == "other" and shared["seen_tools"][1] == ["query_kpi", "search_policy", "get_application"]
    shared, s = run([AIMessage("Tidak ada angka.")], "Tolong bantu", router=False)
    assert "route" not in s and shared["i"] == 1


def test_resume_keeps_finished_rows_and_drops_a_cut_off_line(tmp_path):
    from sigap.copilot.eval import load_done

    f = tmp_path / "run.jsonl"
    assert load_done(f) == []
    lines = ['{"id": "kpi-01", "passed": true}', '{"id": "pol-01", "passed": false}', '{"id": "case-0']
    f.write_text("\n".join(lines), encoding="utf-8")
    assert [r["id"] for r in load_done(f)] == ["kpi-01", "pol-01"]
