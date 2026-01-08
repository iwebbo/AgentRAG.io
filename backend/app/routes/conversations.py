from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from uuid import UUID
from datetime import date, datetime

from app.database import get_db
from app.models import User, Conversation, Message
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationListResponse,
    MessageResponse
)
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])


@router.get("/stats")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get dashboard statistics for current user"""
    
    # Total conversations (chat)
    total_conversations = db.query(func.count(Conversation.id)).filter(
        Conversation.user_id == current_user.id
    ).scalar()
    
    # Messages today (chat)
    today_start = datetime.combine(date.today(), datetime.min.time())
    messages_today = db.query(func.count(Message.id)).join(
        Conversation, Message.conversation_id == Conversation.id
    ).filter(
        Conversation.user_id == current_user.id,
        Message.created_at >= today_start
    ).scalar()
    
    # Total tokens used (chat)
    tokens_used = db.query(func.sum(Message.tokens_used)).join(
        Conversation, Message.conversation_id == Conversation.id
    ).filter(
        Conversation.user_id == current_user.id,
        Message.tokens_used.isnot(None)
    ).scalar() or 0
    
    # RAG Stats
    from app.models import Project, Document
    
    # Total projects RAG
    total_projects = db.query(func.count(Project.id)).filter(
        Project.user_id == current_user.id
    ).scalar() or 0
    
    # Total documents RAG
    total_documents = db.query(func.count(Document.id)).join(
        Project, Document.project_id == Project.id
    ).filter(
        Project.user_id == current_user.id
    ).scalar() or 0
    
    # Total chunks RAG
    total_chunks = db.query(func.sum(Document.chunk_count)).join(
        Project, Document.project_id == Project.id
    ).filter(
        Project.user_id == current_user.id
    ).scalar() or 0
    
    # Total tokens RAG
    total_rag_tokens = db.query(func.sum(Document.total_tokens)).join(
        Project, Document.project_id == Project.id
    ).filter(
        Project.user_id == current_user.id
    ).scalar() or 0
    
    return {
        "total_conversations": total_conversations,
        "messages_today": messages_today,
        "tokens_used": tokens_used,
        "total_projects": total_projects,
        "total_documents": total_documents,
        "total_chunks": total_chunks,
        "rag_tokens": total_rag_tokens
    }


@router.get("/", response_model=List[ConversationListResponse])
async def list_conversations(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all conversations for current user"""
    
    conversations = db.query(
        Conversation,
        func.count(Message.id).label("message_count")
    ).outerjoin(
        Message, Conversation.id == Message.conversation_id
    ).filter(
        Conversation.user_id == current_user.id
    ).group_by(
        Conversation.id
    ).order_by(
        Conversation.updated_at.desc()
    ).offset(skip).limit(limit).all()
    
    return [
        ConversationListResponse(
            id=conv.id,
            title=conv.title,
            provider_name=conv.provider_name,
            model=conv.model,
            updated_at=conv.updated_at,
            message_count=count
        )
        for conv, count in conversations
    ]


@router.post("/", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    conversation_data: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create new conversation"""
    
    conversation = Conversation(
        user_id=current_user.id,
        **conversation_data.model_dump()
    )
    
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    
    return conversation


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get conversation by ID with all messages"""
    
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    return conversation


@router.put("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: UUID,
    conversation_update: ConversationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update conversation"""
    
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Update fields
    update_data = conversation_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(conversation, field, value)
    
    db.commit()
    db.refresh(conversation)
    
    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete conversation"""
    
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    db.delete(conversation)
    db.commit()
    
    return None


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    conversation_id: UUID,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get messages from conversation"""
    
    # Verify conversation ownership
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(
        Message.created_at.asc()
    ).offset(skip).limit(limit).all()
    
    return messages


@router.delete("/{conversation_id}/messages", status_code=status.HTTP_204_NO_CONTENT)
async def clear_messages(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Clear all messages from conversation"""
    
    # Verify conversation ownership
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).delete()
    
    db.commit()
    
    return None