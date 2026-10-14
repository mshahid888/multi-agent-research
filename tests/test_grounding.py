"""Grounding: the analyst must never invent facts.

The template backend is extractive by construction, so its briefs must pass.
A tampered brief (or a misbehaving LLM backend) must fail loudly via
GroundingError instead of flowing into the outreach draft.
"""
import pytest

from src.agents import AnalystAgent
from src.grounding import GroundingError, verify_grounding
from src.llm import LLMBackend, TemplateBackend


def test_template_brief_is_grounded(findings, llm):
    brief = llm.build_brief("Nordwind Logistics GmbH", findings)
    assert verify_grounding(brief, findings) == []


def test_template_brief_is_grounded_for_both_demos(llm, demo_source):
    from src.datasources import DemoDataSource
    from tests.conftest import DATA_PATH
    for cid in ("nordwind", "bluefin"):
        src = DemoDataSource(DATA_PATH, cid)
        findings = [f.to_dict() for f in src.fetch(src.company_name)]
        brief = llm.build_brief(src.company_name, findings)
        assert verify_grounding(brief, findings) == [], f"ungrounded: {cid}"


def test_invented_claim_is_caught(findings, llm):
    brief = llm.build_brief("Nordwind Logistics GmbH", findings)
    brief["strengths"].append({
        "text": "They secretly operate a moon base with 9000 employees.",
        "evidence": ["f1"],
    })
    violations = verify_grounding(brief, findings)
    assert violations, "invented claim slipped through grounding check"
    assert any("moon" in v for v in violations)


def test_meta_statements_are_allowed(findings):
    brief = {
        "what_they_do": [],
        "strengths": [{"text": "No explicit strengths stated in the gathered sources.",
                       "evidence": [], "meta": True}],
        "gaps": [],
        "hooks": [],
    }
    assert verify_grounding(brief, findings) == []


class InventingLLM(LLMBackend):
    """A misbehaving backend that injects an invented fact."""

    def build_brief(self, company, findings):
        brief = TemplateBackend().build_brief(company, findings)
        brief["gaps"].append({
            "text": "The CEO personally dislikes automation and bans computers.",
            "evidence": ["f2"],
        })
        return brief


def test_analyst_raises_on_ungrounded_backend(findings, memory):
    memory.write("researcher", "findings", findings)
    memory.share("company", "Nordwind Logistics GmbH")
    with pytest.raises(GroundingError):
        AnalystAgent().run(memory, InventingLLM())


def test_analyst_needs_findings(memory, llm):
    with pytest.raises(ValueError):
        AnalystAgent().run(memory, llm)
