from typing import Dict, Any, AsyncGenerator
from uuid import UUID
from sqlalchemy.orm import Session
import logging
from datetime import datetime

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class DataGouvAgent(BaseAgent):
    """
    Agent d'exploration du catalogue de données ouvertes data.gouv.fr.

    Exploite le DataGouvMCPServer pour :
        - Rechercher des jeux de données en langage naturel
        - Récupérer les métadonnées et ressources d'un dataset
        - Explorer les organisations productrices
        - Analyser et résumer les résultats via LLM

    Config attendue (agent.config) :
    {
        "mcp_servers": ["datagouv"],
        "mode": "search" | "dataset" | "organization" | "topic",
        "analyze": true,              # passer les résultats au LLM (optionnel, défaut true)
        "page_size": 10               # résultats par page (optionnel)
    }

    Input attendu (input_data) :
        mode=search       → { "query": "population par commune" }
        mode=dataset      → { "dataset_id": "population-legale-2021" }
        mode=organization → { "query": "ministère" }  |  { "org_id": "..." }
        mode=topic        → { "topic_id": "..." }  |  {}  (liste tous les topics)
    """

    MCP_SERVER = "datagouv"

    def __init__(
        self,
        agent_id: UUID,
        user_id: UUID,
        config: Dict[str, Any],
        mcp_config: Dict[str, Any],
        db: Session,
    ):
        super().__init__(agent_id, user_id, config, mcp_config, db)
        self.mode = config.get("mode", "search")
        self.analyze = config.get("analyze", True)
        self.page_size = config.get("page_size", 10)

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #

    async def execute(self, input_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Dispatch vers le bon workflow selon self.mode.
        """
        mode = input_data.get("mode", self.mode)

        self.log("info", f"DataGouvAgent starting — mode={mode}")
        yield self._progress("init", f"Mode d'exécution : {mode}")

        try:
            if mode == "search":
                async for update in self._workflow_search(input_data):
                    yield update

            elif mode == "dataset":
                async for update in self._workflow_dataset(input_data):
                    yield update

            elif mode == "organization":
                async for update in self._workflow_organization(input_data):
                    yield update

            elif mode == "topic":
                async for update in self._workflow_topic(input_data):
                    yield update

            else:
                yield self._error(f"Unknown mode: {mode}. Expected: search|dataset|organization|topic")

        except Exception as exc:
            self.log("error", f"DataGouvAgent failed: {exc}")
            yield self._error(str(exc))

    # ------------------------------------------------------------------ #
    # Workflows
    # ------------------------------------------------------------------ #

    async def _workflow_search(self, input_data: Dict[str, Any]):
        """Search datasets by keyword."""
        query = input_data.get("query")
        if not query:
            yield self._error("Missing 'query' for mode=search")
            return

        page = input_data.get("page", 1)
        tag = input_data.get("tag")
        organization = input_data.get("organization")
        sort = input_data.get("sort", "score")

        self.log("info", f"🔍 Searching datasets: q={query!r}")
        yield self._progress("search", f"Recherche : « {query} »")

        raw = await self.call_mcp(self.MCP_SERVER, "search_datasets", {
            "q": query,
            "page": page,
            "page_size": self.page_size,
            "organization": organization,
            "tag": tag,
            "sort": sort,
        })

        datasets = raw.get("data", [])
        total = raw.get("total", 0)

        self.log("info", f"✅ {total} datasets found, {len(datasets)} returned on page {page}")
        yield self._progress("search_done", f"{total} jeux de données trouvés")

        # Summarise via LLM if requested
        summary = None
        if self.analyze and datasets:
            yield self._progress("llm", "Analyse LLM des résultats...")
            summary = await self._llm_summarise_datasets(query, datasets)

        yield {
            "type": "result",
            "data": {
                "mode": "search",
                "query": query,
                "total": total,
                "page": page,
                "page_size": self.page_size,
                "datasets": [self._slim_dataset(d) for d in datasets],
                "summary": summary,
                "metadata": {
                    "tag": tag,
                    "organization": organization,
                    "sort": sort,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _workflow_dataset(self, input_data: Dict[str, Any]):
        """Fetch a single dataset and its resources."""
        dataset_id = input_data.get("dataset_id")
        if not dataset_id:
            yield self._error("Missing 'dataset_id' for mode=dataset")
            return

        self.log("info", f"📦 Fetching dataset: {dataset_id}")
        yield self._progress("fetch_dataset", f"Chargement du dataset : {dataset_id}")

        dataset = await self.call_mcp(self.MCP_SERVER, "get_dataset", {
            "dataset_id": dataset_id,
        })

        yield self._progress("fetch_resources", "Chargement des ressources...")
        resources_raw = await self.call_mcp(self.MCP_SERVER, "list_dataset_resources", {
            "dataset_id": dataset_id,
            "page_size": 50,
        })
        resources = resources_raw.get("data", [])

        self.log("info", f"✅ Dataset '{dataset.get('title')}' — {len(resources)} resources")

        summary = None
        if self.analyze:
            yield self._progress("llm", "Analyse LLM du dataset...")
            summary = await self._llm_describe_dataset(dataset, resources)

        yield {
            "type": "result",
            "data": {
                "mode": "dataset",
                "dataset": self._slim_dataset(dataset),
                "resources": [self._slim_resource(r) for r in resources],
                "resources_total": resources_raw.get("total", len(resources)),
                "summary": summary,
                "metadata": {"timestamp": datetime.utcnow().isoformat()},
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _workflow_organization(self, input_data: Dict[str, Any]):
        """Search or fetch an organisation."""
        org_id = input_data.get("org_id")
        query = input_data.get("query")

        if org_id:
            # Direct fetch
            self.log("info", f"🏛 Fetching organisation: {org_id}")
            yield self._progress("fetch_org", f"Chargement organisation : {org_id}")

            org = await self.call_mcp(self.MCP_SERVER, "get_organization", {
                "org_id": org_id,
            })
            yield {
                "type": "result",
                "data": {
                    "mode": "organization",
                    "organization": self._slim_org(org),
                    "metadata": {"timestamp": datetime.utcnow().isoformat()},
                },
                "timestamp": datetime.utcnow().isoformat(),
            }

        elif query:
            self.log("info", f"🔍 Searching organisations: q={query!r}")
            yield self._progress("search_org", f"Recherche organisation : « {query} »")

            raw = await self.call_mcp(self.MCP_SERVER, "search_organizations", {
                "q": query,
                "page_size": self.page_size,
            })
            orgs = raw.get("data", [])
            yield {
                "type": "result",
                "data": {
                    "mode": "organization",
                    "total": raw.get("total", 0),
                    "organizations": [self._slim_org(o) for o in orgs],
                    "metadata": {"timestamp": datetime.utcnow().isoformat()},
                },
                "timestamp": datetime.utcnow().isoformat(),
            }

        else:
            yield self._error("Provide 'org_id' or 'query' for mode=organization")

    async def _workflow_topic(self, input_data: Dict[str, Any]):
        """List topics or fetch a specific topic."""
        topic_id = input_data.get("topic_id")

        if topic_id:
            self.log("info", f"📂 Fetching topic: {topic_id}")
            yield self._progress("fetch_topic", f"Chargement thème : {topic_id}")

            topic = await self.call_mcp(self.MCP_SERVER, "get_topic", {
                "topic_id": topic_id,
            })
            yield {
                "type": "result",
                "data": {
                    "mode": "topic",
                    "topic": topic,
                    "metadata": {"timestamp": datetime.utcnow().isoformat()},
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        else:
            self.log("info", "📋 Listing all topics")
            yield self._progress("list_topics", "Chargement des thèmes disponibles...")

            raw = await self.call_mcp(self.MCP_SERVER, "list_topics", {
                "page_size": 100,
            })
            yield {
                "type": "result",
                "data": {
                    "mode": "topic",
                    "total": raw.get("total", 0),
                    "topics": raw.get("data", []),
                    "metadata": {"timestamp": datetime.utcnow().isoformat()},
                },
                "timestamp": datetime.utcnow().isoformat(),
            }

    # ------------------------------------------------------------------ #
    # LLM helpers
    # ------------------------------------------------------------------ #

    async def _llm_summarise_datasets(
        self, query: str, datasets: list
    ) -> str:
        """Ask the LLM to summarise search results in plain French."""
        items = "\n".join(
            f"- [{d.get('title')}] {d.get('description', '')[:120]}..."
            for d in datasets[:10]
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "Tu es un expert en données ouvertes françaises. "
                    "Tu aides les utilisateurs à comprendre les jeux de données disponibles sur data.gouv.fr."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"L'utilisateur a recherché : « {query} »\n\n"
                    f"Voici les jeux de données trouvés :\n{items}\n\n"
                    "Fais un résumé synthétique (5-8 lignes) des données disponibles, "
                    "leur pertinence et les usages possibles."
                ),
            },
        ]
        return await self.call_llm(messages, max_tokens=600)

    async def _llm_describe_dataset(
        self, dataset: Dict[str, Any], resources: list
    ) -> str:
        """Ask the LLM to describe a dataset and its resources."""
        resource_lines = "\n".join(
            f"  • {r.get('title', '?')} [{r.get('format', '?')}] — {r.get('url', '')}"
            for r in resources[:15]
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "Tu es un expert en open data. "
                    "Explique de façon claire et concise les jeux de données data.gouv.fr."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Dataset : {dataset.get('title')}\n"
                    f"Description : {dataset.get('description', 'N/A')[:400]}\n"
                    f"Organisation : {dataset.get('organization', {}).get('name', 'N/A') if dataset.get('organization') else 'N/A'}\n"
                    f"Licence : {dataset.get('license', 'N/A')}\n"
                    f"Ressources :\n{resource_lines}\n\n"
                    "Décris ce dataset en quelques phrases (public cible, contenu, "
                    "utilisation possible, format des fichiers)."
                ),
            },
        ]
        return await self.call_llm(messages, max_tokens=500)

    # ------------------------------------------------------------------ #
    # Slim helpers — reduce payload size
    # ------------------------------------------------------------------ #

    @staticmethod
    def _slim_dataset(d: Dict[str, Any]) -> Dict[str, Any]:
        org = d.get("organization") or {}
        return {
            "id": d.get("id"),
            "slug": d.get("slug"),
            "title": d.get("title"),
            "description": (d.get("description") or "")[:300],
            "url": d.get("page"),
            "license": d.get("license"),
            "created_at": d.get("created_at"),
            "last_modified": d.get("last_modified"),
            "resources_count": len(d.get("resources", [])),
            "organization": org.get("name") if isinstance(org, dict) else None,
            "tags": d.get("tags", [])[:10],
        }

    @staticmethod
    def _slim_resource(r: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": r.get("id"),
            "title": r.get("title"),
            "url": r.get("url"),
            "format": r.get("format"),
            "mime": r.get("mime"),
            "filesize": r.get("filesize"),
            "checksum": r.get("checksum"),
            "created_at": r.get("created_at"),
            "last_modified": r.get("last_modified"),
            "type": r.get("type"),
        }

    @staticmethod
    def _slim_org(o: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": o.get("id"),
            "slug": o.get("slug"),
            "name": o.get("name"),
            "description": (o.get("description") or "")[:200],
            "url": o.get("page"),
            "datasets_count": o.get("metrics", {}).get("datasets", 0) if o.get("metrics") else 0,
        }

    # ------------------------------------------------------------------ #
    # Yield helpers
    # ------------------------------------------------------------------ #

    def _progress(self, step: str, message: str) -> Dict[str, Any]:
        return {
            "type": "progress",
            "data": {"step": step, "message": message},
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _error(self, message: str) -> Dict[str, Any]:
        self.log("error", message)
        return {
            "type": "error",
            "data": {"error": message},
            "timestamp": datetime.utcnow().isoformat(),
        }