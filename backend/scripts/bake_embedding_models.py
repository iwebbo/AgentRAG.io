#!/usr/bin/env python3
"""
Pré-télécharge les modèles d'embedding (et le cache tiktoken) dans l'image Docker.

Sans cela, chaque pod télécharge le modèle depuis Hugging Face au premier appel (cache éphémère) : démarrage
lent, dépendance réseau au runtime, et échec silencieux derrière un proxy.

Utilise EXACTEMENT le chemin de code de l'application (EmbeddingManager) sans importer le paquet `app`
(app/__init__ et app/services/__init__ chargent la base de données, etc.).

Usage : python scripts/bake_embedding_models.py [modèle ...]   (défaut : variable BAKE_EMBEDDING_MODELS)
"""
import importlib.util
import os
import sys
import types

APP_SERVICES = os.path.join(os.environ.get("APP_DIR", "/app"), "app", "services")


def _load(qualified: str, filename: str):
    spec = importlib.util.spec_from_file_location(qualified, os.path.join(APP_SERVICES, filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    spec.loader.exec_module(module)
    return module


def load_embedding_manager():
    for pkg in ("app", "app.services"):
        sys.modules.setdefault(pkg, types.ModuleType(pkg)).__path__ = []
    _load("app.services.embedding_config", "embedding_config.py")
    return _load("app.services.embeddings", "embeddings.py").EmbeddingManager


def main(argv):
    names = argv or os.environ.get("BAKE_EMBEDDING_MODELS", "").replace(",", " ").split()
    if not names:
        print("bake: aucun modèle demandé, rien à faire")
        return 0
    manager_cls = load_embedding_manager()
    for name in names:
        m = manager_cls(name)
        vec = m.encode(["def hello():\n    return 'world'"])[0]
        assert len(vec) == m.dimension, (name, len(vec), m.dimension)
        print(f"bake: {m.model_name} OK (dim={m.dimension}, max_seq_length={m.max_seq_length})")
    try:  # cache tiktoken (comptage de tokens du chunker)
        import tiktoken
        tiktoken.get_encoding("cl100k_base")
        print("bake: tiktoken cl100k_base OK")
    except Exception as exc:  # non bloquant : le chunker a un repli
        print(f"bake: tiktoken non pré-chargé ({exc})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
