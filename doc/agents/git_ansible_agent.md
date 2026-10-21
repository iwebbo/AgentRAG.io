## Git Ansible Role Generator Agent — Code Generation & CI/CD

**Purpose**: This agent utilizes a Large Language Model (LLM) to generate complete, functional Ansible roles based on natural language descriptions and specified requirements. It integrates with **Git platforms** for version control, linting, committing, and Pull Request creation, automating the entire development lifecycle of infrastructure code.

**Workflow**:
1. **Configuration**: Initialize the agent by providing connection details to the Git repository and defining operational parameters (e.g., base branch, roles path).
2. **Execution**: Submit a request containing the desired role name, detailed description, supported operating systems, and test mode status.
3. **Generation**: The LLM generates the Ansible code structure.
4. **Integration**: The agent commits the generated code to the specified Git repository and optionally creates a Pull Request for review.

---

## Agent Account Configuration

### Creating the Ansible Role Generator Agent

**API Endpoint**: `POST /api/agents/`

*Note: All sensitive credentials (URLs, tokens) have been anonymized.*

```bash
curl -sk -X POST "$BASE/api/agents/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Ansible Role Generator",
    "agent_type": "git_ansible_role_generator",
    "config": {
      "mcp_servers": ["git", "linter"],
      "llm_provider": "lmstudio",
      "llm_model": "openai/gpt-oss-20b",
      "llm_temperature": 0.2,
      "base_branch": "main",
      "auto_lint": true,
      "auto_commit": true,
      "auto_create_pr": false,
      "roles_path": "roles"
    },
    "mcp_config": {
      "git": {
        "url": "[GIT_SERVER_URL]",
        "token": "[GIT_ACCESS_TOKEN]",
        "repo": "[USER]/[REPO_NAME]"
      }
    }
  }'
```

**Key Configuration Parameters:**

| Parameter | Description | Notes |
| :--- | :--- | :--- |
| `mcp_servers` | List of connected services. | Requires both Git (`git`) and code quality checking (`linter`). |
| `llm_provider` | The LLM service used for generation. | e.g., `lmstudio`, `openai`. |
| `llm_model` | Specific model identifier. | Determines the capability of the generated code. |
| `auto_lint` | If true, runs linting checks after generation. | Ensures code quality before committing. |
| `auto_commit` | If true, commits changes automatically. | Requires write access to the repository. |
| `mcp_config.git.url` | The base URL of the Git platform. | Must be accessible by the agent. |
| `mcp_config.git.token` | A dedicated token for API interaction. | Should have limited scope permissions. |

---

## Execution Mode: Role Generation

**Endpoint**: `POST /api/agents/<AGENT_ID>/execute`

### 2.1 Generating a New Ansible Role (Standard Use Case)

This example generates an Ansible role to harden Nginx, including TLS setup, security headers, and Fail2ban integration.

```bash
curl -X POST "$BASE/api/agents/<AGENT_ID>/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": {
      "role_name": "nginx_hardening",
      "description": "Ansible role to harden Nginx: TLS, security headers, fail2ban integration.",
      "supported_os": ["Debian", "RedHat"],
      "test_mode": false
    },
    "trigger": "manual"
  }'
```

**Input Data Fields Explained:**

| Field | Type | Description | Required? |
| :--- | :--- | :--- | :--- |
| `role_name` | String | The desired name for the Ansible role. | Yes |
| `description` | String | Detailed natural language description of the role's functionality and goals. | Yes |
| `supported_os` | Array (String) | List of operating systems the role must support (e.g., `["Debian", "RedHat"]`). | Recommended |
| `test_mode` | Boolean | If true, runs a dry-run simulation without committing code. | No |

### 2.2 Workflow Summary

The agent processes the input data through the LLM to generate structured Ansible YAML files (tasks, handlers, templates). It then uses the configured Git connection (`mcp_config`) to:
1. Create the necessary directory structure in the repository.
2. Write the generated code into the appropriate role directories.
3. Commit the changes and optionally open a Pull Request for human review.
