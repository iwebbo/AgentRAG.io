from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks, status  # ← AJOUTER status
from sqlalchemy.orm import Session
from pathlib import Path
from typing import List, Optional  # ← AJOUTER Optional si pas là
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
from app.schemas.document import (DocumentResponse, DocumentUploadResponse)
# Schemas inline temporaires
from pydantic import BaseModel

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

router = APIRouter(prefix="/api/documents", tags=["Documents"])
logger = logging.getLogger(__name__)

# Global instances
vector_store = VectorStore()
embedder = EmbeddingManager()
processor = DocumentProcessor()

UPLOAD_DIR = Path("./data/documents")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def process_document_background(
    document_id: UUID,
    project_id: UUID,
    file_path: Path,
    db: Session
):
    """Traitement asynchrone du document"""
    try:
        # Récupérer projet
        project = db.query(Project).filter(Project.id == project_id).first()
        chunker = SmartChunker(chunk_size=project.chunk_size, overlap=project.chunk_overlap)
        
        # Extraction texte
        text = processor.extract_text(file_path)
        
        # Chunking
        chunks = chunker.chunk_text(text, metadata={
            "filename": file_path.name,
            "project_id": str(project_id),
            "document_id": str(document_id)
        })
        
        # Embeddings
        texts = [c["text"] for c in chunks]
        embeddings = embedder.encode(texts)
        
        # Stockage ChromaDB
        ids = [f"{document_id}_{i}" for i in range(len(chunks))]
        metadatas = [c["metadata"] for c in chunks]
        
        vector_store.add_documents(
            project_id=str(project_id),
            documents=texts,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings
        )
        
        # Mise à jour document
        document = db.query(DocModel).filter(DocModel.id == document_id).first()
        document.chunk_count = len(chunks)
        document.total_tokens = sum(c["tokens"] for c in chunks)
        document.status = "completed"
        document.processed_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"✅ Document {document_id} processed: {len(chunks)} chunks")
        
    except Exception as e:
        logger.error(f"❌ Error processing document {document_id}: {e}")
        document = db.query(DocModel).filter(DocModel.id == document_id).first()
        if document:
            document.status = "failed"
            document.error_message = str(e)
            db.commit()


@router.post("/{project_id}/upload", response_model=DocumentUploadResponse)
async def upload_document(
    project_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload et vectorisation automatique"""
    
    # Vérifier projet
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Vérifier format
    if not processor.is_supported(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Format non supporté. Formats acceptés: {', '.join(processor.SUPPORTED_FORMATS.keys())}"
        )
    
    # Sauvegarder fichier
    document_id = uuid4()
    project_dir = UPLOAD_DIR / str(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = project_dir / f"{document_id}_{file.filename}"
    
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    file_size = file_path.stat().st_size
    
    # Créer entrée DB
    document = DocModel(
        id=document_id,
        project_id=project_id,
        filename=file.filename,
        file_path=str(file_path),
        file_type=file_path.suffix.lower()[1:],
        file_size=file_size,
        status="processing"
    )
    
    db.add(document)
    db.commit()
    db.refresh(document)
    
    # Traitement asynchrone
    background_tasks.add_task(
        process_document_background,
        document_id,
        project_id,
        file_path,
        db
    )
    
    return DocumentUploadResponse(
        document_id=document_id,
        filename=file.filename,
        status="processing",
        message="Document is being processed in background"
    )


@router.get("/{project_id}/documents", response_model=List[DocumentResponse])
async def list_documents(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Liste documents d'un projet"""
    
    # Vérifier accès projet
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    documents = db.query(DocModel).filter(
        DocModel.project_id == project_id
    ).order_by(
        DocModel.uploaded_at.desc()
    ).all()
    
    return documents


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)  # ← status est maintenant défini
async def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Supprime un document"""
    
    document = db.query(DocModel).filter(DocModel.id == document_id).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Vérifier ownership via projet
    project = db.query(Project).filter(
        Project.id == document.project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Supprimer du vectorstore
    vector_store.delete_document(str(document.project_id), str(document_id))
    
    # Supprimer fichier
    try:
        Path(document.file_path).unlink(missing_ok=True)
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
    
    # Supprimer de DB
    db.delete(document)
    db.commit()
    
    return None


@router.get("/{document_id}/status")
async def get_document_status(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Vérifie le statut de traitement"""
    
    document = db.query(DocModel).filter(DocModel.id == document_id).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "document_id": document_id,
        "filename": document.filename,
        "status": document.status,
        "chunk_count": document.chunk_count,
        "total_tokens": document.total_tokens,
        "error_message": document.error_message
    }

@router.get("/documents")
async def get_all_documents(db: Session = Depends(get_db)):
    """Récupère tous les documents"""
    documents = db.query(DocModel).all()
    return documents

# Route par projet - documents du projet
@router.get("/projects/{project_id}/documents")
async def get_project_documents(project_id: str, db: Session = Depends(get_db)):
    """Récupère les documents d'un projet spécifique"""
    # Vérifier que le projet existe
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    documents = db.query(DocModel).filter(DocModel.project_id == project_id).all()
    return documents

# Upload global
@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload un document global (sans projet)"""
    try:
        # Lire le fichier
        content = await file.read()
        
        # Créer l'entrée en base
        doc = DocModel(
            filename=file.filename,
            file_type=file.filename.split('.')[-1],
            file_size=len(content),
            project_id=None  # Document global
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        
        # Traiter le document (chunking + embeddings)
        await process_document(doc.id, content, db)
        
        return {"message": "Document uploaded successfully", "document_id": doc.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Upload par projet
@router.post("/projects/{project_id}/documents/upload")
async def upload_project_document(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload un document pour un projet spécifique"""
    # Vérifier que le projet existe
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        content = await file.read()
        
        doc = DocModel(
            filename=file.filename,
            file_type=file.filename.split('.')[-1],
            file_size=len(content),
            project_id=project_id
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        
        # Traiter le document
        await process_document(doc.id, content, db, project_id=project_id)
        
        return {"message": "Document uploaded successfully", "document_id": doc.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Delete global
@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, db: Session = Depends(get_db)):
    """Supprime un document"""
    doc = db.query(DocModel).filter(DocModel.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Supprimer les embeddings de ChromaDB
    # ... code de suppression dans ChromaDB ...
    
    db.delete(doc)
    db.commit()
    return {"message": "Document deleted successfully"}

# Delete par projet
@router.delete("/projects/{project_id}/documents/{document_id}")
async def delete_project_document(
    project_id: str,
    document_id: str,
    db: Session = Depends(get_db)
):
    """Supprime un document d'un projet"""
    doc = db.query(DocModel).filter(
        DocModel.id == document_id,
        DocModel.project_id == project_id
    ).first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Supprimer les embeddings
    # ... code de suppression dans ChromaDB ...
    
    db.delete(doc)
    db.commit()
    return {"message": "Document deleted successfully"}
