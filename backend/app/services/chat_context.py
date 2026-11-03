"""Préparation du contexte LLM pour le chat simple (sans RAG).

Logique pure (pas d'I/O) : reconstruit prompt système + historique COMPLET +
nouvelle question, mesure le total avec le même budget que le chat RAG
(`context_budget`, `conversation_context`, `model_limit`) et expose le
résultat. Aucune troncature : l'appelant refuse (400) si `usage.overflow`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from app.services.context_budget import ContextUsage, count_tokens
from app.services.conversation_context import History, build_history
from app.services.model_limits import get_model_limit

REASONING_INSTRUCTIONS = {
    "cot": (
        "Solve step by step. Use this format:\n\n"
        "**Step 1:** [Describe]\n"
        "**Reasoning:** [Explain]\n"
        "**Step 2:** ...\n\n"
        "**Final Answer:** [Your answer here]"
    ),
    "deep": (
        "Provide a deep, multi-perspective analysis. "
        "Break down the problem, explore alternatives, validate assumptions with examples or logic, "
        "and deliver a comprehensive, nuanced final answer."
    ),
}


@dataclass(frozen=True)
class PreparedChat:
    messages: list  # prêt à envoyer au provider
    usage: ContextUsage
    history: History


def build_system_prompt(system_prompt: Optional[str], reasoning_mode: Optional[str]) -> str:
    """Un seul message system (certains templates Gemma/Mistral n'en acceptent qu'un)."""
    parts = [system_prompt or "", REASONING_INSTRUCTIONS.get(reasoning_mode or "", "")]
    return "\n\n".join(p for p in parts if p)


def prepare_chat_context(
    past_messages: Sequence,
    system_prompt: Optional[str],
    reasoning_mode: Optional[str],
    question: str,
    model: str,
) -> PreparedChat:
    """`past_messages` : messages persistés AVANT la question courante, ordre chronologique."""
    limit = get_model_limit(model)
    history = build_history(past_messages)
    system = build_system_prompt(system_prompt, reasoning_mode)

    messages: list = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.extend(history.messages)
    messages.append({"role": "user", "content": question})

    usage = ContextUsage(
        limit=limit,
        system_tokens=count_tokens(system),
        history_tokens=history.tokens,
        question_tokens=count_tokens(question),
        history_messages=len(history.messages),
        carried_chunks=history.carried_chunks,
    )
    return PreparedChat(messages=messages, usage=usage, history=history)