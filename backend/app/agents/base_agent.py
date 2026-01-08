from abc import ABC, abstractmethod
from typing import Dict, Any, List, AsyncGenerator, Optional
from uuid import UUID
from sqlalchemy.orm import Session
import logging
from datetime import datetime

from app.models import Project
from app.services.embeddings import EmbeddingManager
from app.services.vector_store import VectorStore
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Classe de base abstraite pour tous les agents.
    
    Architecture extensible et MCP-ready.
    Chaque agent hérite de cette classe et implémente execute().
    """
    
    def __init__(
        self,
        agent_id: UUID,
        user_id: UUID,
        config: Dict[str, Any],
        mcp_config: Dict[str, Any],
        db: Session
    ):
        """
        Args:
            agent_id: ID de l'agent
            user_id: ID de l'utilisateur propriétaire
            config: Configuration de l'agent (project_id, mcp_servers, workflow, etc.)
            mcp_config: Credentials MCP (GitHub tokens, Jira API keys, etc.)
            db: Session SQLAlchemy
        """
        self.agent_id = agent_id
        self.user_id = user_id
        self.config = config
        self.mcp_config = mcp_config
        self.db = db
        
        # Extract common config
        self.project_id = config.get("project_id")
        self.mcp_servers = config.get("mcp_servers", [])
        self.timeout_seconds = config.get("timeout_seconds", 300)
        self.max_retries = config.get("max_retries", 3)
        
        # Initialize services
        self.embeddings = EmbeddingManager()
        self.vector_store = VectorStore()
        self.llm_service = LLMService(db)
        
        # MCP client will be set by executor
        self.mcp_client = None
        
        # Execution state
        self.logs: List[Dict[str, Any]] = []
        self.tokens_used = 0
        self.mcp_calls_count: Dict[str, int] = {}
        
        logger.info(f"Agent {self.agent_id} initialized with config: {config}")
    
    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Exécute la tâche de l'agent.
        
        Cette méthode DOIT être implémentée par chaque agent.
        Elle yield des updates progressifs pour le tracking en temps réel.
        
        Args:
            input_data: Données d'entrée pour l'agent
            
        Yields:
            Dict contenant des updates progressifs:
            {
                "type": "log|progress|result|error",
                "data": {...},
                "timestamp": "..."
            }
        """
        pass
    
    async def get_rag_context(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Récupère le contexte RAG depuis le projet lié.
        
        Args:
            query: Query de recherche sémantique
            top_k: Nombre de résultats à retourner
            
        Returns:
            Liste de chunks pertinents avec metadata
        """
        if not self.project_id:
            logger.warning("No project_id configured, skipping RAG context")
            return []
        
        # Vérifier que le projet existe et appartient à l'user
        project = self.db.query(Project).filter(
            Project.id == self.project_id,
            Project.user_id == self.user_id
        ).first()
        
        if not project:
            logger.error(f"Project {self.project_id} not found or unauthorized")
            return []
        
        try:
            # Générer embedding de la query
            query_embedding = self.embeddings.encode_single(query)
            
            # Search dans le vectorstore
            results = self.vector_store.query(
                project_id=str(self.project_id),
                query_embedding=query_embedding,
                n_results=top_k
            )
            
            # Format results
            chunks = []
            if results and results.get('documents'):
                for i, doc in enumerate(results['documents'][0]):
                    chunks.append({
                        'content': doc,
                        'metadata': results['metadatas'][0][i] if results.get('metadatas') else {},
                        'distance': results['distances'][0][i] if results.get('distances') else None
                    })
            
            logger.info(f"Retrieved {len(chunks)} RAG chunks for query: {query[:50]}...")
            return chunks
            
        except Exception as e:
            logger.error(f"Error retrieving RAG context: {str(e)}")
            return []
    
    async def call_mcp(self, server: str, method: str, params: Dict[str, Any]) -> Any:
        """
        Appelle un MCP server de manière sécurisée.
        
        Args:
            server: Nom du MCP server (github, jira, slack, etc.)
            method: Méthode à appeler (get_pr, create_comment, etc.)
            params: Paramètres de la méthode
            
        Returns:
            Résultat de l'appel MCP
            
        Raises:
            ValueError: Si le server n'est pas activé pour cet agent
            Exception: Si l'appel MCP échoue
        """
        if server not in self.mcp_servers:
            raise ValueError(f"MCP server '{server}' not enabled for this agent")
        
        if not self.mcp_client:
            raise RuntimeError("MCP client not initialized")
        
        # Track MCP calls
        self.mcp_calls_count[server] = self.mcp_calls_count.get(server, 0) + 1
        
        logger.info(f"Calling MCP {server}.{method} with params: {params}")
        
        try:
            result = await self.mcp_client.call(server, method, params)
            logger.info(f"MCP {server}.{method} succeeded")
            return result
        except Exception as e:
            logger.error(f"MCP {server}.{method} failed: {str(e)}")
            raise
    
    async def call_llm(
        self,
        messages: List[Dict[str, str]],
        provider_name: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        """
        Appelle le LLM via LLMService.
        
        Args:
            messages: Messages au format OpenAI [{"role": "...", "content": "..."}]
            provider_name: Provider à utiliser (optionnel, utilise le premier actif)
            model: Modèle à utiliser (optionnel, utilise celui du provider)
            temperature: Température (0.0 - 1.0)
            max_tokens: Nombre max de tokens
            
        Returns:
            Réponse du LLM (texte complet)
        """
        from app.models import Conversation, Message as MessageModel
        from datetime import datetime
        
        # Get active provider
        provider = await self.llm_service.get_active_provider(
            user_id=self.user_id,
            provider_name=provider_name
        )
        
        if not provider:
            raise ValueError(f"No active provider found (requested: {provider_name})")
        
        # Use model from provider config if not specified
        if not model:
            model = provider.config.get("model") or provider.config.get("default_model")
        
        if not model:
            raise ValueError(f"No model specified and no default model in provider {provider.name}")
        
        logger.info(f"Calling LLM: provider={provider.name}, model={model}, temp={temperature}")
        
        # Create temporary conversation for agent
        conversation = Conversation(
            user_id=self.user_id,
            title=f"Agent {self.agent_id} - LLM Call",
            provider_name=provider.name,  # ✅ FIX: Ajouter provider_name
            model=model,                   # ✅ FIX: Ajouter model
            temperature=temperature
        )
        self.db.add(conversation)
        self.db.flush()
        
        # Add messages to conversation
        for msg in messages:
            db_message = MessageModel(
                conversation_id=conversation.id,
                role=msg["role"],
                content=msg["content"]
            )
            self.db.add(db_message)
        
        self.db.commit()
        
        # Call LLM via streaming (but collect full response)
        full_response = ""
        total_tokens = 0
        
        async for chunk in self.llm_service.stream_chat(
            user_id=self.user_id,
            conversation_id=conversation.id,
            message="",  # Message already added to conversation
            provider_name=provider.name,
            model=model,
            temperature=temperature
        ):
            # stream_chat yields raw text chunks
            full_response += chunk
        
        # Estimate tokens (stream_chat doesn't return token count directly)
        from app.services.llm_service import estimate_tokens
        self.tokens_used += estimate_tokens(full_response)
        
        logger.info(f"LLM response received ({len(full_response)} chars, ~{self.tokens_used} tokens)")
        
        return full_response
    
    def log(self, level: str, message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Créer un log structuré pour l'exécution.
        
        Args:
            level: Niveau de log (info, debug, warning, error)
            message: Message du log
            data: Données additionnelles (optionnel)
            
        Returns:
            Log structuré
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message
        }
        
        if data:
            log_entry["data"] = data
        
        self.logs.append(log_entry)
        
        # Log aussi dans les logs système
        log_func = getattr(logger, level, logger.info)
        log_func(f"[Agent {self.agent_id}] {message}")
        
        return log_entry
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """
        Génère un résumé de l'exécution.
        
        Returns:
            Résumé avec metrics et logs
        """
        return {
            "logs": self.logs,
            "tokens_used": self.tokens_used,
            "mcp_calls": self.mcp_calls_count,
            "total_mcp_calls": sum(self.mcp_calls_count.values())
        }