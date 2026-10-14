"""Supervisor: routes work between agents, enforces grounding and the human
approval gate.

Router pattern: :meth:`decide_next` is pure logic — given what is done, what
comes next — so routing decisions are easy to unit test.

The approval gate is mandatory: the draft is shown to a human, and only an
explicit approval lets the pipeline continue. The "send" step is always
simulated — this project contains no sending code at all (no SMTP, no API
calls). ``send_log.json`` records ``sent: false`` every time.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .agents import AnalystAgent, ResearcherAgent, WriterAgent
from .grounding import GroundingError
from .memory import AgentMemory
from .trace import Tracer


@dataclass
class Approval:
    approved: bool
    by: str
    at: str
    note: str = ""


def interactive_approver(draft: dict) -> Approval:
    """Default approver: show the draft at the terminal, ask the human."""
    print("\n" + "-" * 62)
    print("OUTREACH DRAFT — not sent. Please review:")
    print("-" * 62)
    print(f"Subject: {draft['subject']}\n")
    print(draft["body"])
    print("-" * 62)
    answer = input("Approve SIMULATED send? [y/N] ").strip().lower()
    ok = answer in ("y", "yes")
    return Approval(
        approved=ok,
        by="human@terminal",
        at=time.strftime("%Y-%m-%d %H:%M:%S"),
        note="approved at terminal" if ok else "declined at terminal",
    )


DEFAULT_VALUE_PROP = (
    "We help small companies replace manual busywork with simple AI automation "
    "— no big IT project needed."
)


class Supervisor:
    def __init__(self, llm, memory: AgentMemory, tracer: Tracer, run_dir,
                 approver=None, sender_name: str = "[Your Name]",
                 value_prop: str | None = None):
        self.llm = llm
        self.memory = memory
        self.tracer = tracer
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.approver = approver
        self.sender_name = sender_name
        self.value_prop = value_prop or DEFAULT_VALUE_PROP
        self.agents = {
            "researcher": ResearcherAgent(),
            "analyst": AnalystAgent(),
            "writer": WriterAgent(),
        }

    # -- router ---------------------------------------------------------
    def decide_next(self, state: dict) -> str:
        """Pure routing logic: given what is done, what comes next?"""
        if "findings" not in state:
            return "research"
        if not state["findings"]:
            return "abort_empty"
        if "brief" not in state:
            return "analyze"
        if "draft" not in state:
            return "draft"
        if "approval" not in state:
            return "approve"
        if state["approval"].approved:
            return "send"
        return "done_declined"

    # -- run --------------------------------------------------------------
    def run(self, company: str, sources: list) -> dict:
        self.tracer.header(f"Multi-Agent Research Run — {company}")
        self.memory.share("company", company)
        state: dict = {}
        step_from = "start"
        while True:
            nxt = self.decide_next(state)
            self.tracer.route(step_from, nxt)
            step_from = nxt

            if nxt == "research":
                out = self.agents["researcher"].run(
                    self.memory, self.llm, tracer=self.tracer,
                    company=company, sources=sources)
                state["findings"] = out["findings"]

            elif nxt == "abort_empty":
                self.tracer.error("No findings gathered — nothing to analyze. Aborting.")
                return self._finish("aborted_empty", state)

            elif nxt == "analyze":
                try:
                    out = self.agents["analyst"].run(
                        self.memory, self.llm, tracer=self.tracer)
                except GroundingError as exc:
                    self.memory.log("supervisor", "grounding_failed", str(exc))
                    self.tracer.error(f"analyst produced ungrounded claims: {exc}")
                    return self._finish("grounding_failed", state)
                state["brief"] = out["brief"]

            elif nxt == "draft":
                out = self.agents["writer"].run(
                    self.memory, self.llm, tracer=self.tracer,
                    sender_name=self.sender_name, value_prop=self.value_prop)
                state["draft"] = out["draft"]

            elif nxt == "approve":
                approver = self.approver or interactive_approver
                approval = approver(state["draft"])
                if isinstance(approval, dict):
                    approval = Approval(**approval)
                state["approval"] = approval
                self.memory.write("supervisor", "approval", asdict(approval))
                verdict = "APPROVED" if approval.approved else "DECLINED"
                self.tracer.agent("supervisor",
                                  f"human approval: {verdict} ({approval.by})")

            elif nxt == "send":
                return self._send(state)

            elif nxt == "done_declined":
                self.tracer.warn("Draft declined by human — nothing will be sent.")
                self._write_send_log(approved=False, note="declined at approval gate")
                return self._finish("declined", state)

    # -- simulated send -----------------------------------------------------
    def _send(self, state: dict) -> dict:
        draft = state["draft"]
        self.tracer.agent("supervisor",
                          "send step (SIMULATED — no sending code exists, nothing transmitted)")
        self._write_send_log(approved=True, note="approved; simulated only")
        self.tracer.ok(f"send logged as sent=false (subject: {draft['subject']!r})")
        return self._finish("sent_simulated", state)

    def _write_send_log(self, approved: bool, note: str) -> None:
        log = {
            "sent": False,
            "simulated": True,
            "approved": approved,
            "company": self.memory.get_shared("company"),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "note": note,
            "reason": ("Demo mode: this project contains no sending code "
                       "(no SMTP, no API calls). Nothing was transmitted."),
        }
        (self.run_dir / "send_log.json").write_text(
            json.dumps(log, indent=2), encoding="utf-8")

    # -- artifacts ------------------------------------------------------------
    def _finish(self, status: str, state: dict) -> dict:
        self.memory.save(self.run_dir / "memory.json")
        if "findings" in state:
            (self.run_dir / "findings.json").write_text(
                json.dumps(state["findings"], indent=2, ensure_ascii=False),
                encoding="utf-8")
        if "brief" in state:
            (self.run_dir / "brief.json").write_text(
                json.dumps(state["brief"], indent=2, ensure_ascii=False),
                encoding="utf-8")
        if "draft" in state:
            d = state["draft"]
            (self.run_dir / "outreach_draft.md").write_text(
                "# Outreach draft — NOT SENT (simulated)\n\n"
                f"**To:** {d['to_company']}\n"
                f"**Subject:** {d['subject']}\n\n"
                f"{d['body']}\n",
                encoding="utf-8")
        self.tracer.ok(f"artifacts saved in {self.run_dir}/")
        return {"status": status, "run_dir": str(self.run_dir)}
