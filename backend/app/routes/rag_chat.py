"""
Routes RAG Chat - VERSION SCALABLE

La logique métier est dans app/services :
- rag_context.py          : type de requête, retrieval, index projet, system prompt
- conversation_context.py : historique COMPLET (contexte documentaire des tours précédents inclus)
- context_budget.py       : comptage de tokens, usage used/limit, garde-fou d'overflow
- model_limits.py         : limites de contexte par modèle
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from uuid import UUID
import json
import logging
from datetime import datetime

from app.database import get_db
from app.models import User, Project, RAGConversation, RAGMessage, Provider
from app.dependencies import get_current_user
from app.services.vector_store import VectorStore
from app.services.embeddings import EmbeddingManager
from app.services.provider_factory import ProviderFactory
from app.utils.security import decrypt_api_key
from app.config import get_settings
from app.services.verification import (
    SSE_KEEPALIVE, VerificationContext, format_sse, run_verified_stream, status_payload, verdict_payload,
)
from app.services.verification_service import build_request_pipeline, effective_mode
from app.schemas.rag_chat import RAGChatRequest, RAGConversationResponse

# Services RAG / contexte. Les noms ci-dessous (QueryType, RAG_STRATEGIES,
# detect_query_type, generate_project_index, MODEL_CONTEXT_LIMITS, get_model_limit,
# estimate_tokens) restent importables depuis ce module (rétro-compatibilité).
from app.services.context_budget import (
    WARN_PERCENT, ContextUsage, count_tokens as estimate_tokens, rag_room,
)
from app.services.conversation_context import build_history, chunk_hash
from app.services.model_limits import MODEL_CONTEXT_LIMITS, get_model_limit
from app.services.rag_context import (
    RAG_STRATEGIES, QueryType, build_rag_context, build_system_prompt,
    detect_query_type, generate_project_index, resolve_reasoning, retrieve_chunks,
)

router = APIRouter(prefix="/api/rag", tags=["RAG Chat"])
logger = logging.getLogger(__name__)

vector_store = VectorStore()
embedder = EmbeddingManager()


def _get_or_create_conversation(db: Session, request: RAGChatRequest, user: User) -> RAGConversation:
    if request.conversation_id:
        conversation = db.query(RAGConversation).filter(
            RAGConversation.id == request.conversation_id,
            RAGConversation.user_id == user.id
        ).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation

    conversation = RAGConversation(
        project_id=request.project_id,
        user_id=user.id,
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
    return conversation


# ============================================================================
# ENDPOINT PRINCIPAL
# ============================================================================

@router.post("/chat/stream")
async def rag_chat_stream(
    request: RAGChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Chat RAG avec stratégie adaptative.

    Contexte envoyé au LLM à chaque tour :
      system  = index projet + chunks du tour courant + règles
      user[1] = contexte documentaire du tour 1 + question 1
      assistant[1] = réponse 1
      ...
      user[N] = question courante
    L'historique n'est jamais tronqué : si le total approche la limite du
    modèle, la requête est refusée (400) avec un message explicite.
    """
    logger.info(f"🔍 Requête reçue: {request.dict()}")
    logger.info(f"🔍 reasoning_mode: {request.reasoning_mode}")

    project = db.query(Project).filter(
        Project.id == request.project_id,
        Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    conversation = _get_or_create_conversation(db, request, current_user)

    # Historique chargé AVANT le retrieval : le budget RAG dépend de la conversation
    past_messages = db.query(RAGMessage).filter(
        RAGMessage.conversation_id == conversation.id
    ).order_by(RAGMessage.created_at.asc()).all()

    query_type = detect_query_type(request.message, len(past_messages))
    strategy = RAG_STRATEGIES[query_type]
    logger.info(f"🎯 Query type: {query_type.value} - {strategy['description']}")

    context_limit = get_model_limit(request.model)
    question_tokens = estimate_tokens(request.message)

    # Borne haute du budget RAG : ce qui reste après l'historique complet (sans dédup)
    probe = build_history(past_messages)
    room = rag_room(context_limit, probe.tokens, question_tokens)
    if room <= 0:
        logger.error(f"❌ Conversation pleine: historique {probe.tokens:,}/{context_limit:,} tokens")
        raise HTTPException(
            status_code=400,
            detail=f"Conversation pleine ({probe.tokens:,}/{context_limit:,} tokens). "
                   f"Ouvre une nouvelle conversation.",
        )

    # feature/Ticket#55: top_k adaptatif selon stratégie ET modèle
    adaptive_top_k = strategy["top_k"]
    if context_limit < 32000:
        adaptive_top_k = min(adaptive_top_k, 15)  # Petit modèle
    elif context_limit > 100000:
        adaptive_top_k = min(adaptive_top_k, 60)  # Gros modèle
    logger.info(f"📊 Stratégie: top_k={adaptive_top_k}, context_ratio={strategy['context_ratio']}")

    # 1. RETRIEVAL + 2. CONTEXTE RAG du tour courant
    results = retrieve_chunks(
        vector_store, embedder, project, request.project_id, request.message, adaptive_top_k
    )
    rag = build_rag_context(
        request.project_id,
        strategy,
        results,
        max_tokens=min(int(context_limit * strategy["context_ratio"]), room),
    )
    retrieved_chunks = rag.chunks

    # 3. HISTORIQUE COMPLET (chunks déjà présents dans le system prompt non répétés)
    history = build_history(past_messages, exclude={chunk_hash(c) for c in retrieved_chunks})

    # 4. MESSAGES
    messages = []
    system_tokens = 0
    # System prompt (règles, langue, citations) aussi sur les suivis sans nouveau chunk
    if rag.text or history.messages:
        effective_reasoning = resolve_reasoning(request.reasoning_mode, request.message, query_type)
        system_prompt = build_system_prompt(rag.text, query_type, effective_reasoning)
        system_tokens = estimate_tokens(system_prompt)
        messages.append({"role": "system", "content": system_prompt})
        logger.info(f"📋 System prompt: {system_tokens:,} tokens")

    messages.extend(history.messages)
    messages.append({"role": "user", "content": request.message})

    usage = ContextUsage(
        limit=context_limit,
        system_tokens=system_tokens,
        history_tokens=history.tokens,
        question_tokens=question_tokens,
        history_messages=len(history.messages),
        carried_chunks=history.carried_chunks,
    )
    logger.info(
        f"🧠 Model: {request.model} limit={context_limit:,} | historique complet={history.tokens:,} "
        f"({len(history.messages)} msgs, {history.carried_chunks} chunks repris) | room_rag={room:,}"
    )
    log_fn = logger.warning if usage.percent >= WARN_PERCENT else logger.info
    log_fn(usage.log_line())

    if usage.overflow:
        logger.error(f"❌ Context overflow! {usage.used:,} > {context_limit - usage.reserve:,}")
        raise HTTPException(
            status_code=400,
            detail=f"Context too large ({usage.used:,}/{context_limit:,} tokens). "
                   f"Ouvre une nouvelle conversation.",
        )

    # 5. PROVIDER LLM
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

    # Sauvegarde du message user seulement une fois la requête validée
    # (pas de message orphelin en base si 400/404 ci-dessus)
    user_message = RAGMessage(
        conversation_id=conversation.id,
        role="user",
        content=request.message
    )
    db.add(user_message)
    db.commit()

    # 6. STREAM LLM
    async def rag_stream_generator():
        full_response = ""

        try:
            yield f"event: metadata\ndata: {json.dumps({'query_type': query_type.value, 'chunks': len(retrieved_chunks), 'tokens': usage.used})}\n\n"
            yield f"event: context\ndata: {json.dumps(usage.to_event())}\n\n"
            yield f"event: retrieval\ndata: {json.dumps({'chunks': retrieved_chunks})}\n\n"

            # Stream LLM (+ vérification : off | annotate | gate)
            mode = effective_mode(request.verify_mode)
            logger.info(f"🤖 Starting LLM stream with {request.provider_name}/{request.model} (verify: {mode})")

            pipeline = None
            if mode != "off":
                pipeline = build_request_pipeline(
                    db, current_user.id, llm_provider, request.model, is_rag=True
                )
            ctx = VerificationContext(
                question=request.message, retrieved_chunks=retrieved_chunks, is_rag=True
            )
            settings = get_settings()

            def open_stream(msgs):
                return llm_provider.stream_completion(
                    messages=msgs, model=request.model, temperature=request.temperature
                )

            assistant_message = None
            async for event in run_verified_stream(
                open_stream=open_stream,
                messages=messages,
                ctx=ctx,
                pipeline=pipeline,
                mode=mode,
                max_rounds=settings.VERIFY_MAX_ROUNDS,
                min_score=settings.VERIFY_MIN_SCORE,
                keepalive_seconds=settings.VERIFY_KEEPALIVE_SECONDS,
            ):
                if event.kind == "token":
                    yield f"event: message\ndata: {json.dumps({'content': event.data})}\n\n"
                elif event.kind == "final":
                    full_response = event.data
                    # Sauvegarder réponse tout de suite (résiste à une déconnexion client).
                    # retrieved_chunks est relu aux tours suivants pour rejouer le contexte.
                    assistant_message = RAGMessage(
                        conversation_id=conversation.id,
                        role="assistant",
                        content=full_response,
                        retrieved_chunks=json.dumps(retrieved_chunks)
                    )
                    db.add(assistant_message)
                    conversation.updated_at = datetime.utcnow()
                    db.commit()
                elif event.kind == "status":
                    yield format_sse("status", status_payload(event.data))
                elif event.kind == "keepalive":
                    yield SSE_KEEPALIVE
                elif event.kind == "verdict":
                    if assistant_message is not None:
                        try:
                            assistant_message.verification = event.data.to_dict()
                            db.commit()
                        except Exception:
                            logger.exception("Could not persist RAG verification verdict")
                            db.rollback()
                    yield format_sse("verdict", verdict_payload(event.data))

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


# ============================================================================
# CRUD CONVERSATIONS
# ============================================================================

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