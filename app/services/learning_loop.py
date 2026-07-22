from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timezone
import random
import json

from app.models.learning import DecisionRecord, StrategyPerformance, NegativePatternMemory

class LearningLoop:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def get_strategy_context(self, agent_name: str, task_type: str) -> str:
        """
        Retrieves top strategies, implements exploration/exploitation split,
        and provides bottom failing strategies to avoid.
        """
        # Fetch strategies for this agent and task
        strategies = self.db.query(StrategyPerformance).filter(
            StrategyPerformance.tenant_id == self.tenant_id,
            StrategyPerformance.agent_name == agent_name,
            StrategyPerformance.task_type == task_type
        ).order_by(desc(StrategyPerformance.weighted_reward_score)).all()

        if not strategies:
            # Default to exploration if no historical data
            return (
                "## Strategy Context (Exploration Mode)\n"
                "No historical performance data available for this task. "
                "Default to an exploration strategy. Prioritize data collection and log uncertainty explicitly."
            )

        # Separate best and worst
        top_strategies = strategies[:3]
        bottom_strategies = strategies[-2:] if len(strategies) > 3 else []

        # Multi-Armed Bandit / epsilon-greedy selection (e.g. 80% exploit, 20% explore)
        epsilon = 0.20
        if random.random() < epsilon:
            # Exploration: pick a random strategy that isn't in the bottom 2
            safe_strategies = [s for s in strategies if s not in bottom_strategies]
            chosen_strategy = random.choice(safe_strategies).strategy_name if safe_strategies else top_strategies[0].strategy_name
            mode = "EXPLORATION"
        else:
            # Exploitation: pick the top strategy
            chosen_strategy = top_strategies[0].strategy_name
            mode = "EXPLOITATION"

        context_block = f"## Required Context Block (Mode: {mode})\n"
        context_block += "### Top 3 Strategies (By Reward Score):\n"
        for s in top_strategies:
            context_block += f"- {s.strategy_name} (Reward: {s.weighted_reward_score:.2f}, Trend: {s.recent_trend_score:.2f})\n"

        if bottom_strategies:
            context_block += "### Bottom Failing Strategies to AVOID:\n"
            for s in bottom_strategies:
                context_block += f"- {s.strategy_name} (Reward: {s.weighted_reward_score:.2f})\n"

        # Fetch negative patterns
        negative_patterns = self.db.query(NegativePatternMemory).filter(
            NegativePatternMemory.tenant_id == self.tenant_id,
            NegativePatternMemory.agent_name == agent_name,
            NegativePatternMemory.task_type == task_type
        ).limit(5).all()

        if negative_patterns:
            context_block += "### Failure Intelligence (Negative Patterns to Avoid):\n"
            for np in negative_patterns:
                context_block += f"- [{np.failure_reason_category}] {np.pattern_signature}\n"

        context_block += f"\n**Selected Strategy to execute:** {chosen_strategy}\n"
        
        return context_block

    def record_decision(self, agent_name: str, task_type: str, strategy_used: str, 
                        prompt_version: str, confidence_score: float, context_features: dict) -> str:
        """
        Logs a structured decision record. Returns the decision_id.
        """
        decision = DecisionRecord(
            tenant_id=self.tenant_id,
            agent_name=agent_name,
            task_type=task_type,
            strategy_used=strategy_used,
            prompt_version=prompt_version,
            confidence_score=confidence_score,
            context_features=context_features
        )
        self.db.add(decision)
        self.db.commit()
        return decision.id

    def record_outcome_and_update(self, decision_id: str, result_status: str, 
                                  behavioral_signals: dict, quality_score: float = None, 
                                  user_feedback_score: float = None):
        """
        Calculates unified reward and updates the StrategyPerformance table using EMA.
        """
        decision = self.db.query(DecisionRecord).filter(
            DecisionRecord.id == decision_id,
            DecisionRecord.tenant_id == self.tenant_id
        ).first()

        if not decision:
            raise ValueError(f"DecisionRecord with id {decision_id} not found.")

        # Update decision outcome
        decision.result_status = result_status
        decision.quality_score = quality_score
        decision.user_feedback_score = user_feedback_score
        decision.behavioral_signals = behavioral_signals
        decision.outcome_timestamp = datetime.now(timezone.utc)

        # 1. Compute Unified Reward Signal
        # Example mappings based on requirements
        reward = 0.0
        
        # Positive signals
        if behavioral_signals.get("conversion"):
            reward += 100.0
        if behavioral_signals.get("meeting_booked"):
            reward += 20.0
        if behavioral_signals.get("task_resolved"):
            reward += 15.0
        if behavioral_signals.get("reply_received"):
            reward += 10.0

        # Negative signals
        if behavioral_signals.get("unsubscribe"):
            reward -= 50.0
        if behavioral_signals.get("rejection_reason"):
            # severity based penalty, default to -20
            severity = behavioral_signals.get("rejection_severity", 20.0)
            reward -= severity
        if behavioral_signals.get("no_response"):
            reward -= 5.0 # small penalty decay

        # Include quality and feedback if available
        if quality_score is not None:
            reward += (quality_score / 10.0) # Scale down 0-100 to 0-10 impact
        if user_feedback_score is not None:
            reward += user_feedback_score

        # 2. Update Strategy Performance
        perf = self.db.query(StrategyPerformance).filter(
            StrategyPerformance.tenant_id == self.tenant_id,
            StrategyPerformance.agent_name == decision.agent_name,
            StrategyPerformance.task_type == decision.task_type,
            StrategyPerformance.strategy_name == decision.strategy_used
        ).first()

        if not perf:
            perf = StrategyPerformance(
                tenant_id=self.tenant_id,
                agent_name=decision.agent_name,
                task_type=decision.task_type,
                strategy_name=decision.strategy_used,
                success_count=0,
                failure_count=0,
                weighted_reward_score=0.0,
                rolling_success_rate=0.0,
                recent_trend_score=0.0
            )
            self.db.add(perf)

        is_success = result_status == "success"
        if is_success:
            perf.success_count += 1
        else:
            perf.failure_count += 1

        total_trials = perf.success_count + perf.failure_count
        perf.rolling_success_rate = perf.success_count / total_trials

        # Exponential Moving Average (EMA) Update Rule
        # new_value = alpha * new_observation + (1 - alpha) * old_value
        alpha = 0.15 # Learning rate
        old_reward = perf.weighted_reward_score
        
        perf.weighted_reward_score = (alpha * reward) + ((1 - alpha) * old_reward)
        
        # Recent trend (difference between current reward and moving average)
        perf.recent_trend_score = reward - old_reward

        self.db.commit()

        # Publish anonymized outcome telemetry to Global Federated Registry
        try:
            from app.services.federated_learning_service import FederatedLearningService
            fed_service = FederatedLearningService(self.db)
            fed_service.publish_local_strategy(
                agent_name=decision.agent_name,
                task_type=decision.task_type,
                strategy_name=decision.strategy_used,
                reward_score=perf.weighted_reward_score,
                success=is_success
            )
        except Exception as fe:
            import logging
            logging.warning(f"Federated learning strategy publish skipped: {fe}")

    def extract_negative_pattern(self, agent_name: str, task_type: str, failure_category: str, pattern: str):
        """
        Stores failure intelligence to avoid repeating mistakes locally and globally.
        """
        neg = NegativePatternMemory(
            tenant_id=self.tenant_id,
            agent_name=agent_name,
            task_type=task_type,
            failure_reason_category=failure_category,
            pattern_signature=pattern
        )
        self.db.add(neg)
        self.db.commit()

        # Publish to Global Failure Immune System
        try:
            from app.services.federated_learning_service import FederatedLearningService
            fed_service = FederatedLearningService(self.db)
            fed_service.publish_failure_signature(
                agent_name=agent_name,
                task_type=task_type,
                failure_category=failure_category,
                raw_signature=pattern
            )
        except Exception as fe:
            import logging
            logging.warning(f"Federated failure signature publish skipped: {fe}")

