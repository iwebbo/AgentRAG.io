# AgentRAG.io Changelog

## Version v1.1.93 - [03/11/2026]

Adds RAG (Retrieval-Augmented Generation) feature with comprehensive context management services for chat reviews.

---

### New Features & Enhancements

#### RAG Context Management
Implements retrieval-augmented generation context handling through new service modules.

*   **rag_context.py:** New RAG-specific context management service
*   **conversation_context.py:** Conversation state tracking for chat sessions

#### Chat Review Improvements
Enhances chat review functionality with improved context handling.

*   **chat.py routes:** Updated chat route handlers for RAG integration
*   **rag_chat.py routes:** New RAG-specific chat endpoint implementation

#### Context Budget & Limits
Adds model limits and context budget tracking services.

*   **context_budget.py:** Service for managing context token budgets
*   **model_limits.py:** Service for enforcing model usage limits

---
