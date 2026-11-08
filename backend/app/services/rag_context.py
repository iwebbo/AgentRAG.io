"""Construction du contexte RAG d'un tour : type de requête, retrieval, index projet, system prompt."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional
from uuid import UUID

from app.services.context_budget import count_tokens
from app.services.rag_selection import SelectionConfig, select_chunks

logger = logging.getLogger(__name__)


# ============================================================================
# TYPES DE REQUÊTE & STRATÉGIES
# ============================================================================

class QueryType(Enum):
    """Types de requêtes avec stratégies adaptées"""
    ARCHITECTURE = "architecture"
    CODE_GEN = "code_generation"
    DEBUG = "debugging"
    FEATURE = "feature"
    SIMPLE = "simple"


# top_k / context_ratio = plafonds de récupération et de budget.
# max_chunks / rel_drop = sélection par pertinence (voir rag_selection.py) : le contexte
# envoyé au LLM est dimensionné par la pertinence, ces plafonds ne sont plus une cible à remplir.
RAG_STRATEGIES = {
    QueryType.ARCHITECTURE: {
        "description": "Vue globale projet",
        "top_k": 50,
        "context_ratio": 0.5,  # 50% du contexte disponible
        "include_index": True,
        "max_chunks": 20,
        "rel_drop": 0.25,      # vue globale : on accepte des chunks plus éloignés du meilleur
    },
    QueryType.CODE_GEN: {
        "description": "Génération de code",
        "top_k": 60,
        "context_ratio": 0.5,
        "include_index": True,
        "max_chunks": 15,
        "rel_drop": 0.20,
    },
    QueryType.DEBUG: {
        "description": "Debug/Fix",
        "top_k": 50,
        "context_ratio": 0.5,
        "include_index": False,
        "max_chunks": 10,
        "rel_drop": 0.15,
    },
    QueryType.FEATURE: {
        "description": "Nouvelle fonctionnalité",
        "top_k": 50,
        "context_ratio": 0.5,
        "include_index": True,
        "max_chunks": 15,
        "rel_drop": 0.20,
    },
    QueryType.SIMPLE: {
        "description": "Question simple",
        "top_k": 50,
        "context_ratio": 0.5,
        "include_index": False,
        "max_chunks": 8,
        "rel_drop": 0.15,
    }
}


def detect_query_type(message: str, history_length: int = 0) -> QueryType:
    """Détecte le type de requête pour adapter la stratégie RAG."""
    msg_lower = message.lower()

    architecture_keywords = [
        "architecture", "structure", "organisation", "projet complet",
        "vue d'ensemble", "global", "tous les fichiers", "overview",
        "comment est organisé", "structure du code"
    ]
    if any(kw in msg_lower for kw in architecture_keywords):
        return QueryType.ARCHITECTURE

    codegen_keywords = [
        "crée", "génère", "implémente", "développe", "code pour",
        "fonction qui", "classe qui", "endpoint pour", "route pour",
        "ajoute", "nouvelle feature", "créer un"
    ]
    if any(kw in msg_lower for kw in codegen_keywords):
        return QueryType.CODE_GEN

    debug_keywords = [
        "bug", "erreur", "fix", "répare", "ne fonctionne pas",
        "problème avec", "corrige", "pourquoi ça marche pas"
    ]
    if any(kw in msg_lower for kw in debug_keywords):
        return QueryType.DEBUG

    feature_keywords = [
        "améliore", "étend", "module pour", "système pour",
        "fonctionnalité", "optimise", "modifie"
    ]
    if any(kw in msg_lower for kw in feature_keywords):
        return QueryType.FEATURE

    # Conversation longue (>5 messages) → probablement FEATURE
    if history_length > 5:
        return QueryType.FEATURE

    return QueryType.SIMPLE


# ============================================================================
# INDEX PROJET
# ============================================================================

def generate_project_index(project_id: UUID, data_dir: Path = Path("./data")) -> str:
    """Génère un index compact du projet (fichiers importants en évidence)."""
    project_path = data_dir / "documents" / str(project_id)

    if not project_path.exists():
        return ""

    all_files = [f for f in project_path.rglob("*") if f.is_file()]

    ignore_patterns = [
        "__pycache__", "node_modules", ".git", "venv", ".venv",
        ".pyc", ".log", "dist", "build", ".next", ".cache"
    ]
    all_files = [
        f for f in all_files
        if not any(pattern in str(f) for pattern in ignore_patterns)
    ]

    if not all_files:
        return ""

    modules = {}
    for file in all_files:
        try:
            rel_path = file.relative_to(project_path)
            parts = rel_path.parts
            module = parts[0] if len(parts) > 1 else "root"
            modules.setdefault(module, [])

            importance = "low"
            filename_lower = file.name.lower()

            if any(kw in filename_lower for kw in [
                "app.py", "main.py", "__init__.py", "config.py", "settings.py"
            ]):
                importance = "critical"
            elif any(kw in str(file) for kw in [
                "models.py", "routes.py", "api.py", "/core/", "/services/"
            ]):
                importance = "high"
            elif any(kw in str(file) for kw in [
                "utils.py", "helpers.py", "/utils/", "/helpers/"
            ]):
                importance = "medium"

            modules[module].append({
                "path": str(rel_path),
                "name": file.name,
                "importance": importance
            })
        except Exception as e:
            logger.warning(f"Erreur lors du traitement de {file}: {e}")
            continue

    index_lines = ["# STRUCTURE PROJET\n"]

    for module, files in sorted(modules.items()):
        index_lines.append(f"\n##  {module}/")
        index_lines.append(f"- **{len(files)} fichiers**")

        important = [f for f in files if f["importance"] in ["critical", "high"]]
        if important:
            index_lines.append("- **Fichiers clés**:")
            for f in important[:8]:
                icon = "🔴" if f["importance"] == "critical" else "🟠"
                index_lines.append(f"  {icon} `{f['name']}`")

    index_lines.append(f"\n**Total**: {len(all_files)} fichiers")

    return "\n".join(index_lines)


# ============================================================================
# RETRIEVAL
# ============================================================================

def detect_filename_filter(message: str) -> Optional[dict]:
    """Filtre vectoriel si le message cite un nom de fichier (ex: psrp_server.py)."""
    file_match = re.search(r'\b([\w\-]+\.\w+)\b', message)
    if not file_match:
        return None
    detected_file = file_match.group(1)
    logger.info(f"Filename filter detected: {detected_file}")
    return {"filename": {"$eq": detected_file}}


def retrieve_chunks(vector_store, embedder, project, project_id, message: str, top_k: int) -> dict:
    """Recherche sémantique (avec filtre fichier + fallback sans filtre)."""
    logger.info(f"Searching for: {message}")
    query_embedding = embedder.encode_single(message)
    filename_filter = detect_filename_filter(message)

    common = dict(
        project_id=str(project_id),
        query_embedding=query_embedding,
        n_results=top_k,
        vector_store_type=getattr(project, "vector_store_type", "chroma"),
        opensearch_index=getattr(project, "opensearch_index", None),
    )
    results = vector_store.query(where=filename_filter, **common)

    if filename_filter and not results['documents'][0]:
        logger.info("Filename filter returned 0 results, retrying without filter")
        results = vector_store.query(where=None, **common)
    return results


@dataclass
class RagContext:
    text: str = ""
    chunks: list = field(default_factory=list)
    tokens: int = 0


def build_rag_context(
    project_id: UUID,
    strategy: dict,
    results: dict,
    max_tokens: int,
    selection: Optional[SelectionConfig] = None,
) -> RagContext:
    """Assemble index projet + chunks pertinents (voir rag_selection), dans la limite de `max_tokens`."""
    parts: list[str] = []
    chunks: list[dict] = []
    tokens = 0

    if strategy["include_index"]:
        project_index = generate_project_index(project_id)
        if project_index:
            parts.append(project_index)
            tokens += count_tokens(project_index)
            logger.info(f"📇 Index projet ajouté: {tokens} tokens")

    if results['documents'][0]:
        # Sélection par pertinence (seuil + coupure relative au meilleur score), pas remplissage du budget
        selected, stats = select_chunks(results, selection or SelectionConfig.from_env(strategy))
        found = stats["total"]
        logger.info(
            f" RAG selection: {stats['kept']}/{found} chunks kept "
            f"(best={stats['best']:.3f}, floor={stats['floor']:.3f}, selection={'on' if stats['enabled'] else 'off'})"
        )
        parts.append("\n#  DOCUMENTS PERTINENTS\n")

        for i, (doc, metadata, score) in enumerate(selected):
            chunk_text = f"\n## [SOURCE {i+1}] {metadata.get('filename', 'unknown')}\n```\n{doc}\n```"
            chunk_tokens = count_tokens(chunk_text)

            if tokens + chunk_tokens > max_tokens:
                logger.warning(f" RAG context truncated at {tokens} tokens ({i}/{len(selected)} chunks)")
                break

            chunks.append({"text": doc, "metadata": metadata, "score": score})
            parts.append(chunk_text)
            tokens += chunk_tokens
    else:
        logger.warning(" No chunks found")

    text = "\n".join(parts)
    logger.info(f" RAG context: {tokens:,} tokens ({len(chunks)} chunks)")
    return RagContext(text=text, chunks=chunks, tokens=tokens)


# ============================================================================
# SYSTEM PROMPT & RAISONNEMENT (#52)
# ============================================================================

_COT_BLOCK = """
**PROCESSUS DE RAISONNEMENT** (applique en interne avant de répondre):
1. **Compréhension** — reformule mentalement ce qui est demandé
2. **Recherche** — identifie les sources pertinentes dans les documents fournis
3. **Génération** — produis la réponse/solution complète
4. **Vérification** — vérifie la cohérence avec les sources et les règles ci-dessous

"""

_DEEP_BLOCK = """
**PROCESSUS DE RAISONNEMENT** (analyse multi-perspectives avant de répondre):
1. **Compréhension** — décompose la question, identifie les enjeux
2. **Exploration** — explore les alternatives et les compromis depuis les documents
3. **Synthèse** — produis une réponse nuancée et complète
4. **Validation** — confirme la cohérence avec le contexte documentaire

"""

_CODE_KW = ["crée", "génère", "implémente", "code", "fonction", "classe",
            "endpoint", "script", "create", "generate", "implement", "build"]
_ANALYSIS_KW = ["architecture", "analyse", "explique", "compare", "pourquoi",
                "overview", "décris", "explain", "describe"]
_DEBUG_KW = ["bug", "erreur", "error", "fix", "répare", "corrige",
             "ne fonctionne pas", "debug", "crash"]


def resolve_reasoning(reasoning_mode: Optional[str], message: str, query_type: QueryType) -> str:
    """Résout le mode de raisonnement effectif (standard | cot | deep)."""
    effective = reasoning_mode or "standard"
    if effective != "auto":
        return effective

    msg_lower = message.lower()
    if query_type in [QueryType.CODE_GEN] or any(kw in msg_lower for kw in _CODE_KW):
        effective = "cot"
    elif query_type in [QueryType.ARCHITECTURE] or any(kw in msg_lower for kw in _ANALYSIS_KW):
        effective = "deep"
    elif query_type in [QueryType.DEBUG] or any(kw in msg_lower for kw in _DEBUG_KW):
        effective = "cot"
    else:
        effective = "standard"
    logger.info(f" RAG auto-reasoning résolu: '{effective}' (query_type={query_type.value})")
    return effective


def build_system_prompt(rag_context: str, query_type: QueryType, effective_reasoning: str) -> str:
    reasoning_block = {"cot": _COT_BLOCK, "deep": _DEEP_BLOCK}.get(effective_reasoning, "")
    verbosity = (
        "exhaustif et détaillé"
        if query_type in [QueryType.ARCHITECTURE, QueryType.CODE_GEN]
        else "précis et concis et trés détaillé"
    )
    return f"""Tu es un assistant expert qui répond en te basant sur les documents fournis.

{rag_context}
{reasoning_block}
**RÈGLES**:
- Base-toi PRIORITAIREMENT sur le contexte documentaire fourni
- Si l'information n'est pas dans le contexte, utilise tes connaissances générales.
- Cite tes sources avec [SOURCE X]
- L'historique contient, pour chaque question précédente, le contexte documentaire qui avait servi à y répondre : réutilise-le avec tes réponses précédentes, sans redemander les fichiers déjà fournis
- Pour les requêtes de type "{query_type.value}", sois particulièrement {verbosity}
- Réponds en français sauf si demandé autrement
**REGLES**: Si génération de code demandé, ou detécté, respecter les points ci-dessous.
- Produis du code production-ready avec gestion d'erreurs
- Inclus commentaires explicatifs pour logique complexe
- Genere un README.md au format markdown qui explique toute la génération/solution"""