from typing import Dict, Any, AsyncGenerator
from uuid import UUID
from sqlalchemy.orm import Session
from datetime import datetime
import logging
import time

from app.models.agent import Agent, AgentExecution
from app.mcp.mcp_client import MCPClient
from app.mcp.servers.github_server import GitHubMCPServer
from app.mcp.servers.test_runner_server import TestRunnerMCP
from app.mcp.servers.linter_server import LinterMCP
from app.agents.agent_types.branch_code_review_agent import BranchCodeReviewAgent
from app.agents.agent_types.code_generator_agent import CodeGeneratorAgent
from app.agents.agent_types.legal_advisor_agent import LegalAdvisorAgent
from app.agents.agent_types.accounting_advisor_agent import AccountingAdvisorAgent
from app.agents.agent_types.travel_agent import TravelAdvisorAgent
from app.agents.agent_types.email_agent import EmailAgent
from app.agents.agent_types.websearch_agent import WebSearchAgent

logger = logging.getLogger(__name__)


class AgentExecutor:
    """
    Orchestrateur d'exécution d'agents.
    
    Responsabilités:
    - Charger l'agent depuis la DB
    - Initialiser le MCP client avec les servers nécessaires
    - Exécuter l'agent
    - Tracker les logs et metrics
    - Sauvegarder les résultats
    """
    
    # Registry des types d'agents
    AGENT_TYPES = {
        "branch_code_review": BranchCodeReviewAgent,
        "code_generator": CodeGeneratorAgent,
        "legal_fiscal": LegalAdvisorAgent,
        "accounting_finance":AccountingAdvisorAgent,
        "travel_expert":TravelAdvisorAgent,
        "email_expert" :EmailAgent,
        "websearch": WebSearchAgent,
        # "web_search": WebSearchAgent,
        # "deploy": DeployAgent,
        # etc.
    }
    
    def __init__(self, db: Session):
        self.db = db
    
    async def execute_agent(
        self,
        agent_id: UUID,
        execution_id: UUID,
        input_data: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Exécute un agent et stream les résultats.
        
        Args:
            agent_id: ID de l'agent
            execution_id: ID de l'execution record
            input_data: Données d'entrée
            
        Yields:
            Updates progressifs de l'exécution
        """
        start_time = time.time()
        
        # Load agent from DB
        agent_record = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent_record:
            raise ValueError(f"Agent {agent_id} not found")
        
        # Load execution record
        execution_record = self.db.query(AgentExecution).filter(
            AgentExecution.id == execution_id
        ).first()
        if not execution_record:
            raise ValueError(f"Execution {execution_id} not found")
        
        # Update status to running
        execution_record.status = "running"
        self.db.commit()
        
        try:
            # Initialize MCP client
            mcp_client = MCPClient(agent_record.mcp_config)
            
            # Register MCP servers based on agent config
            await self._register_mcp_servers(
                mcp_client,
                agent_record.config.get("mcp_servers", []),
                agent_record.mcp_config
            )
            
            # Get agent class
            agent_class = self.AGENT_TYPES.get(agent_record.agent_type)
            if not agent_class:
                raise ValueError(f"Unknown agent type: {agent_record.agent_type}")
            
            # Instantiate agent
            agent_instance = agent_class(
                agent_id=agent_record.id,
                user_id=agent_record.user_id,
                config=agent_record.config,
                mcp_config=agent_record.mcp_config,
                db=self.db
            )
            
            # Set MCP client
            agent_instance.mcp_client = mcp_client
            
            logger.info(f"Executing agent {agent_record.name} (type: {agent_record.agent_type})")
            
            # Execute agent and stream results
            final_result = None
            
            async for update in agent_instance.execute(input_data):
                # Forward update to caller
                yield update
                
                # Capture final result
                if update.get("type") == "result":
                    final_result = update.get("data")
                
                # Update execution logs in real-time
                execution_record.logs = agent_instance.logs
                self.db.commit()
            
            # Calculate execution time
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            # Update execution record with success
            execution_record.status = "success"
            execution_record.output_data = final_result or {}
            execution_record.tokens_used = agent_instance.tokens_used
            execution_record.execution_time_ms = execution_time_ms
            execution_record.mcp_calls = agent_instance.mcp_calls_count
            execution_record.completed_at = datetime.utcnow()
            
            self.db.commit()
            
            logger.info(
                f"Agent {agent_record.name} completed successfully in {execution_time_ms}ms"
            )
            
        except Exception as e:
            # Calculate execution time even on failure
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            # Update execution record with failure
            execution_record.status = "failed"
            execution_record.output_data = {"error": str(e)}
            execution_record.execution_time_ms = execution_time_ms
            execution_record.completed_at = datetime.utcnow()
            
            self.db.commit()
            
            logger.error(f"Agent {agent_record.name} failed: {str(e)}")
            
            # Re-raise to let caller handle
            raise
    
    async def _register_mcp_servers(
        self,
        mcp_client: MCPClient,
        mcp_servers: list,
        mcp_config: Dict[str, Any]
    ):
        """
        Enregistre les MCP servers nécessaires.
        
        Args:
            mcp_client: Instance du MCP client
            mcp_servers: Liste des servers à activer ["github", "jira", ...]
            mcp_config: Configuration des servers
        """
        for server_name in mcp_servers:
            if server_name == "github":
                github_config = mcp_config.get("github", {})
                token = github_config.get("token")
                repo = github_config.get("repo")
                
                if not token:
                    logger.warning("GitHub server enabled but no token provided")
                    continue
                
                github_server = GitHubMCPServer(token=token, repo=repo)
                mcp_client.register_server("github", github_server)
                
                logger.info(f"Registered MCP server: github (repo: {repo})")
            
            elif server_name == "test_runner":
                test_runner = TestRunnerMCP()
                mcp_client.register_server("test_runner", test_runner)
                logger.info("Registered MCP server: test_runner")
            
            elif server_name == "linter":
                linter = LinterMCP()
                mcp_client.register_server("linter", linter)
                logger.info("Registered MCP server: linter")
            
            else:
                logger.warning(f"Unknown MCP server: {server_name}")