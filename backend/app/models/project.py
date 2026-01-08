from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.database import Base

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    embedding_model = Column(String(100), default="all-MiniLM-L6-v2", nullable=False)
    chunk_size = Column(Integer, default=2000, nullable=False)
    chunk_overlap = Column(Integer, default=200, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="projects")
    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    rag_conversations = relationship("RAGConversation", back_populates="project", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Project {self.name}>"


class Document(Base):
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_type = Column(String(50), nullable=False)  # pdf, docx, txt, etc.
    file_size = Column(Integer, nullable=False)  # bytes
    chunk_count = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)
    status = Column(String(50), default="processing", nullable=False)  # processing, completed, failed
    error_message = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    
    # Relationships
    project = relationship("Project", back_populates="documents")
    
    def __repr__(self):
        return f"<Document {self.filename}>"


class RAGConversation(Base):
    __tablename__ = "rag_conversations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False, default="New RAG Chat")
    provider_name = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    temperature = Column(Float, default=0.7, nullable=False)
    top_k = Column(Integer, default=5, nullable=False)  # Nombre de chunks à récupérer
    reasoning_mode = Column(String(20), default="standard", nullable=False)  # standard, cot, deep
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    project = relationship("Project", back_populates="rag_conversations")
    user = relationship("User", back_populates="rag_conversations")
    messages = relationship("RAGMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="RAGMessage.created_at")
    
    def __repr__(self):
        return f"<RAGConversation {self.title[:30]}>"


class RAGMessage(Base):
    __tablename__ = "rag_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("rag_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    reasoning_content = Column(Text, nullable=True)  # For Chain of Thought
    retrieved_chunks = Column(Text, nullable=True)  # JSON des chunks utilisés
    tokens_used = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    conversation = relationship("RAGConversation", back_populates="messages")
    
    def __repr__(self):
        return f"<RAGMessage {self.role} ({self.created_at})>"
    
