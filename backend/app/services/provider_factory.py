from typing import AsyncGenerator, Optional, Dict, Any, List
from abc import ABC, abstractmethod
import openai
from anthropic import AsyncAnthropic
import httpx
import asyncio
import time
from google.generativeai import GenerativeModel 
from google.generativeai.types import GenerationConfig
import google.generativeai as genai 
from huggingface_hub import AsyncInferenceClient

class BaseLLMProvider(ABC):
    """Base class for LLM providers"""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, config: Dict[str, Any] = None):
        self.api_key = api_key
        self.base_url = base_url
        self.config = config or {}
    
    @abstractmethod
    async def stream_completion(
        self,
        messages: list,
        model: str,
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream completion from provider"""
        pass
    
    @abstractmethod
    async def test_connection(self) -> tuple[bool, str, Optional[int]]:
        """Test provider connection"""
        pass
    
    async def get_available_models(self) -> list:
        """Get available models for this provider"""
        return []

class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider - officiel ou compatible (Groq, OpenRouter, etc.)"""
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",  # par défaut OpenAI officiel
        config: Optional[Dict[str, Any]] = None
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")  # sécurité
        self.config = config or {}

        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=self.base_url,
            timeout=60.0,
            max_retries=2
        )
    
    async def stream_completion(
        self,
        messages: list,
        model: str = "gpt-4-turbo-preview",
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        try:
            stream = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                stream=True,
                **kwargs
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
                    
        except openai.APIError as e:
            raise Exception(f"OpenAI API error: {e.message}")
        except Exception as e:
            raise Exception(f"Streaming error: {str(e)}")
    
    async def test_connection(self) -> tuple[bool, str, Optional[int]]:
        try:
            start_time = time.time()
            await self.client.chat.completions.create(
                model="gpt-3.5-turbo" if "openai.com" in self.base_url else model,  # fallback safe
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5
            )
            latency = int((time.time() - start_time) * 1000)
            return True, "Connection OK", latency
        except Exception as e:
            return False, f"Failed: {str(e)}", None
    
    async def get_available_models(self) -> List[str]:
        """Récupère les modèles réels si possible, sinon fallback"""
        try:
            response = await self.client.models.list()
            return [model.id for model in response.data]
        except:
            # Fallback pour OpenRouter, Groq, etc.
            return [
                "meta-llama/llama-3.3-70b-instruct",
                "google/gemini-flash-1.5",
                "qwen/qwen-2.5-72b-instruct",
                "openai/gpt-4o-mini",
                "anthropic/claude-3.5-sonnet"
            ]
        
class ClaudeProvider(BaseLLMProvider):
    """Anthropic Claude provider implementation"""
    
    def __init__(self, api_key: str, base_url: Optional[str] = None, config: Dict[str, Any] = None):
        super().__init__(api_key, base_url, config)
        self.client = AsyncAnthropic(api_key=api_key)
    
    async def stream_completion(
        self,
        messages: list,
        model: str = "claude-3-5-sonnet-20241022",
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream completion from Claude"""
        try:
            # Claude requires system message separate
            system_message = None
            filtered_messages = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                else:
                    filtered_messages.append(msg)
            
            # Build stream parameters
            stream_params = {
                "model": model,
                "messages": filtered_messages,
                "temperature": temperature,
                "max_tokens": 4096,
                "stream_mode": "values",  # Optionnel: pour un streaming plus précis
                **kwargs
            }
            
            # Add system message if present
            if system_message:
                stream_params["system"] = system_message
            
            # Stream using correct API method
            async with self.client.messages.stream(**stream_params) as stream:
                async for text_block in stream.text_stream:
                    # text_stream yields TextBlock events; extract content
                    if hasattr(text_block, 'text'):
                        yield text_block.text
                    else:
                        yield str(text_block)  # Fallback si structure changée
                        
        except Exception as e:
            import traceback
            print(f"❌ Claude streaming error: {traceback.format_exc()}")
            raise Exception(f"Claude streaming error: {str(e)}")
    
    async def test_connection(self) -> tuple[bool, str, Optional[int]]:
        """Test Claude connection"""
        try:
            start_time = time.time()
            response = await self.client.messages.create(
                model="claude-3-5-haiku-20241022",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )
            latency = int((time.time() - start_time) * 1000)
            return True, "Connection successful", latency
        except Exception as e:
            return False, f"Connection failed: {str(e)}", None
    
    async def get_available_models(self) -> list:
        """Get available Claude models"""
        # Vous pouvez rendre cela dynamique si Anthropic expose list_models()
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307"
        ]

class OllamaProvider(BaseLLMProvider):
    """Ollama local provider implementation"""
    
    def __init__(self, api_key: Optional[str] = None, base_url: str = "http://localhost:11434", config: Dict[str, Any] = None):
        super().__init__(api_key, base_url, config)
        self.base_url = base_url
    
    async def stream_completion(
        self,
        messages: list,
        model: str = "llama2",
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream completion from Ollama"""
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": True,
                        "options": {
                            "temperature": temperature
                        }
                    }
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            import json
                            data = json.loads(line)
                            if "message" in data and "content" in data["message"]:
                                yield data["message"]["content"]
                                
        except Exception as e:
            raise Exception(f"Ollama streaming error: {str(e)}")
    
    async def test_connection(self) -> tuple[bool, str, Optional[int]]:
        """Test Ollama connection"""
        try:
            start_time = time.time()
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                latency = int((time.time() - start_time) * 1000)
                return True, "Connection successful", latency
        except Exception as e:
            return False, f"Connection failed: {str(e)}", None
    
    async def get_available_models(self) -> list:
        """Get available Ollama models from the server"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = [model["name"] for model in data.get("models", [])]
                    return models if models else ["llama2"]
                else:
                    return ["llama2", "mistral", "codellama"]
        except Exception as e:
            print(f"Error fetching Ollama models: {str(e)}")
            return ["llama2", "mistral", "codellama", "neural-chat"]

class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider implementation"""
    
    def __init__(self, api_key: str, base_url: Optional[str] = None, config: Dict[str, Any] = None):
        super().__init__(api_key, base_url, config)
        genai.configure(api_key=api_key)
    
    async def stream_completion(
        self,
        messages: list,
        model: str = "gemini-1.5-pro",
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream completion from Gemini"""
        try:
            # Gemini n'a pas de support natif async streaming, on utilise asyncio pour wrapper
            def sync_generate():
                gemini_model = GenerativeModel(model)
                # Convertir messages en format Gemini (simplifié: concaténer pour chat history)
                history = []
                for msg in messages[:-1]:  # Exclure le dernier (user prompt)
                    if msg["role"] == "user":
                        history.append({"role": "user", "parts": [msg["content"]]})
                    elif msg["role"] == "assistant":
                        history.append({"role": "model", "parts": [msg["content"]]})
                
                chat = gemini_model.start_chat(history=history)
                response = chat.send_message(
                    messages[-1]["content"],
                    generation_config=GenerationConfig(temperature=temperature),
                    stream=True
                )
                for chunk in response:
                    yield chunk.text
            
            # Wrapper async
            for chunk in await asyncio.to_thread(sync_generate):
                yield chunk
                
        except Exception as e:
            raise Exception(f"Gemini streaming error: {str(e)}")
    
    async def test_connection(self) -> tuple[bool, str, Optional[int]]:
        """Test Gemini connection"""
        try:
            start_time = time.time()
            model = GenerativeModel("gemini-1.5-flash")
            await asyncio.to_thread(model.generate_content, "test")
            latency = int((time.time() - start_time) * 1000)
            return True, "Connection successful", latency
        except Exception as e:
            return False, f"Connection failed: {str(e)}", None
    
    async def get_available_models(self) -> list:
        """Get available Gemini models (statique car pas d'API list)"""
        return [
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-1.0-pro"
        ]

class LMStudioProvider(OpenAIProvider):
    """LM Studio provider - Hérite de OpenAIProvider car API compatible"""
    
    def __init__(self, api_key: Optional[str] = None, base_url: str = "http://localhost:1234/v1", config: Dict[str, Any] = None):
        super().__init__(api_key or "lm-studio", base_url, config)  # API key dummy si requis
    
    async def get_available_models(self) -> list:
        """Get available LM Studio models - Appel à /v1/models si disponible"""
        try:
            response = await self.client.models.list()
            return [model.id for model in response.data]
        except:
            return ["local-model"]  # Fallback

class LocalAIProvider(OpenAIProvider):
    """LocalAI provider - compatible OpenAI"""
    
    def __init__(self, api_key: Optional[str] = None, 
                 base_url: str = "http://localhost:8080",   # ← SANS /v1 ici
                 config: Dict[str, Any] = None):
        super().__init__(api_key or "localai", base_url, config)
    
    async def get_available_models(self) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(f"{self.base_url}/v1/models")
                resp.raise_for_status()
                json_data = resp.json()
                models = json_data.get("data", [])
                return [model["id"] for model in models if isinstance(model, dict) and "id" in model]
        except Exception as exc:
            # Utile pour débugger les premières fois
            print(f"[LocalAI] Issue to fetch models: {exc}")
            return []

class LMDeployProvider(OpenAIProvider):
    """LMDeploy provider - Hérite de OpenAIProvider (vérifiez compatibilité)"""
    
    def __init__(self, api_key: Optional[str] = None, base_url: str = "http://localhost:23333/v1", config: Dict[str, Any] = None):  # Ajustez port/base_url
        super().__init__(api_key or "lmdeploy", base_url, config)
    
    async def get_available_models(self) -> list:
        try:
            response = await self.client.models.list()
            return [model.id for model in response.data]
        except:
            return ["internlm2", "other-models"]

class OobaboogaProvider(OpenAIProvider):
    """Oobabooga (text-generation-webui) provider - OpenAI compatible"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "http://localhost:5000/v1",  # ← avec /v1
        config: Dict[str, Any] = None
    ):
        super().__init__(api_key or "sk-1234567890", base_url, config)  # clé bidon ok

    async def get_available_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/models")  # ← /v1/models
                response.raise_for_status()
                data = response.json()
                models = data.get("data", [])
                return [model["id"] for model in models if "id" in model]
        except Exception as e:
            print(f"[Oobabooga] Impossible de récupérer les modèles: {e}")
            # Modèles fallback réalistes si l'API est down ou pas encore prête
            return ["Llama-3.2-8B-Instruct-Q5_K_M.gguf", "gemma-2-9b-it-Q5_K_M.gguf"]

class VLLMProvider(OpenAIProvider):
    """vLLM provider - Hérite de OpenAIProvider"""
    
    def __init__(self, api_key: Optional[str] = None, base_url: str = "http://localhost:8000/v1", config: Dict[str, Any] = None):
        super().__init__(api_key or "vllm", base_url, config)
    
    async def get_available_models(self) -> list:
        try:
            response = await self.client.models.list()
            return [model.id for model in response.data]
        except:
            return ["meta-llama/Llama-2-7b-hf"]

class HuggingFaceProvider(BaseLLMProvider):
    """Layer d'orchestration HuggingFace — mode conversational + fallback."""

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = "https://api-inference.huggingface.co",
        config: Optional[Dict[str, Any]] = None
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.config = config or {}

        self.client = AsyncInferenceClient(
            token=api_key,
            provider="auto",
            timeout=120.0,
        )

    # ----------------------------------------------------------------------
    # INTERNAL: CHAT COMPLETION WITH FALLBACK
    # ----------------------------------------------------------------------

    async def _try_chat_completion(
        self,
        messages: list,
        model: str,
        temperature: float,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Route primaire : chat_completion (si le modèle gère le proto HF chat).
        Si mismatch ou provider incompatible → fallback text_generation.
        """

        try:
            # HF: stream=True renvoie un async generator de deltas.
            stream = await self.client.chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=kwargs.get("max_tokens", 512),
                stream=True
            )

            async for chunk in stream:
                delta = getattr(chunk.choices[0], "delta", None)
                if delta and delta.content:
                    yield delta.content

            return  # Fin normale

        except Exception:
            # Switch soft au fallback low-level
            async for token in self._fallback_text_gen(
                messages=messages,
                model=model,
                temperature=temperature,
                **kwargs
            ):
                yield token

    # ----------------------------------------------------------------------
    # FALLBACK TEXT-GENERATION
    # ----------------------------------------------------------------------

    async def _fallback_text_gen(
        self,
        messages: list,
        model: str,
        temperature: float,
        **kwargs
    ) -> AsyncGenerator[str, None]:

        prompt = self._build_prompt(messages)

        stream = self.client.text_generation(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_new_tokens=kwargs.get("max_tokens", 512),
            do_sample=temperature > 0,
            stream=True,
            **kwargs
        )

        async for chunk in stream:
            if chunk.strip():
                yield chunk

    # ----------------------------------------------------------------------
    # PROMPT BUILDER
    # ----------------------------------------------------------------------

    def _build_prompt(self, messages: list) -> str:
        """Format instruct compatible vieux modèles + TGI fallback"""
        parts = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")

            if role == "system":
                parts.append(f"[INST] <<SYS>>\n{content}\n<</SYS>>\n\n")
            elif role == "user":
                parts.append(f"[INST] {content} [/INST]")
            elif role == "assistant":
                parts.append(f"{content} </s>")

        return "".join(parts) + "[INST] "

    # ----------------------------------------------------------------------
    # PUBLIC API
    # ----------------------------------------------------------------------

    async def stream_completion(
        self,
        messages: list,
        model: str = "HuggingFaceH4/zephyr-7b-beta",
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncGenerator[str, None]:

        async for token in self._try_chat_completion(
            messages, model, temperature, **kwargs
        ):
            yield token

    # ----------------------------------------------------------------------

    async def test_connection(self) -> tuple[bool, str, Optional[int]]:
        """Ping minimaliste du pipeline conversationnel HF."""

        try:
            start = time.time()
            res = await self.client.chat_completion(
                messages=[{"role": "user", "content": "Hello"}],
                model="HuggingFaceH4/zephyr-7b-beta",
                max_tokens=5,
                stream=False,
                temperature=0
            )

            out = res.choices[0].message.content or "No output"
            latency = int((time.time() - start) * 1000)

            return True, f"HF OK • {out[:25]}...", latency

        except Exception as e:
            return False, f"Connection failed: {e}", None

    # ----------------------------------------------------------------------

    async def get_available_models(self) -> List[str]:
        return [
            "HuggingFaceH4/zephyr-7b-beta",
            "microsoft/DialoGPT-medium",
            "microsoft/DialoGPT-large",
            "EleutherAI/gpt-neo-1.3B",
            "gpt2",
        ]

class OpenRouterProvider(OpenAIProvider):
    """OpenRouter - Provider le plus fiable en 2025 (gratuit + payant)"""
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            api_key=api_key or "sk-or-v1-000000000000000000000000000000000000000000000000",
            base_url=base_url,
            config=config or {}
        )
    
    async def test_connection(self) -> tuple[bool, str, Optional[int]]:
        """Test avec le modèle :free le plus stable du moment (14 nov 2025)"""
        try:
            start_time = time.time()
            response = await self.client.chat.completions.create(
                model="mistralai/mistral-7b-instruct:free",   # ← CELUI-LÀ MARCHE TOUJOURS
                messages=[{"role": "user", "content": "ok"}],
                max_tokens=10,
                temperature=0
            )
            latency = int((time.time() - start_time) * 1000)
            return True, f"OpenRouter OK • {response.model}", latency
        except Exception as e:
            return False, f"OpenRouter: {str(e)}", None

    async def get_available_models(self) -> List[str]:
        try:
            resp = await self.client.models.list()
            return [m.id for m in resp.data if ":free" in m.id or m.id]  # priorise les gratuits
        except:
            return [
                "mistralai/mistral-7b-instruct:free",           # gratuit + stable
                "deepseek/deepseek-chat-v3.1:free",             # gratuit (quand pas saturé)
                "z-ai/glm-4.5-air:free",                        # gratuit
                "openai/gpt-oss-20b:free",                      # gratuit
                "google/gemini-2.0-flash-exp:free",             # gratuit si dispo
                # Modèles payants mais excellents (avec vraie clé)
                "openai/gpt-4o-mini",
                "anthropic/claude-3.5-sonnet",
                "meta-llama/llama-3.3-70b-instruct",
                "x-ai/grok-3",
            ]
    
class GrokProvider(OpenAIProvider):
    """xAI Grok - API officielle (Grok-3 & Grok-3 mini)"""
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.x.ai/v1",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            config=config or {}
        )
    
    async def get_available_models(self) -> List[str]:
        """Modèles disponibles sur l'API Grok (novembre 2025)"""
        return [
            "grok-3",           # Le plus puissant (équivalent GPT-5 niveau)
            "grok-3-mini",      # Rapide + très bon marché
            "grok-3-vision",    # Multimodal (bêta)
        ]
    
    async def test_connection(self) -> tuple[bool, str, Optional[int]]:
        """Test spécifique Grok avec grok-3-mini (le moins cher)"""
        try:
            start_time = time.time()
            await self.client.chat.completions.create(
                model="grok-3-mini",
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5
            )
            latency = int((time.time() - start_time) * 1000)
            return True, "Grok API OK • 25$ crédit dispo", latency
        except Exception as e:
            return False, f"Grok échoué: {str(e)}", None

class GroqProvider(OpenAIProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.groq.com/openai/v1",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            config=config
        )
    
    async def test_connection(self) -> tuple[bool, str, Optional[int]]:
        """Test avec un modèle rapide et gratuit"""
        try:
            start_time = time.time()
            response = await self.client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5
            )
            latency = int((time.time() - start_time) * 1000)
            return True, f"Groq OK • {response.model}", latency
        except Exception as e:
            return False, f"Groq error: {str(e)}", None

    async def get_available_models(self) -> List[str]:
        """Modèles réels Groq (nov 2025)"""
        return [
            "openai/gpt-oss-20b"
        ]

class ProviderFactory:
    """Factory to create LLM providers"""
    
    @staticmethod
    def create_provider(
        provider_name: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        config: Dict[str, Any] = None
    ) -> BaseLLMProvider:
        """Create provider instance"""
        
        providers = {
            "openai": OpenAIProvider,
            "claude": ClaudeProvider,
            "ollama": OllamaProvider,
            "gemini": GeminiProvider,
            "lmstudio": LMStudioProvider,
            "localai": LocalAIProvider,
            "lmdeploy": LMDeployProvider,
            "oobabooga": OobaboogaProvider,
            "vllm": VLLMProvider,
            "huggingface": HuggingFaceProvider,
            "openrouter": OpenRouterProvider,
            "groq": GroqProvider,
            "grok": GrokProvider,
        }
        
        provider_class = providers.get(provider_name.lower())
        if not provider_class:
            raise ValueError(f"Unknown provider: {provider_name}")
        
        if provider_name.lower() in ["ollama", "lmstudio", "localai", "lmdeploy", "oobabooga", "vllm"]:
            return provider_class(api_key=api_key, base_url=base_url or provider_class.__init__.__defaults__[1], config=config)
        else:
            if not api_key:
                raise ValueError(f"API key required for {provider_name}")
            return provider_class(api_key=api_key, base_url=base_url, config=config)