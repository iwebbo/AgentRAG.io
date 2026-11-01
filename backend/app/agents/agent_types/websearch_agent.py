import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WebSearchAgent(BaseAgent):
    """
    Agent de recherche web avec analyse LLM optionnelle.

    Pipeline:
        1. Recherche DuckDuckGo
        2. Extraction du contenu des pages (trafilatura)
        3. Analyse LLM par résultat (pertinence, résumé, points clés)
        4. Synthèse LLM globale (optionnelle)

    L'analyse LLM est "best effort": un échec LLM ne fait jamais échouer
    la recherche, les résultats bruts sont toujours retournés.

    search_config:
        max_results (10), language ("fr"), safe_search (True),
        extract_content (True), llm_analysis (True), analyze_top_n (5),
        max_content_chars (6000), synthesize (True),
        cleanup_conversations (True)

    config:
        llm_provider ("ollama"), llm_model ("mistral"), llm_temperature (0.3)
    """

    REGION_MAP = {
        "fr": "fr-fr",
        "en": "en-us",
        "de": "de-de",
        "es": "es-es",
        "it": "it-it",
        "pt": "pt-pt",
    }

    ANALYSIS_SYSTEM_PROMPT = (
        "Tu es un analyste de recherche rigoureux. Tu évalues des contenus web "
        "par rapport à une requête, sans inventer d'information absente du contenu. "
        "Tu réponds uniquement en JSON valide."
    )

    SYNTHESIS_SYSTEM_PROMPT = (
        "Tu es un analyste de recherche rigoureux. Tu produis des synthèses "
        "factuelles basées uniquement sur les sources fournies, en citant leur numéro."
    )

    def __init__(
        self,
        agent_id: UUID,
        user_id: UUID,
        config: Dict[str, Any],
        mcp_config: Dict[str, Any],
        db: Session,
    ):
        super().__init__(agent_id, user_id, config, mcp_config, db)

        # Configuration recherche
        self.search_config = config.get("search_config", {})
        self.max_results = self.search_config.get("max_results", 10)
        self.language = self.search_config.get("language", "fr")
        self.safe_search = self.search_config.get("safe_search", True)
        self.extract_content = self.search_config.get("extract_content", True)

        # Configuration analyse LLM
        self.llm_analysis = self.search_config.get("llm_analysis", True)
        self.analyze_top_n = self.search_config.get("analyze_top_n", 5)
        self.max_content_chars = self.search_config.get("max_content_chars", 6000)
        self.synthesize = self.search_config.get("synthesize", True)
        self.cleanup_conversations = self.search_config.get("cleanup_conversations", True)

        # Configuration LLM
        self.llm_provider = config.get("llm_provider", "ollama")
        self.llm_model = config.get("llm_model", "mistral")
        self.llm_temperature = config.get("llm_temperature", 0.3)

    # ------------------------------------------------------------------ #
    # Exécution
    # ------------------------------------------------------------------ #
    async def execute(self, input_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Exécute une recherche web approfondie avec analyse LLM.

        Input:
            {
                "query": "FastAPI tutoriel français",
                "max_results": 10,        # optionnel
                "language": "fr",         # optionnel
                "extract_content": true,  # optionnel
                "llm_analysis": true,     # optionnel
                "synthesize": true        # optionnel
            }

        Output (type "result"):
            {
                "query": ..., "results_count": ..., "results": [
                    {title, url, snippet, content, ...,
                     "llm_analysis": {relevance, summary, key_points, answers_query} | None}
                ],
                "synthesis": str | None,
                "metadata": {...}
            }
        """
        query = input_data.get("query")
        if not query:
            yield {
                "type": "error",
                "data": {"error": "Missing 'query' in input_data"},
                "timestamp": _now(),
            }
            return

        max_results = input_data.get("max_results", self.max_results)
        language = input_data.get("language", self.language)
        extract_content = input_data.get("extract_content", self.extract_content)
        llm_analysis = input_data.get("llm_analysis", self.llm_analysis)
        synthesize = input_data.get("synthesize", self.synthesize)

        self.log("info", f" Web search: {query}")
        yield {"type": "log", "data": {"message": f"Recherche: {query}"}, "timestamp": _now()}

        try:
            # 1. Recherche DuckDuckGo
            self.log("info", " Searching DuckDuckGo...")
            yield {
                "type": "progress",
                "data": {"step": "search", "message": f"Recherche de {max_results} résultats..."},
                "timestamp": _now(),
            }

            search_results = await self._duckduckgo_search(query, max_results, language)

            if not search_results:
                yield {
                    "type": "result",
                    "data": {
                        "query": query,
                        "results_count": 0,
                        "results": [],
                        "synthesis": None,
                        "message": "Aucun résultat trouvé",
                        "metadata": {"language": language, "timestamp": _now()},
                    },
                    "timestamp": _now(),
                }
                return

            self.log("info", f" Found {len(search_results)} results")

            # 2. Extraction contenu (optionnel)
            if extract_content:
                self.log("info", " Extracting content...")
                yield {
                    "type": "progress",
                    "data": {"step": "extract", "message": "Extraction du contenu des pages..."},
                    "timestamp": _now(),
                }
                search_results = await self._extract_content(search_results)

            # 3. Analyse LLM par résultat (optionnel, best effort)
            synthesis: Optional[str] = None
            analyzed_count = 0
            llm_available = llm_analysis and getattr(self, "llm_service", None) is not None

            if llm_analysis and not llm_available:
                self.log("warning", " llm_service unavailable, skipping LLM analysis")

            if llm_available:
                to_analyze = search_results[: max(0, self.analyze_top_n)]
                for idx, result in enumerate(to_analyze, 1):
                    yield {
                        "type": "progress",
                        "data": {
                            "step": "analyze",
                            "message": f"Analyse LLM {idx}/{len(to_analyze)}: {result.get('title', '')[:60]}",
                        },
                        "timestamp": _now(),
                    }
                    result["llm_analysis"] = await self._analyze_result(query, result)
                    if result["llm_analysis"] is not None:
                        analyzed_count += 1

                # 4. Synthèse globale (optionnel)
                if synthesize and analyzed_count > 0:
                    yield {
                        "type": "progress",
                        "data": {"step": "synthesize", "message": "Synthèse des résultats..."},
                        "timestamp": _now(),
                    }
                    synthesis = await self._synthesize(query, search_results)

            # 5. Résultat
            result_payload = {
                "query": query,
                "results_count": len(search_results),
                "results": search_results,
                "synthesis": synthesis,
                "metadata": {
                    "language": language,
                    "safe_search": self.safe_search,
                    "content_extracted": extract_content,
                    "llm_analysis": bool(llm_available),
                    "llm_analyzed_count": analyzed_count,
                    "llm_provider": self.llm_provider if llm_available else None,
                    "llm_model": self.llm_model if llm_available else None,
                    "timestamp": _now(),
                },
            }

            self.log("info", f" Search completed: {len(search_results)} results")
            yield {"type": "result", "data": result_payload, "timestamp": _now()}

        except Exception as e:
            self.log("error", f" Search failed: {str(e)}")
            yield {
                "type": "error",
                "data": {"error": str(e), "query": query},
                "timestamp": _now(),
            }

    # ------------------------------------------------------------------ #
    # Recherche
    # ------------------------------------------------------------------ #
    async def _duckduckgo_search(
        self, query: str, max_results: int, language: str
    ) -> List[Dict[str, Any]]:
        """Recherche DuckDuckGo (appel bloquant exécuté hors event loop)."""
        region = self.REGION_MAP.get(language, "wt-wt")
        safesearch = "moderate" if self.safe_search else "off"
        logger.info(f"🔍 DuckDuckGo search: query='{query}', max={max_results}, region={region}")

        def _search() -> List[Dict[str, Any]]:
            from ddgs import DDGS

            with DDGS() as ddgs:
                raw = ddgs.text(
                    query,
                    max_results=max_results,
                    region=region,
                    safesearch=safesearch,
                )
                return [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", ""),
                        "source": "duckduckgo",
                    }
                    for r in raw
                ]

        try:
            results = await asyncio.to_thread(_search)
            logger.info(f" DuckDuckGo: {len(results)} results found")
            return results
        except ImportError:
            logger.error(" ddgs not installed (pip install ddgs)")
            return []
        except Exception as e:
            logger.error(f" DuckDuckGo search failed: {e}")
            return []

    # ------------------------------------------------------------------ #
    # Extraction
    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract_one_sync(url: str) -> Optional[str]:
        """Télécharge et extrait le contenu principal d'une page (bloquant)."""
        from trafilatura import extract, fetch_url
        from trafilatura.settings import use_config

        cfg = use_config()
        cfg.set("DEFAULT", "DOWNLOAD_TIMEOUT", "10")

        downloaded = fetch_url(url, config=cfg)
        if not downloaded:
            return None
        return extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            include_links=False,
            no_fallback=False,
        )

    @staticmethod
    def _apply_snippet_fallback(result: Dict[str, Any]) -> None:
        snippet = result.get("snippet", "")
        result["content"] = snippet
        result["content_length"] = len(snippet)
        result["extraction_success"] = False

    async def _extract_content(self, search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrichit les résultats avec 'content', 'content_length', 'extraction_success'."""
        for idx, result in enumerate(search_results, 1):
            logger.info(f" Extracting content {idx}/{len(search_results)}: {result['url']}")
            try:
                content = await asyncio.to_thread(self._extract_one_sync, result["url"])
                if content and len(content) > 50:
                    result["content"] = content
                    result["content_length"] = len(content)
                    result["extraction_success"] = True
                else:
                    logger.warning(f" Extraction empty, using snippet for {result.get('title')}")
                    self._apply_snippet_fallback(result)
            except ImportError:
                logger.warning(" trafilatura not installed. Using snippets only.")
                self._apply_snippet_fallback(result)
            except Exception as e:
                logger.warning(f" Content extraction failed for {result['url']}: {e}")
                self._apply_snippet_fallback(result)

        success = sum(1 for r in search_results if r.get("extraction_success"))
        logger.info(f" Content extraction: {success}/{len(search_results)} successful")
        return search_results

    # ------------------------------------------------------------------ #
    # LLM
    # ------------------------------------------------------------------ #
    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """
        Appel LLM via llm_service.stream_chat avec conversation temporaire.
        La conversation est supprimée ensuite si cleanup_conversations=True.
        """
        from app.models import Conversation, Message as MessageModel

        conv = Conversation(
            user_id=self.user_id,
            title=f"WebSearch Analysis: {user_prompt[:40]}",
            provider_name=self.llm_provider,
            model=self.llm_model,
            temperature=self.llm_temperature,
        )
        self.db.add(conv)
        self.db.flush()
        conv_id = conv.id

        self.db.add(MessageModel(conversation_id=conv_id, role="system", content=system_prompt))
        self.db.add(MessageModel(conversation_id=conv_id, role="user", content=user_prompt))
        self.db.commit()

        response = ""
        try:
            async for chunk in self.llm_service.stream_chat(
                self.user_id,
                conv_id,
                "",
                self.llm_provider,
                self.llm_model,
                self.llm_temperature,
            ):
                if chunk:
                    response += chunk
        finally:
            if self.cleanup_conversations:
                self._cleanup_conversation(conv_id)

        return response.strip()

    def _cleanup_conversation(self, conv_id: Any) -> None:
        """Supprime la conversation temporaire (best effort)."""
        try:
            from app.models import Conversation, Message as MessageModel

            self.db.query(MessageModel).filter(MessageModel.conversation_id == conv_id).delete(
                synchronize_session=False
            )
            self.db.query(Conversation).filter(Conversation.id == conv_id).delete(
                synchronize_session=False
            )
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.warning(f"⚠️ Temp conversation cleanup failed: {e}")

    def _truncate(self, text: str) -> str:
        text = text or ""
        if len(text) <= self.max_content_chars:
            return text
        return text[: self.max_content_chars] + "\n[... contenu tronqué ...]"

    def _build_analysis_prompt(self, query: str, result: Dict[str, Any]) -> str:
        content = self._truncate(result.get("content") or result.get("snippet", ""))
        return (
            f"Requête de recherche: {query}\n\n"
            f"Titre: {result.get('title', '')}\n"
            f"URL: {result.get('url', '')}\n\n"
            f"Contenu:\n{content}\n\n"
            "Analyse ce contenu par rapport à la requête. Réponds UNIQUEMENT avec un JSON:\n"
            '{"relevance": <entier 0-10>, '
            '"answers_query": <true|false>, '
            '"summary": "<résumé en 2-4 phrases centré sur la requête>", '
            '"key_points": ["<point clé>", ...]}'
        )

    @staticmethod
    def _parse_analysis(raw: str) -> Optional[Dict[str, Any]]:
        """Parse robuste de la réponse JSON du LLM (gère ```json et texte autour)."""
        if not raw:
            return None
        text = re.sub(r"```(?:json)?", "", raw).strip()
        start, end = text.find("{"), text.rfind("}")
        data: Optional[Dict[str, Any]] = None
        if start != -1 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
                if isinstance(parsed, dict):
                    data = parsed
            except json.JSONDecodeError:
                data = None

        if data is None:
            # Fallback: réponse non-JSON conservée comme résumé
            return {
                "relevance": None,
                "answers_query": None,
                "summary": raw[:1000],
                "key_points": [],
                "parsed": False,
            }

        try:
            relevance = int(data.get("relevance")) if data.get("relevance") is not None else None
        except (TypeError, ValueError):
            relevance = None
        if relevance is not None:
            relevance = max(0, min(10, relevance))

        key_points = data.get("key_points", [])
        if not isinstance(key_points, list):
            key_points = [str(key_points)]

        return {
            "relevance": relevance,
            "answers_query": data.get("answers_query"),
            "summary": str(data.get("summary", "")),
            "key_points": [str(k) for k in key_points],
            "parsed": True,
        }

    async def _analyze_result(self, query: str, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyse LLM d'un résultat. Retourne None en cas d'échec (jamais d'exception)."""
        try:
            raw = await self._call_llm(
                self.ANALYSIS_SYSTEM_PROMPT, self._build_analysis_prompt(query, result)
            )
            return self._parse_analysis(raw)
        except Exception as e:
            logger.warning(f" LLM analysis failed for {result.get('url')}: {e}")
            try:
                self.db.rollback()
            except Exception:
                pass
            return None

    async def _synthesize(self, query: str, results: List[Dict[str, Any]]) -> Optional[str]:
        """Synthèse globale à partir des analyses par résultat (best effort)."""
        sources = []
        for idx, r in enumerate(results, 1):
            analysis = r.get("llm_analysis")
            if not analysis:
                continue
            points = "; ".join(analysis.get("key_points", []))
            sources.append(
                f"[{idx}] {r.get('title', '')} ({r.get('url', '')})\n"
                f"Pertinence: {analysis.get('relevance')}/10\n"
                f"Résumé: {analysis.get('summary', '')}\n"
                f"Points clés: {points}"
            )
        if not sources:
            return None

        prompt = (
            f"Requête: {query}\n\nSources analysées:\n\n"
            + "\n\n".join(sources)
            + "\n\nRédige une synthèse structurée répondant à la requête. "
            "Cite les sources par leur numéro [n]. Signale les contradictions "
            "et les limites des sources."
        )
        try:
            return await self._call_llm(self.SYNTHESIS_SYSTEM_PROMPT, prompt) or None
        except Exception as e:
            logger.warning(f" LLM synthesis failed: {e}")
            try:
                self.db.rollback()
            except Exception:
                pass
            return None