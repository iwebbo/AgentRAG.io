"""
AgentExecutor v3 — db + user_id injectés dans les MCP servers

Changement vs v2 :
  - _register_mcp_servers() passe db + user_id aux servers qui en ont besoin
  - SSHMCPServer et WinRMMCPServer reçoivent db/user_id au lieu de credentials
  - Les autres MCP (github, linter, test_runner) gardent leur config habituelle
"""
from typing import Dict, Any, AsyncGenerator, Type
from uuid import UUID
from sqlalchemy.orm import Session
from datetime import datetime
import logging
import time

from app.models.agent import Agent, AgentExecution
from app.mcp.mcp_client import MCPClient

# ── MCP imports ───────────────────────────────────────────────────────────────
from app.mcp.servers.github_server import GitHubMCPServer
from app.mcp.servers.test_runner_server import TestRunnerMCP
from app.mcp.servers.linter_server import LinterMCP
from app.mcp.servers.ssh_server import SSHMCPServer
from app.mcp.servers.winrm_server import WinRMMCPServer
from app.mcp.servers.gitea_server import GiteaMCPServer
from app.mcp.servers.datagouv_server import DataGouvMCPServer

# ── Agent imports ─────────────────────────────────────────────────────────────
from app.agents.agent_types.branch_code_review_agent import BranchCodeReviewAgent
from app.agents.agent_types.code_generator_agent import CodeGeneratorAgent
from app.agents.agent_types.legal_advisor_agent import LegalAdvisorAgent
from app.agents.agent_types.accounting_advisor_agent import AccountingAdvisorAgent
from app.agents.agent_types.travel_agent import TravelAdvisorAgent
from app.agents.agent_types.email_agent import EmailAgent
from app.agents.agent_types.websearch_agent import WebSearchAgent
from app.agents.agent_types.skill_agent import SkillAgent
from app.agents.agent_types.gitea_code_generator_agent import GiteaCodeGeneratorAgent
from app.agents.agent_types.datagouv_agent import DataGouvAgent
from app.agents.agent_types.ansible_role_generator_agent import AnsibleRoleGeneratorAgent
from app.agents.agent_types.gitea_ansible_role_generator_agent import GiteaAnsibleRoleGeneratorAgent


logger = logging.getLogger(__name__)


# ── MCP servers qui ont besoin de db + user_id (credential resolution via DB)
DB_AWARE_MCP_SERVERS = {"ssh", "winrm"}

# ── MCP servers qui utilisent mcp_config classique (token/url dans config)
MCP_REGISTRY: Dict[str, Type] = {
    "github":      GitHubMCPServer,
    "linter":      LinterMCP,
    "test_runner": TestRunnerMCP,
    "ssh":         SSHMCPServer,
    "winrm":       WinRMMCPServer,
    "gitea":       GiteaMCPServer,
    "datagouv":    DataGouvMCPServer,
}


class AgentExecutor:

    AGENT_TYPES: Dict[str, Type] = {
        "branch_code_review":  BranchCodeReviewAgent,
        "code_generator":      CodeGeneratorAgent,
        "legal_fiscal":        LegalAdvisorAgent,
        "accounting_finance":  AccountingAdvisorAgent,
        "travel_expert":       TravelAdvisorAgent,
        "email_expert":        EmailAgent,
        "websearch":           WebSearchAgent,
        "skill":               SkillAgent,
        "gitea_code_generator": GiteaCodeGeneratorAgent,
        "datagouv_explorer":   DataGouvAgent,
        "ansible_role_generator":        AnsibleRoleGeneratorAgent,
        "gitea_ansible_role_generator":  GiteaAnsibleRoleGeneratorAgent,
    }

    def __init__(self, db: Session):
        self.db = db

    async def execute_agent(
        self,
        agent_id: UUID,
        execution_id: UUID,
        input_data: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:

        start_time = time.time()

        agent_record = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent_record:
            raise ValueError(f"Agent {agent_id} not found")

        execution_record = self.db.query(AgentExecution).filter(
            AgentExecution.id == execution_id
        ).first()
        if not execution_record:
            raise ValueError(f"Execution {execution_id} not found")

        execution_record.status = "running"
        self.db.commit()

        try:
            mcp_client = MCPClient(agent_record.mcp_config)
            await self._register_mcp_servers(
                mcp_client=mcp_client,
                mcp_servers=agent_record.config.get("mcp_servers", []),
                mcp_config=agent_record.mcp_config,
                user_id=str(agent_record.user_id),
            )

            agent_class = self.AGENT_TYPES.get(agent_record.agent_type)
            if not agent_class:
                raise ValueError(
                    f"Unknown agent type: '{agent_record.agent_type}'. "
                    f"Available: {list(self.AGENT_TYPES.keys())}"
                )

            agent_instance = agent_class(
                agent_id=agent_record.id,
                user_id=agent_record.user_id,
                config=agent_record.config,
                mcp_config=agent_record.mcp_config,
                db=self.db,
            )
            agent_instance.mcp_client = mcp_client

            if input_data.get("conversation_id"):
                from uuid import UUID as _UUID
                agent_instance.conversation_id = _UUID(input_data["conversation_id"])

            logger.info(
                f"Executing agent '{agent_record.name}' "
                f"(type={agent_record.agent_type}, id={agent_id})"
            )

            final_result = None
            async for update in agent_instance.execute(input_data):
                yield update
                if update.get("type") == "result":
                    final_result = update.get("data")
                execution_record.logs = agent_instance.logs
                self.db.commit()

            execution_time_ms = int((time.time() - start_time) * 1000)
            execution_record.status           = "success"
            execution_record.output_data      = final_result or {}
            execution_record.tokens_used      = agent_instance.tokens_used
            execution_record.execution_time_ms = execution_time_ms
            execution_record.mcp_calls        = agent_instance.mcp_calls_count
            execution_record.completed_at     = datetime.utcnow()
            self.db.commit()

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            execution_record.status           = "failed"
            execution_record.output_data      = {"error": str(e)}
            execution_record.execution_time_ms = execution_time_ms
            execution_record.completed_at     = datetime.utcnow()
            self.db.commit()
            logger.error(f"Agent '{agent_record.name}' failed: {e}")
            raise

    async def _register_mcp_servers(
        self,
        mcp_client: MCPClient,
        mcp_servers: list,
        mcp_config: Dict[str, Any],
        user_id: str,
    ):
        """
        Instancie et enregistre les MCP servers.

        Deux catégories :
        - DB-aware (ssh, winrm) : reçoivent db + user_id, ignorent mcp_config
        - Config-based (github, linter...) : reçoivent leur config via **kwargs
        """
        for server_name in mcp_servers:
            server_class = MCP_REGISTRY.get(server_name)
            if not server_class:
                logger.warning(
                    f"MCP '{server_name}' not in registry — skipping. "
                    f"Add it to MCP_REGISTRY in agent_executor.py"
                )
                continue

            try:
                if server_name in DB_AWARE_MCP_SERVERS:
                    # SSH et WinRM : credentials depuis DB, pas de config en clair
                    server_cfg = mcp_config.get(server_name, {})
                    timeout = server_cfg.get("timeout", 30 if server_name == "ssh" else 60)
                    instance = server_class(
                        db=self.db,
                        user_id=user_id,
                        timeout=timeout,
                    )
                else:
                    # Autres MCP : config passée comme **kwargs
                    server_cfg = mcp_config.get(server_name, {})
                    instance = server_class(**server_cfg)

                mcp_client.register_server(server_name, instance)
                logger.info(f"MCP registered: '{server_name}'")

            except TypeError as e:
                logger.error(
                    f"MCP '{server_name}' instantiation failed "
                    f"(check constructor vs config): {e}"
                )

    @classmethod
    def register_dynamic_agent(cls, agent_type: str, agent_class: Type) -> None:
        cls.AGENT_TYPES[agent_type] = agent_class
        logger.info(f"Dynamic agent registered: '{agent_type}' = {agent_class.__name__}")

    @classmethod
    def list_agent_types(cls) -> Dict[str, str]:
        return {k: v.__name__ for k, v in cls.AGENT_TYPES.items()}