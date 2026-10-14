"""LLM backend interface.

The default backend is deterministic and extractive: it reorganizes the
researcher's findings into a brief but never invents new facts (grounding
holds by construction, and the Analyst double-checks it anyway).

Swap in a real model by subclassing :class:`LLMBackend` (see
:class:`RealLLMBackend`) — the grounding contract stays enforced regardless
of which backend produces the brief.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod


class LLMBackend(ABC):
    @abstractmethod
    def build_brief(self, company: str, findings: list[dict]) -> dict:
        """Return a brief dict with keys: what_they_do, strengths, gaps, hooks.

        Each section is a list of claim dicts: {"text": ..., "evidence": [finding_ids]}.
        Claims flagged {"meta": True} are honest statements about the sources
        (e.g. "no strengths stated") and are exempt from grounding checks.
        """


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_POS_CUES = re.compile(
    r"\b(award|leading|leader|certified|certification|grow\w*|sustainab\w*|"
    r"trust\w*|innovat\w*|expand\w*|expanding|best|voted|loyal)\b", re.I)
_GAP_CUES = re.compile(
    r"\b(manual\w*|spreadsheet|paper|outdated|legacy|hiring|looking for|"
    r"challenge|struggl\w*|bottleneck|inefficien\w*|lose track|peak season|"
    r"holiday rush|by phone)\b", re.I)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text.strip()) if len(s.strip()) > 20]


def _shorten(sentence: str, words: int = 12) -> str:
    parts = sentence.split()
    return " ".join(parts[:words]) + ("..." if len(parts) > words else "")


class TemplateBackend(LLMBackend):
    """Deterministic extractive summarizer.

    Claims are sentence spans copied verbatim from findings, so every claim is
    grounded by construction. Strengths/gaps are picked by cue words; hooks
    pair a strength with a gap into an outreach angle.
    """

    def build_brief(self, company: str, findings: list[dict]) -> dict:
        if not findings:
            raise ValueError("no findings to summarize")

        def pick(cues: re.Pattern, limit: int = 3,
                 exclude: set[str] | None = None) -> list[dict]:
            out: list[dict] = []
            exclude = exclude or set()
            for f in findings:
                for s in _sentences(f["text"]):
                    if s in exclude:
                        continue  # a sentence can't be both a strength and a gap
                    if cues.search(s) and all(s != c["text"] for c in out):
                        out.append({"text": s, "evidence": [f["id"]]})
                    if len(out) >= limit:
                        return out
            return out

        about: list[dict] = []
        for f in findings:
            if f.get("kind") in ("about", "webpage"):
                for s in _sentences(f["text"])[:2]:
                    about.append({"text": s, "evidence": [f["id"]]})
            if len(about) >= 2:
                break
        if not about:  # fall back to the first finding's opening sentences
            f0 = findings[0]
            about = [{"text": s, "evidence": [f0["id"]]}
                     for s in _sentences(f0["text"])[:2]]

        # Gaps first: a sentence with strong gap cues (e.g. "manual", "bottleneck")
        # must not also be claimed as a strength via a weak cue (e.g. "growing").
        gaps = pick(_GAP_CUES) or [{
            "text": "No explicit gaps stated in the gathered sources.",
            "evidence": [], "meta": True}]
        strengths = pick(_POS_CUES,
                         exclude={c["text"] for c in gaps if not c.get("meta")}) or [{
            "text": "No explicit strengths stated in the gathered sources.",
            "evidence": [], "meta": True}]

        hooks: list[dict] = []
        for s_claim, g_claim in zip(strengths[:2], gaps[:2]):
            if s_claim.get("meta") or g_claim.get("meta"):
                continue
            hooks.append({
                "text": ("Outreach angle: praise '" + _shorten(s_claim["text"]) +
                         "' then bridge to '" + _shorten(g_claim["text"]) + "'."),
                "evidence": s_claim["evidence"] + g_claim["evidence"],
            })

        return {
            "company": company,
            "what_they_do": about,
            "strengths": strengths,
            "gaps": gaps,
            "hooks": hooks,
        }


class RealLLMBackend(LLMBackend):
    """Template for plugging in a real model (e.g. a local Ollama instance).

    Subclass and implement :meth:`build_brief`. Keep the contract:

    - every claim carries ``evidence`` (finding ids) and uses only finding
      vocabulary;
    - the Analyst agent's grounding check will reject anything else, so a
      sloppy model fails loudly instead of inventing facts.
    """

    def build_brief(self, company: str, findings: list[dict]) -> dict:
        raise NotImplementedError(
            "Plug your model in here. See README 'Swapping in a real LLM'."
        )
