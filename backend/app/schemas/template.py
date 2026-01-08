from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class TemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    content: str = Field(..., min_length=1)
    variables: List[str] = Field(default_factory=list)
    is_public: bool = False


class TemplateCreate(TemplateBase):
    pass


class TemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    content: Optional[str] = Field(None, min_length=1)
    variables: Optional[List[str]] = None
    is_public: Optional[bool] = None


class TemplateResponse(TemplateBase):
    id: UUID
    user_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class TemplateRenderRequest(BaseModel):
    variables: Dict[str, Any] = Field(default_factory=dict)


class TemplateRenderResponse(BaseModel):
    rendered_content: str