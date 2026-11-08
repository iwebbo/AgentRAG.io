# AgentRAG.io Changelog

## Version v1.1.98 - [06/11/2026]

This update significantly enhances embedding capabilities by integrating new services and configuration logic.

---

### New Features & Enhancements

#### Enhanced Embedding Service
The core embedding functionality has been updated to improve performance and integrate external codebases, specifically related to Jina.

*   **Updated embeddings service:** Modified `backend/app/services/embeddings.py` for enhanced logic.
*   **New configuration file:** Added `backend/app/services/embedding_config.py` to manage embedding settings.

#### Improved Vector Store Management
Vector store handling and synchronization processes have been updated.

*   **Updated vector store logic:** Modified `backend/app/services/vector_store.py` for better data management.
*   **Sync manager updates:** Changed `backend/app/services/sync_manager.py` to improve synchronization processes.

#### Embedding Model Baking Script
A new script has been introduced to facilitate the creation and preparation of embedding models.

*   **New model baking tool:** Added `backend/scripts/bake_embedding_models.py` for preparing embedding models.

