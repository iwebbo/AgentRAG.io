"""
Types de base du noyau de vérification + utilitaires de texte.

Ce module est volontairement pur : stdlib uniquement, aucune dépendance à
l'application (base de données, provider LLM, settings). Il est testable en CI
sans LLM.

Vocabulaire
-----------
Finding        un constat produit par un check (code stable, sévérité, message).
CheckResult    le résultat d'un check (statut + liste de findings).
Verdict        l'agrégat de tous les checks (passed, score, issues, repair_hint).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Dict, List, Optional, Protocol, Sequence, Union, runtime_checkable


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


_SEVERITY_ORDER = {Severity.INFO: 0, Severity.WARNING: 1, Severity.ERROR: 2}


def max_severity(severities: Sequence[Severity]) -> Optional[Severity]:
    if not severities:
        return None
    return max(severities, key=lambda s: _SEVERITY_ORDER[s])


class Status(str, Enum):
    PASSED = "passed"      # le check s'est exécuté et n'a rien trouvé de bloquant
    FAILED = "failed"      # au moins un finding
    SKIPPED = "skipped"    # check non applicable à cette réponse / ce contexte
    ERRORED = "errored"    # le check lui-même a planté (ne bloque jamais la réponse)


EVIDENCE_MAX_CHARS = 300


def _clip(value: Any, limit: int = EVIDENCE_MAX_CHARS) -> Any:
    """Borne récursivement les chaînes d'une evidence (persistée en base)."""
    if isinstance(value, str):
        return value if len(value) <= limit else value[: limit - 1] + "…"
    if isinstance(value, dict):
        return {str(k): _clip(v, limit) for k, v in list(value.items())[:20]}
    if isinstance(value, (list, tuple)):
        return [_clip(v, limit) for v in list(value)[:20]]
    return value


@dataclass
class Finding:
    code: str                      # stable, ex. "citation.out_of_range"
    severity: Severity
    message: str                   # lisible, aussi réutilisé dans le prompt de réparation
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, check: Optional[str] = None) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "code": self.code,
            "severity": self.severity.value,
            "message": _clip(self.message, 500),
        }
        if check:
            data["check"] = check
        if self.evidence:
            data["evidence"] = _clip(self.evidence)
        return data


@dataclass
class CheckResult:
    name: str
    status: Status
    findings: List[Finding] = field(default_factory=list)
    duration_ms: int = 0
    note: str = ""

    @property
    def severity(self) -> Optional[Severity]:
        return max_severity([f.severity for f in self.findings])

    @classmethod
    def passed(cls, name: str, note: str = "") -> "CheckResult":
        return cls(name=name, status=Status.PASSED, note=note)

    @classmethod
    def skipped(cls, name: str, note: str = "") -> "CheckResult":
        return cls(name=name, status=Status.SKIPPED, note=note)

    @classmethod
    def errored(cls, name: str, note: str) -> "CheckResult":
        return cls(name=name, status=Status.ERRORED, note=note)

    @classmethod
    def from_findings(cls, name: str, findings: List[Finding], note: str = "") -> "CheckResult":
        if findings:
            return cls(name=name, status=Status.FAILED, findings=findings, note=note)
        return cls(name=name, status=Status.PASSED, note=note)


@dataclass
class VerificationContext:
    """Ce que les checks ont le droit de savoir sur la requête."""

    question: str = ""
    retrieved_chunks: List[Dict[str, Any]] = field(default_factory=list)  # {text, metadata, score}
    is_rag: bool = False
    query_type: Optional[str] = None
    expected_format: Optional[str] = None      # "json" | "yaml" | None
    expected_schema: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


CheckOutput = Union[CheckResult, Awaitable[CheckResult]]


@runtime_checkable
class Check(Protocol):
    """
    Contrat d'un check.

    `run` peut être synchrone ou `async`. Si le check bloque (subprocess, I/O),
    il déclare `blocking = True` et le pipeline l'exécute dans un thread.
    `prior` contient les résultats des checks déjà exécutés (le juge s'en sert
    comme evidence).
    """

    name: str

    def run(self, response: str, ctx: VerificationContext, prior: Sequence[CheckResult]) -> CheckOutput:
        ...


# ─────────────────────────────── utilitaires texte ──────────────────────────────

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN_RE = re.compile(r"<think>", re.IGNORECASE)
_THINK_CLOSE_RE = re.compile(r"</think>", re.IGNORECASE)


def strip_think(text: str) -> str:
    """
    Retire le raisonnement des modèles « reasoning » (<think>…</think>).

    - bloc complet           → retiré
    - `<think>` jamais fermé → tout ce qui suit est du raisonnement tronqué, retiré
    - `</think>` orphelin    → on garde ce qui suit (certains serveurs omettent l'ouverture)
    """
    text = text or ""
    text = _THINK_BLOCK_RE.sub("", text)
    open_match = _THINK_OPEN_RE.search(text)
    if open_match:
        text = text[: open_match.start()]
    close_match = _THINK_CLOSE_RE.search(text)
    if close_match:
        text = text[close_match.end():]
    return text.strip()


@dataclass
class FencedBlock:
    lang: str
    code: str
    start_line: int      # numéro de ligne (1-based) de la ligne d'ouverture
    closed: bool


_FENCE_OPEN_RE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})[ \t]*(?P<info>[^`\n]*)$")


def extract_fenced_blocks(text: str) -> List[FencedBlock]:
    """Extrait les blocs ``` / ~~~ (Markdown). Un bloc non refermé est signalé `closed=False`."""
    blocks: List[FencedBlock] = []
    lines = (text or "").split("\n")
    i = 0
    while i < len(lines):
        match = _FENCE_OPEN_RE.match(lines[i])
        if not match:
            i += 1
            continue
        fence = match.group("fence")
        info = (match.group("info") or "").strip()
        lang = info.split()[0].lower() if info else ""
        lang = lang.strip("{}.")
        body: List[str] = []
        closed = False
        j = i + 1
        while j < len(lines):
            stripped = lines[j].strip()
            if stripped and set(stripped) == {fence[0]} and len(stripped) >= len(fence):
                closed = True
                break
            body.append(lines[j])
            j += 1
        blocks.append(FencedBlock(lang=lang, code="\n".join(body), start_line=i + 1, closed=closed))
        i = j + 1
    return blocks


def strip_fenced_blocks(text: str) -> str:
    """Texte sans les blocs de code (pour compter citations / prose)."""
    out: List[str] = []
    lines = (text or "").split("\n")
    i = 0
    while i < len(lines):
        match = _FENCE_OPEN_RE.match(lines[i])
        if not match:
            out.append(lines[i])
            i += 1
            continue
        fence = match.group("fence")
        j = i + 1
        while j < len(lines):
            stripped = lines[j].strip()
            if stripped and set(stripped) == {fence[0]} and len(stripped) >= len(fence):
                break
            j += 1
        i = j + 1
    return "\n".join(out)


def extract_json_object(text: str) -> Optional[Any]:
    """
    Extrait un objet JSON d'une sortie de LLM (fences, <think>, texte autour).
    Retourne None si rien d'exploitable.
    """
    import json

    cleaned = strip_think(text)
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned.strip(), flags=re.IGNORECASE).strip()
    for candidate in (cleaned,):
        try:
            return json.loads(candidate)
        except ValueError:
            pass
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except ValueError:
            return None
    return None
