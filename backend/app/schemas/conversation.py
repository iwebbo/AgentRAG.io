from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class ConversationBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    provider_name: str = Field(...,)
    model: str = Field(..., min_length=1, max_length=100)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    reasoning_mode: str = Field(default="standard", pattern="^(standard|cot|deep)$")
    system_prompt: Optional[str] = None


class ConversationCreate(ConversationBase):
    pass


class ConversationUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    reasoning_mode: Optional[str] = Field(None, pattern="^(standard|cot|deep)$")
    system_prompt: Optional[str] = None


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    reasoning_content: Optional[str]
    tokens_used: Optional[int]
    latency_ms: Optional[int]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ConversationResponse(ConversationBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = []
    
    model_config = ConfigDict(from_attributes=True)


class ConversationListResponse(BaseModel):
    id: UUID
    title: str
    provider_name: str
    model: str
    updated_at: datetime
    message_count: int = 0
    
    model_config = ConfigDict(from_attributes=True)