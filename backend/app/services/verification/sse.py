"""
Formatage SSE des événements de vérification.

Le payload porte toujours un champ `type` : le parseur du chat standard
(frontend/src/services/streaming.js) lit `data.type` et ignore les types inconnus ;
le parseur du RAG chat ignore les noms d'événements inconnus. Ni l'un ni l'autre
n'a besoin d'être modifié pour que ces événements soient inoffensifs.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from .pipeline import Verdict

SSE_KEEPALIVE = ": keepalive\n\n"  # commentaire SSE : ignoré par les clients, maintient la connexion


def format_sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def status_payload(status: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": "status", **status}


def verdict_payload(verdict: Verdict) -> Dict[str, Any]:
    return {"type": "verdict", **verdict.to_dict()}
