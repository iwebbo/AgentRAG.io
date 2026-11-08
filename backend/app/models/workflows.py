"""
Modèles Workflow : un graphe (DAG) d'agents déterministes existants.

- Workflow     : définition JSON versionnée (contrat v1, voir schemas/workflows.py)
- WorkflowRun  : historique d'une exécution (statut par node, sorties bornées)

Les tables sont créées par init_db() (Base.metadata.create_all) dès que ce module est importé
(il l'est par app.routes.workflows) ; la migration 002_workflows.py couvre le chemin Alembic.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, JSON, DateTime, ForeignKey, UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Workflow(Base):
    __tablename__ = "workflows"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_workflow_user_name"),
        Index("ix_workflows_user_id", "user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    name = Column(String(255), nullable=False)
    description = Column(Text)

    # {version, nodes:[{id,type,agent_id,input,position,ui}], edges:[{source,target}]}
    # Stocké tel quel (ui.values est opaque pour le backend).
    definition = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    runs = relationship(
        "WorkflowRun",
        back_populates="workflow",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self):
        return f"<Workflow {self.name}>"


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        Index("ix_workflow_runs_workflow_id", "workflow_id"),
        Index("ix_workflow_runs_user_id", "user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # running | success | failed | cancelled
    status = Column(String(20), nullable=False, default="running")
    trigger = Column(String(50), default="manual")

    input_data = Column(JSON, default=dict)
    # {node_id: {status, execution_id, output, error}}
    node_results = Column(JSON, default=dict)
    error = Column(Text)

    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime)

    workflow = relationship("Workflow", back_populates="runs")

    def __repr__(self):
        return f"<WorkflowRun {self.id} ({self.status})>"
