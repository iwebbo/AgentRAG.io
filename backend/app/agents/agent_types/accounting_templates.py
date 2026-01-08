"""
Templates et Prompts pour Agent Expert-Comptable
=================================================

Prompts système et templates de documents comptables.
"""

# ═══════════════════════════════════════════════════════════════
# PROMPTS SYSTÈME PAR MODE
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPTS = {
    "accounting_entry": """Tu es un expert-comptable certifié spécialisé dans la saisie et vérification des écritures comptables.

Tes missions :
- Analyser et valider les pièces justificatives (factures, relevés bancaires, notes de frais)
- Proposer les imputations comptables conformes au PCG (Plan Comptable Général 2025)
- Détecter les anomalies (écritures non équilibrées, comptes anormaux, doublons)
- Assurer la cohérence TVA (taux, déductibilité, régime)
- Générer les écritures au format standard (journal, date, compte, libellé, débit, crédit)

Méthodologie :
1. Identifier la nature de l'opération (achat, vente, salaire, investissement)
2. Déterminer les comptes PCG concernés (classe 1 à 7)
3. Calculer la TVA si applicable
4. Vérifier l'équilibre Débit = Crédit
5. Proposer l'écriture avec justification

Référentiel : PCG 2025, Code Général des Impôts, Doctrine fiscale BOFIP.
""",

    "annual_statements": """Tu es un expert-comptable certifié spécialisé dans l'établissement des comptes annuels.

Tes missions :
- Préparer le bilan comptable (actif/passif)
- Établir le compte de résultat (charges/produits)
- Rédiger l'annexe comptable (méthodes, événements significatifs)
- Calculer les ratios financiers (liquidité, solvabilité, rentabilité)
- Valider la conformité avec les normes comptables françaises
- Générer la liasse fiscale (2065 IS ou 2031 BIC/BNC)

Méthodologie :
1. Vérifier la balance comptable (équilibre débit/crédit)
2. Opérations de clôture (amortissements, provisions, stocks)
3. Construction des états financiers
4. Analyse de cohérence et ratios
5. Préparation déclarations fiscales

Référentiel : PCG 2025, Règlement ANC, Code de commerce.
""",

    "tax_optimization": """Tu es un expert-comptable fiscaliste spécialisé dans l'optimisation fiscale légale.

Tes missions :
- Calculer les impôts (IS, IR, TVA, CET, CVAE)
- Identifier les crédits d'impôt applicables (CIR, CII, apprentissage)
- Optimiser le régime fiscal (micro, réel simplifié, réel normal, IS vs IR)
- Simuler les impacts fiscaux de décisions stratégiques
- Préparer et télédéclarer les déclarations fiscales
- Conseiller sur la gestion des déficits et amortissements

Méthodologie :
1. Analyser la situation fiscale actuelle
2. Identifier les leviers d'optimisation légaux
3. Simuler les économies potentielles
4. Proposer un plan d'action chiffré
5. Documenter les justifications légales

Référentiel : CGI 2025, BOFIP, Loi de Finances 2025.
""",

    "social_payroll": """Tu es un expert-comptable spécialisé en gestion sociale et paie.

Tes missions :
- Établir les bulletins de paie conformes
- Calculer les charges sociales (URSSAF, retraite, chômage)
- Générer la DSN (Déclaration Sociale Nominative)
- Vérifier la conformité aux conventions collectives
- Simuler des scénarios d'embauche/licenciement
- Conseiller sur les dispositifs d'aide (ACRE, aides à l'embauche)

Méthodologie :
1. Collecter les éléments variables (heures, primes, absences)
2. Appliquer les taux de cotisations 2025
3. Calculer le net à payer
4. Vérifier les plafonds (Sécurité Sociale, déductibilité)
5. Générer les fichiers DSN

Référentiel : Code du travail, Barèmes URSSAF 2025, Conventions collectives.
""",

    "audit_review": """Tu es un expert-comptable auditeur certifié.

Tes missions :
- Réviser les comptes et procédures internes
- Détecter les irrégularités et risques de fraude
- Évaluer les contrôles internes
- Réaliser des audits d'acquisition (due diligence)
- Évaluer les entreprises (DCF, multiples, actif net)
- Rédiger des rapports d'audit avec recommandations

Méthodologie :
1. Planification de la mission (risques, périmètre)
2. Tests de cohérence et vérifications analytiques
3. Contrôle par sondage des opérations
4. Identification des anomalies significatives
5. Rapport d'audit structuré

Référentiel : NEP (Normes d'Exercice Professionnel), Code de déontologie OEC.
""",

    "strategic_advice": """Tu es un expert-comptable conseil en stratégie d'entreprise.

Tes missions :
- Analyser la situation financière et budgétaire
- Élaborer des business plans et prévisionnels
- Conseiller sur les financements (prêts, subventions, levées de fonds)
- Accompagner les créations d'entreprise (choix statut, formalités)
- Gérer les situations de crise (restructurations, plans de sauvegarde)
- Conseiller sur les opérations juridiques (AG, modifications statutaires)

Méthodologie :
1. Diagnostic financier approfondi
2. Analyse SWOT et opportunités
3. Modélisation financière (scénarios, Monte Carlo)
4. Recommandations stratégiques priorisées
5. Plan d'action opérationnel

Référentiel : Code de commerce, Droit des sociétés, Finance d'entreprise.
""",

    "compliance_check": """Tu es un expert-comptable spécialisé en conformité réglementaire.

Tes missions :
- Vérifier la conformité des obligations comptables et fiscales
- Auditer les risques de non-conformité (contrôle fiscal, URSSAF)
- Assurer la mise à jour des obligations réglementaires
- Former les équipes aux bonnes pratiques
- Mettre en place une veille juridique et fiscale
- Préparer les contrôles (documentation, justificatifs)

Méthodologie :
1. Checklist de conformité exhaustive
2. Revue documentaire (pièces justificatives, déclarations)
3. Identification des écarts et risques
4. Plan de mise en conformité
5. Surveillance continue

Référentiel : PCG, CGI, Code du travail, Code de commerce, Doctrine BOFIP.
"""
}

# ═══════════════════════════════════════════════════════════════
# TEMPLATES DE DOCUMENTS
# ═══════════════════════════════════════════════════════════════

DOCUMENT_TEMPLATES = {
    "ecriture_comptable": """
ÉCRITURE COMPTABLE
==================
Date : {date}
Journal : {journal}
Pièce n° : {piece_num}

Libellé : {libelle}

┌─────────────────────────────────────────────────────────────┐
│ Compte │ Libellé compte         │ Débit     │ Crédit    │
├─────────────────────────────────────────────────────────────┤
{lignes_ecriture}
├─────────────────────────────────────────────────────────────┤
│        │ TOTAL                  │ {total_d} │ {total_c} │
└─────────────────────────────────────────────────────────────┘

Équilibre : {equilibre}
Justificatif : {justificatif}
""",

    "note_analyse_fiscale": """
NOTE D'ANALYSE FISCALE
======================
Date : {date}
Destinataire : {destinataire}
Objet : {objet}

1. CONTEXTE
-----------
{contexte}

2. QUESTION FISCALE POSÉE
--------------------------
{question}

3. ANALYSE JURIDIQUE ET FISCALE
--------------------------------
{analyse}

3.1. Textes applicables
{textes}

3.2. Doctrine administrative (BOFIP)
{doctrine}

3.3. Jurisprudence pertinente
{jurisprudence}

4. IMPACTS FINANCIERS
----------------------
{impacts}

Scénario actuel :
{scenario_actuel}

Scénario optimisé :
{scenario_optimise}

Économie potentielle : {economie}€

5. RISQUES IDENTIFIÉS
----------------------
{risques}

6. RECOMMANDATIONS
------------------
{recommandations}

7. CONCLUSION
-------------
{conclusion}

---
Expert-Comptable : {expert_name}
Cabinet : {cabinet}
Date : {date}
""",

    "bilan_comptable": """
BILAN AU {date_cloture}
Exercice du {date_debut} au {date_cloture}

ACTIF
=====
┌───────────────────────────────────────────────────────────┐
│ IMMOBILISATIONS                        │ Brut  │ Net      │
├───────────────────────────────────────────────────────────┤
│ Immobilisations incorporelles          │       │          │
│ Immobilisations corporelles            │       │          │
│ Immobilisations financières            │       │          │
├───────────────────────────────────────────────────────────┤
│ TOTAL ACTIF IMMOBILISÉ                │       │ {actif_i}│
└───────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────┐
│ ACTIF CIRCULANT                        │       │          │
├───────────────────────────────────────────────────────────┤
│ Stocks et en-cours                     │       │          │
│ Créances clients                       │       │          │
│ Autres créances                        │       │          │
│ Trésorerie                             │       │          │
├───────────────────────────────────────────────────────────┤
│ TOTAL ACTIF CIRCULANT                 │       │ {actif_c}│
└───────────────────────────────────────────────────────────┘

TOTAL ACTIF : {total_actif}€

PASSIF
======
┌───────────────────────────────────────────────────────────┐
│ CAPITAUX PROPRES                                          │
├───────────────────────────────────────────────────────────┤
│ Capital social                                   {capital}│
│ Réserves                                        {reserves}│
│ Résultat de l'exercice                         {resultat}│
├───────────────────────────────────────────────────────────┤
│ TOTAL CAPITAUX PROPRES                   {capitaux_propres}│
└───────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────┐
│ DETTES                                                    │
├───────────────────────────────────────────────────────────┤
│ Emprunts et dettes financières                    {dettes}│
│ Fournisseurs                              {fournisseurs}│
│ Dettes fiscales et sociales            {dettes_fiscales}│
│ Autres dettes                                 {autres_d}│
├───────────────────────────────────────────────────────────┤
│ TOTAL DETTES                               {total_dettes}│
└───────────────────────────────────────────────────────────┘

TOTAL PASSIF : {total_passif}€
""",

    "compte_resultat": """
COMPTE DE RÉSULTAT
Exercice clos le {date_cloture}

PRODUITS D'EXPLOITATION
========================
Ventes de marchandises                           {ventes_march}
Production vendue (services)                     {prod_services}
Subventions d'exploitation                        {subventions}
Autres produits                                    {autres_p}
                                            ─────────────────
TOTAL PRODUITS EXPLOITATION                   {total_produits}

CHARGES D'EXPLOITATION
======================
Achats de marchandises                              {achats}
Autres achats et charges externes                 {externes}
Impôts et taxes                                     {impots}
Salaires et traitements                           {salaires}
Charges sociales                                   {charges}
Dotations aux amortissements                          {amor}
Autres charges                                   {autres_c}
                                            ─────────────────
TOTAL CHARGES EXPLOITATION                    {total_charges}

RÉSULTAT D'EXPLOITATION                        {resultat_exp}

RÉSULTAT FINANCIER                                {res_finan}
RÉSULTAT EXCEPTIONNEL                              {res_excep}
Impôt sur les bénéfices                               {is}
                                            ─────────────────
RÉSULTAT NET                                    {resultat_net}
"""
}

# ═══════════════════════════════════════════════════════════════
# HELPERS POUR TEMPLATES
# ═══════════════════════════════════════════════════════════════

def get_system_prompt(mode: str) -> str:
    """Récupère le prompt système pour un mode donné"""
    return SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["accounting_entry"])


def render_ecriture_template(data: dict) -> str:
    """Génère une écriture comptable formatée"""
    lignes = []
    total_debit = 0
    total_credit = 0
    
    for ligne in data.get("lignes", []):
        compte = ligne["compte"]
        libelle = ligne["libelle"]
        debit = ligne.get("debit", 0)
        credit = ligne.get("credit", 0)
        total_debit += debit
        total_credit += credit
        
        lignes.append(
            f"│ {compte:6} │ {libelle:22} │ {debit:9.2f} │ {credit:9.2f} │"
        )
    
    equilibre = "✅ ÉQUILIBRÉE" if abs(total_debit - total_credit) < 0.01 else "❌ NON ÉQUILIBRÉE"
    
    return DOCUMENT_TEMPLATES["ecriture_comptable"].format(
        date=data["date"],
        journal=data["journal"],
        piece_num=data["piece_num"],
        libelle=data["libelle"],
        lignes_ecriture="\n".join(lignes),
        total_d=f"{total_debit:9.2f}",
        total_c=f"{total_credit:9.2f}",
        equilibre=equilibre,
        justificatif=data.get("justificatif", "")
    )


def render_note_fiscale_template(data: dict) -> str:
    """Génère une note d'analyse fiscale"""
    return DOCUMENT_TEMPLATES["note_analyse_fiscale"].format(**data)