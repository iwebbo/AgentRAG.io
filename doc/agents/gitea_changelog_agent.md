Here is the line-by-line translation of your document into English, maintaining all formatting, code blocks, and structure.

***

Voici le document entièrement adapté pour utiliser **Gitea** au lieu de GitHub. J'ai mis à jour les titres, les descriptions et surtout la configuration JSON pour refléter l'utilisation de Gitea comme plateforme Git principale.
*This document is fully adapted to use **Gitea** instead of GitHub. I have updated the titles, descriptions, and especially the JSON configuration to reflect the use of Gitea as the primary Git platform.*

***

# Gitea Changelog Agent — Documentation & Versioning Generation

**Purpose**: This agent uses a Large Language Model (LLM) to analyze recent Pull Requests (PRs) and automatically generate a structured *Changelog* section. It allows the project documentation to be kept up-to-date based on commit history, thus simulating the versioning writing process from an actual event until its publication in the repository.

**Workflow**:
1. **Authentication**: Obtain an API token for secure access to the agent system.
2. **Configuration**: Initialize the agent by linking it to a specific Git repository and defining LLM parameters (file path, PR state).
3. **Execution (Dry-Run)**: Test content generation without writing or modifying the `CHANGELOG.md` file in the remote repository.
4. **Execution (Live Run)**: Generate the changelog and update the target file (`CHANGELOG.md`) with detected changes.

---


## Agent Account Configuration
### 1. Authentication: Obtaining the Platform Token

*To begin, an access token must be obtained using the provided test credentials.*

```bash
export BASE="https://agentragio.local:30443"

TOKEN=$(curl -sk -X POST "$BASE/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test&password=testtest" \
  | jq -r '.access_token')

echo "TOKEN=$TOKEN"
```

### 2. Creating the Gitea Changelog Agent

*The agent is created via the endpoint `POST /api/agents/`.*


```bash
curl -sk -X POST "$BASE/api/agents/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "GiteaChangelogAgent-APP",
    "description": "Changelog des dernières PRs vers main sur Gitea",
    "agent_type": "gitea_changelog",
    "config": { 
      "mcp_servers": ["gitea"], 
      "base_branch": "main", 
      "pr_state": "open",
      "changelog_path": "CHANGELOG.md", 
      "use_llm": true, 
      "language": "en", 
      "skip_ci": false,
      "llm_provider": "lmstudio", 
      "llm_model": "qwen3.5-4b-claude-4.6-opus-reasoning-distilled", 
      "llm_temperature": 0.1 
    },
    "mcp_config": { 
      "gitea": { 
        "url": "http://gitea.example.com", 
        "token": "[GITEA_ACCESS_TOKEN]", 
        "repo": "owner/repo" 
      } 
    },
    "is_active": true 
  }'
```

**Instructions**: Retrieve the agent ID from the JSON response. This ID will be used as `<AGENT_ID>` for subsequent execution steps.

```bash
export AGENT_ID="068dda6a-7488-4abf-8be7-71cac596a4c2"
```

**Key Configuration Parameters:**

| Parameter | Description | Notes |
| :--- | :--- | :--- |
| `mcp_servers` | List of connected services. | Requires a Gitea connection for PR history. |
| `changelog_path` | Path to the changelog file to update. | Defines the target file (e.g., `CHANGELOG.md`). |
| `pr_state` | State of Pull Requests to consider. | Can be `"open"`, or other states defined by the API. |
| `use_llm` | Indicates if the AI should summarize changes. | If `true`, the LLM is used for content drafting. |
| `language` | Output language of the changelog. | E.g.: `"en"` or `"fr"`. |
| `base_branch` | Main branch source of data. | Generally `main`. |
| `mcp_config.gitea.token` | Access token for the Gitea Git repository. | Must have read rights on history and write rights on the target file. |

---

## Execution Modes
### 2.1 Dry-Run Mode: Simulation Only (Preview)

*This mode executes the changelog generation logic, simulates PR analysis, and generates the expected content without writing or modifying the `CHANGELOG.md` file in the remote repository. It is used to validate the structure and content before publication.*

```bash
curl -sk -X POST "$BASE/api/agents/<AGENT_ID>/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "trigger": "manual", "input_data": { "version": "v1.1.81", "dry_run": true } }'
```

**Key Input Data Fields:**

| Field | Description | Purpose |
| :--- | :--- | :--- |
| `version` | The software version to document. | Defines the title and scope of changes (e.g., `"v1.1.81"`). |
| `dry_run` | **Boolean flag set to `true`**. | Ensures that no actual Git operation is performed; only the content is returned. |

### 2.2 Live Run Mode: Commit and Changelog Update (Production)

*This mode executes all actions: PR analysis, LLM content generation, and updating the `CHANGELOG.md` file in the target branch. This is the final step for integrating the updated changelog.*

```bash
curl -sk -X POST "$BASE/api/agents/<AGENT_ID>/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "trigger": "manual", "input_data": { "version": "v1.1.81", "dry_run": false} }'
```

**Key Input Data Fields:**

| Field | Description | Purpose |
| :--- | :--- | :--- |
| `version` | The software version to document. | Defines the title and scope of changes (e.g., `"v1.1.81"`). |
| `dry_run` | **Boolean flag set to `false`**. | Executes all commands (analysis, writing, commit) in the remote repository. |
