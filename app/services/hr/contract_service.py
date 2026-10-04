import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

CONTRACT_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "full_time_standard": {
        "id": "full_time_standard",
        "name": "Standard Full-Time Employment Agreement",
        "description": "Comprehensive contract for permanent full-time employees including probation, compensation, benefits, and confidentiality.",
        "default_employment_type": "Full-Time Permanent",
        "default_probation_months": "3",
        "default_notice_period_days": "30",
        "content_template": """
# EMPLOYMENT AGREEMENT

This Employment Agreement ("Agreement") is entered into on **{{current_date}}**, by and between:

**Employer:** {{company_name}}, having its principal office at {{company_address}} ("Company").
**Employee:** {{candidate_name}}, residing at {{candidate_address}} ("Employee").

---

### 1. Position and Duties
The Company hereby employs the Employee in the position of **{{job_title}}** within the **{{department}}** department. The Employee will report directly to **{{reporting_manager}}** or such other person as the Company may designate. The Employee agrees to perform the duties and responsibilities associated with this role diligently and in good faith.

### 2. Employment Type and Commencement Date
This is a **{{employment_type}}** position. The Employee's employment will commence on **{{start_date}}** ("Commencement Date").

### 3. Place of Work & Work Mode
The Employee's work mode shall be **{{work_mode}}**. If working remotely, the Employee agrees to maintain a secure and professional home working environment.

### 4. Compensation and Benefits
- **Base Remuneration:** The Employee shall receive an annual base salary of **{{salary_currency}} {{salary_amount}}**, payable in monthly installments in accordance with the Company’s normal payroll schedule.
- **Benefits:** {{benefits_summary}}
- **Equity / Stock Options:** {{stock_options}}

### 5. Probationary Period
The Employee’s first **{{probation_months}} months** of employment shall be a probationary period. During this period, both parties may evaluate mutual suitability.

### 6. Notice Period & Termination
Following the probationary period, either party may terminate this employment agreement by providing **{{notice_period_days}} days** written notice, or pay in lieu thereof.

### 7. Confidentiality and Intellectual Property
The Employee acknowledges that during employment, they will have access to confidential Company information and proprietary trade secrets. All inventions, code, software, documentation, and works created by the Employee in connection with their employment shall belong solely and exclusively to the Company.

---

### ACCEPTANCE & SIGNATURES

IN WITNESS WHEREOF, the parties hereto have executed this Agreement as of the date first above written.

**For the Company:**
Signature: __________________________
Name: **{{signatory_name}}**
Title: **{{signatory_title}}**, {{company_name}}
Date: {{current_date}}

**Employee Acceptance:**
Signature: __________________________
Name: **{{candidate_name}}**
Email: {{candidate_email}}
Date: __________________________
"""
    },
    "contractor_freelance": {
        "id": "contractor_freelance",
        "name": "Independent Contractor / Consulting Agreement",
        "description": "Specialized contract for external contractors, freelancers, and independent technical consultants.",
        "default_employment_type": "Independent Contractor",
        "default_probation_months": "0",
        "default_notice_period_days": "14",
        "content_template": """
# INDEPENDENT CONTRACTOR AGREEMENT

This Independent Contractor Agreement ("Agreement") is made effective as of **{{current_date}}**, by and between:

**Client:** {{company_name}}, located at {{company_address}} ("Company").
**Contractor:** {{candidate_name}}, residing at {{candidate_address}} ("Contractor").

---

### 1. Scope of Services
The Company engages the Contractor to render specialized consulting and technical services as a **{{job_title}}** in support of the **{{department}}** initiatives.

### 2. Term & Engagement
The Contractor's engagement shall begin on **{{start_date}}** and continue until terminated in accordance with this Agreement. The work mode is **{{work_mode}}**.

### 3. Compensation & Invoicing
- **Consulting Fee:** The Company shall compensate the Contractor at the agreed rate of **{{salary_currency}} {{salary_amount}}** per month / milestone.
- **Invoicing:** Invoices shall be submitted monthly and paid within 15 business days of approval.

### 4. Independent Contractor Status
The Contractor is an independent contractor, not an employee, agent, or partner of the Company. The Contractor is solely responsible for all taxes, insurance, and statutory withholdings.

### 5. Intellectual Property & Deliverables
All deliverables, software code, designs, and documentation developed by the Contractor under this Agreement are deemed "work made for hire" and shall be the exclusive property of the Company.

### 6. Termination
Either party may terminate this Agreement at any time with **{{notice_period_days}} days** prior written notice.

---

### SIGNATURES

**For {{company_name}}:**
Signature: __________________________
Name: **{{signatory_name}}**
Title: **{{signatory_title}}**
Date: {{current_date}}

**Contractor:**
Signature: __________________________
Name: **{{candidate_name}}**
Date: __________________________
"""
    },
    "internship_offer": {
        "id": "internship_offer",
        "name": "Internship Offer & Training Agreement",
        "description": "Tailored offer letter for students, trainees, and engineering interns with educational deliverables.",
        "default_employment_type": "Internship",
        "default_probation_months": "1",
        "default_notice_period_days": "7",
        "content_template": """
# INTERNSHIP OFFER LETTER

Date: **{{current_date}}**

Dear **{{candidate_name}}**,

On behalf of **{{company_name}}**, we are thrilled to offer you an internship position as **{{job_title}}** in our **{{department}}** team!

### 1. Internship Details
- **Role:** {{job_title}}
- **Internship Start Date:** {{start_date}}
- **Work Mode:** {{work_mode}}
- **Reporting Mentor:** {{reporting_manager}}

### 2. Stipend & Perks
- **Monthly Stipend:** {{salary_currency}} {{salary_amount}} per month.
- **Perks:** Mentorship from senior engineering staff, real-world production experience, and certificate of completion.

### 3. Expectations & Confidentiality
As an intern, you agree to abide by all Company policies and protect all proprietary knowledge and source code as strictly confidential.

We are excited to welcome you to our team!

---

Sincerely,

**{{signatory_name}}**
{{signatory_title}}, {{company_name}}

**Candidate Acceptance:**
I accept the internship offer described above:

Signature: __________________________
Name: **{{candidate_name}}**
Date: __________________________
"""
    },
    "executive_senior": {
        "id": "executive_senior",
        "name": "Executive & Senior Leadership Offer",
        "description": "Executive appointment contract with equity options, severance provisions, and leadership deliverables.",
        "default_employment_type": "Full-Time Executive",
        "default_probation_months": "6",
        "default_notice_period_days": "60",
        "content_template": """
# EXECUTIVE APPOINTMENT & EMPLOYMENT AGREEMENT

This Agreement is made on **{{current_date}}**, by and between **{{company_name}}** ("Company") and **{{candidate_name}}** ("Executive").

### 1. Executive Role & Mandate
The Company hereby appoints the Executive to serve as **{{job_title}}**, reporting directly to the Board of Directors or CEO.

### 2. Effective Date
This Executive Agreement becomes effective on **{{start_date}}**.

### 3. Total Compensation Package
- **Executive Base Salary:** {{salary_currency}} {{salary_amount}} annually.
- **Executive Incentive / Bonus:** Eligible for annual performance bonus up to 30% of base salary.
- **Equity Award:** {{stock_options}}
- **Executive Health & Wellness:** {{benefits_summary}}

### 4. Non-Compete & Non-Solicitation
During employment and for 12 months thereafter, the Executive shall not engage in competing ventures or solicit company clients/employees.

---

**For the Company:**
Signature: __________________________
Name: **{{signatory_name}}**
Title: **{{signatory_title}}**

**Executive Acceptance:**
Signature: __________________________
Name: **{{candidate_name}}**
Date: __________________________
"""
    }
}


def get_available_templates() -> List[Dict[str, Any]]:
    """Returns metadata for all available contract templates."""
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "description": t["description"],
            "default_employment_type": t.get("default_employment_type", "Full-Time"),
            "default_probation_months": t.get("default_probation_months", "3"),
            "default_notice_period_days": t.get("default_notice_period_days", "30"),
        }
        for t in CONTRACT_TEMPLATES.values()
    ]


def render_contract_document(template_id: str, custom_variables: Dict[str, Any]) -> Dict[str, Any]:
    """Renders a complete contract document with dynamic variables and print-ready HTML styling."""
    template = CONTRACT_TEMPLATES.get(template_id, CONTRACT_TEMPLATES["full_time_standard"])
    raw_markdown = template["content_template"]

    # Current date formatted
    today_str = datetime.now().strftime("%B %d, %Y")

    # Default variables
    merged_vars = {
        "current_date": today_str,
        "company_name": custom_variables.get("company_name") or "OctaOS Technologies Inc.",
        "company_address": custom_variables.get("company_address") or "100 Innovation Way, Suite 400, Tech Park",
        "candidate_name": custom_variables.get("candidate_name") or "Candidate Name",
        "candidate_email": custom_variables.get("candidate_email") or "candidate@example.com",
        "candidate_address": custom_variables.get("candidate_address") or "City, Country",
        "job_title": custom_variables.get("job_title") or custom_variables.get("role") or "Senior Software Engineer",
        "department": custom_variables.get("department") or "Engineering",
        "employment_type": custom_variables.get("employment_type") or template.get("default_employment_type", "Full-Time"),
        "start_date": custom_variables.get("start_date") or custom_variables.get("joining_date") or today_str,
        "salary_amount": custom_variables.get("salary_amount") or custom_variables.get("salary") or "120,000",
        "salary_currency": custom_variables.get("salary_currency") or "USD",
        "work_mode": custom_variables.get("work_mode") or "Remote (Global)",
        "reporting_manager": custom_variables.get("reporting_manager") or "VP of Engineering",
        "probation_months": str(custom_variables.get("probation_months") or template.get("default_probation_months", "3")),
        "notice_period_days": str(custom_variables.get("notice_period_days") or template.get("default_notice_period_days", "30")),
        "benefits_summary": custom_variables.get("benefits_summary") or "Comprehensive Medical, Dental, Vision health coverage, Unlimited PTO, and $2,000 annual learning stipend.",
        "stock_options": custom_variables.get("stock_options") or "Stock options vesting over 4 years with a 1-year standard cliff.",
        "signatory_name": custom_variables.get("signatory_name") or "Alex Vance",
        "signatory_title": custom_variables.get("signatory_title") or "Head of People & Operations",
    }

    # Perform placeholder substitution
    rendered_text = raw_markdown
    for key, val in merged_vars.items():
        rendered_text = rendered_text.replace(f"{{{{{key}}}}}", str(val))

    # Convert to high-end executive styled HTML
    html_body = _markdown_to_executive_html(rendered_text, merged_vars)

    return {
        "template_id": template_id,
        "template_name": template["name"],
        "variables": merged_vars,
        "plain_text": rendered_text,
        "html": html_body,
    }


def _markdown_to_executive_html(markdown_text: str, vars_dict: Dict[str, Any]) -> str:
    """Formats markdown into an executive, print-ready document layout with modern typography."""
    lines = markdown_text.strip().splitlines()
    body_elements = []

    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
        if line_str.startswith("# "):
            title = line_str[2:].strip()
            body_elements.append(f'<h1 style="color: #0f172a; font-size: 26px; font-weight: 800; border-bottom: 2px solid #e2e8f0; padding-bottom: 12px; margin-bottom: 24px; text-transform: uppercase; letter-spacing: 0.5px;">{title}</h1>')
        elif line_str.startswith("### "):
            heading = line_str[4:].strip()
            body_elements.append(f'<h3 style="color: #1e293b; font-size: 16px; font-weight: 700; margin-top: 20px; margin-bottom: 8px;">{heading}</h3>')
        elif line_str == "---":
            body_elements.append('<hr style="border: none; border-top: 1px solid #cbd5e1; margin: 24px 0;" />')
        elif line_str.startswith("- "):
            item = line_str[2:].strip()
            formatted_item = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", item)
            body_elements.append(f'<li style="color: #334155; font-size: 14px; margin-bottom: 6px; line-height: 1.6;">{formatted_item}</li>')
        else:
            formatted_p = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", line_str)
            body_elements.append(f'<p style="color: #334155; font-size: 14px; line-height: 1.7; margin-bottom: 14px;">{formatted_p}</p>')

    inner_html = "\n".join(body_elements)

    full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Offer Letter & Contract - {vars_dict.get('candidate_name')}</title>
<style>
  @media print {{
    body {{ background: #fff !important; padding: 0 !important; }}
    .no-print {{ display: none !important; }}
    .page-container {{ box-shadow: none !important; border: none !important; width: 100% !important; margin: 0 !important; }}
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background-color: #f8fafc;
    color: #1e293b;
    margin: 0;
    padding: 24px;
    display: flex;
    justify-content: center;
  }}
  .page-container {{
    background: #ffffff;
    max-width: 800px;
    width: 100%;
    padding: 48px 56px;
    border-radius: 8px;
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.02);
    border: 1px solid #e2e8f0;
  }}
  .corporate-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 3px solid #0284c7;
    padding-bottom: 18px;
    margin-bottom: 32px;
  }}
  .brand-logo {{
    font-size: 22px;
    font-weight: 900;
    color: #0284c7;
    letter-spacing: -0.5px;
  }}
  .brand-sub {{
    font-size: 11px;
    color: #64748b;
    text-transform: uppercase;
    font-weight: 600;
    letter-spacing: 1px;
  }}
</style>
</head>
<body>
<div class="page-container">
  <div class="corporate-header">
    <div>
      <div class="brand-logo">{vars_dict.get('company_name')}</div>
      <div class="brand-sub">People Operations & Talent Acquisition</div>
    </div>
    <div style="text-align: right; font-size: 12px; color: #64748b;">
      <div>{vars_dict.get('company_address')}</div>
      <div>Date: {vars_dict.get('current_date')}</div>
    </div>
  </div>

  {inner_html}
</div>
</body>
</html>"""
    return full_html


def generate_offer_email_content(candidate_name: str, job_title: str, company_name: str, start_date: str, salary_amount: str, salary_currency: str) -> Tuple[str, str]:
    """Generates a professional offer letter email subject and body."""
    subject = f"Offer of Employment: {job_title} at {company_name}"
    body = f"""Dear {candidate_name},

We are absolutely thrilled to extend an offer for the position of {job_title} with {company_name}!

Key Highlights of Your Offer:
- Position: {job_title}
- Start Date: {start_date}
- Compensation: {salary_currency} {salary_amount}
- Work Arrangement: Remote / Flexible

Please find your official Employment Agreement attached. To accept this offer, please review and reply to this email confirming your acceptance, or return a signed copy of the contract.

We were immensely impressed by your background, skills, and conversations with our team, and we look forward to achieving great things together!

Warm regards,

People Operations & HR Team
{company_name}
"""
    return subject, body
