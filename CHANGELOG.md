# AgentRAG.io Changelog

## Version v1.1.84 - [19/10/2026]

Adds Generator X agents for Gitea and GitHub branch generation with scheduler integration and frontend display updates.

---

### New Features & Enhancements

#### Generator X Agent Implementation
Implements new agent types for generating branches from Gitea and GitHub repositories.

*   **Gitea Branch Generator:** New backend agent supporting branch generation from Gitea repositories
*   **GitHub Branch Generator:** New backend agent supporting branch generation from GitHub repositories

#### Scheduler Agent Integration
Updates scheduler catalog to discover and manage new agents.

*   **Agent Discovery:** Modified scheduler/catalog.py to register new agent types
*   **Executor Updates:** Updated agent_executor.py for new generator agents

#### Frontend Agent Display
Adds UI component for displaying Generator X agents in the Agents page.

*   **Agents.jsx Component:** Added agent.jsx file and updated frontend display

**Fixes & Bug Resolutions**

*   **Scheduler Changelog Bug:** Fixed issue with scheduler adding changelogAgent

---
