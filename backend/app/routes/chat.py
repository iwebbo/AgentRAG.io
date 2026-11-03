from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from uuid import uuid4
from typing import Tuple

from app.database import get_db
from app.models import User, Conversation, Message
from app.schemas.chat import ChatRequest, ChatResponse
from app.dependencies import get_current_user
from app.services.llm_service import LLMService
from app.services.context_budget import ContextOverflow
from app.utils.streaming import sse_generator, heartbeat_generator, merge_generators, stream_manager

router = APIRouter(prefix="/api/chat", tags=["Chat"])


def _get_or_create_conversation(
    request: ChatRequest, user: User, db: Session
) -> Tuple[Conversation, bool]:
    """Retourne (conversation, créée_maintenant)."""
    if request.conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == request.conversation_id,
            Conversation.user_id == user.id
        ).first()

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        return conversation, False

    conversation = Conversation(
        user_id=user.id,
        title=request.message[:50] + "..." if len(request.message) > 50 else request.message,
        provider_name=request.provider_name or "openai",
        model=request.model or "gpt-3.5-turbo",
        temperature=request.temperature or 0.7,
        reasoning_mode=request.reasoning_mode or "standard",
        system_prompt=request.system_prompt
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation, True


def _ensure_context_fits(
    llm_service: LLMService,
    conversation: Conversation,
    request: ChatRequest,
    created: bool,
    db: Session,
) -> None:
    """Refuse explicitement (400) si prompt + historique + question dépassent
    la limite du modèle, avant d'ouvrir le stream. Rien n'est persisté."""
    try:
        llm_service.preflight(
            conversation,
            request.message,
            reasoning_mode=request.reasoning_mode,
            model=request.model,
        )
    except ContextOverflow as e:
        if created:  # ne pas laisser de conversation vide orpheline
            db.delete(conversation)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "context_overflow", "message": str(e)},
        )


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Stream chat completion using Server-Sent Events
    """
    conversation, created = _get_or_create_conversation(request, current_user, db)

    llm_service = LLMService(db)
    _ensure_context_fits(llm_service, conversation, request, created, db)

    # Generate stream ID
    stream_id = str(uuid4())
    await stream_manager.create_stream(stream_id)

    # Get LLM stream
    llm_stream = llm_service.stream_chat(
        user_id=current_user.id,
        conversation_id=conversation.id,
        message=request.message,
        provider_name=request.provider_name,
        model=request.model,
        temperature=request.temperature,
        reasoning_mode=request.reasoning_mode,
        verify_mode=request.verify_mode,
        emit_events=True,
        managed_context=True
    )

    # Create SSE stream with heartbeat
    sse_stream = sse_generator(stream_id, llm_stream, stream_manager)
    heartbeat = heartbeat_generator(interval=15)

    # Merge streams
    combined_stream = merge_generators(sse_stream, heartbeat)

    return StreamingResponse(
        combined_stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Stream-ID": stream_id
        }
    )


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Send message and get complete response (non-streaming)
    """
    conversation, created = _get_or_create_conversation(request, current_user, db)

    llm_service = LLMService(db)
    _ensure_context_fits(llm_service, conversation, request, created, db)

    # Collect full response
    full_response = ""
    async for chunk in llm_service.stream_chat(
        user_id=current_user.id,
        conversation_id=conversation.id,
        message=request.message,
        provider_name=request.provider_name,
        model=request.model,
        temperature=request.temperature,
        reasoning_mode=request.reasoning_mode,
        verify_mode=request.verify_mode,
        managed_context=True
    ):
        full_response += chunk

    # Get last message (assistant response)
    last_message = db.query(Message).filter(
        Message.conversation_id == conversation.id,
        Message.role == "assistant"
    ).order_by(Message.created_at.desc()).first()

    return ChatResponse(
        conversation_id=conversation.id,
        message_id=last_message.id,
        role="assistant",
        content=full_response,
        tokens_used=last_message.tokens_used,
        latency_ms=last_message.latency_ms,
        verification=last_message.verification
    )