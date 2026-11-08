"""
Sélection des chunks injectés dans le contexte RAG.

Avant : le contexte était rempli jusqu'à `max_tokens` avec les top_k résultats, pertinents ou non.
Maintenant : on garde les chunks proches du meilleur score, et on s'arrête dès que la pertinence
décroche. Le contexte est dimensionné par la question, pas par le budget.

Règles (score = 1 - distance cosinus, résultats triés par score décroissant) :
  1. les `min_keep` meilleurs chunks sont toujours gardés (un seuil mal calibré ne vide jamais le contexte) ;
  2. un chunk est coupé s'il est sous `min_score` (plancher absolu) ;
  3. un chunk est coupé s'il est à plus de `rel_drop` sous le meilleur score (coupure relative) ;
  4. au plus `max_chunks` chunks.

Réglages (variables d'environnement, prioritaires sur les valeurs par stratégie) :
  RAG_SELECTION    on | off      off = ancien comportement (remplir le budget)
  RAG_MIN_SCORE    défaut 0.20
  RAG_REL_DROP     défaut 0.18
  RAG_MAX_CHUNKS   défaut 12
  RAG_MIN_KEEP     défaut 2

Les scores dépendent du modèle d'embedding : calibrer min_score / rel_drop sur ses propres
questions (le log "RAG selection" donne best, floor, gardés/total pour chaque requête).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

Selected = Tuple[str, Dict[str, Any], float]  # (texte, metadata, score)


def _env_float(name: str) -> Optional[float]:
    raw = os.getenv(name, "").strip()
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


def _env_int(name: str) -> Optional[int]:
    value = _env_float(name)
    return int(value) if value is not None else None


@dataclass(frozen=True)
class SelectionConfig:
    enabled: bool = True
    min_score: float = 0.20
    rel_drop: float = 0.18
    max_chunks: int = 12
    min_keep: int = 2

    @classmethod
    def from_env(cls, strategy: Optional[dict] = None) -> "SelectionConfig":
        """Priorité : variable d'environnement > valeur de la stratégie > défaut."""
        strategy = strategy or {}

        def pick(env_value, key, default):
            if env_value is not None:
                return env_value
            return strategy.get(key, default)

        return cls(
            enabled=os.getenv("RAG_SELECTION", "on").strip().lower() not in ("off", "false", "0", "no"),
            min_score=float(pick(_env_float("RAG_MIN_SCORE"), "min_score", cls.min_score)),
            rel_drop=float(pick(_env_float("RAG_REL_DROP"), "rel_drop", cls.rel_drop)),
            max_chunks=max(1, int(pick(_env_int("RAG_MAX_CHUNKS"), "max_chunks", cls.max_chunks))),
            min_keep=max(1, int(pick(_env_int("RAG_MIN_KEEP"), "min_keep", cls.min_keep))),
        )


def select_chunks(results: Dict[str, Any], cfg: SelectionConfig) -> Tuple[List[Selected], Dict[str, Any]]:
    """Retourne (chunks retenus, statistiques) à partir d'un résultat de vector_store.query()."""
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    dists = results["distances"][0]
    items: List[Selected] = [(d, m, 1.0 - float(x)) for d, m, x in zip(docs, metas, dists)]
    total = len(items)

    if not items:
        return [], {"total": 0, "kept": 0, "best": 0.0, "floor": 0.0, "enabled": cfg.enabled}

    best = max(score for _, _, score in items)
    floor = max(cfg.min_score, best - cfg.rel_drop)

    if not cfg.enabled:
        return items, {"total": total, "kept": total, "best": best, "floor": floor, "enabled": False}

    ranked = sorted(items, key=lambda it: -it[2])
    kept: List[Selected] = []
    for rank, item in enumerate(ranked):
        if len(kept) >= cfg.max_chunks:
            break
        if rank >= cfg.min_keep and item[2] < floor:
            break  # trié : tous les suivants sont sous le seuil aussi
        kept.append(item)

    return kept, {"total": total, "kept": len(kept), "best": best, "floor": floor, "enabled": True}
