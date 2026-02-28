from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Literal
from datetime import datetime
from uuid import UUID


VectorStoreType = Literal["chroma", "opensearch", "both"]


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    chunk_size: int = Field(default=2000, ge=500, le=8000)
    chunk_overlap: int = Field(default=200, ge=0, le=1000)
    is_active: bool = True

    # ── Vector Store configuration ────────────────────────────────────────────
    # "chroma"     → ChromaDB only  (default, backward-compatible)
    # "opensearch" → OpenSearch only
    # "both"       → index into both; query reads from ChromaDB (primary)
    vector_store_type: VectorStoreType = Field(
        default="chroma",
        description="Vector store backend for this project"
    )
    # Custom OpenSearch index name.
    # If None/empty, auto-generated as: project-<project_id>
    opensearch_index: Optional[str] = Field(
        default=None,
        max_length=255,
        description="OpenSearch index name (auto-generated if not provided)"
    )

    @field_validator("opensearch_index")
    @classmethod
    def validate_index_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().lower()
        if not v:
            return None
        # OpenSearch index naming: lowercase, no spaces, no leading _/-
        import re
        if not re.match(r'^[a-z0-9][a-z0-9_\-]*$', v):
            raise ValueError(
                "OpenSearch index name must be lowercase, start with a letter or digit, "
                "and contain only letters, digits, hyphens, or underscores."
            )
        return v


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    chunk_size: Optional[int] = Field(None, ge=500, le=8000)
    chunk_overlap: Optional[int] = Field(None, ge=0, le=1000)
    is_active: Optional[bool] = None
    opensearch_index: Optional[str] = Field(None, max_length=255)


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
    vector_store_type: str = "chroma"
    opensearch_index: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)