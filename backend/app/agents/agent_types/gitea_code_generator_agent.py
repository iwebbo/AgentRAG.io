"""
GiteaCodeGeneratorAgent — Agent de génération de code pour Gitea self-hosted.

Hérite de CodeGeneratorAgent (même workflow complet) :
  1. Clone le repo via GiteaMCPServer
  2. Analyse l'arborescence + RAG embed
  3. LLM génère le code
  4. Lint/format via LinterMCP
  5. Commit & push sur branche feature
  6. Crée PR (optionnel)

Seule différence vs CodeGeneratorAgent : mcp_server_name = "gitea"
et config mcp_config["gitea"] au lieu de mcp_config["github"].

Config agent attendue :
{
    "mcp_servers": ["gitea", "linter"],
    "llm_provider": "ollama",
    "llm_model":    "codestral:22b",
    "llm_temperature": 0.2,
    "target_branch": "ai-feature",
    "base_branch":   "main",
    "auto_test":     false,
    "auto_lint":     true,
    "auto_commit":   true,
    "auto_create_pr": false
}

mcp_config attendu :
{
    "gitea": {
        "url":   "http://192.168.1.10:3000",
        "token": "your_gitea_token",
        "repo":  "owner/repo"
    }
}

Input data (identique à CodeGeneratorAgent) :
{
    "prompt": "Add OAuth2 authentication with JWT tokens",
    "create_new_files": true,
    "test_mode": false
}
"""
from typing import Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session

from app.agents.agent_types.code_generator_agent import CodeGeneratorAgent


class GiteaCodeGeneratorAgent(CodeGeneratorAgent):
    """
    Agent code generator pour Gitea self-hosted.

    Réutilise 100 % du workflow de CodeGeneratorAgent.
    Seule surcharge : résolution du repo et du MCP server depuis "gitea" au lieu de "github".
    """

    # Nom du MCP server à utiliser (lu par les appels call_mcp dans CodeGeneratorAgent)
    MCP_SERVER_NAME = "gitea"

    def __init__(
        self,
        agent_id: UUID,
        user_id: UUID,
        config: Dict[str, Any],
        mcp_config: Dict[str, Any],
        db: Session,
    ):
        # ── Fix 1 : injecter repo dans config avant super().__init__() ────────
        # CodeGeneratorAgent ligne 79 : config.get("repo") OR mcp_config["github"]["repo"]
        # On s'assure que les deux sources sont disponibles.
        gitea_cfg = mcp_config.get("gitea", {})
 
        if not config.get("repo") and gitea_cfg.get("repo"):
            config = {**config, "repo": gitea_cfg["repo"]}
 
        # ── Fix 2 : alias mcp_config["github"] → mcp_config["gitea"] ─────────
        # Fallback défensif pour le raise ValueError ligne 99 de CodeGeneratorAgent
        if "gitea" in mcp_config and "github" not in mcp_config:
            mcp_config = {**mcp_config, "github": gitea_cfg}
 
        super().__init__(agent_id, user_id, config, mcp_config, db)
 
        # ── Fix 3 : corriger mcp_servers après super().__init__() ────────────
        # BaseAgent.__init__ lit config["mcp_servers"] → peut contenir "github"
        self.mcp_servers = [
            "gitea" if s == "github" else s
            for s in self.mcp_servers
        ]
 
    async def call_mcp(self, server: str, method: str, params: Dict[str, Any]) -> Any:
        """Redirige tous les appels MCP 'github' → 'gitea'."""
        if server == "github":
            server = "gitea"
        return await super().call_mcp(server, method, params)
