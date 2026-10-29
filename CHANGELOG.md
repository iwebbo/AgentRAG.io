# AgentRAG.io Changelog

## Version v1.1.90 - [29/10/2026]

This update introduces support for multiple new service providers and integrates LlamaServer functionality into the system.

---

### New Features & Enhancements

#### Expanded Provider Support
The backend factory and frontend components have been updated to incorporate several new provider options, enhancing connectivity.

*   **New providers added:** Multiple new service providers were integrated into the system.
*   **Updated provider logic:** The `provider_factory.py` was significantly updated to handle expanded provider configurations.

#### LlamaServer Integration
New C++ files were added to support LlamaServer functionality, improving local model serving capabilities.

*   **Added llamaserver.cpp:** The core logic for `llamaserver.cpp` was implemented and added to the codebase.
*   **Frontend integration:** Changes were made in the frontend to support LlamaServer features.

**Fixes & Bug Resolutions**

*   **JudgeLLM value fix:** Corrected a change value issue related to JudgeLLM functionality.

---
