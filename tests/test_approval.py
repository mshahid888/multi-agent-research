"""Approval gate: nothing may be "sent" without explicit human approval —
and even with approval the send is simulated (sent=false, always).

A static guard also proves the project contains no sending code at all.
"""
import json
from pathlib import Path

from src.datasources import DemoDataSource
from src.llm import TemplateBackend
from src.memory import AgentMemory
from src.supervisor import Approval, Supervisor
from src.trace import Tracer
from tests.conftest import DATA_PATH


def run_pipeline(tmp_path, approved: bool) -> dict:
    src = DemoDataSource(DATA_PATH, "nordwind")
    run_dir = tmp_path / "run"
    supervisor = Supervisor(
        llm=TemplateBackend(),
        memory=AgentMemory("approval-test"),
        tracer=Tracer(),
        run_dir=run_dir,
        approver=lambda draft: Approval(
            approved=approved, by="tester",
            at="2026-01-01 00:00:00", note="test"),
        sender_name="Test Sender",
    )
    result = supervisor.run(src.company_name, [src])
    result["log"] = json.loads((run_dir / "send_log.json").read_text(encoding="utf-8"))
    return result


def test_declined_draft_is_blocked(tmp_path):
    result = run_pipeline(tmp_path, approved=False)
    assert result["status"] == "declined"
    assert result["log"]["sent"] is False
    assert result["log"]["approved"] is False


def test_approved_send_is_still_simulated(tmp_path):
    result = run_pipeline(tmp_path, approved=True)
    assert result["status"] == "sent_simulated"
    assert result["log"]["sent"] is False
    assert result["log"]["simulated"] is True
    assert result["log"]["approved"] is True


def test_draft_artifact_exists_but_nothing_transmitted(tmp_path):
    result = run_pipeline(tmp_path, approved=True)
    run_dir = Path(result["run_dir"])
    assert (run_dir / "outreach_draft.md").exists()
    assert (run_dir / "brief.json").exists()
    assert (run_dir / "memory.json").exists()
    # the draft must be labelled as unsent
    draft_md = (run_dir / "outreach_draft.md").read_text(encoding="utf-8")
    assert "NOT SENT" in draft_md


def test_no_sending_code_anywhere():
    """Static guard: no SMTP / sending imports may ever exist in src/."""
    src_dir = Path(__file__).resolve().parents[1] / "src"
    code = " ".join(p.read_text(encoding="utf-8") for p in src_dir.rglob("*.py"))
    for forbidden in ("smtplib", "sendmail", "yagmail", "smtplib.SMTP"):
        assert forbidden not in code, f"sending code found: {forbidden}"
