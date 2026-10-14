"""Grounding checks: every analyst claim must trace back to researcher findings.

A claim is "grounded" when every content token in its text also appears in the
vocabulary of the cited findings (stopwords and a small template-boilerplate
list are ignored). Claims flagged ``meta: True`` (e.g. "no strengths stated in
the sources") are honest statements *about* the sources and are skipped.
"""
from __future__ import annotations

import re

_STOPWORDS = set(
    "a an the and or of to in on for with is are was were be been being "
    "it its this that these those as at by from we you they he she his her "
    "their our your my me him us them i am do does did done have has had "
    "will would can could should shall may might must not no yes so but if "
    "then than too very just also into over under between through during "
    "about against per via etc eg ie ll ve re m d s t".split()
)

# Words the template backend itself adds around quoted finding phrases.
_BOILERPLATE = set("outreach angle praise bridge draft simulated fictional".split())

_WORD = re.compile(r"[a-zäöüß]+")

_SECTIONS = ("what_they_do", "strengths", "gaps", "hooks")


def _tokens(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower())
            if w not in _STOPWORDS and len(w) > 2]


def finding_vocabulary(findings: list) -> set[str]:
    vocab: set[str] = set()
    for f in findings:
        text = f["text"] if isinstance(f, dict) else f.text
        vocab.update(_tokens(text))
    return vocab


def verify_grounding(brief: dict, findings: list) -> list[str]:
    """Return a list of grounding violations; empty list means grounded."""
    vocab = finding_vocabulary(findings)
    violations: list[str] = []
    for section in _SECTIONS:
        for claim in brief.get(section, []) or []:
            if claim.get("meta"):
                continue
            unknown = [t for t in _tokens(claim.get("text", ""))
                       if t not in vocab and t not in _BOILERPLATE]
            if unknown:
                snippet = claim.get("text", "")[:70]
                violations.append(
                    f"{section}: ungrounded tokens {sorted(set(unknown))} in {snippet!r}"
                )
    return violations


class GroundingError(Exception):
    """Raised by the Analyst when a brief contains ungrounded claims."""
