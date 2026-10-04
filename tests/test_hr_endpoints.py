import io
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import deps
from app.models.base import Base, User, Tenant, APICredential
from app.models import verticals as models
from app.api.v1.endpoints.hr import router as hr_router

import os

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_hr.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all tables on engine
Base.metadata.create_all(bind=engine)
models.Candidate.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

def override_get_current_tenant_id():
    return "test-tenant-123"

def override_get_current_user():
    return User(
        id="test-user-123",
        email="hr@test.com",
        tenant_id="test-tenant-123",
        role="admin",
        is_active=True,
        is_system_admin=True
    )

# Setup clean test app
test_app = FastAPI()
test_app.dependency_overrides[deps.get_db] = override_get_db
test_app.dependency_overrides[deps.get_current_tenant_id] = override_get_current_tenant_id
test_app.dependency_overrides[deps.get_current_user] = override_get_current_user
test_app.include_router(hr_router, prefix="/api/v1/hr")

# Seed tenant and mock user if not present
db = TestingSessionLocal()
tenant = db.query(Tenant).filter_by(id="test-tenant-123").first()
if not tenant:
    tenant = Tenant(id="test-tenant-123", name="Test Corp")
    db.add(tenant)

user = db.query(User).filter_by(id="test-user-123").first()
if not user:
    user = User(
        id="test-user-123",
        email="hr@test.com",
        hashed_password="test_hashed_pw",
        tenant_id="test-tenant-123",
        role="admin",
        is_active=True,
        is_system_admin=True
    )
    db.add(user)

db.commit()
db.close()

client = TestClient(test_app)

def test_get_contract_templates():
    response = client.get("/api/v1/hr/contract-templates")
    assert response.status_code == 200
    templates = response.json()
    assert len(templates) >= 4
    template_ids = [t["id"] for t in templates]
    assert "full_time_standard" in template_ids
    assert "contractor_freelance" in template_ids
    assert "internship_offer" in template_ids
    assert "executive_senior" in template_ids

def test_batch_resume_upload_and_ranking():
    sample_resume = b"""
    David Miller
    david.miller@example.com | (555) 321-7654
    Senior Backend Software Engineer with 5+ years of experience in Python, FastAPI, Docker, and PostgreSQL.
    Education: B.S. in Computer Science
    """
    
    files = [
        ("files", ("David_Miller_Resume.txt", io.BytesIO(sample_resume), "text/plain"))
    ]
    data = {
        "role": "Senior Backend Engineer",
        "requirements": "Python, FastAPI, Docker, PostgreSQL, Kubernetes",
        "salary": "$140,000/year",
        "provider": "auto"
    }

    response = client.post("/api/v1/hr/resumes/upload-batch", files=files, data=data)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    assert res_data["processed_count"] == 1
    candidates = res_data["candidates"]
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand["name"] == "David Miller"
    assert cand["email"] == "david.miller@example.com"
    assert cand["scorecard"]["ats_score"] >= 60

def test_interview_email_dispatch():
    db = TestingSessionLocal()
    cand = models.Candidate(
        tenant_id="test-tenant-123",
        name="Elena Rostova",
        email="elena@example.com",
        role="Frontend Engineer",
        status="accepted",
        scorecard={"match_score": 85}
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)
    candidate_id = cand.id
    db.close()

    payload = {
        "interview_date": "2026-10-15",
        "interview_time": "2:00 PM",
        "round_name": "Technical Architecture",
        "meeting_link": "https://meet.google.com/test-meet",
        "interviewer_name": "Chief Architect",
        "custom_notes": "Please prepare a diagram of your recent project.",
        "channel": "smtp"
    }

    response = client.post(f"/api/v1/hr/{candidate_id}/send-interview-email", json=payload)
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["status"] == "success"
    assert res_json["candidate"]["status"] == "interviewed"
    assert res_json["candidate"]["scorecard"]["calendar_booked"] is True

def test_generate_offer_and_send_email():
    db = TestingSessionLocal()
    cand = models.Candidate(
        tenant_id="test-tenant-123",
        name="Marcus Vance",
        email="marcus@example.com",
        role="Staff AI Engineer",
        status="interviewed",
        scorecard={"match_score": 92}
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)
    candidate_id = cand.id
    db.close()

    # 1. Generate Offer Document Preview
    gen_payload = {
        "template_id": "full_time_standard",
        "variables": {
            "salary_amount": "180,000",
            "start_date": "December 1, 2026",
            "work_mode": "Remote (Global)"
        }
    }
    gen_res = client.post(f"/api/v1/hr/{candidate_id}/generate-offer", json=gen_payload)
    assert gen_res.status_code == 200
    doc = gen_res.json()["document"]
    assert "Marcus Vance" in doc["plain_text"]
    assert "180,000" in doc["plain_text"]
    assert "EMPLOYMENT AGREEMENT" in doc["html"]

    # 2. Dispatch Offer Email
    send_payload = {
        "template_id": "full_time_standard",
        "variables": {
            "salary_amount": "180,000",
            "start_date": "December 1, 2026",
            "work_mode": "Remote (Global)"
        },
        "channel": "smtp"
    }
    send_res = client.post(f"/api/v1/hr/{candidate_id}/send-offer-email", json=send_payload)
    assert send_res.status_code == 200
    send_json = send_res.json()
    assert send_json["status"] == "success"
    assert send_json["candidate"]["status"] == "offered"
    assert "offer_details" in send_json["candidate"]["scorecard"]
