"""
Configuration des embeddings : AUCUNE dépendance lourde (ni torch ni sentence-transformers).

Source de vérité du nom de modèle, partagée par `embeddings.py` (chargement du modèle) et
`vector_store.py` (étiquetage et contrôle des collections). Le modèle se choisit par la variable
d'environnement EMBEDDING_MODEL ; sans variable, on garde all-MiniLM-L6-v2 (comportement historique).
"""
from __future__ import annotations

import os
from typing import Optional

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Modèles dont le code distant (trust_remote_code) est accepté sans réglage supplémentaire.
# Tout autre modèle exigeant du code distant demande EMBEDDING_TRUST_REMOTE_CODE=true.
TRUSTED_REMOTE_CODE_MODELS = frozenset({"jinaai/jina-embeddings-v2-base-code"})

# Plafond appliqué par défaut à la fenêtre de séquence (CPU/mémoire). Un chunk de 600 tokens tient dans 1024.
DEFAULT_MAX_SEQ_CAP = 1024


def normalize_model_name(name: str) -> str:
    """'all-MiniLM-L6-v2' et 'sentence-transformers/all-MiniLM-L6-v2' désignent le même modèle."""
    name = (name or "").strip()
    if not name:
        return DEFAULT_MODEL
    if "/" in name or os.path.isdir(name):
        return name
    return f"sentence-transformers/{name}"


def configured_model_name(override: Optional[str] = None) -> str:
    """Nom normalisé du modèle configuré, sans charger quoi que ce soit."""
    return normalize_model_name(override or os.getenv("EMBEDDING_MODEL") or DEFAULT_MODEL)


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def env_int(name: str) -> Optional[int]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None
