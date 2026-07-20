"""
AnsibleRoleGeneratorAgent — Scaffolding de rôles Ansible via MCP Git (GitHub/Gitea).
Config agent attendue (identique à CodeGeneratorAgent) :
{
    "mcp_servers": ["github", "linter"],
    "llm_provider": "ollama",
    "llm_model":    "codestral:22b",
    "llm_temperature": 0.2,
    "target_branch": "ai-ansible-role",   // optionnel, sinon dérivé du role_name
    "base_branch":   "main",
    "auto_lint":     true,
    "auto_commit":   true,
    "auto_create_pr": false,
    "roles_path":    "roles"              // racine où créer le rôle dans le repo
}

mcp_config attendu :
{
    "github": {
        "token": "ghp_...",
        "repo":  "owner/ansible-repo"
    }
}

Input data :
{
    "role_name": "nginx_hardening",
    "description": "Rôle Ansible pour durcir nginx (TLS, headers sécurité, fail2ban)",
    "variables": {"nginx_version": "1.25", "enable_fail2ban": true},   // optionnel
    "dependencies": ["geerlingguy.repo-epel"],                        // optionnel, meta/main.yml
    "supported_os": ["Debian", "RedHat"],                             // optionnel
    "commit_message": "feat: add nginx_hardening ansible role",       // optionnel
    "test_mode": false
}
"""
from typing import Dict, Any, AsyncGenerator, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.agents.agent_types.code_generator_agent import CodeGeneratorAgent

ANSIBLE_GALAXY_SKELETON = """\
roles/<role_name>/
├── tasks/main.yml          # Tâches principales (point d'entrée)
├── handlers/main.yml       # Handlers (notify/restart services)
├── defaults/main.yml       # Variables par défaut (faible précédence)
├── vars/main.yml           # Variables internes (haute précédence)
├── meta/main.yml           # Métadonnées + dépendances Galaxy
├── templates/              # Fichiers .j2 (Jinja2) si nécessaire
├── files/                  # Fichiers statiques si nécessaire
└── README.md                # Documentation du rôle (vars, exemple d'usage)
"""


class AnsibleRoleGeneratorAgent(CodeGeneratorAgent):
    """
    Agent de scaffolding de rôles Ansible.

    Réutilise 100% du pipeline de CodeGeneratorAgent.
    Override : construction du prompt + mapping de l'input structuré → prompt texte.
    """

    def __init__(
        self,
        agent_id: UUID,
        user_id: UUID,
        config: Dict[str, Any],
        mcp_config: Dict[str, Any],
        db: Session,
    ):
        super().__init__(agent_id, user_id, config, mcp_config, db)
        self.roles_path = config.get("roles_path", "roles")

    # ═════════════════════════════════════════════════════════════════════
    # ENTRY POINT — mappe l'input structuré vers le contrat CodeGeneratorAgent
    # ═════════════════════════════════════════════════════════════════════

    async def execute(self, input_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        role_name = input_data.get("role_name")
        if not role_name:
            raise ValueError("Missing required field: role_name")

        description = input_data.get("description", "")
        variables: Dict[str, Any] = input_data.get("variables", {})
        dependencies: List[str] = input_data.get("dependencies", [])
        supported_os: List[str] = input_data.get("supported_os", ["Debian", "RedHat"])

        # Dérive la branche cible du nom du rôle si non explicitement configurée
        if "target_branch" not in self.config:
            self.target_branch = f"ansible-role-{role_name}"

        prompt = self._build_role_prompt(
            role_name=role_name,
            description=description,
            variables=variables,
            dependencies=dependencies,
            supported_os=supported_os,
        )

        mapped_input = {
            "prompt": prompt,
            "target_files": [],
            "create_new_files": True,
            "test_mode": input_data.get("test_mode", False),
            "commit_message": input_data.get(
                "commit_message", f"feat: add ansible role '{role_name}'"
            ),
        }

        # Délègue intégralement au pipeline parent (clone/RAG/LLM/lint/commit/PR)
        async for event in super().execute(mapped_input):
            yield event

    # ═════════════════════════════════════════════════════════════════════
    # PROMPT — conventions Ansible Galaxy
    # ═════════════════════════════════════════════════════════════════════

    def _build_role_prompt(
        self,
        role_name: str,
        description: str,
        variables: Dict[str, Any],
        dependencies: List[str],
        supported_os: List[str],
    ) -> str:
        vars_text = "\n".join(f"  - {k}: {v}" for k, v in variables.items()) or "  (aucune, à déduire du besoin)"
        deps_text = "\n".join(f"  - {d}" for d in dependencies) or "  (aucune)"
        os_text = ", ".join(supported_os)

        return f"""Generate a complete Ansible role named '{role_name}' under '{self.roles_path}/{role_name}/'.

Role purpose:
{description}

Expected Ansible Galaxy structure (create ALL relevant files, skip only what is genuinely unused):
{ANSIBLE_GALAXY_SKELETON}

Requested variables (put in defaults/main.yml unless noted otherwise):
{vars_text}

Role dependencies (meta/main.yml):
{deps_text}

Supported OS families (meta/main.yml galaxy_info.platforms): {os_text}

Conventions to follow strictly:
1. tasks/main.yml: idempotent tasks, use proper Ansible modules (never shell/command unless no module exists), tag each major task block
2. handlers/main.yml: one handler per service action, referenced via 'notify' in tasks
3. defaults/main.yml: every overridable variable with a sane default and a comment
4. meta/main.yml: galaxy_info (author, description, license, min_ansible_version, platforms), dependencies
5. README.md: role purpose, variables table, example playbook usage
6. Use Jinja2 templates (templates/*.j2) instead of inline content for any config file
7. All YAML must be valid (2-space indent, no tabs), follow ansible-lint best practices (FQCN module names, no bare variables in conditionals)
8. Path of every generated file MUST be prefixed with '{self.roles_path}/{role_name}/'"""