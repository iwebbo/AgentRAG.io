"""
Agent Expert-Comptable - Version Production
============================================

Remplace un expert-comptable avec toutes ses compétences métier.

MODES DISPONIBLES:
- accounting_entry   : Saisie/vérification écritures comptables
- annual_statements  : Préparation comptes annuels (bilan, résultat)
- tax_optimization   : Calcul impôts et optimisation fiscale
- social_payroll     : Gestion paie et charges sociales
- audit_review       : Audit et révision comptable
- strategic_advice   : Conseil gestion et stratégie
- compliance_check   : Vérification conformité légale

Architecture:
- Embedding: sentence-transformers/paraphrase-multilingual-mpnet-base-v2
- NER: spaCy fr_core_news_lg + patterns comptables
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
from app.models.agent import Agent
from app.services.chunker import SmartChunker

from .accounting_config import (
    PCG_ACCOUNTS, FISCAL_REGIMES, TAX_TYPES, SOCIAL_CHARGES,
    TAX_CREDITS, NER_PATTERNS, ANOMALY_CHECKS, LEGAL_DEADLINES,
    FINANCIAL_RATIOS, ACCOUNTING_SOURCES
)
from .accounting_templates import (
    SYSTEM_PROMPTS, DOCUMENT_TEMPLATES,
    get_system_prompt, render_ecriture_template, render_note_fiscale_template
)

logger = logging.getLogger(__name__)


class AccountingAdvisorAgent(BaseAgent):
    """Agent Expert-Comptable - Monolithique Centralisé"""
    
    def __init__(self, agent_id: UUID, user_id: UUID, config: Dict[str, Any], mcp_config: Dict[str, Any], db: Any):
        super().__init__(agent_id, user_id, config, mcp_config, db)
        self.accounting_config = config.get("accounting_config", {})
        self.domains = self.accounting_config.get("domains", ["comptabilite", "fiscal", "social"])
        self.embedding_model_name = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
        self.embedding_model = None
        self.nlp = None
        self.project_id = config.get("project_id")
    
    async def execute(self, input_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Point d'entrée principal de l'agent comptable.
        
        input_data structure:
        {
            "mode": "accounting_entry|annual_statements|tax_optimization|social_payroll|audit_review|strategic_advice|compliance_check",
            "query": "Demande utilisateur",
            "documents": ["/path/to/facture.pdf"],  # Optionnel
            "context": {
                "fiscal_year": "2024",
                "regime": "reel_simplifie",
                "urgency": "normal"
            }
        }
        """
        try:
            mode = input_data.get("mode", "accounting_entry")
            yield {"type": "status", "data": f"🧮 Démarrage agent comptable (mode: {mode})"}
            
            # Initialisation modèles
            await self._ensure_models()
            project_id = await self._ensure_project()
            
            # Traitement documents si fournis
            doc_paths = input_data.get("documents", [])
            if doc_paths:
                yield {"type": "status", "data": f"📄 Traitement {len(doc_paths)} document(s)..."}
                await self._process_documents(doc_paths, project_id)
            
            # Routage selon mode
            if mode == "accounting_entry":
                async for update in self._mode_accounting_entry(input_data, project_id):
                    yield update
            
            elif mode == "annual_statements":
                async for update in self._mode_annual_statements(input_data, project_id):
                    yield update
            
            elif mode == "tax_optimization":
                async for update in self._mode_tax_optimization(input_data, project_id):
                    yield update
            
            elif mode == "social_payroll":
                async for update in self._mode_social_payroll(input_data, project_id):
                    yield update
            
            elif mode == "audit_review":
                async for update in self._mode_audit_review(input_data, project_id):
                    yield update
            
            elif mode == "strategic_advice":
                async for update in self._mode_strategic_advice(input_data, project_id):
                    yield update
            
            elif mode == "compliance_check":
                async for update in self._mode_compliance_check(input_data, project_id):
                    yield update
            
            else:
                raise ValueError(f"Mode inconnu: {mode}")
            
            yield {"type": "status", "data": "✅ Traitement terminé"}
        
        except Exception as e:
            logger.error(f"Accounting agent error: {str(e)}", exc_info=True)
            yield {"type": "error", "data": str(e)}
    
    # ═══════════════════════════════════════════════════════════════
    # MODE 1: SAISIE/VÉRIFICATION ÉCRITURES COMPTABLES
    # ═══════════════════════════════════════════════════════════════
    
    async def _mode_accounting_entry(self, input_data: Dict[str, Any], project_id: UUID) -> AsyncGenerator[Dict[str, Any], None]:
        """Saisie et vérification écritures comptables"""
        yield {"type": "status", "data": "🧮 Analyse pièces justificatives..."}
        
        query = input_data.get("query", "")
        context = input_data.get("context", {})
        
        # Extraction entités comptables
        entities = await self._extract_accounting_entities(query)
        
        # RAG: Recherche docs similaires (factures, relevés)
        yield {"type": "status", "data": "📚 Recherche documents de référence..."}
        query_embedding = self.embedding_model.encode(query, convert_to_tensor=False).tolist()
        rag_results = self.vector_store.query(project_id=str(project_id), query_embedding=query_embedding, n_results=5)
        
        rag_context = "\n\n".join([
            f"[SOURCE: {meta.get('filename')}]\n{doc[:600]}"
            for doc, meta in zip(rag_results.get('documents', [[]])[0], rag_results.get('metadatas', [[]])[0])
        ]) if rag_results.get('documents') else "Aucun document comptable de référence."
        
        # Génération écriture par LLM
        yield {"type": "status", "data": "🧠 Génération écriture comptable..."}
        
        system_prompt = get_system_prompt("accounting_entry")
        
        user_prompt = f"""Tu dois analyser cette opération comptable et proposer l'écriture adaptée.

DEMANDE CLIENT :
{query}

ENTITÉS DÉTECTÉES :
- Montants : {', '.join([e['text'] for e in entities.get('amounts', [])])}
- Comptes PCG : {', '.join([e['text'] for e in entities.get('accounts', [])])}
- Dates : {', '.join([e['text'] for e in entities.get('dates', [])])}
- Organismes : {', '.join([e['text'] for e in entities.get('organismes', [])])}

DOCUMENTS DE RÉFÉRENCE :
{rag_context}

CONTEXTE :
- Exercice fiscal : {context.get('fiscal_year', '2024')}
- Régime TVA : {context.get('tva_regime', 'réel normal')}

CONSIGNES :

1. **Imputation comptable** :
   - Identifie la nature de l'opération (achat, vente, charge, produit)
   - Propose les comptes PCG appropriés (référence PCG 2025)
   - Justifie chaque imputation

2. **TVA** :
   - Détermine le taux applicable (20%, 10%, 5.5%, 2.1%)
   - Calcule TVA déductible ou collectée selon contexte
   - Précise le compte TVA (4456, 4457)

3. **Structure écriture** :
   Génère une écriture au format :
   ```
   Date | Journal | N° Pièce | Compte | Libellé | Débit | Crédit
   ```
   
4. **Contrôles** :
   - Vérifie équilibre Débit = Crédit
   - Alerte sur comptes anormaux (ex: 411 créditeur sans justification)
   - Signale doublons potentiels

5. **Format de réponse** :
   Présente l'écriture de manière claire et professionnelle.
   Explique brièvement les choix d'imputation.
   Signale les points d'attention éventuels.

Réponds de manière structurée et professionnelle.
"""
        
        # Combiner system + user prompt
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        # Streaming LLM
        llm_response_chunks = []
        async for chunk in self._stream_llm_response(full_prompt, "Écriture Comptable"):
            llm_response_chunks.append(chunk)
            yield {"type": "stream", "data": chunk}
        
        llm_response = "".join(llm_response_chunks)
        
        # Détection anomalies automatiques
        anomalies = await self._detect_anomalies(entities, context)
        
        yield {
            "type": "result",
            "data": {
                "mode": "accounting_entry",
                "entities": entities,
                "ecriture_generee": llm_response,
                "anomalies_detectees": anomalies,
                "rag_sources": len(rag_results.get('documents', [[]])[0]),
                "summary": f"Écriture comptable générée - {len(anomalies)} anomalie(s) détectée(s)"
            }
        }
    
    # ═══════════════════════════════════════════════════════════════
    # MODE 2: COMPTES ANNUELS
    # ═══════════════════════════════════════════════════════════════
    
    async def _mode_annual_statements(self, input_data: Dict[str, Any], project_id: UUID) -> AsyncGenerator[Dict[str, Any], None]:
        """Préparation comptes annuels (bilan, résultat, annexe)"""
        yield {"type": "status", "data": "📊 Préparation comptes annuels..."}
        
        query = input_data.get("query", "")
        context = input_data.get("context", {})
        fiscal_year = context.get("fiscal_year", "2024")
        
        # RAG: Balance comptable et documents clôture
        yield {"type": "status", "data": "📚 Récupération balance et documents clôture..."}
        search_queries = [
            f"balance comptable {fiscal_year}",
            f"inventaire {fiscal_year}",
            f"amortissements provisions"
        ]
        
        all_docs = []
        for sq in search_queries:
            emb = self.embedding_model.encode(sq, convert_to_tensor=False).tolist()
            results = self.vector_store.query(project_id=str(project_id), query_embedding=emb, n_results=3)
            if results.get('documents'):
                all_docs.extend(zip(results['documents'][0], results['metadatas'][0]))
        
        rag_context = "\n\n".join([
            f"[{meta.get('filename')}]\n{doc[:800]}"
            for doc, meta in all_docs[:10]
        ]) if all_docs else "Aucune balance comptable trouvée."
        
        # Génération états financiers par LLM
        yield {"type": "status", "data": "🧠 Génération états financiers..."}
        
        system_prompt = get_system_prompt("annual_statements")
        
        user_prompt = f"""Tu dois préparer les comptes annuels pour l'exercice {fiscal_year}.

DEMANDE CLIENT :
{query}

DOCUMENTS COMPTABLES DISPONIBLES :
{rag_context}

CONTEXTE :
- Exercice : du 01/01/{fiscal_year} au 31/12/{fiscal_year}
- Régime fiscal : {context.get('regime', 'réel simplifié')}
- Type société : {context.get('company_type', 'SARL')}

MISSIONS :

1. **Bilan comptable** :
   - ACTIF (immobilisations, actif circulant, trésorerie)
   - PASSIF (capitaux propres, dettes)
   - Vérifier équilibre Actif = Passif

2. **Compte de résultat** :
   - Produits d'exploitation
   - Charges d'exploitation
   - Résultat d'exploitation, financier, exceptionnel
   - Résultat net

3. **Annexe comptable** :
   - Méthodes comptables appliquées
   - Événements significatifs
   - Engagements hors bilan

4. **Ratios financiers** :
   - Liquidité générale
   - Solvabilité
   - Rentabilité nette
   - Délais clients/fournisseurs

5. **Liasse fiscale** :
   - Identifier la liasse applicable (2065 IS, 2031 BIC)
   - Pointer les éléments à déclarer

Présente les états de manière structurée et professionnelle.
Calcule les ratios clés et interprète-les.
Signale les points d'attention pour la direction.
"""
        
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        llm_response_chunks = []
        async for chunk in self._stream_llm_response(full_prompt, "Comptes Annuels"):
            llm_response_chunks.append(chunk)
            yield {"type": "stream", "data": chunk}
        
        llm_response = "".join(llm_response_chunks)
        
        yield {
            "type": "result",
            "data": {
                "mode": "annual_statements",
                "fiscal_year": fiscal_year,
                "etats_financiers": llm_response,
                "documents_sources": len(all_docs),
                "summary": f"Comptes annuels {fiscal_year} générés"
            }
        }
    
    # ═══════════════════════════════════════════════════════════════
    # MODE 3: OPTIMISATION FISCALE
    # ═══════════════════════════════════════════════════════════════
    
    async def _mode_tax_optimization(self, input_data: Dict[str, Any], project_id: UUID) -> AsyncGenerator[Dict[str, Any], None]:
        """Calcul impôts et optimisation fiscale légale"""
        yield {"type": "status", "data": "💰 Analyse situation fiscale..."}
        
        query = input_data.get("query", "")
        context = input_data.get("context", {})
        
        # RAG: Recherche docs fiscaux
        yield {"type": "status", "data": "📚 Recherche documentation fiscale..."}
        tax_queries = [
            "déclarations fiscales impôts",
            "crédits d'impôt",
            "optimisation fiscale régime"
        ]
        
        tax_docs = []
        for tq in tax_queries:
            emb = self.embedding_model.encode(tq, convert_to_tensor=False).tolist()
            results = self.vector_store.query(project_id=str(project_id), query_embedding=emb, n_results=3)
            if results.get('documents'):
                tax_docs.extend(zip(results['documents'][0], results['metadatas'][0]))
        
        rag_context = "\n\n".join([
            f"[{meta.get('filename')}]\n{doc[:700]}"
            for doc, meta in tax_docs[:8]
        ]) if tax_docs else "Aucun document fiscal de référence."
        
        # Génération analyse fiscale par LLM
        yield {"type": "status", "data": "🧠 Simulation optimisations fiscales..."}
        
        system_prompt = get_system_prompt("tax_optimization")
        
        user_prompt = f"""Tu dois analyser la situation fiscale et proposer des optimisations légales.

DEMANDE CLIENT :
{query}

DOCUMENTS FISCAUX DISPONIBLES :
{rag_context}

CONTEXTE :
- Exercice fiscal : {context.get('fiscal_year', '2024')}
- Régime actuel : {context.get('regime', 'réel simplifié')}
- CA estimé : {context.get('ca_estimate', 'NC')}€

MISSIONS :

1. **Calcul des impôts** :
   - IS (25% ou 15% <38k€)
   - IR (barème 2025 selon tranches)
   - TVA (régime applicable)
   - CET (CFE + CVAE si CA >500k€)

2. **Crédits d'impôt applicables** :
   - CIR (30% dépenses R&D <100M€)
   - CII (20% innovation, plafond 400k€)
   - JEI (exonérations IS + charges)
   - Apprentissage (1600€ par apprenti)

3. **Optimisation régime** :
   - Micro vs Réel : simulation économies
   - IS vs IR : selon situation personnelle
   - TVA : franchise, réel simplifié, réel normal

4. **Gestion déficits et amortissements** :
   - Report déficits (1 an arrière, 10 ans avant)
   - Optimisation amortissements dégressifs
   - Provisions déductibles

5. **Plan d'action chiffré** :
   - Scénario actuel (impôts calculés)
   - Scénario optimisé (économies potentielles)
   - Actions concrètes à entreprendre

Présente une analyse structurée avec :
- Calculs détaillés et justifiés
- Références CGI et BOFIP
- Tableau comparatif scénarios
- Recommandations priorisées

Ton : Professionnel, didactique, rassurant sur la légalité.
"""
        
        llm_response_chunks = []
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        llm_response_chunks = []
        async for chunk in self._stream_llm_response(full_prompt, "Agent Comptable"):
            llm_response_chunks.append(chunk)
            yield {"type": "stream", "data": chunk}
        
        llm_response = "".join(llm_response_chunks)
        
        yield {
            "type": "result",
            "data": {
                "mode": "tax_optimization",
                "analyse_fiscale": llm_response,
                "documents_sources": len(tax_docs),
                "summary": "Analyse fiscale et optimisations générées"
            }
        }
    
    # ═══════════════════════════════════════════════════════════════
    # MODE 4: GESTION SOCIALE ET PAIE
    # ═══════════════════════════════════════════════════════════════
    
    async def _mode_social_payroll(self, input_data: Dict[str, Any], project_id: UUID) -> AsyncGenerator[Dict[str, Any], None]:
        """Gestion paie et charges sociales"""
        yield {"type": "status", "data": "👥 Gestion paie et charges sociales..."}
        
        query = input_data.get("query", "")
        context = input_data.get("context", {})
        
        # RAG: Recherche éléments paie
        yield {"type": "status", "data": "📚 Recherche éléments de paie..."}
        emb = self.embedding_model.encode(query, convert_to_tensor=False).tolist()
        rag_results = self.vector_store.query(project_id=str(project_id), query_embedding=emb, n_results=5)
        
        rag_context = "\n\n".join([
            f"[{meta.get('filename')}]\n{doc[:600]}"
            for doc, meta in zip(rag_results.get('documents', [[]])[0], rag_results.get('metadatas', [[]])[0])
        ]) if rag_results.get('documents') else "Aucun élément de paie trouvé."
        
        # Génération par LLM
        yield {"type": "status", "data": "🧠 Calcul bulletin de paie..."}
        
        system_prompt = get_system_prompt("social_payroll")
        
        user_prompt = f"""Tu dois gérer la paie et les charges sociales.

DEMANDE CLIENT :
{query}

ÉLÉMENTS DISPONIBLES :
{rag_context}

CONTEXTE :
- Période : {context.get('period', 'Mois en cours')}
- Convention collective : {context.get('convention', 'NC')}

MISSIONS :

1. **Bulletin de paie** :
   - Salaire brut
   - Cotisations sociales (URSSAF, retraite, chômage, prévoyance)
   - CSG/CRDS non déductible
   - Net à payer avant impôt
   - Prélèvement à la source
   - Net à payer

2. **Charges sociales 2025** :
   - Part salariale : 22.25% (maladie, vieillesse, CSG/CRDS)
   - Part patronale : 42% (moyenne)
   - Retraite complémentaire AGIRC-ARRCO : 15.40% total
   - Chômage : 4.05% (patronal uniquement)
   - Plafond SS mensuel 2025 : 3864€

3. **DSN** :
   - Éléments à déclarer (individuel nominatif)
   - Échéance : 15 du mois suivant pour >50 salariés, 5 si <50

4. **Conformité** :
   - Vérification respect convention collective
   - SMIC, minimums conventionnels
   - Heures supplémentaires (majoration 25% ou 50%)

5. **Simulations** :
   - Coût total employeur (brut + charges)
   - Impact d'une embauche/licenciement

Présente :
- Bulletin de paie détaillé
- Calculs étape par étape
- Total charges patronales
- Points d'attention légaux
"""
        
        llm_response_chunks = []
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        llm_response_chunks = []
        async for chunk in self._stream_llm_response(full_prompt, "Agent Comptable"):
            llm_response_chunks.append(chunk)
            yield {"type": "stream", "data": chunk}
        
        llm_response = "".join(llm_response_chunks)
        
        yield {
            "type": "result",
            "data": {
                "mode": "social_payroll",
                "bulletin_paie": llm_response,
                "summary": "Bulletin de paie et charges sociales générés"
            }
        }
    
    # ═══════════════════════════════════════════════════════════════
    # MODE 5: AUDIT ET RÉVISION
    # ═══════════════════════════════════════════════════════════════
    
    async def _mode_audit_review(self, input_data: Dict[str, Any], project_id: UUID) -> AsyncGenerator[Dict[str, Any], None]:
        """Audit et révision comptable"""
        yield {"type": "status", "data": "🔍 Audit comptable..."}
        
        query = input_data.get("query", "")
        context = input_data.get("context", {})
        
        # RAG: Recherche tous docs comptables
        yield {"type": "status", "data": "📚 Récupération documents comptables..."}
        emb = self.embedding_model.encode("documents comptables balance écritures", convert_to_tensor=False).tolist()
        rag_results = self.vector_store.query(project_id=str(project_id), query_embedding=emb, n_results=10)
        
        rag_context = "\n\n".join([
            f"[{meta.get('filename')}]\n{doc[:500]}"
            for doc, meta in zip(rag_results.get('documents', [[]])[0], rag_results.get('metadatas', [[]])[0])
        ]) if rag_results.get('documents') else "Aucun document disponible."
        
        # Génération rapport audit par LLM
        yield {"type": "status", "data": "🧠 Génération rapport d'audit..."}
        
        system_prompt = get_system_prompt("audit_review")
        
        user_prompt = f"""Tu dois réaliser un audit comptable et produire un rapport.

DEMANDE CLIENT :
{query}

DOCUMENTS COMPTABLES AUDITÉS :
{rag_context}

CONTEXTE :
- Type audit : {context.get('audit_type', 'révision générale')}
- Périmètre : {context.get('scope', 'comptes annuels')}

MISSIONS :

1. **Révision des comptes** :
   - Cohérence balance (débit = crédit)
   - Validation imputations comptables
   - Contrôle TVA (collectée, déductible)
   - Vérification rapprochements bancaires

2. **Détection anomalies** :
   - Écritures non équilibrées
   - Comptes solde anormal (ex: 411 créditeur)
   - Doublons factures
   - Incohérences TVA

3. **Évaluation contrôles internes** :
   - Séparation des tâches
   - Procédures validation
   - Traçabilité opérations

4. **Tests analytiques** :
   - Évolution postes clés
   - Ratios financiers
   - Comparaison N/N-1

5. **Rapport d'audit** :
   - Synthèse exécutive
   - Constats détaillés (avec gravité)
   - Recommandations priorisées
   - Plan d'action

Présente un rapport structuré avec :
- Points forts identifiés
- Faiblesses et risques
- Gravité (bloquant/majeur/mineur)
- Recommandations actionnables
"""
        
        llm_response_chunks = []
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        llm_response_chunks = []
        async for chunk in self._stream_llm_response(full_prompt, "Agent Comptable"):
            llm_response_chunks.append(chunk)
            yield {"type": "stream", "data": chunk}
        
        llm_response = "".join(llm_response_chunks)
        
        yield {
            "type": "result",
            "data": {
                "mode": "audit_review",
                "rapport_audit": llm_response,
                "documents_audites": len(rag_results.get('documents', [[]])[0]),
                "summary": "Rapport d'audit comptable généré"
            }
        }
    
    # ═══════════════════════════════════════════════════════════════
    # MODE 6: CONSEIL STRATÉGIQUE
    # ═══════════════════════════════════════════════════════════════
    
    async def _mode_strategic_advice(self, input_data: Dict[str, Any], project_id: UUID) -> AsyncGenerator[Dict[str, Any], None]:
        """Conseil gestion et stratégie"""
        yield {"type": "status", "data": "🎯 Conseil stratégique..."}
        
        query = input_data.get("query", "")
        context = input_data.get("context", {})
        
        # RAG: Recherche docs financiers
        yield {"type": "status", "data": "📚 Analyse situation financière..."}
        emb = self.embedding_model.encode(query, convert_to_tensor=False).tolist()
        rag_results = self.vector_store.query(project_id=str(project_id), query_embedding=emb, n_results=8)
        
        rag_context = "\n\n".join([
            f"[{meta.get('filename')}]\n{doc[:700]}"
            for doc, meta in zip(rag_results.get('documents', [[]])[0], rag_results.get('metadatas', [[]])[0])
        ]) if rag_results.get('documents') else "Aucune donnée financière disponible."
        
        # Génération conseil par LLM
        yield {"type": "status", "data": "🧠 Élaboration recommandations stratégiques..."}
        
        system_prompt = get_system_prompt("strategic_advice")
        
        user_prompt = f"""Tu es conseiller en stratégie d'entreprise. Analyse la situation et propose des recommandations.

DEMANDE CLIENT :
{query}

DONNÉES FINANCIÈRES DISPONIBLES :
{rag_context}

CONTEXTE :
- Secteur : {context.get('sector', 'NC')}
- Taille entreprise : {context.get('size', 'PME')}
- Objectif : {context.get('objective', 'croissance')}

MISSIONS :

1. **Diagnostic financier** :
   - Analyse bilan (structure, équilibre)
   - Analyse compte de résultat (rentabilité)
   - Ratios clés (liquidité, solvabilité, rentabilité)
   - Trésorerie et BFR

2. **Business plan** :
   - Prévisionnel CA, charges, résultat
   - Plan de financement
   - Seuil de rentabilité

3. **Conseil financement** :
   - Prêts bancaires (capacité d'endettement)
   - Subventions publiques (BPI, régions)
   - Levées de fonds si pertinent

4. **Création d'entreprise** :
   - Choix statut (SARL, SAS, EURL, auto-entrepreneur)
   - Avantages/inconvénients fiscaux et sociaux
   - Formalités INPI

5. **Gestion de crise** :
   - Détection signaux faibles
   - Plan de sauvegarde
   - Restructuration dettes

Présente :
- Diagnostic SWOT
- Scénarios chiffrés (pessimiste/réaliste/optimiste)
- Recommandations hiérarchisées
- Plan d'action opérationnel
"""
        
        llm_response_chunks = []
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        llm_response_chunks = []
        async for chunk in self._stream_llm_response(full_prompt, "Agent Comptable"):
            llm_response_chunks.append(chunk)
            yield {"type": "stream", "data": chunk}
        
        llm_response = "".join(llm_response_chunks)
        
        yield {
            "type": "result",
            "data": {
                "mode": "strategic_advice",
                "conseil_strategique": llm_response,
                "summary": "Conseil stratégique et recommandations générés"
            }
        }
    
    # ═══════════════════════════════════════════════════════════════
    # MODE 7: VÉRIFICATION CONFORMITÉ
    # ═══════════════════════════════════════════════════════════════
    
    async def _mode_compliance_check(self, input_data: Dict[str, Any], project_id: UUID) -> AsyncGenerator[Dict[str, Any], None]:
        """Vérification conformité légale"""
        yield {"type": "status", "data": "✅ Vérification conformité..."}
        
        query = input_data.get("query", "")
        context = input_data.get("context", {})
        
        # RAG: Recherche docs obligatoires
        yield {"type": "status", "data": "📚 Vérification documents obligatoires..."}
        emb = self.embedding_model.encode("obligations légales déclarations", convert_to_tensor=False).tolist()
        rag_results = self.vector_store.query(project_id=str(project_id), query_embedding=emb, n_results=8)
        
        rag_context = "\n\n".join([
            f"[{meta.get('filename')}]\n{doc[:600]}"
            for doc, meta in zip(rag_results.get('documents', [[]])[0], rag_results.get('metadatas', [[]])[0])
        ]) if rag_results.get('documents') else "Aucun document de conformité."
        
        # Génération rapport conformité par LLM
        yield {"type": "status", "data": "🧠 Génération rapport de conformité..."}
        
        system_prompt = get_system_prompt("compliance_check")
        
        user_prompt = f"""Tu dois vérifier la conformité aux obligations comptables, fiscales et sociales.

DEMANDE CLIENT :
{query}

DOCUMENTS DISPONIBLES :
{rag_context}

CONTEXTE :
- Période vérifiée : {context.get('period', 'exercice en cours')}
- Régime : {context.get('regime', 'réel simplifié')}

MISSIONS :

1. **Obligations comptables** :
   - Tenue livres obligatoires (journal, grand livre, balance)
   - Inventaire annuel
   - Conservation pièces justificatives (10 ans)

2. **Obligations fiscales** :
   - Déclarations TVA (CA3/CA12)
   - Déclaration IS/IR dans les délais
   - Paiement acomptes IS
   - Liasse fiscale complète

3. **Obligations sociales** :
   - DSN mensuelle (avant le 15)
   - Bulletins de paie conformes
   - Registre unique du personnel
   - Affichages obligatoires

4. **Risques identifiés** :
   - Retards déclarations (pénalités 10-40%)
   - Documents manquants
   - Non-conformités légales

5. **Plan de mise en conformité** :
   - Actions correctives immédiates
   - Échéances à respecter
   - Documentation à produire

Présente :
- Checklist conformité (✅/❌)
- Écarts constatés avec gravité
- Calendrier des obligations à venir
- Recommandations priorisées
"""
        
        llm_response_chunks = []
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        llm_response_chunks = []
        async for chunk in self._stream_llm_response(full_prompt, "Agent Comptable"):
            llm_response_chunks.append(chunk)
            yield {"type": "stream", "data": chunk}
        
        llm_response = "".join(llm_response_chunks)
        
        yield {
            "type": "result",
            "data": {
                "mode": "compliance_check",
                "rapport_conformite": llm_response,
                "summary": "Rapport de conformité généré"
            }
        }
    
    # ═══════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════
    
    async def _ensure_models(self):
        """Initialise embedding model et NER"""
        if not self.embedding_model:
            logger.info(f"Loading embedding model: {self.embedding_model_name}")
            self.embedding_model = SentenceTransformer(self.embedding_model_name)
        
        if not self.nlp:
            try:
                self.nlp = spacy.load("fr_core_news_lg")
                logger.info("✅ spaCy fr_core_news_lg loaded successfully")
            except:
                logger.warning("spaCy fr_core_news_lg not found, NER disabled")
            
            if self.nlp and "entity_ruler" not in self.nlp.pipe_names:
                ruler = self.nlp.add_pipe("entity_ruler", before="ner")
                ruler.add_patterns(NER_PATTERNS)
    
    async def _ensure_project(self) -> UUID:
        """Assure qu'un projet existe, le crée automatiquement si nécessaire"""
        
        # Si project_id fourni, vérifier qu'il existe
        if self.project_id:
            project = self.db.query(Project).filter(
                Project.id == self.project_id, 
                Project.user_id == self.user_id
            ).first()
            if project:
                return self.project_id
            logger.warning(f"Project {self.project_id} not found, creating new one")
        
        # Créer automatiquement un projet dédié pour cet agent
        from uuid import uuid4
        
        agent_record = self.db.query(Agent).filter(Agent.id == self.agent_id).first()
        agent_name = agent_record.name if agent_record else "Agent Comptable"
        
        project = Project(
            id=uuid4(),
            user_id=self.user_id,
            name=f"Project {agent_name}",
            description=f"Projet RAG auto-créé pour agent comptable",
            embedding_model="sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
            chunk_size=800,
            chunk_overlap=100,
            is_active=True
        )
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        
        # Mettre à jour la config de l'agent avec le project_id
        if agent_record:
            agent_record.config["project_id"] = str(project.id)
            self.db.commit()
        
        self.project_id = project.id
        
        logger.info(f"✅ Projet auto-créé: {project.id} pour agent {self.agent_id}")
        
        return project.id
    
    async def _process_documents(self, doc_paths: List[str], project_id: UUID):
        """Traite et indexe documents comptables"""
        from app.services.document_processor import DocumentProcessor
        processor = DocumentProcessor()
        chunker = SmartChunker(chunk_size=800, overlap=100)
        
        for doc_path in doc_paths:
            file_path = Path(doc_path)
            existing = self.db.query(Document).filter(
                Document.project_id == project_id,
                Document.filename == file_path.name
            ).first()
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
                project_id=project_id,
                filename=file_path.name,
                file_path=str(file_path),
                file_type=file_path.suffix.lstrip('.'),
                file_size=file_path.stat().st_size,
                status='processing',
                metadata={"entities": entities}
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
    
    async def _extract_accounting_entities(self, text: str) -> Dict:
        """Extraction entités comptables (NER)"""
        if not self.nlp:
            return {"amounts": [], "accounts": [], "dates": [], "organismes": []}
        
        doc = self.nlp(text)
        entities = {
            "amounts": [{"text": e.text, "label": e.label_} for e in doc.ents if e.label_ == "MONTANT"],
            "accounts": [{"text": e.text, "label": e.label_} for e in doc.ents if e.label_ == "COMPTE_PCG"],
            "dates": [{"text": e.text, "label": e.label_} for e in doc.ents if e.label_ in ["DATE_CLOTURE", "EXERCICE"]],
            "organismes": [{"text": e.text, "label": e.label_} for e in doc.ents if e.label_ == "ORGANISME"]
        }
        return entities
    
    async def _detect_anomalies(self, entities: Dict, context: Dict) -> List[Dict]:
        """Détection anomalies comptables basiques"""
        anomalies = []
        
        # Exemple: Vérifier équilibre si débit/crédit présents
        # (logique simplifiée, en prod il faudrait parser les écritures)
        
        # Anomalie: Pas de compte PCG détecté
        if not entities.get("accounts"):
            anomalies.append({
                "type": "missing_account",
                "severity": "majeur",
                "message": "Aucun compte PCG détecté dans l'écriture"
            })
        
        return anomalies
    
    async def _stream_llm_response(self, prompt: str, title: str = "Agent Comptable") -> AsyncGenerator[str, None]:
        """Helper pour streaming LLM avec création conversation"""
        # Créer conversation
        conv = Conversation(
            user_id=self.user_id,
            title=title,
            provider_name=self.config.get("llm_provider", "ollama"),
            model=self.config.get("llm_model", "mistral"),
            temperature=self.config.get("llm_temperature", 0.3)
        )
        self.db.add(conv)
        self.db.flush()
        
        # Ajouter message utilisateur
        self.db.add(MessageModel(conversation_id=conv.id, role="user", content=prompt))
        self.db.commit()
        
        # Streamer réponse LLM
        async for chunk in self.llm_service.stream_chat(
            self.user_id, conv.id, "",
            self.config.get("llm_provider", "ollama"),
            self.config.get("llm_model", "mistral"),
            self.config.get("llm_temperature", 0.3)
        ):
            if chunk:
                yield chunk