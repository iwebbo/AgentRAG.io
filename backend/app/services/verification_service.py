"""
Colle applicative de la couche de vérification (accès DB / providers / settings).

Le noyau pur vit dans `app.services.verification` ; ici on ne fait que résoudre le
backend du juge et fournir les helpers partagés par le chat et le RAG chat.
"""
from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Provider
from app.services.provider_factory import ProviderFactory
from app.services.verification import (
    VerificationPipeline,
    make_complete,
    pipeline_from_settings,
    resolve_mode,
)
from app.services.verification.judge import CompleteFn
from app.utils.security import decrypt_api_key

logger = logging.getLogger(__name__)


def resolve_verifier_backend(
    db: Session, user_id: UUID, llm_provider: Any, model: str
) -> Optional[CompleteFn]:
    """
    Fonction `complete(messages) -> str` du juge.
    VERIFIER_PROVIDER_NAME / VERIFIER_MODEL (settings) permettent un juge dédié ; à défaut le
    provider et le modèle de la requête sont réutilisés. Retourne None si rien d'exploitable.
    """
    settings = get_settings()
    judge_provider = llm_provider
    judge_model = settings.VERIFIER_MODEL or model
    name = (settings.VERIFIER_PROVIDER_NAME or "").strip()
    try:
        if name:
            row = db.query(Provider).filter(
                Provider.user_id == user_id, Provider.name == name, Provider.is_active == True  # noqa: E712
            ).first()
            if row is None:
                logger.warning("VERIFIER_PROVIDER_NAME=%r not configured for user, using request provider", name)
            else:
                api_key = decrypt_api_key(row.api_key) if row.api_key else None
                judge_provider = ProviderFactory.create_provider(
                    row.name, api_key=api_key, base_url=row.base_url, config=row.config
                )
        if judge_provider is None or not judge_model:
            return None
        return make_complete(judge_provider, judge_model)
    except Exception:
        logger.exception("Could not build the verification judge; continuing without it")
        return None


def build_request_pipeline(
    db: Session, user_id: UUID, llm_provider: Any, model: str, *, is_rag: bool
) -> VerificationPipeline:
    judge = resolve_verifier_backend(db, user_id, llm_provider, model)
    return pipeline_from_settings(get_settings(), is_rag=is_rag, judge_complete=judge)


def effective_mode(request_mode: Optional[str]) -> str:
    return resolve_mode(request_mode, get_settings())
