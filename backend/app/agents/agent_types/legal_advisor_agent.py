"""
Agent Conseiller Juridique Complet - Version Centralisée Production
====================================================================

Remplace un conseiller juridique avec toutes ses compétences métier.

MODES DISPONIBLES:
- claim_processing   : Traitement réclamations/litiges
- compliance_check   : Audit conformité (RGPD, contrats)
- risk_assessment    : Évaluation risques juridiques
- document_drafting  : Rédaction assistée
- legal_research     : Recherche juridique RAG
- monitoring         : Veille réglementaire
- training           : Génération matériel formation
- analyze            : Analyse documents (legacy)

Architecture:
- Embedding: sentence-transformers/paraphrase-multilingual-mpnet-base-v2
- NER: spaCy fr_dep_news_trf + patterns juridiques
- VectorDB: ChromaDB isolation par project_id
- LLM: Ollama/OpenAI/Claude
"""

from typing import Dict, Any, List, AsyncGenerator, Optional
from uuid import UUID
from datetime import datetime, timedelta
import logging
from sentence_transformers import SentenceTransformer
import spacy
from pathlib import Path
import re

from app.agents.base_agent import BaseAgent
from app.models import Project, Document, Conversation, Message as MessageModel
from app.services.chunker import SmartChunker

from .legal_config import (
    COMPLIANCE_CHECKLISTS, NER_PATTERNS, LEGAL_SOURCES,
    RISK_WEIGHTS, CLAIM_TYPES, DOCUMENT_TYPES
)
from .legal_templates import TEMPLATES, PROMPTS, get_template, render_template

logger = logging.getLogger(__name__)


class LegalAdvisorAgent(BaseAgent):
    """Agent Conseiller Juridique - Monolithique Centralisé"""
    
    def __init__(self, agent_id: UUID, user_id: UUID, config: Dict[str, Any], mcp_config: Dict[str, Any], db: Any):
        super().__init__(agent_id, user_id, config, mcp_config, db)
        self.legal_config = config.get("legal_config", {})
        self.domains = self.legal_config.get("domains", ["fiscal", "social", "commercial"])
        self.embedding_model_name = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
        self.embedding_model = None
        self.nlp = None
        self.project_id = config.get("project_id")
    
    async def execute(self, input_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """Point d'entrée principal"""
        try:
            mode = input_data.get("mode", "legal_research")
            yield {"type": "status", "data": f"🔧 Mode {mode}"}
            
            await self._init_models()
            project_id = await self._ensure_project()
            
            documents = input_data.get("documents", [])
            if documents:
                yield {"type": "status", "data": f"📄 Traitement {len(documents)} docs..."}
                await self._process_documents(documents, project_id)
            
            handlers = {
                "claim_processing": self._mode_claim_processing,
                "compliance_check": self._mode_compliance_check,
                "risk_assessment": self._mode_risk_assessment,
                "document_drafting": self._mode_document_drafting,
                "legal_research": self._mode_legal_research,
                "monitoring": self._mode_monitoring,
                "training": self._mode_training,
                "analyze": self._mode_analyze
            }
            
            handler = handlers.get(mode)
            if not handler:
                raise ValueError(f"Mode inconnu: {mode}")
            
            async for update in handler(input_data, project_id):
                yield update
                
        except Exception as e:
            logger.error(f"Agent error: {str(e)}")
            yield {"type": "error", "data": str(e)}
            raise
    
    # ═══════════════════════════════════════════════════════════════
    # MODES MÉTIER P0
    # ═══════════════════════════════════════════════════════════════
    
    async def _mode_claim_processing(self, input_data: Dict[str, Any], project_id: UUID) -> AsyncGenerator[Dict[str, Any], None]:
        """Traitement réclamations"""
        yield {"type": "status", "data": "🔍 Analyse réclamation..."}
        
        query = input_data.get("query", "")
        context = input_data.get("context", {})
        
        # Classification
        classification = await self._classify_claim(query, context)
        yield {"type": "progress", "data": {"step": "classification", "result": classification}}
        
        # Extraction entités
        entities = await self._extract_legal_entities(query)
        yield {"type": "progress", "data": {"step": "entities", "result": entities}}
        
        # Textes applicables
        applicable_law = await self._find_applicable_law(query, classification["domain"], project_id)
        
        # Jurisprudence
        similar_cases = await self._find_similar_cases(query, classification["type"], project_id)
        
        # Risque
        risk_analysis = await self._quick_risk_assessment(query, classification, similar_cases)
        yield {"type": "progress", "data": {"step": "risk", "result": risk_analysis}}
        
        # Réponse
        yield {"type": "status", "data": "✍️ Génération réponse..."}
        response_draft = await self._generate_claim_response(
            query, classification, entities, applicable_law, similar_cases, risk_analysis, context
        )
        
        # Recommandations
        recommendations = self._generate_claim_recommendations(classification, risk_analysis, entities)
        
        yield {
            "type": "result",
            "data": {
                "mode": "claim_processing",
                "classification": classification,
                "entities": entities,
                "applicable_law": applicable_law[:3],
                "similar_cases": similar_cases[:5],
                "risk_analysis": risk_analysis,
                "response_draft": response_draft,
                "recommendations": recommendations,
                "summary": f"Réclamation {classification['type']} - Risque {risk_analysis['level']}"
            }
        }
    
    async def _mode_compliance_check(self, input_data: Dict[str, Any], project_id: UUID) -> AsyncGenerator[Dict[str, Any], None]:
        """Vérification conformité"""
        yield {"type": "status", "data": "📋 Audit conformité..."}
        
        doc_path = input_data.get("documents", [None])[0]
        if not doc_path:
            yield {"type": "error", "data": "Aucun document"}
            return
        
        doc_type = input_data.get("context", {}).get("document_type", "auto")
        query = input_data.get("query", "")
        
        if doc_type == "auto":
            doc_type = await self._detect_document_type(doc_path)
            yield {"type": "progress", "data": {"detected_type": doc_type}}
        
        checklist = COMPLIANCE_CHECKLISTS.get(doc_type, COMPLIANCE_CHECKLISTS.get("generic", {}))
        
        from app.services.document_processor import DocumentProcessor
        text = DocumentProcessor().extract_text(Path(doc_path))
        
        # Checklist automatique
        extracted_clauses = await self._extract_clauses(text, doc_type)
        compliance_results = await self._check_compliance_points(text, extracted_clauses, checklist)
        
        total = len(checklist.get("required_items", []))
        passed = sum(1 for i in compliance_results["items"] if i["compliant"])
        score = passed / total if total > 0 else 0
        
        # ✅ AJOUT : Analyse LLM professionnelle
        yield {"type": "status", "data": "🧠 Analyse juridique approfondie..."}
        
        # Construire contexte pour LLM
        issues_summary = "\n".join([
            f"❌ {item['item']} - Gravité: {item['severity']}"
            for item in compliance_results["items"]
            if not item["compliant"]
        ])
        
        compliant_items = "\n".join([
            f"✅ {item['item']}"
            for item in compliance_results["items"]
            if item["compliant"]
        ])
        
        # Prompt LLM expert
        prompt = f"""Tu es un juriste expert en conformité réglementaire.

TYPE DE DOCUMENT : {DOCUMENT_TYPES.get(doc_type, doc_type)}
RÉGLEMENTATION : {checklist.get('regulation', 'Générale')}

AUDIT AUTOMATIQUE EFFECTUÉ :
Score de conformité : {int(score*100)}%
Points conformes ({passed}/{total}) :
{compliant_items}

Points non conformes ({total - passed}/{total}) :
{issues_summary}

EXTRAIT DU DOCUMENT (premiers 2000 caractères) :
{text[:2000]}

Ta mission d'expert juridique :

1. **ANALYSE APPROFONDIE** :
   - Évalue la gravité réelle de chaque non-conformité
   - Identifie les risques juridiques et financiers
   - Détecte les problèmes subtils non détectés par l'audit automatique

2. **RECOMMANDATIONS EXPERTISES** :
   - Priorise les corrections (critique/urgent/important/mineur)
   - Propose des formulations conformes pour chaque point
   - Indique les délais de mise en conformité recommandés

3. **SYNTHÈSE EXÉCUTIVE** :
   - Donne ton avis d'expert : document utilisable en l'état ? (Oui/Non)
   - Si non, quelles sont les 3 actions prioritaires ?
   - Quel est le niveau de risque global ? (Faible/Moyen/Élevé/Critique)

Réponds de manière structurée, professionnelle et actionnabilité."""

        # Appel LLM
        conv = Conversation(
            user_id=self.user_id,
            title=f"Compliance Check {doc_type}",
            provider_name=self.config.get("llm_provider", "ollama"),
            model=self.config.get("llm_model", "mistral"),
            temperature=0.3
        )
        self.db.add(conv)
        self.db.flush()
        self.db.add(MessageModel(conversation_id=conv.id, role="user", content=prompt))
        self.db.commit()
        
        llm_analysis = ""
        async for chunk in self.llm_service.stream_chat(
            self.user_id, conv.id, "",
            self.config.get("llm_provider", "ollama"),
            self.config.get("llm_model", "mistral"),
            0.3
        ):
            if chunk:
                llm_analysis += chunk
        
        # Recommandations automatiques + LLM
        recommendations = self._generate_compliance_recommendations(compliance_results, doc_type)
        
        # Rapport final avec analyse LLM
        report = await self._generate_compliance_report(
            Path(doc_path).name, doc_type, score, compliance_results, recommendations
        )
        
        yield {
            "type": "result",
            "data": {
                "mode": "compliance_check",
                "compliant": score >= 0.8,
                "compliance_score": round(score, 2),
                "total_checks": total,
                "passed_checks": passed,
                "issues": [i for i in compliance_results["items"] if not i["compliant"]][:10],
                "recommendations": recommendations,
                "expert_analysis": llm_analysis,  # ✅ Analyse LLM
                "report": report,
                "summary": f"{'✅ Conforme' if score >= 0.8 else '❌ Non conforme'} - {int(score*100)}%"
            }
        }
    
    async def _mode_risk_assessment(self, input_data: Dict[str, Any], project_id: UUID) -> AsyncGenerator[Dict[str, Any], None]:
        """Évaluation risques"""
        yield {"type": "status", "data": "⚠️ Évaluation risques..."}
        
        query = input_data.get("query", "")
        context = input_data.get("context", {})
        risk_types = context.get("risk_types", ["all"])
        
        # Analyse automatique
        entities = await self._extract_legal_entities(query)
        risk_patterns = await self._detect_risk_patterns(query, entities)
        unfavorable_cases = await self._find_unfavorable_cases(query, risk_types, project_id)
        
        risk_factors = []
        categories = risk_types if "all" not in risk_types else ["contentieux", "fiscal", "rgpd", "commercial"]
        
        for risk_type in categories:
            factor = await self._assess_risk_category(query, risk_type, entities, unfavorable_cases, project_id)
            if factor:
                risk_factors.append(factor)
        
        overall_risk = self._calculate_overall_risk(risk_factors)
        mitigation = self._generate_mitigation_strategies(risk_factors)
        financial = self._estimate_financial_impact(risk_factors, context)
        
        # ✅ AJOUT : Analyse LLM experte
        yield {"type": "status", "data": "🧠 Analyse juridique experte des risques..."}
        
        # RAG : Récupérer documents pertinents
        query_embedding = self.embedding_model.encode(query, convert_to_tensor=False).tolist()
        rag_results = self.vector_store.query(project_id=str(project_id), query_embedding=query_embedding, n_results=5)
        
        rag_context = "\n\n".join([
            f"[SOURCE: {meta.get('filename')}]\n{doc[:800]}"
            for doc, meta in zip(rag_results.get('documents', [[]])[0], rag_results.get('metadatas', [[]])[0])
        ]) if rag_results.get('documents') else "Aucun document de référence disponible."
        
        # Prompt LLM expert
        risk_summary = "\n".join([
            f"- {f['category'].upper()} : Probabilité {int(f['probability']*100)}% | Impact {f['impact']} | {f['description']}"
            for f in risk_factors
        ])
        
        patterns_summary = "\n".join([
            f"- {p['type']} (gravité: {p['severity']})"
            for p in risk_patterns
        ])
        
        prompt = f"""Tu es un juriste expert en gestion des risques juridiques et financiers.

SITUATION À ANALYSER :
{query}

CONTEXTE FINANCIER :
Exposition financière : {context.get('financial_exposure', 'Non spécifiée')}€
Deadline : {context.get('deadline_closing', 'Non spécifiée')}

DOCUMENTS DE RÉFÉRENCE :
{rag_context}

ANALYSE AUTOMATIQUE EFFECTUÉE :

Niveau de risque global : {overall_risk.get('level', 'Non évalué')} (score: {overall_risk.get('score', 0):.2f})

Facteurs de risque identifiés ({len(risk_factors)}) :
{risk_summary if risk_summary else "Aucun facteur automatique détecté"}

Patterns détectés :
{patterns_summary if patterns_summary else "Aucun pattern détecté"}

Cas défavorables trouvés : {len(unfavorable_cases)}

Ta mission d'expert juridique :

1. **ANALYSE APPROFONDIE DES RISQUES** :
   - Valide ou conteste l'évaluation automatique
   - Identifie des risques cachés non détectés automatiquement
   - Analyse les interactions entre risques (effet domino)
   - Évalue les probabilités réalistes basées sur jurisprudence

2. **QUANTIFICATION FINANCIÈRE** :
   - Estime l'impact financier minimum/maximum/probable pour chaque risque
   - Calcule le coût des litiges potentiels (avocat + procédure)
   - Évalue le coût d'opportunité (temps, image)

3. **STRATÉGIE DE MITIGATION** :
   - Propose 3-5 actions concrètes priorisées
   - Pour chaque action : coût estimé, délai, réduction du risque
   - Identifie les "quick wins" (actions rapides/pas chères)

4. **RECOMMANDATION FINALE** :
   - Go / No-Go / Go sous conditions ?
   - Quel niveau décisionnel requis ? (opérationnel/direction/conseil)
   - Délai de décision recommandé ?

Réponds de manière structurée, chiffrée et actionnabilité. Utilise ton expertise juridique pour aller au-delà du scoring automatique."""

        # Appel LLM
        conv = Conversation(
            user_id=self.user_id,
            title="Risk Assessment Expert",
            provider_name=self.config.get("llm_provider", "ollama"),
            model=self.config.get("llm_model", "mistral"),
            temperature=0.3
        )
        self.db.add(conv)
        self.db.flush()
        self.db.add(MessageModel(conversation_id=conv.id, role="user", content=prompt))
        self.db.commit()
        
        expert_analysis = ""
        async for chunk in self.llm_service.stream_chat(
            self.user_id, conv.id, "",
            self.config.get("llm_provider", "ollama"),
            self.config.get("llm_model", "mistral"),
            0.3
        ):
            if chunk:
                expert_analysis += chunk
        
        # Rapport détaillé
        detailed = await self._generate_risk_analysis_report(query, risk_factors, overall_risk, unfavorable_cases, mitigation)
        
        yield {
            "type": "result",
            "data": {
                "mode": "risk_assessment",
                "overall_risk": overall_risk,
                "risk_factors": risk_factors,
                "risk_patterns": risk_patterns,
                "unfavorable_cases_count": len(unfavorable_cases),
                "mitigation_strategies": mitigation,
                "financial_impact": financial,
                "expert_analysis": expert_analysis,  # ✅ Analyse LLM
                "detailed_analysis": detailed,
                "summary": f"Risque {overall_risk.get('level', 'indéterminé')} - {len(risk_factors)} facteurs - Analyse experte complète"
            }
        }
    
    async def _mode_document_drafting(self, input_data: Dict[str, Any], project_id: UUID) -> AsyncGenerator[Dict[str, Any], None]:
        """Rédaction assistée"""
        yield {"type": "status", "data": "✍️ Rédaction document juridique..."}
        
        query = input_data.get("query", "")
        
        # Auto-détection type document depuis query
        query_lower = query.lower()
        if "mise en demeure" in query_lower:
            doc_type = "courrier_mise_en_demeure"
        elif "recours" in query_lower:
            doc_type = "reponse_recours"
        elif "contestation" in query_lower or "répon" in query_lower:
            doc_type = "reponse_contestation"
        elif "note" in query_lower:
            doc_type = "note_juridique"
        elif "acte" in query_lower:
            doc_type = "acte_administratif"
        else:
            doc_type = "note_juridique"  # Par défaut
        
        yield {"type": "progress", "data": {"document_type": doc_type}}
        
        # Extraction entités pour contexte
        entities = await self._extract_legal_entities(query)
        
        # RAG : Rechercher références légales et documents similaires
        query_embedding = self.embedding_model.encode(query, convert_to_tensor=False).tolist()
        legal_refs = self.vector_store.query(project_id=str(project_id), query_embedding=query_embedding, n_results=5)
        
        rag_context = ""
        if legal_refs.get('documents') and legal_refs['documents'][0]:
            rag_context = "\n\n".join([
                f"[{meta.get('filename')}]\n{doc[:500]}"
                for doc, meta in zip(legal_refs['documents'][0], legal_refs['metadatas'][0])
            ])
        
        # ✅ Génération LLM complète avec template guidance
        yield {"type": "status", "data": "🧠 Rédaction par expert juridique..."}
        
        # Template guidance selon type
        template_guidance = {
            "courrier_mise_en_demeure": """
Structure attendue :
- En-tête : LETTRE RECOMMANDÉE AVEC AR
- Coordonnées expéditeur/destinataire
- Objet : Mise en demeure + référence
- Rappel des faits chronologique
- Fondement juridique (articles de loi)
- Demande précise avec délai (généralement 8 jours)
- Conséquences en cas non-respect
- Formule de politesse formelle
""",
            "note_juridique": """
Structure attendue :
- En-tête : NOTE JURIDIQUE + Date + Destinataire
- CONTEXTE (situation factuelle)
- QUESTION JURIDIQUE (problème posé)
- ANALYSE (droit applicable + jurisprudence)
- TEXTES APPLICABLES (références précises)
- RISQUES IDENTIFIÉS (juridiques + financiers)
- RECOMMANDATIONS (priorisées)
- CONCLUSION (synthèse + orientation)
""",
            "reponse_recours": """
Structure attendue :
- Coordonnées + Date
- Objet : Réponse à votre recours du [date]
- Accusé de réception du recours
- Analyse des arguments invoqués
- Réponse juridique motivée point par point
- Références textes applicables
- Conclusion (acceptation/rejet/partiel)
- Voies de recours restantes
- Formule politesse
""",
            "reponse_contestation": """
Structure similaire réponse recours, ton moins formel.
""",
            "acte_administratif": """
Structure officielle :
- ACTE ADMINISTRATIF + Numéro
- Vu (textes de référence)
- Articles numérotés
- Article final : notification
- Signature + fonction
"""
        }
        
        prompt = f"""Tu es un juriste rédacteur expert. Tu dois rédiger un {doc_type} professionnel et conforme.

DEMANDE DU CLIENT :
{query}

ENTITÉS JURIDIQUES DÉTECTÉES :
- Montants : {', '.join([e['text'] for e in entities.get('amounts', [])])}
- Dates/Délais : {', '.join([e['text'] for e in entities.get('deadlines', [])])}
- Références légales : {', '.join([e['text'] for e in entities.get('legal_refs', [])])}
- Autorités : {', '.join([e['text'] for e in entities.get('authorities', [])])}

DOCUMENTS DE RÉFÉRENCE DISPONIBLES :
{rag_context if rag_context else "Aucun document de référence spécifique trouvé."}

{template_guidance.get(doc_type, "")}

CONSIGNES DE RÉDACTION :

1. **Ton et Style** :
   - Langage juridique précis mais accessible
   - Ton ferme mais professionnel (pas agressif)
   - Formulations courantes en droit français

2. **Contenu** :
   - Intègre TOUS les faits mentionnés par le client
   - Cite les références légales pertinentes (Code civil, commercial, etc.)
   - Mentionne les délais légaux applicables
   - Calcule pénalités légales si applicable (intérêts retard, forfait 40€...)

3. **Forme** :
   - Structure claire avec sections distinctes
   - Dates au format JJ/MM/AAAA
   - Montants précis en euros TTC
   - Formules de politesse appropriées au contexte

4. **Conformité** :
   - Respect des usages juridiques français
   - Mentions obligatoires selon type de document
   - Aucune formulation ambiguë

Rédige maintenant le document COMPLET, prêt à être envoyé. Ne mets PAS de commentaires, seulement le document final."""

        # Appel LLM
        conv = Conversation(
            user_id=self.user_id,
            title=f"Draft {doc_type}",
            provider_name=self.config.get("llm_provider", "ollama"),
            model=self.config.get("llm_model", "mistral"),
            temperature=0.4  # Légèrement plus créatif pour rédaction
        )
        self.db.add(conv)
        self.db.flush()
        self.db.add(MessageModel(conversation_id=conv.id, role="user", content=prompt))
        self.db.commit()
        
        generated_content = ""
        async for chunk in self.llm_service.stream_chat(
            self.user_id, conv.id, "",
            self.config.get("llm_provider", "ollama"),
            self.config.get("llm_model", "mistral"),
            0.4
        ):
            if chunk:
                generated_content += chunk
        
        # Suggestions amélioration basiques
        suggestions = []
        if len(generated_content.split()) < 100:
            suggestions.append("Document court, considérer développer davantage")
        if not any(ref in generated_content.lower() for ref in ["article", "code", "loi"]):
            suggestions.append("Ajouter références légales précises")
        
        yield {
            "type": "result",
            "data": {
                "mode": "document_drafting",
                "document_type": doc_type,
                "content": generated_content,
                "legal_references": [
                    {"source": meta.get("filename"), "relevance": 1 - dist}
                    for meta, dist in zip(legal_refs.get('metadatas', [[]])[0], legal_refs.get('distances', [[]])[0])
                ] if legal_refs.get('metadatas') else [],
                "entities_used": entities,
                "suggestions": suggestions,
                "summary": f"Document {doc_type} généré ({len(generated_content.split())} mots)"
            }
        }
    
    async def _mode_legal_research(self, input_data: Dict[str, Any], project_id: UUID) -> AsyncGenerator[Dict[str, Any], None]:
        """Recherche juridique"""
        yield {"type": "status", "data": "🔍 Recherche juridique..."}
        
        query = input_data.get("query", "")
        max_results = input_data.get("options", {}).get("max_results", 10)
        
        # RAG search
        query_embedding = self.embedding_model.encode(query, convert_to_tensor=False).tolist()
        rag_results = self.vector_store.query(project_id=str(project_id), query_embedding=query_embedding, n_results=max_results)
        
        # Recherche externe (TODO: Légifrance)
        external = await self._search_legifrance(query)
        all_results = self._merge_search_results(rag_results, external)
        
        entities = await self._extract_legal_entities(query)
        
        # ✅ AJOUT : Synthèse LLM experte des résultats
        yield {"type": "status", "data": "🧠 Synthèse juridique par expert..."}
        
        # Construire contexte des résultats pour LLM
        results_context = ""
        for i, result in enumerate(all_results[:10], 1):
            results_context += f"\n{i}. [{result.get('source', 'Source inconnue')}] (pertinence: {result.get('score', 0):.2f})\n{result.get('text', '')[:500]}...\n"
        
        prompt = f"""Tu es un juriste chercheur expert.

QUESTION DE RECHERCHE :
{query}

ENTITÉS JURIDIQUES DÉTECTÉES :
{entities}

RÉSULTATS DE RECHERCHE TROUVÉS ({len(all_results)}) :
{results_context}

Ta mission d'expert :

1. **SYNTHÈSE DES RÉSULTATS** :
   - Quels sont les 3 points clés qui ressortent ?
   - Y a-t-il consensus ou divergences dans les sources ?
   - Quelles sont les références légales essentielles ?

2. **ANALYSE JURIDIQUE** :
   - Quelle est la réponse juridique à la question posée ?
   - Quels sont les principes de droit applicables ?
   - Y a-t-il des exceptions ou cas particuliers ?

3. **ORIENTATION PRATIQUE** :
   - Quelle est ta recommandation d'action ?
   - Quelles sont les sources prioritaires à consulter ?
   - Quelles sont les zones d'incertitude nécessitant expertise complémentaire ?

4. **PISTES D'APPROFONDISSEMENT** :
   - Quels autres textes/jurisprudence faudrait-il consulter ?
   - Quelles questions connexes méritent recherche ?

Réponds de manière structurée et cite précisément les sources (par numéro [1], [2], etc.)."""

        # Appel LLM
        conv = Conversation(
            user_id=self.user_id,
            title="Legal Research Synthesis",
            provider_name=self.config.get("llm_provider", "ollama"),
            model=self.config.get("llm_model", "mistral"),
            temperature=0.3
        )
        self.db.add(conv)
        self.db.flush()
        self.db.add(MessageModel(conversation_id=conv.id, role="user", content=prompt))
        self.db.commit()
        
        expert_synthesis = ""
        async for chunk in self.llm_service.stream_chat(
            self.user_id, conv.id, "",
            self.config.get("llm_provider", "ollama"),
            self.config.get("llm_model", "mistral"),
            0.3
        ):
            if chunk:
                expert_synthesis += chunk
        
        yield {
            "type": "result",
            "data": {
                "mode": "legal_research",
                "query": query,
                "results": all_results[:max_results],
                "query_entities": entities,
                "total_results": len(all_results),
                "expert_synthesis": expert_synthesis,  # ✅ Synthèse LLM
                "summary": f"{len(all_results)} résultats trouvés - Synthèse experte générée"
            }
        }
    
    async def _mode_monitoring(self, input_data: Dict[str, Any], project_id: UUID) -> AsyncGenerator[Dict[str, Any], None]:
        """Veille réglementaire"""
        yield {"type": "status", "data": "📡 Veille réglementaire..."}
        
        domain = input_data.get("context", {}).get("domain", "fiscal")
        new_texts = await self._scan_legal_updates(domain, None)
        
        impacts = []
        for text in new_texts:
            impact = await self._analyze_legal_impact(text, project_id)
            if impact["severity"] != "none":
                impacts.append(impact)
        
        yield {
            "type": "result",
            "data": {
                "mode": "monitoring",
                "new_texts_count": len(new_texts),
                "impactful_changes": len(impacts),
                "alerts": impacts
            }
        }
    
    async def _mode_training(self, input_data: Dict[str, Any], project_id: UUID) -> AsyncGenerator[Dict[str, Any], None]:
        """Génération formation"""
        yield {"type": "status", "data": "📚 Génération matériel de formation..."}
        
        topic = input_data.get("query", "")
        format_type = input_data.get("context", {}).get("format", "fiche")
        audience = input_data.get("context", {}).get("audience", "agents")
        
        # RAG : Rassembler contenu pertinent
        content = await self._gather_training_content(topic, project_id)
        
        # ✅ Génération LLM selon format
        yield {"type": "status", "data": f"🧠 Création {format_type} pédagogique..."}
        
        # Construire contexte sources
        sources_context = "\n\n".join([
            f"SOURCE {i+1} - {c.get('source', 'Document')}:\n{c.get('text', '')[:800]}"
            for i, c in enumerate(content[:5])
        ]) if content else "Pas de documentation spécifique disponible. Base-toi sur tes connaissances juridiques."
        
        # Prompts selon format
        format_prompts = {
            "fiche": f"""Tu es un formateur juridique expert. Crée une FICHE PRATIQUE professionnelle.

THÈME : {topic}
PUBLIC : {audience}

SOURCES DISPONIBLES :
{sources_context}

FORMAT ATTENDU :

📋 FICHE PRATIQUE : {topic.upper()}
═══════════════════════════════════════

👥 Public cible : {audience}
⏱️ Temps de lecture : 5-10 minutes

🎯 OBJECTIFS PÉDAGOGIQUES
─────────────────────────
(3 objectifs clairs : "À l'issue, vous saurez...")

💡 POINTS CLÉS (5-7 points essentiels)
──────────────────────────────────────
Pour chaque point :
- Titre explicite
- Explication simple (2-3 phrases)
- Exemple concret si pertinent

📜 RÉFÉRENCES LÉGALES
─────────────────────
(Textes applicables avec articles précis)

⚠️ PIÈGES À ÉVITER
──────────────────
(3-5 erreurs courantes)

✅ CHECKLIST ACTION
───────────────────
(Points de vérification pratiques)

🔗 POUR ALLER PLUS LOIN
───────────────────────
(Ressources complémentaires)

Rédige de manière pédagogique, accessible mais rigoureuse juridiquement.""",

            "guide": f"""Tu es un formateur juridique expert. Crée un GUIDE COMPLET professionnel.

THÈME : {topic}
PUBLIC : {audience}

SOURCES DISPONIBLES :
{sources_context}

FORMAT ATTENDU :

📘 GUIDE : {topic.upper()}
═══════════════════════════════════════

TABLE DES MATIÈRES
─────────────────

1. INTRODUCTION
   - Contexte et enjeux
   - À qui s'adresse ce guide

2. CADRE JURIDIQUE
   - Textes applicables
   - Évolutions récentes
   - Autorités compétentes

3. OBLIGATIONS ET BONNES PRATIQUES
   - Obligations légales détaillées
   - Recommandations pratiques
   - Exemples d'application

4. CAS PRATIQUES
   - Scénario 1 : [Cas courant]
   - Scénario 2 : [Cas complexe]
   - Scénario 3 : [Cas limite]

5. FAQ (10 questions fréquentes)

6. RESSOURCES ET CONTACTS
   - Textes de référence
   - Organismes utiles
   - Outils pratiques

Développe chaque section avec exemples concrets, conseils actionnables et références précises.""",

            "faq": f"""Tu es un formateur juridique expert. Crée une FAQ COMPLÈTE professionnelle.

THÈME : {topic}
PUBLIC : {audience}

SOURCES DISPONIBLES :
{sources_context}

FORMAT ATTENDU :

❓ FAQ : {topic.upper()}
═══════════════════════════════════════

Crée 15-20 questions/réponses couvrant :

📌 QUESTIONS BASIQUES (5-7)
─────────────────────────
(Définitions, principes, champ d'application)

⚙️ QUESTIONS PRATIQUES (5-7)
────────────────────────────
(Procédures, démarches, documents)

⚠️ QUESTIONS COMPLEXES (3-5)
────────────────────────────
(Cas limites, exceptions, contentieux)

🔍 QUESTIONS PIÈGES (2-3)
─────────────────────────
(Idées reçues à déconstruire)

Pour chaque Q/R :
- Question claire et directe
- Réponse structurée (2-5 paragraphes)
- Références légales si pertinent
- Exemple concret si utile
- ⚠️ Alerte si point d'attention

Rédige de manière accessible mais juridiquement précise."""
        }
        
        prompt = format_prompts.get(format_type, format_prompts["fiche"])
        
        # Appel LLM
        conv = Conversation(
            user_id=self.user_id,
            title=f"Training {format_type}",
            provider_name=self.config.get("llm_provider", "ollama"),
            model=self.config.get("llm_model", "mistral"),
            temperature=0.5  # Plus créatif pour pédagogie
        )
        self.db.add(conv)
        self.db.flush()
        self.db.add(MessageModel(conversation_id=conv.id, role="user", content=prompt))
        self.db.commit()
        
        training_material = ""
        async for chunk in self.llm_service.stream_chat(
            self.user_id, conv.id, "",
            self.config.get("llm_provider", "ollama"),
            self.config.get("llm_model", "mistral"),
            0.5
        ):
            if chunk:
                training_material += chunk
        
        yield {
            "type": "result",
            "data": {
                "mode": "training",
                "topic": topic,
                "format": format_type,
                "audience": audience,
                "material": training_material,
                "sources_count": len(content),
                "summary": f"{format_type.capitalize()} pédagogique généré - {len(training_material.split())} mots"
            }
        }
    
    async def _mode_analyze(self, input_data: Dict[str, Any], project_id: UUID) -> AsyncGenerator[Dict[str, Any], None]:
        """Analyse documents (legacy)"""
        yield {"type": "status", "data": "📊 Analyse..."}
        
        query = input_data.get("query", "")
        
        query_embedding = self.embedding_model.encode(query, convert_to_tensor=False).tolist()
        results = self.vector_store.query(project_id=str(project_id), query_embedding=query_embedding, n_results=3)
        
        context = "\n\n".join([f"[{m.get('filename')}]\n{d[:500]}" for d, m in zip(results['documents'][0], results['metadatas'][0])])
        
        system_prompt = PROMPTS["analysis"].format(domain="juridique")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"CONTEXTE:\n{context}\n\nQUESTION: {query}"}
        ]
        
        conv = Conversation(user_id=self.user_id, title="Analysis", provider_name=self.config.get("llm_provider", "ollama"), model=self.config.get("llm_model", "mistral"), temperature=0.3)
        self.db.add(conv)
        self.db.flush()
        
        for msg in messages:
            self.db.add(MessageModel(conversation_id=conv.id, role=msg["role"], content=msg["content"]))
        self.db.commit()
        
        analysis = ""
        async for chunk in self.llm_service.stream_chat(self.user_id, conv.id, "", self.config.get("llm_provider", "ollama"), self.config.get("llm_model", "mistral"), 0.3):
            if chunk:
                analysis += chunk
                yield {"type": "stream", "data": chunk}
        
        yield {"type": "result", "data": {"analysis": analysis, "sources": [m.get("filename") for m in results['metadatas'][0]]}}
    
    # ═══════════════════════════════════════════════════════════════
    # FONCTIONS UTILITAIRES
    # ═══════════════════════════════════════════════════════════════
    
    async def _init_models(self):
        if not self.embedding_model:
            self.embedding_model = SentenceTransformer(self.embedding_model_name)
        if not self.nlp:
            # ✅ Utiliser fr_core_news_lg qui a un composant NER natif
            try:
                self.nlp = spacy.load("fr_core_news_lg")
            except:
                raise RuntimeError("French spaCy model not installed. Run: python -m spacy download fr_core_news_lg")
            
            # Ajouter entity_ruler AVANT ner pour patterns juridiques prioritaires
            if "entity_ruler" not in self.nlp.pipe_names:
                ruler = self.nlp.add_pipe("entity_ruler", before="ner")
                ruler.add_patterns(NER_PATTERNS)
    
    async def _ensure_project(self) -> UUID:
        if not self.project_id:
            raise ValueError("project_id required")
        project = self.db.query(Project).filter(Project.id == self.project_id, Project.user_id == self.user_id).first()
        if not project:
            raise ValueError(f"Project {self.project_id} not found")
        return self.project_id
    
    async def _process_documents(self, doc_paths: List[str], project_id: UUID):
        from app.services.document_processor import DocumentProcessor
        processor = DocumentProcessor()
        chunker = SmartChunker(chunk_size=800, overlap=100)
        
        for doc_path in doc_paths:
            file_path = Path(doc_path)
            existing = self.db.query(Document).filter(Document.project_id == project_id, Document.filename == file_path.name).first()
            if existing:
                continue
            
            text = processor.extract_text(file_path)
            if not text:
                continue
            
            entities = []
            if self.nlp:
                doc_nlp = self.nlp(text[:100000])
                entities = [{"text": e.text, "label": e.label_} for e in doc_nlp.ents]
            
            document = Document(
                project_id=project_id, filename=file_path.name, file_path=str(file_path),
                file_type=file_path.suffix.lstrip('.'), file_size=file_path.stat().st_size,
                status='processing', metadata={"entities": entities}
            )
            self.db.add(document)
            self.db.commit()
            self.db.refresh(document)
            
            chunks = chunker.chunk_text(text, metadata={"filename": file_path.name, "document_id": str(document.id)})
            embeddings = self.embedding_model.encode([c["text"] for c in chunks], convert_to_tensor=False).tolist()
            
            self.vector_store.add_documents(
                project_id=str(project_id),
                documents=[c["text"] for c in chunks],
                metadatas=[c["metadata"] for c in chunks],
                ids=[f"{document.id}_{i}" for i in range(len(chunks))],
                embeddings=embeddings
            )
            
            document.status = 'completed'
            document.chunk_count = len(chunks)
            self.db.commit()
    
    async def _classify_claim(self, text: str, context: Dict) -> Dict:
        text_lower = text.lower()
        claim_type = "contestation"
        for ctype, kws in CLAIM_TYPES.items():
            if any(k in text_lower for k in kws):
                claim_type = ctype
                break
        
        urgency = context.get("urgency", "medium")
        if any(w in text_lower for w in ["urgent", "immédiat", "avant le"]):
            urgency = "high"
        
        domain = "general"
        for d, kws in {"fiscal": ["impôt", "cgi"], "social": ["urssaf", "cotisation"], "commercial": ["contrat", "client"]}.items():
            if any(k in text_lower for k in kws):
                domain = d
                break
        
        return {"type": claim_type, "domain": domain, "urgency": urgency, "deadline": "À déterminer"}
    
    async def _extract_legal_entities(self, text: str) -> Dict:
        if not self.nlp:
            return {"legal_refs": [], "amounts": [], "deadlines": [], "authorities": [], "procedures": []}
        
        doc = self.nlp(text[:50000])
        entities = {"legal_refs": [], "amounts": [], "deadlines": [], "authorities": [], "procedures": []}
        
        for ent in doc.ents:
            data = {"text": ent.text, "label": ent.label_}
            if ent.label_ == "LEGAL_REF":
                entities["legal_refs"].append(data)
            elif ent.label_ == "AMOUNT":
                entities["amounts"].append(data)
            elif ent.label_ == "DEADLINE":
                entities["deadlines"].append(data)
            elif ent.label_ == "AUTHORITY":
                entities["authorities"].append(data)
            elif ent.label_ == "PROCEDURE":
                entities["procedures"].append(data)
        
        return entities
    
    async def _find_applicable_law(self, query: str, domain: str, project_id: UUID) -> List[Dict]:
        emb = self.embedding_model.encode(query, convert_to_tensor=False).tolist()
        results = self.vector_store.query(project_id=str(project_id), query_embedding=emb, n_results=5)
        
        laws = []
        if results['documents'][0]:
            for doc, meta, dist in zip(results['documents'][0], results['metadatas'][0], results['distances'][0]):
                laws.append({"article": meta.get("filename", ""), "text": doc[:300], "relevance_score": 1 - dist})
        return laws
    
    async def _find_similar_cases(self, query: str, claim_type: str, project_id: UUID) -> List[Dict]:
        emb = self.embedding_model.encode(f"jurisprudence {claim_type} {query}", convert_to_tensor=False).tolist()
        results = self.vector_store.query(project_id=str(project_id), query_embedding=emb, n_results=10)
        
        cases = []
        if results['documents'][0]:
            for doc, meta, dist in zip(results['documents'][0], results['metadatas'][0], results['distances'][0]):
                if any(k in doc.lower() for k in ["arrêt", "jugement", "jurisprudence"]):
                    cases.append({
                        "reference": meta.get("filename", ""),
                        "excerpt": doc[:200],
                        "similarity": 1 - dist,
                        "decision": "favorable" if "favorable" in doc.lower() else "défavorable"
                    })
        return cases
    
    async def _quick_risk_assessment(self, query: str, classification: Dict, similar_cases: List) -> Dict:
        unfav = sum(1 for c in similar_cases if c["decision"] == "défavorable")
        total = len(similar_cases)
        score = unfav / total if total > 0 else 0.5
        
        if classification["urgency"] == "high":
            score += 0.15
        
        score = min(max(score, 0), 1)
        level = "critique" if score > 0.7 else ("élevé" if score > 0.5 else ("moyen" if score > 0.3 else "faible"))
        
        return {"level": level, "score": round(score, 2), "factors": [f"{unfav}/{total} cas défavorables"]}
    
    async def _generate_claim_response(self, claim_text: str, classification: Dict, entities: Dict, 
                                      applicable_law: List, similar_cases: List, risk: Dict, context: Dict) -> str:
        legal_ctx = "\n".join([f"- {l['article']}: {l['text']}" for l in applicable_law[:3]])
        cases_ctx = "\n".join([f"- {c['reference']}: {c['decision']}" for c in similar_cases[:3]])
        
        prompt = PROMPTS.get("claim_response", "").format(
            claim_text=claim_text[:1000], claim_type=classification['type'],
            domain=classification['domain'], legal_context=legal_ctx,
            cases_context=cases_ctx, risk_level=risk['level'], urgency=classification['urgency']
        )
        
        conv = Conversation(user_id=self.user_id, title="Claim Response", 
                           provider_name=self.config.get("llm_provider", "ollama"),
                           model=self.config.get("llm_model", "mistral"), temperature=0.3)
        self.db.add(conv)
        self.db.flush()
        self.db.add(MessageModel(conversation_id=conv.id, role="user", content=prompt))
        self.db.commit()
        
        response = ""
        async for chunk in self.llm_service.stream_chat(self.user_id, conv.id, "", 
                                                        self.config.get("llm_provider", "ollama"),
                                                        self.config.get("llm_model", "mistral"), 0.3):
            if chunk:
                response += chunk
        
        return response
    
    def _generate_claim_recommendations(self, classification: Dict, risk: Dict, entities: Dict) -> List[Dict]:
        recs = []
        if risk["level"] in ["élevé", "critique"]:
            recs.append({"action": "Consulter avocat spécialisé", "priority": "immédiate"})
        if classification["urgency"] == "high":
            recs.append({"action": f"Répondre avant {classification.get('deadline', '48h')}", "priority": "immédiate"})
        recs.append({"action": "Archiver correspondance", "priority": "normale"})
        return recs
    
    async def _detect_document_type(self, doc_path: str) -> str:
        from app.services.document_processor import DocumentProcessor
        text = DocumentProcessor().extract_text(Path(doc_path))[:5000].lower()
        
        patterns = {
            "rgpd_notice": ["rgpd", "données personnelles"],
            "cgv": ["conditions générales", "cgv"],
            "contract": ["contrat", "parties"],
            "policy": ["politique", "confidentialité"]
        }
        
        for dtype, kws in patterns.items():
            if sum(1 for k in kws if k in text) >= 2:
                return dtype
        return "generic"
    
    async def _extract_clauses(self, text: str, doc_type: str) -> Dict:
        patterns = {
            "prix": r"prix\s*[:\-]?\s*([^\n]{10,100})",
            "durée": r"durée\s*[:\-]?\s*([^\n]{10,100})",
            "résiliation": r"résiliation\s*[:\-]?\s*([^\n]{10,100})"
        }
        clauses = {}
        for ctype, pattern in patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                clauses[ctype] = matches
        return clauses
    
    async def _check_compliance_points(self, text: str, clauses: Dict, checklist: Dict) -> Dict:
        results = {"items": []}
        text_lower = text.lower()
        
        for item in checklist.get("required_items", []):
            kws = item.get("keywords", [])
            if isinstance(kws, str):
                kws = [kws]
            compliant = all(k.lower() in text_lower for k in kws)
            
            results["items"].append({
                "item": item["name"],
                "compliant": compliant,
                "severity": item.get("severity", "majeur")
            })
        return results
    
    def _generate_compliance_recommendations(self, results: Dict, doc_type: str) -> List[Dict]:
        recs = []
        for item in results["items"]:
            if not item["compliant"] and item["severity"] in ["bloquant", "majeur"]:
                recs.append({"item": item["item"], "action": f"Ajouter {item['item']}", 
                           "priority": "haute" if item["severity"] == "bloquant" else "moyenne"})
        return recs
    
    async def _generate_compliance_report(self, doc_name: str, doc_type: str, score: float, 
                                         results: Dict, recs: List) -> str:
        report = f"""
RAPPORT AUDIT CONFORMITÉ
========================
Document: {doc_name}
Score: {int(score*100)}%

RÉSULTATS:
"""
        for item in results["items"]:
            status = "✅" if item["compliant"] else "❌"
            report += f"{status} {item['item']}\n"
        
        if recs:
            report += "\nRECOMMANDATIONS:\n"
            for i, r in enumerate(recs, 1):
                report += f"{i}. {r['action']} (Priorité: {r['priority']})\n"
        
        return report
    
    async def _detect_risk_patterns(self, query: str, entities: Dict) -> List[Dict]:
        patterns = []
        q = query.lower()
        
        if any(w in q for w in ["selon", "environ", "approximativement"]):
            patterns.append({"type": "clause_floue", "severity": "moyen"})
        
        if entities.get("amounts") and not any(w in q for w in ["garantie", "caution"]):
            patterns.append({"type": "exposition_financiere", "severity": "élevé"})
        
        return patterns
    
    async def _find_unfavorable_cases(self, query: str, risk_types: List, project_id: UUID) -> List[Dict]:
        cases = await self._find_similar_cases(query, "contentieux", project_id)
        return [c for c in cases if c["decision"] == "défavorable"]
    
    async def _assess_risk_category(self, query: str, risk_type: str, entities: Dict, 
                                    unfav: List, project_id: UUID) -> Optional[Dict]:
        emb = self.embedding_model.encode(f"{risk_type} risque {query}", convert_to_tensor=False).tolist()
        results = self.vector_store.query(project_id=str(project_id), query_embedding=emb, n_results=3)
        
        if not results['documents'][0]:
            return None
        
        prob = 0.5
        if len(unfav) > 5:
            prob = 0.75
        
        impact = "moyen"
        if entities.get("amounts"):
            impact = "élevé"
        
        return {
            "category": risk_type,
            "description": f"Risque {risk_type}",
            "probability": prob,
            "impact": impact,
            "mitigation": f"Réviser clauses {risk_type}"
        }
    
    def _calculate_overall_risk(self, factors: List) -> Dict:
        if not factors:
            return {"level": "faible", "score": 0.0}
        
        impacts = {"faible": 0.3, "moyen": 0.6, "élevé": 1.0}
        total_score = sum(f["probability"] * impacts.get(f["impact"], 0.5) * RISK_WEIGHTS.get(f["category"], 0.5) for f in factors)
        avg = total_score / len(factors)
        
        level = "critique" if avg > 0.7 else ("élevé" if avg > 0.5 else ("moyen" if avg > 0.3 else "faible"))
        return {"level": level, "score": round(avg, 2)}
    
    def _generate_mitigation_strategies(self, factors: List) -> List[Dict]:
        strategies = []
        for f in factors:
            if f["probability"] > 0.6:
                strategies.append({
                    "risk_id": f["category"],
                    "action": f.get("mitigation", "Réviser documentation"),
                    "priority": "immédiate" if f["impact"] == "élevé" else "court_terme"
                })
        return strategies
    
    def _estimate_financial_impact(self, factors: List, context: Dict) -> Dict:
        base = context.get("financial_exposure", 0)
        total = base
        for f in factors:
            if f["category"] == "fiscal":
                total += base * 0.3
        return {"base_exposure": base, "estimated_total_exposure": int(total)}
    
    async def _generate_risk_analysis_report(self, query: str, factors: List, overall: Dict, 
                                            unfav: List, mitigation: List) -> str:
        return f"""
ANALYSE RISQUE JURIDIQUE
========================
Niveau: {overall['level'].upper()} ({overall['score']:.2f})
Facteurs: {len(factors)}
Cas défavorables: {len(unfav)}

FACTEURS:
""" + "\n".join([f"- {f['category']}: {f['impact']} (prob: {int(f['probability']*100)}%)" for f in factors]) + """

MITIGATIONS:
""" + "\n".join([f"- {s['action']} (priorité: {s['priority']})" for s in mitigation[:5]])
    
    async def _generate_document_content(self, template: Dict, data: Dict, doc_type: str, project_id: UUID) -> str:
        prompt = PROMPTS.get(f"draft_{doc_type}", PROMPTS.get("generic_draft", "Générer un document juridique")).format(**data)
        
        conv = Conversation(user_id=self.user_id, title=f"Draft {doc_type}",
                           provider_name=self.config.get("llm_provider", "ollama"),
                           model=self.config.get("llm_model", "mistral"), temperature=0.4)
        self.db.add(conv)
        self.db.flush()
        self.db.add(MessageModel(conversation_id=conv.id, role="user", content=prompt))
        self.db.commit()
        
        content = ""
        async for chunk in self.llm_service.stream_chat(self.user_id, conv.id, "",
                                                        self.config.get("llm_provider", "ollama"),
                                                        self.config.get("llm_model", "mistral"), 0.4):
            if chunk:
                content += chunk
        
        if template:
            content = render_template(template, {"content": content, **data})
        
        return content
    
    async def _suggest_document_improvements(self, content: str, doc_type: str, legal_refs: List) -> List[str]:
        suggestions = []
        if len(content.split()) < 100:
            suggestions.append("Document trop court")
        if len(legal_refs) == 0:
            suggestions.append("Ajouter références légales")
        return suggestions
    
    async def _search_legifrance(self, query: str) -> List[Dict]:
        # TODO: Implémenter API Légifrance
        return []
    
    def _merge_search_results(self, rag: Dict, external: List) -> List[Dict]:
        results = []
        if rag.get('documents') and rag['documents'][0]:
            for doc, meta, dist in zip(rag['documents'][0], rag['metadatas'][0], rag['distances'][0]):
                results.append({"text": doc, "source": meta.get("filename", ""), "score": 1 - dist})
        
        for ext in external:
            results.append({"text": ext.get("text", ""), "source": "Légifrance", "score": 0.5})
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return results
    
    async def _scan_legal_updates(self, domain: str, since: Optional[str]) -> List[Dict]:
        # TODO: Implémenter scan
        return []
    
    async def _analyze_legal_impact(self, text: Dict, project_id: UUID) -> Dict:
        return {"severity": "none"}
    
    async def _gather_training_content(self, topic: str, project_id: UUID) -> List[Dict]:
        emb = self.embedding_model.encode(topic, convert_to_tensor=False).tolist()
        results = self.vector_store.query(project_id=str(project_id), query_embedding=emb, n_results=10)
        
        content = []
        if results['documents'][0]:
            for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
                content.append({"text": doc, "source": meta.get("filename", "")})
        return content
    
    async def _generate_training_sheet(self, topic: str, content: List, audience: str) -> str:
        return f"""
FICHE PRATIQUE: {topic.upper()}
================================
Public: {audience}

POINTS CLÉS:
""" + "\n".join([f"{i+1}. {c['text'][:200]}..." for i, c in enumerate(content[:5])])
    
    async def _generate_training_guide(self, topic: str, content: List, audience: str) -> str:
        return await self._generate_training_sheet(topic, content, audience)
    
    async def _generate_training_faq(self, topic: str, content: List, audience: str) -> str:
        return f"""
FAQ: {topic.upper()}
====================
Q1: Qu'est-ce que {topic} ?
A1: [Voir contenu]

Q2: Quelles obligations légales ?
A2: [Voir contenu]
"""