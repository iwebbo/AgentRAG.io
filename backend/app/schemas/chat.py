from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class ChatRequest(BaseModel):
    conversation_id: Optional[UUID] = None
    message: str = Field(..., min_length=1)
    provider_name: Optional[str] = Field(None)
    model: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    reasoning_mode: Optional[str] = Field(None, pattern="^(standard|cot|deep)$")
    system_prompt: Optional[str] = None
    stream: bool = True


class ChatResponse(BaseModel):
    conversation_id: UUID
    message_id: UUID
    role: str
    content: str
    reasoning_content: Optional[str] = None
    tokens_used: Optional[int] = None
    latency_ms: Optional[int] = None


class StreamChunk(BaseModel):
    type: str  # content, reasoning, metadata, error, done
    data: str
    conversation_id: Optional[UUID] = None
    message_id: Optional[UUID] = None