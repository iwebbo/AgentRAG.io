"""Comptage de tokens et suivi du contexte LLM (logique pure, sans I/O)."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache

import tiktoken

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        logger.warning("%s invalide, valeur par défaut %s utilisée", name, default)
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        logger.warning("%s invalide, valeur par défaut %s utilisée", name, default)
        return default


# Tokens réservés à la réponse du modèle (plafonné à 25 % de la limite)
OUTPUT_RESERVE = _env_int("CONTEXT_OUTPUT_RESERVE", 4096)
# Marge sur l'estimation (les tokenizers non-OpenAI divergent de ~10-15 %)
SAFETY_FACTOR = _env_float("CONTEXT_SAFETY_FACTOR", 1.10)
# Seuil (%) à partir duquel l'usage est loggé en WARNING
WARN_PERCENT = _env_float("CONTEXT_WARN_PERCENT", 80.0)
# Tokens réservés au gabarit du system prompt (règles, bloc de raisonnement), hors RAG
PROMPT_OVERHEAD = _env_int("CONTEXT_PROMPT_OVERHEAD", 600)


class ContextOverflow(Exception):
    """Le contexte dépasse la limite du modèle."""


@lru_cache(maxsize=1)
def _encoder():
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        logger.warning(
            "tiktoken indisponible (cache absent / pas d'egress) → fallback len//4. "
            "Embarquer l'encodage dans l'image Docker (TIKTOKEN_CACHE_DIR)."
        )
        return None


def count_tokens(text: str) -> int:
    """Estime le nombre de tokens, avec marge de sécurité."""
    if not text:
        return 0
    enc = _encoder()
    n = len(enc.encode(text, disallowed_special=())) if enc else len(text) // 4
    return int(n * SAFETY_FACTOR) + 1


def output_reserve(limit: int) -> int:
    return min(OUTPUT_RESERVE, limit // 4)


def rag_room(limit: int, history_tokens: int, question_tokens: int) -> int:
    """Tokens disponibles pour le contexte RAG du tour courant, une fois
    réservés : la réponse, le gabarit du system prompt, l'historique COMPLET
    et la question."""
    return limit - output_reserve(limit) - PROMPT_OVERHEAD - history_tokens - question_tokens


@dataclass(frozen=True)
class ContextUsage:
    """Décomposition du contexte réellement envoyé au LLM pour ce tour."""

    limit: int
    system_tokens: int  # index projet + chunks du tour + règles
    history_tokens: int  # tours précédents (questions + contexte documentaire + réponses)
    question_tokens: int
    history_messages: int = 0
    carried_chunks: int = 0  # chunks de tours précédents réinjectés

    @property
    def used(self) -> int:
        return self.system_tokens + self.history_tokens + self.question_tokens

    @property
    def reserve(self) -> int:
        return output_reserve(self.limit)

    @property
    def percent(self) -> float:
        return self.used / self.limit * 100 if self.limit else 0.0

    @property
    def overflow(self) -> bool:
        return self.used > self.limit - self.reserve

    def log_line(self) -> str:
        return (
            f"Total context: {self.used:,}/{self.limit:,} tokens ({self.percent:.1f}%) "
            f"= system/RAG {self.system_tokens:,} + historique {self.history_tokens:,} "
            f"+ question {self.question_tokens:,}"
        )

    def to_event(self) -> dict:
        """Payload de l'event SSE `context` (jauge used/limit côté front)."""
        return {
            "used": self.used,
            "limit": self.limit,
            "percent": round(self.percent, 1),
            "system_rag": self.system_tokens,
            "history": self.history_tokens,
            "question": self.question_tokens,
            "history_messages": self.history_messages,
            "carried_chunks": self.carried_chunks,
            "output_reserve": self.reserve,
        }