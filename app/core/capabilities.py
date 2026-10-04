from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class CapabilityCost(BaseModel):
    type: str # 'flat', 'per_unit'
    amount: float
    unit_field: Optional[str] = None

class CapabilityDefinition(BaseModel):
    id: str
    version: str = "1.0.0"
    department: str
    description: str
    side_effect_class: str # 'R0_INFORMATIONAL', 'R1_INTERNAL_REVERSIBLE', 'R2_EXTERNAL_REVERSIBLE', 'R3_EXTERNAL_IRREVERSIBLE', 'R4_FINANCIAL_CRITICAL'
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    required_permissions: list[str] = []
    cost_model: CapabilityCost
    default_autonomy: str = "L1"
    max_autonomy: str = "L2"
    dry_run_supported: bool = True
    idempotent: bool = True
    is_compensable: bool = False
    compensation_capability_id: Optional[str] = None


class BaseCapability(ABC):
    @property
    @abstractmethod
    def definition(self) -> CapabilityDefinition:
        """Returns the formal capability metadata, schema, and safety contract."""
        pass

    @abstractmethod
    async def dry_run(self, tenant_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Calculates expected effects, token cost, API calls, and risks without performing mutations."""
        pass

    @abstractmethod
    async def execute(self, tenant_id: str, inputs: Dict[str, Any], idempotency_key: str) -> Dict[str, Any]:
        """Executes the actual side effect idempotently."""
        pass

    @abstractmethod
    async def compensate(self, tenant_id: str, original_inputs: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        """Rolls back or compensates for the completed side effect if the DAG subsequently aborts."""
        pass


class SendSalesSequenceCapability(BaseCapability):
    """
    R3 External Irreversible capability for outbound email sequence dispatch.
    """
    @property
    def definition(self) -> CapabilityDefinition:
        return CapabilityDefinition(
            id="sales.send_sequence",
            version="1.0.0",
            department="Sales",
            description="Dispatches a personalized email sequence to qualified leads via configured SMTP/outreach provider.",
            side_effect_class="R3_EXTERNAL_IRREVERSIBLE",
            input_schema={
                "type": "object",
                "required": ["lead_ids", "template_id", "channel"],
                "properties": {
                    "lead_ids": {"type": "array", "items": {"type": "string"}},
                    "template_id": {"type": "string"},
                    "channel": {"type": "string", "enum": ["smtp", "sendgrid"]}
                }
            },
            output_schema={
                "type": "object",
                "required": ["dispatched_count", "message_ids"],
                "properties": {
                    "dispatched_count": {"type": "integer"},
                    "message_ids": {"type": "array", "items": {"type": "string"}}
                }
            },
            required_permissions=["outreach.send"],
            cost_model=CapabilityCost(type="per_unit", amount=0.05, unit_field="lead_ids"),
            default_autonomy="L1",
            max_autonomy="L2",
            dry_run_supported=True,
            idempotent=True,
            is_compensable=False, # External emails cannot be un-sent
            compensation_capability_id=None
        )

    async def dry_run(self, tenant_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        leads = inputs.get("lead_ids", [])
        count = len(leads)
        cost = count * 0.05
        return {
            "would_dispatch_count": count,
            "channel": inputs.get("channel", "smtp"),
            "estimated_spend": cost,
            "requires_approval": True,
            "risk_warning": "Dispatches external irreversible communications to recipients."
        }

    async def execute(self, tenant_id: str, inputs: Dict[str, Any], idempotency_key: str) -> Dict[str, Any]:
        leads = inputs.get("lead_ids", [])
        # Simulated or actual dispatch
        message_ids = [f"msg-{idempotency_key[:8]}-{idx}" for idx in range(len(leads))]
        return {
            "dispatched_count": len(leads),
            "message_ids": message_ids,
            "status": "success",
            "idempotency_key": idempotency_key
        }

    async def compensate(self, tenant_id: str, original_inputs: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        # Sent emails cannot be rolled back
        return {
            "status": "COMPENSATION_NOT_SUPPORTED",
            "message": "Sent emails are irreversible. Sequence paused for future touches."
        }


class TagContactCapability(BaseCapability):
    """
    R1 Internal Reversible capability for tagging contacts.
    """
    @property
    def definition(self) -> CapabilityDefinition:
        return CapabilityDefinition(
            id="crm.tag_contact",
            version="1.0.0",
            department="CRM",
            description="Applies tags to internal contact records.",
            side_effect_class="R1_INTERNAL_REVERSIBLE",
            input_schema={
                "type": "object",
                "required": ["contact_id", "tag"],
                "properties": {
                    "contact_id": {"type": "string"},
                    "tag": {"type": "string"}
                }
            },
            output_schema={
                "type": "object",
                "required": ["status"],
                "properties": {
                    "status": {"type": "string"}
                }
            },
            required_permissions=["crm.write"],
            cost_model=CapabilityCost(type="flat", amount=0.0),
            default_autonomy="L2",
            max_autonomy="L3",
            dry_run_supported=True,
            idempotent=True,
            is_compensable=True
        )

    async def dry_run(self, tenant_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {"would_tag": inputs.get("tag"), "contact_id": inputs.get("contact_id")}

    async def execute(self, tenant_id: str, inputs: Dict[str, Any], idempotency_key: str) -> Dict[str, Any]:
        return {"status": "TAGGED", "contact_id": inputs.get("contact_id"), "tag": inputs.get("tag")}

    async def compensate(self, tenant_id: str, original_inputs: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "TAG_REMOVED", "contact_id": original_inputs.get("contact_id"), "tag": original_inputs.get("tag")}


# In-memory registry singleton for runtime capability lookup
_REGISTRY: Dict[str, BaseCapability] = {}

def register_capability(capability: BaseCapability):
    key = f"{capability.definition.id}:{capability.definition.version}"
    _REGISTRY[key] = capability

def get_capability_instance(capability_id: str, version: str = "1.0.0") -> BaseCapability:
    key = f"{capability_id}:{version}"
    if key not in _REGISTRY:
        raise KeyError(f"Capability '{key}' not registered in Capability Registry.")
    return _REGISTRY[key]

# Auto-register Phase 0 & Phase 1 capabilities
register_capability(SendSalesSequenceCapability())
register_capability(TagContactCapability())
