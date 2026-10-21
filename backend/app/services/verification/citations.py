"""
CitationCheck — vérifie les citations `[SOURCE n]` d'une réponse RAG.

Ce qui est vérifié mécaniquement :
  - chaque `[SOURCE n]` pointe vers une source réellement fournie au modèle (1 ≤ n ≤ nb de chunks) ;
  - une citation n'est jamais faite alors qu'aucun document n'a été récupéré ;
  - une source citée n'est pas vide ;
  - en RAG, une réponse substantielle sans aucune citation est signalée.

Ce check ne dit PAS si la source soutient réellement l'affirmation : c'est le rôle
du juge (judge.py), qui reçoit les chunks comme evidence.
"""
from __future__ import annotations

import re
from typing import List, Sequence, Set

from .base import (
    CheckResult,
    Finding,
    Severity,
    VerificationContext,
    strip_fenced_blocks,
    strip_think,
)

# [SOURCE 1] · [SOURCE 1, 3] · [SOURCE 1, SOURCE 3] · [SOURCE 1-3] · [Source: 2] · [SOURCES 1 et 2]
_CITATION_RE = re.compile(
    r"\[\s*SOURCES?\s*[:#]?\s*"
    r"(?P<body>\d+(?:\s*(?:[,;&]|\bet\b|\band\b|[-–])\s*(?:SOURCES?\s*[:#]?\s*)?\d+)*)"
    r"\s*\]",
    re.IGNORECASE,
)
_RANGE_RE = re.compile(r"(\d+)\s*[-–]\s*(\d+)")
_NUMBER_RE = re.compile(r"\d+")
_MAX_RANGE = 50


def extract_citation_numbers(text: str) -> List[int]:
    """Numéros cités (avec doublons supprimés, ordre d'apparition), hors blocs de code."""
    seen: Set[int] = set()
    ordered: List[int] = []
    prose = strip_fenced_blocks(strip_think(text))
    for match in _CITATION_RE.finditer(prose):
        body = match.group("body")
        numbers: List[int] = []
        remainder = body
        for rng in _RANGE_RE.finditer(body):
            low, high = int(rng.group(1)), int(rng.group(2))
            if low <= high and high - low <= _MAX_RANGE:
                numbers.extend(range(low, high + 1))
            else:
                numbers.extend([low, high])
        remainder = _RANGE_RE.sub(" ", remainder)
        numbers.extend(int(n) for n in _NUMBER_RE.findall(remainder))
        for n in numbers:
            if n not in seen:
                seen.add(n)
                ordered.append(n)
    return ordered


class CitationCheck:
    name = "citations"
    blocking = False

    def __init__(self, require_citations: bool = True, min_chars_for_citation: int = 200):
        self.require_citations = require_citations
        self.min_chars_for_citation = min_chars_for_citation

    def run(self, response: str, ctx: VerificationContext, prior: Sequence[CheckResult]) -> CheckResult:
        cited = extract_citation_numbers(response)
        chunks = ctx.retrieved_chunks or []

        if not ctx.is_rag and not cited:
            return CheckResult.skipped(self.name, "not a RAG answer")

        findings: List[Finding] = []
        total = len(chunks)

        for n in cited:
            if n < 1 or n > total:
                findings.append(Finding(
                    "citation.out_of_range",
                    Severity.ERROR,
                    f"The answer cites [SOURCE {n}] but " + (
                        f"only {total} source(s) were provided (valid range: 1-{total})."
                        if total else "no source was retrieved at all."
                    ),
                    {"cited": n, "available": total},
                ))
                continue
            text = (chunks[n - 1].get("text") or "").strip()
            if not text:
                findings.append(Finding(
                    "citation.empty_source",
                    Severity.WARNING,
                    f"[SOURCE {n}] is cited but its content is empty.",
                    {"cited": n},
                ))

        if self.require_citations and ctx.is_rag and total and not cited:
            prose = strip_fenced_blocks(strip_think(response)).strip()
            if len(prose) >= self.min_chars_for_citation:
                findings.append(Finding(
                    "citation.missing",
                    Severity.WARNING,
                    f"The answer does not cite any of the {total} retrieved source(s) with [SOURCE n].",
                    {"available": total},
                ))

        return CheckResult.from_findings(self.name, findings, note=f"{len(cited)} citation(s), {total} source(s)")
