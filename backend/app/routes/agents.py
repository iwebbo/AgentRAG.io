from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from uuid import UUID
from datetime import datetime
import logging

from app.database import get_db
from app.models import User
from app.models.agent import Agent, AgentExecution
from app.dependencies import get_current_user
from app.schemas.agent import (
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentListResponse,
    AgentExecutionCreate,
    AgentExecutionResponse,
    AgentExecutionListResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["Agents"])


# ============= AGENT CRUD =============

@router.get("/", response_model=List[AgentListResponse])
async def list_agents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Liste tous les agents de l'utilisateur"""
    agents = db.query(Agent).filter(
        Agent.user_id == current_user.id
    ).order_by(
        Agent.updated_at.desc()
    ).all()
    
    # Ajouter le nombre d'exÃ©cutions
    result = []
    for agent in agents:
        execution_count = db.query(AgentExecution).filter(
            AgentExecution.agent_id == agent.id
        ).count()
        
        result.append(AgentListResponse(
            id=agent.id,
            name=agent.name,
            description=agent.description,
            agent_type=agent.agent_type,
            is_active=agent.is_active,
            execution_count=execution_count,
            created_at=agent.created_at,
            updated_at=agent.updated_at
        ))
    
    return result


@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_data: AgentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crée un nouveau agent"""
    
    # Vérifier si nom existe déjà
    existing = db.query(Agent).filter(
        Agent.user_id == current_user.id,
        Agent.name == agent_data.name
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Agent '{agent_data.name}' already exists"
        )
    
    # ✅ Si legal_fiscal SANS project_id → Créer project avec embedding juridique
    if agent_data.agent_type == "legal_fiscal" and not agent_data.config.get("project_id"):
        from app.models import Project
        from datetime import datetime
        
        # Extraire domain ou utiliser "fiscal" par défaut
        legal_config = agent_data.config.get("legal_config", {})
        domain = legal_config.get("domain", "fiscal")
        
        # Créer project dédié avec embedding juridique
        project_name = f"Agent{domain}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        project = Project(
            user_id=current_user.id,
            name=project_name,
            description=f"Auto-generated RAG for - {domain}",
            embedding_model="sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
            chunk_size=800,
            chunk_overlap=100
        )
        
        db.add(project)
        db.commit()
        db.refresh(project)
        
        # Ajouter project_id dans config agent
        agent_data.config["project_id"] = str(project.id)
        
        logger.info(f"✅ Created legal project: {project_name} (ID: {project.id}) for agent {agent_data.name}")
    
    agent = Agent(
        user_id=current_user.id,
        **agent_data.model_dump()
    )
    
    db.add(agent)
    db.commit()
    db.refresh(agent)
    
    logger.info(f"Agent created: {agent.name} ({agent.agent_type}) by user {current_user.id}")
    
    # Add execution_count for response
    response = AgentResponse.model_validate(agent)
    response.execution_count = 0
    
    return response


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """RÃ©cupÃ¨re un agent avec ses dÃ©tails"""
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    # Add execution count
    execution_count = db.query(AgentExecution).filter(
        AgentExecution.agent_id == agent_id
    ).count()
    
    response = AgentResponse.model_validate(agent)
    response.execution_count = execution_count
    
    return response


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: UUID,
    agent_update: AgentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Met Ã  jour un agent"""
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    update_data = agent_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(agent, field, value)
    
    agent.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(agent)
    
    logger.info(f"Agent updated: {agent.name} by user {current_user.id}")
    
    execution_count = db.query(AgentExecution).filter(
        AgentExecution.agent_id == agent_id
    ).count()
    
    response = AgentResponse.model_validate(agent)
    response.execution_count = execution_count
    
    return response


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Supprime un agent et tout son historique"""
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    logger.info(f"Agent deleted: {agent.name} by user {current_user.id}")
    
    db.delete(agent)
    db.commit()
    
    return None


@router.patch("/{agent_id}/toggle", response_model=AgentResponse)
async def toggle_agent_status(
    agent_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Toggle le statut actif/inactif d'un agent"""
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    agent.is_active = not agent.is_active
    agent.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(agent)
    
    logger.info(f"Agent status toggled: {agent.name} -> {agent.is_active}")
    
    execution_count = db.query(AgentExecution).filter(
        AgentExecution.agent_id == agent_id
    ).count()
    
    response = AgentResponse.model_validate(agent)
    response.execution_count = execution_count
    
    return response


# ============= AGENT EXECUTION =============

@router.post("/{agent_id}/execute", response_model=AgentExecutionResponse)
async def execute_agent(
    agent_id: UUID,
    execution_data: AgentExecutionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """ExÃ©cute un agent avec input_data"""
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    if not agent.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agent is not active"
        )
    
    # CrÃ©er l'execution record
    execution = AgentExecution(
        agent_id=agent_id,
        status="pending",
        trigger=execution_data.trigger,
        input_data=execution_data.input_data,
        started_at=datetime.utcnow()
    )
    
    db.add(execution)
    db.commit()
    db.refresh(execution)
    
    logger.info(f"Agent execution started: {agent.name} (execution_id: {execution.id})")
    
    # Execute agent in background (for now, synchronously)
    # TODO: Move to background task with Celery/RQ for production
    from app.agents.agent_executor import AgentExecutor
    
    executor = AgentExecutor(db)
    
    try:
        # Execute and consume all updates
        async for update in executor.execute_agent(
            agent_id=agent_id,
            execution_id=execution.id,
            input_data=execution_data.input_data
        ):
            # For now, just log updates
            # In production, these would be sent via WebSocket
            logger.debug(f"Execution update: {update.get('type')}")
        
        # Refresh execution to get final state
        db.refresh(execution)
        
    except Exception as e:
        logger.error(f"Agent execution failed: {str(e)}")
        # Execution status is already updated by executor
        db.refresh(execution)
    
    return execution


@router.get("/{agent_id}/executions", response_model=List[AgentExecutionListResponse])
async def list_agent_executions(
    agent_id: UUID,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Liste les exÃ©cutions d'un agent"""
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    executions = db.query(AgentExecution).filter(
        AgentExecution.agent_id == agent_id
    ).order_by(
        AgentExecution.started_at.desc()
    ).limit(limit).all()
    
    return executions


@router.get("/executions/{execution_id}", response_model=AgentExecutionResponse)
async def get_execution(
    execution_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """RÃ©cupÃ¨re les dÃ©tails d'une exÃ©cution"""
    execution = db.query(AgentExecution).join(Agent).filter(
        AgentExecution.id == execution_id,
        Agent.user_id == current_user.id
    ).first()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found"
        )
    
    return execution


@router.get("/{agent_id}/stats")
async def get_agent_stats(
    agent_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Statistiques d'un agent"""
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Stats executions
    total_executions = db.query(AgentExecution).filter(
        AgentExecution.agent_id == agent_id
    ).count()
    
    success_count = db.query(AgentExecution).filter(
        AgentExecution.agent_id == agent_id,
        AgentExecution.status == "success"
    ).count()
    
    failed_count = db.query(AgentExecution).filter(
        AgentExecution.agent_id == agent_id,
        AgentExecution.status == "failed"
    ).count()
    
    avg_execution_time = db.query(
        func.avg(AgentExecution.execution_time_ms)
    ).filter(
        AgentExecution.agent_id == agent_id,
        AgentExecution.execution_time_ms.isnot(None)
    ).scalar() or 0
    
    total_tokens = db.query(
        func.sum(AgentExecution.tokens_used)
    ).filter(
        AgentExecution.agent_id == agent_id
    ).scalar() or 0
    
    return {
        "agent_id": agent_id,
        "name": agent.name,
        "agent_type": agent.agent_type,
        "is_active": agent.is_active,
        "total_executions": total_executions,
        "success_count": success_count,
        "failed_count": failed_count,
        "success_rate": (success_count / total_executions * 100) if total_executions > 0 else 0,
        "avg_execution_time_ms": int(avg_execution_time),
        "total_tokens_used": total_tokens
    }