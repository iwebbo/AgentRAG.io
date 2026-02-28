"""
Unified Vector Store Manager
Supports ChromaDB (default), OpenSearch, or both simultaneously.
All vector operations are centralized here - never import backend libs elsewhere.
"""
import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Optional, Any
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


# ── ChromaDB Backend ──────────────────────────────────────────────────────────

class ChromaBackend:
    """ChromaDB vector store backend."""

    def __init__(self, persist_directory: str = "./data/chromadb"):
        self.persist_dir = Path(persist_directory)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True)
        )
        logger.info(f"✅ ChromaDB initialized at {self.persist_dir}")

    def _collection_name(self, project_id: str) -> str:
        return f"project_{project_id}".replace("-", "_")

    def get_or_create_collection(self, project_id: str):
        return self.client.get_or_create_collection(
            name=self._collection_name(project_id),
            metadata={
                "hnsw:space": "cosine",
                "hnsw:construction_ef": 200,
                "hnsw:search_ef": 100
            }
        )

    def add_documents(
        self,
        project_id: str,
        documents: List[str],
        metadatas: List[Dict],
        ids: List[str],
        embeddings: Optional[List[List[float]]] = None
    ):
        col = self.get_or_create_collection(project_id)
        kwargs: Dict[str, Any] = dict(documents=documents, metadatas=metadatas, ids=ids)
        if embeddings:
            kwargs["embeddings"] = embeddings
        col.add(**kwargs)
        logger.info(f"✅ ChromaDB: {len(documents)} chunks added to project {project_id}")

    def query(
        self,
        project_id: str,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict] = None
    ) -> Dict:
        col = self.get_or_create_collection(project_id)
        return col.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"]
        )

    def delete_document(self, project_id: str, document_id: str):
        col = self.get_or_create_collection(project_id)
        results = col.get(where={"document_id": document_id}, include=[])
        if results["ids"]:
            col.delete(ids=results["ids"])
            logger.info(f"🗑️ ChromaDB: document {document_id} deleted from project {project_id}")

    def delete_collection(self, project_id: str):
        try:
            self.client.delete_collection(name=self._collection_name(project_id))
            logger.info(f"🗑️ ChromaDB: collection deleted for project {project_id}")
        except Exception as e:
            logger.error(f"ChromaDB delete_collection error: {e}")

    def get_stats(self, project_id: str) -> Dict:
        col = self.get_or_create_collection(project_id)
        return {"count": col.count(), "name": col.name, "backend": "chroma"}


# ── OpenSearch Backend ────────────────────────────────────────────────────────

class OpenSearchBackend:
    """OpenSearch vector store backend using k-NN plugin."""

    def __init__(self):
        from opensearchpy import OpenSearch
        from app.config import get_settings
        settings = get_settings()

        auth = None
        if settings.OPENSEARCH_USER and settings.OPENSEARCH_PASSWORD:
            auth = (settings.OPENSEARCH_USER, settings.OPENSEARCH_PASSWORD)

        self.client = OpenSearch(
            hosts=[{"host": settings.OPENSEARCH_HOST, "port": settings.OPENSEARCH_PORT}],
            http_auth=auth,
            use_ssl=settings.OPENSEARCH_USE_SSL,
            verify_certs=settings.OPENSEARCH_VERIFY_CERTS,
            ssl_show_warn=False,
            timeout=30,
            max_retries=3,
            retry_on_timeout=True,
        )
        self.embedding_dim = settings.OPENSEARCH_EMBEDDING_DIM
        logger.info(
            f"✅ OpenSearch initialized at {settings.OPENSEARCH_HOST}:{settings.OPENSEARCH_PORT}"
        )

    def _index_name(self, project_id: str, custom_index: Optional[str] = None) -> str:
        """Resolve index name: custom > auto-generated from project_id."""
        if custom_index and custom_index.strip():
            return custom_index.strip().lower()
        # auto: project-<uuid>  (dashes, lowercase, OS-safe)
        return f"project-{str(project_id).replace('_', '-').lower()}"

    def _default_mapping(self) -> Dict:
        return {
            "settings": {
                "index": {
                    "knn": True,
                    "knn.algo_param.ef_search": 100,
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                }
            },
            "mappings": {
                "properties": {
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": self.embedding_dim,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "nmslib",
                            "parameters": {"ef_construction": 200, "m": 16},
                        },
                    },
                    "content": {"type": "text"},
                    "document_id": {"type": "keyword"},
                    "project_id": {"type": "keyword"},
                    "filename": {"type": "keyword"},
                    "chunk_index": {"type": "integer"},
                    "metadata": {"type": "object", "enabled": True},
                }
            },
        }

    def get_or_create_index(
        self, project_id: str, custom_index: Optional[str] = None
    ) -> str:
        index = self._index_name(project_id, custom_index)
        try:
            if not self.client.indices.exists(index=index):
                self.client.indices.create(index=index, body=self._default_mapping())
                logger.info(f"✅ OpenSearch: index created '{index}'")
        except Exception as e:
            logger.error(f"OpenSearch unreachable during get_or_create_index: {e}")
        return index

    def create_index(self, index_name: str) -> bool:
        """Explicitly create a named index. Returns True if created, False if exists."""
        index = index_name.strip().lower()
        try:
            if self.client.indices.exists(index=index):
                return False
            self.client.indices.create(index=index, body=self._default_mapping())
            logger.info(f"✅ OpenSearch: index explicitly created '{index}'")
            return True
        except Exception as e:
            logger.error(f"OpenSearch unreachable during create_index: {e}")
            raise

    def index_exists(self, index_name: str) -> bool:
        try:
            return bool(self.client.indices.exists(index=index_name.strip().lower()))
        except Exception:
            return False

    def list_project_indices(self) -> List[Dict]:
        """List all project indices (pattern: project-*)."""
        try:
            result = self.client.cat.indices(
                index="project-*", h="index,docs.count,store.size", format="json"
            )
            return result if result else []
        except Exception as e:
            logger.error(f"OpenSearch list_project_indices error: {e}")
            return []

    def add_documents(
        self,
        project_id: str,
        documents: List[str],
        metadatas: List[Dict],
        ids: List[str],
        embeddings: Optional[List[List[float]]] = None,
        custom_index: Optional[str] = None,
    ):
        from opensearchpy.helpers import bulk

        index = self.get_or_create_index(project_id, custom_index)
        actions = []
        for i, (doc, meta, doc_id) in enumerate(zip(documents, metadatas, ids)):
            source: Dict[str, Any] = {
                "content": doc,
                "metadata": meta,
                "document_id": meta.get("document_id", ""),
                "project_id": meta.get("project_id", str(project_id)),
                "filename": meta.get("filename", ""),
                "chunk_index": i,
            }
            if embeddings and i < len(embeddings):
                source["embedding"] = embeddings[i]
            actions.append({"_index": index, "_id": doc_id, "_source": source})

        success, failed = bulk(self.client, actions, refresh=True, raise_on_error=False)
        logger.info(
            f"✅ OpenSearch: {success} chunks indexed in '{index}'"
            + (f", {len(failed)} failed" if failed else "")
        )

    def query(
        self,
        project_id: str,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict] = None,
        custom_index: Optional[str] = None,
    ) -> Dict:
        index = self._index_name(project_id, custom_index)
        empty = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        try:
            if not self.client.indices.exists(index=index):
                return empty
        except Exception as e:
            logger.error(f"OpenSearch unreachable during query (index check): {e}")
            return empty

        knn_clause: Dict[str, Any] = {
            "knn": {"embedding": {"vector": query_embedding, "k": n_results}}
        }

        if where:
            body = {
                "size": n_results,
                "query": {
                    "bool": {
                        "must": [knn_clause],
                        "filter": [{"term": {k: v}} for k, v in where.items()],
                    }
                },
            }
        else:
            body = {"size": n_results, "query": knn_clause}

        try:
            resp = self.client.search(index=index, body=body)
        except Exception as e:
            logger.error(f"OpenSearch query error: {e}")
            return empty

        hits = resp["hits"]["hits"]
        return {
            "ids": [[h["_id"] for h in hits]],
            "documents": [[h["_source"].get("content", "") for h in hits]],
            "metadatas": [[h["_source"].get("metadata", {}) for h in hits]],
            "distances": [[1.0 - float(h.get("_score", 1.0)) for h in hits]],
        }

    def delete_document(
        self, project_id: str, document_id: str, custom_index: Optional[str] = None
    ):
        index = self._index_name(project_id, custom_index)
        try:
            self.client.delete_by_query(
                index=index,
                body={"query": {"term": {"document_id": document_id}}},
                refresh=True,
            )
            logger.info(
                f"🗑️ OpenSearch: document {document_id} deleted from index '{index}'"
            )
        except Exception as e:
            logger.error(f"OpenSearch delete_document error: {e}")

    def delete_index(self, project_id: str, custom_index: Optional[str] = None):
        index = self._index_name(project_id, custom_index)
        try:
            if self.client.indices.exists(index=index):
                self.client.indices.delete(index=index)
                logger.info(f"🗑️ OpenSearch: index deleted '{index}'")
        except Exception as e:
            logger.error(f"OpenSearch delete_index error: {e}")

    def get_stats(self, project_id: str, custom_index: Optional[str] = None) -> Dict:
        index = self._index_name(project_id, custom_index)
        try:
            if not self.client.indices.exists(index=index):
                return {"count": 0, "name": index, "backend": "opensearch", "exists": False}
            count = self.client.count(index=index)["count"]
            return {"count": count, "name": index, "backend": "opensearch", "exists": True}
        except Exception as e:
            logger.error(f"OpenSearch get_stats error: {e}")
            return {"count": 0, "name": index, "backend": "opensearch", "exists": False}

    def health(self) -> Dict:
        try:
            info = self.client.info()
            cluster = self.client.cluster.health()
            return {
                "status": "ok",
                "cluster_status": cluster.get("status", "unknown"),
                "version": info["version"]["number"],
                "cluster_name": info["cluster_name"],
            }
        except Exception as e:
            return {"status": "error", "detail": str(e)}


# ── Unified VectorStore (public interface) ────────────────────────────────────

class VectorStore:
    """
    Unified Vector Store Manager.

    vector_store_type values:
      - "chroma"      → ChromaDB only  (default, backward-compatible)
      - "opensearch"  → OpenSearch only
      - "both"        → index into both; query ChromaDB as primary

    All callers keep the same method signatures. Pass vector_store_type and
    opensearch_index per call (from the Project model).
    """

    def __init__(self, persist_directory: str = "./data/chromadb"):
        self._chroma = ChromaBackend(persist_directory)
        self._opensearch: Optional[OpenSearchBackend] = None

    # ── internal helpers ─────────────────────────────────────────────────────

    def _os(self) -> OpenSearchBackend:
        """Lazy-init OpenSearch backend."""
        if self._opensearch is None:
            self._opensearch = OpenSearchBackend()
        return self._opensearch

    @staticmethod
    def _resolve(vector_store_type: Optional[str]):
        """Returns (use_chroma: bool, use_opensearch: bool)."""
        t = (vector_store_type or "chroma").lower()
        return ("chroma" in t or t == "both"), ("opensearch" in t or t == "both")

    # ── public API ───────────────────────────────────────────────────────────

    def get_or_create_collection(
        self,
        project_id: str,
        vector_store_type: str = "chroma",
        opensearch_index: Optional[str] = None,
    ):
        use_c, use_os = self._resolve(vector_store_type)
        if use_c:
            self._chroma.get_or_create_collection(project_id)
        if use_os:
            self._os().get_or_create_index(project_id, opensearch_index)

    def add_documents(
        self,
        project_id: str,
        documents: List[str],
        metadatas: List[Dict],
        ids: List[str],
        embeddings: Optional[List[List[float]]] = None,
        vector_store_type: str = "chroma",
        opensearch_index: Optional[str] = None,
    ):
        use_c, use_os = self._resolve(vector_store_type)
        if use_c:
            self._chroma.add_documents(project_id, documents, metadatas, ids, embeddings)
        if use_os:
            self._os().add_documents(
                project_id, documents, metadatas, ids, embeddings, opensearch_index
            )

    def query(
        self,
        project_id: str,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict] = None,
        vector_store_type: str = "chroma",
        opensearch_index: Optional[str] = None,
    ) -> Dict:
        """
        Query vector store.
        - chroma  → ChromaDB
        - opensearch → OpenSearch
        - both    → ChromaDB (primary)
        """
        use_c, use_os = self._resolve(vector_store_type)
        if use_os and not use_c:
            # OpenSearch-only project
            return self._os().query(
                project_id, query_embedding, n_results, where, opensearch_index
            )
        # chroma or both → chroma is primary query backend
        return self._chroma.query(project_id, query_embedding, n_results, where)

    def delete_document(
        self,
        project_id: str,
        document_id: str,
        vector_store_type: str = "chroma",
        opensearch_index: Optional[str] = None,
    ):
        use_c, use_os = self._resolve(vector_store_type)
        if use_c:
            self._chroma.delete_document(project_id, document_id)
        if use_os:
            self._os().delete_document(project_id, document_id, opensearch_index)

    def delete_collection(
        self,
        project_id: str,
        vector_store_type: str = "chroma",
        opensearch_index: Optional[str] = None,
    ):
        use_c, use_os = self._resolve(vector_store_type)
        if use_c:
            self._chroma.delete_collection(project_id)
        if use_os:
            self._os().delete_index(project_id, opensearch_index)

    def get_collection_stats(
        self,
        project_id: str,
        vector_store_type: str = "chroma",
        opensearch_index: Optional[str] = None,
    ) -> Dict:
        use_c, use_os = self._resolve(vector_store_type)
        stats: Dict[str, Any] = {}

        if use_c:
            stats = self._chroma.get_stats(project_id)

        if use_os:
            os_stats = self._os().get_stats(project_id, opensearch_index)
            if use_c:
                # merge: add opensearch sub-key, sum counts
                stats["opensearch"] = os_stats
                stats["count"] = stats.get("count", 0) + os_stats.get("count", 0)
            else:
                stats = os_stats

        return stats

    # ── OpenSearch management helpers (used by /api/opensearch/* routes) ─────

    def opensearch_health(self) -> Dict:
        try:
            return self._os().health()
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    def opensearch_list_indices(self) -> List[Dict]:
        try:
            return self._os().list_project_indices()
        except Exception as e:
            logger.error(f"opensearch_list_indices error: {e}")
            return []

    def opensearch_create_index(self, index_name: str) -> bool:
        return self._os().create_index(index_name)

    def opensearch_index_exists(self, index_name: str) -> bool:
        try:
            return self._os().index_exists(index_name)
        except Exception:
            return False