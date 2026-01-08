"""
Configuration Expert-Comptable - Référentiels métier
=====================================================

Constantes et référentiels pour l'agent comptable.
"""

# ═══════════════════════════════════════════════════════════════
# RÉFÉRENTIELS COMPTABLES
# ═══════════════════════════════════════════════════════════════

PCG_ACCOUNTS = {
    "1": {"name": "Comptes de capitaux", "examples": ["101 Capital", "106 Réserves", "108 Compte exploitant"]},
    "2": {"name": "Comptes d'immobilisations", "examples": ["205 Logiciels", "211 Terrains", "215 Matériel"]},
    "3": {"name": "Comptes de stocks", "examples": ["31 Matières premières", "37 Marchandises"]},
    "4": {"name": "Comptes de tiers", "examples": ["401 Fournisseurs", "411 Clients", "421 Personnel"]},
    "5": {"name": "Comptes financiers", "examples": ["512 Banque", "531 Caisse"]},
    "6": {"name": "Comptes de charges", "examples": ["601 Achats", "641 Salaires", "645 Charges sociales"]},
    "7": {"name": "Comptes de produits", "examples": ["701 Ventes", "706 Prestations", "775 Produits exceptionnels"]}
}

# ═══════════════════════════════════════════════════════════════
# RÉGIMES FISCAUX
# ═══════════════════════════════════════════════════════════════

FISCAL_REGIMES = {
    "micro_entreprise": {
        "name": "Micro-entreprise (auto-entrepreneur)",
        "ca_limits": {"vente": 188700, "service": 77700},
        "abattement": {"vente": 0.71, "service": 0.50, "bnc": 0.34},
        "obligations": "Livre recettes, factures"
    },
    "reel_simplifie": {
        "name": "Réel simplifié",
        "ca_limits": {"min": 0, "max": 818000},
        "obligations": "Bilan, compte résultat, annexe simplifiée, liasse 2033"
    },
    "reel_normal": {
        "name": "Réel normal",
        "ca_limits": {"min": 818000, "max": None},
        "obligations": "Comptabilité complète, liasse 2050, bilan, annexe détaillée"
    },
    "is": {
        "name": "Impôt sur les sociétés",
        "taux": {"normal": 0.25, "reduit_38k": 0.15},
        "obligations": "Liasse 2065, bilan, annexe, relevé de solde IS"
    }
}

# ═══════════════════════════════════════════════════════════════
# IMPÔTS ET TAXES
# ═══════════════════════════════════════════════════════════════

TAX_TYPES = {
    "tva": {
        "name": "TVA",
        "taux": {"normal": 0.20, "intermediaire": 0.10, "reduit": 0.055, "particulier": 0.021},
        "regimes": ["franchise", "reel_simplifie", "reel_normal", "mini_reel"],
        "declarations": "CA3 (mensuelle/trimestrielle), CA12 (annuelle)"
    },
    "is": {
        "name": "Impôt sur les sociétés",
        "taux_2025": 0.25,
        "taux_reduit": 0.15,  # Jusqu'à 42500€
        "acomptes": "15/03, 15/06, 15/09, 15/12",
        "liquidation": "Avant fin 3ème mois N+1"
    },
    "ir": {
        "name": "Impôt sur le revenu",
        "baremes_2025": [
            {"min": 0, "max": 11294, "taux": 0.00},
            {"min": 11295, "max": 28797, "taux": 0.11},
            {"min": 28798, "max": 82341, "taux": 0.30},
            {"min": 82342, "max": 177106, "taux": 0.41},
            {"min": 177107, "max": None, "taux": 0.45}
        ]
    },
    "cvae": {
        "name": "Cotisation sur la valeur ajoutée des entreprises",
        "seuil": 500000,
        "taux_max": 0.0075
    },
    "cet": {
        "name": "Contribution économique territoriale (CFE + CVAE)",
        "cfe_base": "Valeur locative foncière"
    }
}

# ═══════════════════════════════════════════════════════════════
# CHARGES SOCIALES 2025
# ═══════════════════════════════════════════════════════════════

SOCIAL_CHARGES = {
    "urssaf": {
        "name": "URSSAF (Sécurité sociale)",
        "taux_salarie": 0.2225,  # Part salarié (maladie, vieillesse, CSG/CRDS)
        "taux_patronal": 0.42,   # Part patronale
        "plafond_ss_2025": 3864  # Mensuel
    },
    "retraite_complementaire": {
        "name": "AGIRC-ARRCO",
        "taux_total": 0.1540,  # 7.87% + 6.73% répartis
        "taux_salarie": 0.0387,
        "taux_patronal": 0.1153
    },
    "chomage": {
        "name": "Assurance chômage",
        "taux_patronal": 0.0405,
        "taux_salarie": 0.0
    },
    "prevoyance": {
        "name": "Prévoyance/mutuelle",
        "obligatoire": True,
        "taux_moyen": 0.015  # Variable selon accord
    },
    "formation": {
        "name": "Formation professionnelle",
        "taux": 0.0055  # <11 salariés, sinon 1%
    }
}

# ═══════════════════════════════════════════════════════════════
# CRÉDITS D'IMPÔT
# ═══════════════════════════════════════════════════════════════

TAX_CREDITS = {
    "cir": {
        "name": "Crédit Impôt Recherche",
        "taux": {"<100M": 0.30, ">100M": 0.05},
        "plafond": 100000000,
        "justificatifs": ["Dépenses R&D", "Personnel affecté", "Amortissements"]
    },
    "cii": {
        "name": "Crédit Impôt Innovation",
        "taux": 0.20,
        "plafond": 400000,
        "conditions": "PME, dépenses innovation produits nouveaux"
    },
    "jei": {
        "name": "Jeune Entreprise Innovante",
        "exonerations": {"is": 1.0, "charges_sociales": 0.50},
        "duree": "8 ans max",
        "conditions": "Création <8 ans, R&D >15% charges"
    },
    "apprentissage": {
        "name": "Crédit apprentissage",
        "montant": 1600,  # Par apprenti niveau <Bac
        "conditions": "Contrat 1 mois minimum"
    }
}

# ═══════════════════════════════════════════════════════════════
# NER PATTERNS COMPTABLES
# ═══════════════════════════════════════════════════════════════

NER_PATTERNS = [
    # Comptes PCG
    {"label": "COMPTE_PCG", "pattern": [{"TEXT": {"REGEX": r"^[1-7]\d{1,5}$"}}]},
    
    # Montants financiers
    {"label": "MONTANT", "pattern": [{"TEXT": {"REGEX": r"^\d{1,3}(?:\s?\d{3})*(?:[,.]\d{2})?$"}}, {"LOWER": {"IN": ["€", "eur", "euros"]}}]},
    {"label": "MONTANT", "pattern": [{"TEXT": {"REGEX": r"^\d+[,.]\d{2}$"}}, {"TEXT": "€"}]},
    
    # Dates comptables
    {"label": "EXERCICE", "pattern": [{"LOWER": "exercice"}, {"TEXT": {"REGEX": r"^\d{4}$"}}]},
    {"label": "DATE_CLOTURE", "pattern": [{"LOWER": {"IN": ["au", "clôture"]}}, {"TEXT": {"REGEX": r"^\d{1,2}/\d{1,2}/\d{4}$"}}]},
    
    # Références fiscales
    {"label": "TVA", "pattern": [{"LOWER": "tva"}, {"TEXT": {"REGEX": r"^\d{1,2}[.,]?\d*%?$"}}]},
    {"label": "IS", "pattern": [{"LOWER": {"IN": ["is", "impôt", "sociétés"]}}]},
    {"label": "IR", "pattern": [{"LOWER": {"IN": ["ir", "impôt", "revenu"]}}]},
    
    # Organismes
    {"label": "ORGANISME", "pattern": [{"LOWER": {"IN": ["urssaf", "rsi", "msa", "dgfip", "tresor", "impots"]}}]},
    
    # Documents comptables
    {"label": "DOC_COMPTABLE", "pattern": [{"LOWER": {"IN": ["bilan", "compte", "résultat", "liasse", "annexe", "balance", "grand", "livre"]}}]}
]

# ═══════════════════════════════════════════════════════════════
# ANOMALIES COMPTABLES
# ═══════════════════════════════════════════════════════════════

ANOMALY_CHECKS = {
    "balance_desequilibre": {
        "description": "Balance débit ≠ crédit",
        "severity": "bloquant",
        "check": "sum(debit) - sum(credit) > 1€"
    },
    "tva_incoherente": {
        "description": "TVA collectée < TVA déductible sans justification",
        "severity": "majeur",
        "check": "tva_collectee < tva_deductible * 0.5"
    },
    "compte_solde_anormal": {
        "description": "Compte avec solde inversé (ex: 411 créditeur)",
        "severity": "majeur",
        "check": "validate_account_sign()"
    },
    "ecriture_non_equilibree": {
        "description": "Écriture avec débit ≠ crédit",
        "severity": "bloquant",
        "check": "entry_debit != entry_credit"
    },
    "doublon_facture": {
        "description": "Numéro facture déjà utilisé",
        "severity": "majeur",
        "check": "duplicate_invoice_number()"
    },
    "plafond_ss_depasse": {
        "description": "Cotisations > plafond SS sans justification",
        "severity": "mineur",
        "check": "salary > PLAFOND_SS * 1.1"
    }
}

# ═══════════════════════════════════════════════════════════════
# OBLIGATIONS LÉGALES PAR DATE
# ═══════════════════════════════════════════════════════════════

LEGAL_DEADLINES = {
    "mensuel": [
        {"date": "15", "obligation": "Déclaration TVA CA3 (régime normal)", "type": "tva"},
        {"date": "25", "obligation": "DSN (Déclaration Sociale Nominative)", "type": "social"}
    ],
    "trimestriel": [
        {"date": "15/01", "obligation": "Acompte IS 4ème trimestre", "type": "fiscal"},
        {"date": "15/04", "obligation": "Acompte IS 1er trimestre", "type": "fiscal"},
        {"date": "15/06", "obligation": "Acompte IS 2ème trimestre", "type": "fiscal"},
        {"date": "15/09", "obligation": "Acompte IS 3ème trimestre", "type": "fiscal"},
        {"date": "30/04", "obligation": "Déclaration TVA CA12 (si trimestriel)", "type": "tva"}
    ],
    "annuel": [
        {"date": "30/04", "obligation": "Liasse fiscale 2065 (IS)", "type": "fiscal"},
        {"date": "30/05", "obligation": "Déclaration IR 2042 (BIC/BNC)", "type": "fiscal"},
        {"date": "15/05", "obligation": "Liquidation IS N-1", "type": "fiscal"},
        {"date": "31/12", "obligation": "Inventaire annuel", "type": "comptable"}
    ]
}

# ═══════════════════════════════════════════════════════════════
# RATIOS FINANCIERS CLÉS
# ═══════════════════════════════════════════════════════════════

FINANCIAL_RATIOS = {
    "liquidite_generale": {
        "formula": "actif_circulant / passif_circulant",
        "optimal": "> 1.5",
        "interpretation": "Capacité à payer dettes court terme"
    },
    "solvabilite": {
        "formula": "capitaux_propres / total_passif",
        "optimal": "> 0.33",
        "interpretation": "Autonomie financière"
    },
    "rentabilite_nette": {
        "formula": "resultat_net / ca",
        "optimal": "> 0.05",
        "interpretation": "Marge nette"
    },
    "rotation_stocks": {
        "formula": "ca / stock_moyen",
        "optimal": "> 4",
        "interpretation": "Vitesse écoulement stocks"
    },
    "delai_paiement_clients": {
        "formula": "(clients / ca_ttc) * 365",
        "optimal": "< 60 jours",
        "interpretation": "DSO - Days Sales Outstanding"
    }
}

# ═══════════════════════════════════════════════════════════════
# SOURCES DE VEILLE RÉGLEMENTAIRE
# ═══════════════════════════════════════════════════════════════

ACCOUNTING_SOURCES = {
    "bofip": {
        "url": "https://bofip.impots.gouv.fr",
        "description": "Doctrine fiscale officielle",
        "enabled": True
    },
    "anc": {
        "url": "https://www.anc.gouv.fr",
        "description": "Autorité des Normes Comptables",
        "enabled": True
    },
    "ordre_experts_comptables": {
        "url": "https://www.experts-comptables.fr",
        "description": "Ordre des experts-comptables",
        "enabled": True
    },
    "legifrance": {
        "url": "https://www.legifrance.gouv.fr",
        "description": "Codes (commerce, fiscal, travail)",
        "enabled": False  # Nécessite API key
    }
}