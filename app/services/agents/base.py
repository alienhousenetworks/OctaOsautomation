from sqlalchemy.orm import Session
from app.services.llm_gateway import LLMGateway
from app.models.agents import KnowledgeDocument, ActivityLog
from app.services.memory_service import MemoryService
from app.services.learning_loop import LearningLoop
from typing import Dict, Any, Tuple

class BaseAgent:
    def __init__(self, db: Session, tenant_id: str, agent_name: str, department: str = "general"):
        self.db = db
        self.tenant_id = tenant_id
        self.agent_name = agent_name
        self.department = department
        self.llm = LLMGateway(db, tenant_id)
        self.memory = MemoryService(db, tenant_id)
        self.learning_loop = LearningLoop(db, tenant_id)

    def log_activity(self, action: str, description: str, status: str = "success"):
        log = ActivityLog(
            tenant_id=self.tenant_id,
            agent_name=self.agent_name,
            action=action,
            description=description,
            status=status
        )
        self.db.add(log)
        self.db.commit()

    def get_knowledge_context(self, task_type: str = "general_task", department: str = None) -> str:
        from app.services.rag.hybrid_engine import HybridRAGEngine

        # 1. Pinned Directives & Brand Guidelines (Always included)
        query = self.db.query(KnowledgeDocument).filter(
            KnowledgeDocument.tenant_id == self.tenant_id,
            KnowledgeDocument.is_active == True,
            KnowledgeDocument.doc_type.in_(["Prompt Directives", "Brand Guidelines"])
        )
        if department:
            query = query.filter(KnowledgeDocument.department.in_([department, "General"]))
        pinned_docs = query.all()

        # 2. Targeted semantic retrieval for the specific task
        rag_engine = HybridRAGEngine(self.db, self.tenant_id)
        rag_hits = rag_engine.retrieve(task_type, department=department or self.department, top_k=4)

        # Augment with Global Rules from Memory Layer
        global_rules = self.memory.get_global_rules(category=department or self.department)
        
        context = (
            "Company Guidelines & Knowledge Base:\n"
            "CRITICAL INSTRUCTION: You must strictly adhere to the company guidelines, brand rules, "
            "contact details (e.g. email, phone), and websites listed below. Incorporate them "
            "into your generated output (social posts, emails, replies, etc.) whenever relevant.\n\n"
        )
        
        for doc in pinned_docs:
            context += f"- [{doc.doc_type}]: {doc.content}\n"

        if rag_hits:
            context += "\nRelevant Knowledge Base Extracts:\n"
            for h in rag_hits:
                context += f"- {h['citation']}: {h['content']}\n"
            
        context += "\nLearned Rules (Highest Priority):\n"
        for rule in global_rules:
            context += f"- {rule.rule_name}: {rule.content}\n"
            
        # Add Learning Loop Strategy Context
        strategy_context = self.learning_loop.get_strategy_context(self.agent_name, task_type)
        context += f"\n{strategy_context}\n"
            
        return context

    def log_decision(self, task_type: str, strategy_used: str, prompt_version: str, confidence_score: float, context_features: dict) -> str:
        """
        Logs a decision record to the Learning Loop for future outcome tracking.
        """
        return self.learning_loop.record_decision(
            agent_name=self.agent_name,
            task_type=task_type,
            strategy_used=strategy_used,
            prompt_version=prompt_version,
            confidence_score=confidence_score,
            context_features=context_features
        )

    async def evaluate_output_confidence(self, prompt: str, generated_output: str) -> Tuple[bool, float, str]:
        """
        Self-Review Layer: Evaluates the generated output against global rules.
        Returns (is_approved, confidence_score, feedback_reason).
        """
        import json
        
        eval_prompt = f"""
        You are a Manager QA bot. Evaluate the following generated output against these criteria:
        1. Does it sound like a generic AI or a human employee?
        2. Does it violate any obvious company policies or formatting rules?
        3. Is it accurate to the provided prompt context?
        
        Prompt context: {prompt}
        Generated Output: {generated_output}
        
        Respond ONLY with a JSON object: {{"confidence_score": <0-100>, "is_approved": <boolean, true if >= 80>, "reason": "<short reason>"}}
        """
        
        try:
            result_str = await self.llm.complete(eval_prompt)
            # Clean up the output in case the LLM wrapped it in markdown code blocks
            cleaned = result_str.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            parsed = json.loads(cleaned)
            confidence_score = float(parsed.get("confidence_score", 0.0))
            is_approved = bool(parsed.get("is_approved", confidence_score >= 80.0))
            reason = str(parsed.get("reason", "Evaluation complete."))
            return is_approved, confidence_score, reason
        except Exception as e:
            import logging
            logging.error(f"Failed to evaluate output confidence: {e}")
            return False, 0.0, f"Evaluation failed: {str(e)}"
