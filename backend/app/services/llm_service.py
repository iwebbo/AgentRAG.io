from typing import AsyncGenerator, Optional, List, Dict, Any
from sqlalchemy.orm import Session
from uuid import UUID
import time
import logging
from datetime import datetime

from app.models import Provider, Conversation, Message
from app.services.provider_factory import ProviderFactory
from app.utils.security import decrypt_api_key
from app.config import get_settings
from app.services.verification import StreamEvent, VerificationContext, run_verified_stream
from app.services.verification_service import build_request_pipeline, effective_mode

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """
    Estimate the number of tokens in a text.
    Rule of thumb: ~4 characters = 1 token
    """
    if not text:
        return 0
    text = ' '.join(text.split())
    char_based = len(text) // 4
    words = len(text.split())
    word_based = int(words * 0.75)
    estimated = (char_based + word_based) // 2
    return max(1, estimated)


class LLMService:
    """Service for LLM operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def get_active_provider(self, user_id: UUID, provider_name: Optional[str] = None) -> Provider:
        """
        Get active provider for user with fallback logic
        """
        query = self.db.query(Provider).filter(
            Provider.user_id == user_id,
            Provider.is_active == True
        )
        
        if provider_name:
            provider = query.filter(Provider.name == provider_name).first()
            if provider:
                return provider
        
        provider = query.order_by(Provider.priority.desc()).first()
        
        if not provider:
            raise ValueError("No active provider configured")
        
        return provider
    
    def _prepare_messages(
        self,
        conversation: Conversation,
        new_message: str,
        reasoning_mode: str
    ) -> List[Dict[str, str]]:
        """
        Prepare messages array for LLM
        """
        messages = []
        
        if conversation.system_prompt:
            messages.append({
                "role": "system",
                "content": conversation.system_prompt
            })
        
        if reasoning_mode == "cot":
            reasoning_instruction = {
                "role": "system",
                "content": (
                    "Solve step by step. Use this format:\n\n"
                    "**Step 1:** [Describe]\n"
                    "**Reasoning:** [Explain]\n"
                    "**Step 2:** ...\n\n"
                    "**Final Answer:** [Your answer here]"
                )
            }
            messages.append(reasoning_instruction)
        elif reasoning_mode == "deep":
            reasoning_instruction = {
                "role": "system",
                "content": (
                    "Provide a deep, multi-perspective analysis. "
                    "Break down the problem, explore alternatives, validate assumptions with examples or logic, "
                    "and deliver a comprehensive, nuanced final answer."
                )
            }
            messages.append(reasoning_instruction)
        
        for msg in conversation.messages:
            messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        messages.append({
            "role": "user",
            "content": new_message
        })
        
        return messages
    
    async def stream_chat(
        self,
        user_id: UUID,
        conversation_id: UUID,
        message: str,
        provider_name: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        reasoning_mode: Optional[str] = None,
        verify_mode: Optional[str] = None,
        emit_events: bool = False
    ) -> AsyncGenerator[Any, None]:
        """
        Stream chat completion.

        Yields `str` chunks (unchanged contract for existing callers). With
        `emit_events=True` it also yields `StreamEvent` objects (status / verdict /
        keepalive) for the SSE layer. `verify_mode`: off | annotate | gate
        (default: settings.VERIFY_MODE). Verification is lint/check/judge based,
        see app/services/verification.
        """
        start_time = time.time()
        
        logger.info(f"Starting chat stream for conversation {conversation_id}")
        
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()
        
        if not conversation:
            raise ValueError("Conversation not found")
        
        message_count = self.db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).count()
        
        is_first_message = (message_count == 0)
        
        # Save user message WITH token estimation
        user_tokens = estimate_tokens(message)
        user_message = Message(
            conversation_id=conversation_id,
            role="user",
            content=message,
            tokens_used=user_tokens
        )
        self.db.add(user_message)
        self.db.commit()
        logger.info(f"User message saved: {message[:50]}... (tokens: {user_tokens})")
        
        provider = await self.get_active_provider(
            user_id,
            provider_name or conversation.provider_name
        )
        
        api_key = None
        if provider.api_key:
            api_key = decrypt_api_key(provider.api_key)
        
        llm_provider = ProviderFactory.create_provider(
            provider.name,
            api_key=api_key,
            base_url=provider.base_url,
            config=provider.config
        )
        
        messages = self._prepare_messages(
            conversation,
            message,
            reasoning_mode or conversation.reasoning_mode
        )
        
        settings = get_settings()
        mode = effective_mode(verify_mode)
        used_model = model or conversation.model
        used_temperature = temperature or conversation.temperature

        def open_stream(msgs):
            return llm_provider.stream_completion(
                messages=msgs, model=used_model, temperature=used_temperature
            )

        pipeline = None
        if mode != "off":
            pipeline = build_request_pipeline(self.db, user_id, llm_provider, used_model, is_rag=False)
        ctx = VerificationContext(question=message, is_rag=False)

        full_response = ""
        verdict = None
        saved_message = None
        try:
            logger.info("Starting LLM streaming (verify mode: %s)...", mode)
            logger.info("Reasoning mode: %s (user input)", reasoning_mode)
            logger.info("Fallback reasoning mode: %s", conversation.reasoning_mode)
            async for event in run_verified_stream(
                open_stream=open_stream,
                messages=messages,
                ctx=ctx,
                pipeline=pipeline,
                mode=mode,
                max_rounds=settings.VERIFY_MAX_ROUNDS,
                min_score=settings.VERIFY_MIN_SCORE,
                keepalive_seconds=settings.VERIFY_KEEPALIVE_SECONDS,
            ):
                if event.kind == "token":
                    yield event.data
                elif event.kind == "final":
                    # Persist right away: the answer must survive a client disconnect
                    # that happens while the judge is still running.
                    full_response = event.data
                    saved_message = self._save_assistant_message(
                        conversation, conversation_id, full_response, start_time,
                        message, is_first_message, provider_name, model, temperature, reasoning_mode,
                    )
                elif event.kind == "verdict":
                    verdict = event.data
                    self._attach_verdict(saved_message, verdict)
                    if emit_events:
                        yield event
                elif emit_events:
                    yield event

            logger.info(f"Streaming complete. Response length: {len(full_response)}")

        except Exception as e:
            logger.error(f"Streaming error during generation: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            self.db.rollback()
            raise

    def _attach_verdict(self, assistant_message: Optional[Message], verdict: Any) -> None:
        if assistant_message is None or verdict is None:
            return
        try:
            assistant_message.verification = verdict.to_dict()
            self.db.commit()
        except Exception:
            logger.exception("Could not persist verification verdict")
            self.db.rollback()

    def _save_assistant_message(
        self,
        conversation: Conversation,
        conversation_id: UUID,
        full_response: str,
        start_time: float,
        message: str,
        is_first_message: bool,
        provider_name: Optional[str],
        model: Optional[str],
        temperature: Optional[float],
        reasoning_mode: Optional[str],
    ) -> Optional[Message]:
        # Save assistant message WITH token estimation
        try:
            latency_ms = int((time.time() - start_time) * 1000)
            
            # ESTIMATE TOKENS for assistant response
            assistant_tokens = estimate_tokens(full_response)
            
            logger.info(f"Saving assistant message...")
            logger.info(f"   Length: {len(full_response)} chars")
            logger.info(f"   Tokens: {assistant_tokens} (estimated)")
            logger.info(f"   Preview: {full_response[:100]}...")
            
            assistant_message = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=full_response,
                latency_ms=latency_ms,
                tokens_used=assistant_tokens  # 
            )
            self.db.add(assistant_message)
            
            # Mettre à jour la conversation avec les settings utilisés
            conversation.updated_at = datetime.utcnow()
            if provider_name:
                conversation.provider_name = provider_name
            if model:
                conversation.model = model
            if temperature is not None:
                conversation.temperature = temperature
            if reasoning_mode:
                conversation.reasoning_mode = reasoning_mode
            
            if is_first_message:
                new_title = message[:50].strip()
                if len(message) > 50:
                    new_title += "..."
                conversation.title = new_title
                logger.info(f"Auto-generated title: {new_title}")
            
            self.db.commit()
            self.db.refresh(assistant_message)
            
            logger.info(f"Assistant message saved successfully!")
            logger.info(f"   Message ID: {assistant_message.id}")
            logger.info(f"   Tokens used: {assistant_tokens}")
            return assistant_message
            
        except Exception as e:
            logger.error(f"CRITICAL: Error saving assistant message: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            self.db.rollback()
        return None

    async def get_available_models(self, provider_name: str) -> List[str]:
        """
        Get available models for a provider using dynamic fetching
        """
        try:
            # Get a provider instance (we don't need user_id for this)
            provider = self.db.query(Provider).filter(
                Provider.name == provider_name.lower(),
                Provider.is_active == True
            ).first()
            
            # Decrypt API key if needed
            api_key = None
            base_url = None
            if provider:
                if provider.api_key:
                    api_key = decrypt_api_key(provider.api_key)
                base_url = provider.base_url
            
            # Create provider instance
            llm_provider = ProviderFactory.create_provider(
                provider_name.lower(),
                api_key=api_key,
                base_url=base_url
            )
            
            # Get models from provider
            models = await llm_provider.get_available_models()
            return models if models else []
            
        except Exception as e:
            logger.error(f"Error getting models for {provider_name}: {str(e)}")
            # Return fallback models
            models_map = {
                "openai": [
                    "gpt-4-turbo-preview",
                    "gpt-4",
                    "gpt-3.5-turbo",
                    "gpt-3.5-turbo-16k"
                ],
                "claude": [
                    "claude-3-5-sonnet-20241022",
                    "claude-3-5-haiku-20241022",
                    "claude-3-opus-20240229",
                    "claude-3-sonnet-20240229",
                    "claude-3-haiku-20240307"
                ],
                "ollama": ["llama2", "mistral", "codellama", "neural-chat"]
            }
            return models_map.get(provider_name.lower(), [])