from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import datetime

from app.database import get_db
from app.models import User, Project, Document
from app.dependencies import get_current_user
from app.services.vector_store import VectorStore
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse
)

router = APIRouter(prefix="/api/projects", tags=["RAG Projects"])

# Global instance
vector_store = VectorStore()


@router.get("/", response_model=List[ProjectListResponse])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Liste tous les projets RAG de l'utilisateur"""
    projects = db.query(Project).filter(
        Project.user_id == current_user.id
    ).order_by(
        Project.updated_at.desc()
    ).all()
    
    # Ajouter stats documents
    result = []
    for project in projects:
        doc_count = db.query(Document).filter(
            Document.project_id == project.id
        ).count()
        
        total_chunks = db.query(func.sum(Document.chunk_count)).filter(
            Document.project_id == project.id
        ).scalar() or 0
        
        result.append(ProjectListResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            document_count=doc_count,
            total_chunks=total_chunks,
            is_active=project.is_active,
            created_at=project.created_at,
            updated_at=project.updated_at
        ))
    
    return result


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crée un nouveau projet RAG"""
    
    # Vérifier si nom existe déjà
    existing = db.query(Project).filter(
        Project.user_id == current_user.id,
        Project.name == project_data.name
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project '{project_data.name}' already exists"
        )
    
    project = Project(
        user_id=current_user.id,
        **project_data.model_dump()
    )
    
    db.add(project)
    db.commit()
    db.refresh(project)
    
    # Créer collection ChromaDB
    vector_store.get_or_create_collection(str(project.id))
    
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Récupère un projet avec ses documents"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_update: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Met à jour un projet"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    update_data = project_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Supprime un projet et tous ses documents"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Supprimer collection ChromaDB
    vector_store.delete_collection(str(project_id))
    
    # Supprimer projet (cascade sur documents)
    db.delete(project)
    db.commit()
    
    return None


@router.get("/{project_id}/stats")
async def get_project_stats(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Statistiques d'un projet"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    doc_count = db.query(Document).filter(
        Document.project_id == project_id
    ).count()
    
    total_chunks = db.query(func.sum(Document.chunk_count)).filter(
        Document.project_id == project_id
    ).scalar() or 0
    
    total_tokens = db.query(func.sum(Document.total_tokens)).filter(
        Document.project_id == project_id
    ).scalar() or 0
    
    # Stats ChromaDB
    chroma_stats = vector_store.get_collection_stats(str(project_id))
    
    return {
        "project_id": project_id,
        "name": project.name,
        "documents": doc_count,
        "chunks": total_chunks,
        "tokens": total_tokens,
        "vector_count": chroma_stats["count"]
    }