"""
GiteaAnsibleRoleGeneratorAgent — Scaffolding de rôles Ansible pour Gitea self-hosted.

Hérite de AnsibleRoleGeneratorAgent (même workflow complet, mêmes conventions Ansible).
Seule différence vs AnsibleRoleGeneratorAgent : mcp_server_name = "gitea"
et config mcp_config["gitea"] au lieu de mcp_config["github"].

Pattern identique à GiteaCodeGeneratorAgent (3 fixes), pour rester cohérent
avec l'existant plutôt que de paramétrer une classe unique multi-provider.

Config agent attendue :
{
    "mcp_servers": ["gitea", "linter"],
    "llm_provider": "ollama",
    "llm_model":    "codestral:22b",
    "llm_temperature": 0.2,
    "base_branch":   "main",
    "auto_lint":     true,
    "auto_commit":   true,
    "auto_create_pr": false,
    "roles_path":    "roles"
}

mcp_config attendu :
{
    "gitea": {
        "url":   "http://192.168.1.10:3000",
        "token": "your_gitea_token",
        "repo":  "owner/ansible-repo"
    }
}

Input data : identique à AnsibleRoleGeneratorAgent.
"""
from typing import Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session

from app.agents.agent_types.ansible_role_generator_agent import AnsibleRoleGeneratorAgent


class GiteaAnsibleRoleGeneratorAgent(AnsibleRoleGeneratorAgent):
    """
    Agent de scaffolding de rôles Ansible pour Gitea self-hosted.

    Réutilise 100% du workflow de AnsibleRoleGeneratorAgent.
    Seule surcharge : résolution du repo et du MCP server depuis "gitea" au lieu de "github".
    """

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
        gitea_cfg = mcp_config.get("gitea", {})

        if not config.get("repo") and gitea_cfg.get("repo"):
            config = {**config, "repo": gitea_cfg["repo"]}

        # ── Fix 2 : alias mcp_config["github"] → mcp_config["gitea"] ─────────
        if "gitea" in mcp_config and "github" not in mcp_config:
            mcp_config = {**mcp_config, "github": gitea_cfg}

        super().__init__(agent_id, user_id, config, mcp_config, db)

        # ── Fix 3 : corriger mcp_servers après super().__init__() ────────────
        self.mcp_servers = [
            "gitea" if s == "github" else s
            for s in self.mcp_servers
        ]

    async def call_mcp(self, server: str, method: str, params: Dict[str, Any]) -> Any:
        """Redirige tous les appels MCP 'github' → 'gitea'."""
        if server == "github":
            server = "gitea"
        return await super().call_mcp(server, method, params)