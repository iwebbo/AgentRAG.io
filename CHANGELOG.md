# AgentRAG.io Changelog

## Version v1.1.76 - [13/10/2026]

We are thrilled to announce a major release focused on transforming autonomous agents from simple scripts into reliable, scheduled background processes. This update introduces the powerful Scheduler module, allowing users to manage complex workflows and periodic tasks with unprecedented control and reliability. We have also expanded our connectivity options by adding new provider support.

---

### New Features & Enhancements

#### Agent Scheduler Module (Major Feature)
The dedicated Scheduler allows you to transform your autonomous agents into robust, scheduled background processes. You can now schedule the periodic execution of complex agent workflows or run simple LLM prompts according to a precise calendar, with complete supervision over the entire task lifecycle.

*   **Cron-Based Scheduling:** Define recurring tasks using standard cron frequency definitions. Ideal for routine maintenance, daily report generation, or continuous monitoring checks.
*   **Deterministic Agent Execution:** Execute agents with fixed and predefined arguments. Perfect for predictable, routine tasks such as system status checks or log reporting on specific parameters.
*   **Periodic LLM Prompt Scheduling:** Launch simple prompts directly via a calendar trigger. This is useful for automated content generation (e.g., market analysis reports) or regular data aggregation without needing a full agent workflow.
*   **Multi-Step Workflows:** Chain multiple agents or steps sequentially within a single job. One agent can reliably trigger the next, ensuring complex and complete operational workflows.

#### Workflow Control & Safety Features
To ensure maximum reliability and safety for critical tasks, we have implemented advanced control mechanisms:

*   **Approval Modes:** Gain granular control over every execution using manual, auto, or skip-all modes. This ensures that human oversight is mandatory for high-risk or critical operations.
*   **Notifications and Auditing:** Receive immediate results via in-app notification or email alerts upon completion or failure. Every single execution is logged, providing a complete and immutable audit trail for full traceability.

### Integrations & Connectivity

#### New Provider Support: SGlang
We have significantly expanded our connectivity options by integrating the SGlang provider. This addition allows AgentRAG.io to interact with new services and data sources, broadening the scope of automation possible within your workflows.

### Improvements & Fixes

*   **Email HTML Quick Fix:** Addressed a quick fix for an issue related to HTML tags in email generation, ensuring cleaner and more reliable communication outputs.
*   **General Stability:** Various minor updates have been implemented across the platform to improve overall stability and performance of scheduled tasks.