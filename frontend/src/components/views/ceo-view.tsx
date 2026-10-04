'use client';

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Target, Plus, Loader2, Check, Play, Zap, Sparkles,
  Shield, AlertTriangle, Activity, BarChart3, Pause,
  RefreshCw, XCircle, ArrowRight, Eye, CheckCircle2,
  FileText, Users, DollarSign, Layers, ChevronRight
} from 'lucide-react';

interface CEOViewProps {
  token: string | null;
  API_URL: string;
  fetchWithAuth: (url: string, options?: any) => Promise<Response>;
  fetchData: () => Promise<void>;
  timeline: any[];
  setActiveView: (view: string) => void;
}

export default function CEOView({
  token,
  API_URL,
  fetchWithAuth,
  fetchData,
  timeline,
  setActiveView,
}: CEOViewProps) {
  // Navigation & Workflow state
  const [ceoWorkflows, setCeoWorkflows] = useState<any[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
  const [selectedWorkflow, setSelectedWorkflow] = useState<any | null>(null);

  // Executive Vitals state
  const [vitals, setVitals] = useState<any>({
    active_pipelines: 0,
    completed_pipelines: 0,
    pending_approvals_count: 0,
    total_budget_allocated: 0,
    total_budget_spent: 0,
    budget_utilization_pct: 0,
    system_status: 'HEALTHY',
    attention_items: []
  });

  // Strategy Formulation & Multi-Variant Plans state
  const [objectivePrompt, setObjectivePrompt] = useState('');
  const [budgetCapInput, setBudgetCapInput] = useState('25000');
  const [isCompiling, setIsCompiling] = useState(false);
  const [availablePlans, setAvailablePlans] = useState<any[]>([]);
  const [activeVariantTab, setActiveVariantTab] = useState<'AGGRESSIVE' | 'BALANCED' | 'CONSERVATIVE'>('BALANCED');
  const [selectedPlanDetails, setSelectedPlanDetails] = useState<any | null>(null);

  // Dry Run Simulation state
  const [isDryRunning, setIsDryRunning] = useState(false);
  const [dryRunResult, setDryRunResult] = useState<any | null>(null);
  const [showDryRunModal, setShowDryRunModal] = useState(false);

  // Execution & Live Stream state
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionProjection, setExecutionProjection] = useState<any | null>(null);
  const [liveStreamEvents, setLiveStreamEvents] = useState<any[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // Boardroom & Post-Mortem state
  const [isEscalating, setIsEscalating] = useState(false);
  const [escalationSuccess, setEscalationSuccess] = useState<string | null>(null);
  const [postMortemBrief, setPostMortemBrief] = useState<any | null>(null);
  const [showPostMortemModal, setShowPostMortemModal] = useState(false);
  const [isGeneratingBrief, setIsGeneratingBrief] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const sseRef = useRef<EventSource | null>(null);

  // 1. Initial Load: Fetch Vitals & Workflows
  useEffect(() => {
    if (token) {
      fetchVitals();
      fetchCeoWorkflows();
    }
  }, [token]);

  // 2. Refresh workflow details & plan versions on selection
  useEffect(() => {
    if (selectedWorkflowId && token) {
      fetchCeoWorkflowDetails(selectedWorkflowId);
      fetchWorkflowPlans(selectedWorkflowId);
      fetchWorkflowPostMortem(selectedWorkflowId);
    }
  }, [selectedWorkflowId, token]);

  // 3. Connect SSE Stream when workflow is active
  useEffect(() => {
    if (selectedWorkflowId && selectedWorkflow?.status === 'RUNNING') {
      connectEventStream(selectedWorkflowId);
    }
    return () => {
      if (sseRef.current) {
        sseRef.current.close();
      }
    };
  }, [selectedWorkflowId, selectedWorkflow?.status]);

  const fetchVitals = async () => {
    try {
      const res = await fetchWithAuth(`${API_URL}/ceo/cockpit/vitals`);
      if (res.ok) {
        const data = await res.json();
        setVitals(data);
      }
    } catch (e) {
      console.error('Error fetching cockpit vitals:', e);
    }
  };

  const fetchCeoWorkflows = async () => {
    try {
      const res = await fetchWithAuth(`${API_URL}/ceo/workflows`);
      if (res.ok) {
        const data = await res.json();
        setCeoWorkflows(data);
        if (data.length > 0 && !selectedWorkflowId) {
          setSelectedWorkflowId(data[0].id);
        }
      }
    } catch (e) {
      console.error('Error fetching workflows:', e);
    }
  };

  const fetchCeoWorkflowDetails = async (wfId: string) => {
    try {
      const res = await fetchWithAuth(`${API_URL}/ceo/workflows/${wfId}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedWorkflow(data);
      }
    } catch (e) {
      console.error('Error fetching workflow details:', e);
    }
  };

  const fetchWorkflowPlans = async (wfId: string) => {
    try {
      const res = await fetchWithAuth(`${API_URL}/ceo/plans/${wfId}`);
      if (res.ok) {
        const plans = await res.json();
        setAvailablePlans(plans);
        const match = plans.find((p: any) => p.strategy_variant === activeVariantTab) || plans[0];
        if (match) {
          fetchPlanDetails(wfId, match.id);
        }
      }
    } catch (e) {
      console.error('Error fetching workflow plans:', e);
    }
  };

  const fetchPlanDetails = async (wfId: string, planVersionId: string) => {
    try {
      const res = await fetchWithAuth(`${API_URL}/ceo/plans/${wfId}/${planVersionId}`);
      if (res.ok) {
        const details = await res.json();
        setSelectedPlanDetails(details);
      }
    } catch (e) {
      console.error('Error fetching plan details:', e);
    }
  };

  const fetchWorkflowPostMortem = async (wfId: string) => {
    try {
      const res = await fetchWithAuth(`${API_URL}/ceo/workflows/${wfId}/post-mortem`);
      if (res.ok) {
        const data = await res.json();
        setPostMortemBrief(data);
      } else {
        setPostMortemBrief(null);
      }
    } catch (e) {
      setPostMortemBrief(null);
    }
  };

  const connectEventStream = (wfId: string) => {
    if (sseRef.current) {
      sseRef.current.close();
    }
    const sse = new EventSource(`${API_URL}/ceo/workflows/${wfId}/stream`);
    sse.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        setLiveStreamEvents((prev) => [payload, ...prev.slice(0, 49)]);
        // Automatically sync workflow state on tick/completion
        if (payload.event_type?.includes('workflow_') || payload.event_type?.includes('task_')) {
          fetchCeoWorkflowDetails(wfId);
          fetchVitals();
        }
      } catch (e) {
        console.error('SSE parse error:', e);
      }
    };
    sseRef.current = sse;
  };

  // Compile Multi-Plan Variants via Strategy Compiler
  const handleCompilePlans = async () => {
    if (!objectivePrompt.trim() || !selectedWorkflowId) return;
    setIsCompiling(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/ceo/compiler/compile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workflow_id: selectedWorkflowId,
          prompt: objectivePrompt,
          budget_override: parseFloat(budgetCapInput) || undefined
        })
      });
      if (res.ok) {
        const compiledPlans = await res.json();
        setAvailablePlans(compiledPlans);
        const currentMatch = compiledPlans.find((p: any) => p.strategy_variant === activeVariantTab) || compiledPlans[0];
        if (currentMatch) {
          fetchPlanDetails(selectedWorkflowId, currentMatch.id);
        }
        fetchVitals();
      }
    } catch (e) {
      console.error('Error compiling strategy plans:', e);
    } finally {
      setIsCompiling(false);
    }
  };

  // Switch Strategy Variant Tab
  const handleSelectVariant = (variant: 'AGGRESSIVE' | 'BALANCED' | 'CONSERVATIVE') => {
    setActiveVariantTab(variant);
    if (!selectedWorkflowId || availablePlans.length === 0) return;
    const match = availablePlans.find((p: any) => p.strategy_variant === variant);
    if (match) {
      fetchPlanDetails(selectedWorkflowId, match.id);
    }
  };

  // Pre-Execution Dry Run Simulation
  const handleRunDryRun = async () => {
    if (!selectedWorkflowId || !selectedPlanDetails) return;
    setIsDryRunning(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/ceo/plans/${selectedWorkflowId}/${selectedPlanDetails.id}/dry-run`, {
        method: 'POST'
      });
      if (res.ok) {
        const sim = await res.json();
        setDryRunResult(sim);
        setShowDryRunModal(true);
      }
    } catch (e) {
      console.error('Dry run failed:', e);
    } finally {
      setIsDryRunning(false);
    }
  };

  // Activate Strategy Plan
  const handleActivatePlan = async () => {
    if (!selectedWorkflowId || !selectedPlanDetails) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/ceo/plans/${selectedWorkflowId}/${selectedPlanDetails.id}/activate`, {
        method: 'POST'
      });
      if (res.ok) {
        fetchWorkflowPlans(selectedWorkflowId);
        fetchCeoWorkflowDetails(selectedWorkflowId);
      }
    } catch (e) {
      console.error('Error activating plan:', e);
    }
  };

  // Workflow Execution Controls
  const handleStartWorkflow = async () => {
    if (!selectedWorkflowId || !selectedPlanDetails) return;
    setIsExecuting(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/ceo/workflows/${selectedWorkflowId}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan_version_id: selectedPlanDetails.id })
      });
      if (res.ok) {
        fetchCeoWorkflowDetails(selectedWorkflowId);
        fetchVitals();
      }
    } catch (e) {
      console.error('Error starting workflow:', e);
    } finally {
      setIsExecuting(false);
    }
  };

  const handleTickWorkflow = async () => {
    if (!selectedWorkflowId || !selectedPlanDetails) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/ceo/workflows/${selectedWorkflowId}/tick`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan_version_id: selectedPlanDetails.id })
      });
      if (res.ok) {
        fetchCeoWorkflowDetails(selectedWorkflowId);
        fetchVitals();
      }
    } catch (e) {
      console.error('Error executing workflow tick:', e);
    }
  };

  const handlePauseWorkflow = async () => {
    if (!selectedWorkflowId) return;
    try {
      await fetchWithAuth(`${API_URL}/ceo/workflows/${selectedWorkflowId}/pause`, { method: 'POST' });
      fetchCeoWorkflowDetails(selectedWorkflowId);
    } catch (e) {
      console.error('Error pausing workflow:', e);
    }
  };

  const handleResumeWorkflow = async () => {
    if (!selectedWorkflowId) return;
    try {
      await fetchWithAuth(`${API_URL}/ceo/workflows/${selectedWorkflowId}/resume`, { method: 'POST' });
      fetchCeoWorkflowDetails(selectedWorkflowId);
    } catch (e) {
      console.error('Error resuming workflow:', e);
    }
  };

  // Escalate to Agent Boardroom
  const handleEscalateToBoardroom = async () => {
    if (!selectedWorkflowId || !selectedPlanDetails) return;
    setIsEscalating(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/ceo/plans/${selectedWorkflowId}/${selectedPlanDetails.id}/escalate-to-boardroom`, {
        method: 'POST'
      });
      if (res.ok) {
        const data = await res.json();
        setEscalationSuccess(`Escalated to Boardroom: "${data.title}"`);
        setTimeout(() => setEscalationSuccess(null), 6000);
      }
    } catch (e) {
      console.error('Error escalating to boardroom:', e);
    } finally {
      setIsEscalating(false);
    }
  };

  // Generate Board-Ready Strategic Brief / Post-Mortem
  const handleGeneratePostMortem = async () => {
    if (!selectedWorkflowId) return;
    setIsGeneratingBrief(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/ceo/workflows/${selectedWorkflowId}/generate-post-mortem`, {
        method: 'POST'
      });
      if (res.ok) {
        const brief = await res.json();
        setPostMortemBrief(brief);
        setShowPostMortemModal(true);
      }
    } catch (e) {
      console.error('Error generating strategic brief:', e);
    } finally {
      setIsGeneratingBrief(false);
    }
  };

  // Active selected node for inspection drawer
  const activeNode = useMemo(() => {
    if (!selectedNodeId || !selectedPlanDetails?.nodes) return null;
    return selectedPlanDetails.nodes.find((n: any) => n.id === selectedNodeId) || null;
  }, [selectedNodeId, selectedPlanDetails]);

  // Topological Level partition for DAG visualizer
  const dagLevels = useMemo(() => {
    if (!selectedPlanDetails?.nodes || selectedPlanDetails.nodes.length === 0) return [];
    const nodes = selectedPlanDetails.nodes;
    const levelMap: Record<string, number> = {};

    const getLevel = (nid: string, visited = new Set<string>()): number => {
      if (levelMap[nid] !== undefined) return levelMap[nid];
      if (visited.has(nid)) return 0;
      visited.add(nid);
      const node = nodes.find((n: any) => n.id === nid);
      if (!node || !node.depends_on || node.depends_on.length === 0) {
        levelMap[nid] = 0;
        return 0;
      }
      const maxParent = Math.max(...node.depends_on.map((p: string) => getLevel(p, new Set(visited))));
      levelMap[nid] = maxParent + 1;
      return maxParent + 1;
    };

    nodes.forEach((n: any) => getLevel(n.id));
    const maxLvl = Math.max(...Object.values(levelMap), 0);
    const levels: any[][] = Array.from({ length: maxLvl + 1 }, () => []);

    nodes.forEach((n: any) => {
      const lvl = levelMap[n.id] || 0;
      levels[lvl].push(n);
    });

    return levels;
  }, [selectedPlanDetails]);

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-16 font-sans text-slate-100">
      {/* 1. Reconciled Executive Vitals Strip */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-4 shadow-sm backdrop-blur">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Active Pipelines</span>
            <Activity className="h-4 w-4 text-sky-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-white">{vitals.active_pipelines}</span>
            <span className="text-xs text-slate-400">({vitals.completed_pipelines} completed)</span>
          </div>
          <p className="text-[11px] text-slate-400 mt-1">Autonomous executive DAGs in progress</p>
        </div>

        <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-4 shadow-sm backdrop-blur">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Budget Envelope</span>
            <DollarSign className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-white">${vitals.total_budget_spent.toLocaleString()}</span>
            <span className="text-xs text-slate-400">/ ${vitals.total_budget_allocated.toLocaleString()}</span>
          </div>
          <div className="w-full bg-slate-800 rounded-full h-1.5 mt-2 overflow-hidden">
            <div
              className="bg-emerald-500 h-1.5 rounded-full transition-all"
              style={{ width: `${Math.min(vitals.budget_utilization_pct, 100)}%` }}
            />
          </div>
          <p className="text-[11px] text-slate-400 mt-1">{vitals.budget_utilization_pct}% authorized capital utilized</p>
        </div>

        <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-4 shadow-sm backdrop-blur">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Governance Gates</span>
            <Shield className="h-4 w-4 text-amber-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-white">{vitals.pending_approvals_count}</span>
            <span className="text-xs text-amber-400 font-medium">Pending Approvals</span>
          </div>
          <p className="text-[11px] text-slate-400 mt-1">Dual-Key and $R3/$R4 policy checkpoints</p>
        </div>

        <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-4 shadow-sm backdrop-blur">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Control Plane Status</span>
            <span className={`h-2.5 w-2.5 rounded-full ${vitals.system_status === 'HEALTHY' ? 'bg-emerald-400' : 'bg-amber-400 animate-pulse'}`} />
          </div>
          <div className="mt-2">
            <span className={`text-base font-bold ${vitals.system_status === 'HEALTHY' ? 'text-emerald-400' : 'text-amber-400'}`}>
              {vitals.system_status === 'HEALTHY' ? 'Deterministic & Compliant' : 'Attention Required'}
            </span>
          </div>
          <p className="text-[11px] text-slate-400 mt-1">Zero unverified leakage | AST Fail-Closed</p>
        </div>
      </div>

      {escalationSuccess && (
        <div className="bg-emerald-950/40 border border-emerald-500/40 text-emerald-300 px-4 py-3 rounded-2xl text-xs flex items-center justify-between animate-in fade-in">
          <span>{escalationSuccess}</span>
          <Button size="sm" variant="ghost" onClick={() => setActiveView('boardroom')} className="text-emerald-400 font-bold hover:underline">
            Go to Boardroom →
          </Button>
        </div>
      )}

      {/* 2. Main Executive Cockpit Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Directive Compiler & Strategic Variants */}
        <div className="lg:col-span-4 space-y-6">
          <Card className="bg-slate-900/90 border-slate-800 rounded-3xl overflow-hidden shadow-lg">
            <CardHeader className="pb-3 border-b border-slate-800/60">
              <div className="flex items-center gap-2">
                <Target className="h-5 w-5 text-sky-400" />
                <CardTitle className="text-base text-white font-bold">Strategy Compiler</CardTitle>
              </div>
              <CardDescription className="text-slate-400 text-xs">
                Directives are parsed by Chief of Staff and synthesized into 3 policy-checked candidate DAGs.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 pt-4">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-slate-300">Executive Directive</label>
                <Textarea
                  placeholder="e.g. Accelerate outbound sales pipeline to reach $100k in Q4 without hiring new SDR reps"
                  value={objectivePrompt}
                  onChange={(e) => setObjectivePrompt(e.target.value)}
                  className="bg-slate-950/80 border-slate-800 text-white rounded-xl text-xs min-h-[90px] focus:border-sky-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-slate-300">Budget Envelope ($)</label>
                  <Input
                    type="number"
                    value={budgetCapInput}
                    onChange={(e) => setBudgetCapInput(e.target.value)}
                    className="bg-slate-950/80 border-slate-800 text-white text-xs rounded-xl"
                  />
                </div>
                <div className="flex flex-col justify-end">
                  <Button
                    onClick={handleCompilePlans}
                    disabled={isCompiling || !objectivePrompt.trim()}
                    className="bg-sky-600 hover:bg-sky-500 text-white font-bold text-xs h-9 rounded-xl shadow transition-all"
                  >
                    {isCompiling ? (
                      <>
                        <Loader2 className="animate-spin mr-1.5 h-3.5 w-3.5" />
                        Compiling...
                      </>
                    ) : (
                      'Compile Strategies'
                    )}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Strategy Variant Scorecard */}
          <Card className="bg-slate-900/90 border-slate-800 rounded-3xl overflow-hidden shadow-lg">
            <CardHeader className="pb-3 border-b border-slate-800/60">
              <CardTitle className="text-base text-white font-bold flex items-center justify-between">
                <span>Multi-Plan Variants</span>
                <span className="text-[10px] text-slate-400 font-normal">v{selectedPlanDetails?.version_num || 1}</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-4 space-y-4">
              {/* Variant Switcher Tabs */}
              <div className="grid grid-cols-3 gap-1 bg-slate-950/80 p-1 rounded-xl border border-slate-800">
                {(['AGGRESSIVE', 'BALANCED', 'CONSERVATIVE'] as const).map((variant) => (
                  <button
                    key={variant}
                    onClick={() => handleSelectVariant(variant)}
                    className={`py-1.5 text-[11px] font-bold rounded-lg transition-all ${
                      activeVariantTab === variant
                        ? 'bg-slate-800 text-sky-400 shadow-sm'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    {variant === 'AGGRESSIVE' ? '🚀 Aggressive' : variant === 'BALANCED' ? '⚖️ Balanced' : '🛡️ Safe'}
                  </button>
                ))}
              </div>

              {selectedPlanDetails ? (
                <div className="space-y-3">
                  <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800/80 space-y-1">
                    <span className="text-[10px] uppercase font-bold text-slate-400">Objective</span>
                    <p className="text-xs text-slate-200 line-clamp-2">{selectedPlanDetails.objective}</p>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="p-2.5 bg-slate-950/60 rounded-xl border border-slate-800/80">
                      <span className="text-[10px] text-slate-400">Estimated Budget</span>
                      <p className="font-bold text-white text-sm mt-0.5">${Number(selectedPlanDetails.estimated_budget).toLocaleString()}</p>
                    </div>
                    <div className="p-2.5 bg-slate-950/60 rounded-xl border border-slate-800/80">
                      <span className="text-[10px] text-slate-400">Fragility Score</span>
                      <p className="font-bold text-white text-sm mt-0.5">
                        {selectedPlanDetails.red_team_critique?.fragility_score ?? 0.25}
                        <span className="text-[10px] font-normal text-slate-400 ml-1">/ 1.0</span>
                      </p>
                    </div>
                  </div>

                  {/* Quant Monte Carlo Forecast Preview */}
                  {selectedPlanDetails.quant_forecast && (
                    <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800/80 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">1,000 Monte Carlo Runs</span>
                        <span className="text-[10px] text-emerald-400 font-bold">
                          {Math.round((selectedPlanDetails.quant_forecast.p_target_attainment || 0.85) * 100)}% Success
                        </span>
                      </div>
                      <div className="grid grid-cols-3 gap-1 text-center pt-1 border-t border-slate-800/60">
                        <div>
                          <span className="text-[9px] text-slate-400">P10 Baseline</span>
                          <p className="text-xs font-semibold text-slate-300">
                            ${Math.round(selectedPlanDetails.quant_forecast.p10_outcome || 0).toLocaleString()}
                          </p>
                        </div>
                        <div>
                          <span className="text-[9px] text-sky-400 font-bold">P50 Expected</span>
                          <p className="text-xs font-bold text-white">
                            ${Math.round(selectedPlanDetails.quant_forecast.p50_outcome || 0).toLocaleString()}
                          </p>
                        </div>
                        <div>
                          <span className="text-[9px] text-emerald-400">P90 Upside</span>
                          <p className="text-xs font-semibold text-slate-300">
                            ${Math.round(selectedPlanDetails.quant_forecast.p90_outcome || 0).toLocaleString()}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Action Buttons: Dry Run, Activate, Escalate */}
                  <div className="grid grid-cols-2 gap-2 pt-2">
                    <Button
                      onClick={handleRunDryRun}
                      disabled={isDryRunning}
                      variant="outline"
                      className="border-slate-700 bg-slate-800/50 hover:bg-slate-800 text-white font-bold text-xs h-9 rounded-xl"
                    >
                      {isDryRunning ? <Loader2 className="animate-spin h-3.5 w-3.5 mr-1" /> : <Eye className="h-3.5 w-3.5 mr-1" />}
                      Dry Run Check
                    </Button>
                    <Button
                      onClick={handleActivatePlan}
                      className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs h-9 rounded-xl shadow"
                    >
                      <Check className="h-3.5 w-3.5 mr-1" />
                      Set Active
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="py-8 text-center text-xs text-slate-400">
                  Select or compile a strategy to review variants.
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Interactive DAG Canvas & Real-time Live Execution */}
        <div className="lg:col-span-8 space-y-6">
          {/* Executive Cockpit Header & Execution Controls */}
          <Card className="bg-slate-900/90 border-slate-800 rounded-3xl p-5 shadow-lg relative overflow-hidden">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-sky-400 bg-sky-950/60 px-2 py-0.5 rounded border border-sky-800/50">
                    {selectedPlanDetails?.strategy_variant || 'BALANCED'} VARIANT
                  </span>
                  <span className="text-[10px] text-slate-400">Status: {selectedWorkflow?.status || 'READY'}</span>
                </div>
                <h2 className="text-lg font-bold text-white truncate mt-1">
                  {selectedWorkflow?.name || 'Active Executive Workflow'}
                </h2>
              </div>

              {/* Execution Action Triggers */}
              <div className="flex items-center gap-2 shrink-0">
                <Button
                  onClick={handleEscalateToBoardroom}
                  disabled={isEscalating}
                  variant="outline"
                  className="border-slate-700 bg-slate-800/40 hover:bg-slate-800 text-slate-300 font-bold text-xs h-9 rounded-xl"
                >
                  {isEscalating ? <Loader2 className="animate-spin h-3.5 w-3.5 mr-1" /> : <Users className="h-3.5 w-3.5 mr-1" />}
                  Boardroom Review
                </Button>

                {selectedWorkflow?.status === 'RUNNING' ? (
                  <>
                    <Button
                      onClick={handleTickWorkflow}
                      className="bg-sky-600 hover:bg-sky-500 text-white font-bold text-xs h-9 rounded-xl shadow"
                    >
                      <Play className="h-3.5 w-3.5 mr-1" />
                      Execute Tick
                    </Button>
                    <Button
                      onClick={handlePauseWorkflow}
                      variant="outline"
                      className="border-slate-700 bg-slate-800/40 hover:bg-slate-800 text-slate-300 text-xs h-9 rounded-xl"
                    >
                      <Pause className="h-3.5 w-3.5" />
                    </Button>
                  </>
                ) : selectedWorkflow?.status === 'COMPLETED' ? (
                  <Button
                    onClick={() => setShowPostMortemModal(true)}
                    className="bg-emerald-600/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-600/30 font-bold text-xs h-9 rounded-xl"
                  >
                    <FileText className="h-3.5 w-3.5 mr-1" />
                    Strategic Brief
                  </Button>
                ) : (
                  <Button
                    onClick={handleStartWorkflow}
                    disabled={isExecuting}
                    className="bg-sky-600 hover:bg-sky-500 text-white font-bold text-xs h-9 px-5 rounded-xl shadow"
                  >
                    {isExecuting ? <Loader2 className="animate-spin h-3.5 w-3.5 mr-1" /> : <Play className="h-3.5 w-3.5 mr-1" />}
                    Start Execution
                  </Button>
                )}
              </div>
            </div>
          </Card>

          {/* Interactive DAG Canvas */}
          <Card className="bg-slate-900/90 border-slate-800 rounded-3xl p-6 shadow-lg relative">
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs uppercase font-bold tracking-wider text-slate-400">
                Topological Execution Graph (DAG)
              </span>
              <span className="text-[11px] text-slate-400">
                {selectedPlanDetails?.nodes?.length || 0} policy-checked steps
              </span>
            </div>

            <div
              ref={containerRef}
              className="bg-slate-950/70 border border-slate-800/80 rounded-2xl min-h-[360px] p-6 overflow-x-auto flex justify-between gap-10 items-center"
            >
              {dagLevels.length === 0 ? (
                <div className="w-full text-center py-16 text-slate-500 text-xs">
                  No plan nodes compiled. Enter an objective and compile a strategy.
                </div>
              ) : (
                dagLevels.map((lvlNodes, lvlIdx) => (
                  <div key={lvlIdx} className="flex flex-col gap-5 items-center min-w-[170px] z-10">
                    <span className="text-[9px] uppercase font-bold text-slate-500 tracking-wider">
                      Level {lvlIdx}
                    </span>
                    {lvlNodes.map((node: any) => {
                      const isSelected = selectedNodeId === node.id;
                      const isIrreversible = node.capability_id?.includes('send') || node.capability_id?.includes('allocate');

                      return (
                        <div
                          key={node.id}
                          onClick={() => setSelectedNodeId(node.id)}
                          className={`w-48 p-3.5 rounded-2xl border transition-all cursor-pointer select-none text-left ${
                            isSelected
                              ? 'bg-slate-800 border-sky-500 shadow-md scale-[1.02]'
                              : 'bg-slate-900/80 border-slate-800 hover:border-slate-700 hover:bg-slate-800/50'
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1.5">
                            <span className="text-[8px] font-bold px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                              {node.department}
                            </span>
                            <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded ${
                              isIrreversible ? 'bg-amber-950/60 text-amber-400 border border-amber-800/40' : 'bg-slate-800 text-slate-400'
                            }`}>
                              {isIrreversible ? 'R3/R4 Gate' : 'R1 Auto'}
                            </span>
                          </div>
                          <h4 className="font-bold text-xs text-white leading-tight line-clamp-2">{node.name}</h4>
                          <span className="text-[9px] text-slate-400 mt-1 block truncate">
                            {node.capability_id}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                ))
              )}
            </div>
          </Card>

          {/* Node Inspector Drawer */}
          {activeNode && (
            <Card className="bg-slate-900/90 border-slate-800 rounded-3xl p-5 shadow-lg animate-in fade-in">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div>
                  <span className="text-[10px] uppercase font-bold text-sky-400">{activeNode.department} Node</span>
                  <h3 className="text-base font-bold text-white mt-0.5">{activeNode.name}</h3>
                </div>
                <Button size="sm" variant="ghost" onClick={() => setSelectedNodeId(null)} className="text-slate-400 text-xs">
                  Close
                </Button>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 py-3 text-xs border-b border-slate-800">
                <div>
                  <span className="text-[10px] text-slate-400">Capability</span>
                  <p className="font-bold text-white mt-0.5">{activeNode.capability_id}</p>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400">Version</span>
                  <p className="font-bold text-white mt-0.5">{activeNode.capability_version || '1.0.0'}</p>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400">Estimated Duration</span>
                  <p className="font-bold text-white mt-0.5">{activeNode.estimated_duration_seconds}s</p>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400">Compensable</span>
                  <p className="font-bold text-white mt-0.5">{activeNode.is_compensable ? 'Yes ✓' : 'No'}</p>
                </div>
              </div>
              <div className="mt-3">
                <span className="text-[10px] uppercase font-bold text-slate-400">Canonical Node Parameters</span>
                <pre className="bg-slate-950/80 p-3 rounded-xl border border-slate-800/80 text-[11px] text-slate-300 font-mono mt-1 overflow-x-auto">
                  {JSON.stringify(activeNode.parameters, null, 2)}
                </pre>
              </div>
            </Card>
          )}

          {/* Real-time SSE Live Event Stream */}
          {liveStreamEvents.length > 0 && (
            <Card className="bg-slate-900/90 border-slate-800 rounded-3xl p-5 shadow-lg">
              <span className="text-xs uppercase font-bold tracking-wider text-slate-400 block mb-3">
                Live Executive Event Stream (SSE)
              </span>
              <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                {liveStreamEvents.map((evt, idx) => (
                  <div key={idx} className="p-2.5 bg-slate-950/60 border border-slate-800/80 rounded-xl flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span className="h-1.5 w-1.5 rounded-full bg-sky-400" />
                      <span className="font-mono text-slate-300 text-[11px]">{evt.event_type}</span>
                    </div>
                    <span className="text-[10px] text-slate-500 font-mono">seq #{evt.sequence_num || evt.id?.slice(0, 6)}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* 3. Pre-Execution Dry Run Modal */}
      {showDryRunModal && dryRunResult && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <Card className="bg-slate-900 border-slate-700 max-w-2xl w-full rounded-3xl shadow-2xl p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Shield className="h-5 w-5 text-sky-400" />
                <h3 className="text-lg font-bold text-white">Pre-Execution Dry Run Simulation</h3>
              </div>
              <Button size="sm" variant="ghost" onClick={() => setShowDryRunModal(false)} className="text-slate-400">
                ✕
              </Button>
            </div>

            <div className="grid grid-cols-3 gap-3 text-xs">
              <div className="p-3 bg-slate-950/80 rounded-xl border border-slate-800">
                <span className="text-[10px] text-slate-400">Simulation Status</span>
                <p className={`font-bold mt-0.5 ${dryRunResult.simulation_status === 'PASSED' ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {dryRunResult.simulation_status}
                </p>
              </div>
              <div className="p-3 bg-slate-950/80 rounded-xl border border-slate-800">
                <span className="text-[10px] text-slate-400">Estimated Duration</span>
                <p className="font-bold text-white mt-0.5">{dryRunResult.total_estimated_duration_seconds}s</p>
              </div>
              <div className="p-3 bg-slate-950/80 rounded-xl border border-slate-800">
                <span className="text-[10px] text-slate-400">Estimated Cost</span>
                <p className="font-bold text-white mt-0.5">${dryRunResult.total_estimated_cost_usd}</p>
              </div>
            </div>

            {/* Approval Checkpoints Required */}
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                Required Governance Approval Checkpoints ({dryRunResult.approval_checkpoints_count})
              </span>
              <div className="mt-2 space-y-2">
                {dryRunResult.approval_checkpoints.map((cp: any, idx: number) => (
                  <div key={idx} className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl flex items-center justify-between text-xs">
                    <div>
                      <p className="font-bold text-white">{cp.node_name}</p>
                      <p className="text-[10px] text-slate-400">{cp.capability_id} — {cp.side_effect_class}</p>
                    </div>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-950/60 text-amber-400 border border-amber-800/40">
                      {cp.required_keys === 2 ? 'Dual-Key ($R4)' : 'Single-Key ($R3)'}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-2 flex justify-end gap-2 border-t border-slate-800">
              <Button onClick={() => setShowDryRunModal(false)} variant="outline" className="border-slate-700 text-xs">
                Dismiss
              </Button>
              <Button
                onClick={() => {
                  setShowDryRunModal(false);
                  handleActivatePlan();
                }}
                className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs"
              >
                Approve & Activate Plan
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* 4. Strategic Brief & Post-Mortem Modal */}
      {showPostMortemModal && postMortemBrief && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <Card className="bg-slate-900 border-slate-700 max-w-3xl w-full rounded-3xl shadow-2xl p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-emerald-400" />
                <h3 className="text-lg font-bold text-white">Boardroom Strategic Brief & Post-Mortem</h3>
              </div>
              <Button size="sm" variant="ghost" onClick={() => setShowPostMortemModal(false)} className="text-slate-400">
                ✕
              </Button>
            </div>

            <div className="bg-slate-950/80 p-5 rounded-2xl border border-slate-800 text-slate-300 text-xs whitespace-pre-line leading-relaxed font-sans">
              {postMortemBrief.executive_brief_markdown}
            </div>

            <div className="pt-2 flex justify-end gap-2 border-t border-slate-800">
              <Button onClick={() => setShowPostMortemModal(false)} className="bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold">
                Close Brief
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
