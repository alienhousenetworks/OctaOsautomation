from typing import Dict, Any, Optional
from app.services.ai_gateway.routing import MODEL_REGISTRY
import logging

logger = logging.getLogger(__name__)

class AICostOptimizer:
    @staticmethod
    def get_model_specs(provider: str, model: str) -> Dict[str, Any]:
        """
        Retrieves cost and properties for a given provider/model.
        """
        p_lower = (provider or "").lower().strip()
        if p_lower in ("togetherapi", "together_ai"):
            p_lower = "together"
        elif p_lower in ("xai",):
            p_lower = "grok"

        m_lower = (model or "").lower().strip()
        registry_key = f"{p_lower}/{m_lower}"
        
        # Exact match
        if registry_key in MODEL_REGISTRY:
            return MODEL_REGISTRY[registry_key]

        # Fallback keyword match if exact model name differs (e.g. version suffixes)
        for key, spec in MODEL_REGISTRY.items():
            if spec["provider"] == p_lower and (spec["model"] in m_lower or m_lower in spec["model"]):
                return spec
                
        # Default fallback
        return {
            "provider": p_lower,
            "model": model,
            "input_cost_1m": 1.0,
            "output_cost_1m": 3.0,
            "supports_batch": False,
            "supports_caching": False
        }

    @classmethod
    def estimateCost(cls, prompt: str, model: str, system_prompt: Optional[str] = None, provider: str = "openai") -> float:
        """
        Estimates task cost prior to execution.
        """
        specs = cls.get_model_specs(provider, model)
        
        # Rough token approximation (1 word = 1.33 tokens)
        input_words = len(prompt.split()) + (len(system_prompt.split()) if system_prompt else 0)
        est_input_tokens = int(input_words * 1.33)
        # Assume output is roughly 150 tokens or 1/3 of input
        est_output_tokens = max(150, int(est_input_tokens * 0.33))

        input_cost = (est_input_tokens * specs["input_cost_1m"]) / 1_000_000
        output_cost = (est_output_tokens * specs["output_cost_1m"]) / 1_000_000
        
        return input_cost + output_cost

    @classmethod
    def calculate_actual_cost(
        cls,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
        is_batch: bool = False,
        cache_hit: bool = False
    ) -> Dict[str, float]:
        """
        Calculates exact cost and savings based on token usage.
        Returns: {
            "cost": float,
            "savings": float
        }
        """
        specs = cls.get_model_specs(provider, model)
        
        input_rate = specs["input_cost_1m"] / 1_000_000
        output_rate = specs["output_cost_1m"] / 1_000_000

        # Cache hit local bypass: saves 100% cost
        if cache_hit:
            baseline_cost = (input_tokens * input_rate) + (output_tokens * output_rate)
            return {
                "cost": 0.0,
                "savings": baseline_cost
            }

        # Pricing with optimization
        actual_input_tokens = input_tokens
        input_savings = 0.0

        # Native prompt caching savings
        # Typically, cache read tokens are discounted by 50% to 90% depending on provider.
        # We assume a standard 50% discount on cached tokens.
        if cached_tokens > 0:
            cached_rate = input_rate * 0.5
            input_savings = cached_tokens * (input_rate - cached_rate)
            # Subtract cached tokens from normal pricing rate
            normal_tokens = max(0, input_tokens - cached_tokens)
            input_cost = (normal_tokens * input_rate) + (cached_tokens * cached_rate)
        else:
            input_cost = input_tokens * input_rate

        total_cost = input_cost + (output_tokens * output_rate)
        
        # Native batch discount (50% off total cost)
        batch_savings = 0.0
        if is_batch:
            batch_savings = total_cost * 0.5
            total_cost = total_cost * 0.5

        return {
            "cost": total_cost,
            "savings": input_savings + batch_savings
        }
