from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID


class DocumentResponse(BaseModel):
    id: UUID
    project_id: UUID
    filename: str
    file_type: str
    file_size: int
    chunk_count: int
    total_tokens: int
    status: str
    error_message: Optional[str]
    uploaded_at: datetime
    processed_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


class DocumentUploadResponse(BaseModel):
    document_id: UUID
    filename: str
    status: str
    message: str