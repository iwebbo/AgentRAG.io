import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models import User, Project, Document as DocModel
from app.dependencies import get_current_user
from app.services.vector_store import VectorStore
from app.services.embeddings import EmbeddingManager
from app.services.document_processor import DocumentProcessor
from app.services.chunker import SmartChunker

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

MAX_FILE_SIZE = int(os.getenv("MAX_UPLOAD_SIZE_MB", "100")) * 1024 * 1024
STALE_PROCESSING_MINUTES = int(os.getenv("DOC_STALE_MINUTES", "30"))
executor = ThreadPoolExecutor(
    max_workers=int(os.getenv("DOC_PROCESSING_WORKERS", "2")),
    thread_name_prefix="doc-processing",
)


# ── Background processing ─────────────────────────────────────────────────────

def process_document(
    document_id: UUID,
    project_id: UUID,
    file_path: Path,
    vector_store_type: str,
    opensearch_index: Optional[str],
):
    """extract → chunk → embed → store. Runs in `executor` with its own DB session."""
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        chunker = SmartChunker(chunk_size=project.chunk_size, overlap=project.chunk_overlap)

        text = processor.extract_text(file_path)
        chunks = chunker.chunk_text(
            text,
            metadata={
                "filename": file_path.name,
                "project_id": str(project_id),
                "document_id": str(document_id),
            },
        )
        if not chunks:
            raise ValueError("Aucun texte extractible dans ce document")

        texts = [c["text"] for c in chunks]
        embeddings = embedder.encode(texts)

        vector_store.add_documents(
            project_id=str(project_id),
            documents=texts,
            metadatas=[c["metadata"] for c in chunks],
            ids=[f"{document_id}_{i}" for i in range(len(chunks))],
            embeddings=embeddings,
            vector_store_type=vector_store_type,
            opensearch_index=opensearch_index,
        )

        document = db.query(DocModel).filter(DocModel.id == document_id).first()
        document.chunk_count = len(chunks)
        document.total_tokens = sum(c["tokens"] for c in chunks)
        document.status = "completed"
        document.processed_at = datetime.utcnow()
        db.commit()
        logger.info(f"Document {document_id} processed: {len(chunks)} chunks [{vector_store_type}]")

    except Exception as e:
        db.rollback()
        logger.error(f"Error processing document {document_id}: {e}")
        try:
            vector_store.delete_document(
                project_id=str(project_id),
                document_id=str(document_id),
                vector_store_type=vector_store_type,
                opensearch_index=opensearch_index,
            )
        except Exception as cleanup_error:
            logger.warning(f"Vector cleanup failed for {document_id}: {cleanup_error}")
        document = db.query(DocModel).filter(DocModel.id == document_id).first()
        if document:
            document.status = "failed"
            document.error_message = str(e)[:500]
            db.commit()
    finally:
        db.close()


def _fail_stale_documents(db: Session, project_id: UUID):
    """Marks documents orphaned by a restart (task lost) as failed."""
    cutoff = datetime.utcnow() - timedelta(minutes=STALE_PROCESSING_MINUTES)
    updated = (
        db.query(DocModel)
        .filter(
            DocModel.project_id == project_id,
            DocModel.status == "processing",
            DocModel.uploaded_at < cutoff,
        )
        .update(
            {"status": "failed", "error_message": "Traitement interrompu (redémarrage du service)"},
            synchronize_session=False,
        )
    )
    if updated:
        db.commit()


def _get_user_project(db: Session, project_id: UUID, user: User) -> Project:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/{project_id}/upload", response_model=DocumentUploadResponse)
def upload_document(
    project_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload d'un fichier puis vectorisation asynchrone. Appelé une fois par fichier."""
    project = _get_user_project(db, project_id, current_user)

    filename = Path(file.filename or "").name
    if not filename or not processor.is_supported(filename):
        raise HTTPException(
            status_code=400,
            detail=f"Format non supporté. Formats: {', '.join(processor.SUPPORTED_FORMATS.keys())}",
        )

    duplicate = (
        db.query(DocModel.id)
        .filter(
            DocModel.project_id == project_id,
            DocModel.filename == filename,
            DocModel.status != "failed",
        )
        .first()
    )
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=f"'{filename}' existe déjà dans ce projet (supprimez-le avant de le renvoyer)",
        )

    document_id = uuid4()
    doc_dir = UPLOAD_DIR / str(project_id) / str(document_id)
    doc_dir.mkdir(parents=True)
    file_path = doc_dir / filename

    try:
        file_size = 0
        with file_path.open("wb") as out:
            while chunk := file.file.read(1024 * 1024):
                file_size += len(chunk)
                if file_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Fichier trop volumineux (max {MAX_FILE_SIZE // (1024 * 1024)} MB)",
                    )
                out.write(chunk)
        if file_size == 0:
            raise HTTPException(status_code=400, detail="Fichier vide")

        db.add(
            DocModel(
                id=document_id,
                project_id=project_id,
                filename=filename,
                file_path=str(file_path),
                file_type=file_path.suffix.lower()[1:],
                file_size=file_size,
                status="processing",
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        shutil.rmtree(doc_dir, ignore_errors=True)
        raise

    executor.submit(
        process_document,
        document_id,
        project_id,
        file_path,
        getattr(project, "vector_store_type", "chroma"),
        getattr(project, "opensearch_index", None),
    )

    return DocumentUploadResponse(
        document_id=document_id,
        filename=filename,
        status="processing",
        message="Document is being processed in background",
    )


@router.get("/{project_id}/documents", response_model=List[DocumentResponse])
async def list_documents(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_user_project(db, project_id, current_user)
    _fail_stale_documents(db, project_id)

    return (
        db.query(DocModel)
        .filter(DocModel.project_id == project_id)
        .order_by(DocModel.uploaded_at.desc())
        .all()
    )


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

    vector_store.delete_document(
        project_id=str(document.project_id),
        document_id=str(document_id),
        vector_store_type=getattr(project, "vector_store_type", "chroma"),
        opensearch_index=getattr(project, "opensearch_index", None),
    )

    try:
        file_path = Path(document.file_path)
        if file_path.parent.name == str(document_id):
            shutil.rmtree(file_path.parent, ignore_errors=True)
        else:
            file_path.unlink(missing_ok=True)
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
    document = (
        db.query(DocModel)
        .join(Project, Project.id == DocModel.project_id)
        .filter(DocModel.id == document_id, Project.user_id == current_user.id)
        .first()
    )
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