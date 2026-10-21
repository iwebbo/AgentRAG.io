"""
SanityCheck — défauts grossiers d'une génération, indépendants du sujet :

- réponse vide, ou uniquement du raisonnement (<think>) sans réponse ;
- raisonnement jamais refermé (génération tronquée pendant la réflexion) ;
- boucle de répétition (petits modèles qui bouclent sur la même ligne).
"""
from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple

from .base import CheckResult, Finding, Severity, VerificationContext, strip_think

_THINK_OPEN_RE = re.compile(r"<think>", re.IGNORECASE)
_THINK_CLOSE_RE = re.compile(r"</think>", re.IGNORECASE)


class SanityCheck:
    name = "sanity"
    blocking = False

    def __init__(self, min_chars: int = 2, repeat_threshold: int = 6, min_repeat_line_chars: int = 8):
        self.min_chars = min_chars
        self.repeat_threshold = repeat_threshold
        self.min_repeat_line_chars = min_repeat_line_chars

    def run(self, response: str, ctx: VerificationContext, prior: Sequence[CheckResult]) -> CheckResult:
        findings: List[Finding] = []
        raw = response or ""
        visible = strip_think(raw)

        opens = len(_THINK_OPEN_RE.findall(raw))
        closes = len(_THINK_CLOSE_RE.findall(raw))
        if opens > closes:
            findings.append(Finding(
                "sanity.reasoning_truncated",
                Severity.ERROR,
                "The model's reasoning (<think>) was never closed: the generation was probably truncated "
                "before any answer was produced.",
            ))
        elif len(visible) < self.min_chars:
            findings.append(Finding(
                "sanity.empty",
                Severity.ERROR,
                "The answer is empty" + (" (only reasoning was produced)." if raw.strip() else "."),
            ))

        repeated = self._find_repetition(visible)
        if repeated:
            line, count = repeated
            findings.append(Finding(
                "sanity.repetition_loop",
                Severity.ERROR,
                f"The model is looping: the same line is repeated {count} times in a row.",
                {"line": line, "count": count},
            ))

        return CheckResult.from_findings(self.name, findings)

    def _find_repetition(self, text: str) -> Optional[Tuple[str, int]]:
        previous = None
        run = 0
        for raw_line in text.split("\n"):
            line = raw_line.strip()
            if len(line) < self.min_repeat_line_chars:
                previous, run = None, 0
                continue
            if line == previous:
                run += 1
                if run + 1 >= self.repeat_threshold:
                    return line, run + 1
            else:
                previous, run = line, 0
        return None
