from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database import get_db
from app.models import User, Provider
from app.schemas.provider import (
    ProviderCreate,
    ProviderUpdate,
    ProviderResponse,
    ProviderTestResponse
)
from app.dependencies import get_current_user
from app.utils.security import encrypt_api_key, decrypt_api_key
from app.services.provider_factory import ProviderFactory
from app.services.llm_service import LLMService

router = APIRouter(prefix="/api/providers", tags=["Providers"])


@router.get("/", response_model=List[ProviderResponse])
async def list_providers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all configured providers for current user"""
    
    providers = db.query(Provider).filter(
        Provider.user_id == current_user.id
    ).order_by(
        Provider.priority.desc(),
        Provider.created_at.desc()
    ).all()
    
    return providers


@router.post("/", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(
    provider_data: ProviderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add new provider configuration"""
    
    # Check if provider already exists
    existing = db.query(Provider).filter(
        Provider.user_id == current_user.id,
        Provider.name == provider_data.name
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider {provider_data.name} already configured"
        )
    
    # Encrypt API key if provided
    encrypted_key = None
    if provider_data.api_key:
        encrypted_key = encrypt_api_key(provider_data.api_key)
    
    provider = Provider(
        user_id=current_user.id,
        name=provider_data.name,
        api_key=encrypted_key,
        base_url=provider_data.base_url,
        is_active=provider_data.is_active,
        priority=provider_data.priority,
        config=provider_data.config
    )
    
    db.add(provider)
    db.commit()
    db.refresh(provider)
    
    return provider


@router.put("/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: UUID,
    provider_update: ProviderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update provider configuration"""
    
    provider = db.query(Provider).filter(
        Provider.id == provider_id,
        Provider.user_id == current_user.id
    ).first()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )
    
    # Update fields
    update_data = provider_update.model_dump(exclude_unset=True)
    
    # Encrypt new API key if provided
    if "api_key" in update_data and update_data["api_key"]:
        update_data["api_key"] = encrypt_api_key(update_data["api_key"])
    
    for field, value in update_data.items():
        setattr(provider, field, value)
    
    db.commit()
    db.refresh(provider)
    
    return provider


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete provider configuration"""
    
    provider = db.query(Provider).filter(
        Provider.id == provider_id,
        Provider.user_id == current_user.id
    ).first()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )
    
    db.delete(provider)
    db.commit()
    
    return None


@router.post("/{provider_id}/test", response_model=ProviderTestResponse)
async def test_provider(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test provider connection"""
    
    provider = db.query(Provider).filter(
        Provider.id == provider_id,
        Provider.user_id == current_user.id
    ).first()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )
    
    try:
        # Decrypt API key
        api_key = None
        if provider.api_key:
            api_key = decrypt_api_key(provider.api_key)
        
        # Create provider instance
        llm_provider = ProviderFactory.create_provider(
            provider.name,
            api_key=api_key,
            base_url=provider.base_url,
            config=provider.config
        )
        
        # Test connection
        success, message, latency = await llm_provider.test_connection()
        
        return ProviderTestResponse(
            success=success,
            message=message,
            latency_ms=latency
        )
        
    except Exception as e:
        return ProviderTestResponse(
            success=False,
            message=f"Test failed: {str(e)}",
            latency_ms=None
        )


@router.get("/available", response_model=dict)
async def get_available_providers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of available providers and their models"""
    
    llm_service = LLMService(db)
    
    return {
            "openai": {
                "name": "OpenAI",
                "requires_api_key": True,
                "models": await llm_service.get_available_models("openai")
            },
            "claude": {
                "name": "Anthropic Claude",
                "requires_api_key": True,
                "models": await llm_service.get_available_models("claude")
            },
            "gemini": {
                "name": "Google Gemini",
                "requires_api_key": True,
                "models": await llm_service.get_available_models("gemini")
            },
            "openrouter": {
                "name": "OpenRouter",
                "requires_api_key": True,
                "models": await llm_service.get_available_models("openrouter")
            },
            "groq": {
                "name": "Groq",
                "requires_api_key": True,
                "models": await llm_service.get_available_models("groq")
            },
            "grok": {
                "name": "xAI Grok",
                "requires_api_key": True,
                "models": await llm_service.get_available_models("grok")
            },
            "ollama": {
                "name": "Ollama (Local)",
                "requires_api_key": False,
                "models": await llm_service.get_available_models("ollama")
            },
            "lmstudio": {
                "name": "LM Studio",
                "requires_api_key": False,
                "models": await llm_service.get_available_models("lmstudio")
            },
            "localai": {
                "name": "LocalAI",
                "requires_api_key": False,
                "models": await llm_service.get_available_models("localai")
            },
            "oobabooga": {
                "name": "Oobabooga WebUI",
                "requires_api_key": False,
                "models": await llm_service.get_available_models("oobabooga")
            },
            "vllm": {
                "name": "vLLM",
                "requires_api_key": False,
                "models": await llm_service.get_available_models("vllm")
            },
            "lmdeploy": {
                "name": "LMDeploy",
                "requires_api_key": False,
                "models": await llm_service.get_available_models("lmdeploy")
            },
        }


@router.get("/{provider_name}/models", response_model=dict)
async def get_provider_models(
    provider_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get available models for a specific provider"""
    
    # Optionnel: Vérifie si configuré (sinon fallback)
    provider = db.query(Provider).filter(
        Provider.name == provider_name.lower(),
        Provider.user_id == current_user.id
    ).first()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_name} not configured"
        )
    
    llm_service = LLMService(db)
    models = await llm_service.get_available_models(provider_name.lower())
    
    return {
        "provider": provider_name,
        "models": models
    }