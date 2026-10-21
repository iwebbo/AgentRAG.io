"""
Assemblage du pipeline à partir de la configuration.

Aucun import de l'application : `settings` est lu par duck-typing (getattr avec valeurs par
défaut), donc ce module reste testable sans base de données ni variables d'environnement.
"""
from __future__ import annotations

from typing import Any, Optional

from .citations import CitationCheck
from .code import CodeBlockCheck, LintRunner
from .judge import CompleteFn, JudgeCheck
from .orchestrator import normalize_mode
from .pipeline import VerificationPipeline
from .retrieval import RetrievalCheck
from .sanity import SanityCheck
from .schema import SchemaCheck


def build_pipeline(
    *,
    is_rag: bool,
    judge_complete: Optional[CompleteFn] = None,
    judge_mode: str = "auto",
    min_retrieval_score: float = 0.25,
    use_ruff: bool = True,
    timeout_seconds: Optional[float] = 45.0,
    lint: Optional[LintRunner] = None,
) -> VerificationPipeline:
    """
    Ordre = déterministe d'abord, juge en dernier (il reçoit les constats précédents).

      RAG  : sanity → citations → retrieval → code → schema → judge
      chat : sanity →                         code → schema → judge
    """
    checks = [SanityCheck()]
    if is_rag:
        checks += [CitationCheck(), RetrievalCheck(min_score=min_retrieval_score)]
    checks += [CodeBlockCheck(lint=lint, use_ruff=use_ruff), SchemaCheck()]
    if judge_complete is not None and judge_mode != "off":
        checks.append(JudgeCheck(judge_complete, mode=judge_mode))
    return VerificationPipeline(checks, timeout_seconds=timeout_seconds)


def pipeline_from_settings(
    settings: Any, *, is_rag: bool, judge_complete: Optional[CompleteFn] = None
) -> VerificationPipeline:
    judge_mode = str(getattr(settings, "VERIFY_JUDGE", "auto") or "auto").lower()
    if judge_mode not in ("off", "auto", "always"):
        judge_mode = "auto"
    return build_pipeline(
        is_rag=is_rag,
        judge_complete=judge_complete,
        judge_mode=judge_mode,
        min_retrieval_score=float(getattr(settings, "RAG_MIN_SCORE", 0.25)),
        use_ruff=bool(getattr(settings, "VERIFY_RUFF", True)),
        timeout_seconds=float(getattr(settings, "VERIFY_TIMEOUT_SECONDS", 45)),
    )


def resolve_mode(request_mode: Optional[str], settings: Any) -> str:
    """Priorité : valeur de la requête > settings.VERIFY_MODE > annotate."""
    default = normalize_mode(getattr(settings, "VERIFY_MODE", None), "annotate")
    return normalize_mode(request_mode, default) if request_mode else default
