'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Briefcase,
  Play,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Layers,
  Sparkles,
  ShieldCheck,
  Plus,
  Loader2,
  Send,
  Zap,
  Check,
  X,
  ExternalLink,
  ShieldAlert,
  ArrowRight,
  TrendingUp,
  MessageSquare,
  DollarSign,
  UserCheck,
  Compass,
  Activity,
  Copy,
  Search
} from 'lucide-react';

interface MarketplaceViewProps {
  token: string | null;
  API_URL: string;
  fetchWithAuth: (url: string, options?: any) => Promise<Response>;
  fetchData: () => Promise<void>;
  apps: any[];
}

interface PackageItem {
  id: string;
  name: string;
  slug: string;
  section: string;
  category: string;
  desc: string;
  icon: string;
  complexity: string;
  time_saved: string;
  is_system?: boolean;
  is_inbuilt?: boolean;
  is_core_default?: boolean;
  is_installed: boolean;
  installation_id?: string;
  features: string[];
  config_schema: Record<string, any>;
  eval_scores: {
    task_success?: number;
    tool_accuracy?: number;
    avg_latency_s?: number;
    avg_cost_usd?: number;
  };
  flow_steps: any[];
  sample_input?: Record<string, any>;
}

interface FlowRunItem {
  id: string;
  flow_id: string;
  flow_name: string;
  section: string;
  status: string;
  trigger_type: string;
  duration_ms: number;
  cost_usd: number;
  tokens: number;
  created_at: string;
  error?: string;
  steps: any[];
}

interface ApprovalItem {
  id: string;
  flow_run_id: string;
  title: string;
  description: string;
  risk_level: string;
  payload: any;
  created_at: string;
}

const DEFAULT_FALLBACK_PACKAGES: PackageItem[] = [
  {
    id: "pkg_restaurant_growth_autopilot",
    name: "Restaurant Review & Dining Autopilot",
    slug: "restaurant_growth_autopilot",
    section: "marketing",
    category: "Restaurant & Dining",
    desc: "Autonomous dining growth: analyzes Google/Yelp reviews, crafts hospitality replies, routes urgent kitchen feedback, and triggers VIP booking perks.",
    icon: "🍽️",
    complexity: "Intermediate",
    time_saved: "20h/week",
    is_system: true,
    is_inbuilt: true,
    is_core_default: false,
    is_installed: false,
    features: ["Review Sentiment & Critical Alerting", "VIP Loyalty Perks Trigger", "Automated Hospitality Replies", "Menu & Food Trend Triage"],
    config_schema: { restaurant_name: { type: "string", default: "Bella Vista Trattoria", label: "Restaurant Name" } },
    eval_scores: { task_success: 97.2, tool_accuracy: 98.5, avg_latency_s: 3.5, avg_cost_usd: 0.018 },
    flow_steps: [
      { id: "step_review_intake", name: "Parse Dining Guest Feedback", type: "agent", agent_slug: "support_ai" },
      { id: "step_reply_approval", name: "Host Approval for Public Reply", type: "approval", risk_level: "low" },
    ],
    sample_input: {
      guest_name: "Sophia Martinez",
      rating: 5,
      review_text: "The truffle pappardelle and wine pairing were sublime! Will celebrate our anniversary here again.",
      platform: "Google Reviews",
      email: "sophia.m@example.com"
    }
  },
  {
    id: "pkg_real_estate_showing_concierge",
    name: "Real Estate Buyer & Showing Concierge",
    slug: "real_estate_showing_concierge",
    section: "sales",
    category: "Real Estate",
    desc: "Screens property buyer inquiries, scores pre-approval and purchasing timeline, schedules private showings, and syncs buyer preferences to CRM.",
    icon: "🏡",
    complexity: "Intermediate",
    time_saved: "32h/week",
    is_system: true,
    is_inbuilt: true,
    is_core_default: false,
    is_installed: false,
    features: ["Buyer Budget & Timeline Scoring", "Listing & Neighborhood Matcher", "Private Showing Scheduler", "Automated Broker Follow-up"],
    config_schema: { brokerage_name: { type: "string", default: "Apex Luxury Realty", label: "Brokerage / Agency Name" } },
    eval_scores: { task_success: 96.8, tool_accuracy: 98.2, avg_latency_s: 4.1, avg_cost_usd: 0.022 },
    flow_steps: [
      { id: "step_buyer_intake", name: "Qualify Buyer Criteria & Purchasing Power", type: "agent", agent_slug: "sales_ai" },
      { id: "step_approval", name: "Agent Review Showing Schedule", type: "approval", risk_level: "medium" },
    ],
    sample_input: {
      buyer_name: "Marcus Vance",
      email: "marcus.vance@example.com",
      budget: "$1,200,000",
      target_property: "3-Bed Penthouse or Brownstone with Parking",
      timeline: "Next 60 days"
    }
  },
  {
    id: "pkg_education_admissions_concierge",
    name: "EdTech & Student Admissions Concierge",
    slug: "education_admissions_concierge",
    section: "support",
    category: "Education & EdTech",
    desc: "Answers prospective student questions from course knowledge bases, verifies prerequisite criteria, and schedules admissions interviews.",
    icon: "🎓",
    complexity: "Intermediate",
    time_saved: "25h/week",
    is_system: true,
    is_inbuilt: true,
    is_core_default: false,
    is_installed: false,
    features: ["Course & Syllabus Knowledge RAG", "Prerequisite Criteria Verification", "Admissions Interview Coordinator", "Automated Information Packet Dispatch"],
    config_schema: { institution_name: { type: "string", default: "Novus Academy of Applied AI", label: "School or Institute Name" } },
    eval_scores: { task_success: 96.0, tool_accuracy: 97.8, avg_latency_s: 3.8, avg_cost_usd: 0.019 },
    flow_steps: [
      { id: "step_inquiry", name: "Analyze Prospective Student Inquiry", type: "agent", agent_slug: "support_ai" },
      { id: "step_schedule", name: "Admissions Interview Invitation", type: "tool", tool: "email.send" },
    ],
    sample_input: {
      student_name: "Aria Montgomery",
      email: "aria.m@example.com",
      program_of_interest: "Accelerated AI Systems Engineering (Fall Cohort)",
      question: "Can I transfer credits from my electrical engineering bachelor degree?"
    }
  },
  {
    id: "pkg_fitness_membership_autopilot",
    name: "Gym & Fitness Membership Autopilot",
    slug: "fitness_membership_autopilot",
    section: "sales",
    category: "Fitness & Wellness",
    desc: "Engages gym trial signups, scores fitness goals, schedules personal training consultations, and converts free trial members.",
    icon: "💪",
    complexity: "Beginner",
    time_saved: "18h/week",
    is_system: true,
    is_inbuilt: true,
    is_core_default: false,
    is_installed: false,
    features: ["Trial Signup Qualification", "Trainer Booking Scheduler", "SMS Goal Check-in Automation", "Membership Renewal Sequences"],
    config_schema: { gym_name: { type: "string", default: "IronPulse Fitness Club", label: "Gym or Studio Name" } },
    eval_scores: { task_success: 95.8, tool_accuracy: 97.4, avg_latency_s: 3.2, avg_cost_usd: 0.015 },
    flow_steps: [
      { id: "step_qualify", name: "Assess Fitness Goals & Commitment", type: "agent", agent_slug: "sales_ai" },
      { id: "step_confirm", name: "Send Workout Pass & Orientation Invite", type: "tool", tool: "email.send" },
    ],
    sample_input: {
      lead_name: "Jordan Lee",
      email: "jordan.fit@example.com",
      fitness_goal: "Strength training & conditioning 4 days a week",
      preferred_trainer_time: "Weekday mornings 7:00 AM"
    }
  },
  {
    id: "pkg_saas_outreach_system",
    name: "SaaS Inbound & Outbound Growth System",
    slug: "saas_outreach_system",
    section: "sales",
    category: "B2B Outbound",
    desc: "End-to-end autonomous SDR flow: researches prospect, calculates lead score, drafts personalized outreach, requires approval, and dispatches email.",
    icon: "🚀",
    complexity: "Advanced",
    time_saved: "35h/week",
    is_system: true,
    is_inbuilt: true,
    is_core_default: true,
    is_installed: true,
    features: ["Autonomous Web Research", "Algorithmic ICP Lead Scoring", "Manager Approval Gate", "Automated CRM Sync"],
    config_schema: { min_score: { type: "integer", default: 70, label: "Minimum Qualification Score" } },
    eval_scores: { task_success: 96.5, tool_accuracy: 98.0, avg_latency_s: 4.2, avg_cost_usd: 0.024 },
    flow_steps: [
      { id: "step_research", name: "Autonomous Prospect Intelligence", type: "agent", agent_slug: "sales_ai" },
      { id: "step_approval", name: "Outreach Pitch Approval", type: "approval", risk_level: "medium" },
    ],
    sample_input: { company: "Stripe", email: "patrick@stripe.com", contact_name: "Patrick Collison" }
  },
  {
    id: "pkg_ecommerce_growth_autopilot",
    name: "E-Commerce Growth & Retention Autopilot",
    slug: "ecommerce_growth_autopilot",
    section: "marketing",
    category: "E-Commerce",
    desc: "SEO product desc generator, competitor price monitor, and abandoned cart SMS/email recovery sequences.",
    icon: "🛍️",
    complexity: "Intermediate",
    time_saved: "25h/week",
    is_system: true,
    is_inbuilt: true,
    is_core_default: true,
    is_installed: true,
    features: ["SEO Product Writer", "Competitor Price Monitor", "Cart Recovery Sequencing"],
    config_schema: { store_url: { type: "string", label: "Online Store URL" } },
    eval_scores: { task_success: 95.0, tool_accuracy: 96.5, avg_latency_s: 3.9, avg_cost_usd: 0.02 },
    flow_steps: [{ id: "step_copy", name: "Generate SEO Product Narrative", type: "agent", agent_slug: "marketing_ai" }],
    sample_input: { product: "Wireless Ergonomic Mechanical Keyboard", price: 149, email: "shopper@example.com" }
  },
  {
    id: "pkg_medical_clinic_receptionist",
    name: "Medical & Healthcare Patient Receptionist",
    slug: "medical_clinic_receptionist",
    section: "support",
    category: "Healthcare",
    desc: "Automates patient scheduling, SMS check-in reminders, and insurance triage ticketing.",
    icon: "🏥",
    complexity: "Intermediate",
    time_saved: "18h/week",
    is_system: true,
    is_inbuilt: true,
    is_core_default: true,
    is_installed: true,
    features: ["Patient Calendar Sync", "SMS Confirmation Reminder", "Insurance Eligibility Triage"],
    config_schema: { clinic_name: { type: "string", label: "Clinic or Practice Name" } },
    eval_scores: { task_success: 97.0, tool_accuracy: 98.9, avg_latency_s: 3.1, avg_cost_usd: 0.015 },
    flow_steps: [{ id: "step_triage", name: "Patient Query Triage", type: "agent", agent_slug: "support_ai" }],
    sample_input: { patient_name: "Elena Rostova", appointment_type: "Annual Health Checkup", email: "elena@example.com" }
  },
  {
    id: "pkg_law_firm_document_automator",
    name: "Law Firm Contract & Clause Analyzer",
    slug: "law_firm_document_automator",
    section: "finance",
    category: "LegalTech",
    desc: "Parses NDAs, master service agreements, highlights liability cap exceptions, and drafts partner memos.",
    icon: "⚖️",
    complexity: "Advanced",
    time_saved: "30h/week",
    is_system: true,
    is_inbuilt: true,
    is_core_default: false,
    is_installed: false,
    features: ["Indemnity Clause Extraction", "Non-Standard Risk Highlighting", "Executive Summary Generator"],
    config_schema: { jurisdiction: { type: "string", default: "Delaware, USA", label: "Governing Law Jurisdiction" } },
    eval_scores: { task_success: 98.2, tool_accuracy: 99.1, avg_latency_s: 5.5, avg_cost_usd: 0.035 },
    flow_steps: [{ id: "step_parse", name: "Contract Risk Analyzer", type: "agent", agent_slug: "finance_ai" }],
    sample_input: { contract_type: "Non-Disclosure Agreement (NDA)", counterparty: "Apex Systems LLC" }
  },
  {
    id: "pkg_hr_recruiter_system",
    name: "AI Talent Screener & Interview Scheduler",
    slug: "hr_recruiter_system",
    section: "hr",
    category: "HR & Recruitment",
    desc: "Autonomous resume parsing, rubric-based qualification scoring, candidate screening chat, and interview booking.",
    icon: "💼",
    complexity: "Intermediate",
    time_saved: "28h/week",
    is_system: true,
    is_inbuilt: true,
    is_core_default: true,
    is_installed: true,
    features: ["Blind Resume Scoring", "Candidate Q&A Bot", "Hiring Manager Calendar Sync"],
    config_schema: { role_title: { type: "string", default: "Senior Software Engineer", label: "Target Job Role" } },
    eval_scores: { task_success: 96.0, tool_accuracy: 97.5, avg_latency_s: 3.6, avg_cost_usd: 0.018 },
    flow_steps: [{ id: "step_screen", name: "Screen Candidate Resume", type: "agent", agent_slug: "hr_ai" }],
    sample_input: { candidate_name: "David Kim", target_role: "Staff Platform Engineer", email: "david.kim@example.com" }
  },
  {
    id: "pkg_creative_content_lab",
    name: "Multi-Channel Creative Content Lab",
    slug: "creative_content_lab",
    section: "marketing",
    category: "Creative Agency",
    desc: "Generates cross-platform marketing campaigns (LinkedIn, X, blog, email newsletter) with human editorial review gates.",
    icon: "🎨",
    complexity: "Intermediate",
    time_saved: "20h/week",
    is_system: true,
    is_inbuilt: true,
    is_core_default: true,
    is_installed: true,
    features: ["Cross-Platform Copywriting", "Multi-Persona Tone Adaptation", "Marketing Manager Approval Gate"],
    config_schema: { brand_voice: { type: "string", default: "Authoritative & Futuristic", label: "Brand Voice Description" } },
    eval_scores: { task_success: 95.5, tool_accuracy: 96.0, avg_latency_s: 4.0, avg_cost_usd: 0.021 },
    flow_steps: [{ id: "step_draft", name: "Draft Multi-Platform Campaign", type: "agent", agent_slug: "marketing_ai" }],
    sample_input: { topic: "Launch of autonomous AI agents in enterprise workflows", audience: "CTOs and VP Engineering" }
  },
  {
    id: "pkg_executive_compliance_audit",
    name: "Automated Security & SOC2 Compliance Auditor",
    slug: "executive_compliance_audit",
    section: "finance",
    category: "Compliance & Security",
    desc: "Monitors access logs, checks audit trail anomalies, and prepares weekly executive compliance summaries.",
    icon: "🛡️",
    complexity: "Advanced",
    time_saved: "22h/week",
    is_system: true,
    is_inbuilt: true,
    is_core_default: false,
    is_installed: false,
    features: ["Audit Trail Anomaly Detection", "SOC2 Control Evidence Collector", "CISO Executive Digest"],
    config_schema: { report_frequency: { type: "string", default: "Weekly", label: "Digest Cadence" } },
    eval_scores: { task_success: 98.0, tool_accuracy: 99.4, avg_latency_s: 4.8, avg_cost_usd: 0.029 },
    flow_steps: [{ id: "step_audit", name: "Scan System Access Logs", type: "agent", agent_slug: "finance_ai" }],
    sample_input: { timeframe: "Last 7 days", scope: "IAM & Admin Role Changes" }
  }
];

export default function MarketplaceView({
  token,
  API_URL,
  fetchWithAuth,
  fetchData,
  apps,
}: MarketplaceViewProps) {
  // Navigation tabs
  const [activeTab, setActiveTab] = useState<'catalog' | 'installed' | 'approvals'>('catalog');
  const [selectedSection, setSelectedSection] = useState<string>('all');
  const [packOriginFilter, setPackOriginFilter] = useState<'all' | 'inbuilt' | 'custom'>('all');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [cloningId, setCloningId] = useState<string | null>(null);
  const [clonedSuccessMsg, setClonedSuccessMsg] = useState<string | null>(null);

  // Industry Categories for pre-populated catalog filtering
  const INDUSTRY_CATEGORIES = [
    { id: 'all', label: 'All Industries', icon: '🌐' },
    { id: 'Restaurant & Dining', label: 'Restaurant & Dining', icon: '🍽️' },
    { id: 'Real Estate', label: 'Real Estate', icon: '🏡' },
    { id: 'Education & EdTech', label: 'Education & EdTech', icon: '🎓' },
    { id: 'Fitness & Wellness', label: 'Fitness & Gym', icon: '💪' },
    { id: 'E-Commerce', label: 'E-Commerce', icon: '🛍️' },
    { id: 'Healthcare', label: 'Healthcare', icon: '🏥' },
    { id: 'LegalTech', label: 'Legal & Compliance', icon: '⚖️' },
    { id: 'Creative Agency', label: 'Agency & Media', icon: '🎨' },
  ];

  // Packages list - immediately initialized with pre-populated industry catalog
  const [packages, setPackages] = useState<PackageItem[]>(DEFAULT_FALLBACK_PACKAGES);
  const [loadingPacks, setLoadingPacks] = useState(false);

  // Flow runs & approvals
  const [flowRuns, setFlowRuns] = useState<FlowRunItem[]>([]);
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [loadingRuns, setLoadingRuns] = useState(false);

  // Configure & Install modal state
  const [configuringPack, setConfiguringPack] = useState<PackageItem | null>(null);
  const [installConfig, setInstallConfig] = useState<Record<string, any>>({});
  const [installing, setInstalling] = useState(false);

  // Trigger Run Modal with Smart Pre-Populated Payloads
  const [runModalPack, setRunModalPack] = useState<PackageItem | null>(null);
  const [runInputJson, setRunInputJson] = useState('{\n  "company": "Acme Corp",\n  "email": "alex@acme.com"\n}');
  const [triggeringRun, setTriggeringRun] = useState(false);

  const handleOpenRunModal = (pack: PackageItem) => {
    setRunModalPack(pack);
    if (pack.sample_input && Object.keys(pack.sample_input).length > 0) {
      setRunInputJson(JSON.stringify(pack.sample_input, null, 2));
    } else {
      setRunInputJson('{\n  "company": "Acme Corp",\n  "email": "alex@acme.com"\n}');
    }
  };

  // Create Custom Package Modal
  const [isCreatePackOpen, setIsCreatePackOpen] = useState(false);
  const [newPackName, setNewPackName] = useState('');
  const [newPackSection, setNewPackSection] = useState('sales');
  const [newPackCategory, setNewPackCategory] = useState('B2B Growth');
  const [newPackDesc, setNewPackDesc] = useState('');
  const [newPackFeatures, setNewPackFeatures] = useState('');
  const [savingNewPack, setSavingNewPack] = useState(false);

  // Approval Decision Modal
  const [decisionModalAppr, setDecisionModalAppr] = useState<ApprovalItem | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [decidingAppr, setDecidingAppr] = useState(false);

  // Fetch Packages
  const fetchPackages = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/dashboard/marketplace/packs`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          setPackages(data);
        }
      }
    } catch (e) {
      console.warn('Network issue fetching live packs from server; using pre-populated catalog:', e);
    } finally {
      setLoadingPacks(false);
    }
  }, [token, API_URL, fetchWithAuth]);

  // Fetch Flow Runs & Approvals
  const fetchRunsAndApprovals = useCallback(async () => {
    if (!token) return;
    setLoadingRuns(true);
    try {
      const [runsRes, apprRes] = await Promise.all([
        fetchWithAuth(`${API_URL}/dashboard/flows/runs`),
        fetchWithAuth(`${API_URL}/dashboard/approvals`),
      ]);
      if (runsRes.ok) setFlowRuns(await runsRes.json());
      if (apprRes.ok) setApprovals(await apprRes.json());
    } catch (e) {
      console.error('Failed to fetch runs/approvals:', e);
    } finally {
      setLoadingRuns(false);
    }
  }, [token, API_URL, fetchWithAuth]);

  useEffect(() => {
    fetchPackages();
    fetchRunsAndApprovals();
  }, [token, fetchPackages, fetchRunsAndApprovals]);

  // Handle Install
  const handleInstallPack = async () => {
    if (!configuringPack) return;
    setInstalling(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/dashboard/marketplace/install`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          package_id: configuringPack.id,
          app_name: configuringPack.name,
          config: installConfig,
        }),
      });

      if (res.ok) {
        setConfiguringPack(null);
        setInstallConfig({});
        fetchPackages();
        fetchData();
        alert(`'${configuringPack.name}' installed and provisioned into section '${configuringPack.section}'.`);
      } else {
        const err = await res.json();
        alert(`Installation failed: ${err.detail || 'Unknown error'}`);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setInstalling(false);
    }
  };

  // Handle Trigger Run
  const handleTriggerRun = async () => {
    if (!runModalPack) return;
    setTriggeringRun(true);
    try {
      let parsedInputs = {};
      try {
        parsedInputs = JSON.parse(runInputJson);
      } catch {
        alert('Invalid JSON input parameters');
        setTriggeringRun(false);
        return;
      }

      // Check if installed pack has active flows
      const flowsRes = await fetchWithAuth(`${API_URL}/dashboard/flows?section=${runModalPack.section}`);
      if (flowsRes.ok) {
        const flows = await flowsRes.json();
        const targetFlow = flows[0];
        if (targetFlow) {
          const runRes = await fetchWithAuth(`${API_URL}/dashboard/flows/${targetFlow.id}/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ inputs: parsedInputs }),
          });
          if (runRes.ok) {
            setRunModalPack(null);
            fetchRunsAndApprovals();
            setActiveTab('installed');
            alert('Flow run initiated successfully.');
          }
        }
      }
    } catch (e) {
      console.error(e);
    } finally {
      setTriggeringRun(false);
    }
  };

  // Handle Approval Decision
  const handleApprovalDecision = async (decision: 'approve' | 'reject') => {
    if (!decisionModalAppr) return;
    setDecidingAppr(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/dashboard/approvals/${decisionModalAppr.id}/decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          decision,
          rejection_reason: decision === 'reject' ? rejectReason : undefined,
        }),
      });

      if (res.ok) {
        setDecisionModalAppr(null);
        setRejectReason('');
        fetchRunsAndApprovals();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setDecidingAppr(false);
    }
  };

  // Handle Create Custom Package
  const handleCreatePackage = async () => {
    if (!newPackName.trim() || !newPackDesc.trim()) {
      alert('Please fill in package name and description.');
      return;
    }
    setSavingNewPack(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/dashboard/marketplace/packs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newPackName,
          section: newPackSection,
          category: newPackCategory,
          desc: newPackDesc,
          features: newPackFeatures.split('\n').filter((f) => f.trim().length > 0),
          flow: [
            { id: 'step_1', name: 'Intake & Analysis', type: 'agent', agent_slug: 'sales_ai' },
            { id: 'step_2', name: 'Operational Review', type: 'approval', risk_level: 'medium' },
          ],
        }),
      });

      if (res.ok) {
        setIsCreatePackOpen(false);
        setNewPackName('');
        setNewPackDesc('');
        setNewPackFeatures('');
        fetchPackages();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setSavingNewPack(false);
    }
  };

  // Handle Clone Package into Custom Agent Studio Flow
  const handleCloneToStudio = async (pack: PackageItem) => {
    setCloningId(pack.id);
    try {
      const res = await fetchWithAuth(`${API_URL}/dashboard/marketplace/packs/${pack.id}/clone`, {
        method: 'POST',
      });
      if (res.ok) {
        const data = await res.json();
        setClonedSuccessMsg(data.message || `Cloned '${pack.name}' into custom Flow!`);
        fetchData();
        setTimeout(() => setClonedSuccessMsg(null), 6000);
      } else {
        const err = await res.json();
        alert(`Error cloning pack: ${err.detail || 'Request failed'}`);
      }
    } catch (e) {
      console.error(e);
      alert('Failed to clone package.');
    } finally {
      setCloningId(null);
    }
  };

  // Filtered packages by Section, Origin, Industry Category, and Search Query
  const filteredPacks = packages.filter((p) => {
    const matchesSection = selectedSection === 'all' || p.section === selectedSection;
    const matchesOrigin =
      packOriginFilter === 'all' ||
      (packOriginFilter === 'inbuilt' && (p.is_inbuilt || p.is_system)) ||
      (packOriginFilter === 'custom' && !p.is_inbuilt && !p.is_system);
    const matchesCategory =
      selectedCategory === 'all' ||
      p.category.toLowerCase().includes(selectedCategory.toLowerCase());
    const query = searchQuery.trim().toLowerCase();
    const matchesSearch =
      query === '' ||
      p.name.toLowerCase().includes(query) ||
      p.desc.toLowerCase().includes(query) ||
      p.category.toLowerCase().includes(query) ||
      (p.features && p.features.some((f) => f.toLowerCase().includes(query)));
    return matchesSection && matchesOrigin && matchesCategory && matchesSearch;
  });

  return (
    <div className="max-w-6xl mx-auto space-y-6 pb-20 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-800/60 pb-6">
        <div>
          <h1 className="text-4xl font-extrabold text-white tracking-tight flex items-center gap-3">
            <Briefcase className="text-pink-500 h-9 w-9" /> Autonomous Package Marketplace
          </h1>
          <p className="text-gray-400 mt-1">
            Install and run section-dedicated agentic automations with verifiable evaluation scores and human governance.
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center gap-2 bg-gray-900/80 p-1.5 rounded-2xl border border-gray-800/80">
          <button
            onClick={() => setActiveTab('catalog')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              activeTab === 'catalog'
                ? 'bg-pink-600 text-white shadow-lg shadow-pink-500/20'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            <Compass size={14} /> Workflow Packages
          </button>
          <button
            onClick={() => setActiveTab('installed')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              activeTab === 'installed'
                ? 'bg-pink-600 text-white shadow-lg shadow-pink-500/20'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            <Activity size={14} /> Live Runs & History
            <span className="text-[10px] bg-pink-500/20 text-pink-300 px-1.5 py-0.5 rounded-full ml-1">
              {flowRuns.length}
            </span>
          </button>
          <button
            onClick={() => setActiveTab('approvals')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              activeTab === 'approvals'
                ? 'bg-amber-600 text-white shadow-lg shadow-amber-500/20'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            <ShieldCheck size={14} /> Approval Inbox
            {approvals.length > 0 && (
              <span className="text-[10px] bg-amber-500 text-black font-extrabold px-1.5 py-0.5 rounded-full ml-1 animate-pulse">
                {approvals.length}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────────────────────
          TAB 1: WORKFLOW PACKAGES CATALOG
         ───────────────────────────────────────────────────────────────────────────── */}
      {activeTab === 'catalog' && (
        <div className="space-y-6 animate-in fade-in duration-200">
          {/* Cloned Success Alert */}
          {clonedSuccessMsg && (
            <div className="p-3.5 bg-violet-500/15 border border-violet-500/40 rounded-2xl flex items-center justify-between text-xs text-violet-200 animate-in slide-in-from-top-2">
              <span className="flex items-center gap-2 font-medium">
                <Sparkles size={15} className="text-violet-400" />
                {clonedSuccessMsg}
              </span>
              <button
                onClick={() => setClonedSuccessMsg(null)}
                className="text-violet-400 hover:text-white text-xs font-bold px-2 py-0.5"
              >
                Dismiss
              </button>
            </div>
          )}

          {/* Section Filter & Origin Filter & Create Button */}
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-3">
              {/* Origin Filter (Inbuilt vs Custom) */}
              <div className="flex items-center gap-1 bg-gray-900/90 p-1 rounded-xl border border-gray-800">
                <button
                  onClick={() => setPackOriginFilter('all')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                    packOriginFilter === 'all'
                      ? 'bg-pink-600 text-white shadow-sm'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  All ({packages.length})
                </button>
                <button
                  onClick={() => setPackOriginFilter('inbuilt')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
                    packOriginFilter === 'inbuilt'
                      ? 'bg-emerald-600 text-white shadow-sm shadow-emerald-500/20'
                      : 'text-emerald-400 hover:text-emerald-300'
                  }`}
                >
                  <Zap size={11} className="fill-current" /> Inbuilt Core ({packages.filter((p) => p.is_inbuilt || p.is_system).length})
                </button>
                <button
                  onClick={() => setPackOriginFilter('custom')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                    packOriginFilter === 'custom'
                      ? 'bg-violet-600 text-white shadow-sm'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  Custom
                </button>
              </div>

              {/* Section Filters */}
              <div className="flex flex-wrap items-center gap-1 bg-gray-900/60 p-1 rounded-xl border border-gray-800/80">
                {[
                  { id: 'all', label: 'All Sections' },
                  { id: 'sales', label: 'Sales CRM' },
                  { id: 'marketing', label: 'Marketing' },
                  { id: 'support', label: 'Support' },
                  { id: 'hr', label: 'Hiring & HR' },
                  { id: 'finance', label: 'Finance & Legal' },
                ].map((s) => (
                  <button
                    key={s.id}
                    onClick={() => setSelectedSection(s.id)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                      selectedSection === s.id
                        ? 'bg-pink-600 text-white'
                        : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>

              {/* Keyword Search Input */}
              <div className="relative min-w-[200px] flex-1">
                <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
                <Input
                  type="text"
                  placeholder="Search restaurant, real estate, edtech..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 pr-3 h-9 bg-gray-900/80 border-gray-800 text-xs text-white rounded-xl placeholder:text-gray-500 focus:border-pink-500"
                />
              </div>
            </div>

            <Button
              onClick={() => setIsCreatePackOpen(true)}
              className="bg-pink-600 hover:bg-pink-500 text-white font-bold h-10 rounded-xl px-4 shadow-lg shadow-pink-500/20 flex items-center gap-2 hover:scale-[1.02] active:scale-95 transition-all self-start lg:self-auto"
            >
              <Plus size={16} /> Create Custom Package
            </Button>
          </div>

          {/* Industry Verticals Quick-Filter Pills */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1.5 pt-0.5 no-scrollbar text-xs">
            <span className="text-[10px] uppercase font-bold text-gray-500 whitespace-nowrap mr-1 flex items-center gap-1">
              Industries:
            </span>
            {INDUSTRY_CATEGORIES.map((cat) => (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                className={`px-3 py-1 rounded-xl text-xs font-bold transition-all whitespace-nowrap flex items-center gap-1.5 border ${
                  selectedCategory === cat.id
                    ? 'bg-pink-600 border-pink-500 text-white shadow-sm shadow-pink-500/20'
                    : 'bg-gray-900/60 border-gray-800/80 text-gray-400 hover:text-white hover:border-gray-700'
                }`}
              >
                <span>{cat.icon}</span>
                <span>{cat.label}</span>
              </button>
            ))}
          </div>

          {/* Packages Grid */}
          {loadingPacks ? (
            <div className="flex flex-col items-center justify-center py-20 text-gray-400 gap-3">
              <Loader2 size={32} className="animate-spin text-pink-500" />
              <span className="text-xs font-bold uppercase tracking-wider">Loading Marketplace Packages...</span>
            </div>
          ) : filteredPacks.length === 0 ? (
            <div className="p-12 text-center glass-panel rounded-3xl border border-gray-800 space-y-4">
              <p className="text-gray-300 text-sm font-medium">No packages found matching your active filters or search.</p>
              <Button
                variant="outline"
                onClick={() => {
                  setSelectedSection('all');
                  setPackOriginFilter('all');
                  setSelectedCategory('all');
                  setSearchQuery('');
                }}
                className="bg-transparent border-gray-700 text-pink-400 hover:text-white hover:bg-pink-600/20 rounded-xl text-xs font-bold"
              >
                Clear All Filters & Show All Packages
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredPacks.map((pack) => {
                const evalScores = pack.eval_scores || { task_success: 96.0, avg_latency_s: 4.2, avg_cost_usd: 0.02 };

              return (
                <Card
                  key={pack.id}
                  className="glass-panel border-transparent hover:border-pink-500/30 transition-all duration-300 rounded-3xl overflow-hidden shadow-2xl relative flex flex-col justify-between p-6"
                >
                  <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-pink-500 to-transparent" />

                  <CardHeader className="p-0 pb-4">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex flex-wrap items-center gap-1.5">
                        {pack.is_inbuilt || pack.is_system ? (
                          <span className="flex items-center gap-1 text-[9px] uppercase font-black tracking-widest text-emerald-300 bg-emerald-500/15 px-2.5 py-0.5 rounded-full border border-emerald-500/30 shadow-sm shadow-emerald-500/10">
                            <Zap size={10} className="fill-emerald-400 text-emerald-400" /> Inbuilt
                          </span>
                        ) : (
                          <span className="text-[9px] uppercase font-bold text-violet-300 bg-violet-500/10 px-2 py-0.5 rounded-md border border-violet-500/20">
                            Custom Pack
                          </span>
                        )}
                        {pack.is_core_default && (
                          <span className="text-[9px] font-extrabold uppercase tracking-wide text-amber-300 bg-amber-500/15 px-2 py-0.5 rounded-md border border-amber-500/30">
                            Core Default
                          </span>
                        )}
                        <span className="text-[9px] uppercase font-black tracking-widest text-pink-400 bg-pink-500/10 px-2.5 py-0.5 rounded-full border border-pink-500/20">
                          {pack.section}
                        </span>
                        <span className="text-[9px] uppercase font-bold text-gray-400 bg-gray-900 px-2 py-0.5 rounded-md border border-gray-800">
                          {pack.category}
                        </span>
                      </div>
                      <span className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-md border border-emerald-500/20 whitespace-nowrap">
                        {pack.time_saved} saved
                      </span>
                    </div>

                    <div className="flex items-center gap-3 mb-2">
                      <div className="text-3xl p-2 bg-pink-500/10 rounded-2xl border border-pink-500/20 flex items-center justify-center h-12 w-12 flex-shrink-0">
                        {pack.icon}
                      </div>
                      <div>
                        <CardTitle className="text-lg text-white font-extrabold leading-snug">{pack.name}</CardTitle>
                        <span className="text-[10px] text-gray-400 font-medium">Complexity: {pack.complexity}</span>
                      </div>
                    </div>

                    <CardDescription className="text-gray-300 text-xs mt-2 leading-relaxed line-clamp-3">
                      {pack.desc}
                    </CardDescription>

                    {/* Verifiable Eval Score Badge */}
                    <div className="mt-3 p-2.5 bg-gray-950/70 border border-gray-800/80 rounded-xl space-y-1">
                      <div className="flex items-center justify-between text-[10px]">
                        <span className="text-gray-400 font-bold uppercase flex items-center gap-1">
                          <ShieldCheck size={11} className="text-emerald-400" /> Evaluation Benchmark
                        </span>
                        <span className="text-emerald-400 font-extrabold">{evalScores.task_success}% Success</span>
                      </div>
                      <div className="flex justify-between text-[9px] text-gray-500 font-mono">
                        <span>Latency: ~{evalScores.avg_latency_s}s</span>
                        <span>Cost: ~${evalScores.avg_cost_usd}/run</span>
                      </div>
                    </div>
                  </CardHeader>

                  <CardContent className="mt-auto pt-4 border-t border-gray-800/60 p-0 space-y-4">
                    <div className="space-y-1.5">
                      <span className="text-[10px] font-bold uppercase text-gray-500 tracking-wider">
                        Included Pipeline Features:
                      </span>
                      <ul className="space-y-1">
                        {pack.features.map((feat, idx) => (
                          <li key={idx} className="text-[11px] text-gray-300 flex items-center gap-2 leading-tight">
                            <span className="h-1 w-1 rounded-full bg-pink-500 flex-shrink-0" />
                            <span>{feat}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="flex items-center gap-2 pt-2">
                      {pack.is_installed ? (
                        <>
                          <Button
                            onClick={() => handleOpenRunModal(pack)}
                            className="flex-1 bg-violet-600 hover:bg-violet-500 text-white font-bold h-10 rounded-xl flex items-center justify-center gap-1.5 text-xs shadow-md shadow-violet-500/20"
                          >
                            <Play size={13} /> Run Automation
                          </Button>
                          <Button
                            variant="outline"
                            onClick={() => handleCloneToStudio(pack)}
                            disabled={cloningId === pack.id}
                            title="Clone into Custom Agent Studio to modify flow steps"
                            className="h-10 px-3 bg-gray-900/80 border-gray-800 hover:border-violet-500/50 hover:bg-violet-500/10 text-gray-300 hover:text-white rounded-xl text-xs font-bold transition-all flex items-center gap-1"
                          >
                            {cloningId === pack.id ? <Loader2 size={13} className="animate-spin" /> : <Copy size={13} />}
                            <span className="hidden sm:inline">Clone</span>
                          </Button>
                          <div
                            className="h-10 px-2.5 bg-emerald-500/10 border border-emerald-500/30 rounded-xl flex items-center justify-center text-emerald-400 text-xs font-extrabold"
                            title="Pre-installed and active in this workspace"
                          >
                            Active ✓
                          </div>
                        </>
                      ) : (
                        <>
                          <Button
                            onClick={() => {
                              setConfiguringPack(pack);
                              setInstallConfig(pack.config_schema ? { ...pack.config_schema } : {});
                            }}
                            className="flex-1 bg-pink-600 hover:bg-pink-500 text-white font-bold h-10 rounded-xl shadow-lg shadow-pink-500/20 hover:scale-[1.02] active:scale-95 transition-all text-xs"
                          >
                            Configure & Install
                          </Button>
                          <Button
                            variant="outline"
                            onClick={() => handleCloneToStudio(pack)}
                            disabled={cloningId === pack.id}
                            title="Clone into Custom Agent Studio"
                            className="h-10 px-3 bg-gray-900/80 border-gray-800 hover:border-violet-500/50 hover:bg-violet-500/10 text-gray-300 hover:text-white rounded-xl text-xs font-bold transition-all flex items-center gap-1"
                          >
                            {cloningId === pack.id ? <Loader2 size={13} className="animate-spin" /> : <Copy size={13} />}
                            <span className="hidden sm:inline">Clone</span>
                          </Button>
                        </>
                      )}
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    )}

      {/* ─────────────────────────────────────────────────────────────────────────────
          TAB 2: ACTIVE AUTOMATIONS & LIVE RUNS
         ───────────────────────────────────────────────────────────────────────────── */}
      {activeTab === 'installed' && (
        <div className="space-y-6 animate-in fade-in duration-200">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Activity className="text-pink-400" /> Active Automation Runs & Timeline
            </h2>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchRunsAndApprovals}
              className="bg-gray-900 border-gray-800 text-gray-300 hover:text-white rounded-xl text-xs"
            >
              Refresh Timeline
            </Button>
          </div>

          <div className="space-y-4">
            {flowRuns.length === 0 ? (
              <div className="p-12 text-center bg-gray-950/40 rounded-3xl border border-gray-800/60">
                <Compass className="h-10 w-10 text-gray-600 mx-auto mb-3" />
                <h3 className="text-base font-bold text-white">No active runs recorded yet</h3>
                <p className="text-gray-400 text-xs mt-1">
                  Install a package from the marketplace and click &quot;Run Automation&quot; to execute multi-agent pipelines.
                </p>
              </div>
            ) : (
              flowRuns.map((run) => (
                <Card
                  key={run.id}
                  className="glass-panel border-gray-800/80 rounded-2xl p-6 relative overflow-hidden space-y-4"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-gray-800/60 pb-4">
                    <div>
                      <div className="flex items-center gap-2.5">
                        <span className="font-extrabold text-white text-base">{run.flow_name}</span>
                        <span
                          className={`text-[9px] font-black uppercase px-2.5 py-0.5 rounded-full border ${
                            run.status === 'succeeded'
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                              : run.status === 'waiting_approval'
                              ? 'bg-amber-500/10 text-amber-400 border-amber-500/20 animate-pulse'
                              : run.status === 'failed'
                              ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                              : 'bg-violet-500/10 text-violet-400 border-violet-500/20'
                          }`}
                        >
                          {run.status.replace('_', ' ')}
                        </span>
                        <span className="text-[10px] bg-gray-900 border border-gray-800 text-gray-400 px-2 py-0.5 rounded-md font-bold uppercase">
                          {run.section}
                        </span>
                      </div>
                      <span className="text-xs text-gray-450 block mt-1">
                        Run ID: {run.id} • Trigger: {run.trigger_type}
                      </span>
                    </div>

                    <div className="flex items-center gap-4 text-xs font-mono text-gray-400">
                      <span>Wall Time: {run.duration_ms ? `${(run.duration_ms / 1000).toFixed(1)}s` : '-'}</span>
                      <span className="text-emerald-400 font-bold">${run.cost_usd ? run.cost_usd.toFixed(4) : '0.000'}</span>
                    </div>
                  </div>

                  {/* Step Timeline */}
                  <div className="space-y-2">
                    <span className="text-[10px] font-bold uppercase text-gray-500 tracking-wider block">
                      Execution Steps:
                    </span>
                    <div className="grid grid-cols-1 gap-2">
                      {run.steps.map((st, idx) => (
                        <div
                          key={idx}
                          className="flex items-center justify-between p-3 rounded-xl bg-gray-950/60 border border-gray-800/40 text-xs"
                        >
                          <div className="flex items-center gap-2.5">
                            {st.status === 'succeeded' ? (
                              <CheckCircle2 size={16} className="text-emerald-400 flex-shrink-0" />
                            ) : st.status === 'waiting_approval' ? (
                              <Clock size={16} className="text-amber-400 flex-shrink-0 animate-spin" />
                            ) : st.status === 'failed' ? (
                              <AlertTriangle size={16} className="text-rose-400 flex-shrink-0" />
                            ) : (
                              <Activity size={16} className="text-violet-400 flex-shrink-0" />
                            )}
                            <div>
                              <span className="font-bold text-white">{st.step_id}</span>
                              <span className="text-[10px] text-gray-400 ml-2 font-mono uppercase">
                                [{st.step_type}]
                              </span>
                            </div>
                          </div>

                          <div className="flex items-center gap-3 text-right">
                            {st.duration_ms > 0 && (
                              <span className="text-[10px] text-gray-500 font-mono">
                                {(st.duration_ms / 1000).toFixed(1)}s
                              </span>
                            )}
                            {st.cost_usd > 0 && (
                              <span className="text-[10px] text-emerald-400 font-mono">
                                ${st.cost_usd.toFixed(4)}
                              </span>
                            )}
                            <span
                              className={`text-[9px] font-bold uppercase px-2 py-0.5 rounded-md ${
                                st.status === 'succeeded'
                                  ? 'bg-emerald-500/10 text-emerald-400'
                                  : st.status === 'waiting_approval'
                                  ? 'bg-amber-500/10 text-amber-400'
                                  : 'bg-gray-800 text-gray-400'
                              }`}
                            >
                              {st.status}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </Card>
              ))
            )}
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────────────────
          TAB 3: HUMAN GOVERNANCE & APPROVAL INBOX
         ───────────────────────────────────────────────────────────────────────────── */}
      {activeTab === 'approvals' && (
        <div className="space-y-6 animate-in fade-in duration-200">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <ShieldCheck className="text-amber-400" /> Pending Governance Approval Inbox
            </h2>
            <span className="text-xs text-gray-400">
              High-risk tools (outbound emails, contract signing, external webhooks) require operator sign-off.
            </span>
          </div>

          <div className="space-y-4">
            {approvals.length === 0 ? (
              <div className="p-12 text-center bg-gray-950/40 rounded-3xl border border-gray-800/60">
                <CheckCircle2 className="h-10 w-10 text-emerald-500 mx-auto mb-3" />
                <h3 className="text-base font-bold text-white">All approval queues clear</h3>
                <p className="text-gray-400 text-xs mt-1">
                  No automated flows are currently paused awaiting human governance.
                </p>
              </div>
            ) : (
              approvals.map((appr) => (
                <Card
                  key={appr.id}
                  className="glass-panel border-amber-500/20 rounded-2xl p-6 relative overflow-hidden space-y-4"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-[9px] font-black uppercase tracking-widest text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20">
                          Risk: {appr.risk_level}
                        </span>
                        <h3 className="text-base font-extrabold text-white">{appr.title}</h3>
                      </div>
                      <p className="text-xs text-gray-400 mt-1">{appr.description}</p>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        onClick={() => setDecisionModalAppr(appr)}
                        className="bg-amber-600 hover:bg-amber-500 text-black font-bold h-9 rounded-xl text-xs px-4"
                      >
                        Review & Sign-Off
                      </Button>
                    </div>
                  </div>

                  <div className="p-3 bg-gray-950 rounded-xl border border-gray-800 text-xs font-mono text-gray-300 max-h-[140px] overflow-y-auto">
                    {JSON.stringify(appr.payload, null, 2)}
                  </div>
                </Card>
              ))
            )}
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────────────────
          MODAL: CONFIGURE & INSTALL PACKAGE
         ───────────────────────────────────────────────────────────────────────────── */}
      <Dialog open={!!configuringPack} onOpenChange={(open) => !open && setConfiguringPack(null)}>
        <DialogContent className="glass-panel border-pink-500/20 text-white rounded-3xl max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-white font-extrabold text-xl flex items-center gap-2">
              <span>{configuringPack?.icon}</span> Install {configuringPack?.name}
            </DialogTitle>
          </DialogHeader>

          {configuringPack && (
            <div className="space-y-4 py-3">
              <p className="text-xs text-gray-300 leading-relaxed">{configuringPack.desc}</p>

              {/* Target Section Notice */}
              <div className="p-3 bg-gray-900/60 rounded-xl border border-gray-800 flex items-center justify-between text-xs">
                <span className="text-gray-400">Target Operating Section:</span>
                <span className="font-bold text-pink-400 uppercase">{configuringPack.section}</span>
              </div>

              {/* Permissions & Scopes Summary */}
              <div className="p-3 bg-violet-950/20 border border-violet-500/20 rounded-xl space-y-1.5">
                <span className="text-[10px] font-bold uppercase text-violet-400 block">
                  Permissions & Capabilities Requested:
                </span>
                <div className="text-[11px] text-gray-300 space-y-1">
                  <div className="flex items-center gap-1.5">
                    <Check size={12} className="text-emerald-400" />
                    <span>Read verified company knowledge and prospect data</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Check size={12} className="text-emerald-400" />
                    <span>Execute external web research and intent verification</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <ShieldAlert size={12} className="text-amber-400" />
                    <span>Outbound emails protected behind human approval gate</span>
                  </div>
                </div>
              </div>

              {/* Configuration Inputs */}
              {Object.keys(configuringPack.config_schema || {}).length > 0 && (
                <div className="space-y-3 pt-2">
                  <span className="text-xs font-bold text-gray-400 uppercase block">Configuration Settings:</span>
                  {Object.entries(configuringPack.config_schema).map(([key, schema]: [string, any]) => (
                    <div key={key} className="space-y-1">
                      <label className="text-xs text-gray-300 font-medium block">
                        {schema.label || key}
                      </label>
                      <Input
                        defaultValue={schema.default || ''}
                        onChange={(e) =>
                          setInstallConfig((prev) => ({ ...prev, [key]: e.target.value }))
                        }
                        className="bg-gray-900 border-gray-800 text-white rounded-xl text-xs h-9"
                      />
                    </div>
                  ))}
                </div>
              )}

              <Button
                onClick={handleInstallPack}
                disabled={installing}
                className="w-full bg-pink-600 hover:bg-pink-500 text-white font-bold h-10 rounded-xl mt-4 shadow-lg shadow-pink-500/20"
              >
                {installing ? <Loader2 size={14} className="animate-spin mr-2" /> : null}
                Confirm & Activate Package
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ─────────────────────────────────────────────────────────────────────────────
          MODAL: TRIGGER AUTOMATION RUN
         ───────────────────────────────────────────────────────────────────────────── */}
      <Dialog open={!!runModalPack} onOpenChange={(open) => !open && setRunModalPack(null)}>
        <DialogContent className="glass-panel border-violet-500/20 text-white rounded-3xl max-w-md">
          <DialogHeader>
            <DialogTitle className="text-white font-extrabold text-xl flex items-center gap-2">
              <Play className="text-violet-400" /> Run {runModalPack?.name}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-3">
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-gray-400 uppercase">Input Payload (JSON)</label>
                <div className="flex items-center gap-2">
                  {runModalPack?.sample_input && (
                    <button
                      type="button"
                      onClick={() => setRunInputJson(JSON.stringify(runModalPack.sample_input, null, 2))}
                      className="text-[10px] text-pink-400 hover:text-pink-300 font-bold underline cursor-pointer"
                    >
                      Reset Sample
                    </button>
                  )}
                  <span className="text-[10px] text-emerald-400 font-bold bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                    ✨ Pre-Populated
                  </span>
                </div>
              </div>
              <p className="text-[11px] text-gray-400">
                Pre-populated with realistic test inputs for {runModalPack?.name}. You can edit any parameter before triggering.
              </p>
              <Textarea
                value={runInputJson}
                onChange={(e) => setRunInputJson(e.target.value)}
                className="bg-gray-900 border-gray-800 text-white text-xs font-mono min-h-[160px] rounded-xl focus:border-violet-500"
              />
            </div>

            <Button
              onClick={handleTriggerRun}
              disabled={triggeringRun}
              className="w-full bg-violet-600 hover:bg-violet-500 text-white font-bold h-10 rounded-xl shadow-lg shadow-violet-500/20"
            >
              {triggeringRun ? <Loader2 size={14} className="animate-spin mr-2" /> : null}
              Trigger Autonomous Execution
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ─────────────────────────────────────────────────────────────────────────────
          MODAL: APPROVAL REVIEW & SIGN-OFF
         ───────────────────────────────────────────────────────────────────────────── */}
      <Dialog open={!!decisionModalAppr} onOpenChange={(open) => !open && setDecisionModalAppr(null)}>
        <DialogContent className="glass-panel border-amber-500/20 text-white rounded-3xl max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-white font-extrabold text-xl flex items-center gap-2">
              <ShieldCheck className="text-amber-400" /> Human Approval Sign-Off
            </DialogTitle>
          </DialogHeader>

          {decisionModalAppr && (
            <div className="space-y-4 py-3">
              <div>
                <h4 className="font-extrabold text-white text-sm">{decisionModalAppr.title}</h4>
                <p className="text-xs text-gray-400 mt-0.5">{decisionModalAppr.description}</p>
              </div>

              <div className="space-y-1">
                <span className="text-[10px] font-bold text-gray-400 uppercase">Execution Data Review</span>
                <div className="p-3 bg-gray-950 rounded-xl border border-gray-800 text-xs font-mono text-gray-200 max-h-[160px] overflow-y-auto">
                  {JSON.stringify(decisionModalAppr.payload, null, 2)}
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold text-gray-400 uppercase">
                  Rejection Reason (if declining)
                </label>
                <Input
                  placeholder="Optional feedback..."
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  className="bg-gray-900 border-gray-800 text-white text-xs h-9 rounded-xl"
                />
              </div>

              <div className="flex gap-3 pt-2">
                <Button
                  onClick={() => handleApprovalDecision('reject')}
                  disabled={decidingAppr}
                  className="flex-1 bg-transparent border border-rose-900/40 text-rose-400 hover:bg-rose-950/20 font-bold h-10 rounded-xl text-xs"
                >
                  Reject & Halt
                </Button>
                <Button
                  onClick={() => handleApprovalDecision('approve')}
                  disabled={decidingAppr}
                  className="flex-1 bg-amber-500 hover:bg-amber-400 text-black font-extrabold h-10 rounded-xl text-xs shadow-lg shadow-amber-500/20"
                >
                  {decidingAppr ? <Loader2 size={14} className="animate-spin mr-1" /> : null}
                  Approve & Resume Flow
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ─────────────────────────────────────────────────────────────────────────────
          MODAL: CREATE CUSTOM PACKAGE
         ───────────────────────────────────────────────────────────────────────────── */}
      <Dialog open={isCreatePackOpen} onOpenChange={setIsCreatePackOpen}>
        <DialogContent className="glass-panel border-pink-500/20 text-white rounded-3xl max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-white font-extrabold text-xl flex items-center gap-2">
              <Plus className="text-pink-400" /> Create & Publish Custom Package
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-3">
            <div className="space-y-1">
              <label className="text-xs font-bold text-gray-400 uppercase">Package Name</label>
              <Input
                placeholder="e.g. Real Estate Lead Qualifier"
                value={newPackName}
                onChange={(e) => setNewPackName(e.target.value)}
                className="bg-gray-900 border-gray-800 text-white rounded-xl text-xs h-9"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs font-bold text-gray-400 uppercase">Target Section</label>
                <Select value={newPackSection} onValueChange={(val) => val && setNewPackSection(val)}>
                  <SelectTrigger className="bg-gray-900 border-gray-800 text-white rounded-xl text-xs h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-gray-900 border-gray-800 text-white">
                    <SelectItem value="sales">Sales CRM</SelectItem>
                    <SelectItem value="marketing">Marketing</SelectItem>
                    <SelectItem value="support">Support</SelectItem>
                    <SelectItem value="hr">HR & Hiring</SelectItem>
                    <SelectItem value="finance">Finance</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <label className="text-xs font-bold text-gray-400 uppercase">Category</label>
                <Input
                  placeholder="e.g. Property Tech"
                  value={newPackCategory}
                  onChange={(e) => setNewPackCategory(e.target.value)}
                  className="bg-gray-900 border-gray-800 text-white rounded-xl text-xs h-9"
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-bold text-gray-400 uppercase">Package Description</label>
              <Textarea
                placeholder="What does this autonomous flow automate?"
                value={newPackDesc}
                onChange={(e) => setNewPackDesc(e.target.value)}
                className="bg-gray-900 border-gray-800 text-white text-xs min-h-[80px] rounded-xl"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-bold text-gray-400 uppercase">Features (one per line)</label>
              <Textarea
                placeholder="Autonomous property valuation&#10;Lead contact scoring&#10;Email sequence dispatch"
                value={newPackFeatures}
                onChange={(e) => setNewPackFeatures(e.target.value)}
                className="bg-gray-900 border-gray-800 text-white text-xs min-h-[70px] rounded-xl"
              />
            </div>

            <Button
              onClick={handleCreatePackage}
              disabled={savingNewPack}
              className="w-full bg-pink-600 hover:bg-pink-500 text-white font-bold h-10 rounded-xl mt-2 shadow-lg shadow-pink-500/20"
            >
              {savingNewPack ? <Loader2 size={14} className="animate-spin mr-2" /> : null}
              Publish Package to Workspace
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
