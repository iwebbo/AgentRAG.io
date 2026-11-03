"""Limites de contexte par modèle."""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

MODEL_CONTEXT_LIMITS = {
    # OpenAI
    "gpt-4-turbo": 128000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4": 8192,
    "gpt-3.5-turbo": 16385,

    # Claude
    "claude-3-5-sonnet": 200000,
    "claude-3-opus": 200000,
    "claude-3-haiku": 200000,

    # Google
    "gemini-1.5-pro": 2000000,  # 2M tokens!
    "gemini-1.5-flash": 1000000,

    # Ollama - Llama 3.1 (Meta)
    "llama3.1:8b": 128000,
    "llama3.1:70b": 128000,
    "llama3.1:405b": 128000,
    "llama3.1": 128000,  # Alias

    # Ollama - Llama 3.2 (Meta)
    "llama3.2:1b": 131072,
    "llama3.2:3b": 131072,
    "llama3.2:90b": 131072,

    # Ollama - Mistral
    "mistral:7b": 32768,
    "mistral:latest": 32768,
    "mistral-small": 32768,
    "mistral-large": 128000,
    "codestral:22b": 32000,
    "mixtral:latest": 32000,
    "mixtral:8x7b": 32000,
    "mistrallite:latest": 32000,

    # Ollama - Qwen 2.5 (Alibaba)
    "qwen2.5:7b": 32768,
    "qwen2.5:14b": 32768,
    "qwen2.5:32b": 32768,
    "qwen2.5:72b": 131072,
    "qwen3-coder:30b": 256000,

    # Ollama - Gemma 2 (Google)
    "gemma2:2b": 8192,
    "gemma2:9b": 8192,
    "gemma2:27b": 8192,
    "gemma3:4b": 128000,
    "gemma3:27b": 128000,
    "gemma3:27b-it-qat": 128000,
    "gemma4:e4b": 128000,
    "gemma4:26b": 128000,
    "gemma4:e2b": 128000,

    # Ollama - Phi-3.5 (Microsoft)
    "phi3:14b": 128000,
    "phi3:latest": 128000,
    "phi4:14b": 16000,
    "phi4:latest": 16000,
    "phi4-reasoning:14b": 32000,

    # Ollama - DeepSeek
    "deepseek-coder:6.7b": 16384,
    "deepseek-coder:33b": 16384,
    "deepseek-r1:32b": 128000,
    "deepseek-r1:14b": 128000,

    # Ollama - Code Llama
    "codellama:7b": 16384,
    "codellama:13b": 16384,
    "codellama:34b": 128000,

    # Ollama - Gpt-oss
    "gpt-oss:20b": 128000,

    # LMStudio - gpt-oss
    "openai/gpt-oss-20b": 128000,

    # LMStudio - Gemma
    "google/gemma-4-e4b": 128000,
    "google/gemma-4-e2b": 128000,

    # LMStudio - Mistral
    "mistralai/ministral-3-3b": 128000,
    "mistralai/ministral-3-14b-reasoning": 128000,
    "mistralai/codestral-22b-v0.1": 128000,

    # LMStudio - Llama
    "meta-llama-3.1-8b-instruct": 128000,
    "llama-3.2-3b-instruct": 128000,

    # LMStudio - Qwen
    "qwen/qwen3.5-9b": 128000,
    "qwen3.5-4b-claude-4.6-opus-reasoning-distilled": 128000,

    # Fallback
    "default": 8192,
}


def get_model_limit(model: str) -> int:
    """Limite de contexte : override env > match exact > plus long match > défaut.

    LLM_CONTEXT_LIMIT_OVERRIDE doit refléter le `n_ctx` réellement chargé dans
    LM Studio / Ollama (souvent inférieur au maximum théorique du modèle).
    """
    override = os.getenv("LLM_CONTEXT_LIMIT_OVERRIDE")
    if override:
        try:
            return int(override)
        except ValueError:
            logger.warning("LLM_CONTEXT_LIMIT_OVERRIDE invalide: %r", override)

    m = (model or "").lower()
    if m in MODEL_CONTEXT_LIMITS:
        return MODEL_CONTEXT_LIMITS[m]
    matches = [k for k in MODEL_CONTEXT_LIMITS if k != "default" and k in m]
    if matches:
        return MODEL_CONTEXT_LIMITS[max(matches, key=len)]
    return MODEL_CONTEXT_LIMITS["default"]