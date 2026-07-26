from sqlalchemy import Column, String, Text, Integer, Float, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.models.base import Base

class LLMTrajectory(Base):
    __tablename__ = "llm_trajectories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(64), index=True, nullable=True)
    user_id = Column(String(64), index=True, nullable=True)
    session_id = Column(String(64), index=True, nullable=True)
    
    initial_user_prompt = Column(Text, nullable=False)
    system_instructions = Column(Text, nullable=True)
    domain_category = Column(String(64), index=True, default="general")
    
    # Execution Metrics
    total_tokens_used = Column(Integer, default=0)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_cost_usd = Column(Float, default=0.0)
    execution_time_ms = Column(Integer, default=0)
    
    # Quality & Training Annotations
    status = Column(String(32), default="PENDING")  # SUCCESS, FAILED, PARTIAL
    quality_score = Column(Float, nullable=True)  # 1.0 to 5.0 (Judge evaluated)
    eval_reasoning = Column(Text, nullable=True)
    is_usable_for_sft = Column(Boolean, default=False)
    user_accepted = Column(Boolean, default=True)  # Downstream feedback signal
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    steps = relationship("TrajectoryStep", back_populates="trajectory", cascade="all, delete-orphan")


class TrajectoryStep(Base):
    __tablename__ = "trajectory_steps"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trajectory_id = Column(String(36), ForeignKey("llm_trajectories.id"), index=True, nullable=False)
    step_number = Column(Integer, nullable=False)
    
    thought_process = Column(Text, nullable=True)  # Internal CoT / ReAct reasoning
    model_name = Column(String(64), nullable=False)
    
    prompt_payload = Column(JSON, nullable=False)
    response_payload = Column(JSON, nullable=False)
    
    tool_calls = Column(JSON, nullable=True)  # List of [{tool_name, args, output}]
    latency_ms = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    trajectory = relationship("LLMTrajectory", back_populates="steps")
