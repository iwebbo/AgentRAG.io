from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class RAGChatRequest(BaseModel):
    """Request pour chat RAG avec contexte documentaire"""
    project_id: UUID
    conversation_id: Optional[UUID] = None
    message: str = Field(..., min_length=1)
    provider_name: str
    model: str
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    reasoning_mode: str = Field(default="standard")
    top_k: Optional[int] = Field(default=5, ge=1, le=20)


class RAGChatResponse(BaseModel):
    """Response d'un message RAG"""
    conversation_id: UUID
    message_id: UUID
    role: str
    content: str
    retrieved_chunks: Optional[str]


class RetrievedChunk(BaseModel):
    """Chunk récupéré du vector store"""
    text: str
    metadata: Dict[str, Any]
    score: float


class RAGMessageResponse(BaseModel):
    """Message d'une conversation RAG"""
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    reasoning_content: Optional[str] = None
    retrieved_chunks: Optional[str]
    tokens_used: Optional[int]
    latency_ms: Optional[int]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class RAGConversationResponse(BaseModel):
    """Conversation RAG complète"""
    id: UUID
    project_id: UUID
    user_id: UUID
    title: str
    provider_name: str
    model: str
    temperature: float
    reasoning_mode: str
    top_k: int
    created_at: datetime
    updated_at: datetime
    messages: List[RAGMessageResponse] = []
    
    model_config = ConfigDict(from_attributes=True)