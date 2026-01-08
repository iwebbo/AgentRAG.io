"""
Configuration Centralisée Agent Juridique
==========================================

Toutes les configurations métier :
- Checklists de conformité (RGPD, contrats, CGV)
- Patterns NER juridiques enrichis
- Poids des risques par catégorie
- Types de réclamations
- Sources juridiques
"""

# ═══════════════════════════════════════════════════════════════
# PATTERNS NER JURIDIQUES ENRICHIS
# ═══════════════════════════════════════════════════════════════

NER_PATTERNS = [
    # Références légales
    {"label": "LEGAL_REF", "pattern": [{"TEXT": {"REGEX": r"(CGI|BOI|Code|Article|Loi|Décret|Directive)\s+\w*\d+"}}]},
    {"label": "LEGAL_REF", "pattern": [{"LOWER": "article"}, {"TEXT": {"REGEX": r"\d+"}}]},
    {"label": "LEGAL_REF", "pattern": [{"LOWER": "code"}, {"LOWER": {"IN": ["civil", "pénal", "travail", "commerce"]}}]},
    
    # Juridictions
    {"label": "COURT", "pattern": [{"TEXT": {"REGEX": r"(Cour de cassation|Conseil d'État|CA|TJ|CE|Cass\.|Tribunal)"}}]},
    {"label": "COURT", "pattern": [{"LOWER": "cour"}, {"LOWER": "d'appel"}]},
    {"label": "COURT", "pattern": [{"LOWER": "tribunal"}, {"LOWER": {"IN": ["judiciaire", "administratif", "commerce"]}}]},
    
    # Décisions
    {"label": "DECISION", "pattern": [{"TEXT": {"REGEX": r"(Arrêt|Jugement|Décision)\s+n?°?\s*\d+"}}]},
    {"label": "DECISION", "pattern": [{"LOWER": "arrêt"}, {"LOWER": "du"}, {"TEXT": {"REGEX": r"\d{2}/\d{2}/\d{4}"}}]},
    
    # Délais et dates limites
    {"label": "DEADLINE", "pattern": [{"TEXT": {"REGEX": r"\d{1,2}/(0?[1-9]|1[0-2])/\d{4}"}}]},
    {"label": "DEADLINE", "pattern": [{"LOWER": {"IN": ["avant", "jusqu'au", "délai"]}}, {"LOWER": "le"}, {"TEXT": {"REGEX": r"\d+"}}]},
    {"label": "DEADLINE", "pattern": [{"TEXT": {"REGEX": r"\d+"}} , {"LOWER": "jours"}]},
    
    # Pénalités et amendes
    {"label": "PENALTY", "pattern": [{"LOWER": {"IN": ["amende", "pénalité", "sanction"]}}, {"TEXT": {"REGEX": r"\d+\s*(€|euros?|%)"}}]},
    {"label": "PENALTY", "pattern": [{"TEXT": {"REGEX": r"(amende|pénalité)"}}, {"LOWER": "de"}, {"TEXT": {"REGEX": r"\d+"}}]},
    
    # Montants
    {"label": "AMOUNT", "pattern": [{"TEXT": {"REGEX": r"\d+[\s\.]?\d*\s*(€|euros?|k€|M€)"}}]},
    {"label": "AMOUNT", "pattern": [{"TEXT": {"REGEX": r"\d+"}}, {"LOWER": {"IN": ["euros", "euro", "€"]}}]},
    
    # Autorités
    {"label": "AUTHORITY", "pattern": [{"TEXT": {"IN": ["URSSAF", "CNIL", "DGFIP", "DIRECCTE", "Trésor Public", "Douanes"]}}]},
    {"label": "AUTHORITY", "pattern": [{"LOWER": "direction"}, {"LOWER": "générale"}]},
    {"label": "AUTHORITY", "pattern": [{"LOWER": "administration"}, {"LOWER": "fiscale"}]},
    
    # Procédures
    {"label": "PROCEDURE", "pattern": [{"TEXT": {"REGEX": r"(recours|appel|pourvoi|médiation|transaction|arbitrage)"}}]},
    {"label": "PROCEDURE", "pattern": [{"LOWER": "recours"}, {"LOWER": {"IN": ["gracieux", "contentieux", "hiérarchique"]}}]},
]

# ═══════════════════════════════════════════════════════════════
# TYPES DE RÉCLAMATIONS
# ═══════════════════════════════════════════════════════════════

CLAIM_TYPES = {
    "recours": ["recours", "appel", "contestation formelle", "pourvoi"],
    "contestation": ["conteste", "contestation", "désaccord", "opposition"],
    "mise_en_demeure": ["mise en demeure", "sommation", "injonction", "demande formelle"],
    "demande_info": ["demande", "information", "précision", "clarification"],
    "plainte": ["plainte", "dénonciation", "signalement"]
}

# ═══════════════════════════════════════════════════════════════
# TYPES DE DOCUMENTS
# ═══════════════════════════════════════════════════════════════

DOCUMENT_TYPES = {
    "contract": "Contrat commercial",
    "cgv": "Conditions Générales de Vente",
    "cgu": "Conditions Générales d'Utilisation",
    "rgpd_notice": "Notice RGPD",
    "policy": "Politique de confidentialité",
    "acte": "Acte juridique",
    "courrier": "Courrier officiel",
    "note_juridique": "Note juridique",
    "generic": "Document générique"
}

# ═══════════════════════════════════════════════════════════════
# CHECKLISTS DE CONFORMITÉ
# ═══════════════════════════════════════════════════════════════

COMPLIANCE_CHECKLISTS = {
    "rgpd_notice": {
        "name": "Notice RGPD",
        "regulation": "RGPD - Règlement (UE) 2016/679",
        "required_items": [
            {
                "name": "Identité du responsable de traitement",
                "keywords": ["responsable du traitement", "responsable de traitement"],
                "severity": "bloquant",
                "legal_basis": "RGPD Article 13.1.a",
                "description": "Nom et coordonnées du responsable du traitement"
            },
            {
                "name": "Coordonnées du DPO",
                "keywords": ["délégué à la protection", "dpo", "dpd"],
                "severity": "majeur",
                "legal_basis": "RGPD Article 13.1.b",
                "description": "Coordonnées du délégué à la protection des données"
            },
            {
                "name": "Finalités du traitement",
                "keywords": ["finalités", "finalité du traitement"],
                "severity": "bloquant",
                "legal_basis": "RGPD Article 13.1.c",
                "description": "Finalités du traitement et base juridique"
            },
            {
                "name": "Destinataires des données",
                "keywords": ["destinataires", "destinataire des données"],
                "severity": "majeur",
                "legal_basis": "RGPD Article 13.1.e",
                "description": "Destinataires ou catégories de destinataires"
            },
            {
                "name": "Durée de conservation",
                "keywords": ["durée de conservation", "conservation des données"],
                "severity": "bloquant",
                "legal_basis": "RGPD Article 13.2.a",
                "description": "Durée de conservation ou critères de détermination"
            },
            {
                "name": "Droit d'accès",
                "keywords": ["droit d'accès"],
                "severity": "majeur",
                "legal_basis": "RGPD Article 15",
                "description": "Information sur le droit d'accès aux données"
            },
            {
                "name": "Droit de rectification",
                "keywords": ["droit de rectification"],
                "severity": "majeur",
                "legal_basis": "RGPD Article 16"
            },
            {
                "name": "Droit à l'effacement",
                "keywords": ["droit à l'effacement", "droit à l'oubli"],
                "severity": "majeur",
                "legal_basis": "RGPD Article 17"
            },
            {
                "name": "Droit d'opposition",
                "keywords": ["droit d'opposition"],
                "severity": "majeur",
                "legal_basis": "RGPD Article 21"
            },
            {
                "name": "Droit de réclamation CNIL",
                "keywords": ["réclamation auprès de la cnil", "introduire une réclamation"],
                "severity": "mineur",
                "legal_basis": "RGPD Article 77"
            }
        ]
    },
    
    "contract": {
        "name": "Contrat commercial",
        "regulation": "Code civil + Code de commerce",
        "required_items": [
            {
                "name": "Identification des parties",
                "keywords": ["parties", "entre les soussignés"],
                "severity": "bloquant",
                "legal_basis": "Code civil Article 1108"
            },
            {
                "name": "Objet du contrat",
                "keywords": ["objet", "a pour objet"],
                "severity": "bloquant",
                "legal_basis": "Code civil Article 1108"
            },
            {
                "name": "Prix et modalités de paiement",
                "keywords": ["prix", "paiement", "modalités de paiement"],
                "severity": "bloquant",
                "legal_basis": "Code civil Article 1591"
            },
            {
                "name": "Durée du contrat",
                "keywords": ["durée", "période"],
                "severity": "majeur",
                "legal_basis": "Code civil Article 1210"
            },
            {
                "name": "Conditions de résiliation",
                "keywords": ["résiliation", "résolution"],
                "severity": "majeur",
                "legal_basis": "Code civil Article 1184"
            },
            {
                "name": "Clause de responsabilité",
                "keywords": ["responsabilité", "responsable"],
                "severity": "majeur",
                "legal_basis": "Code civil Article 1231"
            },
            {
                "name": "Juridiction compétente",
                "keywords": ["juridiction", "tribunal compétent", "compétence"],
                "severity": "mineur",
                "legal_basis": "Code de procédure civile"
            },
            {
                "name": "Loi applicable",
                "keywords": ["loi applicable", "droit applicable"],
                "severity": "mineur"
            }
        ]
    },
    
    "cgv": {
        "name": "Conditions Générales de Vente",
        "regulation": "Code de commerce + Code de la consommation",
        "required_items": [
            {
                "name": "Mentions légales vendeur",
                "keywords": ["raison sociale", "siret", "siren"],
                "severity": "bloquant",
                "legal_basis": "Code de commerce L441-1"
            },
            {
                "name": "Prix TTC",
                "keywords": ["prix ttc", "toutes taxes comprises"],
                "severity": "bloquant",
                "legal_basis": "Code de la consommation L111-1"
            },
            {
                "name": "Frais de livraison",
                "keywords": ["frais de livraison", "frais de port"],
                "severity": "majeur",
                "legal_basis": "Code de la consommation L111-1"
            },
            {
                "name": "Délai de livraison",
                "keywords": ["délai de livraison", "délai d'expédition"],
                "severity": "majeur",
                "legal_basis": "Code de la consommation L216-1"
            },
            {
                "name": "Droit de rétractation",
                "keywords": ["droit de rétractation", "14 jours"],
                "severity": "bloquant",
                "legal_basis": "Code de la consommation L221-18"
            },
            {
                "name": "Garantie légale de conformité",
                "keywords": ["garantie légale de conformité", "garantie de conformité"],
                "severity": "bloquant",
                "legal_basis": "Code de la consommation L217-4"
            },
            {
                "name": "Garantie des vices cachés",
                "keywords": ["garantie des vices cachés", "vices cachés"],
                "severity": "majeur",
                "legal_basis": "Code civil Article 1641"
            },
            {
                "name": "Médiation consommateur",
                "keywords": ["médiateur", "médiation de la consommation"],
                "severity": "majeur",
                "legal_basis": "Code de la consommation L612-1"
            }
        ]
    },
    
    "policy": {
        "name": "Politique de confidentialité",
        "regulation": "RGPD + Loi Informatique et Libertés",
        "required_items": [
            {
                "name": "Types de données collectées",
                "keywords": ["données collectées", "données personnelles collectées"],
                "severity": "bloquant",
                "legal_basis": "RGPD Article 13"
            },
            {
                "name": "Finalités de la collecte",
                "keywords": ["finalités", "finalité de la collecte"],
                "severity": "bloquant",
                "legal_basis": "RGPD Article 13"
            },
            {
                "name": "Durée de conservation",
                "keywords": ["durée de conservation", "conservation des données"],
                "severity": "bloquant",
                "legal_basis": "RGPD Article 13"
            },
            {
                "name": "Droits des personnes",
                "keywords": ["vos droits", "droits d'accès"],
                "severity": "bloquant",
                "legal_basis": "RGPD Articles 15-22"
            },
            {
                "name": "Cookies",
                "keywords": ["cookies", "traceurs"],
                "severity": "majeur",
                "legal_basis": "Directive ePrivacy"
            },
            {
                "name": "Sécurité des données",
                "keywords": ["sécurité", "sécurité des données"],
                "severity": "majeur",
                "legal_basis": "RGPD Article 32"
            }
        ]
    },
    
    "generic": {
        "name": "Document générique",
        "regulation": "Principes généraux",
        "required_items": [
            {
                "name": "Date du document",
                "keywords": ["date", "fait le"],
                "severity": "mineur"
            },
            {
                "name": "Signatures",
                "keywords": ["signature", "signé"],
                "severity": "mineur"
            }
        ]
    }
}

# ═══════════════════════════════════════════════════════════════
# POIDS DES RISQUES PAR CATÉGORIE
# ═══════════════════════════════════════════════════════════════

RISK_WEIGHTS = {
    "contentieux": 1.0,      # Impact direct sur litiges
    "fiscal": 0.9,           # Pénalités lourdes
    "rgpd": 0.8,             # Amendes importantes (4% CA)
    "social": 0.85,          # Risques URSSAF/Prud'hommes
    "commercial": 0.7,       # Impact business
    "reputationnel": 0.6,    # Moins quantifiable
    "environnemental": 0.75, # Obligations croissantes
    "penal": 1.0            # Risque pénal
}

# ═══════════════════════════════════════════════════════════════
# SOURCES JURIDIQUES
# ═══════════════════════════════════════════════════════════════

LEGAL_SOURCES = {
    "legifrance": {
        "url": "https://api.legifrance.gouv.fr",
        "enabled": False,  # Requiert API key
        "description": "Base officielle textes législatifs et réglementaires"
    },
    "bofip": {
        "url": "https://bofip.impots.gouv.fr",
        "enabled": False,
        "description": "Bulletin Officiel des Finances Publiques - Impôts"
    },
    "doctrine": {
        "url": "https://www.doctrine.fr",
        "enabled": False,
        "description": "Jurisprudence administrative et judiciaire"
    },
    "cnil": {
        "url": "https://www.cnil.fr",
        "enabled": True,  # Scraping possible
        "description": "Délibérations et guides CNIL"
    }
}

# ═══════════════════════════════════════════════════════════════
# NIVEAUX DE GRAVITÉ
# ═══════════════════════════════════════════════════════════════

SEVERITY_LEVELS = {
    "bloquant": {
        "priority": 1,
        "description": "Empêche l'utilisation du document",
        "action_required": "Correction immédiate obligatoire",
        "icon": "🔴"
    },
    "majeur": {
        "priority": 2,
        "description": "Risque juridique significatif",
        "action_required": "Correction recommandée sous 7 jours",
        "icon": "🟡"
    },
    "mineur": {
        "priority": 3,
        "description": "Amélioration recommandée",
        "action_required": "À traiter selon disponibilité",
        "icon": "🟢"
    }
}

# ═══════════════════════════════════════════════════════════════
# DOMAINES JURIDIQUES
# ═══════════════════════════════════════════════════════════════

LEGAL_DOMAINS = {
    "fiscal": {
        "name": "Droit fiscal",
        "keywords": ["impôt", "taxe", "cgi", "fisc", "redressement", "bofip"],
        "authorities": ["DGFIP", "Trésor Public", "SIP"],
        "typical_deadlines": {"recours": "2 mois", "contentieux": "2 mois"}
    },
    "social": {
        "name": "Droit social",
        "keywords": ["urssaf", "cotisation", "sécurité sociale", "pôle emploi", "retraite"],
        "authorities": ["URSSAF", "CPAM", "Pôle Emploi", "Inspection du travail"],
        "typical_deadlines": {"recours": "2 mois", "prud'hommes": "12 mois"}
    },
    "commercial": {
        "name": "Droit commercial",
        "keywords": ["contrat", "client", "fournisseur", "cgv", "commande"],
        "authorities": ["DGCCRF"],
        "typical_deadlines": {"mise_en_demeure": "8 jours", "action": "5 ans"}
    },
    "contentieux": {
        "name": "Contentieux",
        "keywords": ["tribunal", "justice", "procès", "avocat", "assignation"],
        "authorities": ["Tribunal", "Cour d'appel", "Cour de cassation"],
        "typical_deadlines": {"appel": "1 mois", "cassation": "2 mois"}
    },
    "rgpd": {
        "name": "Protection des données",
        "keywords": ["rgpd", "données personnelles", "cnil", "consentement"],
        "authorities": ["CNIL"],
        "typical_deadlines": {"recours": "2 mois", "mise_en_conformité": "Variable"}
    }
}

# ═══════════════════════════════════════════════════════════════
# DÉLAIS LÉGAUX TYPES
# ═══════════════════════════════════════════════════════════════

LEGAL_DEADLINES = {
    "recours_gracieux": "2 mois",
    "recours_contentieux": "2 mois",
    "appel": "1 mois",
    "cassation": "2 mois",
    "retractation_consommateur": "14 jours",
    "paiement_facture": "30 jours",
    "mise_en_demeure": "8 jours minimum",
    "prescription_commerciale": "5 ans",
    "prescription_civile": "5 ans",
    "prescription_fiscale": "3 ans"
}

# ═══════════════════════════════════════════════════════════════
# MONTANTS PÉNALITÉS TYPES
# ═══════════════════════════════════════════════════════════════

PENALTY_RANGES = {
    "rgpd_max": "20000000 ou 4% CA mondial",  # RGPD Article 83
    "travail_dissimule": "45000€ + 3 ans prison",  # Code du travail L8224-1
    "discrimination": "45000€ + 3 ans prison",  # Code pénal 225-2
    "retard_paiement": "Intérêts + 40€ forfait",  # LME
    "clause_abusive": "Nullité clause"  # Code consommation L132-1
}