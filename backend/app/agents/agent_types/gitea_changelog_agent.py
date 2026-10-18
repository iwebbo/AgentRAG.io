"""
GiteaChangelogAgent — génère le CHANGELOG.md d'une Pull Request et le pousse
sur la branche source de cette PR (Gitea self-hosted).

Hérite de GitHubChangelogAgent (même workflow complet). Seule différence :
le MCP server appelé est "gitea" (GiteaMCPServer) au lieu de "github".
Les payloads PR / commits / fichiers de l'API Gitea ont la même forme que ceux
de GitHub pour les champs utilisés (number, title, base.ref, head.ref,
head.repo.full_name, commit.message, filename, status, additions, deletions).

Config agent attendue :
{
    "mcp_servers": ["gitea"],
    "base_branch": "main",
    "pr_state": "open",
    "changelog_path": "CHANGELOG.md",
    "use_llm": true,
    "language": "en",
    "skip_ci": false,
    "llm_provider": "lmstudio",
    "llm_model": "openai/gpt-oss-20b",
    "llm_temperature": 0.2
}

mcp_config attendu (clés EXACTES du constructeur GiteaMCPServer — toute autre
clé fait échouer l'instanciation et le serveur n'est pas enregistré) :
{
    "gitea": {
        "url":   "http://gitea.example.local:3000",
        "token": "your_gitea_token",
        "repo":  "owner/repo"
    }
}

Input data :
{
    "version": "v1.1.78",
    "pr_number": 42,        # optionnel
    "dry_run": false        # optionnel
}
"""
from app.agents.agent_types.github_changelog_agent import GitHubChangelogAgent


class GiteaChangelogAgent(GitHubChangelogAgent):
    """Agent changelog pour Gitea self-hosted (réutilise 100 % du workflow GitHub)."""

    MCP_SERVER = "gitea"
    PROVIDER_LABEL = "Gitea"