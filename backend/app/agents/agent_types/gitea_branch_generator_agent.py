"""
GiteaBranchGeneratorAgent — équivalent Gitea (self-hosted) de GitHubBranchGeneratorAgent.

Même workflow (génération LLM dans /tmp → create_branch → clone → commit_and_push
→ create_pull_request optionnel), mais via le MCP "gitea".

Config agent attendue :
{
    "mcp_servers": ["gitea"],
    "base_branch": "main",
    "auto_create_pr": false,
    "max_files": 40,
    "max_tokens": 8000,
    "llm_provider": "lmstudio",
    "llm_model": "openai/gpt-oss-20b",
    "llm_temperature": 0.2
}

mcp_config attendu (clés EXACTES du constructeur GiteaMCPServer) :
{
    "gitea": { "url": "https://gitea.example.com", "token": "...", "repo": "owner/repo" }
}

Input data : identique à GitHubBranchGeneratorAgent
(prompt, branch, base_branch, repo, commit_message, pr_title, create_pr, context, dry_run).
"""
from app.agents.agent_types.github_branch_generator_agent import GitHubBranchGeneratorAgent


class GiteaBranchGeneratorAgent(GitHubBranchGeneratorAgent):
    """Génère des fichiers via LLM, les pousse sur une nouvelle branche, PR optionnelle (Gitea)."""

    MCP_SERVER = "gitea"
    PROVIDER_LABEL = "Gitea"

    def _web_base(self) -> str:
        url = str(((self.mcp_config or {}).get("gitea") or {}).get("url") or "").strip()
        return url.rstrip("/")
