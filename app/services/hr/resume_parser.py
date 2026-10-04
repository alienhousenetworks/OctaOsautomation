import re
import io
import json
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Core tech & business skill dictionary for deterministic zero-cost heuristic matching
COMMON_SKILLS = [
    # Programming Languages
    "Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "Go", "Golang", "Rust", "Ruby", "PHP", "Swift", "Kotlin", "Scala", "SQL",
    # Frontend
    "React", "React.js", "Next.js", "Vue", "Vue.js", "Angular", "HTML", "HTML5", "CSS", "CSS3", "Tailwind", "TailwindCSS", "Redux", "GraphQL", "Sass", "Webpack", "Vite",
    # Backend & Frameworks
    "Node.js", "Express", "FastAPI", "Django", "Flask", "Spring Boot", "NestJS", "Ruby on Rails", "ASP.NET", "REST", "RESTful", "gRPC", "WebSockets", "Microservices",
    # Databases & Caching
    "PostgreSQL", "Postgres", "MySQL", "MongoDB", "Redis", "SQLite", "DynamoDB", "Cassandra", "Elasticsearch", "Prisma", "SQLAlchemy", "Firebase", "Supabase",
    # Cloud & DevOps
    "AWS", "Amazon Web Services", "Azure", "GCP", "Google Cloud", "Docker", "Kubernetes", "K8s", "CI/CD", "GitHub Actions", "Terraform", "Linux", "Nginx", "Ansible",
    # AI / ML & Data
    "Machine Learning", "Deep Learning", "NLP", "LLM", "Prompt Engineering", "PyTorch", "TensorFlow", "Pandas", "NumPy", "Scikit-Learn", "RAG", "LangChain", "OpenAI",
    # General Engineering & Soft Skills
    "System Design", "Agile", "Scrum", "Git", "Jira", "Unit Testing", "TDD", "Integration Testing", "Leadership", "Project Management", "Problem Solving", "Communication"
]

def extract_resume_text(filename: str, file_bytes: bytes) -> str:
    """Deterministically extracts clean text from PDF, DOCX, or text files locally at $0 cost."""
    lower_name = filename.lower()
    text = ""

    # 1. PDF via PyMuPDF (fitz) with fallback to pypdf
    if lower_name.endswith(".pdf") or file_bytes.startswith(b"%PDF"):
        try:
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            extracted = []
            for page in doc:
                page_text = page.get_text("text")
                if page_text:
                    extracted.append(page_text)
            text = "\n".join(extracted)
        except Exception as e:
            logger.warning(f"PyMuPDF failed on {filename}: {e}. Trying pypdf fallback.")
            try:
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                extracted = [page.extract_text() or "" for page in reader.pages]
                text = "\n".join(extracted)
            except Exception as e2:
                logger.error(f"All PDF extractors failed on {filename}: {e2}")

    # 2. Word DOCX via python-docx
    elif lower_name.endswith(".docx"):
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                    if row_text:
                        paragraphs.append(row_text)
            text = "\n".join(paragraphs)
        except Exception as e:
            logger.error(f"DOCX extraction failed on {filename}: {e}")

    # 3. Plain text / Markdown
    elif lower_name.endswith((".txt", ".md", ".json")):
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = file_bytes.decode("latin-1", errors="ignore")

    return text.strip()


def extract_heuristic_entities(text: str, filename: str = "") -> Dict[str, Any]:
    """Zero-cost regex and rule-based entity extraction (Name, Email, Phone, Links, Experience, Skills)."""
    # 1. Email extraction
    email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text)
    email = email_match.group(0) if email_match else ""

    # 2. Phone extraction
    phone_match = re.search(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b", text)
    phone = phone_match.group(0).strip() if phone_match else ""

    # 3. Links (LinkedIn, GitHub, Portfolio)
    linkedin_match = re.search(r"(?:https?:\/\/)?(?:www\.)?linkedin\.com\/in\/[a-zA-Z0-9_-]+", text)
    linkedin = linkedin_match.group(0) if linkedin_match else ""

    github_match = re.search(r"(?:https?:\/\/)?(?:www\.)?github\.com\/[a-zA-Z0-9_-]+", text)
    github = github_match.group(0) if github_match else ""

    # 4. Name extraction
    name = ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines:
        for line in lines[:5]:
            # Look for 2 to 4 capitalized words without special characters or numbers
            if 3 <= len(line) <= 40 and not any(char in line for char in ["@", "http", "www", "/", "\\", "{", "}"]):
                words = line.split()
                if 1 <= len(words) <= 4 and all(w[0].isupper() for w in words if w.isalpha()):
                    name = line
                    break

    # Fallback name from filename or email if not found in header
    if not name:
        clean_fn = re.sub(r"[-_]", " ", filename.rsplit(".", 1)[0])
        clean_fn = re.sub(r"(?i)(resume|cv|profile|doc)", "", clean_fn).strip()
        if clean_fn and len(clean_fn) > 2:
            name = clean_fn.title()
        elif email:
            name = email.split("@")[0].replace(".", " ").replace("_", " ").title()
        else:
            name = "Candidate"

    # 5. Detected Skills (Local keyword lookup)
    detected_skills = set()
    text_lower = f" {text.lower()} "
    for skill in COMMON_SKILLS:
        pattern = r"(?i)\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, text_lower):
            detected_skills.add(skill)

    # 6. Detected Years of Experience
    experience_years = 0
    exp_matches = re.findall(r"(\d{1,2})\+?\s*(?:years?|yrs?)\s*(?:of\s+)?experience", text, re.IGNORECASE)
    if exp_matches:
        try:
            experience_years = max(int(m) for m in exp_matches if int(m) <= 40)
        except:
            experience_years = 0
    
    if experience_years == 0:
        # Detect year ranges like 2018 - 2024
        year_ranges = re.findall(r"\b(20[0-2]\d|19[8-9]\d)\s*(?:-|–|—|to)\s*(20[0-2]\d|present|current)\b", text, re.IGNORECASE)
        if year_ranges:
            total_span = 0
            for start_yr, end_yr in year_ranges:
                try:
                    s = int(start_yr)
                    e = 2026 if end_yr.lower() in ("present", "current") else int(end_yr)
                    if 0 <= (e - s) <= 30:
                        total_span = max(total_span, e - s)
                except:
                    pass
            experience_years = total_span

    # 7. Education extraction
    education = "Not specified"
    edu_keywords = ["Ph.D", "PhD", "Doctorate", "Master", "M.Tech", "M.S.", "MS in", "Bachelor", "B.Tech", "B.S.", "BS in", "B.E.", "BCA", "MCA", "Diploma"]
    for edu in edu_keywords:
        if re.search(r"(?i)\b" + re.escape(edu) + r"\b", text):
            education = edu
            break

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "linkedin": linkedin,
        "github": github,
        "skills": sorted(list(detected_skills)),
        "experience_years": experience_years,
        "education": education,
    }


def calculate_ats_keyword_score(candidate_skills: List[str], candidate_text: str, requirements: str, role: str) -> Dict[str, Any]:
    """Computes transparent deterministic ATS Keyword match metrics at $0 cost."""
    req_combined = f"{role} {requirements}".lower()
    
    # Extract expected skill keywords from role requirements
    expected_skills = set()
    for skill in COMMON_SKILLS:
        if re.search(r"(?i)\b" + re.escape(skill.lower()) + r"\b", req_combined):
            expected_skills.add(skill)

    # Perform case-insensitive matching against candidate skills
    expected_skills_dict = {s.lower(): s for s in expected_skills}
    candidate_skills_dict = {s.lower(): s for s in candidate_skills}

    # Also check if any expected skill is present directly in candidate text
    cand_text_lower = f" {candidate_text.lower()} "
    for k, original_skill in expected_skills_dict.items():
        if k not in candidate_skills_dict:
            if re.search(r"(?i)\b" + re.escape(k) + r"\b", cand_text_lower):
                candidate_skills_dict[k] = original_skill

    matched_keys = set(expected_skills_dict.keys()).intersection(set(candidate_skills_dict.keys()))
    missing_keys = set(expected_skills_dict.keys()) - set(candidate_skills_dict.keys())

    matched_skills = sorted([expected_skills_dict[k] for k in matched_keys])
    missing_skills = sorted([expected_skills_dict[k] for k in missing_keys])

    if expected_skills:
        match_ratio = len(matched_skills) / len(expected_skills)
        score = int(min(100, max(20, round(match_ratio * 100))))
    else:
        # If no specific tech skills required, score based on general skill density
        score = min(85, max(45, len(candidate_skills) * 4))

    return {
        "ats_score": score,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "total_required_skills_found": len(expected_skills),
    }


async def evaluate_semantic_fit(
    llm_gateway: Any,
    condensed_profile: Dict[str, Any],
    role: str,
    requirements: str,
    provider: str = "auto",
    model: Optional[str] = None
) -> Dict[str, Any]:
    """Cost-effective condensed semantic evaluation using high-speed, cheap models (<500 tokens)."""
    # Build compact representation to save 95%+ of LLM tokens
    profile_payload = {
        "name": condensed_profile.get("name"),
        "role_applied": role,
        "detected_skills": condensed_profile.get("skills", [])[:20],
        "experience_years": condensed_profile.get("experience_years", 0),
        "education": condensed_profile.get("education", ""),
        "ats_matched_skills": condensed_profile.get("matched_skills", []),
        "ats_missing_skills": condensed_profile.get("missing_skills", []),
        "text_summary": condensed_profile.get("text_excerpt", "")[:1200]  # Only condensed first 1200 chars
    }

    prompt = f"""You are an elite corporate technical recruiter and ATS evaluation system.
Assess this candidate profile strictly against the Role and Requirements.

Target Role: {role}
Role Requirements: {requirements}

Candidate Summary:
{json.dumps(profile_payload, indent=2)}

Respond with ONLY a valid JSON object in this exact schema:
{{
  "semantic_score": <integer 0 to 100 indicating semantic suitability, domain fit, and career seniority>,
  "experience_summary": "<Concise 2-sentence summary of the candidate's career and main background>",
  "strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
  "gaps": ["<gap or red flag 1>", "<gap or red flag 2>"],
  "recommendation": "<Strong Hire | Recommended | Consider | Review Needed | Reject>",
  "fit_verdict": "<1-sentence hiring decision insight>"
}}"""

    try:
        # Route to fast/cheap models
        if provider == "auto" or not provider:
            req_provider = "gemini"
            req_model = "gemini-2.5-flash"
        else:
            req_provider = provider
            req_model = model

        response = await llm_gateway.complete(prompt=prompt, provider=req_provider, model=req_model)
        cleaned = response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        parsed = json.loads(cleaned.strip())
        return parsed
    except Exception as e:
        logger.warning(f"Semantic LLM evaluation fallback due to: {e}")
        # Deterministic fallback calculation
        ats_score = condensed_profile.get("ats_score", 60)
        return {
            "semantic_score": min(95, max(30, ats_score - 5 if condensed_profile.get("missing_skills") else ats_score + 5)),
            "experience_summary": f"{condensed_profile.get('name')} with approximately {condensed_profile.get('experience_years', 'several')} years of experience with skills in {', '.join(condensed_profile.get('skills', [])[:4])}.",
            "strengths": [f"Demonstrated skills in {', '.join(condensed_profile.get('matched_skills', ['Core capabilities'])[:3])}"],
            "gaps": [f"Missing direct match for {s}" for s in condensed_profile.get("missing_skills", [])[:2]] or ["Standard interview verification required"],
            "recommendation": "Recommended" if ats_score >= 70 else "Consider",
            "fit_verdict": "Candidate meets primary criteria based on heuristic ATS scorecard."
        }


def compute_composite_ranking(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Calculates composite match score and assigns rank #1, #2, #3... to candidates."""
    for c in candidates:
        ats = c.get("ats_score", 50)
        semantic = c.get("semantic_score", 50)
        # Weighted composite: 45% deterministic ATS keyword match + 55% semantic evaluation
        composite = int(round(ats * 0.45 + semantic * 0.55))
        c["composite_score"] = composite

    # Sort descending by composite score, then by experience years
    sorted_candidates = sorted(
        candidates, 
        key=lambda x: (x.get("composite_score", 0), x.get("experience_years", 0)), 
        reverse=True
    )

    for rank, cand in enumerate(sorted_candidates, start=1):
        cand["rank"] = rank

    return sorted_candidates
