"""
Orchestrateur de livraison : off / annotate / gate.

C'est le seul endroit qui connaît l'articulation « génération en streaming » ↔
« vérification ». Les routes ne font que traduire les `StreamEvent` en SSE.

Modes
-----
off       pass-through : les tokens sont émis au fil de l'eau, aucune vérification.
annotate  les tokens sont émis au fil de l'eau (aucune latence ajoutée sur le texte) ;
          la réponse est vérifiée une fois complète, le verdict arrive ensuite.
gate      la réponse est générée en tampon, vérifiée ; si elle échoue, elle est
          régénérée avec les constats concrets (max `max_rounds` tours) ; la
          meilleure version est ensuite rejouée en tokens. Le client reçoit des
          `status` pendant l'attente, et des `keepalive` pour que les proxys ne
          coupent pas la connexion.

Événements émis (`StreamEvent.kind`)
-----------------------------------
token      str   : morceau de texte à afficher
status     dict  : {"phase": generating|verifying|repairing, "round": n}
keepalive  None  : à traduire en commentaire SSE
final      str   : texte définitif (à persister) — émis avant le verdict ; en annotate avant
                     même la vérification, en gate avant le rejeu des tokens
verdict    Verdict (absent en mode off)

Garanties
---------
- Une erreur de GÉNÉRATION se propage à l'appelant (comportement inchangé).
- Une erreur de VÉRIFICATION ne casse jamais la réponse : verdict neutre `unverified`.
- Le mode gate ne retient jamais silencieusement une réponse en échec : si les tours de
  réparation sont épuisés, la meilleure version est livrée avec son verdict `failed`.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import aclosing
from dataclasses import dataclass
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional, Tuple

from .base import VerificationContext
from .pipeline import Verdict, VerificationPipeline

logger = logging.getLogger(__name__)

MODES = ("off", "annotate", "gate")
OpenStream = Callable[[List[Dict[str, str]]], AsyncIterator[str]]


@dataclass
class StreamEvent:
    kind: str
    data: Any = None


def normalize_mode(value: Optional[str], default: str = "annotate") -> str:
    """`off` | `annotate` | `gate`. Toute valeur inconnue → default (jamais d'exception)."""
    candidate = (value or "").strip().lower()
    if candidate in MODES:
        return candidate
    return default if default in MODES else "annotate"


def build_repair_messages(messages: List[Dict[str, str]], draft: str, verdict: Verdict) -> List[Dict[str, str]]:
    """Conversation de réparation : question initiale + brouillon + constats concrets."""
    instruction = (
        "An automated review of your previous answer found problems that must be fixed:\n"
        f"{verdict.repair_hint}\n\n"
        "Rewrite the COMPLETE answer fixing every problem above. "
        "Keep the same language as your previous answer. "
        "Cite only sources that exist. Return full, working code with no placeholders. "
        "Do not mention this review and do not apologise."
    )
    return list(messages) + [
        {"role": "assistant", "content": draft},
        {"role": "user", "content": instruction},
    ]


async def _collect(open_stream: OpenStream, messages: List[Dict[str, str]]) -> str:
    parts: List[str] = []
    async for chunk in open_stream(messages):
        parts.append(chunk)
    return "".join(parts)


class _Box:
    """Récupère la valeur de retour d'un générateur asynchrone (qui ne peut pas `return` une valeur)."""

    value: Any = None


async def _drive(awaitable: Awaitable[Any], interval: float, box: _Box) -> AsyncIterator[StreamEvent]:
    """
    Attend `awaitable` en émettant un `keepalive` toutes les `interval` secondes ; le résultat
    est déposé dans `box.value` (ou l'exception de la tâche est relevée). Si le consommateur
    abandonne (déconnexion client), la tâche est annulée.
    """
    task = asyncio.ensure_future(awaitable)
    try:
        while True:
            done, _pending = await asyncio.wait({task}, timeout=interval)
            if done:
                box.value = task.result()
                return
            yield StreamEvent("keepalive")
    finally:
        if not task.done():
            task.cancel()


async def _verify(pipeline: VerificationPipeline, text: str, ctx: VerificationContext) -> Verdict:
    """Vérification sans jamais lever (hors annulation)."""
    try:
        return await pipeline.run(text, ctx)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception("Verification pipeline crashed")
        return Verdict.unverified(f"pipeline crashed: {exc}")


Candidate = Tuple[str, Verdict]


def _better(candidate: Candidate, best: Optional[Candidate]) -> Candidate:
    if best is None:
        return candidate
    # (réponse sans erreur, score) ; à égalité on garde la plus ancienne
    return candidate if (candidate[1].passed, candidate[1].score) > (best[1].passed, best[1].score) else best


async def run_verified_stream(
    *,
    open_stream: OpenStream,
    messages: List[Dict[str, str]],
    ctx: VerificationContext,
    pipeline: Optional[VerificationPipeline],
    mode: str = "annotate",
    max_rounds: int = 2,
    min_score: float = 0.7,
    keepalive_seconds: float = 10.0,
    replay_chunk_chars: int = 120,
) -> AsyncIterator[StreamEvent]:
    mode = normalize_mode(mode)
    logger.info(
        "verification start: mode=%s rag=%s chunks=%d pipeline=%s max_rounds=%d min_score=%.2f",
        mode, ctx.is_rag, len(ctx.retrieved_chunks or []), "yes" if pipeline is not None else "no",
        max_rounds, min_score,
    )

    if pipeline is None or mode == "off":
        parts: List[str] = []
        async for chunk in open_stream(messages):
            parts.append(chunk)
            yield StreamEvent("token", chunk)
        yield StreamEvent("final", "".join(parts))
        return

    if mode == "annotate":
        parts = []
        async for chunk in open_stream(messages):
            parts.append(chunk)
            yield StreamEvent("token", chunk)
        text = "".join(parts)
        # `final` AVANT la vérification : l'appelant peut persister la réponse tout de suite
        # (elle n'est pas perdue si le client se déconnecte pendant le juge).
        yield StreamEvent("final", text)
        yield StreamEvent("status", {"phase": "verifying", "round": 0})
        box = _Box()
        async with aclosing(_drive(_verify(pipeline, text, ctx), keepalive_seconds, box)) as events:
            async for event in events:
                yield event
        yield StreamEvent("verdict", box.value or Verdict.unverified())
        return

    # ── gate ──────────────────────────────────────────────────────────────────────
    best: Optional[Candidate] = None
    current_messages = messages
    attempts = 0  # nombre de régénérations effectuées
    for round_index in range(max_rounds + 1):
        yield StreamEvent("status", {"phase": "generating" if round_index == 0 else "repairing", "round": round_index})
        box = _Box()
        async with aclosing(_drive(_collect(open_stream, current_messages), keepalive_seconds, box)) as events:
            async for event in events:
                yield event
        draft: str = box.value or ""

        yield StreamEvent("status", {"phase": "verifying", "round": round_index})
        box = _Box()
        async with aclosing(_drive(_verify(pipeline, draft, ctx), keepalive_seconds, box)) as events:
            async for event in events:
                yield event
        verdict: Verdict = box.value or Verdict.unverified()
        verdict.repaired = round_index > 0  # ce candidat est issu d'une réparation
        best = _better((draft, verdict), best)

        needs_repair = verdict.needs_repair(min_score)
        reason = "error" if not verdict.passed else (f"score<{min_score:.2f}" if needs_repair else "ok")
        logger.info(
            "gate round %d/%d: status=%s score=%.2f needs_repair=%s (%s)",
            round_index, max_rounds, verdict.status, verdict.score, needs_repair, reason,
        )
        if not needs_repair:
            break
        if round_index == max_rounds:
            logger.warning(
                "gate: repair rounds exhausted (%d), delivering the best version anyway", max_rounds
            )
            break
        attempts = round_index + 1
        current_messages = build_repair_messages(messages, draft, verdict)

    assert best is not None
    final_text, final_verdict = best
    final_verdict.rounds = attempts
    logger.info(
        "gate delivered: status=%s score=%.2f repaired=%s regenerations=%d chars=%d",
        final_verdict.status, final_verdict.score, final_verdict.repaired, attempts, len(final_text),
    )
    # `final` d'abord : la réponse validée est persistable avant le rejeu (déconnexion client).
    yield StreamEvent("final", final_text)
    step = max(1, replay_chunk_chars)
    for start in range(0, len(final_text), step):
        yield StreamEvent("token", final_text[start:start + step])
        await asyncio.sleep(0)
    yield StreamEvent("verdict", final_verdict)
