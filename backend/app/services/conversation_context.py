"""Reconstruction de l'historique COMPLET d'une conversation RAG.

Chaque tour est rejoué tel que le LLM l'a vu : le contexte documentaire
(chunks lus dans `RAGMessage.retrieved_chunks` de la réponse) + la question,
puis la réponse. Aucune troncature : si le total dépasse la limite, c'est
la route qui refuse explicitement (400) plutôt que de perdre du contexte.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from app.services.context_budget import count_tokens

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class History:
    messages: list = field(default_factory=list)  # dicts {"role", "content"}
    tokens: int = 0
    carried_chunks: int = 0  # chunks de tours précédents réinjectés
    skipped_messages: int = 0  # tours sans réponse (stream en échec), ignorés


def chunk_hash(chunk: dict) -> str:
    meta = chunk.get("metadata") or {}
    key = f"{meta.get('filename', '')}\x00{chunk.get('text', '')}"
    return hashlib.sha1(key.encode("utf-8", "ignore")).hexdigest()


def parse_chunks(raw) -> list[dict]:
    """`retrieved_chunks` est stocké en JSON (str) ; accepte aussi une liste."""
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return []
    if not isinstance(raw, list):
        return []
    return [c for c in raw if isinstance(c, dict) and c.get("text")]


def render_turn(question: str, chunks: Sequence[dict]) -> str:
    if not chunks:
        return question
    blocks = "\n".join(
        f"### {(c.get('metadata') or {}).get('filename', 'unknown')}\n```\n{c['text']}\n```"
        for c in chunks
    )
    return (
        f"[CONTEXTE DOCUMENTAIRE DE CE TOUR]\n{blocks}\n[FIN CONTEXTE]\n\n"
        f"QUESTION :\n{question}"
    )


def build_history(past_messages: Sequence, exclude: Iterable[str] = ()) -> History:
    """Historique complet, alterné user/assistant.

    - Chaque question user est précédée des chunks qui avaient servi à y répondre.
    - Un chunk n'est inclus qu'à sa première occurrence ; `exclude` contient les
      hash des chunks du tour courant (déjà dans le system prompt).
    - Un message user sans réponse assistant (tour en échec) est ignoré, pour
      garder l'alternance exigée par les templates de chat (Gemma, Mistral...).
    """
    seen = set(exclude)
    out: list[dict] = []
    tokens = 0
    carried = 0
    skipped = 0
    n = len(past_messages)

    for i, msg in enumerate(past_messages):
        if msg.role == "user":
            nxt = past_messages[i + 1] if i + 1 < n else None
            if nxt is None or nxt.role != "assistant":
                skipped += 1
                continue
            fresh: list[dict] = []
            for c in parse_chunks(getattr(nxt, "retrieved_chunks", None)):
                h = chunk_hash(c)
                if h not in seen:
                    seen.add(h)
                    fresh.append(c)
            carried += len(fresh)
            content = render_turn(msg.content, fresh)
        elif msg.role == "assistant":
            if not out or out[-1]["role"] != "user":
                skipped += 1
                continue
            content = msg.content
        else:
            continue

        out.append({"role": msg.role, "content": content})
        tokens += count_tokens(content)

    if skipped:
        logger.warning("📚 %d message(s) ignoré(s) dans l'historique (tour sans réponse)", skipped)
    return History(out, tokens, carried, skipped)