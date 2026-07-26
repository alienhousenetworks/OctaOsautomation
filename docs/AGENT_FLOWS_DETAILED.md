# OctaOS — Detailed Agent Flows, Data Sources, Validation & Improvement

This companion to `FULL_APP_DOCUMENTATION.md` explains **how every agent actually works**, with flow diagrams, **where data comes from**, **how it is validated**, and **how the agent improves**.

Sales is covered in the most depth: user requirements → N leads → validation → customized email → meeting conversion.

---

## Shared brain: how every agent thinks

All department agents inherit `BaseAgent` (`app/services/agents/base.py`).

```text
┌─────────────────────────────────────────────────────────────────┐
│                         BaseAgent                                │
│  tenant_id + db + agent_name                                     │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │ LLMGateway   │  │ MemoryService│  │ LearningLoop          │ │
│  │ (models/keys)│  │ (global rules│  │ (strategy bandit +    │ │
│  │              │  │  USER rules) │  │  decision/outcomes)   │ │
│  └──────────────┘  └──────────────┘  └───────────────────────┘ │
│                                                                  │
│  get_knowledge_context()                                         │
│    = KnowledgeDocument (dept) + learned rules + strategy block   │
│                                                                  │
│  log_decision() → DecisionRecord                                 │
│  evaluate_output_confidence() → Manager QA JSON (0–100)          │
│  log_activity() → ActivityLog (UI timeline)                      │
└─────────────────────────────────────────────────────────────────┘
```

### Shared improvement loop (all agents)

```text
                    ┌──────────────────┐
                    │  Execute task    │
                    └────────┬─────────┘
                             │
              inject strategy context (ε-greedy)
              80% exploit best strategy / 20% explore
                             │
                             ▼
                    ┌──────────────────┐
                    │  LLM generation  │
                    └────────┬─────────┘
                             │
              optional evaluate_output_confidence
              (human-like? policy? accurate?)
                             │
                             ▼
                    ┌──────────────────┐
                    │ Deliver / store  │
                    └────────┬─────────┘
                             │
              real-world outcome arrives
              (meeting, reply, CSAT, engagement…)
                             │
                             ▼
              LearningLoop.record_outcome_and_update
              reward EMA (α=0.15) → StrategyPerformance
                             │
              federated publish (PII stripped)
                             │
                             ▼
              next run prefers high-reward strategies
              + avoids NegativePatternMemory
```

**Reward map used by the learning loop:**

| Signal | Reward |
|--------|--------|
| conversion | +100 |
| meeting_booked | +20 |
| task_resolved | +15 |
| reply_received | +10 |
| unsubscribe | −50 |
| rejection | −severity |
| no_response | −5 |
| quality_score | +quality/10 |
| user_feedback | +score |

---

# 1. Sales AI — end-to-end (deep dive)

**Class:** `SalesAgent` · `SalesService` · `SalesReplyHandler`  
**Files:** `app/services/agents/sales.py`, `app/services/sales/*`, `app/services/verticals/sales.py`

Sales has **two entry modes**:

| Mode | When | What |
|------|------|------|
| **A. One-shot actions** | Orchestrator / API | `generate_leads`, `sales_outreach`, `schedule_meeting` |
| **B. Sales AI V3** | Business Profile + “Run V3” | Full 10-step engine using **your ICP requirements** |

---

## 1.1 Where user requirements come from

### Mode B (V3) — primary product path

User fills **Business Profile** (tenant-scoped):

| Field | Used for |
|-------|----------|
| `company_name`, `website` | Brand voice, subject lines, “from” identity |
| `industry`, `service_description` | ICP generation |
| `target_countries` | Geography bias (via LLM prompts / provider filters) |
| `target_industries` | **Primary search query** for discovery |
| `target_budget_range` | Qualification gate |
| `usp`, `offer_details` | Pain-point mapping + email personalization |
| `extra_context` | Free-text user rules (“use apollo”, “only CTOs”, etc.) |

```text
┌─────────────────────┐
│  Business Profile   │  ← user requirements
│  (target industries,│
│   budget, USP, …)   │
└──────────┬──────────┘
           │
           ▼
    Step 1: Understand Service
           LLM → Ideal Customer Profile (ICP paragraph)
           (stored in v3_workflow_status steps)
```

### Mode A — Orchestrator / manual

User says e.g. *“Source 20 CTOs at AI startups in NYC via Apollo”*.

```text
Orchestrator plan JSON
  department: Sales
  action: generate_leads
  parameters: { provider, query, count }
           │
           ▼
    _generate_leads(params)
```

---

## 1.2 How Sales gets “that many” leads (count)

### Flow: count request → provider → DB rows

```text
                    count = N (user or V3 default ~50)
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Provider router (LLM or rules)                             │
│  • Local / brick-and-mortar → google_places or apify        │
│  • B2B corporate → apollo or hunter                         │
│  • Explicit “use X” in extra_context → that provider        │
│  • Fallback chain if primary returns 0                      │
└────────────────────────────┬────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
    Apollo mixed_people  Hunter discover    Google Places /
    per_page=N           + domain-search    Apify actors
         │                   │                   │
         └───────────────────┴───────────────────┘
                             │
                             ▼
              list of raw people/companies (≤ N)
                             │
                    STRICT VALIDATION
                    (many may be dropped)
                             │
                             ▼
              validated leads M ≤ N saved to Lead table
              (V3 only keeps name+real email rows)
```

**Important:** User asks for N leads → API is called with `per_page`/`count` = N, but **only validated rows become CRM leads**. If Apollo returns 20 but 8 have `***` names or generic emails, V3 may keep fewer than 20 (and will error if zero survive validation — no simulated leads).

### Apollo path (B2B people search)

```text
User query: "CTOs at early-stage AI startups in New York"
                    │
                    ▼
     LLM (Anthropic) converts query → Apollo JSON filters:
       person_titles, person_locations,
       organization_num_employees_ranges,
       contact_email_status: ["verified"]   ← always forced
       q_keywords, q_organization_domains
                    │
                    ▼
     POST apollo.io mixed_people/api_search
       page = random(1..5)   ← freshness
       per_page = count
                    │
                    ▼
     For each person:
       reject if first/last empty or "***" in name
       map name, email, company, website, phone
```

### Hunter path

```text
Query → LLM maps to Hunter Discover payload
  (industry filter from hunter_industries.json OR natural language)
        │
        ▼
  Discover companies → domains list (shuffled)
        │
        ▼
  For each domain until len(leads) >= count:
    domain-search type=personal limit=2
    take first personal email → lead
    (1 contact per domain → company diversity)
```

### Google Places / Apify (local)

```text
google_places: Text Search → company names (often no email)
apify: LLM routes actor
  • compass/crawler-google-places  (local)
  • apify/instagram-scraper        (D2C / influencers)
  • anchor/linkedin-profile-scraper (B2B social)
```

Local sources often lack emails → **waterfall enrichment** (next section).

---

## 1.3 Data sources (Sales)

| Source | Type | What it provides | When used |
|--------|------|------------------|-----------|
| **BusinessProfile** | User input | ICP, budget, USP, industries | All V3 steps |
| **Apollo** | External API | People, verified emails, org news/jobs | Discovery + deep context |
| **Hunter** | External API | Company domains + personal emails | Discovery + enrichment |
| **Google Places** | External API | Local businesses | Local queries |
| **Apify** | Scrapers | Places / IG / LinkedIn / website crawl | Flexible discovery |
| **ZoomInfo / Cognism / PDL / Clearbit / Crunchbase** | External | Alt discovery (if keys exist) | Optional providers |
| **SMTP / Gmail** | Send channel | Actual outbound email delivery | Day-1 outreach |
| **WhatsApp (Meta)** | Send channel | Fallback if email fails + phone exists | Step 8 |
| **Google Calendar** | Booking | freeBusy + Meet link | Meeting conversion |
| **Gmail poll / webhooks** | Inbound | Real prospect replies | Conversation AI |
| **Telegram** | Notify | Alerts to human sales owner | Replies / meetings |
| **Knowledge base** | Internal | Brand rules, pricing, case studies | Reply drafting |
| **Lead.data conversation** | Internal | Last 50 messages | Classification context |
| **LearningLoop strategies** | Internal | What messaging worked before | Future outreach |

---

## 1.4 How Sales **validates** data

### Stage A — Discovery strict filter (V3 Step 2)

```text
For each raw contact c:
  email missing?  OR  no "@"?  OR  starts with contact@/info@?
  OR name in {Manager, General Inquiry, Unknown}?
       │
       YES → needs_enrichment = true
       │
       ▼ Waterfall enrich via Hunter → Apollo → Apify (domain-based)
       │
  Final gate (BOTH required):
    has_name  = real person name (not Manager / General Inquiry)
    has_contact = real email (not contact@ / info@)
       │
  FAIL both → DISCARD (never saved)
  PASS → companies[]
```

If **zero** pass:

```text
Exception: "API returned leads, but after strict waterfall enrichment,
none had the mandatory real Name and Email. No simulated data is allowed."
+ dumps raw rejected JSON for debugging
```

### Stage B — Qualification (Step 3)

```text
Per company:
  LLM scores purchasing capacity vs profile.target_budget_range
  buckets: 20K–1L | 1L–3L | 3L–7L | 7L–15L | 15L+
  qualified true/false + reason
       │
  Pipeline health rule: first ~50% of list forced qualified=true
  (keeps pipeline from emptying on aggressive filters)
```

### Stage C — Scoring (Step 6)

Weighted formula (0–100 factors):

```text
total = budget×0.25 + pain×0.25 + intent×0.20
      + industry×0.15 + growth×0.10 + contact×0.05

contact_score fixed at 95 once email validated

category:
  ≥85 Hot Lead
  ≥72 Warm Lead
  ≥60 Qualified Lead
  else Ignore (still may be stored if earlier qualified)
```

### Stage D — Outreach delivery validation

```text
Try SMTP → if fail try Gmail → if fail try WhatsApp (needs phone)
sent_successfully?
  YES → status=contacted, sent_actual=true, conversation logged
  NO  → status=scored, sent_actual=false (draft schedule kept)
```

### Stage E — Meeting validation

```text
book_meeting_for_lead:
  email regex must match
  status must not already be meeting_scheduled
  google_calendar credential required
  freeBusy: primary calendar must be free for slot
  Google Meet conferenceData required
  on success: status=meeting_scheduled + Telegram alert
```

### Stage F — Reply classification validation

```text
LLM JSON:
  intent: interested | question | decline | neutral
  interested=true ONLY if clearly wants call/demo/meeting
  should_auto_reply=false on unsubscribe/decline

Fallback if JSON parse fails:
  keyword scan: meet|call|demo|schedule|available|yes|interested
```

---

## 1.5 Full Sales V3 flow diagram

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                         SALES AI V3 ENGINE                               │
└──────────────────────────────────────────────────────────────────────────┘

[1] UNDERSTAND SERVICE
    BusinessProfile → LLM → ICP paragraph
              │
              ▼
[2] MARKET DISCOVERY + VALIDATION
    available keys → LLM picks primary_source
    try primary → fallback providers until data
    waterfall enrich weak emails
    STRICT: real name + non-generic email only
              │
              ▼
[3] QUALIFICATION
    budget fit vs target_budget_range (lenient LLM)
              │
              ▼
[4] PAIN + DEEP CONTEXT
    Apollo org id → news + jobs (if key)
    LLM → exactly 2 pain points tied to USP/offer
              │
              ▼
[5] DECISION MAKER
    contacts already validated in step 2
              │
              ▼
[6] SCORING
    multi-factor weighted score → Hot/Warm/Qualified
              │
              ▼
[7] CUSTOM EMAIL GENERATION  ──────────────────────────┐
    Per lead LLM prompt:                               │
    - contact name + company                           │
    - their 2 pain points                              │
    - recent news / jobs (if any)                      │
    - your USP + offer_details                         │
    - <150 words, no placeholders, body only           │
              │                                        │
              ▼                                        │
[8] MULTI-CHANNEL SEQUENCE + DAY-1 SEND                │
    Day1 Email (personalized body)  ◄──────────────────┘
    Day3 LinkedIn DM template (pain[0])
    Day5 Email follow-up (pain[1])
    Day8 WhatsApp nudge
    Day12 Call placeholder
    Actually send Day1 via SMTP → Gmail → WhatsApp
    Save Lead + outreach_schedule + conversation
              │
              ▼
[9] CONVERSATION AI ARMED
    Gmail poll every 3m + email/WhatsApp webhooks
              │
              ▼
[10] MEETING CONVERSION
    Only if Lead.status=replied AND classification.interested
    book_meeting_for_lead → Calendar + Meet + Telegram
```

---

## 1.6 How customized mail is written (persuasion logic)

### Prompt inputs that make it “custom” (not a template)

```text
┌──────────────────┐     ┌────────────────────┐
│ BusinessProfile  │     │ Lead context       │
│ USP              │     │ name, title, co    │
│ offer_details    │     │ pain_points[2]     │
│ company_name     │     │ news titles        │
└────────┬─────────┘     │ job openings       │
         │               └─────────┬──────────┘
         └───────────┬─────────────┘
                     ▼
         LLM write email body only
         rules: short, professional, <150 words
         reference THEIR pain + YOUR offer
                     │
                     ▼
         Unique string per lead → outreach_message
```

### Multi-channel conviction sequence (nudge ladder)

```text
Day 1 ── Value + pain-aware email (first touch)
Day 3 ── Soft LinkedIn connect referencing same pain
Day 5 ── Follow-up email: second pain + revenue angle
Day 8 ── WhatsApp short availability ask
Day 12 ─ Call placeholder (human/ops)
```

Persuasion is **pain → offer → soft CTA**, not hard close on day 1. Hard conversion happens when they reply.

---

## 1.7 How replies convert to meetings (convince → book)

```text
Prospect replies (email webhook / WhatsApp / Gmail poll)
                    │
                    ▼
         Match sender → Lead (email/phone)
                    │
                    ▼
         register_inbound → status=replied
         Telegram: "Prospect replied…"
                    │
                    ▼
         _classify_reply (LLM + history + last outbound)
                    │
         ┌──────────┼──────────────────┐
         ▼          ▼                  ▼
    interested   question/neutral   decline
         │          │                  │
         │          ▼                  ▼
         │   draft suggested_reply   no auto-reply
         │   review_first OR auto_send
         │
         ▼
  if auto_book_meetings:
    book_meeting_for_lead
      freeBusy next day 10:00 UTC
      Google Meet link
      lead.status = meeting_scheduled
      Telegram meeting alert
      reminders: ~24h, ~1h, post-outreach nudge
```

**Suggested reply when interested** aims to confirm time and lock the meeting (human tone, no “I am AI”).

**Settings** (`provider=sales`):

| Setting | Effect |
|---------|--------|
| `sales_auto_reply` | On/off AI replies |
| `reply_mode=review_first` | Draft goes to PolicyEngine / human approve |
| `reply_mode=auto_send` | Celery delay 60–120s then send |
| `auto_book_meetings` | Calendar book on interested |

---

## 1.8 How Sales improves over time

```text
Outreach strategy used (tone, pain-first, news-hook, …)
        │
        logged DecisionRecord
        │
        outcomes:
          reply_received  (+10)
          meeting_booked  (+20)
          conversion      (+100)
          no_response     (−5)
          unsubscribe     (−50)
        │
        EMA update StrategyPerformance
        │
        next generate/outreach:
          LearningLoop injects top-3 strategies
          + bottom strategies to AVOID
          + NegativePatternMemory signatures
```

**Additional improvement signals:**

| Signal | Source | Improves |
|--------|--------|----------|
| Hot vs ignore scores | Step 6 | Which ICP segments to prioritize |
| sent_actual true/false | Step 8 | Channel reliability |
| reply_classification | Inbox | Which email styles get “interested” |
| Federated registry | Global hub | Cross-tenant strategy averages (PII-free) |

---

## 1.9 Simple one-shot Sales (non-V3)

```text
generate_leads
  → fetch provider
  → dedupe by email
  → status=captured
  → enrich_lead_task (Apollo match + LLM enrichment JSON)
  → score_lead_task
  → generate_outreach (SalesService)

handle_lead_with_ai_task
  → enrich → score → generate_outreach
  → status=contacted if message created
```

Enrichment fields written when empty: personal/company email, mobile, need_of_what, how_much, why, target_context, priority.

---

# 2. Marketing AI

**Class:** `MarketingAgent` · `MarketingAnalyticsService`  
**Files:** `marketing.py`, `worker.generate_campaign_task`, `marketing/analytics.py`

## 2.1 Flow

```text
User topic + days + platforms + model choices
              │
              ▼
MarketingAgent.generate_campaign → Celery queue
              │
              ▼
For day in 1..days:
  For platform in platforms:
      system_prompt = STRICT platform format
        (IG hooks/hashtags | FB paragraphs | LI professional)
      + Brand KB / contact rules
      + learning_prompt_block(platform)   ◄── past winners
              │
              ▼
      LLM text (default gemini)
      optional image (openai)
              │
              ▼
      ContentPost status=draft/pending
              │
              ▼
Human Approvals Pipeline
  approve → scheduled_at  OR  publish_now
              │
              ▼
publish_scheduled_posts (every 5 min)
  Meta Graph / LinkedIn Share
  external_post_id stored
              │
              ▼
every 6h: sync insights
  impressions, likes, comments, CTR, ER
  performance_score 0–100
  rebuild MarketingLearningPattern
              │
              ▼
next campaign prompt includes learned patterns
```

## 2.2 Data sources

| Source | Use |
|--------|-----|
| Knowledge documents (Marketing/General) | Brand voice, CTA, website, phones |
| Learning patterns / top posts | What hooks/hashtags worked |
| User campaign params | Topic, platforms, days, models |
| Meta insights / LinkedIn stats | Ground-truth engagement |
| Image providers | Creative assets |

## 2.3 Validation

| Check | How |
|-------|-----|
| Copy format | Platform-specific system prompts ban markdown/meta labels |
| Publish readiness | Needs OAuth/token + page IDs |
| Insights trust | Only posts with `external_post_id` + status published |
| Score math | log-damped impressions + ER + CTR blend 0–100 |

## 2.4 How Marketing improves

```text
Published post metrics → tags (hooks, CTA style, emoji density…)
        → pattern aggregates (what wins on IG vs LI)
        → learning_prompt_block injected next time
        → higher performance_score styles reinforced
```

Also uses shared LearningLoop when decisions are logged for campaign strategy names.

---

# 3. Support AI

**Class:** `SupportAgent` · `KnowledgeRAGService`  
**Files:** `support.py`, `kb_rag.py`

## 3.1 Flow

```text
Inbound email / WhatsApp webhook
           │
           ▼
   Is sender an active sales lead?
      YES → SalesReplyHandler (exit support)
      NO  ↓
   Open/create Ticket + TicketMessage
   Telegram new-ticket alert
   Queue boardroom triage (optional)
           │
           ▼
   auto_reply enabled?
      delay: WhatsApp ~4–5 min | Email ~20 min
           │
           ▼
   auto_reply_task
      cancel if human already replied / human_handling
           │
           ▼
   KnowledgeRAGService.answer_context
      retrieve chunks (keyword fingerprint)
      answer_allowed?  NO → escalate message only
                        YES ↓
   LLM draft grounded on KB + history
   PolicyEngine HITL if required
   send SMTP / WhatsApp
```

## 3.2 Data sources

| Source | Use |
|--------|-----|
| Ticket + message history | Conversation continuity |
| KnowledgeDocument / KnowledgeChunk | Grounded answers + citations |
| TenantPolicy | Refuse-if-not-in-KB, HITL rules |
| Meta WhatsApp / SMTP | Delivery |
| SubscriptionService | Budget/quota gate |

## 3.3 Validation

| Check | How |
|-------|-----|
| Channel credentials | validate_credentials before handle |
| Knowledge ground | `answer_allowed` false → no hallucination |
| Human override | Later agent messages cancel AI send |
| Policy | block / require approval on low confidence |

## 3.4 How Support improves

- CSAT / ticket_resolved outcomes → strategy rewards  
- Negative patterns for bad replies (policy blocks, user complaints)  
- Better KB docs → better RAG hits (operator improvement)  
- Boardroom meetings on high-value tickets improve escalation routing  

---

# 4. Orchestrator AI (chat)

**Class:** `OrchestratorAgent`

## 4.1 Flow

```text
User natural language
      │
      ├─ regex: "my {provider} key is …" → save_credential → ack
      │
      ▼
List configured providers
      │
      ▼
LLM plan (JSON schema OrchestratorPlan) with retry
  tasks: [{department, action, parameters}]
      │
      ▼
For each task:
  Marketing / Sales / Support / Finance / HR .execute_task
  OR System.request_key if missing integration
      │
      ▼
Return plan + results to UI
```

## 4.2 Data sources

- User prompt  
- `APICredential` list  
- Department agent outputs  

## 4.3 Validation

- Plan must parse as structured JSON (retry manager)  
- Missing keys → request_key message instead of silent fail  
- Provider exceptions mapped to “need your X key”  

## 4.4 Improvement

- Daily ops 08:00 runs marketing/sales/HR routines  
- Relies on child-agent learning; orchestrator itself logs “Delegate Tasks”  
- Future: bandit over plan shapes / tool-choice strategies  

---

# 5. CEO AI

**Class:** `CEOService`

## 5.1 Flow

```text
Business objective string
        │
        ▼
LLM → 4–6 DAG tasks (depends_on)
  types: marketing_research | sales_leads | sales_outreach
         hr_source | finance_budget | ceo_summary
        │
        ▼
Persist Workflow + WorkflowTasks
        │
        ▼
execute_workflow loop:
  while pending:
    ready = deps all completed
    run ready in parallel (asyncio.gather)
    on fail → abort workflow
  deadlock detection if nothing ready
        │
        ▼
ceo_summary aggregates child results → executive report
```

## 5.2 Data sources

- Objective text  
- Child agent APIs (real leads/outreach when tasks call them)  
- Activity logs  

## 5.3 Validation

- JSON plan parse with regex recovery  
- Always injects `ceo_summary` if missing  
- Dependency IDs remapped temp → DB  
- Task failure fails whole plan  

## 5.4 Improvement

- Better LLM plans from clearer objectives + KB  
- Child outcome rewards (leads, meetings) reflect plan quality  
- Place of improvement: log plan templates that produced high ROI  

---

# 6. Boardroom / Coordination

**Class:** `BoardroomService`

## 6.1 Flow

```text
Topic OR support ticket
        │
        ▼
build_decision_profile
  detect industry, category, constraints, metrics
        │
        ▼
assemble_boardroom
  CEO + Universal experts
  + Industry experts
  + Signal experts (CRM, marketing, legal, HR keywords)
        │
        ▼
Multi-role LLM discussion → decision / AgentMeeting
Telegram notify as needed
```

Ticket path: `classify_ticket_inquiry` → needs_meeting for enterprise sales / billing emergency / exec HR.

## 6.2 Data / validation / improve

| | |
|--|--|
| **Sources** | Ticket body, title, industry map, credentials keywords |
| **Validation** | LLM classification schema; only escalate matching rules |
| **Improve** | Outcomes of board decisions; fewer false escalations over time |

---

# 7. HR AI

**Class:** `HRAgent`

## 7.1 Flow

```text
source_candidates(role, requirements, salary, count, platforms)
        │
        ▼
Need platform API key (e.g. linkedin) or fail
        │
        ▼
Fetch candidates → dedupe email
        │
        ▼
LLM resume → scorecard (skills, match_score, requirements_match)
        │
        ▼
candidate_outreach → SMTP/Gmail personalized
schedule_interview → Google Calendar freeBusy-style booking
```

## 7.2 Data / validation / improve

| | |
|--|--|
| **Sources** | Job requirements (user), LinkedIn/other APIs, KB HR docs |
| **Validation** | Credentials required (no fake candidates); email dedupe; scorecard match_score |
| **Improve** | Interview show-up / hire outcomes → strategy on outreach templates |

---

# 8. Finance AI

**Class:** `FinanceAgent`

## 8.1 Flow

```text
track_roi(amount)     → AgentMetric revenue_impact +=
create_invoice(...)   → FinanceRecord open
categorize_expense    → rules (ads/payroll/cloud/travel) + optional LLM
ar_followup / overdue → list open AR
PolicyEngine can gate sensitive actions
```

## 8.2 Data / validation / improve

| | |
|--|--|
| **Sources** | User amounts, ProviderUsage (for org ROI via ROIService), FinanceRecord |
| **Validation** | Numeric amounts; policy engine on money actions |
| **Improve** | Category accuracy feedback; link real revenue outcomes to campaigns |

---

# 9. Video Agent

## 9.1 Flow

```text
plan_video_task → LLM scenes/script
render_video_task → Remotion video-renderer
Feature flag ENABLE_IN_APP_VIDEO gates marketing video gen
```

**Improve:** human ratings on renders; cost caps; not fully closed-loop yet.

---

# 10. Octa AI Manager Orchestrator (DAG / SLM)

```text
goal → DAGDecomposer (tasks + estimated ROI)
    → for task:
         ModelRouter:
           CRITICAL → frontier GPT-4o
           high ROI / long → SLM 14B
           routine → SLM 7B
         execute
         QualityGate inspect → reflection rewrite if fail
    → trajectory + logs
```

**Validation:** quality gate text inspection.  
**Improve:** SFT/DPO dataset_builder from trajectories (`octa_orchestrator/dataset_builder`).

---

# 11. Master “data truth” diagram

```text
                    ┌──────────── USER ────────────┐
                    │ Profile · Prompts · Approvals │
                    │ KB docs · API keys · Settings  │
                    └──────────────┬────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                        ▼
   External APIs              LLM providers            Channels
   Apollo/Hunter/Places       OpenAI/Claude/Gemini     SMTP/Gmail
   Meta/LinkedIn insights     Groq/Mistral/Local       WhatsApp
   Calendar freeBusy                                   Telegram
          │                        │                        │
          └────────────────────────┼────────────────────────┘
                                   ▼
                          Validation gates
                   (schema · email · freeBusy · KB
                    · policy · human approve)
                                   │
                                   ▼
                          Durable DB state
                   Lead · Post · Ticket · Workflow
                   DecisionRecord · OutcomeEvent
                                   │
                                   ▼
                          Learning + ROI
```

---

# 12. Per-agent improvement checklist (practical)

| Agent | Auto-learns from | You should also do |
|-------|------------------|--------------------|
| **Sales** | Replies, meetings, unsubscribes, strategy EMA | Keep BusinessProfile accurate; connect Apollo+SMTP+Calendar+Telegram |
| **Marketing** | Real ER/CTR/performance_score patterns | Approve only on-brand posts; connect Meta+LinkedIn insights |
| **Support** | CSAT/resolve outcomes; blocked bad drafts | Upload complete KB FAQs; enable refuse-if-not-in-KB |
| **Orchestrator** | Child success/failure logs | Configure keys before complex goals |
| **CEO** | Child task outcomes | Clear objectives with numbers (count, market, budget) |
| **HR** | Interview scheduling success | Provide sharp role requirements |
| **Finance** | Expense categories / ROI metrics | Feed real revenue amounts into track_roi |
| **Boardroom** | Escalation correctness | Tag industry correctly for expert set |

---

# 13. Sales FAQ (implementation-accurate)

**Q: If I ask for 50 leads, do I always get 50?**  
A: The system **requests** 50 from the provider. After validation (real name + non-generic email, enrichment, qualification), you may get fewer. V3 refuses to invent fake leads.

**Q: How does it know my requirements?**  
A: V3 reads Business Profile (industries, countries, budget, USP, offer, extra_context). Orchestrator mode uses the natural-language query + parameters.

**Q: How is email personalized?**  
A: Each lead gets its own LLM generation using **that lead’s pain points + news/jobs + your USP/offer**, not a shared template string.

**Q: How does it convince someone to meet?**  
A: Multi-day multi-channel sequence → when they reply, classifier detects interest → optional persuasive auto-reply → auto-book Google Meet if enabled.

**Q: What if the calendar slot is busy?**  
A: `freeBusy` raises; meeting booking fails with an explicit error (improvement: try next free slot).

---

# 14. Related docs

| Doc | Purpose |
|-----|---------|
| `docs/FULL_APP_DOCUMENTATION.md` | Full product map, ROI, directory, workers |
| `docs/GUIDE.md` | Setup & marketplace |
| `docs/EMAIL_WEBHOOKS.md` | Inbound email plumbing |
| **This file** | Deep agent flows, validation, improvement |

---

*Keep this file updated when Sales V3 validation rules, scoring weights, or meeting booking logic change.*
