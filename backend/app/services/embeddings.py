"""
Point d'entrée UNIQUE des embeddings de l'application.

Tout ce qui est vectorisé (documents uploadés, dépôts Git / Drive, questions du chat RAG, skills) doit passer
par `EmbeddingManager` : l'application ne confie JAMAIS le calcul des vecteurs à ChromaDB (voir vector_store.py).

Réglages (variables d'environnement) :
  EMBEDDING_MODEL               modèle sentence-transformers (défaut all-MiniLM-L6-v2)
  EMBEDDING_MAX_SEQ_LENGTH      fenêtre de séquence imposée (défaut : min(fenêtre du modèle, 1024))
  EMBEDDING_BATCH_SIZE          taille de lot à l'encodage (défaut 32)
  EMBEDDING_REVISION            révision (commit) du modèle à charger, pour figer une version
  EMBEDDING_TRUST_REMOTE_CODE   true : autorise le code distant d'un modèle hors liste de confiance

`EmbeddingManager(...)` renvoie une instance PARTAGÉE par modèle : les `EmbeddingManager()` existants du code
(documents.py, rag_chat.py, skill_registry.py, agents…) partagent donc une seule copie du modèle en mémoire.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Dict, List, Optional

import torch
from sentence_transformers import SentenceTransformer

from app.services.embedding_config import (
    DEFAULT_MAX_SEQ_CAP,
    TRUSTED_REMOTE_CODE_MODELS,
    configured_model_name,
    env_flag,
    env_int,
)

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 32


class EmbeddingManager:
    """Gestionnaire d'embeddings (sentence-transformers). Une instance partagée par modèle."""

    _instances: Dict[str, "EmbeddingManager"] = {}
    _lock = threading.Lock()

    def __new__(cls, model_name: Optional[str] = None):
        name = configured_model_name(model_name)
        with cls._lock:  # le chargement se fait sous verrou : jamais deux copies du même modèle
            instance = cls._instances.get(name)
            if instance is None:
                instance = super().__new__(cls)
                instance._load(name)
                cls._instances[name] = instance
            return instance

    def __init__(self, model_name: Optional[str] = None):
        # Tout est fait dans __new__ (instance partagée) : __init__ est volontairement vide.
        pass

    # ------------------------------------------------------------------ chargement

    def _load(self, name: str) -> None:
        self.model_name = name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        kwargs = {"device": self.device}
        if name in TRUSTED_REMOTE_CODE_MODELS or env_flag("EMBEDDING_TRUST_REMOTE_CODE"):
            kwargs["trust_remote_code"] = True
        revision = os.getenv("EMBEDDING_REVISION", "").strip()
        if revision:
            kwargs["revision"] = revision

        self.model = SentenceTransformer(name, **kwargs)

        explicit = env_int("EMBEDDING_MAX_SEQ_LENGTH")
        current = getattr(self.model, "max_seq_length", None)
        if explicit:
            self.model.max_seq_length = explicit
        elif current is None or current > DEFAULT_MAX_SEQ_CAP:
            self.model.max_seq_length = DEFAULT_MAX_SEQ_CAP

        self.max_seq_length = self.model.max_seq_length
        self.dimension = int(self.model.get_sentence_embedding_dimension())
        self.batch_size = env_int("EMBEDDING_BATCH_SIZE") or DEFAULT_BATCH_SIZE
        logger.info(
            f"✅ Embedding model loaded: {name} on {self.device} "
            f"(dim={self.dimension}, max_seq_length={self.max_seq_length})"
        )

    # ------------------------------------------------------------------ API

    def encode(self, texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
        """Embeddings d'une liste de textes (documents)."""
        if not texts:
            return []
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size or self.batch_size,
            show_progress_bar=len(texts) > 10,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    def encode_single(self, text: str) -> List[float]:
        """Embedding d'un texte unique (question, skill)."""
        embedding = self.model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embedding.tolist()

    # Noms explicites pour le code futur (modèles à préfixes asymétriques) ; même comportement aujourd'hui.
    encode_documents = encode
    encode_query = encode_single


def get_embedder(model_name: Optional[str] = None) -> EmbeddingManager:
    """Embedder de référence de l'application (instance partagée)."""
    return EmbeddingManager(model_name)
