from sqlalchemy import Column, String, Text, JSON, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.database import Base


class Agent(Base):
    """Agent autonome avec config MCP et workflow"""
    __tablename__ = "agents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Metadata
    name = Column(String(255), nullable=False)
    description = Column(Text)
    agent_type = Column(String(50), nullable=False)  # web_search, code_review, etc.
    
    # Configuration
    config = Column(JSON, default={})
    """
    Structure config:
    {
        "project_id": "uuid",           # RAG Project ID (optional)
        "mcp_servers": ["github", "slack"],  # MCP servers enabled
        "workflow": {                   # Workflow definition
            "steps": [...],
            "conditions": [...]
        },
        "timeout_seconds": 300,
        "max_retries": 3
    }
    """
    
    # MCP Configuration (encrypted credentials)
    mcp_config = Column(JSON, default={})
    """
    Structure mcp_config:
    {
        "github": {
            "token": "encrypted_token",
            "repo": "user/repo",
            "branch": "main"
        },
        "jira": {
            "url": "https://...",
            "token": "encrypted_token",
            "project_key": "PROJ"
        },
        "slack": {
            "token": "encrypted_token",
            "channel": "#general"
        }
    }
    """
    
    # Status
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # Pour ordre d'exécution
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    executions = relationship(
        "AgentExecution", 
        back_populates="agent", 
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    user = relationship("User")
    
    def __repr__(self):
        return f"<Agent {self.name} ({self.agent_type})>"

class AgentExecution(Base):
    """Historique d'exécution d'un agent"""
    __tablename__ = "agent_executions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    
    # Execution metadata
    status = Column(String(20), nullable=False, default="pending")
    # Status values: pending, running, success, failed, timeout
    
    trigger = Column(String(50), default="manual")
    # Trigger values: manual, scheduled, webhook, api
    
    # Execution data
    input_data = Column(JSON, default={})
    """
    Input data passé à l'agent:
    {
        "query": "...",
        "params": {...},
        "context": {...}
    }
    """
    
    output_data = Column(JSON)
    """
    Résultat de l'exécution:
    {
        "status": "success",
        "result": {...},
        "artifacts": [...]
    }
    """
    
    logs = Column(JSON, default=[])
    """
    Logs structurés de l'exécution:
    [
        {"timestamp": "...", "level": "info", "message": "..."},
        {"timestamp": "...", "level": "debug", "message": "..."}
    ]
    """
    
    # Metrics
    tokens_used = Column(Integer, default=0)
    execution_time_ms = Column(Integer)
    
    mcp_calls = Column(JSON, default={})
    """
    Tracking des appels MCP:
    {
        "github": {"count": 3, "time_ms": 450},
        "slack": {"count": 1, "time_ms": 120}
    }
    """
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime)
    
    # Relationships
    agent = relationship("Agent", back_populates="executions")
    
    def __repr__(self):
        return f"<AgentExecution {self.id} ({self.status})>"
    
class EmailAgentConfig(BaseModel):
    """Configuration agent email"""
    
    # Credentials IMAP/SMTP
    email: EmailStr
    password: str  # Mot de passe application
    
    # Config IMAP (réception)
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    
    # Config SMTP (envoi)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    
    # Paramètres agent
    auto_categorize: bool = True
    auto_reply_enabled: bool = False
    signature: Optional[str] = None
    
    # Style réponse
    default_tone: str = "professional"  # professional|friendly|formal
    language: str = "fr"