"""Router decisions: the supervisor must pick the right next step for every state."""
import pytest

from src.llm import TemplateBackend
from src.memory import AgentMemory
from src.supervisor import Approval, Supervisor
from src.trace import Tracer


def make_supervisor(**kwargs):
    return Supervisor(
        llm=TemplateBackend(),
        memory=AgentMemory("router-test"),
        tracer=Tracer(),  # no log path -> stdout only
        run_dir="/tmp/multi-agent-router-test",
        **kwargs,
    )


def _approval(approved: bool) -> Approval:
    return Approval(approved=approved, by="tester",
                    at="2026-01-01 00:00:00", note="test")


def test_routes_to_research_first():
    assert make_supervisor().decide_next({}) == "research"


def test_aborts_when_no_findings():
    assert make_supervisor().decide_next({"findings": []}) == "abort_empty"


def test_routes_to_analyze_after_research():
    state = {"findings": [{"id": "f1", "text": "x", "kind": "about", "source": "s"}]}
    assert make_supervisor().decide_next(state) == "analyze"


def test_routes_to_draft_after_brief():
    state = {"findings": [{"id": "f1"}], "brief": {"company": "X"}}
    assert make_supervisor().decide_next(state) == "draft"


def test_routes_to_approve_after_draft():
    state = {"findings": [{"id": "f1"}], "brief": {}, "draft": {}}
    assert make_supervisor().decide_next(state) == "approve"


def test_routes_to_send_when_approved():
    state = {"findings": [{"id": "f1"}], "brief": {}, "draft": {},
             "approval": _approval(True)}
    assert make_supervisor().decide_next(state) == "send"


def test_routes_to_declined_end_when_not_approved():
    state = {"findings": [{"id": "f1"}], "brief": {}, "draft": {},
             "approval": _approval(False)}
    assert make_supervisor().decide_next(state) == "done_declined"
