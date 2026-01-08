"""
Configuration agent de voyage - Profils et paramètres
"""
from typing import Dict, List, Any


class TravelConfig:
    """Configuration de l'agent voyage"""
    
    # Profils de voyageurs prédéfinis
    TRAVELER_PROFILES = {
        "backpacker": {
            "budget_range": "low",
            "accommodation": ["hostel", "guesthouse", "camping"],
            "transport": ["bus", "train", "hitchhiking"],
            "pace": "flexible",
            "interests": ["culture", "nature", "local_experience"]
        },
        "luxury": {
            "budget_range": "high",
            "accommodation": ["5star_hotel", "resort", "villa"],
            "transport": ["first_class", "private", "business_flight"],
            "pace": "relaxed",
            "interests": ["gastronomy", "spa", "exclusive_experiences"]
        },
        "family": {
            "budget_range": "medium",
            "accommodation": ["family_hotel", "apartment", "resort"],
            "transport": ["comfortable", "direct_routes"],
            "pace": "moderate",
            "interests": ["kid_friendly", "educational", "safe_activities"]
        },
        "adventure": {
            "budget_range": "medium",
            "accommodation": ["lodge", "camping", "eco_resort"],
            "transport": ["4x4", "boat", "trekking"],
            "pace": "active",
            "interests": ["hiking", "diving", "extreme_sports", "wildlife"]
        },
        "cultural": {
            "budget_range": "medium",
            "accommodation": ["boutique_hotel", "guesthouse", "heritage_hotel"],
            "transport": ["public", "walking", "bicycle"],
            "pace": "moderate",
            "interests": ["museums", "historical_sites", "local_culture", "art"]
        },
        "digital_nomad": {
            "budget_range": "medium",
            "accommodation": ["coworking_hotel", "apartment", "coliving"],
            "transport": ["flexible", "long_term_rental"],
            "pace": "slow_travel",
            "interests": ["wifi", "coworking", "expat_community", "work_life_balance"]
        }
    }
    
    # Types d'activités par catégorie
    ACTIVITY_CATEGORIES = {
        "nature": ["hiking", "wildlife_safari", "beach", "mountains", "national_parks"],
        "culture": ["museums", "temples", "historical_sites", "local_markets", "festivals"],
        "adventure": ["diving", "climbing", "rafting", "skydiving", "surfing"],
        "gastronomy": ["cooking_class", "food_tours", "wine_tasting", "street_food", "restaurants"],
        "wellness": ["spa", "yoga", "meditation", "hot_springs", "retreats"],
        "urban": ["shopping", "nightlife", "architecture", "street_art", "city_tours"]
    }
    
    # Postes budgétaires standards
    BUDGET_CATEGORIES = {
        "transport": {
            "flight": "40-50%",
            "local_transport": "10-15%",
            "description": "Vols internationaux, transferts, transports locaux"
        },
        "accommodation": {
            "percentage": "25-35%",
            "description": "Hôtels, auberges, locations"
        },
        "food": {
            "percentage": "15-25%",
            "description": "Restaurants, marchés, snacks"
        },
        "activities": {
            "percentage": "10-20%",
            "description": "Visites, excursions, entrées"
        },
        "miscellaneous": {
            "percentage": "5-10%",
            "description": "Souvenirs, imprévus, pourboires"
        }
    }
    
    # Documents requis par type de voyage
    REQUIRED_DOCUMENTS = {
        "international": [
            "passport (valid 6+ months)",
            "visa (if required)",
            "travel insurance",
            "vaccination certificate",
            "flight tickets",
            "hotel confirmations"
        ],
        "domestic": [
            "ID card",
            "transport tickets",
            "accommodation confirmations"
        ],
        "adventure": [
            "medical certificate",
            "emergency contact",
            "equipment list",
            "local guide contact"
        ]
    }
    
    # Checklist pré-départ
    DEPARTURE_CHECKLIST = {
        "1_month_before": [
            "Vérifier passeport/visa",
            "Souscrire assurance voyage",
            "Réserver vols et hébergements principaux",
            "Vérifier vaccins nécessaires"
        ],
        "2_weeks_before": [
            "Confirmer toutes réservations",
            "Préparer itinéraire détaillé",
            "Informer banque du voyage",
            "Télécharger applications utiles"
        ],
        "1_week_before": [
            "Faire copies documents importants",
            "Préparer trousse médical",
            "Vérifier météo destination",
            "Préparer valise"
        ],
        "48h_before": [
            "Check-in en ligne",
            "Vérifier restrictions bagages",
            "Charger tous appareils",
            "Prévoir devises locales"
        ]
    }
    
    # Templates de prompts spécialisés
    PROMPT_TEMPLATES = {
        "destination_comparison": """Compare les destinations suivantes pour un voyage de {duration}:
{destinations}

Critères de comparaison:
- Budget: {budget}
- Intérêts: {interests}
- Saison: {season}

Fournis un tableau comparatif avec:
1. Coût estimé total
2. Météo à la période
3. Activités principales
4. Points forts/faibles
5. Recommandation finale

Sois factuel et précis dans les estimations.""",

        "emergency_planning": """Crée un plan d'urgence pour un voyage à {destination}:

Inclus:
1. Numéros d'urgence locaux (police, ambulance, pompiers)
2. Ambassade/Consulat coordonnées
3. Hôpitaux recommandés
4. Zones à éviter
5. Procédure perte passeport
6. Contacts assistance rapatriement

Sois complet et rassurant.""",

        "packing_list": """Génère une liste de bagages optimale pour:
- Destination: {destination}
- Durée: {duration}
- Saison: {season}
- Type de voyage: {travel_type}
- Activités prévues: {activities}

Organise par catégories:
1. Documents essentiels
2. Vêtements (selon météo)
3. Électronique
4. Trousse toilette
5. Médicaments
6. Matériel spécifique activités
7. Accessoires pratiques

Limite au strict nécessaire, indique poids approximatif.""",

        "local_customs": """Explique les coutumes et étiquette locale pour {destination}:

Couvre:
1. Salutations et politesse
2. Dress code approprié
3. Comportement dans lieux publics/religieux
4. Pourboires (montants et situations)
5. Gestes à éviter
6. Négociation marchés
7. Horaires repas et habitudes
8. Expressions utiles en langue locale

Aide le voyageur à s'intégrer respectueusement.""",

        "food_guide": """Crée un guide gastronomique pour {destination}:

Inclus:
1. Plats typiques incontournables (5-7)
2. Où les trouver (types de lieux)
3. Prix moyens
4. Allergies/restrictions courantes
5. Street food safe vs à éviter
6. Restaurants recommandés (3 budgets)
7. Expériences culinaires uniques
8. Règles de table locales

Rends le guide appétissant et pratique."""
    }
    
    @staticmethod
    def get_profile(profile_name: str) -> Dict[str, Any]:
        """Récupère un profil voyageur"""
        return TravelConfig.TRAVELER_PROFILES.get(
            profile_name,
            TravelConfig.TRAVELER_PROFILES["cultural"]  # Default
        )
    
    @staticmethod
    def get_activities_by_interest(interests: List[str]) -> List[str]:
        """Récupère activités selon intérêts"""
        activities = []
        for interest in interests:
            if interest in TravelConfig.ACTIVITY_CATEGORIES:
                activities.extend(TravelConfig.ACTIVITY_CATEGORIES[interest])
        return list(set(activities))  # Déduplique
    
    @staticmethod
    def estimate_daily_budget(
        destination_tier: str,
        travel_style: str
    ) -> Dict[str, str]:
        """Estimation budget quotidien"""
        
        # Tiers de coût par destination
        cost_tiers = {
            "low": {"backpacker": "20-30€", "budget": "40-60€", "comfort": "80-100€", "luxury": "150-200€"},
            "medium": {"backpacker": "30-50€", "budget": "60-80€", "comfort": "100-150€", "luxury": "200-300€"},
            "high": {"backpacker": "50-70€", "budget": "80-120€", "comfort": "150-250€", "luxury": "300-500€"}
        }
        
        tier = cost_tiers.get(destination_tier, cost_tiers["medium"])
        return {
            "daily_budget": tier.get(travel_style, tier["budget"]),
            "tier": destination_tier,
            "style": travel_style
        }


# Configuration par défaut agents
DEFAULT_TRAVEL_CONFIG = {
    "specialties": ["destination", "itinerary", "budget", "activities"],
    "auto_budget_calculation": True,
    "suggest_alternatives": True,
    "weather_aware": True,
    "cultural_insights": True,
    "max_destinations": 5,
    "max_activities_per_day": 4,
    "default_profile": "cultural",
    "supported_languages": ["fr", "en", "es", "de", "it"],
    "currency": "EUR"
}