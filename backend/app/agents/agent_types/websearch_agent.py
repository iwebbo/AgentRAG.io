from typing import Dict, Any, List, AsyncGenerator, Optional
from uuid import UUID
from sqlalchemy.orm import Session
import logging
from datetime import datetime
from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class WebSearchAgent(BaseAgent):
    """
    Agent de recherche web - Résultats bruts.
    
    Features:
    - Recherche DuckDuckGo approfondie
    - Extraction contenu complet
    - Résultats bruts sans analyse LLM
    - Rapide et précis
    """
    
    def __init__(
        self,
        agent_id: UUID,
        user_id: UUID,
        config: Dict[str, Any],
        mcp_config: Dict[str, Any],
        db: Session
    ):
        super().__init__(agent_id, user_id, config, mcp_config, db)
        
        # Configuration recherche
        self.search_config = config.get("search_config", {})
        self.max_results = self.search_config.get("max_results", 10)
        self.language = self.search_config.get("language", "fr")
        self.safe_search = self.search_config.get("safe_search", True)
        self.extract_content = self.search_config.get("extract_content", True)
    
    async def execute(self, input_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Exécute une recherche web approfondie.
        
        Input:
            {
                "query": "FastAPI tutoriel français",
                "max_results": 10,     # optionnel
                "language": "fr",      # optionnel
                "extract_content": true # optionnel
            }
        
        Output:
            {
                "type": "result",
                "data": {
                    "query": "FastAPI tutoriel français",
                    "results_count": 10,
                    "results": [
                        {
                            "title": "...",
                            "url": "...",
                            "snippet": "...",
                            "content": "..." // si extract_content=true
                        }
                    ],
                    "metadata": {...}
                }
            }
        """
        query = input_data.get("query")
        if not query:
            yield {
                "type": "error",
                "data": {"error": "Missing 'query' in input_data"},
                "timestamp": datetime.utcnow().isoformat()
            }
            return
        
        # Override config si fourni
        max_results = input_data.get("max_results", self.max_results)
        language = input_data.get("language", self.language)
        extract_content = input_data.get("extract_content", self.extract_content)
        
        self.log("info", f"🔍 Web search: {query}")
        yield {
            "type": "log",
            "data": {"message": f"Recherche: {query}"},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            # 1. Recherche DuckDuckGo
            self.log("info", "🌐 Searching DuckDuckGo...")
            yield {
                "type": "progress",
                "data": {
                    "step": "search",
                    "message": f"Recherche de {max_results} résultats..."
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            search_results = await self._duckduckgo_search(
                query,
                max_results,
                language
            )
            
            if not search_results:
                yield {
                    "type": "result",
                    "data": {
                        "query": query,
                        "results_count": 0,
                        "results": [],
                        "message": "Aucun résultat trouvé",
                        "metadata": {
                            "language": language,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
                return
            
            self.log("info", f"✅ Found {len(search_results)} results")
            
            # 2. Extraction contenu (optionnel)
            if extract_content:
                self.log("info", "📄 Extracting content...")
                yield {
                    "type": "progress",
                    "data": {
                        "step": "extract",
                        "message": "Extraction du contenu des pages..."
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                search_results = await self._extract_content(search_results)
            
            # 3. Retourner résultats bruts
            result = {
                "query": query,
                "results_count": len(search_results),
                "results": search_results,
                "metadata": {
                    "language": language,
                    "safe_search": self.safe_search,
                    "content_extracted": extract_content,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            
            self.log("info", f"✅ Search completed: {len(search_results)} results")
            yield {
                "type": "result",
                "data": result,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.log("error", f"❌ Search failed: {str(e)}")
            yield {
                "type": "error",
                "data": {"error": str(e), "query": query},
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _duckduckgo_search(
        self,
        query: str,
        max_results: int,
        language: str
    ) -> List[Dict[str, Any]]:
        """
        Recherche DuckDuckGo approfondie.
        
        Returns:
            Liste de résultats avec title, url, snippet
        """
        try:
            from duckduckgo_search import DDGS
            
            results = []
            
            # Region code pour la langue
            region_map = {
                "fr": "fr-fr",
                "en": "en-us",
                "de": "de-de",
                "es": "es-es",
                "it": "it-it",
                "pt": "pt-pt"
            }
            region = region_map.get(language, "wt-wt")
            
            logger.info(f"🔍 DuckDuckGo search: query='{query}', max={max_results}, region={region}")
            
            with DDGS() as ddgs:
                search_results = ddgs.text(
                    query,
                    max_results=max_results,
                    region=region,
                    safesearch="moderate" if self.safe_search else "off"
                )
                
                for r in search_results:
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", ""),
                        "source": "duckduckgo"
                    })
            
            logger.info(f"✅ DuckDuckGo: {len(results)} results found")
            return results
            
        except ImportError:
            logger.error("❌ duckduckgo-search not installed")
            logger.error("Run: pip install duckduckgo-search --break-system-packages")
            return []
        except Exception as e:
            logger.error(f"❌ DuckDuckGo search failed: {e}")
            return []
    
    async def _extract_content(
        self,
        search_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extrait le contenu complet des pages web.
        
        Args:
            search_results: Liste des résultats avec url
            
        Returns:
            Résultats enrichis avec 'content' et 'content_length'
        """
        enriched_results = []
        
        for idx, result in enumerate(search_results, 1):
            try:
                logger.info(f"📄 Extracting content {idx}/{len(search_results)}: {result['url']}")
                
                # Import dynamique
                from trafilatura import fetch_url, extract
                
                # Fetch avec timeout
                downloaded = fetch_url(result["url"], timeout=10)
                
                if downloaded:
                    # Extraction du contenu principal
                    content = extract(
                        downloaded,
                        include_comments=False,
                        include_tables=True,
                        include_links=False,
                        no_fallback=False
                    )
                    
                    if content and len(content) > 50:
                        result["content"] = content
                        result["content_length"] = len(content)
                        result["extraction_success"] = True
                        logger.info(f"✅ Extracted {len(content)} chars from {result['title']}")
                    else:
                        # Fallback sur snippet
                        result["content"] = result["snippet"]
                        result["content_length"] = len(result["snippet"])
                        result["extraction_success"] = False
                        logger.warning(f"⚠️ Extraction failed, using snippet for {result['title']}")
                else:
                    # Fallback sur snippet
                    result["content"] = result["snippet"]
                    result["content_length"] = len(result["snippet"])
                    result["extraction_success"] = False
                    logger.warning(f"⚠️ Download failed for {result['url']}")
                
                enriched_results.append(result)
            
            except ImportError:
                logger.warning("⚠️ trafilatura not installed. Using snippets only.")
                result["content"] = result["snippet"]
                result["content_length"] = len(result["snippet"])
                result["extraction_success"] = False
                enriched_results.append(result)
                
            except Exception as e:
                logger.warning(f"⚠️ Content extraction failed for {result['url']}: {e}")
                # Fallback sur snippet
                result["content"] = result["snippet"]
                result["content_length"] = len(result["snippet"])
                result["extraction_success"] = False
                enriched_results.append(result)
        
        success_count = sum(1 for r in enriched_results if r.get("extraction_success", False))
        logger.info(f"📊 Content extraction: {success_count}/{len(enriched_results)} successful")
        
        return enriched_results