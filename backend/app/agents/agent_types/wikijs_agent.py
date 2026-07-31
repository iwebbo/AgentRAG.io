from typing import Dict, Any, AsyncGenerator, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
import logging
from datetime import datetime

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class WikiJSAgent(BaseAgent):
    """
    Agent d'intégration Wiki.js.

    Exploite le WikiJSMCPServer pour :
        - Lire une page existante et la faire analyser/expliquer par le LLM
        - Rechercher des pages
        - Générer une NOUVELLE page à partir d'un prompt + contexte (LLM local)
        - Modifier une page existante à partir d'une instruction (LLM local)
        - Générer un LOT de pages en une seule exécution (batch_create)

    Config attendue (agent.config) :
    {
        "mcp_servers": ["wikijs"],
        "mode": "read" | "search" | "create" | "update" | "batch_create",
        "default_locale": "fr",
        "default_tags": ["auto-généré"]
    }

    Input attendu (input_data), selon le mode :
        read          → { "path": "..." }  ou  { "page_id": 12 }, { "question": "..."} (optionnel)
        search        → { "query": "..." }
        create        → { "path": "...", "title": "...", "prompt": "...", "context": "..."(optionnel) }
        update        → { "path": "..." } ou { "page_id": 12 }, { "instruction": "..." }
        batch_create  → { "items": [ {path, title, prompt, context, tags}, ... ] }
    """

    MCP_SERVER = "wikijs"

    def __init__(
        self,
        agent_id: UUID,
        user_id: UUID,
        config: Dict[str, Any],
        mcp_config: Dict[str, Any],
        db: Session,
    ):
        super().__init__(agent_id, user_id, config, mcp_config, db)
        self.mode = config.get("mode", "read")
        self.default_locale = config.get("default_locale", "en")
        self.default_tags = config.get("default_tags", [])
        # Convention du projet (cf. gitea_ansible_role_generator) : provider/modèle
        # figés dans la config de l'agent plutôt que de dépendre du provider actif
        # "par défaut" de l'utilisateur, qui peut changer ailleurs sans prévenir.
        self.llm_provider = config.get("llm_provider")
        self.llm_model = config.get("llm_model")
        self.llm_temperature = config.get("llm_temperature", 0.7)

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #

    async def execute(self, input_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        mode = input_data.get("mode", self.mode)

        self.log("info", f"WikiJSAgent starting — mode={mode}")
        yield self._progress("init", f"Mode d'exécution : {mode}")

        try:
            if mode == "read":
                async for update in self._workflow_read(input_data):
                    yield update

            elif mode == "search":
                async for update in self._workflow_search(input_data):
                    yield update

            elif mode == "create":
                async for update in self._workflow_create(input_data):
                    yield update

            elif mode == "update":
                async for update in self._workflow_update(input_data):
                    yield update

            elif mode == "batch_create":
                async for update in self._workflow_batch_create(input_data):
                    yield update

            else:
                yield self._error(
                    f"Unknown mode: {mode}. Expected: read|search|create|update|batch_create"
                )

        except Exception as exc:
            self.log("error", f"WikiJSAgent failed: {exc}")
            yield self._error(str(exc))

    # ------------------------------------------------------------------ #
    # Workflows
    # ------------------------------------------------------------------ #

    async def _workflow_read(self, input_data: Dict[str, Any]):
        """Charge une page existante et, en option, répond à une question dessus."""
        path = input_data.get("path")
        page_id = input_data.get("page_id")
        question = input_data.get("question")

        if not path and not page_id:
            yield self._error("Provide 'path' or 'page_id' for mode=read")
            return

        # Surchargeable par appel : évite de devoir recréer l'agent si le wiki
        # n'est pas dans la locale par défaut de la config.
        locale = input_data.get("locale", self.default_locale)

        yield self._progress("fetch_page", f"Lecture de la page : {path or page_id}")
        page = await self.call_mcp(self.MCP_SERVER, "get_page", {
            "page_id": page_id,
            "path": path,
            "locale": locale,
        })

        if not page:
            yield self._error(f"Page introuvable (path={path}, id={page_id})")
            return

        self.log("info", f"✅ Page loaded: {page['path']} ({len(page.get('content', ''))} chars)")

        yield self._progress("llm", "Analyse LLM du contenu...")
        analysis = await self._llm_analyze_page(page, question)

        yield {
            "type": "result",
            "data": {
                "mode": "read",
                "page": self._slim_page(page),
                "question": question,
                "analysis": analysis,
                "metadata": {"timestamp": datetime.utcnow().isoformat()},
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _workflow_search(self, input_data: Dict[str, Any]):
        query = input_data.get("query")
        if not query:
            yield self._error("Missing 'query' for mode=search")
            return

        # Pas de filtre locale par défaut : on cherche dans tout le wiki.
        # Ne filtrer que si explicitement demandé (input_data["locale"]),
        # car forcer default_locale ferait remonter 0 résultat sur un wiki
        # mono-langue dont la locale diffère de default_locale.
        locale = input_data.get("locale")

        yield self._progress("search", f"Recherche : « {query} »")
        result = await self.call_mcp(self.MCP_SERVER, "search_pages", {
            "query_text": query,
            "locale": locale,
        })

        yield {
            "type": "result",
            "data": {
                "mode": "search",
                "query": query,
                "total_hits": result.get("totalHits", 0),
                "results": result.get("results", []),
                "suggestions": result.get("suggestions", []),
                "metadata": {"timestamp": datetime.utcnow().isoformat()},
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _workflow_create(self, input_data: Dict[str, Any]):
        """Génère le contenu d'une page via LLM à partir d'un prompt, puis la publie."""
        path = input_data.get("path")
        title = input_data.get("title")
        prompt = input_data.get("prompt")

        if not path or not title or not prompt:
            yield self._error("Provide 'path', 'title' and 'prompt' for mode=create")
            return

        context = input_data.get("context", "")
        tags = input_data.get("tags", self.default_tags)
        description = input_data.get("description", "")

        yield self._progress("llm", "Génération du contenu par le LLM...")
        content = await self._llm_generate_page(title=title, prompt=prompt, context=context)

        yield self._progress("publish", f"Publication sur WikiJS : {path}")
        page = await self.call_mcp(self.MCP_SERVER, "upsert_page", {
            "path": path,
            "title": title,
            "content": content,
            "description": description or prompt[:150],
            "tags": tags,
            "locale": self.default_locale,
        })

        self.log("info", f"✅ Page publiée : {page['path']} (id={page['id']})")

        yield {
            "type": "result",
            "data": {
                "mode": "create",
                "page": page,
                "content_preview": content[:300],
                "metadata": {"timestamp": datetime.utcnow().isoformat()},
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _workflow_update(self, input_data: Dict[str, Any]):
        """Modifie une page existante via une instruction en langage naturel."""
        path = input_data.get("path")
        page_id = input_data.get("page_id")
        instruction = input_data.get("instruction")

        if (not path and not page_id) or not instruction:
            yield self._error("Provide ('path' or 'page_id') and 'instruction' for mode=update")
            return

        yield self._progress("fetch_page", "Lecture de la page actuelle...")
        current = await self.call_mcp(self.MCP_SERVER, "get_page", {
            "page_id": page_id, "path": path, "locale": self.default_locale,
        })
        if not current:
            yield self._error(f"Page introuvable (path={path}, id={page_id})")
            return

        yield self._progress("llm", "Réécriture du contenu par le LLM...")
        new_content = await self._llm_revise_page(current, instruction)

        yield self._progress("publish", f"Mise à jour : {current['path']}")
        page = await self.call_mcp(self.MCP_SERVER, "update_page", {
            "page_id": current["id"],
            "content": new_content,
        })

        self.log("info", f"✅ Page mise à jour : {page['path']} (id={page['id']})")

        yield {
            "type": "result",
            "data": {
                "mode": "update",
                "page": page,
                "instruction": instruction,
                "content_preview": new_content[:300],
                "metadata": {"timestamp": datetime.utcnow().isoformat()},
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _workflow_batch_create(self, input_data: Dict[str, Any]):
        """
        Génère N pages en une seule exécution : une entrée = un besoin = une page.
        Chaque item est traité indépendamment ; un échec sur un item n'interrompt
        pas les suivants (le rapport final liste succès/échecs).
        """
        items: List[Dict[str, Any]] = input_data.get("items", [])
        if not items:
            yield self._error("Missing 'items' (list) for mode=batch_create")
            return

        yield self._progress("batch_start", f"{len(items)} page(s) à générer")

        created, failed = [], []

        for idx, item in enumerate(items, start=1):
            path = item.get("path")
            title = item.get("title")
            prompt = item.get("prompt")

            if not path or not title or not prompt:
                failed.append({"index": idx, "error": "path/title/prompt manquant", "item": item})
                continue

            yield self._progress(
                "batch_item", f"[{idx}/{len(items)}] Génération : {title}"
            )

            try:
                content = await self._llm_generate_page(
                    title=title,
                    prompt=prompt,
                    context=item.get("context", ""),
                )
                page = await self.call_mcp(self.MCP_SERVER, "upsert_page", {
                    "path": path,
                    "title": title,
                    "content": content,
                    "description": item.get("description", prompt[:150]),
                    "tags": item.get("tags", self.default_tags),
                    "locale": item.get("locale", self.default_locale),
                })
                created.append(page)
                self.log("info", f"✅ [{idx}/{len(items)}] Page publiée : {page['path']}")

            except Exception as exc:
                failed.append({"index": idx, "error": str(exc), "path": path})
                self.log("error", f"❌ [{idx}/{len(items)}] Échec sur {path}: {exc}")

        yield {
            "type": "result",
            "data": {
                "mode": "batch_create",
                "requested": len(items),
                "created_count": len(created),
                "failed_count": len(failed),
                "created": created,
                "failed": failed,
                "metadata": {"timestamp": datetime.utcnow().isoformat()},
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------ #
    # LLM helpers
    # ------------------------------------------------------------------ #

    async def _llm_analyze_page(self, page: Dict[str, Any], question: Optional[str]) -> str:
        instruction = (
            f"Réponds précisément à cette question sur la page : « {question} »"
            if question else
            "Fais une synthèse claire de cette page (objectif, points clés, public visé) "
            "et signale les éventuelles incohérences ou parties incomplètes."
        )
        messages = [
            {
                "role": "system",
                "content": "Tu es un assistant technique qui aide à comprendre et exploiter "
                           "le contenu d'un wiki d'entreprise (Wiki.js).",
            },
            {
                "role": "user",
                "content": (
                    f"Titre : {page.get('title')}\n"
                    f"Path : {page.get('path')}\n"
                    f"Description : {page.get('description', '')}\n\n"
                    f"Contenu :\n{page.get('content', '')[:6000]}\n\n"
                    f"{instruction}"
                ),
            },
        ]
        return await self.call_llm(
            messages,
            provider_name=self.llm_provider,
            model=self.llm_model,
            temperature=self.llm_temperature,
            max_tokens=800,
        )

    async def _llm_generate_page(self, title: str, prompt: str, context: str = "") -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "Tu es un rédacteur technique. Tu écris des pages de documentation "
                    "pour un wiki d'entreprise (Wiki.js), au format Markdown. "
                    "Structure toujours avec des titres (##), des listes quand pertinent, "
                    "et des blocs de code si des commandes/config sont mentionnées. "
                    "Ne mets pas de titre H1 (le titre de la page est géré séparément)."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Titre de la page : {title}\n\n"
                    f"Besoin / instructions : {prompt}\n\n"
                    + (f"Contexte additionnel fourni :\n{context}\n\n" if context else "")
                    + "Rédige le contenu Markdown complet de cette page."
                ),
            },
        ]
        return await self.call_llm(
            messages,
            provider_name=self.llm_provider,
            model=self.llm_model,
            temperature=self.llm_temperature,
            max_tokens=2000,
        )

    async def _llm_revise_page(self, page: Dict[str, Any], instruction: str) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "Tu es un rédacteur technique. Tu modifies une page Wiki.js existante "
                    "au format Markdown en respectant strictement l'instruction donnée, "
                    "sans supprimer les sections non concernées."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Contenu actuel de la page « {page.get('title')} » :\n"
                    f"{page.get('content', '')}\n\n"
                    f"Instruction de modification : {instruction}\n\n"
                    "Retourne le contenu Markdown COMPLET mis à jour (pas de diff, pas de commentaire)."
                ),
            },
        ]
        return await self.call_llm(
            messages,
            provider_name=self.llm_provider,
            model=self.llm_model,
            temperature=self.llm_temperature,
            max_tokens=2500,
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _slim_page(p: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": p.get("id"),
            "path": p.get("path"),
            "title": p.get("title"),
            "description": p.get("description"),
            "locale": p.get("locale"),
            "isPublished": p.get("isPublished"),
            "tags": p.get("tags", []),
            "updatedAt": p.get("updatedAt"),
            "content_length": len(p.get("content", "") or ""),
        }

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