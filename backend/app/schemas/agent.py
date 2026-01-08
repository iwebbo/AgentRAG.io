from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime


class AgentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    agent_type: str = Field(..., min_length=1)


class AgentCreate(AgentBase):
    config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    mcp_config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    is_active: bool = True
    priority: int = 0


class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    mcp_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None


class AgentResponse(AgentBase):
    id: UUID
    user_id: UUID
    config: Dict[str, Any]
    mcp_config: Dict[str, Any]
    is_active: bool
    priority: int
    execution_count: int = 0 
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AgentListResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    agent_type: str
    is_active: bool
    execution_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class AgentExecutionCreate(BaseModel):
    input_data: Dict[str, Any]
    trigger: str = "manual"


class AgentExecutionResponse(BaseModel):
    id: UUID
    agent_id: UUID
    status: str
    trigger: str
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]] = None
    logs: List[Dict[str, Any]] = []
    tokens_used: int = 0
    execution_time_ms: Optional[int] = None
    mcp_calls: Dict[str, Any] = {}
    started_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AgentExecutionListResponse(BaseModel):
    id: UUID
    agent_id: UUID
    status: str
    trigger: str
    tokens_used: int
    execution_time_ms: Optional[int]
    started_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True