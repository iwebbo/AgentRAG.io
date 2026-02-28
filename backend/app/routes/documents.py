from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from pathlib import Path
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime
import shutil
import logging

from app.database import get_db
from app.models import User, Project, Document as DocModel
from app.dependencies import get_current_user
from app.services.vector_store import VectorStore
from app.services.embeddings import EmbeddingManager
from app.services.document_processor import DocumentProcessor
from app.services.chunker import SmartChunker
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ── Inline schemas ────────────────────────────────────────────────────────────

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

    class Config:
        from_attributes = True


class DocumentUploadResponse(BaseModel):
    document_id: UUID
    filename: str
    status: str
    message: str


# ── Router & global instances ─────────────────────────────────────────────────

router = APIRouter(prefix="/api/documents", tags=["Documents"])

vector_store = VectorStore()
embedder = EmbeddingManager()
processor = DocumentProcessor()

UPLOAD_DIR = Path("./data/documents")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ── Background processing ─────────────────────────────────────────────────────

def process_document_background(
    document_id: UUID,
    project_id: UUID,
    file_path: Path,
    db: Session,
    vector_store_type: str = "chroma",
    opensearch_index: Optional[str] = None,
):
    """
    Async background task: extract → chunk → embed → store in vector backend(s).
    vector_store_type and opensearch_index come from the owning Project model.
    """
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        chunker = SmartChunker(
            chunk_size=project.chunk_size, overlap=project.chunk_overlap
        )

        # Extract text
        text = processor.extract_text(file_path)

        # Chunk
        chunks = chunker.chunk_text(
            text,
            metadata={
                "filename": file_path.name,
                "project_id": str(project_id),
                "document_id": str(document_id),
            },
        )

        # Embed (same model regardless of vector store backend)
        texts = [c["text"] for c in chunks]
        embeddings = embedder.encode(texts)

        # Store in vector backend(s)
        ids = [f"{document_id}_{i}" for i in range(len(chunks))]
        metadatas = [c["metadata"] for c in chunks]

        vector_store.add_documents(
            project_id=str(project_id),
            documents=texts,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings,
            vector_store_type=vector_store_type,
            opensearch_index=opensearch_index,
        )

        # Update document record
        document = db.query(DocModel).filter(DocModel.id == document_id).first()
        document.chunk_count = len(chunks)
        document.total_tokens = sum(c["tokens"] for c in chunks)
        document.status = "completed"
        document.processed_at = datetime.utcnow()
        db.commit()

        logger.info(f"✅ Document {document_id} processed: {len(chunks)} chunks [{vector_store_type}]")

    except Exception as e:
        logger.error(f"❌ Error processing document {document_id}: {e}")
        document = db.query(DocModel).filter(DocModel.id == document_id).first()
        if document:
            document.status = "failed"
            document.error_message = str(e)
            db.commit()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/{project_id}/upload", response_model=DocumentUploadResponse)
async def upload_document(
    project_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload et vectorisation automatique dans le vector store du projet."""

    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not processor.is_supported(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Format non supporté. Formats: {', '.join(processor.SUPPORTED_FORMATS.keys())}",
        )

    document_id = uuid4()
    project_dir = UPLOAD_DIR / str(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    file_path = project_dir / f"{document_id}_{file.filename}"

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_size = file_path.stat().st_size

    document = DocModel(
        id=document_id,
        project_id=project_id,
        filename=file.filename,
        file_path=str(file_path),
        file_type=file_path.suffix.lower()[1:],
        file_size=file_size,
        status="processing",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Pass vector store config from project to background task
    background_tasks.add_task(
        process_document_background,
        document_id,
        project_id,
        file_path,
        db,
        getattr(project, "vector_store_type", "chroma"),
        getattr(project, "opensearch_index", None),
    )

    return DocumentUploadResponse(
        document_id=document_id,
        filename=file.filename,
        status="processing",
        message="Document is being processed in background",
    )


@router.get("/{project_id}/documents", response_model=List[DocumentResponse])
async def list_documents(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    documents = (
        db.query(DocModel)
        .filter(DocModel.project_id == project_id)
        .order_by(DocModel.uploaded_at.desc())
        .all()
    )
    return documents


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Supprime un document et ses vecteurs dans le/les backends actifs."""
    document = db.query(DocModel).filter(DocModel.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    project = (
        db.query(Project)
        .filter(
            Project.id == document.project_id,
            Project.user_id == current_user.id,
        )
        .first()
    )
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")

    # Delete vectors from all active backends for this project
    vector_store.delete_document(
        project_id=str(document.project_id),
        document_id=str(document_id),
        vector_store_type=getattr(project, "vector_store_type", "chroma"),
        opensearch_index=getattr(project, "opensearch_index", None),
    )

    try:
        Path(document.file_path).unlink(missing_ok=True)
    except Exception as e:
        logger.error(f"Error deleting file: {e}")

    db.delete(document)
    db.commit()
    return None


@router.get("/{document_id}/status")
async def get_document_status(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = db.query(DocModel).filter(DocModel.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "document_id": document_id,
        "filename": document.filename,
        "status": document.status,
        "chunk_count": document.chunk_count,
        "total_tokens": document.total_tokens,
        "error_message": document.error_message,
    }