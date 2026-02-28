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
    ProjectListResponse,
)

router = APIRouter(prefix="/api/projects", tags=["RAG Projects"])

# Global vector store instance (lazy OpenSearch init on first use)
vector_store = VectorStore()


@router.get("/", response_model=List[ProjectListResponse])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Liste tous les projets RAG de l'utilisateur."""
    projects = (
        db.query(Project)
        .filter(Project.user_id == current_user.id)
        .order_by(Project.updated_at.desc())
        .all()
    )

    result = []
    for project in projects:
        doc_count = (
            db.query(Document).filter(Document.project_id == project.id).count()
        )
        total_chunks = (
            db.query(func.sum(Document.chunk_count))
            .filter(Document.project_id == project.id)
            .scalar()
            or 0
        )
        result.append(
            ProjectListResponse(
                id=project.id,
                name=project.name,
                description=project.description,
                document_count=doc_count,
                total_chunks=total_chunks,
                is_active=project.is_active,
                vector_store_type=getattr(project, "vector_store_type", "chroma"),
                opensearch_index=getattr(project, "opensearch_index", None),
                created_at=project.created_at,
                updated_at=project.updated_at,
            )
        )

    return result


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crée un nouveau projet RAG avec le vector store sélectionné."""

    # Check duplicate name
    existing = (
        db.query(Project)
        .filter(
            Project.user_id == current_user.id,
            Project.name == project_data.name,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project '{project_data.name}' already exists",
        )

    project = Project(user_id=current_user.id, **project_data.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)

    # Initialize vector store backend(s) for this project
    try:
        vector_store.get_or_create_collection(
            project_id=str(project.id),
            vector_store_type=project.vector_store_type,
            opensearch_index=project.opensearch_index,
        )
    except Exception as e:
        # Don't roll back the project — vector store init can be retried on first upload
        import logging
        logging.getLogger(__name__).error(
            f"Vector store init failed for project {project.id}: {e}"
        )

    return project


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_update: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

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
    db: Session = Depends(get_db),
):
    """Supprime un projet et toutes ses collections vector store."""
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Delete vector store collection(s)
    try:
        vector_store.delete_collection(
            project_id=str(project_id),
            vector_store_type=getattr(project, "vector_store_type", "chroma"),
            opensearch_index=getattr(project, "opensearch_index", None),
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Vector store cleanup error for {project_id}: {e}")

    db.delete(project)
    db.commit()
    return None


@router.get("/{project_id}/stats")
async def get_project_stats(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Statistiques d'un projet (DB + vector store)."""
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    doc_count = db.query(Document).filter(Document.project_id == project_id).count()
    total_chunks = (
        db.query(func.sum(Document.chunk_count))
        .filter(Document.project_id == project_id)
        .scalar()
        or 0
    )
    total_tokens = (
        db.query(func.sum(Document.total_tokens))
        .filter(Document.project_id == project_id)
        .scalar()
        or 0
    )

    vs_type = getattr(project, "vector_store_type", "chroma")
    os_index = getattr(project, "opensearch_index", None)
    vs_stats = vector_store.get_collection_stats(
        project_id=str(project_id),
        vector_store_type=vs_type,
        opensearch_index=os_index,
    )

    return {
        "project_id": project_id,
        "name": project.name,
        "documents": doc_count,
        "chunks": total_chunks,
        "tokens": total_tokens,
        "vector_store_type": vs_type,
        "opensearch_index": os_index,
        "vector_count": vs_stats.get("count", 0),
        "vector_store_stats": vs_stats,
    }