class AgentExecution(Base):
    __tablename__ = "agent_executions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    
    # Execution metadata
    status = Column(String(20))  # pending, running, success, failed
    trigger = Column(String(50))  # manual, scheduled, webhook
    
    # Execution data
    input_data = Column(JSON)
    output_data = Column(JSON)
    logs = Column(JSON, default=[])
    """
    [
      {"timestamp": "...", "level": "info", "message": "Starting task..."},
      {"timestamp": "...", "level": "debug", "message": "Calling MCP github..."},
    ]
    """
    
    # Metrics
    tokens_used = Column(Integer, default=0)
    execution_time_ms = Column(Integer)
    mcp_calls = Column(JSON, default={})  # Tracking des appels MCP
    
    # Relationships
    agent = relationship("Agent", back_populates="executions")
    
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))