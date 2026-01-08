from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    chunk_size: int = Field(default=2000, ge=500, le=8000)
    chunk_overlap: int = Field(default=200, ge=0, le=1000)
    is_active: bool = True


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    chunk_size: Optional[int] = Field(None, ge=500, le=8000)
    chunk_overlap: Optional[int] = Field(None, ge=0, le=1000)
    is_active: Optional[bool] = None


class ProjectResponse(ProjectBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ProjectListResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    document_count: int
    total_chunks: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)