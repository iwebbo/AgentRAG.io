from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from uuid import UUID, uuid4
import asyncio

from app.database import get_db
from app.models import User, Conversation
from app.schemas.chat import ChatRequest, ChatResponse
from app.dependencies import get_current_user
from app.services.llm_service import LLMService
from app.utils.streaming import sse_generator, heartbeat_generator, merge_generators, stream_manager

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Stream chat completion using Server-Sent Events
    """
    
    # Create or get conversation
    if request.conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == request.conversation_id,
            Conversation.user_id == current_user.id
        ).first()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
    else:
        # Create new conversation
        conversation = Conversation(
            user_id=current_user.id,
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
    
    # Create LLM service
    llm_service = LLMService(db)
    
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
        reasoning_mode=request.reasoning_mode
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
    
    # Create or get conversation
    if request.conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == request.conversation_id,
            Conversation.user_id == current_user.id
        ).first()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
    else:
        # Create new conversation
        conversation = Conversation(
            user_id=current_user.id,
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
    
    # Create LLM service
    llm_service = LLMService(db)
    
    # Collect full response
    full_response = ""
    async for chunk in llm_service.stream_chat(
        user_id=current_user.id,
        conversation_id=conversation.id,
        message=request.message,
        provider_name=request.provider_name,
        model=request.model,
        temperature=request.temperature,
        reasoning_mode=request.reasoning_mode
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
        latency_ms=last_message.latency_ms
    )