"""
Templates et Prompts Centralisés Agent Juridique
=================================================

Tous les templates de documents et prompts LLM :
- Templates Jinja2 (réponses, actes, notes)
- Prompts LLM spécialisés par mode
- Fonctions helper pour rendu
"""

from typing import Dict, Any, Optional
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# TEMPLATES JINJA2
# ═══════════════════════════════════════════════════════════════

TEMPLATES = {
    "reponse_recours": {
        "id": "reponse_recours",
        "name": "Réponse à un recours",
        "type": "courrier",
        "content": """
{{recipient}}
{{address}}

Objet : Réponse à votre recours du {{date_recours}}
Référence : {{reference}}

{{date}}

{{recipient}},

Nous accusons réception de votre recours en date du {{date_recours}} concernant {{subject}}.

Après analyse approfondie de votre demande et examen des pièces justificatives, nous vous apportons les éléments de réponse suivants :

{{content}}

Les textes applicables sont les suivants :
{% for ref in legal_refs %}
- {{ref}}
{% endfor %}

En conséquence, {{conclusion}}.

Nous vous rappelons que conformément aux dispositions légales, vous disposez d'un délai de {{deadline}} pour exercer un recours contentieux devant le tribunal compétent.

Nous restons à votre disposition pour tout complément d'information.

Veuillez agréer, {{recipient}}, l'expression de nos salutations distinguées.

{{signature}}
"""
    },
    
    "reponse_contestation": {
        "id": "reponse_contestation",
        "name": "Réponse à une contestation",
        "type": "courrier",
        "content": """
{{date}}

{{recipient}}
{{address}}

Objet : {{subject}}
Référence : {{reference}}

{{recipient}},

Suite à votre courrier en date du {{date_contestation}}, nous avons pris connaissance de votre contestation portant sur {{objet_contestation}}.

{{content}}

Références légales applicables :
{% for ref in legal_refs %}
- {{ref}}
{% endfor %}

{{conclusion}}

Cordialement,

{{signature}}
"""
    },
    
    "note_juridique": {
        "id": "note_juridique",
        "name": "Note juridique interne",
        "type": "note",
        "content": """
NOTE JURIDIQUE

Date : {{date}}
Objet : {{subject}}
Destinataire : {{recipient}}
Rédacteur : {{author}}

CONTEXTE
--------
{{context}}

QUESTION JURIDIQUE
------------------
{{question}}

ANALYSE
-------
{{content}}

TEXTES APPLICABLES
------------------
{% for ref in legal_refs %}
{{ref}}
{% endfor %}

RECOMMANDATIONS
---------------
{{recommendations}}

RISQUES IDENTIFIÉS
------------------
{{risks}}

CONCLUSION
----------
{{conclusion}}
"""
    },
    
    "acte_administratif": {
        "id": "acte_administratif",
        "name": "Acte administratif",
        "type": "acte",
        "content": """
ACTE ADMINISTRATIF

Numéro : {{numero}}
Date : {{date}}

TITRE : {{title}}

Vu {{legal_basis}},

{{content}}

Article 1 : {{article_1}}

Article 2 : {{article_2}}

Article 3 : Le présent acte sera notifié à {{destinataires}}.

Fait à {{lieu}}, le {{date}}

{{signature}}
{{fonction}}
"""
    },
    
    "courrier_mise_en_demeure": {
        "id": "courrier_mise_en_demeure",
        "name": "Mise en demeure",
        "type": "courrier",
        "content": """
LETTRE RECOMMANDÉE AVEC ACCUSÉ DE RÉCEPTION

{{expediteur}}
{{adresse_expediteur}}

{{destinataire}}
{{adresse_destinataire}}

{{date}}

Objet : Mise en demeure
Référence : {{reference}}

{{destinataire}},

Par la présente, nous vous mettons formellement en demeure de {{objet_demeure}}.

RAPPEL DES FAITS :
{{faits}}

FONDEMENT JURIDIQUE :
{% for ref in legal_refs %}
- {{ref}}
{% endfor %}

En conséquence, nous vous demandons de {{demande}} dans un délai de {{delai}} jours à compter de la réception de la présente.

Passé ce délai, et en l'absence de régularisation, nous nous verrons dans l'obligation d'engager {{action_contentieuse}}, à vos frais et risques.

Veuillez agréer, {{destinataire}}, nos salutations distinguées.

{{signature}}
"""
    }
}

# ═══════════════════════════════════════════════════════════════
# PROMPTS LLM SPÉCIALISÉS
# ═══════════════════════════════════════════════════════════════

PROMPTS = {
    "analysis": """Tu es un expert juridique français spécialisé en {domain}.

Analyse les documents fournis en contexte et réponds à la question de manière précise et structurée.

Instructions :
- Base ton analyse uniquement sur le contexte fourni
- Cite les articles et références légales pertinents
- Identifie les points clés et les risques
- Formule une recommandation claire
- Reste factuel et objectif
- Utilise un langage juridique précis mais accessible

Format de réponse attendu :
1. Synthèse (2-3 phrases)
2. Analyse détaillée
3. Références légales
4. Recommandations
5. Points de vigilance""",

    "claim_response": """Tu es un conseiller juridique chargé de rédiger une réponse à une réclamation.

RÉCLAMATION :
{claim_text}

TYPE : {claim_type}
DOMAINE : {domain}
URGENCE : {urgency}

CONTEXTE JURIDIQUE :
{legal_context}

JURISPRUDENCE PERTINENTE :
{cases_context}

NIVEAU DE RISQUE : {risk_level}

Ta mission :
1. Analyser la réclamation avec objectivité
2. Identifier les arguments juridiques solides
3. Proposer une réponse argumentée et diplomate
4. Citer les textes applicables
5. Suggérer une stratégie (acceptation partielle, rejet motivé, proposition transaction)

Rédige une réponse professionnelle, équilibrée et juridiquement solide.

FORMAT :
- Introduction (accusé réception)
- Analyse des arguments
- Réponse juridique motivée
- Références légales
- Conclusion et suite à donner""",

    "risk_evaluation": """Tu es un expert en évaluation des risques juridiques.

Analyse la situation suivante et évalue les risques :

SITUATION :
{situation}

DOMAINE : {domain}
ÉLÉMENTS DÉTECTÉS : {elements}

Ta mission :
1. Identifier tous les risques juridiques
2. Évaluer la probabilité et l'impact de chaque risque
3. Proposer des mesures préventives et correctives
4. Estimer les impacts financiers potentiels

Sois précis et factuel. Cite les textes applicables.""",

    "document_review": """Tu es un juriste chargé de réviser un document.

DOCUMENT TYPE : {doc_type}
RÉGLEMENTATION : {regulation}

Ta mission :
1. Identifier les clauses manquantes ou problématiques
2. Vérifier la conformité réglementaire
3. Détecter les clauses abusives ou déséquilibrées
4. Proposer des améliorations concrètes

Sois exhaustif et méthodique.""",

    "generic_draft": """Tu es un juriste chargé de rédiger un document juridique.

TYPE DE DOCUMENT : {document_type}
DESTINATAIRE : {recipient}
OBJET : {subject}

CONTENU À INTÉGRER :
{content}

RÉFÉRENCES LÉGALES PERTINENTES :
{legal_refs}

Ta mission :
1. Rédiger un document professionnel et structuré
2. Utiliser un langage juridique précis
3. Intégrer les références légales de manière appropriée
4. Respecter les formules de politesse et les usages
5. Assurer la clarté et la complétude du document

Le document doit être prêt à être envoyé.""",

    "compliance_analysis": """Tu es un auditeur juridique spécialisé en conformité.

DOCUMENT À AUDITER : {document_type}
RÉGLEMENTATION : {regulation}

CHECKLIST À VÉRIFIER :
{checklist}

Ta mission :
1. Vérifier point par point la conformité
2. Identifier les manquements
3. Évaluer la gravité de chaque manquement
4. Proposer des corrections précises

Sois rigoureux et exhaustif.""",

    "jurisprudence_analysis": """Tu es un expert en analyse jurisprudentielle.

QUESTION JURIDIQUE :
{question}

CAS SIMILAIRES IDENTIFIÉS :
{similar_cases}

Ta mission :
1. Analyser la tendance jurisprudentielle
2. Identifier les arguments récurrents
3. Évaluer les chances de succès
4. Recommander une stratégie contentieuse

Base ton analyse uniquement sur la jurisprudence fournie.""",

    "legal_research": """Tu es un chercheur juridique.

REQUÊTE :
{query}

DOCUMENTS TROUVÉS :
{documents}

Ta mission :
1. Synthétiser les informations pertinentes
2. Citer les sources avec précision
3. Identifier les textes applicables
4. Proposer des pistes d'approfondissement

Reste factuel et précis."""
}

# ═══════════════════════════════════════════════════════════════
# FONCTIONS HELPER
# ═══════════════════════════════════════════════════════════════

def get_template(template_type: str, template_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Récupère un template par type ou ID
    
    Args:
        template_type: Type de document (reponse_recours, note_juridique, etc.)
        template_id: ID spécifique du template (optionnel)
    
    Returns:
        Dict contenant le template ou None
    """
    if template_id and template_id in TEMPLATES:
        return TEMPLATES[template_id]
    
    # Map type -> template ID
    type_mapping = {
        "reponse_reclamation": "reponse_recours",
        "note_juridique": "note_juridique",
        "acte": "acte_administratif",
        "courrier": "courrier_mise_en_demeure",
        "mise_en_demeure": "courrier_mise_en_demeure"
    }
    
    template_id = type_mapping.get(template_type, template_type)
    return TEMPLATES.get(template_id)


def render_template(template: Dict[str, Any], data: Dict[str, Any]) -> str:
    """
    Rend un template avec les données fournies
    
    Args:
        template: Template dict avec 'content'
        data: Données à injecter dans le template
    
    Returns:
        Texte rendu
    """
    content = template.get("content", "")
    
    # Simple string formatting (en production, utiliser Jinja2)
    # Pour simplifier, on fait un remplacement basique
    try:
        # Replace simple variables
        for key, value in data.items():
            if isinstance(value, str):
                content = content.replace("{{" + key + "}}", value)
            elif isinstance(value, list):
                # Handle lists (for legal_refs, etc.)
                list_content = "\n".join([f"- {item}" for item in value])
                content = content.replace("{% for ref in " + key + " %}\n- {{ref}}\n{% endfor %}", list_content)
        
        # Clean up remaining template tags
        import re
        content = re.sub(r'\{\{[^}]+\}\}', '[À COMPLÉTER]', content)
        content = re.sub(r'\{%[^%]+%\}', '', content)
        
        return content.strip()
    except Exception as e:
        return f"Erreur de rendu du template: {str(e)}\n\n{content}"


def get_prompt(prompt_type: str, **kwargs) -> str:
    """
    Récupère et formate un prompt LLM
    
    Args:
        prompt_type: Type de prompt (analysis, claim_response, etc.)
        **kwargs: Variables à injecter dans le prompt
    
    Returns:
        Prompt formaté
    """
    prompt_template = PROMPTS.get(prompt_type, PROMPTS.get("generic_draft", ""))
    
    try:
        return prompt_template.format(**kwargs)
    except KeyError as e:
        # Si une variable manque, on la remplace par [MANQUANT]
        import re
        formatted = prompt_template
        for key in re.findall(r'\{(\w+)\}', prompt_template):
            if key not in kwargs:
                formatted = formatted.replace("{" + key + "}", f"[{key.upper()} MANQUANT]")
            else:
                formatted = formatted.replace("{" + key + "}", str(kwargs[key]))
        return formatted


# ═══════════════════════════════════════════════════════════════
# TEMPLATES DE CLAUSES TYPES
# ═══════════════════════════════════════════════════════════════

CLAUSE_TEMPLATES = {
    "confidentialite": """
CLAUSE DE CONFIDENTIALITÉ

Les parties s'engagent à garder strictement confidentielles toutes les informations 
échangées dans le cadre du présent contrat, qu'elles soient de nature technique, 
commerciale ou financière.

Cette obligation de confidentialité s'applique pendant toute la durée du contrat 
et pendant une période de {duree} ans après sa résiliation.

Toute violation de cette clause entraînera le paiement d'une indemnité forfaitaire 
de {montant_penalite} euros, sans préjudice de tous dommages et intérêts complémentaires.
""",
    
    "resiliation": """
CLAUSE DE RÉSILIATION

Le présent contrat pourra être résilié :
1. De plein droit en cas de manquement grave de l'une des parties à ses obligations, 
   après mise en demeure restée sans effet pendant {delai_mise_en_demeure} jours
2. Par accord amiable des deux parties
3. À l'initiative de chaque partie moyennant un préavis de {delai_preavis} mois

La résiliation n'affecte pas les obligations nées antérieurement à sa date d'effet.
""",
    
    "responsabilite": """
CLAUSE DE RESPONSABILITÉ

Chaque partie est responsable des dommages directs causés à l'autre partie du fait 
de l'inexécution ou de la mauvaise exécution de ses obligations contractuelles.

La responsabilité de chaque partie est limitée au montant de {montant_plafond} euros 
par événement et par an.

Sont exclus de la responsabilité contractuelle les dommages indirects tels que les 
pertes de chiffre d'affaires, de clientèle, de données ou de bénéfices.
""",
    
    "rgpd": """
CLAUSE RGPD - TRAITEMENT DES DONNÉES PERSONNELLES

Dans le cadre de l'exécution du présent contrat, les parties peuvent être amenées 
à traiter des données à caractère personnel.

Chaque partie s'engage à :
- Traiter les données uniquement pour les finalités définies
- Respecter les principes de minimisation et de limitation de conservation
- Mettre en œuvre les mesures de sécurité appropriées
- Informer sans délai l'autre partie en cas de violation de données

Les personnes concernées disposent d'un droit d'accès, de rectification, d'effacement, 
de limitation et d'opposition conformément au RGPD (Règlement UE 2016/679).

Pour exercer ces droits : {contact_dpo}
""",
    
    "juridiction": """
CLAUSE DE COMPÉTENCE JURIDICTIONNELLE

En cas de litige relatif à l'interprétation ou à l'exécution du présent contrat, 
les parties s'efforceront de le résoudre à l'amiable.

À défaut d'accord amiable dans un délai de {delai_mediation} jours, le litige sera 
porté devant {tribunal_competent}, auquel les parties attribuent compétence exclusive.

Le présent contrat est régi par le droit français.
"""
}


# ═══════════════════════════════════════════════════════════════
# FORMULES DE POLITESSE
# ═══════════════════════════════════════════════════════════════

FORMULES_POLITESSE = {
    "introduction_formelle": "Nous avons l'honneur de vous informer que",
    "introduction_neutre": "Nous vous informons que",
    "introduction_cordiale": "Nous avons le plaisir de vous informer que",
    
    "conclusion_formelle": "Veuillez agréer, {destinataire}, l'expression de nos salutations distinguées.",
    "conclusion_neutre": "Cordialement,",
    "conclusion_cordiale": "Nous vous prions d'agréer, {destinataire}, l'expression de nos sentiments les meilleurs.",
    
    "remerciements": "Nous vous remercions de votre compréhension.",
    "disponibilite": "Nous restons à votre entière disposition pour tout complément d'information."
}


# ═══════════════════════════════════════════════════════════════
# SIGNATURES TYPES
# ═══════════════════════════════════════════════════════════════

SIGNATURE_TEMPLATES = {
    "standard": """
{nom}
{fonction}
{entreprise}
{contact}
""",
    
    "avocat": """
Maître {nom}
Avocat au Barreau de {barreau}
{cabinet}
Tél: {telephone}
Email: {email}
""",
    
    "administration": """
{nom}
{fonction}
{service}
{ministere}
"""
}