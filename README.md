# OctaOS Automation Platform

Welcome to **OctaOS**, an advanced AI Employee Workspace that transforms business operations by providing autonomous AI employees for Marketing, Sales, Support, and Finance. The platform utilizes a FastAPI backend powered by Celery for background tasks, PostgreSQL for relational data, Redis for message queuing/caching, and a modern Next.js frontend interface.

---

## 🏗️ Project Architecture & Directory Structure

```text
├── app/                  # FastAPI Backend Application
│   ├── api/              # API Endpoints (v1 & v2 routes)
│   ├── core/             # Configuration, Middleware, and Security
│   ├── db/               # Database session & base model setups
│   ├── models/           # SQLAlchemy models (tenants, leads, posts, etc.)
│   ├── schemas/          # Pydantic schemas for validation
│   ├── services/         # Core business logic & AI orchestrator routines
│   └── worker/           # Celery workers & task orchestrations
├── frontend/             # Next.js Frontend Client
├── docs/                 # Detailed manuals and integration guides
├── alembic/              # Database migration configurations
├── requirements.txt      # Python dependencies
└── README.md             # This comprehensive guide
```

---

## ⚡ Prerequisites

Ensure the following tools are installed and running locally:
- **Python 3.10+**
- **Node.js 18+** & npm/yarn
- **PostgreSQL** (running on default port `5432`)
- **Redis** (running on default port `6379` for Celery & caching)

---

## ⚙️ Environment Configuration

1. In the root directory, copy the example environment file:
   ```bash
   cp .env.example .env
   ```
2. Open the `.env` file and configure your credentials:
   - **PostgreSQL Database:** Set `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` (default is `octaos`).
   - **AI Brain API Keys:** Set `ANTHROPIC_API_KEY` (Claude) and/or `OPENAI_API_KEY` (OpenAI).
   - **SMTP:** Add your email configurations for automated support responses.
   - **Frontend API URL:** Configure `NEXT_PUBLIC_API_URL` to point to your backend API server (e.g. `http://localhost:8000/api/v1`).

---

## 🚀 Setup & Execution Guide

### 1. Backend Setup (FastAPI & Celery)

1. **Activate Virtual Environment:**
   ```bash
   # Create virtual environment if you haven't already
   python3 -m venv venv
   source venv/bin/activate
   ```
2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Database Configuration & Setup:**
   Ensure PostgreSQL is running and you have created the `octaos` database:
   ```bash
   # Create database using pgcli or psql
   createdb octaos
   ```
   Run database migrations to initialize tables:
   ```bash
   alembic upgrade head
   ```
4. **Start the FastAPI Server:**
   ```bash
   uvicorn app.main:app --port 8000 --reload
   ```
   Your backend API will be available at [http://localhost:8000](http://localhost:8000). You can access the auto-generated documentation (Swagger UI) at [http://localhost:8000/docs](http://localhost:8000/docs).
5. **Start Celery (Optional, for Autonomous/Background tasks):**
   Open a **new terminal tab**, activate the virtual environment, and run the worker:
   ```bash
   celery -A app.worker.tasks worker --loglevel=info
   ```
   To trigger the scheduled automated routines (such as auto-posting or email syncs), run the Celery beat scheduler:
   ```bash
   celery -A app.worker.tasks beat --loglevel=info
   ```

---

### 2. Frontend Setup (Next.js)

1. **Navigate to the frontend folder:**
   ```bash
   cd frontend
   ```
2. **Install npm packages:**
   ```bash
   npm install
   ```
3. **Run the Development Server:**
   ```bash
   npm run dev
   ```
   The Next.js dashboard will be accessible at [http://localhost:3000](http://localhost:3000).

---

## 🛠️ Platform Setup & API Connection Guide

To allow the autonomous AI agents to perform real-world tasks, configure your credentials on the dashboard under **Instructions & APIs** (or pass keys directly to the **Orchestrator AI** chat).

### 🧠 1. LLM Brains (Claude / OpenAI)
*Powers decision-making and content generation.*
- **Claude (Anthropic):** Generate a key from the [Anthropic Console](https://console.anthropic.com/). Keys start with `sk-ant-`.
- **OpenAI:** Create a secret key from the [OpenAI Platform Dashboard](https://platform.openai.com/api-keys). Keys usually start with `sk-proj-` or `sk-`.
> [!IMPORTANT]
> At least one primary LLM key is mandatory for the Orchestrator AI to operate.

### 🌐 2. Social Media Channels
*Enables the Marketing Agent to schedule and publish posts.*
- **OAuth flow (Recommended):** Set up `META_APP_ID`, `META_APP_SECRET`, `LINKEDIN_CLIENT_ID`, and `LINKEDIN_CLIENT_SECRET` in `.env`. Authenticate via the OAuth endpoints:
  - Meta: `http://localhost:8000/api/v1/meta/auth?tenant_id=YOUR_TENANT_ID`
  - LinkedIn: `http://localhost:8000/api/v1/linkedin/auth?tenant_id=YOUR_TENANT_ID`
- **Manual token (Fallback):** Paste extended Page/User access tokens directly under the dashboard's API Settings.

### 💬 3. Chat Messaging (WhatsApp & Telegram)
*Connects support lines directly to the Support AI.*
- **WhatsApp Cloud API:** Create an app in the [Meta Developer Console](https://developers.facebook.com/), add WhatsApp, and configure the Phone Number ID and Access Token.
- **Telegram Bot API:** Message `@BotFather` on Telegram, create a bot using `/newbot`, and paste the HTTP API Token. Get your `chat_id` using `@userinfobot` to receive real-time sales alerts.

### 📧 4. Outbound Sales & Email Webhooks
- **Google Cloud OAuth:** Enable **Gmail API** and **Google Calendar API** in your Google Cloud Console. Download your OAuth Client ID JSON to configure integration.
- **SMTP Alternative:** Set up an SMTP sender with Gmail App Passwords.
- **Inbound Replies Handling:** Point your email providers (e.g. SendGrid, Mailgun) webhooks to:
  `POST /api/v1/support/email/webhook/{tenant_id}`.
  Celery also polls the configured Gmail inboxes every 3 minutes using the `poll_gmail_sales_inbox` task.

### 🔍 5. Lead Generation (Apollo, Apify & Google Places)
- **Apify:** Retrieve your token from the [Apify Console](https://console.apify.com/) to utilize web scrapers.
- **Apollo.io / Hunter.io:** Obtain API keys to search, fetch, and enrich cold outbound leads.

---

## 🤖 Agent Behavioral Parameters

OctaOS is designed to act naturally and avoid looking like a robot:
*   **WhatsApp Support Auto-Replies:** Delays responses by **4–5 minutes** to feel human-like.
*   **Email Ticket Auto-Replies:** Delays email support responses by **20 minutes**.
*   **Human Interception Override:** If you type a manual reply in the support ticket UI before the delay expires, the AI automatically cancels its draft and yields to the human agent.
*   **Knowledge Base Integration:** Agents scan documents (FAQs, pricing sheets, job specs) uploaded to the **Knowledge Base** prior to responding.

---

## ⚡ Ready-to-Run Prompts

Input these prompts in the **Orchestrator AI** tab to test setups instantly:
- **SaaS Outreach System:**
  ```text
  Execute the SaaS Outreach System. Sourcing 5 CTOs at early-stage AI startups in New York, and write personalized outbound LinkedIn DMs.
  ```
- **Creative Content Lab:**
  ```text
  Create an SEO Blog Outline Writer task with the Creative Content Lab. Write an outline on 'How AI employees are transforming small businesses'.
  ```

---

## 🔍 Troubleshooting Common Issues

1. **"Waiting for primary AI API key" / UI Frozen:**
   Ensure your Claude or OpenAI keys are set in **API Settings** or configure them in `.env`.
2. **Celery Worker Connection Refused:**
   Check if your Redis server is running:
   ```bash
   redis-cli ping
   ```
   If it returns `PONG`, check that the worker is started using the correct command:
   ```bash
   celery -A app.worker.tasks worker --loglevel=info
   ```
3. **Database Connectivity Error:**
   Verify PostgreSQL credentials inside `.env`. Check that the `octaos` database exists. You can run the database check script to verify:
   ```bash
   python check_db.py
   ```
