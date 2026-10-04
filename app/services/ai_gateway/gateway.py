import time
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.base import APICredential, ProviderUsage, AIBatchJob
from app.core.config import settings
from app.core.security import decrypt_api_key
import pybreaker
from app.core.resilience import llm_breaker
from app.core.observability import metrics_registry

from app.services.ai_gateway.adapters import (
    BaseProviderAdapter, OpenAIAdapter, AnthropicAdapter, GeminiAdapter,
    GrokAdapter, GroqAdapter, MistralAdapter, CohereAdapter, LocalAdapter,
    OpenRouterAdapter, TogetherAdapter
)
from app.services.ai_gateway.caching import PromptOptimizationEngine
from app.services.ai_gateway.routing import AIRoutingEngine
from app.services.ai_gateway.cost_optimizer import AICostOptimizer
from app.services.ai_gateway.batching import BatchExecutionEngine

logger = logging.getLogger(__name__)

class AIProviderGateway:
    def __init__(self):
        self.adapters: Dict[str, BaseProviderAdapter] = {}
        self._initialize_adapters()

    def _initialize_adapters(self):
        # We will dynamically instantiate adapters with keys in executeRequest
        pass

    def _get_adapter(self, provider: str, api_key: str) -> BaseProviderAdapter:
        # Returns or instantiates the adapter for the given provider
        provider_lower = (provider or "").lower().strip()
        if provider_lower == "openai":
            return OpenAIAdapter(api_key=api_key)
        elif provider_lower == "openrouter":
            return OpenRouterAdapter(api_key=api_key)
        elif provider_lower in ("together", "togetherapi", "together_ai"):
            return TogetherAdapter(api_key=api_key)
        elif provider_lower == "anthropic":
            return AnthropicAdapter(api_key=api_key)
        elif provider_lower == "gemini":
            return GeminiAdapter(api_key=api_key)
        elif provider_lower in ("grok", "xai"):
            return GrokAdapter(api_key=api_key)
        elif provider_lower == "groq":
            return GroqAdapter(api_key=api_key)
        elif provider_lower == "mistral":
            return MistralAdapter(api_key=api_key)
        elif provider_lower == "cohere":
            return CohereAdapter(api_key=api_key)
        elif provider_lower == "local":
            return LocalAdapter(api_key=api_key)
        else:
            raise ValueError(f"Provider '{provider}' is not supported. Please configure a valid API key.")

    def registerProvider(self, provider_name: str, adapter: BaseProviderAdapter) -> None:
        self.adapters[provider_name.lower()] = adapter

    def selectProvider(
        self,
        configured_providers: List[str],
        complexity: str = "medium",
        realtime: bool = False,
        bulk: bool = False
    ) -> tuple:
        return AIRoutingEngine.selectProvider(configured_providers, complexity, realtime, bulk)

    def get_tenant_ai_mode(self, db: Session, tenant_id: str) -> str:
        """
        Returns 'inbuilt' or 'byok' for the tenant.
        Checks APICredential with provider='ai_mode'.
        If not set, defaults to 'byok' if tenant has configured credentials,
        or settings.DEFAULT_AI_MODE ('inbuilt') if system env keys exist.
        """
        if tenant_id and db:
            cred = db.query(APICredential).filter(
                APICredential.tenant_id == tenant_id,
                APICredential.provider == "ai_mode"
            ).first()
            if cred and cred.settings and "mode" in cred.settings:
                return cred.settings["mode"].lower()
            # If tenant has configured any AI brain credential, default to byok
            has_creds = db.query(APICredential).filter(
                APICredential.tenant_id == tenant_id,
                APICredential.provider.in_(["openrouter", "together", "groq", "grok", "anthropic", "openai", "gemini"])
            ).first()
            if has_creds:
                return "byok"
        return (getattr(settings, "DEFAULT_AI_MODE", None) or "inbuilt").lower()

    def set_tenant_ai_mode(self, db: Session, tenant_id: str, mode: str) -> str:
        """Sets the tenant's AI mode ('inbuilt' or 'byok')."""
        normalized = "byok" if mode.lower() == "byok" else "inbuilt"
        if not tenant_id or not db:
            return normalized
        cred = db.query(APICredential).filter(
            APICredential.tenant_id == tenant_id,
            APICredential.provider == "ai_mode"
        ).first()
        if not cred:
            cred = APICredential(
                tenant_id=tenant_id,
                provider="ai_mode",
                encrypted_key="",
                settings={"mode": normalized}
            )
            db.add(cred)
        else:
            curr = dict(cred.settings or {})
            curr["mode"] = normalized
            cred.settings = curr
        db.commit()
        return normalized

    def _get_system_env_key(self, provider: str) -> str:
        p = (provider or "").lower().strip()
        import os
        if p == "openrouter":
            return getattr(settings, "OPENROUTER_API_KEY", None) or os.getenv("OPENROUTER_API_KEY") or ""
        elif p in ("together", "togetherapi", "together_ai"):
            return (
                getattr(settings, "TOGETHER_API_KEY", None)
                or os.getenv("TOGETHER_API_KEY")
                or getattr(settings, "TOGETHERAI_API_KEY", None)
                or os.getenv("TOGETHERAI_API_KEY")
                or ""
            )
        elif p == "groq":
            return getattr(settings, "GROQ_API_KEY", None) or os.getenv("GROQ_API_KEY") or ""
        elif p in ("grok", "xai"):
            return (
                getattr(settings, "GROK_API_KEY", None)
                or os.getenv("GROK_API_KEY")
                or getattr(settings, "XAI_API_KEY", None)
                or os.getenv("XAI_API_KEY")
                or ""
            )
        elif p == "anthropic":
            return settings.SHARED_CLAUDE_KEY or settings.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY") or ""
        elif p == "openai":
            return settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY") or ""
        elif p == "gemini":
            return (
                getattr(settings, "GEMINI_API_KEY", None)
                or os.getenv("GEMINI_API_KEY")
                or getattr(settings, "GOOGLE_API_KEY", None)
                or os.getenv("GOOGLE_API_KEY")
                or ""
            )
        elif p == "mistral":
            return os.getenv("MISTRAL_API_KEY") or ""
        elif p == "cohere":
            return os.getenv("COHERE_API_KEY") or ""
        elif p == "firecrawl":
            return getattr(settings, "FIRECRAWL_API_KEY", None) or os.getenv("FIRECRAWL_API_KEY") or ""
        return ""

    def _get_api_key(self, db: Session, tenant_id: str, provider: str) -> str:
        provider_lower = (provider or "").lower().strip()
        if provider_lower in ("togetherapi", "together_ai"):
            provider_lower = "together"
        elif provider_lower in ("xai",):
            provider_lower = "grok"

        # Check tenant's configured mode
        mode = self.get_tenant_ai_mode(db, tenant_id)

        # 1. If in BYOK mode: lookup key from database APICredential
        if mode == "byok" and tenant_id:
            cred = db.query(APICredential).filter(
                APICredential.tenant_id == tenant_id,
                APICredential.provider == provider_lower
            ).first()
            if cred and cred.encrypted_key:
                return decrypt_api_key(cred.encrypted_key)
            return ""

        # 2. If in Inbuilt mode or tenant_id is empty: use server environment settings
        system_key = self._get_system_env_key(provider_lower)
        if system_key:
            return system_key

        # 3. Fallback: if server key is not in env, check if tenant has a BYOK credential
        if tenant_id:
            cred = db.query(APICredential).filter(
                APICredential.tenant_id == tenant_id,
                APICredential.provider == provider_lower
            ).first()
            if cred and cred.encrypted_key:
                return decrypt_api_key(cred.encrypted_key)

        return ""

    def _get_configured_providers(self, db: Session, tenant_id: str) -> List[str]:
        configured = set()
        mode = self.get_tenant_ai_mode(db, tenant_id)

        # In BYOK mode: prioritize tenant's own credentials
        if mode == "byok" and tenant_id:
            creds = db.query(APICredential).filter(APICredential.tenant_id == tenant_id).all()
            for c in creds:
                if c.encrypted_key and c.provider not in ("ai_mode",):
                    p = c.provider.lower()
                    if p in ("togetherapi", "together_ai"):
                        p = "together"
                    elif p in ("xai",):
                        p = "grok"
                    configured.add(p)

        # In Inbuilt mode (or if no BYOK keys found): include server environment keys
        for p in ["openrouter", "together", "groq", "grok", "anthropic", "openai", "gemini", "mistral", "cohere"]:
            if self._get_system_env_key(p):
                configured.add(p)

        # If tenant has BYOK credentials even in Inbuilt mode, include them as well
        if tenant_id:
            creds = db.query(APICredential).filter(APICredential.tenant_id == tenant_id).all()
            for c in creds:
                if c.encrypted_key and c.provider not in ("ai_mode",):
                    p = c.provider.lower()
                    if p in ("togetherapi", "together_ai"):
                        p = "together"
                    elif p in ("xai",):
                        p = "grok"
                    configured.add(p)

        return list(configured)

    async def executeRequest(
        self,
        db: Session,
        tenant_id: str,
        prompt: str,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        system_prompt: Optional[str] = None,
        task_type: str = "general",
        realtime: bool = False,
        complexity: str = "medium",
        bulk: bool = False,
        **kwargs
    ) -> str:
        """
        Main execution point for standard completions.
        Handles: Dynamic Routing, Multi-Provider Failover, Cost tracking, and DB logging.
        """
        configured = self._get_configured_providers(db, tenant_id)
        if not configured:
            req_prov = provider or "anthropic"
            raise ValueError(f"No API key configured for provider '{req_prov}'. Please configure your API key under Platform Setup -> API Settings.")
        
        # 1. Routing Decision
        if not provider or not model:
            provider, model = self.selectProvider(configured, complexity, realtime, bulk)
            
        # Keep track of tried providers for failover chain
        tried_providers = []
        current_provider = provider
        current_model = model
        
        # Default chain of fallback providers for safety & redundancy
        primary_pref = (getattr(settings, "DEFAULT_AI_PROVIDER", None) or "openrouter").lower().strip()
        all_vendors = ["openrouter", "together", "groq", "grok", "openai", "anthropic", "gemini"]
        # Ensure primary is tried first, then others
        fallback_chain = [primary_pref] + [v for v in all_vendors if v != primary_pref]
        
        def _get_failover_model(prov: str, original_model: Optional[str] = None) -> str:
            prov_lower = (prov or "").lower().strip()
            if prov_lower == "openrouter":
                # If original model was on another provider, OpenRouter can route it directly or use default
                if original_model and ("/" in original_model or "gpt" in original_model or "claude" in original_model):
                    return original_model
                return getattr(settings, "DEFAULT_AI_MODEL", None) or "google/gemini-2.5-flash"
            elif prov_lower in ("together", "togetherapi"):
                return "meta-llama/Llama-3.3-70B-Instruct-Turbo"
            elif prov_lower == "groq":
                return "llama-3.3-70b-versatile"
            elif prov_lower in ("grok", "xai"):
                return "grok-2"
            elif prov_lower == "openai":
                return "gpt-4o-mini"
            elif prov_lower == "anthropic":
                return "claude-haiku-4-5-20251001"
            elif prov_lower == "gemini":
                return "gemini-2.5-flash"
            return "default-model"

        while current_provider:
            tried_providers.append(current_provider)
            api_key = self._get_api_key(db, tenant_id, current_provider)
            
            # Determine failover source if applicable
            failover_from = tried_providers[-2] if len(tried_providers) > 1 else None
            
            # If no API key, trigger failover to next configured provider or raise error
            if not api_key:
                logger.warning(f"Provider {current_provider} API key missing. Failover triggered.")
                
                # Log failed attempt
                usage_failed = ProviderUsage(
                    tenant_id=tenant_id,
                    provider=current_provider,
                    model=current_model,
                    input_tokens=0,
                    output_tokens=0,
                    cost=0.0,
                    latency=0.0,
                    status="failed",
                    task_type=task_type,
                    error_message="API key missing",
                    failover_from=failover_from
                )
                db.add(usage_failed)
                db.commit()
                
                # Record metrics
                metrics_registry.record_ai_call(
                    provider=current_provider,
                    model=current_model,
                    status="failed",
                    duration=0.0
                )
                
                # Find other configured providers not tried yet
                configured_remaining = [p for p in configured if p not in tried_providers]
                if not configured_remaining:
                    raise ValueError(
                        f"No API key configured for any provider. "
                        f"Please go to Platform Setup → API Settings and add a provider key "
                        f"(OpenRouter, Together AI, Groq, Grok, OpenAI, Anthropic, Gemini)."
                    )
                
                current_provider = configured_remaining[0]
                current_model = _get_failover_model(current_provider, model)
                continue
                
            try:
                start_time = time.time()
                adapter = self._get_adapter(current_provider, api_key)
                
                logger.info(f"Executing request via provider={current_provider}, model={current_model}")
                with llm_breaker.calling():
                    response_data = await adapter.execute_request(
                        prompt=prompt,
                        model=current_model,
                        system_prompt=system_prompt,
                        **kwargs
                    )
                latency = time.time() - start_time
                
                content = response_data["content"]
                input_tokens = response_data["input_tokens"]
                output_tokens = response_data["output_tokens"]
                cached_tokens = response_data.get("cached_tokens", 0)
                
                # Calculate actual cost and savings
                cost_calc = AICostOptimizer.calculate_actual_cost(
                    provider=current_provider,
                    model=current_model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cached_tokens=cached_tokens,
                    is_batch=bulk,
                    cache_hit=False
                )
                
                # Log successful usage
                usage = ProviderUsage(
                    tenant_id=tenant_id,
                    provider=current_provider,
                    model=current_model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=cost_calc["cost"],
                    latency=latency,
                    status="success" if not failover_from else "failover",
                    task_type=task_type,
                    cached_tokens=cached_tokens,
                    is_batch=bulk,
                    failover_from=failover_from
                )
                db.add(usage)
                db.commit()
                
                # Record metrics
                metrics_registry.record_ai_call(
                    provider=current_provider,
                    model=current_model,
                    status="success",
                    duration=latency
                )
                
                # Auto-cache locally if provider lacks native caching
                PromptOptimizationEngine.fallbackLocalCaching(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    response_text=content,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    provider=current_provider,
                    model=current_model
                )
                
                return content
                
            except Exception as e:
                latency = time.time() - start_time
                logger.error(f"Execution failed on {current_provider}: {e}. Activating safety failover.")
                
                # Log failed attempt
                usage_failed = ProviderUsage(
                    tenant_id=tenant_id,
                    provider=current_provider,
                    model=current_model,
                    input_tokens=0,
                    output_tokens=0,
                    cost=0.0,
                    latency=latency,
                    status="failed",
                    task_type=task_type,
                    error_message=str(e),
                    failover_from=failover_from
                )
                db.add(usage_failed)
                db.commit()
                
                # Record metrics
                metrics_registry.record_ai_call(
                    provider=current_provider,
                    model=current_model,
                    status="failed",
                    duration=latency
                )
                
                # Find other configured providers not tried yet
                configured_remaining = [p for p in configured if p not in tried_providers]
                if not configured_remaining:
                    raise ValueError(
                        f"All configured providers failed. Last provider '{current_provider}' failed with: {e}. "
                        f"Please check your API keys under Platform Setup → API Settings."
                    )
                
                current_provider = configured_remaining[0]
                current_model = _get_failover_model(current_provider, model)
                continue

        raise Exception("All configured providers failed.")

    def failoverProvider(self, tried_providers: List[str], fallback_chain: List[str]) -> tuple:
        """
        Implements primary -> secondary -> local fallback progression.
        """
        for p in fallback_chain:
            if p not in tried_providers:
                if p == "openrouter":
                    return "openrouter", getattr(settings, "DEFAULT_AI_MODEL", None) or "google/gemini-2.5-flash"
                elif p in ("together", "togetherapi"):
                    return "together", "meta-llama/Llama-3.3-70B-Instruct-Turbo"
                elif p == "groq":
                    return "groq", "llama-3.3-70b-versatile"
                elif p in ("grok", "xai"):
                    return "grok", "grok-2"
                elif p == "openai":
                    return "openai", "gpt-4o-mini"
                elif p == "anthropic":
                    return "anthropic", "claude-haiku-4-5-20251001"
                elif p == "gemini":
                    return "gemini", "gemini-2.5-flash"
                elif p == "local":
                    return "local", "llama3"
                    
        raise ValueError(
            "All configured providers failed. Please check your API keys under "
            "Platform Setup → API Settings or add a new provider."
        )

    async def executeCached(
        self,
        db: Session,
        tenant_id: str,
        prompt: str,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        system_prompt: Optional[str] = None,
        task_type: str = "general",
        realtime: bool = False,
        complexity: str = "medium",
        bulk: bool = False,
        **kwargs
    ) -> str:
        """
        Executes request with universal prompt caching logic.
        """
        # Check universal cache engine first
        cached_result = PromptOptimizationEngine.retrievePrompt(prompt, system_prompt)
        if cached_result:
            # Cache hit!
            logger.info("Universal Cache Hit! Bypassing provider execution.")
            
            # Log usage as cache hit (saves cost & latency)
            usage = ProviderUsage(
                tenant_id=tenant_id,
                provider=cached_result["provider"],
                model=cached_result["model"],
                input_tokens=cached_result["input_tokens"],
                output_tokens=cached_result["output_tokens"],
                cost=0.0, # 100% free!
                latency=0.005, # negligible
                status="success",
                task_type=task_type,
                cache_hit=True,
                cached_tokens=cached_result["input_tokens"],
                is_batch=bulk
            )
            db.add(usage)
            db.commit()
            
            # Record metrics
            metrics_registry.record_ai_call(
                provider=cached_result["provider"],
                model=cached_result["model"],
                status="success",
                duration=0.005,
                cache_hit=True
            )
            return cached_result["content"]
            
        # Cache miss: execute standard request
        content = await self.executeRequest(
            db=db,
            tenant_id=tenant_id,
            prompt=prompt,
            model=model,
            provider=provider,
            system_prompt=system_prompt,
            task_type=task_type,
            realtime=realtime,
            complexity=complexity,
            bulk=bulk,
            **kwargs
        )
        
        # Populate cache (executeRequest already calls PromptOptimizationEngine.fallbackLocalCaching internally,
        # but we also explicitly populate it for native caching models here just in case)
        # Note: we need to lookup provider and model if not supplied, which is done during executeRequest.
        # So executeRequest is the best place to cache the successful response.
        
        return content

    async def executeBatch(
        self,
        db: Session,
        tenant_id: str,
        tasks: List[Dict[str, Any]],
        provider: Optional[str] = None,
        model: Optional[str] = None
    ) -> AIBatchJob:
        """
        Main execution point for batches.
        """
        configured = self._get_configured_providers(db, tenant_id)
        if not provider or not model:
            provider, model = self.selectProvider(configured, bulk=True)
            
        # Create database batch job record
        job = BatchExecutionEngine.createBatch(db, tenant_id, provider, model, tasks)
        
        # Get adapter to submit
        api_key = self._get_api_key(db, tenant_id, provider)
        adapter = self._get_adapter(provider, api_key)
        
        # Submit
        await BatchExecutionEngine.submitToProvider(db, job.id, adapter)
        
        return job

    def estimateCost(self, prompt: str, model: str, system_prompt: Optional[str] = None, provider: str = "openai") -> float:
        return AICostOptimizer.estimateCost(prompt, model, system_prompt, provider)
