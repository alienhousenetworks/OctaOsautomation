"""Groundedness and Compliance Gate Test Suite.

Workstream D:
- Verifies deterministic claim verification and NLI citation matching.
- Enforces 0 unsupported numeric claims gate.
- Verifies compliance rules engine catches prohibited guarantees.
"""
import pytest
from app.services.marketing.campaign_os.claim_verifier import ClaimVerifier
from app.services.marketing.campaign_os.compliance_engine import ComplianceRulesEngine


def test_verified_claims_pass_groundedness_gate():
    """Verify that copy with metrics matching approved evidence records passes."""
    approved_evidence = [
        {"claim": "OctaOS reduced operational cycle times by 25%.", "raw_snippet": "25% reduction"},
        {"claim": "Over 500 enterprise customers use the system.", "raw_snippet": "500 customers"},
    ]

    post_content = (
        "Enterprise operations demand precision. Teams using OctaOS experienced a 25% reduction "
        "in cycle times across their workflows. Today, over 500 customers rely on this architecture."
    )

    result = ClaimVerifier.verify_post_claims(post_content, approved_evidence)
    assert result.all_claims_grounded is True
    assert len(result.unsupported_claims) == 0
    assert result.citation_coverage_score == 1.0


def test_unsupported_numeric_claim_is_caught_and_rejected():
    """Critical Gate: Unsupported numeric metrics MUST be flagged and rejected."""
    approved_evidence = [
        {"claim": "OctaOS reduced operational cycle times by 25%.", "raw_snippet": "25% reduction"},
    ]

    # Hallucinated 99.9% uplift and $10M revenue
    post_content = (
        "OctaOS delivers a 25% reduction in cycle times, resulting in a 99.9% conversion uplift "
        "and over $10M in incremental profits in the first month."
    )

    result = ClaimVerifier.verify_post_claims(post_content, approved_evidence)
    assert result.all_claims_grounded is False
    assert len(result.unsupported_claims) >= 1
    assert any("99.9%" in u or "$10M" in u for u in result.unsupported_claims)
    assert result.citation_coverage_score < 1.0


def test_compliance_engine_flags_prohibited_guarantees():
    """Verify compliance engine catches deceptive guarantees and hyperbole."""
    bad_post = (
        "This revolutionary breakthrough offers a guaranteed 100% ROI within two weeks! "
        "It is a foolproof miracle solution for instant scale."
    )

    audit = ComplianceRulesEngine.audit_post(bad_post, platform="linkedin")
    assert audit.passed is False
    assert any("prohibited" in v.lower() for v in audit.violations)
    assert any("hyperbolic" in w.lower() for w in audit.warnings)


def test_compliance_engine_enforces_platform_limits():
    """Verify platform hashtag limits are checked."""
    too_many_tags = "Great insight on operations. " + " ".join([f"#tag{i}" for i in range(12)])
    audit = ComplianceRulesEngine.audit_post(too_many_tags, platform="linkedin")
    assert any("hashtag count" in w.lower() for w in audit.warnings)
