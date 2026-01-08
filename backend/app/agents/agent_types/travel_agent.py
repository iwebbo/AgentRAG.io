"""
Agent de Voyage - Expert Organisation Voyages
==============================================

MODES DISPONIBLES:
- destination_search      : Recherche destinations personnalisées
- itinerary_planning      : Planification itinéraire jour par jour
- budget_optimization     : Optimisation et répartition budget
- activity_recommendations: Recommandations activités locales
- travel_analysis         : Analyse documents voyage (réservations, visas)
"""

from typing import Dict, Any, List, AsyncGenerator, Optional
from uuid import UUID
from datetime import datetime
import logging
from pathlib import Path

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class TravelAdvisorAgent(BaseAgent):
    """Agent Expert en Organisation de Voyages"""
    
    def __init__(self, agent_id: UUID, user_id: UUID, config: Dict[str, Any], mcp_config: Dict[str, Any], db: Any):
        super().__init__(agent_id, user_id, config, mcp_config, db)
        self.travel_config = config.get("travel_config", {})
        self.project_id = config.get("project_id")
    
    async def execute(self, input_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """Point d'entrée principal"""
        try:
            mode = input_data.get("mode", "destination_search")
            yield {"type": "status", "data": f"🌍 Mode {mode}"}
            
            handlers = {
                "destination_search": self._mode_destination_search,
                "itinerary_planning": self._mode_itinerary_planning,
                "budget_optimization": self._mode_budget_optimization,
                "activity_recommendations": self._mode_activity_recommendations,
                "travel_analysis": self._mode_travel_analysis
            }
            
            handler = handlers.get(mode)
            if not handler:
                raise ValueError(f"Mode inconnu: {mode}")
            
            async for update in handler(input_data):
                yield update
                
        except Exception as e:
            logger.error(f"Agent error: {str(e)}")
            yield {"type": "error", "data": str(e)}
            raise
    
    # ═══════════════════════════════════════════════════════
    # MODES MÉTIER
    # ═══════════════════════════════════════════════════════
    
    async def _mode_destination_search(self, input_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """Recherche destinations selon critères"""
        query = input_data.get("query", "")
        preferences = input_data.get("preferences", {})
        
        yield {"type": "status", "data": "🔍 Recherche destinations..."}
        
        # RAG context si project_id existe
        rag_context = ""
        if self.project_id:
            chunks = await self.get_rag_context(query, top_k=3)
            rag_context = "\n".join([c['content'] for c in chunks])
        
        # Load documents si fournis
        documents = input_data.get("documents", [])
        doc_context = await self._load_documents(documents)
        
        # Build prompt
        prompt = self._build_destination_prompt(query, preferences, rag_context, doc_context)
        
        yield {"type": "status", "data": "💬 Appel LLM..."}
        
        # Créer conversation temporaire
        from app.models import Conversation, Message as MessageModel
        
        conv = Conversation(
            user_id=self.user_id,
            title=f"Travel Search: {query[:50]}",
            provider_name=self.config.get("llm_provider", "ollama"),
            model=self.config.get("llm_model", "mistral"),
            temperature=self.config.get("llm_temperature", 0.7)
        )
        self.db.add(conv)
        self.db.flush()
        
        system_msg = "Tu es un expert en voyage avec connaissance mondiale des destinations."
        self.db.add(MessageModel(conversation_id=conv.id, role="system", content=system_msg))
        self.db.add(MessageModel(conversation_id=conv.id, role="user", content=prompt))
        self.db.commit()
        
        # Appel LLM via stream_chat
        response = ""
        async for chunk in self.llm_service.stream_chat(
            self.user_id,
            conv.id,
            "",
            self.config.get("llm_provider", "ollama"),
            self.config.get("llm_model", "mistral"),
            self.config.get("llm_temperature", 0.7)
        ):
            if chunk:
                response += chunk
        
        yield {"type": "result", "data": {
            "success": True,
            "mode": "destination_search",
            "query": query,
            "response": response,
            "timestamp": datetime.utcnow().isoformat()
        }}
    
    async def _mode_itinerary_planning(self, input_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """Planification itinéraire détaillé"""
        query = input_data.get("query", "")
        preferences = input_data.get("preferences", {})
        
        yield {"type": "status", "data": "📅 Planification itinéraire..."}
        
        rag_context = ""
        if self.project_id:
            chunks = await self.get_rag_context(query, top_k=3)
            rag_context = "\n".join([c['content'] for c in chunks])
        
        documents = input_data.get("documents", [])
        doc_context = await self._load_documents(documents)
        
        prompt = self._build_itinerary_prompt(query, preferences, rag_context, doc_context)
        
        from app.models import Conversation, Message as MessageModel
        
        conv = Conversation(
            user_id=self.user_id,
            title=f"Itinerary: {query[:50]}",
            provider_name=self.config.get("llm_provider", "ollama"),
            model=self.config.get("llm_model", "mistral"),
            temperature=self.config.get("llm_temperature", 0.6)
        )
        self.db.add(conv)
        self.db.flush()
        
        self.db.add(MessageModel(conversation_id=conv.id, role="system", content="Tu es un planificateur de voyage expert."))
        self.db.add(MessageModel(conversation_id=conv.id, role="user", content=prompt))
        self.db.commit()
        
        response = ""
        async for chunk in self.llm_service.stream_chat(
            self.user_id, conv.id, "",
            self.config.get("llm_provider", "ollama"),
            self.config.get("llm_model", "mistral"),
            self.config.get("llm_temperature", 0.6)
        ):
            if chunk:
                response += chunk
        
        yield {"type": "result", "data": {
            "success": True,
            "mode": "itinerary_planning",
            "query": query,
            "itinerary": response,
            "timestamp": datetime.utcnow().isoformat()
        }}
    
    async def _mode_budget_optimization(self, input_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """Optimisation budget voyage"""
        query = input_data.get("query", "")
        preferences = input_data.get("preferences", {})
        budget_limit = preferences.get("budget", "non spécifié")
        
        yield {"type": "status", "data": "💰 Optimisation budget..."}
        
        rag_context = ""
        if self.project_id:
            chunks = await self.get_rag_context(query, top_k=3)
            rag_context = "\n".join([c['content'] for c in chunks])
        
        documents = input_data.get("documents", [])
        doc_context = await self._load_documents(documents)
        
        prompt = self._build_budget_prompt(query, budget_limit, rag_context, doc_context)
        
        from app.models import Conversation, Message as MessageModel
        
        conv = Conversation(
            user_id=self.user_id,
            title=f"Budget: {query[:50]}",
            provider_name=self.config.get("llm_provider", "ollama"),
            model=self.config.get("llm_model", "mistral"),
            temperature=self.config.get("llm_temperature", 0.5)
        )
        self.db.add(conv)
        self.db.flush()
        
        self.db.add(MessageModel(conversation_id=conv.id, role="system", content="Tu es un expert en optimisation de budgets voyage."))
        self.db.add(MessageModel(conversation_id=conv.id, role="user", content=prompt))
        self.db.commit()
        
        response = ""
        async for chunk in self.llm_service.stream_chat(
            self.user_id, conv.id, "",
            self.config.get("llm_provider", "ollama"),
            self.config.get("llm_model", "mistral"),
            self.config.get("llm_temperature", 0.5)
        ):
            if chunk:
                response += chunk
        
        yield {"type": "result", "data": {
            "success": True,
            "mode": "budget_optimization",
            "query": query,
            "budget_plan": response,
            "timestamp": datetime.utcnow().isoformat()
        }}
    
    async def _mode_activity_recommendations(self, input_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """Recommandations activités personnalisées"""
        query = input_data.get("query", "")
        preferences = input_data.get("preferences", {})
        
        yield {"type": "status", "data": "🎯 Recommandations activités..."}
        
        rag_context = ""
        if self.project_id:
            chunks = await self.get_rag_context(query, top_k=3)
            rag_context = "\n".join([c['content'] for c in chunks])
        
        documents = input_data.get("documents", [])
        doc_context = await self._load_documents(documents)
        
        prompt = self._build_activities_prompt(query, preferences, rag_context, doc_context)
        
        from app.models import Conversation, Message as MessageModel
        
        conv = Conversation(
            user_id=self.user_id,
            title=f"Activities: {query[:50]}",
            provider_name=self.config.get("llm_provider", "ollama"),
            model=self.config.get("llm_model", "mistral"),
            temperature=self.config.get("llm_temperature", 0.7)
        )
        self.db.add(conv)
        self.db.flush()
        
        self.db.add(MessageModel(conversation_id=conv.id, role="system", content="Tu es un expert en activités touristiques et expériences locales."))
        self.db.add(MessageModel(conversation_id=conv.id, role="user", content=prompt))
        self.db.commit()
        
        response = ""
        async for chunk in self.llm_service.stream_chat(
            self.user_id, conv.id, "",
            self.config.get("llm_provider", "ollama"),
            self.config.get("llm_model", "mistral"),
            self.config.get("llm_temperature", 0.7)
        ):
            if chunk:
                response += chunk
        
        yield {"type": "result", "data": {
            "success": True,
            "mode": "activity_recommendations",
            "query": query,
            "activities": response,
            "timestamp": datetime.utcnow().isoformat()
        }}
    
    async def _mode_travel_analysis(self, input_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """Analyse documents voyage (réservations, visas)"""
        query = input_data.get("query", "")
        documents = input_data.get("documents", [])
        
        if not documents:
            yield {"type": "error", "data": "Aucun document fourni"}
            return
        
        yield {"type": "status", "data": f"📄 Analyse {len(documents)} documents..."}
        
        doc_context = await self._load_documents(documents)
        
        prompt = f"""Tu es un expert en analyse de documents de voyage.

Documents analysés:
{doc_context}

Question: {query}

Analyse les documents et fournis:
1. Résumé des informations clés
2. Dates importantes à retenir
3. Documents manquants éventuels
4. Recommandations d'organisation
5. Checklist pré-départ

Réponds de manière structurée et pratique."""

        from app.models import Conversation, Message as MessageModel
        
        conv = Conversation(
            user_id=self.user_id,
            title=f"Analysis: {query[:50]}",
            provider_name=self.config.get("llm_provider", "ollama"),
            model=self.config.get("llm_model", "mistral"),
            temperature=self.config.get("llm_temperature", 0.4)
        )
        self.db.add(conv)
        self.db.flush()
        
        self.db.add(MessageModel(conversation_id=conv.id, role="system", content="Tu es un expert en analyse de documents de voyage."))
        self.db.add(MessageModel(conversation_id=conv.id, role="user", content=prompt))
        self.db.commit()
        
        response = ""
        async for chunk in self.llm_service.stream_chat(
            self.user_id, conv.id, "",
            self.config.get("llm_provider", "ollama"),
            self.config.get("llm_model", "mistral"),
            self.config.get("llm_temperature", 0.4)
        ):
            if chunk:
                response += chunk
        
        yield {"type": "result", "data": {
            "success": True,
            "mode": "travel_analysis",
            "query": query,
            "analysis": response,
            "documents_analyzed": len(documents),
            "timestamp": datetime.utcnow().isoformat()
        }}
    
    # ═══════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════
    
    async def _load_documents(self, documents: List[str]) -> str:
        """Charge contenu documents"""
        if not documents:
            return ""
        
        contexts = []
        for doc_path in documents:
            try:
                path = Path(doc_path)
                if path.exists():
                    content = path.read_text(encoding='utf-8')
                    contexts.append(f"Document {path.name}:\n{content}\n")
            except Exception as e:
                contexts.append(f"Erreur lecture {doc_path}: {str(e)}")
        
        return "\n".join(contexts)
    
    def _build_destination_prompt(self, query: str, preferences: Dict[str, Any], rag: str, docs: str) -> str:
        """Build prompt destinations"""
        budget = preferences.get("budget", "flexible")
        duration = preferences.get("duration", "non spécifié")
        interests = preferences.get("interests", [])
        season = preferences.get("season", "toute l'année")
        
        context = ""
        if rag:
            context += f"\nCONTEXTE PROJET:\n{rag}\n"
        if docs:
            context += f"\nDOCUMENTS:\n{docs}\n"
        
        return f"""REQUÊTE: {query}

PRÉFÉRENCES:
- Budget: {budget}
- Durée: {duration}
- Intérêts: {', '.join(interests) if interests else 'découverte générale'}
- Saison: {season}
{context}
Propose 3-5 destinations idéales avec pour chacune:
1. Nom et localisation
2. Pourquoi elle correspond
3. Budget estimé (vol + hébergement + activités)
4. Meilleure période
5. Points forts uniques
6. Conseils pratiques (visa, sécurité)

Sois structuré et engageant."""
    
    def _build_itinerary_prompt(self, query: str, preferences: Dict[str, Any], rag: str, docs: str) -> str:
        """Build prompt itinéraire"""
        duration = preferences.get("duration", "7 jours")
        pace = preferences.get("pace", "modéré")
        interests = preferences.get("interests", [])
        
        context = ""
        if rag:
            context += f"\nCONTEXTE PROJET:\n{rag}\n"
        if docs:
            context += f"\nDOCUMENTS:\n{docs}\n"
        
        return f"""DEMANDE: {query}

PARAMÈTRES:
- Durée: {duration}
- Rythme: {pace}
- Intérêts: {', '.join(interests) if interests else 'varié'}
{context}
Crée itinéraire jour par jour avec:
1. Programme détaillé chaque jour
2. Temps trajet réalistes
3. Mix activités/repos
4. Restaurants recommandés
5. Budget quotidien estimé
6. Conseils logistiques

Précis sur horaires et distances."""
    
    def _build_budget_prompt(self, query: str, budget: str, rag: str, docs: str) -> str:
        """Build prompt budget"""
        context = ""
        if rag:
            context += f"\nCONTEXTE PROJET:\n{rag}\n"
        if docs:
            context += f"\nDOCUMENTS:\n{docs}\n"
        
        return f"""REQUÊTE: {query}

BUDGET: {budget}
{context}
Plan budgétaire avec:
1. Répartition par poste (transport, hébergement, food, activités)
2. Astuces économies
3. Alternatives économiques
4. Marge sécurité (10-15%)
5. Tableau récap

Montants réalistes et actionnables."""
    
    def _build_activities_prompt(self, query: str, preferences: Dict[str, Any], rag: str, docs: str) -> str:
        """Build prompt activités"""
        interests = preferences.get("interests", [])
        group_size = preferences.get("group_size", "solo")
        
        context = ""
        if rag:
            context += f"\nCONTEXTE PROJET:\n{rag}\n"
        if docs:
            context += f"\nDOCUMENTS:\n{docs}\n"
        
        return f"""DEMANDE: {query}

PROFIL:
- Intérêts: {', '.join(interests) if interests else 'varié'}
- Groupe: {group_size}
{context}
Recommande activités avec:
1. Nom et type
2. Description unique
3. Durée et timing
4. Prix approximatif
5. Réservation nécessaire ?
6. Conseil expert

Varie les types (culture, nature, gastro, aventure)."""