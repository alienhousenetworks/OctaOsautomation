from typing import List, Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)

# Standard model configurations with costs in USD per 1,000,000 tokens
# Latency values are representative benchmarks (lower is faster)
MODEL_REGISTRY = {
    # OpenAI
    "openai/gpt-4o": {
        "provider": "openai",
        "model": "gpt-4o",
        "complexity": "high",
        "latency": 1.2,
        "input_cost_1m": 5.00,
        "output_cost_1m": 15.00,
        "supports_batch": True,
        "supports_caching": True
    },
    "openai/gpt-4o-mini": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "complexity": "low",
        "latency": 0.4,
        "input_cost_1m": 0.15,
        "output_cost_1m": 0.60,
        "supports_batch": True,
        "supports_caching": True
    },
    # Anthropic
    "anthropic/claude-opus-4-8": {
        "provider": "anthropic",
        "model": "claude-opus-4-8",
        "complexity": "high",
        "latency": 2.0,
        "input_cost_1m": 5.00,
        "output_cost_1m": 25.00,
        "supports_batch": True,
        "supports_caching": True
    },
    "anthropic/claude-sonnet-4-6": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "complexity": "high",
        "latency": 1.2,
        "input_cost_1m": 3.00,
        "output_cost_1m": 15.00,
        "supports_batch": True,
        "supports_caching": True
    },
    "anthropic/claude-haiku-4-5-20251001": {
        "provider": "anthropic",
        "model": "claude-haiku-4-5-20251001",
        "complexity": "low",
        "latency": 0.4,
        "input_cost_1m": 1.00,
        "output_cost_1m": 5.00,
        "supports_batch": True,
        "supports_caching": True
    },
    # Google Gemini (2.5 series — stable, recommended for most keys)
    "gemini/gemini-2.5-pro": {
        "provider": "gemini",
        "model": "gemini-2.5-pro",
        "complexity": "high",
        "latency": 1.8,
        "input_cost_1m": 1.25,
        "output_cost_1m": 5.00,
        "supports_batch": True,
        "supports_caching": True
    },
    "gemini/gemini-2.5-flash": {
        "provider": "gemini",
        "model": "gemini-2.5-flash",
        "complexity": "low",
        "latency": 0.35,
        "input_cost_1m": 0.075,
        "output_cost_1m": 0.30,
        "supports_batch": True,
        "supports_caching": True
    },
    # Google Gemini (2.0 series — widely available, fast)
    "gemini/gemini-2.0-flash": {
        "provider": "gemini",
        "model": "gemini-2.0-flash",
        "complexity": "low",
        "latency": 0.30,
        "input_cost_1m": 0.10,
        "output_cost_1m": 0.40,
        "supports_batch": False,
        "supports_caching": True
    },
    "gemini/gemini-2.0-flash-lite": {
        "provider": "gemini",
        "model": "gemini-2.0-flash-lite",
        "complexity": "low",
        "latency": 0.20,
        "input_cost_1m": 0.075,
        "output_cost_1m": 0.30,
        "supports_batch": False,
        "supports_caching": False
    },
    # Google Gemini (1.5 series — legacy, may not be available on all keys)
    "gemini/gemini-1.5-pro": {
        "provider": "gemini",
        "model": "gemini-1.5-pro",
        "complexity": "high",
        "latency": 1.8,
        "input_cost_1m": 1.25,
        "output_cost_1m": 5.00,
        "supports_batch": True,
        "supports_caching": True
    },
    "gemini/gemini-1.5-flash": {
        "provider": "gemini",
        "model": "gemini-1.5-flash",
        "complexity": "low",
        "latency": 0.35,
        "input_cost_1m": 0.075,
        "output_cost_1m": 0.30,
        "supports_batch": True,
        "supports_caching": True
    },
    # Grok (xAI)
    "grok/grok-2": {
        "provider": "grok",
        "model": "grok-2",
        "complexity": "high",
        "latency": 1.1,
        "input_cost_1m": 2.00,
        "output_cost_1m": 10.00,
        "supports_batch": False,
        "supports_caching": False
    },
    "grok/grok-2-latest": {
        "provider": "grok",
        "model": "grok-2-latest",
        "complexity": "high",
        "latency": 1.1,
        "input_cost_1m": 2.00,
        "output_cost_1m": 10.00,
        "supports_batch": False,
        "supports_caching": False
    },
    "grok/grok-2-vision-1212": {
        "provider": "grok",
        "model": "grok-2-vision-1212",
        "complexity": "high",
        "latency": 1.3,
        "input_cost_1m": 2.00,
        "output_cost_1m": 10.00,
        "supports_batch": False,
        "supports_caching": False
    },
    "grok/grok-beta": {
        "provider": "grok",
        "model": "grok-beta",
        "complexity": "medium",
        "latency": 1.0,
        "input_cost_1m": 5.00,
        "output_cost_1m": 15.00,
        "supports_batch": False,
        "supports_caching": False
    },
    # OpenRouter (Meta-Hub for all Frontier & Open-Weights Models)
    "openrouter/google/gemini-2.5-flash": {
        "provider": "openrouter",
        "model": "google/gemini-2.5-flash",
        "complexity": "low",
        "latency": 0.35,
        "input_cost_1m": 0.075,
        "output_cost_1m": 0.30,
        "supports_batch": True,
        "supports_caching": True
    },
    "openrouter/google/gemini-2.5-pro": {
        "provider": "openrouter",
        "model": "google/gemini-2.5-pro",
        "complexity": "high",
        "latency": 1.8,
        "input_cost_1m": 1.25,
        "output_cost_1m": 5.00,
        "supports_batch": True,
        "supports_caching": True
    },
    "openrouter/openai/gpt-4o": {
        "provider": "openrouter",
        "model": "openai/gpt-4o",
        "complexity": "high",
        "latency": 1.2,
        "input_cost_1m": 2.50,
        "output_cost_1m": 10.00,
        "supports_batch": True,
        "supports_caching": True
    },
    "openrouter/openai/gpt-4o-mini": {
        "provider": "openrouter",
        "model": "openai/gpt-4o-mini",
        "complexity": "low",
        "latency": 0.35,
        "input_cost_1m": 0.15,
        "output_cost_1m": 0.60,
        "supports_batch": True,
        "supports_caching": True
    },
    "openrouter/anthropic/claude-3.5-sonnet": {
        "provider": "openrouter",
        "model": "anthropic/claude-3.5-sonnet",
        "complexity": "high",
        "latency": 1.2,
        "input_cost_1m": 3.00,
        "output_cost_1m": 15.00,
        "supports_batch": True,
        "supports_caching": True
    },
    "openrouter/anthropic/claude-3.5-haiku": {
        "provider": "openrouter",
        "model": "anthropic/claude-3.5-haiku",
        "complexity": "low",
        "latency": 0.4,
        "input_cost_1m": 0.80,
        "output_cost_1m": 4.00,
        "supports_batch": True,
        "supports_caching": True
    },
    "openrouter/deepseek/deepseek-chat": {
        "provider": "openrouter",
        "model": "deepseek/deepseek-chat",
        "complexity": "low",
        "latency": 0.6,
        "input_cost_1m": 0.14,
        "output_cost_1m": 0.28,
        "supports_batch": True,
        "supports_caching": True
    },
    "openrouter/deepseek/deepseek-r1": {
        "provider": "openrouter",
        "model": "deepseek/deepseek-r1",
        "complexity": "high",
        "latency": 2.0,
        "input_cost_1m": 0.55,
        "output_cost_1m": 2.19,
        "supports_batch": True,
        "supports_caching": True
    },
    "openrouter/meta-llama/llama-3.3-70b-instruct": {
        "provider": "openrouter",
        "model": "meta-llama/llama-3.3-70b-instruct",
        "complexity": "high",
        "latency": 0.45,
        "input_cost_1m": 0.35,
        "output_cost_1m": 0.40,
        "supports_batch": True,
        "supports_caching": True
    },
    "openrouter/qwen/qwen-2.5-72b-instruct": {
        "provider": "openrouter",
        "model": "qwen/qwen-2.5-72b-instruct",
        "complexity": "high",
        "latency": 0.5,
        "input_cost_1m": 0.35,
        "output_cost_1m": 0.40,
        "supports_batch": True,
        "supports_caching": True
    },
    # Together AI (High-Speed Open-Weights & DeepSeek Hub)
    "together/meta-llama/Llama-3.3-70B-Instruct-Turbo": {
        "provider": "together",
        "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "complexity": "high",
        "latency": 0.3,
        "input_cost_1m": 0.88,
        "output_cost_1m": 0.88,
        "supports_batch": False,
        "supports_caching": False
    },
    "together/meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo": {
        "provider": "together",
        "model": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        "complexity": "low",
        "latency": 0.15,
        "input_cost_1m": 0.18,
        "output_cost_1m": 0.18,
        "supports_batch": False,
        "supports_caching": False
    },
    "together/deepseek-ai/DeepSeek-V3": {
        "provider": "together",
        "model": "deepseek-ai/DeepSeek-V3",
        "complexity": "high",
        "latency": 0.8,
        "input_cost_1m": 1.25,
        "output_cost_1m": 1.25,
        "supports_batch": False,
        "supports_caching": False
    },
    "together/deepseek-ai/DeepSeek-R1": {
        "provider": "together",
        "model": "deepseek-ai/DeepSeek-R1",
        "complexity": "high",
        "latency": 2.0,
        "input_cost_1m": 2.50,
        "output_cost_1m": 2.50,
        "supports_batch": False,
        "supports_caching": False
    },
    "together/Qwen/Qwen2.5-72B-Instruct-Turbo": {
        "provider": "together",
        "model": "Qwen/Qwen2.5-72B-Instruct-Turbo",
        "complexity": "high",
        "latency": 0.4,
        "input_cost_1m": 1.20,
        "output_cost_1m": 1.20,
        "supports_batch": False,
        "supports_caching": False
    },
    "together/mistralai/Mixtral-8x7B-Instruct-v0.1": {
        "provider": "together",
        "model": "mistralai/Mixtral-8x7B-Instruct-v0.1",
        "complexity": "medium",
        "latency": 0.35,
        "input_cost_1m": 0.60,
        "output_cost_1m": 0.60,
        "supports_batch": False,
        "supports_caching": False
    },
    # Groq
    "groq/llama-3.3-70b-versatile": {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "complexity": "high",
        "latency": 0.25,
        "input_cost_1m": 0.59,
        "output_cost_1m": 0.79,
        "supports_batch": False,
        "supports_caching": False
    },
    "groq/llama-3.1-8b-instant": {
        "provider": "groq",
        "model": "llama-3.1-8b-instant",
        "complexity": "low",
        "latency": 0.15,
        "input_cost_1m": 0.05,
        "output_cost_1m": 0.08,
        "supports_batch": False,
        "supports_caching": False
    },
    "groq/mixtral-8x7b-32768": {
        "provider": "groq",
        "model": "mixtral-8x7b-32768",
        "complexity": "medium",
        "latency": 0.20,
        "input_cost_1m": 0.24,
        "output_cost_1m": 0.24,
        "supports_batch": False,
        "supports_caching": False
    },
    # Mistral
    "mistral/mistral-large-latest": {
        "provider": "mistral",
        "model": "mistral-large-latest",
        "complexity": "high",
        "latency": 1.4,
        "input_cost_1m": 2.00,
        "output_cost_1m": 6.00,
        "supports_batch": True,
        "supports_caching": False
    },
    # Cohere
    "cohere/command-r-plus": {
        "provider": "cohere",
        "model": "command-r-plus",
        "complexity": "high",
        "latency": 1.3,
        "input_cost_1m": 2.50,
        "output_cost_1m": 10.00,
        "supports_batch": False,
        "supports_caching": False
    },
    # Local Inference
    "local/llama3": {
        "provider": "local",
        "model": "llama3",
        "complexity": "medium",
        "latency": 0.6,
        "input_cost_1m": 0.00,
        "output_cost_1m": 0.00,
        "supports_batch": False,
        "supports_caching": False
    }
}


def get_provider_models(provider: str) -> List[Dict[str, Any]]:
    """
    Returns available models for a given provider, dynamically merging built-in
    registry models with any custom models specified in environment variables
    (e.g., OPENROUTER_MODELS, TOGETHER_MODELS, GROQ_MODELS, GROK_MODELS).
    """
    from app.core.config import settings
    import os

    p_lower = (provider or "").lower().strip()
    # Normalize aliases
    if p_lower in ("togetherapi", "together_ai"):
        p_lower = "together"
    elif p_lower in ("xai",):
        p_lower = "grok"

    results: List[Dict[str, Any]] = []
    seen_model_ids = set()

    # 1. Models from MODEL_REGISTRY
    for key, spec in MODEL_REGISTRY.items():
        if spec["provider"] == p_lower:
            m_id = spec["model"]
            if m_id not in seen_model_ids:
                seen_model_ids.add(m_id)
                results.append(spec)

    # 2. Dynamic models specified in environment variables
    env_str = ""
    if p_lower == "openrouter":
        env_str = getattr(settings, "OPENROUTER_MODELS", None) or os.getenv("OPENROUTER_MODELS", "")
    elif p_lower == "together":
        env_str = getattr(settings, "TOGETHER_MODELS", None) or os.getenv("TOGETHER_MODELS", "")
    elif p_lower == "groq":
        env_str = getattr(settings, "GROQ_MODELS", None) or os.getenv("GROQ_MODELS", "")
    elif p_lower == "grok":
        env_str = getattr(settings, "GROK_MODELS", None) or os.getenv("GROK_MODELS", "")

    if env_str:
        for custom_model in [m.strip() for m in env_str.split(",") if m.strip()]:
            if custom_model not in seen_model_ids:
                seen_model_ids.add(custom_model)
                results.append({
                    "provider": p_lower,
                    "model": custom_model,
                    "complexity": "medium",
                    "latency": 0.8,
                    "input_cost_1m": 1.0,
                    "output_cost_1m": 2.0,
                    "supports_batch": False,
                    "supports_caching": False,
                })

    return results


class AIRoutingEngine:
    @staticmethod
    def selectProvider(
        configured_providers: List[str],
        complexity: str = "medium",
        realtime: bool = False,
        bulk: bool = False
    ) -> Tuple[str, str]:
        """
        Dynamically selects the best provider and model based on parameters,
        what API keys are connected, and environment default configuration.
        Returns: (provider_name, model_name)
        """
        from app.core.config import settings

        available_providers = set(p.lower() for p in configured_providers)
        # Normalize together aliases
        if "togetherapi" in available_providers:
            available_providers.add("together")
        if "xai" in available_providers:
            available_providers.add("grok")

        # 0. Check if an environment default provider is active and available
        pref_provider = (getattr(settings, "DEFAULT_AI_PROVIDER", None) or "openrouter").lower().strip()
        pref_model = getattr(settings, "DEFAULT_AI_MODEL", None)

        if pref_provider in available_providers:
            models_for_pref = [
                spec for key, spec in MODEL_REGISTRY.items()
                if spec["provider"] == pref_provider
            ]
            if pref_model:
                logger.info(f"Routed via env DEFAULT_AI_PROVIDER ({pref_provider}) and model ({pref_model})")
                return pref_provider, pref_model
            elif models_for_pref:
                # If specific mode requested, find best match in preferred provider
                if realtime:
                    selected = min(models_for_pref, key=lambda m: m["latency"])
                elif bulk:
                    batch_m = [m for m in models_for_pref if m.get("supports_batch")]
                    src = batch_m if batch_m else models_for_pref
                    selected = min(src, key=lambda m: m["input_cost_1m"] + m["output_cost_1m"])
                elif complexity == "high":
                    high_m = [m for m in models_for_pref if m.get("complexity") == "high"]
                    src = high_m if high_m else models_for_pref
                    selected = min(src, key=lambda m: m["input_cost_1m"] + m["output_cost_1m"])
                else:
                    selected = min(models_for_pref, key=lambda m: m["input_cost_1m"] + m["output_cost_1m"])
                logger.info(f"Routed via env DEFAULT_AI_PROVIDER: {selected['provider']}/{selected['model']}")
                return selected["provider"], selected["model"]

        # Filter MODEL_REGISTRY for keys that are active
        eligible_models = {
            key: spec for key, spec in MODEL_REGISTRY.items()
            if spec["provider"] in available_providers
        }

        if not eligible_models:
            raise ValueError(
                "No AI API key is configured. Please go to Platform Setup → API Settings "
                "and add at least one provider key (OpenRouter, Together AI, Groq, Grok, OpenAI, Anthropic, Gemini)."
            )

        # Apply standard routing logic
        if realtime:
            # LOWEST LATENCY
            best_key = min(eligible_models.keys(), key=lambda k: eligible_models[k]["latency"])
            selected = eligible_models[best_key]
            logger.info(f"Routed for REALTIME (lowest latency): {selected['provider']}/{selected['model']}")
            return selected["provider"], selected["model"]

        elif bulk:
            # BATCH-CAPABLE CHEAPEST
            batch_models = {k: v for k, v in eligible_models.items() if v["supports_batch"]}
            source_models = batch_models if batch_models else eligible_models

            # Find cheapest by combined token cost
            best_key = min(source_models.keys(), key=lambda k: source_models[k]["input_cost_1m"] + source_models[k]["output_cost_1m"])
            selected = source_models[best_key]
            logger.info(f"Routed for BULK (cheapest batch/overall): {selected['provider']}/{selected['model']}")
            return selected["provider"], selected["model"]

        elif complexity == "high":
            # STRONGEST REASONING MODEL (high complexity rating)
            high_models = {k: v for k, v in eligible_models.items() if v["complexity"] == "high"}
            source_models = high_models if high_models else eligible_models

            # Tie break by cost among high models
            best_key = min(source_models.keys(), key=lambda k: source_models[k]["input_cost_1m"] + source_models[k]["output_cost_1m"])
            selected = source_models[best_key]
            logger.info(f"Routed for HIGH COMPLEXITY (strongest reasoning): {selected['provider']}/{selected['model']}")
            return selected["provider"], selected["model"]

        else:
            # LOWEST COST VALID
            best_key = min(eligible_models.keys(), key=lambda k: eligible_models[k]["input_cost_1m"] + eligible_models[k]["output_cost_1m"])
            selected = eligible_models[best_key]
            logger.info(f"Routed for DEFAULT (lowest cost): {selected['provider']}/{selected['model']}")
            return selected["provider"], selected["model"]

