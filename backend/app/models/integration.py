"""Integration model - Store Git/Drive configs per project."""
from sqlalchemy import Column, String, JSON, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from app.database import Base

class Integration(Base):
    """External integrations (Git, Google Drive) per project."""
    __tablename__ = "integrations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    
    # Type: 'git' or 'gdrive'
    type = Column(String(50), nullable=False)
    
    # Unique name for this integration
    name = Column(String(255), nullable=False)
    
    # Configuration as JSON
    config = Column(JSON, nullable=False)
    # For Git: {"url": "...", "branch": "main", "token": "...", "patterns": [...]}
    # For GDrive: {"folder_id": "...", "service_account": {...}}
    
    # Status
    enabled = Column(Boolean, default=True)
    last_sync = Column(DateTime, nullable=True)
    status = Column(String(50), default='active')  # active, error, disabled
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Pas de relationship pour éviter l'erreur avec Project
    # On accède aux integrations via query directe
    
    def __repr__(self):
        return f"<Integration {self.type}:{self.name} for project {self.project_id}>"