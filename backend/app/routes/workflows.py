import json
import logging
from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.models.workflows import Workflow, WorkflowRun
from app.schemas.workflows import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse,
    WorkflowListResponse,
    WorkflowExecuteRequest,
    WorkflowRunResponse,
    WorkflowRunListResponse,
)
from app.services import workflows as workflow_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["Workflows"])


def _get_owned(db: Session, workflow_id: UUID, user: User) -> Workflow:
    workflow = db.query(Workflow).filter(
        Workflow.id == workflow_id, Workflow.user_id == user.id
    ).first()
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return workflow


def _name_taken(db: Session, user: User, name: str, exclude_id: UUID = None) -> bool:
    q = db.query(Workflow).filter(Workflow.user_id == user.id, Workflow.name == name)
    if exclude_id is not None:
        q = q.filter(Workflow.id != exclude_id)
    return q.first() is not None


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str, ensure_ascii=False)}\n\n"


# ============= CRUD =============

@router.get("/", response_model=List[WorkflowListResponse])
async def list_workflows(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflows = db.query(Workflow).filter(
        Workflow.user_id == current_user.id
    ).order_by(Workflow.updated_at.desc()).all()

    return [
        WorkflowListResponse(
            id=w.id,
            name=w.name,
            description=w.description,
            node_count=len((w.definition or {}).get("nodes") or []),
            created_at=w.created_at,
            updated_at=w.updated_at,
        )
        for w in workflows
    ]


@router.post("/", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    data: WorkflowCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if _name_taken(db, current_user, data.name):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Workflow '{data.name}' already exists")

    now = datetime.utcnow()
    workflow = Workflow(
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        definition=data.definition.model_dump(mode="json", exclude_unset=True),
        created_at=now,
        updated_at=now,
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    logger.info(f"Workflow created: {workflow.name} by user {current_user.id}")
    return workflow


# Déclaré avant /{workflow_id} : chemins à deux segments, aucune ambiguïté mais lisibilité
@router.get("/runs/{run_id}", response_model=WorkflowRunResponse)
async def get_workflow_run(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = db.query(WorkflowRun).filter(
        WorkflowRun.id == run_id, WorkflowRun.user_id == current_user.id
    ).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_owned(db, workflow_id, current_user)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: UUID,
    data: WorkflowUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = _get_owned(db, workflow_id, current_user)

    if data.name is not None and data.name != workflow.name and _name_taken(db, current_user, data.name, workflow.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Workflow '{data.name}' already exists")

    fields = data.model_fields_set
    if "name" in fields and data.name is not None:
        workflow.name = data.name
    if "description" in fields:
        workflow.description = data.description
    if "definition" in fields and data.definition is not None:
        # réaffectation complète (mutation JSON non détectée par SQLAlchemy)
        workflow.definition = data.definition.model_dump(mode="json", exclude_unset=True)
    workflow.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(workflow)
    logger.info(f"Workflow updated: {workflow.name} by user {current_user.id}")
    return workflow


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = _get_owned(db, workflow_id, current_user)
    logger.info(f"Workflow deleted: {workflow.name} by user {current_user.id}")
    db.delete(workflow)
    db.commit()
    return None


# ============= HISTORIQUE =============

@router.get("/{workflow_id}/runs", response_model=List[WorkflowRunListResponse])
async def list_workflow_runs(
    workflow_id: UUID,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = _get_owned(db, workflow_id, current_user)
    return db.query(WorkflowRun).filter(
        WorkflowRun.workflow_id == workflow.id
    ).order_by(WorkflowRun.started_at.desc()).limit(min(max(limit, 1), 200)).all()


# ============= EXÉCUTION (SSE) =============

@router.post("/{workflow_id}/execute/stream")
async def execute_workflow_stream(
    workflow_id: UUID,
    execution_data: WorkflowExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Exécute le DAG d'agents ; événements : init | log | progress | node_status | result | error | done
    (node_id dans le payload pour ceux qui concernent un node)."""
    workflow = _get_owned(db, workflow_id, current_user)

    # Validation stricte AVANT le flux : erreur JSON 400 lisible par le frontend (detail)
    try:
        plan = workflow_service.validate_for_execution(db, current_user.id, workflow.definition or {})
    except workflow_service.WorkflowValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="; ".join(exc.errors))

    user_id = current_user.id
    input_data = dict(execution_data.input_data or {})
    trigger = execution_data.trigger

    async def event_generator():
        try:
            async for event, payload in workflow_service.run_workflow(
                db, user_id, workflow, plan, input_data, trigger
            ):
                yield _sse(event, payload)
        except Exception as e:  # filet de sécurité : le moteur gère déjà ses erreurs
            logger.error(f"Workflow stream failed: {e}")
            yield _sse("error", {"error": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
