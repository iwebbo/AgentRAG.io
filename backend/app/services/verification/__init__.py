"""
Couche de vérification des réponses LLM (chat, RAG chat).

Le noyau est pur (stdlib + PyYAML optionnel) : ce package n'importe rien de
l'application, il se teste donc en CI sans base de données ni LLM.

    from app.services.verification import (
        VerificationContext, build_pipeline, run_verified_stream,
    )
"""
from .base import (
    Check,
    CheckResult,
    Finding,
    Severity,
    Status,
    VerificationContext,
)
from .citations import CitationCheck, extract_citation_numbers
from .code import CodeBlockCheck, RuffRunner
from .factory import build_pipeline, pipeline_from_settings, resolve_mode
from .judge import JudgeCheck, make_complete
from .orchestrator import MODES, StreamEvent, normalize_mode, run_verified_stream
from .pipeline import Verdict, VerificationPipeline
from .retrieval import RetrievalCheck
from .sanity import SanityCheck
from .schema import SchemaCheck, validate_schema
from .sse import SSE_KEEPALIVE, format_sse, status_payload, verdict_payload

__all__ = [
    "Check", "CheckResult", "Finding", "Severity", "Status", "VerificationContext",
    "CitationCheck", "extract_citation_numbers", "CodeBlockCheck", "RuffRunner",
    "JudgeCheck", "make_complete", "RetrievalCheck", "SanityCheck", "SchemaCheck", "validate_schema",
    "Verdict", "VerificationPipeline", "build_pipeline", "pipeline_from_settings", "resolve_mode",
    "MODES", "StreamEvent", "normalize_mode", "run_verified_stream",
    "SSE_KEEPALIVE", "format_sse", "status_payload", "verdict_payload",
]
