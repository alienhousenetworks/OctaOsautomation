import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.learning import (
    StrategyPerformance,
    NegativePatternMemory,
    GlobalStrategyRegistry,
    GlobalFailurePattern,
    GlobalSkillPackage
)

class FederatedLearningService:
    """
    Privacy-Preserving Federated Learning & Anonymization Engine for OctaOS.
    Strips PII, database passwords, local file paths, and secret tokens before 
    aggregating strategy performance rewards and failure patterns into the Global Hub.
    """
    def __init__(self, db: Session):
        self.db = db

    def sanitize_telemetry(self, features_or_text: Any) -> Any:
        """
        Sanitizes input data to strip PII, secrets, emails, IP addresses, and local directory paths.
        """
        if isinstance(features_or_text, str):
            text = features_or_text
            # Strip emails
            text = re.sub(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[REDACTED_EMAIL]", text)
            # Strip IP addresses
            text = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[REDACTED_IP]", text)
            # Strip secret keys
            text = re.sub(r"(sk-[a-zA-Z0-9_-]{20,})", "[REDACTED_API_KEY]", text)
            # Strip local home paths
            text = re.sub(r"/(Users|home)/[a-zA-Z0-9_-]+", "/[REDACTED_USER_PATH]", text)
            return text
        elif isinstance(features_or_text, dict):
            sanitized = {}
            for k, v in features_or_text.items():
                if any(secret_key in k.lower() for secret_key in ["password", "secret", "token", "key", "auth"]):
                    sanitized[k] = "[REDACTED_SECRET]"
                else:
                    sanitized[k] = self.sanitize_telemetry(v)
            return sanitized
        elif isinstance(features_or_text, list):
            return [self.sanitize_telemetry(item) for item in features_or_text]
        return features_or_text

    def publish_local_strategy(self, agent_name: str, task_type: str, strategy_name: str, 
                               reward_score: float, success: bool) -> GlobalStrategyRegistry:
        """
        Publishes anonymized strategy performance to the Global Strategy Registry.
        """
        global_rec = self.db.query(GlobalStrategyRegistry).filter(
            GlobalStrategyRegistry.agent_name == agent_name,
            GlobalStrategyRegistry.task_type == task_type,
            GlobalStrategyRegistry.strategy_name == strategy_name
        ).first()

        if not global_rec:
            global_rec = GlobalStrategyRegistry(
                agent_name=agent_name,
                task_type=task_type,
                strategy_name=strategy_name,
                global_weighted_reward=reward_score,
                total_evaluations=1,
                global_success_rate=1.0 if success else 0.0
            )
            self.db.add(global_rec)
        else:
            # Update weighted average reward
            prev_total = global_rec.total_evaluations
            new_total = prev_total + 1
            global_rec.global_weighted_reward = (
                (global_rec.global_weighted_reward * prev_total) + reward_score
            ) / new_total
            global_rec.total_evaluations = new_total
            if success:
                global_rec.global_success_rate = (
                    (global_rec.global_success_rate * prev_total) + 1.0
                ) / new_total

        self.db.commit()
        return global_rec

    def publish_failure_signature(self, agent_name: str, task_type: str, failure_category: str, 
                                  raw_signature: str) -> GlobalFailurePattern:
        """
        Publishes anonymized failure pattern to the Global Failure Immune System.
        """
        clean_signature = self.sanitize_telemetry(raw_signature)
        pattern = self.db.query(GlobalFailurePattern).filter(
            GlobalFailurePattern.agent_name == agent_name,
            GlobalFailurePattern.task_type == task_type,
            GlobalFailurePattern.anonymized_pattern_signature == clean_signature
        ).first()

        if not pattern:
            pattern = GlobalFailurePattern(
                agent_name=agent_name,
                task_type=task_type,
                failure_category=failure_category,
                anonymized_pattern_signature=clean_signature,
                immunity_score=1.0
            )
            self.db.add(pattern)
        else:
            pattern.immunity_score += 0.5

        self.db.commit()
        return pattern

    def get_global_immunity_patterns(self, agent_name: str, task_type: str) -> List[str]:
        """
        Retrieves global immunity signatures for a given agent and task.
        """
        patterns = self.db.query(GlobalFailurePattern).filter(
            GlobalFailurePattern.agent_name == agent_name,
            GlobalFailurePattern.task_type == task_type
        ).order_by(GlobalFailurePattern.immunity_score.desc()).limit(5).all()

        return [p.anonymized_pattern_signature for p in patterns]
