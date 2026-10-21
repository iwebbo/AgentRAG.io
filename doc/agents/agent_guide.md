## Agentic - Agent

#### **Agent Types Available**

| Agent | `agent_type` | Use Case | MCP Servers | RAG Context |
|-------|-------------|----------|-------------|-------------|
| **Code Generator** | `code_generator` | Generate code from natural language | GitHub, Linter, Test Runner | Repository docs |
| **Branch Code Review** | `branch_code_review` | Automated PR review with suggestions | GitHub | Coding standards |
| **Legal Advisor** | `legal_fiscal` | Contract analysis, compliance checks | — | Legal database |
| **Accounting Advisor** | `accounting_finance` | Financial analysis, invoice processing | — | Accounting rules |
| **Web Search** | `websearch` | Real-time web search & synthesis | — | — |
| **Travel Expert** | `travel_expert` | Trip planning, itinerary management | — | Travel knowledge |
| **Email Expert** | `email_expert` | Draft, analyse and send emails via LLM | — | — |
| **Gitea Code Generator** | `gitea_code_generator` | fixed | `gitea`, `linter` | Generate code, lint, commit and PR on self-hosted Gitea |
| **Gitea Ansible Role Generator** | `gitea_ansible_role_generator` | fixed | `gitea`, `linter` | Generate Role Ansible, lint, commit and PR on self-hosted Gitea |
| **Git Ansible Role Generator** | `ansible_role_generator` | fixed | `git`, `linter` | Generate Role Ansible, lint, commit and PR on self-hosted GitHub |
| **Git Branch Generator** | `GitHubBranchGeneratorAgent` | fixed | `git` | Generate any, lint, commit and PR on self-hosted GitHub |
| **Gitea Branch Generator** | `GiteaBranchGeneratorAgent` | fixed | `gitea` | Generate any, lint, commit and PR on self-hosted Gitea |
| **Git CHANGELOG Agent** | `GitHubChangelogAgent` | fixed | `git` | Generate CHANGELOG.md - Versionning, lint, commit and add to PR on self-hosted GitHub |
| **Gitea CHANGELOG Agent** | `GiteaChangelogAgent` | fixed | `gitea` | Generate CHANGELOG.md - Versionning, lint, commit and add to PR on self-hosted Gitea |
| **DataGouv Explorer** | `datagouv_explorer` | fixed | `datagouv` | Search and explore the French open data catalogue |
| **WikiJS Assistant** | `wikijs` | fixed | `wikijs` | Search, read, create and update Wiki.js documentation pages via LLM |
| **SSH Agent** | `skill` (.md) | Remote command execution on Linux/Unix hosts | SSH (DB-aware) | — |
| **WinRM Agent** | `skill` (.md) | Remote PowerShell execution on Windows hosts | WinRM (DB-aware) | — |
| **Skill Agent** | `skill` | Any custom agent defined via `.md` frontmatter | Any registered MCP | Any project |
| **SonarQube Security** | `sonarqube` | Projects inventory, vulnerabilities, security hotspots, quality gate, and LLM-assisted remediation (modes: `projects`, `overview`, `issues`, `hotspots`, `remediate`) | `sonarqube` | Optional — repository project (`use_rag: true` + `project_id`) |

| *(Custom)* | `skill` | Build your own specialized agent | Any MCP server | Any project |



***
## AI Agent Guide (Agent Registry)

*   **[Code Generator Agent](code_generator_agent.md)** : The primary engine for generating code from natural language descriptions.
*   **[Branch Code Review Agent](branch_code_generator_review_agent.md)** : Performs automated reviews of Pull Requests with suggested improvements.
*   **[Git Ansible Agent](git_ansible_agent.md)** : Generates and manages Ansible roles for GitHub.
*   **[Gitea Code Generator Agent](gitea_code_generator_agent.md)** : Code generator equivalent, optimized for the self-hosted Gitea environment.
*   **[Git Branch Generator Agent](git_branch_generator_agent.md)** : Generates and manages Git branches on GitHub.
*   **[Gitea Branch Generator Agent](gitea_branch_generator_agent.md)** : Generates and manages Gitea branches on a self-hosted Gitea instance.
*   **[Git Changelog Agent](git_changelog_agent.md)** : Automates the creation of the `CHANGELOG.md` file for GitHub.
*   **[Gitea Changelog Agent](gitea_changelog_agent.md)** : Automates the creation of the `CHANGELOG.md` file for a self-hosted Gitea instance.
*   **[Legal Advisor Agent](legal_advisor_agent.md)** : Analyzes contracts, verifying legal and tax compliance.
*   **[Accounting Advisor Agent](accounting_advisor_agent.md)** : Advanced financial processing, invoice analysis, and accounting.
*   **[Travel Expert Agent](travel_expert_agent.md)** : Plans complex trips and manages detailed itineraries.
*   **[Email Expert Agent](email_expert_agent.md)** : Assists in drafting, analyzing, and tracking email communications using an LLM.
*   **[Web Search Agent](web_search_agent.md)** : Searches for real-time information on the web and synthesizes multiple results.
*   **[SSH Agent](ssh_agent.md)** : Executes remote commands on Linux/Unix hosts via SSH.
*   **[WinRM Agent](winrm_agent.md)** : Executes remote PowerShell scripts on Windows machines.
*   **[SonarQube Security Agent](sonarqube_security_agent.md)** : Audits project security, identifies vulnerabilities, and suggests remediation steps.
*   **[WikiJS Assistant](wikijs_agent.md)** : Comprehensive management of Wiki content (reading, creating, updating) using an LLM.
*   **[DataGouv FR Agent](datagouv_fr_agent.md)** : Explores and performs targeted searches within the French open data catalog.
*   **[Skill Agent](skill_agent.md)** : The universal agent. Allows defining and executing any custom task via an `.md` file (Frontmatter).

***