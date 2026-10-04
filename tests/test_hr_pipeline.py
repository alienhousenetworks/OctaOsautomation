import pytest
from app.services.hr.resume_parser import (
    extract_heuristic_entities,
    calculate_ats_keyword_score,
    compute_composite_ranking,
)
from app.services.hr.contract_service import (
    get_available_templates,
    render_contract_document,
    generate_offer_email_content,
)

SAMPLE_RESUME_TEXT = """
Sarah Jenkins
San Francisco, CA | sarah.jenkins@example.com | (555) 987-6543
LinkedIn: linkedin.com/in/sarahjenkins-dev | GitHub: github.com/sarah-j

PROFESSIONAL SUMMARY
Results-driven Senior Full Stack Software Engineer with 6+ years of experience designing, building, and deploying scalable distributed web applications.

TECHNICAL SKILLS
- Languages: Python, JavaScript, TypeScript, SQL
- Frontend: React, Next.js, TailwindCSS, Redux
- Backend: FastAPI, Node.js, Express, PostgreSQL, Redis
- Cloud & DevOps: Docker, AWS, CI/CD, Git, Microservices

WORK EXPERIENCE
Senior Software Engineer | TechForward Inc. | 2021 – Present
- Architected microservices with FastAPI and PostgreSQL handling 5M daily requests.
- Developed real-time collaborative UI using Next.js, React, and WebSockets.

Software Engineer | CloudScale Labs | 2018 – 2021
- Built Python data pipelines and RESTful APIs.

EDUCATION
Bachelor of Science in Computer Science (B.S.) | University of California, Berkeley
"""

def test_heuristic_entity_extraction():
    entities = extract_heuristic_entities(SAMPLE_RESUME_TEXT, filename="Sarah_Jenkins_Resume.pdf")
    assert entities["name"] == "Sarah Jenkins"
    assert entities["email"] == "sarah.jenkins@example.com"
    assert "(555) 987-6543" in entities["phone"]
    assert "linkedin.com/in/sarahjenkins-dev" in entities["linkedin"]
    assert "github.com/sarah-j" in entities["github"]
    assert entities["experience_years"] >= 6
    assert "Python" in entities["skills"]
    assert "React" in entities["skills"]
    assert "FastAPI" in entities["skills"]
    assert "PostgreSQL" in entities["skills"]
    assert "B.S." in entities["education"] or "Bachelor" in entities["education"]

def test_ats_keyword_scoring():
    skills = ["Python", "FastAPI", "React", "PostgreSQL", "Docker", "AWS"]
    requirements = "We require strong expertise in Python, FastAPI, React, PostgreSQL, Docker, and Kubernetes."
    role = "Senior Full Stack Engineer"
    
    res = calculate_ats_keyword_score(skills, SAMPLE_RESUME_TEXT, requirements, role)
    assert res["ats_score"] >= 75
    assert "Python" in res["matched_skills"]
    assert "FastAPI" in res["matched_skills"]
    assert "Docker" in res["matched_skills"]
    assert "Kubernetes" in res["missing_skills"]

def test_composite_ranking():
    candidates = [
        {"name": "Alice", "ats_score": 90, "semantic_score": 85, "experience_years": 7},
        {"name": "Bob", "ats_score": 60, "semantic_score": 65, "experience_years": 2},
        {"name": "Charlie", "ats_score": 80, "semantic_score": 80, "experience_years": 4},
    ]
    ranked = compute_composite_ranking(candidates)
    assert ranked[0]["name"] == "Alice"
    assert ranked[0]["rank"] == 1
    assert ranked[1]["name"] == "Charlie"
    assert ranked[1]["rank"] == 2
    assert ranked[2]["name"] == "Bob"
    assert ranked[2]["rank"] == 3

def test_contract_templates_and_rendering():
    templates = get_available_templates()
    assert len(templates) >= 4
    template_ids = [t["id"] for t in templates]
    assert "full_time_standard" in template_ids
    assert "contractor_freelance" in template_ids
    assert "internship_offer" in template_ids
    assert "executive_senior" in template_ids

    doc = render_contract_document("full_time_standard", {
        "candidate_name": "Sarah Jenkins",
        "job_title": "Staff Engineer",
        "salary_amount": "175,000",
        "salary_currency": "USD",
        "start_date": "November 1, 2026",
        "work_mode": "Remote",
    })
    assert "Sarah Jenkins" in doc["plain_text"]
    assert "Staff Engineer" in doc["plain_text"]
    assert "175,000" in doc["plain_text"]
    assert "Remote" in doc["plain_text"]
    assert "<!DOCTYPE html>" in doc["html"]
    assert "EMPLOYMENT AGREEMENT" in doc["html"]

def test_offer_email_content_generator():
    subject, body = generate_offer_email_content(
        candidate_name="Sarah Jenkins",
        job_title="Staff Engineer",
        company_name="Acme Corp",
        start_date="November 1, 2026",
        salary_amount="175,000",
        salary_currency="USD"
    )
    assert "Offer of Employment: Staff Engineer at Acme Corp" in subject
    assert "Sarah Jenkins" in body
    assert "175,000" in body
