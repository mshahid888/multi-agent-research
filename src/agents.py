"""Worker agents: Researcher, Analyst, Writer.

Each agent declares a role prompt (used by a real LLM later), its inputs and
outputs, and communicates only through the shared :class:`AgentMemory`.

Pipeline contract:
    Researcher  in: company name + data sources      out: memory["researcher"]["findings"]
    Analyst     in: findings                          out: memory["analyst"]["brief"] (grounded)
    Writer      in: brief                             out: memory["writer"]["draft"]  (draft only!)
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .grounding import GroundingError, verify_grounding


class Agent(ABC):
    name: str = "agent"
    role_prompt: str = ""

    @abstractmethod
    def run(self, memory, llm, tracer=None, **kwargs) -> dict:
        """Do the agent's job; read/write memory; return a small result dict."""


class ResearcherAgent(Agent):
    name = "researcher"
    role_prompt = (
        "You are the Researcher. Given a company name and a set of data sources, "
        "collect factual findings about the company. Record every finding together "
        "with the source it came from. Never invent data — if a source has nothing, "
        "say so explicitly."
    )

    def run(self, memory, llm, tracer=None, company: str = "",
            sources=(), **kwargs) -> dict:
        collected = []
        for src in sources or []:
            if tracer:
                tracer.agent(self.name, f"querying source: {src.name} ...")
            found = src.fetch(company)
            if tracer:
                tracer.ok(f"{len(found)} finding(s) from {src.name}")
            collected.extend(found)
        findings = []
        for i, f in enumerate(collected, 1):
            d = f.to_dict() if hasattr(f, "to_dict") else dict(f)
            d["id"] = f"f{i}"
            findings.append(d)
        memory.write(self.name, "findings", findings)
        memory.log(self.name, "research_complete",
                   f"{len(findings)} findings from {len(sources or [])} source(s)")
        return {"findings": findings}


class AnalystAgent(Agent):
    name = "analyst"
    role_prompt = (
        "You are the Analyst. Turn the researcher's raw findings into a structured "
        "brief: what the company does, strengths, gaps, and outreach hooks. Every "
        "bullet must be grounded in cited findings — no invented facts. If the "
        "sources are thin, say so instead of guessing."
    )

    def run(self, memory, llm, tracer=None, **kwargs) -> dict:
        findings = memory.read("researcher", "findings", [])
        if not findings:
            raise ValueError("no researcher findings in memory — cannot analyze")
        company = memory.get_shared("company", "")
        if tracer:
            tracer.agent(self.name,
                         f"building brief for {company} from {len(findings)} findings ...")
        brief = llm.build_brief(company, findings)
        brief["company"] = company
        violations = verify_grounding(brief, findings)
        if violations:
            raise GroundingError("; ".join(violations))
        memory.write(self.name, "brief", brief)
        memory.log(self.name, "analysis_complete",
                   f"{len(brief['strengths'])} strengths, "
                   f"{len(brief['gaps'])} gaps, {len(brief['hooks'])} hooks")
        if tracer:
            tracer.ok("brief grounded — every claim cites researcher findings")
        return {"brief": brief}


class WriterAgent(Agent):
    name = "writer"
    role_prompt = (
        "You are the Writer. Draft ONE short, personalized outreach email from the "
        "analyst brief. Use only facts that appear in the brief — never invent "
        "details about the company. You do not send email; you produce a draft "
        "for human approval."
    )

    def run(self, memory, llm, tracer=None, sender_name="[Your Name]",
            value_prop="", **kwargs) -> dict:
        brief = memory.read("analyst", "brief")
        if not brief:
            raise ValueError("no analyst brief in memory — cannot write")
        company = brief.get("company", "your company")
        strengths = [c["text"] for c in brief.get("strengths", []) if not c.get("meta")]
        gaps = [c["text"] for c in brief.get("gaps", []) if not c.get("meta")]

        lines = ["Hi there,", ""]
        if strengths:
            lines.append(f"I came across {company} — {strengths[0]}")
            lines.append("")
        if gaps:
            first = gaps[0]
            lines.append(f"I also noticed that {first[0].lower() + first[1:]}")
            lines.append("")
        if value_prop:
            lines.append(value_prop)
            lines.append("")
        lines.append("Would a 15-minute call next week be useful to explore this?")
        lines.append("")
        lines.append(f"Best regards,\n{sender_name}")

        draft = {
            "subject": f"Quick idea for {company}",
            "body": "\n".join(lines),
            "to_company": company,
            "status": "draft — NOT sent",
        }
        memory.write(self.name, "draft", draft)
        memory.log(self.name, "draft_complete", draft["subject"])
        if tracer:
            tracer.ok("draft written — awaiting human approval (never auto-sent)")
        return {"draft": draft}
