from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_NODES = 100


class WorkflowNode(BaseModel):
    """Node de la définition. Les clés inconnues (ui, ...) sont conservées telles quelles."""
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1, max_length=64)
    type: str = "agent"
    agent_id: Optional[str] = None  # null autorisé : brouillon (l'exécution l'exige)
    input: Dict[str, Any] = Field(default_factory=dict)
    position: Optional[Dict[str, Any]] = None
    ui: Optional[Dict[str, Any]] = None

    @field_validator("agent_id", mode="before")
    @classmethod
    def _agent_id_uuid_or_none(cls, v):
        if v is None or v == "":
            return None
        try:
            return str(UUID(str(v)))
        except ValueError:
            raise ValueError("agent_id must be a UUID")


class WorkflowEdge(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)


class WorkflowDefinition(BaseModel):
    """Contrat v1. Validation structurelle uniquement (brouillons acceptés) ;
    la validation stricte (agents, DAG, références) est faite à l'exécution."""
    model_config = ConfigDict(extra="allow")

    version: int = 1
    nodes: List[WorkflowNode] = Field(default_factory=list)
    edges: List[WorkflowEdge] = Field(default_factory=list)

    @model_validator(mode="after")
    def _structure(self):
        if self.version != 1:
            raise ValueError(f"Unsupported definition version: {self.version}")
        if len(self.nodes) > MAX_NODES:
            raise ValueError(f"Too many nodes (max {MAX_NODES})")
        ids = [n.id for n in self.nodes]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate node ids")
        known = set(ids)
        for e in self.edges:
            if e.source not in known or e.target not in known:
                raise ValueError(f"Edge {e.source} -> {e.target} references an unknown node")
            if e.source == e.target:
                raise ValueError(f"Edge {e.source} -> {e.target} is a self-loop")
        return self


class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    definition: WorkflowDefinition = Field(default_factory=WorkflowDefinition)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


class WorkflowUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    definition: Optional[WorkflowDefinition] = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v):
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


class WorkflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    name: str
    description: Optional[str] = None
    definition: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime] = None


class WorkflowListResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    node_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None


class WorkflowExecuteRequest(BaseModel):
    input_data: Dict[str, Any] = Field(default_factory=dict)
    trigger: str = "manual"


class WorkflowRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_id: UUID
    status: str
    trigger: Optional[str] = None
    input_data: Dict[str, Any] = Field(default_factory=dict)
    node_results: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


class WorkflowRunListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_id: UUID
    status: str
    trigger: Optional[str] = None
    input_data: Dict[str, Any] = Field(default_factory=dict)
    started_at: datetime
    completed_at: Optional[datetime] = None
