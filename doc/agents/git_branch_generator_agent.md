## GitHub Branch Generator Agent — Code Scaffolding & Version Control

**Purpose**: This agent leverages a Large Language Model (LLM) to generate structured code files based on natural language prompts and automatically manages version control workflows using GitHub. It allows users to scaffold new features, templates, or components directly into a dedicated branch, simulating the entire development cycle from idea to Pull Request (PR).

**Workflow**:
1. **Authentication**: Obtain an API token for secure access to the agent system.
2. **Configuration**: Initialize the agent by linking it to a specific GitHub repository and defining LLM parameters.
3. **Execution (Dry-Run)**: Test the prompt generation process without making any changes to the remote repository.
4. **Execution (Live Run)**: Generate code, create a new branch, commit the files, and optionally open a Pull Request for review.

---

## Agent Account Configuration

### Creating the GitHub Branch Generator Agent

**API Endpoint**: `POST /api/agents/`

*Note: All sensitive credentials (tokens) have been anonymized.*

```bash
curl -sk -X POST "$BASE/api/agents/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "GitHub Branch Generator",
    "description": "Generate files on a new branch",
    "agent_type": "github_branch_generator",
    "config": {
      "mcp_servers": ["github"],
      "base_branch": "main",
      "auto_create_pr": false,
      "max_files": 40,
      "max_tokens": 8000,
      "llm_provider": "lmstudio",
      "llm_model": "qwen3.5-4b-claude-4.6-opus-reasoning-distilled",
      "llm_temperature": 0.2
    },
    "mcp_config": {
      "github": {
        "token": "[GITHUB_PAT]",
        "repo": "iwebbo/Jenkins"
      }
    },
    "is_active": true
  }'
```

**Key Configuration Parameters:**

| Parameter | Description | Notes |
| :--- | :--- | :--- |
| `mcp_servers` | List of connected services. | Requires connection to GitHub for version control. |
| `llm_provider` | The LLM service used for code generation. | e.g., `lmstudio`. |
| `llm_model` | Specific model identifier. | Determines the quality and style of generated code. |
| `base_branch` | The primary branch from which new features are branched off (e.g., `main`). | Defines the source of truth for the repository. |
| `auto_create_pr` | If true, automatically opens a PR upon successful commit. | Useful for CI/CD automation. |
| `mcp_config.github.token` | A GitHub Personal Access Token (PAT). | Must have write access to the target repository. |

---

## Execution Modes

### 2.1 Dry-Run Mode: Simulation Only

This mode executes the generation process and simulates the Git operations without committing or pushing any changes to the remote repository. It is used for validation and previewing the generated code structure.

```bash
# Trigger: manual (user initiated)
curl -sk -X POST "$BASE/api/agents/<AGENT_ID>/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"trigger":"manual","input_data":{
        "prompt":"Create a jenkins template groovy example",
        "branch":"feature/AgentRAG-new","dry_run":true}}'
```

**Key Input Data Fields:**

| Field | Description | Purpose |
| :--- | :--- | :--- |
| `prompt` | The detailed instruction for the LLM. | Defines *what* code needs to be generated (e.g., "Create a jenkins template groovy example"). |
| `branch` | The name of the new feature branch to create. | Isolates the work from the main codebase. |
| `dry_run` | **Boolean flag set to `true`**. | Ensures no actual Git operations occur; only output is returned. |

### 2.2 Live Run Mode: Commit and Pull Request Creation

This mode performs all actions: code generation, branch creation, file commit, and optionally opening a PR. This is the final step for integrating generated code into the repository.

```bash
# Trigger: manual (user initiated)
curl -sk -X POST "$BASE/api/agents/<AGENT_ID>/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"trigger":"manual","input_data":{
        "prompt":"Create a jenkins template groovy example",
        "branch":"feature/AgentRAG-new","base_branch":"main",
        "commit_message":"feat: add helm chart","create_pr":true,"dry_run":false}}'
```

**Key Input Data Fields:**

| Field | Description | Purpose |
| :--- | :--- | :--- |
| `prompt` | The detailed instruction for the LLM. | Defines *what* code needs to be generated. |
| `branch` | The name of the new feature branch. | Where the generated files will live. |
| `base_branch` | The target branch (e.g., `main`) for merging the PR into. | Specifies the integration point. |
| `commit_message` | A conventional commit message summarizing the changes. | Required for clean Git history. |
| `create_pr` | **Boolean flag set to `true`**. | Triggers the final step: opening a Pull Request for review. |
| `dry_run` | **Boolean flag set to `false`**. | Executes all commands (branching, committing, pushing). |
