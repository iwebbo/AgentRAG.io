"""
Routes RAG Chat - VERSION SCALABLE
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from uuid import UUID, uuid4
import json
import logging
from datetime import date, datetime
import tiktoken
from pathlib import Path
from enum import Enum
from typing import List, Dict
import re

from app.database import get_db
from app.models import User, Project, RAGConversation, RAGMessage, Provider
from app.dependencies import get_current_user
from app.services.vector_store import VectorStore
from app.services.embeddings import EmbeddingManager
from app.services.llm_service import LLMService
from app.services.provider_factory import ProviderFactory 
from app.utils.security import decrypt_api_key 
from app.utils.streaming import sse_generator, stream_manager
from app.schemas.rag_chat import RAGChatRequest, RAGChatResponse, RAGConversationResponse, RAGMessageResponse

router = APIRouter(prefix="/api/rag", tags=["RAG Chat"])
logger = logging.getLogger(__name__)

vector_store = VectorStore()
embedder = EmbeddingManager()

class QueryType(Enum):
    """Types de requêtes avec stratégies adaptées"""
    ARCHITECTURE = "architecture"
    CODE_GEN = "code_generation"
    DEBUG = "debugging"
    FEATURE = "feature"
    SIMPLE = "simple"

# Stratégies RAG par type de requête
RAG_STRATEGIES = {
    QueryType.ARCHITECTURE: {
        "description": "Vue globale projet",
        "top_k": 5,
        "context_ratio": 0.5,  # 60% du contexte disponible
        "include_index": True
    },
    QueryType.CODE_GEN: {
        "description": "Génération de code",
        "top_k": 6,
        "context_ratio": 0.5,
        "include_index": True
    },
    QueryType.DEBUG: {
        "description": "Debug/Fix",
        "top_k": 5,
        "context_ratio": 0.5,
        "include_index": False
    },
    QueryType.FEATURE: {
        "description": "Nouvelle fonctionnalité",
        "top_k": 8,
        "context_ratio": 0.5,
        "include_index": True
    },
    QueryType.SIMPLE: {
        "description": "Question simple",
        "top_k": 5,
        "context_ratio": 0.5,
        "include_index": False
    }
}

# Limites de contexte par modèle
MODEL_CONTEXT_LIMITS = {
    # OpenAI
    "gpt-4-turbo": 128000,
    "gpt-4": 8192,
    "gpt-3.5-turbo": 16385,
    
    # Claude
    "claude-3-5-sonnet": 200000,
    "claude-3-opus": 200000,
    "claude-3-haiku": 200000,
    
    # Google
    "gemini-1.5-pro": 2000000,  # 2M tokens!
    "gemini-1.5-flash": 1000000,
    
    # Ollama - Llama 3.1 (Meta)
    "llama3.1:8b": 128000,
    "llama3.1:70b": 128000,
    "llama3.1:405b": 128000,
    "llama3.1": 128000,  # Alias
    
    # Ollama - Llama 3.2 (Meta)
    "llama3.2:1b": 131072,
    "llama3.2:3b": 131072,
    "llama3.2:90b": 131072,
    
    # Ollama - Mistral
    "mistral:7b": 32768,
    "mistral:latest": 32768,
    "mistral-small": 32768,
    "mistral-large": 128000,
    "codestral:22b": 32000,
    "mixtral:latest": 32000,
    "mixtral:8x7b": 32000,
    "mistrallite:latest": 32000,


    # Ollama - Qwen 2.5 (Alibaba)
    "qwen2.5:7b": 32768,
    "qwen2.5:14b": 32768,
    "qwen2.5:32b": 32768,
    "qwen2.5:72b": 131072,
    "qwen3-coder:30b": 256000,

    # Ollama - Gemma 2 (Google)
    "gemma2:2b": 8192,
    "gemma2:9b": 8192,
    "gemma2:27b": 8192,
    "gemma3:4b": 128000,
    "gemma3:27b": 128000,
    "gemma3:27b-it-qat": 128000,
    "gemma4:e4b": 128000,
    "gemma4:26b": 128000,
    "gemma4:e2b": 128000,
    
    # Ollama - Phi-3.5 (Microsoft)
    "phi3:14b": 128000,
    "phi3:latest": 128000,
    "phi4:14b": 16000,
    "phi4:latest": 16000,
    "phi4-reasoning:14b": 32000,

    # Ollama - DeepSeek
    "deepseek-coder:6.7b": 16384,
    "deepseek-coder:33b": 16384,
    "deepseek-r1:32b": 128000,
    "deepseek-r1:14b": 128000,
    
    # Ollama - Code Llama
    "codellama:7b": 16384,
    "codellama:13b": 16384,
    "codellama:34b": 128000,

    # Ollama - Gpt-oss
    "gpt-oss:20b": 128000,
    
    # LMStudio - gpt-oss
    "openai/gpt-oss-20b": 128000,

    # LMStudio - Gemma
    "google/gemma-4-e4b": 128000,

    # LMStudio - Mistral
    "mistralai/ministral-3-3b": 128000,
    "mistralai/ministral-3-14b-reasoning": 128000,
    "mistralai/codestral-22b-v0.1": 128000,

    # LMStudio - Llama
    "meta-llama-3.1-8b-instruct": 128000,
    "llama-3.2-3b-instruct": 128000,
    
    # LMStudio - Qwen
    "qwen/qwen3.5-9b": 128000,

    # Fallback
    "default": 8192
}

def estimate_tokens(text: str) -> int:
    """Estime tokens (approximation rapide)"""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except:
        return len(text) // 4

def get_model_limit(model: str) -> int:
    """Récupère la limite de contexte d'un modèle"""
    for key in MODEL_CONTEXT_LIMITS:
        if key in model.lower():
            return MODEL_CONTEXT_LIMITS[key]
    return MODEL_CONTEXT_LIMITS["default"]

# ============================================================================
# DÉTECTION INTELLIGENTE TYPE REQUÊTE
# ============================================================================

def detect_query_type(message: str, history_length: int = 0) -> QueryType:
    """
    Détecte le type de requête pour adapter la stratégie RAG
    
    Args:
        message: Message utilisateur
        history_length: Nombre de messages dans l'historique
    
    Returns:
        QueryType détecté
    """
    msg_lower = message.lower()
    
    # Patterns ARCHITECTURE
    architecture_keywords = [
        "architecture", "structure", "organisation", "projet complet",
        "vue d'ensemble", "global", "tous les fichiers", "overview",
        "comment est organisé", "structure du code"
    ]
    if any(kw in msg_lower for kw in architecture_keywords):
        return QueryType.ARCHITECTURE
    
    # Patterns CODE GENERATION
    codegen_keywords = [
        "crée", "génère", "implémente", "développe", "code pour",
        "fonction qui", "classe qui", "endpoint pour", "route pour",
        "ajoute", "nouvelle feature", "créer un"
    ]
    if any(kw in msg_lower for kw in codegen_keywords):
        return QueryType.CODE_GEN
    
    # Patterns DEBUG
    debug_keywords = [
        "bug", "erreur", "fix", "répare", "ne fonctionne pas",
        "problème avec", "corrige", "pourquoi ça marche pas"
    ]
    if any(kw in msg_lower for kw in debug_keywords):
        return QueryType.DEBUG
    
    # Patterns FEATURE
    feature_keywords = [
        "améliore", "étend", "module pour", "système pour",
        "fonctionnalité", "optimise", "modifie"
    ]
    if any(kw in msg_lower for kw in feature_keywords):
        return QueryType.FEATURE
    
    # Si conversation longue (>5 messages) → probablement FEATURE
    if history_length > 5:
        return QueryType.FEATURE
    
    return QueryType.SIMPLE

# ============================================================================
# GÉNÉRATION INDEX PROJET
# ============================================================================

def generate_project_index(project_id: UUID, data_dir: Path = Path("./data")) -> str:
    """
    Génère un index compact du projet
    
    Structure hiérarchique avec fichiers importants en évidence
    """
    
    project_path = data_dir / "documents" / str(project_id)
    
    if not project_path.exists():
        return ""
    
    # Scan fichiers
    all_files = list(project_path.rglob("*"))
    all_files = [f for f in all_files if f.is_file()]
    
    # Filtrage patterns ignorés
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
    
    # Organisation par module (1er niveau de dossier)
    modules = {}
    for file in all_files:
        try:
            rel_path = file.relative_to(project_path)
            parts = rel_path.parts
            
            module = parts[0] if len(parts) > 1 else "root"
            
            if module not in modules:
                modules[module] = []
            
            # Détection importance fichier
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
    
    # Formatage index compact
    index_lines = ["# 📁 STRUCTURE PROJET\n"]
    
    for module, files in sorted(modules.items()):
        index_lines.append(f"\n## 📦 {module}/")
        index_lines.append(f"- **{len(files)} fichiers**")
        
        # Fichiers critiques/importants
        important = [f for f in files if f["importance"] in ["critical", "high"]]
        if important:
            index_lines.append("- **Fichiers clés**:")
            for f in important[:8]:  # Max 8 fichiers importants
                icon = "🔴" if f["importance"] == "critical" else "🟠"
                index_lines.append(f"  {icon} `{f['name']}`")
    
    index_lines.append(f"\n**Total**: {len(all_files)} fichiers")
    
    return "\n".join(index_lines)

# ============================================================================
# TRONCATURE INTELLIGENTE HISTORIQUE (VOTRE CODE)
# ============================================================================

def smart_truncate_history(
    past_messages: list,
    max_tokens: int,
    keep_recent: int = 5
) -> list:
    """Tronque intelligemment l'historique pour respecter max_tokens"""
    if len(past_messages) <= keep_recent:
        return past_messages
    
    recent = past_messages[-keep_recent:]
    older = past_messages[:-keep_recent]
    
    recent_tokens = sum(estimate_tokens(msg.content) for msg in recent)
    available = max_tokens - recent_tokens
    
    if available <= 0:
        logger.warning(f"⚠️ Contexte saturé, garde seulement {keep_recent} derniers messages")
        return recent
    
    truncated_older = []
    current_tokens = 0
    
    for msg in reversed(older):
        msg_tokens = estimate_tokens(msg.content)
        if current_tokens + msg_tokens > available:
            break
        truncated_older.insert(0, msg)
        current_tokens += msg_tokens
    
    logger.info(f"📚 Historique: {len(truncated_older)} anciens + {len(recent)} récents = {len(truncated_older) + len(recent)} messages")
    
    return truncated_older + recent

# ============================================================================
# ENDPOINT PRINCIPAL - VERSION SCALABLE
# ============================================================================

@router.post("/chat/stream")
async def rag_chat_stream(
    request: RAGChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Chat RAG avec stratégie adaptative scalable
    
    Nouveautés:
    - Détection automatique type requête
    - Stratégie RAG adaptée (5 à 50 chunks)
    - Index projet pour vue globale
    - Gestion optimale contexte 200K+ tokens
    """
    logger.info(f"🔍 Requête reçue: {request.dict()}")
    logger.info(f"🔍 reasoning_mode: {request.reasoning_mode}")

    # Vérifier projet
    project = db.query(Project).filter(
        Project.id == request.project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Récupérer ou créer conversation
    if request.conversation_id:
        conversation = db.query(RAGConversation).filter(
            RAGConversation.id == request.conversation_id,
            RAGConversation.user_id == current_user.id
        ).first()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = RAGConversation(
            project_id=request.project_id,
            user_id=current_user.id,
            title=request.message[:50] + "..." if len(request.message) > 50 else request.message,
            provider_name=request.provider_name,
            model=request.model,
            temperature=request.temperature,
            reasoning_mode=request.reasoning_mode or "standard",
            top_k=request.top_k or 5
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    
    # ✅ NOUVEAU: Détection type requête
    past_messages_count = db.query(RAGMessage).filter(
        RAGMessage.conversation_id == conversation.id
    ).count()
    
    query_type = detect_query_type(request.message, past_messages_count)
    strategy = RAG_STRATEGIES[query_type]
    
    logger.info(f"🎯 Query type: {query_type.value} - {strategy['description']}")
    
    # Déterminer limite contexte modèle
    context_limit = get_model_limit(request.model)
    logger.info(f"🧠 Model: {request.model} → Context limit: {context_limit:,} tokens")
    
    # ✅ NOUVEAU: top_k adaptatif selon stratégie ET modèle
    adaptive_top_k = strategy["top_k"]
    
    # Ajuster selon capacité modèle
    if context_limit < 32000:
        adaptive_top_k = min(adaptive_top_k, 15)  # Petit modèle
    elif context_limit > 100000:
        adaptive_top_k = min(adaptive_top_k, 60)  # Gros modèle
    
    logger.info(f"📊 Stratégie: top_k={adaptive_top_k}, context_ratio={strategy['context_ratio']}")
    
    # 1. RETRIEVAL - Recherche sémantique
    logger.info(f"🔍 Searching for: {request.message}")
    query_embedding = embedder.encode_single(request.message)
    
    # Release/Fix add detect name file - Request RAG
    filename_filter = None
    file_match = re.search(r'\b([\w\-]+\.\w+)\b', request.message)
    if file_match:
        detected_file = file_match.group(1)
        filename_filter = {"filename": {"$eq": detected_file}}
        logger.info(f"📎 Filename filter detected: {detected_file}")

    retrieval_results = vector_store.query(
        project_id=str(request.project_id),
        query_embedding=query_embedding,
        n_results=adaptive_top_k,
        where=filename_filter,
        vector_store_type=getattr(project, "vector_store_type", "chroma"),
        opensearch_index=getattr(project, "opensearch_index", None),
    )
    
    if filename_filter and not retrieval_results['documents'][0]:
        logger.info(f"📎 Filename filter returned 0 results, retrying without filter")
        retrieval_results = vector_store.query(
            project_id=str(request.project_id),
            query_embedding=query_embedding,
            n_results=adaptive_top_k,
            where=None,
            vector_store_type=getattr(project, "vector_store_type", "chroma"),
            opensearch_index=getattr(project, "opensearch_index", None),
        )

    # 2. Construction contexte RAG
    retrieved_chunks = []
    rag_context_parts = []
    rag_tokens = 0
    
    # ✅ NOUVEAU: Ajout index projet si demandé
    if strategy["include_index"]:
        project_index = generate_project_index(request.project_id)
        if project_index:
            rag_context_parts.append(project_index)
            rag_tokens += estimate_tokens(project_index)
            logger.info(f"📇 Index projet ajouté: {rag_tokens} tokens")
    
    # Limite contexte RAG basée sur stratégie
    ### ?????
    max_rag_tokens = int(context_limit * strategy["context_ratio"])
    
    if retrieval_results['documents'][0]:
        chunks_found = len(retrieval_results['documents'][0])
        logger.info(f"✅ Found {chunks_found} chunks")
        
        rag_context_parts.append("\n# 📚 DOCUMENTS PERTINENTS\n")
        
        for i, (doc, metadata, distance) in enumerate(zip(
            retrieval_results['documents'][0],
            retrieval_results['metadatas'][0],
            retrieval_results['distances'][0]
        )):
            chunk_text = f"\n## [SOURCE {i+1}] {metadata.get('filename', 'unknown')}\n```\n{doc}\n```"
            chunk_tokens = estimate_tokens(chunk_text)
            
            # Vérifier limite RAG
            if rag_tokens + chunk_tokens > max_rag_tokens:
                logger.warning(f"⚠️ RAG context truncated at {rag_tokens} tokens ({i}/{chunks_found} chunks)")
                break
            
            retrieved_chunks.append({
                "text": doc,
                "metadata": metadata,
                "score": 1 - distance
            })
            rag_context_parts.append(chunk_text)
            rag_tokens += chunk_tokens
    else:
        logger.warning("⚠️ No chunks found")
    
    rag_context = "\n".join(rag_context_parts)
    logger.info(f"📄 RAG context: {rag_tokens:,} tokens ({len(retrieved_chunks)} chunks)")
    
    # 3. Sauvegarder message utilisateur
    user_message = RAGMessage(
        conversation_id=conversation.id,
        role="user",
        content=request.message
    )
    db.add(user_message)
    db.commit()
    
    # 4. Construction messages avec historique intelligent
    messages = []
    
    # System prompt avec contexte RAG
    system_tokens = 0
    if rag_context:
            # =====================================================================
            # AUTO-REASONING RAG — détection depuis le type de requête + message
            # Indépendant des règles RAG documentaires (qui restent inchangées)
            # #52 Ticket in GITEA.
            # =====================================================================
            reasoning_block = ""
            effective_reasoning = request.reasoning_mode or "standard"

            if effective_reasoning == "auto":
                msg_lower = request.message.lower()
                _code_kw = ["crée", "génère", "implémente", "code", "fonction", "classe",
                            "endpoint", "script", "create", "generate", "implement", "build"]
                _analysis_kw = ["architecture", "analyse", "explique", "compare", "pourquoi",
                                "overview", "décris", "explain", "describe"]
                _debug_kw = ["bug", "erreur", "error", "fix", "répare", "corrige",
                            "ne fonctionne pas", "debug", "crash"]

                if query_type in [QueryType.CODE_GEN] or any(kw in msg_lower for kw in _code_kw):
                    effective_reasoning = "cot"
                elif query_type in [QueryType.ARCHITECTURE] or any(kw in msg_lower for kw in _analysis_kw):
                    effective_reasoning = "deep"
                elif query_type in [QueryType.DEBUG] or any(kw in msg_lower for kw in _debug_kw):
                    effective_reasoning = "cot"
                else:
                    effective_reasoning = "standard"
                logger.info(f"🧠 RAG auto-reasoning résolu: '{effective_reasoning}' (query_type={query_type.value})")

            if effective_reasoning == "cot":
                reasoning_block = """
    **PROCESSUS DE RAISONNEMENT** (applique en interne avant de répondre):
    1. **Compréhension** — reformule mentalement ce qui est demandé
    2. **Recherche** — identifie les sources pertinentes dans les documents fournis
    3. **Génération** — produis la réponse/solution complète
    4. **Vérification** — vérifie la cohérence avec les sources et les règles ci-dessous

    """
            elif effective_reasoning == "deep":
                reasoning_block = """
    **PROCESSUS DE RAISONNEMENT** (analyse multi-perspectives avant de répondre):
    1. **Compréhension** — décompose la question, identifie les enjeux
    2. **Exploration** — explore les alternatives et les compromis depuis les documents
    3. **Synthèse** — produis une réponse nuancée et complète
    4. **Validation** — confirme la cohérence avec le contexte documentaire

    """

            system_prompt = f"""Tu es un assistant expert qui répond en te basant sur les documents fournis.

    {rag_context}
    {reasoning_block}
    **RÈGLES**:
    - Base-toi PRIORITAIREMENT sur le contexte documentaire fourni
    - Si l'information n'est pas dans le contexte, utilise tes connaissances générales.
    - Cite tes sources avec [SOURCE X]
    - Pour les requêtes de type "{query_type.value}", sois particulièrement {"exhaustif et détaillé" if query_type in [QueryType.ARCHITECTURE, QueryType.CODE_GEN] else "précis et concis et trés détaillé"}
    - Réponds en français sauf si demandé autrement
    **REGLES**: Si génération de code demandé, ou detécté, respecter les points ci-dessous.
    - Produis du code production-ready avec gestion d'erreurs
    - Inclus commentaires explicatifs pour logique complexe
    - Genere un README.md au format markdown qui explique toute la génération/solution"""

            system_tokens = estimate_tokens(system_prompt)
            messages.append({
                "role": "system",
                "content": system_prompt
            })
            
            logger.info(f"📋 System prompt: {system_tokens:,} tokens")
    
    # Charger historique
    past_messages = db.query(RAGMessage).filter(
        RAGMessage.conversation_id == conversation.id,
        RAGMessage.id != user_message.id
    ).order_by(RAGMessage.created_at.asc()).all()
    
    # Budget pour historique
    user_msg_tokens = estimate_tokens(request.message)
    history_budget = context_limit - system_tokens - user_msg_tokens - 2000  # Marge réponse
    
    # Tronquer historique
    truncated_history = smart_truncate_history(
        past_messages,
        max_tokens=history_budget,
        keep_recent=5
    )
    
    # Ajouter messages
    for msg in truncated_history:
        messages.append({
            "role": msg.role,
            "content": msg.content
        })
    
    messages.append({
        "role": "user",
        "content": request.message
    })
    
    # Stats finales
    total_tokens = system_tokens + sum(estimate_tokens(m["content"]) for m in messages[1:])
    usage_percent = (total_tokens / context_limit) * 100
    
    logger.info(f"📨 Total context: {total_tokens:,}/{context_limit:,} tokens ({usage_percent:.1f}%)")
    
    if total_tokens > context_limit * 0.95:
        logger.error(f"❌ Context overflow! {total_tokens} > {context_limit}")
        raise HTTPException(
            status_code=400,
            detail=f"Context too large ({total_tokens:,} tokens). Reduce history or documents."
        )
    
    # 5. Provider LLM (VOTRE CODE EXISTANT)
    provider = db.query(Provider).filter(
        Provider.user_id == current_user.id,
        Provider.name == request.provider_name,
        Provider.is_active == True
    ).first()
    
    if not provider:
        raise HTTPException(
            status_code=404,
            detail=f"Provider {request.provider_name} not configured"
        )
    
    api_key = None
    if provider.api_key:
        api_key = decrypt_api_key(provider.api_key)
    
    llm_provider = ProviderFactory.create_provider(
        provider.name,
        api_key=api_key,
        base_url=provider.base_url,
        config=provider.config
    )
    
    # 6. Stream LLM (VOTRE CODE)
    async def rag_stream_generator():
        full_response = ""
        
        try:
            # Envoyer métadonnées requête
            yield f"event: metadata\ndata: {json.dumps({'query_type': query_type.value, 'chunks': len(retrieved_chunks), 'tokens': total_tokens})}\n\n"
            
            # Envoyer chunks
            yield f"event: retrieval\ndata: {json.dumps({'chunks': retrieved_chunks})}\n\n"
            
            # Stream LLM
            logger.info(f"🤖 Starting LLM stream with {request.provider_name}/{request.model}")
            
            async for chunk in llm_provider.stream_completion(
                messages=messages,
                model=request.model,
                temperature=request.temperature
            ):
                full_response += chunk
                yield f"event: message\ndata: {json.dumps({'content': chunk})}\n\n"
            
            # Sauvegarder réponse
            assistant_message = RAGMessage(
                conversation_id=conversation.id,
                role="assistant",
                content=full_response,
                retrieved_chunks=json.dumps(retrieved_chunks)
            )
            db.add(assistant_message)
            
            conversation.updated_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"✅ RAG chat completed: {len(full_response)} chars")
            yield f"event: done\ndata: {json.dumps({'conversation_id': str(conversation.id)})}\n\n"
            
        except Exception as e:
            logger.error(f"❌ RAG streaming error: {str(e)}", exc_info=True)
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        rag_stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.get("/conversations/{project_id}")
async def list_rag_conversations(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Liste conversations RAG d'un projet"""
    conversations = db.query(RAGConversation).filter(
        RAGConversation.project_id == project_id,
        RAGConversation.user_id == current_user.id
    ).order_by(
        RAGConversation.updated_at.desc()
    ).all()
    
    return conversations


@router.get("/conversation/{conversation_id}", response_model=RAGConversationResponse)
async def get_rag_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Récupère UNE conversation RAG avec tous ses messages"""
    conversation = db.query(RAGConversation).filter(
        RAGConversation.id == conversation_id,
        RAGConversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    messages = db.query(RAGMessage).filter(
        RAGMessage.conversation_id == conversation_id
    ).order_by(RAGMessage.created_at.asc()).all()
    
    conversation.messages = messages
    
    logger.info(f"✅ Conversation {conversation_id} chargée: {len(messages)} messages")
    
    return conversation


@router.delete("/conversations/{conversation_id}")
async def delete_rag_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Supprime une conversation RAG"""
    conversation = db.query(RAGConversation).filter(
        RAGConversation.id == conversation_id,
        RAGConversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    db.delete(conversation)
    db.commit()
    
    return {"message": "Conversation deleted"}