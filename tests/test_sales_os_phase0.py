"""Tests for Phase 0: Groundedness Evaluation, 3-Point Suppression, and Deal Room models."""
import pytest
from app.services.sales_os.evals.groundedness import GroundednessEvaluator
from app.models.deal_room import DealRoom, BuyingCommitteeMember, AccountSignal, SuppressionRecord


def test_groundedness_evaluator_valid_claims():
    evaluator = GroundednessEvaluator(min_confidence=0.85)
    
    evidence = [
        {
            "claim": "OctaOS automates enterprise outreach and lead scoring with 99% uptime.",
            "source": "product_spec_v2.pdf",
            "confidence": 0.95
        },
        {
            "claim": "Target company Acme Corp closed a $15M Series B funding round in September 2026.",
            "source": "crunchbase_signal",
            "confidence": 0.92
        }
    ]
    
    generated_text = (
        "Congratulations on Acme Corp's recent $15M Series B funding round. "
        "OctaOS automates enterprise outreach and lead scoring with verified high reliability. "
        "Let me know if you are open for a brief conversation."
    )
    
    report = evaluator.evaluate(generated_text, evidence, strict_mode=False)
    assert report.grounded_claims >= 1
    assert report.groundedness_score >= 0.5


def test_groundedness_evaluator_catches_hallucinations():
    evaluator = GroundednessEvaluator(min_confidence=0.85)
    
    evidence = [
        {
            "claim": "Acme Corp is an eCommerce apparel brand founded in 2021.",
            "source": "company_about.html",
            "confidence": 0.90
        }
    ]
    
    # Fabricated claims about struggle and cloud migration
    generated_text = (
        "I noticed Acme Corp is struggling with high customer acquisition costs. "
        "Your recent migration to Google Cloud has caused severe latency issues across your platform."
    )
    
    report = evaluator.evaluate(generated_text, evidence, strict_mode=True)
    assert not report.is_fully_grounded
    assert len(report.ungrounded_claims) >= 1


def test_deal_room_model_instantiation():
    room = DealRoom(
        tenant_id="tenant_123",
        company_name="Acme Corp",
        domain="acme.com",
        stage="qualified",
        icp_fit_score=0.88,
        timing_score=0.75,
        priority_index=0.66,
        calibrated_win_prob=0.32,
        is_multi_threaded=True,
        committee_coverage=0.60
    )
    assert room.company_name == "Acme Corp"
    assert room.domain == "acme.com"
    assert room.priority_index == 0.66
    assert room.is_multi_threaded is True


def test_buying_committee_member_instantiation():
    member = BuyingCommitteeMember(
        deal_room_id="room_123",
        tenant_id="tenant_123",
        name="Sarah Connor",
        email="sconnor@acme.com",
        title="Chief Revenue Officer",
        role_type="economic_buyer",
        engagement_state="uncontacted",
        provenance={"source": "apollo", "confidence": 0.98}
    )
    assert member.name == "Sarah Connor"
    assert member.role_type == "economic_buyer"
    assert member.provenance["confidence"] == 0.98
