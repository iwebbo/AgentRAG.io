from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID

# name: str = Field(..., pattern="^(openai|claude|ollama)$")

class ProviderBase(BaseModel):
    name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    is_active: bool = True
    priority: int = Field(default=0, ge=0, le=100)
    config: Dict[str, Any] = Field(default_factory=dict)


class ProviderCreate(ProviderBase):
    pass


class ProviderUpdate(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = Field(None, ge=0, le=100)
    config: Optional[Dict[str, Any]] = None


class ProviderResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    base_url: Optional[str]
    is_active: bool
    priority: int
    config: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ProviderTestResponse(BaseModel):
    success: bool
    message: str
    latency_ms: Optional[int] = None