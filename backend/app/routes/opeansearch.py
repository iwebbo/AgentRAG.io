from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
import logging
import re

from app.routes.projects import vector_store
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/opensearch", tags=["OpenSearch"])


class OpenSearchHealthResponse(BaseModel):
    status: str
    cluster_status: Optional[str] = None
    version: Optional[str] = None
    cluster_name: Optional[str] = None
    detail: Optional[str] = None


class IndexInfo(BaseModel):
    index: str
    docs_count: Optional[str] = None
    store_size: Optional[str] = None


class CreateIndexRequest(BaseModel):
    index_name: str = Field(..., min_length=1, max_length=255)

    @field_validator("index_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r'^[a-z0-9][a-z0-9_\-]*$', v):
            raise ValueError(
                "Index name must be lowercase, start with letter/digit, "
                "contain only letters, digits, hyphens, or underscores."
            )
        return v


class OpenSearchSettingsResponse(BaseModel):
    host: str
    port: int
    user: Optional[str]
    use_ssl: bool
    verify_certs: bool
    embedding_dim: int


@router.get("/health", response_model=OpenSearchHealthResponse)
async def opensearch_health():
    result = vector_store.opensearch_health()
    return OpenSearchHealthResponse(**result)


@router.get("/indices", response_model=List[IndexInfo])
async def list_opensearch_indices():
    raw = vector_store.opensearch_list_indices()
    return [
        IndexInfo(
            index=item.get("index", ""),
            docs_count=item.get("docs.count"),
            store_size=item.get("store.size"),
        )
        for item in raw
    ]


@router.post("/indices", status_code=201)
async def create_opensearch_index(body: CreateIndexRequest):
    try:
        created = vector_store.opensearch_create_index(body.index_name)
        if created:
            return {"index": body.index_name, "created": True}
        return {"index": body.index_name, "created": False, "message": "Index already exists"}
    except Exception as e:
        logger.error(f"Create index error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/indices/{index_name}/exists")
async def index_exists(index_name: str):
    exists = vector_store.opensearch_index_exists(index_name.strip().lower())
    return {"index": index_name, "exists": exists}


@router.get("/settings", response_model=OpenSearchSettingsResponse)
async def get_opensearch_settings():
    s = get_settings()
    return OpenSearchSettingsResponse(
        host=s.OPENSEARCH_HOST,
        port=s.OPENSEARCH_PORT,
        user=s.OPENSEARCH_USER,
        use_ssl=s.OPENSEARCH_USE_SSL,
        verify_certs=s.OPENSEARCH_VERIFY_CERTS,
        embedding_dim=s.OPENSEARCH_EMBEDDING_DIM,
    )