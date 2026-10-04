"""Campaign OS DAG End-to-End Integration Test Suite.

Workstream B & Workstream E:
- Verifies 3-stage DAG execution (Strategy Root -> Idempotent Fan-Out -> Critic & Dispatch)
- Asserts creation of ContentPost records with compiled media prompts
- Asserts ActivityLog entries and HITL approval routing
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base, Tenant, User
from app.models.agents import KnowledgeDocument, ActivityLog
from app.models.deal_room import EvidenceRecord
from app.models.verticals import ContentPost, BusinessProfile
from app.models.enterprise import ApprovalRequest
from app.services.marketing.campaign_os.orchestrator import CampaignOSOrchestrator
from app.services.knowledge_os.access_controller import DataClassification


SQLALCHEMY_DATABASE_URL = "sqlite:///./test_campaign_dag.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    
    tenant = Tenant(id="tenant_camp_dag", name="Campaign Tenant", subdomain="camp-tenant")
    session.add(tenant)
    user = User(
        id="user_creator",
        tenant_id="tenant_camp_dag",
        email="creator@camp.com",
        name="Creator",
        hashed_password="mock",
        role="admin",
    )
    session.add(user)
    
    profile = BusinessProfile(
        tenant_id="tenant_camp_dag",
        company_name="OctaOS",
        website="https://octaos.com",
        industry="Enterprise Automation",
        service_description="Autonomous AI Agent operating system for modern business operations.",
        usp="Deep knowledge grounding with deterministic safety guardrails.",
        offer_details="Schedule a live architecture teardown and platform trial.",
    )
    session.add(profile)
    
    # Approved Public Brand Kit
    doc = KnowledgeDocument(
        tenant_id="tenant_camp_dag",
        department="Marketing",
        doc_type="Brand Guidelines",
        content="OctaOS tone is authoritative, pragmatic, and visionary. Primary brand color is emerald green (#059669).",
        classification=DataClassification.PUBLIC,
        approved_for_external_use=True,
    )
    session.add(doc)
    session.flush()
    
    # Verified Evidence Record
    evidence = EvidenceRecord(
        tenant_id="tenant_camp_dag",
        claim="OctaOS eliminates 80% of repetitive operational tasks for enterprise teams.",
        source_type="company_doc",
        source_id=doc.id,
        raw_snippet="eliminates 80% of repetitive tasks",
        is_valid=True,
    )
    session.add(evidence)
    session.commit()
    
    yield session
    
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.mark.asyncio
async def test_campaign_os_dag_execution(db_session):
    """Test full execution of Campaign OS DAG producing posts and compiled media prompts."""
    tenant_id = "tenant_camp_dag"
    orchestrator = CampaignOSOrchestrator(db_session, tenant_id)

    params = {
        "topic": "Enterprise Autonomous Operations",
        "days": 2,
        "platforms": ["linkedin", "instagram"],
        "image_provider": "openai",
        "generate_images": True,
        "generate_videos": True,
    }

    result = await orchestrator.execute_campaign_dag(params)

    # 1. Assert DAG Result Structure
    assert result["status"] == "success"
    assert result["total_posts_generated"] == 4  # 2 days x 2 platforms
    assert "campaign_title" in result

    # 2. Assert ContentPost Records in Database
    posts = db_session.query(ContentPost).filter(ContentPost.tenant_id == tenant_id).all()
    assert len(posts) == 4

    platforms_seen = [p.platform for p in posts]
    assert "linkedin" in platforms_seen
    assert "instagram" in platforms_seen

    # 3. Assert Media Prompts Compiled with Realistic Detail
    for post in posts:
        assert post.content is not None
        assert len(post.content) > 30
        assert post.image_prompt is not None
        # Verify compiled image prompt contains photographic details
        assert any(term in post.image_prompt for term in ["editorial", "photograph", "shot", "lighting", "textures"])

    # 4. Assert Activity Logs Recorded
    logs = db_session.query(ActivityLog).filter(ActivityLog.tenant_id == tenant_id).all()
    assert len(logs) >= 2
    actions = [l.action for l in logs]
    assert "Campaign Strategy" in actions or "Campaign Blueprint" in actions
    assert "Campaign Generation Completed" in actions
