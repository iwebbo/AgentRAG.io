"""
VerificationPipeline — exécute les checks dans l'ordre et agrège un Verdict.

Garanties :
  - un check qui plante est isolé (`errored`), il ne casse jamais la réponse ;
  - un timeout global renvoie le verdict partiel des checks déjà terminés ;
  - les checks synchrones qui déclarent `blocking = True` tournent dans un thread
    (ruff = subprocess) pour ne pas bloquer l'event loop.

Barème du score (0.0 → 1.0) : chaque finding retire une pénalité selon sa sévérité
(error 0.35 · warning 0.10 · info 0). `passed` est faux dès qu'il existe un finding
de sévérité `error`.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from .base import (
    Check,
    CheckResult,
    Finding,
    Severity,
    Status,
    VerificationContext,
)

logger = logging.getLogger(__name__)

DEFAULT_PENALTIES: Dict[Severity, float] = {
    Severity.ERROR: 0.35,
    Severity.WARNING: 0.10,
    Severity.INFO: 0.0,
}

STATUS_VERIFIED = "verified"      # au moins un check passé, aucun avertissement
STATUS_WARNINGS = "warnings"      # avertissements, aucune erreur
STATUS_FAILED = "failed"          # au moins une erreur
STATUS_UNVERIFIED = "unverified"  # rien n'a pu être vérifié (tout est skipped / errored)

MAX_REPAIR_FINDINGS = 8


@dataclass
class Verdict:
    passed: bool
    score: float
    status: str
    results: List[CheckResult] = field(default_factory=list)
    duration_ms: int = 0
    timed_out: bool = False
    rounds: int = 0          # nombre de régénérations effectuées (mode gate)
    repaired: bool = False   # la réponse livrée est issue d'une réparation

    @property
    def findings(self) -> List[Finding]:
        return [f for r in self.results for f in r.findings]

    @property
    def issues(self) -> List[Dict[str, Any]]:
        return [f.to_dict(check=r.name) for r in self.results for f in r.findings]

    @property
    def repair_hint(self) -> str:
        """Constats actionnables (erreurs d'abord) à renvoyer au générateur."""
        ordered = sorted(
            ((r.name, f) for r in self.results for f in r.findings if f.severity != Severity.INFO),
            key=lambda item: 0 if item[1].severity == Severity.ERROR else 1,
        )
        return "\n".join(f"- [{f.severity.value}] {f.message}" for _name, f in ordered[:MAX_REPAIR_FINDINGS])

    def needs_repair(self, min_score: float) -> bool:
        return (not self.passed) or self.score < min_score

    def to_dict(self) -> Dict[str, Any]:
        """Forme persistée (colonne JSON `verification`) et émise (`event: verdict`)."""
        return {
            "passed": self.passed,
            "status": self.status,
            "score": round(self.score, 3),
            "issues": self.issues,
            "checks": [
                {"name": r.name, "status": r.status.value, "ms": r.duration_ms, **({"note": r.note} if r.note else {})}
                for r in self.results
            ],
            "repair_hint": self.repair_hint,
            "rounds": self.rounds,
            "repaired": self.repaired,
            "timed_out": self.timed_out,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def unverified(cls, note: str = "") -> "Verdict":
        """Verdict neutre (vérification impossible) : n'empêche jamais la livraison."""
        results = [CheckResult.errored("pipeline", note)] if note else []
        return cls(passed=True, score=1.0, status=STATUS_UNVERIFIED, results=results)


class VerificationPipeline:
    def __init__(
        self,
        checks: Sequence[Check],
        *,
        penalties: Optional[Dict[Severity, float]] = None,
        timeout_seconds: Optional[float] = None,
    ):
        self.checks = list(checks)
        self.penalties = penalties or DEFAULT_PENALTIES
        self.timeout_seconds = timeout_seconds

    async def run(self, response: str, ctx: Optional[VerificationContext] = None) -> Verdict:
        ctx = ctx or VerificationContext()
        started = time.monotonic()
        results: List[CheckResult] = []
        timed_out = False

        try:
            if self.timeout_seconds:
                await asyncio.wait_for(self._run_all(response, ctx, results), timeout=self.timeout_seconds)
            else:
                await self._run_all(response, ctx, results)
        except asyncio.TimeoutError:
            timed_out = True
            logger.warning("Verification timed out after %ss (%d/%d checks done)",
                           self.timeout_seconds, len(results), len(self.checks))
            results.append(CheckResult.errored("pipeline", f"timed out after {self.timeout_seconds}s"))

        verdict = self._aggregate(results)
        verdict.timed_out = timed_out
        verdict.duration_ms = int((time.monotonic() - started) * 1000)
        self._log_verdict(verdict)
        return verdict

    @staticmethod
    def _log_verdict(verdict: Verdict) -> None:
        """Une ligne INFO par vérification (détail des constats en DEBUG)."""
        checks = ", ".join(
            f"{r.name}:{r.status.value}({r.duration_ms}ms{', ' + r.note if r.note else ''})" for r in verdict.results
        )
        issues = ", ".join(f"{f.code}[{f.severity.value}]" for f in verdict.findings[:12]) or "none"
        logger.info(
            "verification: status=%s passed=%s score=%.2f duration=%dms timed_out=%s | checks: %s | issues: %s",
            verdict.status, verdict.passed, verdict.score, verdict.duration_ms, verdict.timed_out, checks, issues,
        )
        for result in verdict.results:
            for finding in result.findings:
                logger.debug("verification finding [%s] %s: %s", result.name, finding.code, finding.message)

    async def _run_all(self, response: str, ctx: VerificationContext, results: List[CheckResult]) -> None:
        for check in self.checks:
            results.append(await self._run_one(check, response, ctx, results))

    async def _run_one(
        self, check: Check, response: str, ctx: VerificationContext, prior: Sequence[CheckResult]
    ) -> CheckResult:
        name = getattr(check, "name", check.__class__.__name__)
        started = time.monotonic()
        try:
            if getattr(check, "blocking", False) and not inspect.iscoroutinefunction(check.run):
                result = await asyncio.to_thread(check.run, response, ctx, list(prior))
            else:
                result = check.run(response, ctx, list(prior))
                if inspect.isawaitable(result):
                    result = await result
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Verification check %r crashed", name)
            result = CheckResult.errored(name, f"check crashed: {exc}")
        result.duration_ms = int((time.monotonic() - started) * 1000)
        if not result.name:
            result.name = name
        return result

    def _aggregate(self, results: List[CheckResult]) -> Verdict:
        findings = [f for r in results for f in r.findings]
        penalty = sum(self.penalties.get(f.severity, 0.0) for f in findings)
        score = max(0.0, 1.0 - penalty)
        has_error = any(f.severity == Severity.ERROR for f in findings)
        has_warning = any(f.severity == Severity.WARNING for f in findings)
        any_passed = any(r.status in (Status.PASSED, Status.FAILED) for r in results)

        if has_error:
            status = STATUS_FAILED
        elif has_warning:
            status = STATUS_WARNINGS
        elif any_passed:
            status = STATUS_VERIFIED
        else:
            status = STATUS_UNVERIFIED
        return Verdict(passed=not has_error, score=score, status=status, results=results)
