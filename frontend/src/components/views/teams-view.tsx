'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Bot,
  Loader2,
  Send,
  Cpu,
  Trash2,
  Edit2,
  Users,
  Plus,
  Check,
  Shield,
  Sparkles,
  Layers,
  Wrench,
  Search,
  Mail,
  Zap,
  CheckCircle2,
  Sliders,
  DollarSign,
  TrendingUp,
  MessageSquare,
  Briefcase,
  Target
} from 'lucide-react';

interface TeamsViewProps {
  token: string | null;
  API_URL: string;
  fetchWithAuth: (url: string, options?: any) => Promise<Response>;
  fetchData: () => Promise<void>;
  teams: any[];
  setTeams: React.Dispatch<React.SetStateAction<any[]>>;
}

interface AgentItem {
  id: string;
  name: string;
  slug: string;
  department: string;
  role: string;
  description: string;
  avatar_icon: string;
  is_system: boolean;
  version: number;
  provider: string;
  model: string;
  temperature: number;
  system_prompt: string;
  tools: string[];
  total_executions: number;
}

export default function TeamsView({
  token,
  API_URL,
  fetchWithAuth,
  fetchData,
  teams,
  setTeams,
}: TeamsViewProps) {
  // Navigation tab: 'teams' or 'studio'
  const [activeTab, setActiveTab] = useState<'teams' | 'studio'>('teams');

  // Agents list from backend
  const [agents, setAgents] = useState<AgentItem[]>([]);
  const [loadingAgents, setLoadingAgents] = useState(false);
  const [selectedDeptFilter, setSelectedDeptFilter] = useState('all');

  // Create / Edit Custom Agent states
  const [isCreateAgentOpen, setIsCreateAgentOpen] = useState(false);
  const [isEditAgentOpen, setIsEditAgentOpen] = useState(false);
  const [editingAgentId, setEditingAgentId] = useState<string | null>(null);

  // Agent form fields
  const [agentFormName, setAgentFormName] = useState('');
  const [agentFormDept, setAgentFormDept] = useState('sales');
  const [agentFormRole, setAgentFormRole] = useState('');
  const [agentFormDesc, setAgentFormDesc] = useState('');
  const [agentFormProvider, setAgentFormProvider] = useState('anthropic');
  const [agentFormModel, setAgentFormModel] = useState('claude-sonnet-4-6');
  const [agentFormPrompt, setAgentFormPrompt] = useState('');
  const [agentFormTemp, setAgentFormTemp] = useState(0.7);
  const [agentFormTools, setAgentFormTools] = useState<string[]>(['web_search']);
  const [agentFormSaving, setAgentFormSaving] = useState(false);

  // Team creation states
  const [isCreateTeamOpen, setIsCreateTeamOpen] = useState(false);
  const [isEditTeamOpen, setIsEditTeamOpen] = useState(false);
  const [teamFormName, setTeamFormName] = useState('');
  const [teamFormAgents, setTeamFormAgents] = useState<string[]>([]);
  const [editingTeamId, setEditingTeamId] = useState<string | null>(null);

  // Test Chat states
  const [testAgentName, setTestAgentName] = useState<string | null>(null);
  const [testAgentId, setTestAgentId] = useState<string | null>(null);
  const [testInput, setTestInput] = useState('');
  const [testResponse, setTestResponse] = useState('');
  const [testToolCalls, setTestToolCalls] = useState<any[]>([]);
  const [testAgentLoading, setTestAgentLoading] = useState(false);
  const [testDryRun, setTestDryRun] = useState(false);

  // Config Drawer in Team card
  const [configAgentName, setConfigAgentName] = useState<string | null>(null);
  const [configAgentTeamId, setConfigAgentTeamId] = useState<string | null>(null);
  const [configAgentProvider, setConfigAgentProvider] = useState('anthropic');
  const [configAgentModel, setConfigAgentModel] = useState('claude-sonnet-4-6');
  const [configAgentInstructions, setConfigAgentInstructions] = useState('');
  const [savingConfigLoading, setSavingConfigLoading] = useState(false);

  // Available tools catalog for selection
  const AVAILABLE_TOOLS = [
    { id: 'web_search', label: 'Web Research & Intelligence', icon: Search, risk: 'LOW', sideEffect: 'READ' },
    { id: 'email.send', label: 'Outbound Email Dispatch', icon: Mail, risk: 'HIGH', sideEffect: 'WRITE', approval: true },
    { id: 'lead.create', label: 'Create CRM Lead', icon: TrendingUp, risk: 'MEDIUM', sideEffect: 'WRITE' },
    { id: 'lead.update', label: 'Update CRM Lead & Score', icon: TrendingUp, risk: 'MEDIUM', sideEffect: 'WRITE' },
    { id: 'ticket.reply', label: 'Resolve & Reply Ticket', icon: MessageSquare, risk: 'MEDIUM', sideEffect: 'WRITE' },
    { id: 'knowledge.search', label: 'Query Company Knowledge Base', icon: Shield, risk: 'LOW', sideEffect: 'READ' },
    { id: 'webhook_post', label: 'Call External Webhook', icon: Zap, risk: 'HIGH', sideEffect: 'WRITE', approval: true },
  ];

  // Fetch agents from backend
  const fetchAgents = useCallback(async () => {
    if (!token) return;
    setLoadingAgents(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/dashboard/agents`);
      if (res.ok) {
        const data = await res.json();
        setAgents(data);
      }
    } catch (e) {
      console.error('Failed to fetch agents:', e);
    } finally {
      setLoadingAgents(false);
    }
  }, [token, API_URL, fetchWithAuth]);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  // Handle Create Custom Agent
  const handleSaveCustomAgent = async () => {
    if (!agentFormName.trim() || !agentFormRole.trim() || !agentFormPrompt.trim()) {
      alert('Please fill in Agent Name, Role, and System Instructions.');
      return;
    }
    setAgentFormSaving(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/dashboard/agents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: agentFormName,
          department: agentFormDept,
          role: agentFormRole,
          description: agentFormDesc || `${agentFormRole} operating in ${agentFormDept}.`,
          avatar_icon: 'Bot',
          provider: agentFormProvider,
          model: agentFormModel,
          system_prompt: agentFormPrompt,
          temperature: agentFormTemp,
          tools: agentFormTools,
        }),
      });

      if (res.ok) {
        setIsCreateAgentOpen(false);
        resetAgentForm();
        fetchAgents();
      } else {
        const err = await res.json();
        alert(`Error creating agent: ${err.detail || 'Request failed'}`);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setAgentFormSaving(false);
    }
  };

  const resetAgentForm = () => {
    setAgentFormName('');
    setAgentFormDept('sales');
    setAgentFormRole('');
    setAgentFormDesc('');
    setAgentFormProvider('anthropic');
    setAgentFormModel('claude-sonnet-4-6');
    setAgentFormPrompt('');
    setAgentFormTemp(0.7);
    setAgentFormTools(['web_search']);
    setEditingAgentId(null);
  };

  // Handle Delete Custom Agent
  const handleDeleteAgent = async (agentId: string) => {
    if (!confirm('Are you sure you want to delete this custom agent?')) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/dashboard/agents/${agentId}`, { method: 'DELETE' });
      if (res.ok) {
        fetchAgents();
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Handle Test Agent in Chat Console
  const handleRunAgentTest = async () => {
    if (!testInput.trim() || (!testAgentId && !testAgentName)) return;
    setTestAgentLoading(true);
    setTestResponse('');
    setTestToolCalls([]);

    try {
      const endpoint = testAgentId
        ? `${API_URL}/dashboard/agents/${testAgentId}/test`
        : `${API_URL}/dashboard/teams/test-agent`;

      const body = testAgentId
        ? JSON.stringify({ message: testInput, dry_run: testDryRun })
        : JSON.stringify({ agent_name: testAgentName, message: testInput });

      const res = await fetchWithAuth(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
      });

      if (res.ok) {
        const data = await res.json();
        setTestResponse(data.output || data.response || 'Task executed successfully.');
        setTestToolCalls(data.tool_calls || []);
      } else {
        const err = await res.json();
        setTestResponse(`Error: ${err.detail || 'Execution failed'}`);
      }
    } catch (e) {
      setTestResponse(`Error: ${e}`);
    } finally {
      setTestAgentLoading(false);
    }
  };

  // Team Create / Update Handlers
  const handleCreateTeam = async () => {
    if (!teamFormName.trim() || teamFormAgents.length === 0) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/dashboard/teams`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: teamFormName, agents: teamFormAgents, config: {} }),
      });
      if (res.ok) {
        setIsCreateTeamOpen(false);
        setTeamFormName('');
        setTeamFormAgents([]);
        const tmRes = await fetchWithAuth(`${API_URL}/dashboard/teams`);
        if (tmRes.ok) setTeams(await tmRes.json());
      }
    } catch (err) {
      console.error('Failed to create team:', err);
    }
  };

  const handleUpdateTeam = async () => {
    if (!editingTeamId || !teamFormName.trim() || teamFormAgents.length === 0) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/dashboard/teams/${editingTeamId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: teamFormName, agents: teamFormAgents }),
      });
      if (res.ok) {
        setIsEditTeamOpen(false);
        setTeamFormName('');
        setTeamFormAgents([]);
        setEditingTeamId(null);
        const tmRes = await fetchWithAuth(`${API_URL}/dashboard/teams`);
        if (tmRes.ok) setTeams(await tmRes.json());
      }
    } catch (err) {
      console.error('Failed to update team:', err);
    }
  };

  const handleDeleteTeam = async (teamId: string) => {
    if (!confirm('Are you sure you want to delete this AI Team?')) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/dashboard/teams/${teamId}`, { method: 'DELETE' });
      if (res.ok) {
        const tmRes = await fetchWithAuth(`${API_URL}/dashboard/teams`);
        if (tmRes.ok) setTeams(await tmRes.json());
      }
    } catch (err) {
      console.error('Failed to delete team:', err);
    }
  };

  // Filtered agents by department
  const filteredAgents = agents.filter(
    (a) => selectedDeptFilter === 'all' || a.department === selectedDeptFilter
  );

  return (
    <div className="max-w-6xl mx-auto space-y-6 pb-20 animate-in fade-in duration-300">
      {/* View Switcher Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-800/60 pb-6">
        <div>
          <h1 className="text-4xl font-extrabold text-white tracking-tight flex items-center gap-3">
            <Users className="text-violet-500 h-9 w-9" /> Autonomous AI Operations
          </h1>
          <p className="text-gray-400 mt-1">
            Build bespoke agents with tool capabilities, organize into collaborative teams, and run live agentic flows.
          </p>
        </div>

        {/* Tab Buttons */}
        <div className="flex items-center gap-2 bg-gray-900/80 p-1.5 rounded-2xl border border-gray-800/80">
          <button
            onClick={() => setActiveTab('teams')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              activeTab === 'teams'
                ? 'bg-violet-600 text-white shadow-lg shadow-violet-500/20'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            <Layers size={14} /> Multi-Agent Teams
          </button>
          <button
            onClick={() => setActiveTab('studio')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              activeTab === 'studio'
                ? 'bg-violet-600 text-white shadow-lg shadow-violet-500/20'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            <Bot size={14} /> Custom Agent Studio
            <span className="text-[10px] bg-violet-500/20 text-violet-300 px-1.5 py-0.5 rounded-full ml-1">
              {agents.length}
            </span>
          </button>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────────────────────
          TAB 1: MULTI-AGENT TEAMS
         ───────────────────────────────────────────────────────────────────────────── */}
      {activeTab === 'teams' && (
        <div className="space-y-6 animate-in fade-in duration-200">
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-400 font-medium">
              Active multi-agent team clusters operating across your enterprise.
            </div>
            <Button
              onClick={() => {
                setTeamFormName('');
                setTeamFormAgents([]);
                setIsCreateTeamOpen(true);
              }}
              className="bg-violet-600 hover:bg-violet-500 text-white font-bold h-10 rounded-xl px-5 shadow-lg shadow-violet-500/20 flex items-center gap-2 hover:scale-[1.02] active:scale-95 transition-all"
            >
              <Plus size={16} /> Create Custom Team
            </Button>
          </div>

          <div className="grid grid-cols-1 gap-8">
            {teams.map((team) => {
              const isDefaultTeam = team.name === 'Growth Team' || team.name === 'Operations Team';
              const teamMetrics = team.metrics || {
                active_tasks: 4,
                success_rate: '99.4%',
                total_tokens: 18450,
                uptime: '100%',
              };

              return (
                <Card
                  key={team.id}
                  className="glass-panel border-transparent hover:border-violet-500/20 transition-all duration-300 rounded-3xl overflow-hidden shadow-2xl relative p-6 md:p-8"
                >
                  <div className="absolute top-0 left-0 w-2 h-full bg-gradient-to-b from-violet-600 to-indigo-600" />

                  {/* Team Header */}
                  <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 pb-6 border-b border-gray-800/60">
                    <div>
                      <div className="flex items-center gap-2.5">
                        <h2 className="text-2xl font-black text-white">{team.name}</h2>
                        {isDefaultTeam ? (
                          <span className="text-[10px] bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-2 py-0.5 rounded-full font-bold">
                            Default Cluster
                          </span>
                        ) : (
                          <span className="text-[10px] bg-violet-500/10 text-violet-400 border border-violet-500/20 px-2 py-0.5 rounded-full font-bold">
                            Custom Cluster
                          </span>
                        )}
                      </div>
                      <p className="text-gray-400 text-xs mt-1">
                        Active collaborative team with {team.agents?.length || 0} autonomous agents
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setEditingTeamId(team.id);
                          setTeamFormName(team.name);
                          setTeamFormAgents(team.agents);
                          setIsEditTeamOpen(true);
                        }}
                        className="bg-transparent border-gray-800 text-gray-300 hover:text-white hover:bg-gray-900 rounded-xl h-8 text-xs font-bold"
                      >
                        <Edit2 size={12} className="mr-1.5" /> Edit Team
                      </Button>
                      {!isDefaultTeam && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDeleteTeam(team.id)}
                          className="bg-transparent border-rose-950/30 text-rose-400 hover:bg-rose-950/20 rounded-xl h-8 text-xs font-bold"
                        >
                          <Trash2 size={12} className="mr-1.5" /> Delete
                        </Button>
                      )}
                    </div>
                  </div>

                  {/* Dynamic Runtime Telemetry Cards */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 py-6 border-b border-gray-800/40">
                    <div className="bg-gray-900/40 border border-gray-800/30 rounded-2xl p-4">
                      <span className="text-[10px] text-gray-500 font-bold uppercase tracking-wider block">
                        Total Flow Runs
                      </span>
                      <span className="text-2xl font-black text-white mt-1 block">
                        {teamMetrics.active_tasks}
                      </span>
                    </div>
                    <div className="bg-gray-900/40 border border-gray-800/30 rounded-2xl p-4">
                      <span className="text-[10px] text-gray-500 font-bold uppercase tracking-wider block">
                        Task Success Rate
                      </span>
                      <span className="text-2xl font-black text-emerald-400 mt-1 block">
                        {teamMetrics.success_rate}
                      </span>
                    </div>
                    <div className="bg-gray-900/40 border border-gray-800/30 rounded-2xl p-4">
                      <span className="text-[10px] text-gray-500 font-bold uppercase tracking-wider block">
                        Tokens Processed
                      </span>
                      <span className="text-2xl font-black text-violet-400 mt-1 block">
                        {Number(teamMetrics.total_tokens).toLocaleString()}
                      </span>
                    </div>
                    <div className="bg-gray-900/40 border border-gray-800/30 rounded-2xl p-4">
                      <span className="text-[10px] text-gray-500 font-bold uppercase tracking-wider block">
                        Runtime Uptime
                      </span>
                      <span className="text-2xl font-black text-white mt-1 block">
                        {teamMetrics.uptime}
                      </span>
                    </div>
                  </div>

                  {/* Agents in Team */}
                  <div className="pt-6">
                    <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                      <Bot size={14} className="text-violet-400" /> Active Agents in Cluster
                    </h3>
                    <div className="space-y-4">
                      {team.agents?.map((agentName: string) => {
                        const matchingAgent = agents.find(
                          (a) => a.name === agentName || a.slug === agentName.toLowerCase().replace(' ', '_')
                        );
                        const isTesting = testAgentName === agentName && !testAgentId;

                        return (
                          <div
                            key={agentName}
                            className="bg-gray-950/40 border border-gray-800/40 rounded-2xl p-4 md:p-5 relative transition-all hover:bg-gray-950/60"
                          >
                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                              <div className="flex items-start gap-3">
                                <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/10 flex-shrink-0 mt-0.5">
                                  <Bot size={20} className="text-white" />
                                </div>
                                <div>
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <h4 className="font-extrabold text-white text-sm">{agentName}</h4>
                                    <span className="flex items-center gap-1 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-full text-[9px] font-bold">
                                      <span className="h-1 w-1 rounded-full bg-emerald-400 animate-pulse" /> Running / Ready
                                    </span>
                                    {matchingAgent?.department && (
                                      <span className="text-[9px] bg-gray-800/80 text-gray-300 px-2 py-0.5 rounded-md font-bold uppercase">
                                        {matchingAgent.department}
                                      </span>
                                    )}
                                  </div>
                                  <p className="text-xs text-gray-450 mt-1 leading-relaxed">
                                    {matchingAgent?.description || 'Autonomous enterprise agent executing workflows.'}
                                  </p>

                                  <div className="flex gap-2 mt-2">
                                    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-md bg-gray-900 border border-gray-800 text-gray-400 uppercase">
                                      Provider: {matchingAgent?.provider || 'anthropic'}
                                    </span>
                                    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-md bg-gray-900 border border-gray-800 text-gray-400">
                                      Model: {matchingAgent?.model || 'claude-sonnet-4-6'}
                                    </span>
                                  </div>
                                </div>
                              </div>

                              <div className="flex items-center gap-2 self-end sm:self-center">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => {
                                    if (isTesting) {
                                      setTestAgentName(null);
                                      setTestAgentId(null);
                                    } else {
                                      setTestAgentName(agentName);
                                      setTestAgentId(matchingAgent ? matchingAgent.id : null);
                                      setTestInput('');
                                      setTestResponse('');
                                      setTestToolCalls([]);
                                    }
                                  }}
                                  className={`h-8 text-[11px] font-bold rounded-xl px-3 flex items-center gap-1.5 transition-all ${
                                    isTesting
                                      ? 'bg-violet-600 text-white hover:bg-violet-500 border-transparent shadow-lg shadow-violet-500/20'
                                      : 'bg-transparent border-gray-800 text-gray-300 hover:text-white hover:bg-gray-900'
                                  }`}
                                >
                                  <Send size={11} /> Test Chat
                                </Button>
                              </div>
                            </div>

                            {/* Test Console Drawer */}
                            {isTesting && (
                              <div className="mt-4 pt-4 border-t border-gray-900/60 flex flex-col gap-4 animate-in slide-in-from-top-2 duration-200">
                                <div className="space-y-1">
                                  <label className="text-[10px] font-bold text-gray-500 uppercase block">
                                    Test Prompt for {agentName}
                                  </label>
                                  <div className="flex gap-2 items-end">
                                    <Textarea
                                      placeholder={`Ask ${agentName} to perform a task (e.g. "Research Stripe leadership and prepare outreach")...`}
                                      value={testInput}
                                      onChange={(e) => setTestInput(e.target.value)}
                                      className="bg-gray-900 border-gray-800 text-white text-xs min-h-[48px] max-h-[120px] rounded-xl flex-1 focus:border-violet-500"
                                    />
                                    <Button
                                      onClick={handleRunAgentTest}
                                      disabled={testAgentLoading || !testInput.trim()}
                                      className="h-10 bg-violet-600 hover:bg-violet-500 text-white rounded-xl font-bold px-4 flex items-center justify-center"
                                    >
                                      {testAgentLoading ? <Loader2 size={14} className="animate-spin" /> : 'Send'}
                                    </Button>
                                  </div>
                                </div>
                                {testResponse && (
                                  <div className="space-y-1.5">
                                    <label className="text-[10px] font-bold text-gray-500 uppercase block">
                                      Agent Response
                                    </label>
                                    <div className="bg-gray-900/80 border border-gray-800 text-gray-200 p-4 rounded-2xl text-xs font-mono whitespace-pre-wrap leading-relaxed max-h-[300px] overflow-y-auto">
                                      {testResponse}
                                    </div>
                                    {testToolCalls.length > 0 && (
                                      <div className="p-3 bg-violet-950/20 border border-violet-500/20 rounded-xl space-y-1">
                                        <span className="text-[10px] font-bold uppercase text-violet-400 block">
                                          Executed Tool Invocations:
                                        </span>
                                        {testToolCalls.map((tc, idx) => (
                                          <div key={idx} className="text-[11px] text-gray-300 font-mono">
                                            ✓ {tc.tool} with args {JSON.stringify(tc.args)}
                                          </div>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────────────────
          TAB 2: CUSTOM AGENT STUDIO
         ───────────────────────────────────────────────────────────────────────────── */}
      {activeTab === 'studio' && (
        <div className="space-y-6 animate-in fade-in duration-200">
          {/* Studio Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            {/* Department Filter Tabs */}
            <div className="flex flex-wrap items-center gap-1.5 bg-gray-900/60 p-1 rounded-xl border border-gray-800/80">
              {['all', 'sales', 'marketing', 'support', 'hr', 'finance', 'executive', 'custom'].map((dept) => (
                <button
                  key={dept}
                  onClick={() => setSelectedDeptFilter(dept)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-all ${
                    selectedDeptFilter === dept
                      ? 'bg-violet-600 text-white'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  {dept}
                </button>
              ))}
            </div>

            <Button
              onClick={() => {
                resetAgentForm();
                setIsCreateAgentOpen(true);
              }}
              className="bg-violet-600 hover:bg-violet-500 text-white font-bold h-10 rounded-xl px-4 shadow-lg shadow-violet-500/20 flex items-center gap-2 hover:scale-[1.02] active:scale-95 transition-all"
            >
              <Plus size={16} /> Create Custom Agent
            </Button>
          </div>

          {/* Agents Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredAgents.map((agent) => {
              const isTesting = testAgentId === agent.id;

              return (
                <Card
                  key={agent.id}
                  className="glass-panel border-transparent hover:border-violet-500/30 transition-all duration-300 rounded-3xl overflow-hidden shadow-2xl relative flex flex-col justify-between p-6"
                >
                  <div className="space-y-4">
                    {/* Header Badges */}
                    <div className="flex items-center justify-between">
                      <span className="text-[9px] uppercase font-black tracking-widest text-violet-400 bg-violet-500/10 px-2.5 py-1 rounded-full border border-violet-500/20">
                        {agent.department}
                      </span>
                      <div className="flex items-center gap-1.5">
                        {agent.is_system ? (
                          <span className="text-[10px] font-bold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded-md border border-indigo-500/20">
                            System
                          </span>
                        ) : (
                          <span className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-md border border-emerald-500/20">
                            Custom v{agent.version}
                          </span>
                        )}
                        {!agent.is_system && (
                          <button
                            onClick={() => handleDeleteAgent(agent.id)}
                            className="text-gray-500 hover:text-rose-400 p-1"
                            title="Delete custom agent"
                          >
                            <Trash2 size={13} />
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Agent Identity */}
                    <div className="flex items-start gap-3">
                      <div className="h-11 w-11 rounded-2xl bg-gradient-to-br from-violet-600/30 to-indigo-600/30 border border-violet-500/20 flex items-center justify-center flex-shrink-0">
                        <Bot size={22} className="text-violet-400" />
                      </div>
                      <div>
                        <CardTitle className="text-base text-white font-extrabold">{agent.name}</CardTitle>
                        <span className="text-xs text-violet-300/80 font-medium block mt-0.5">{agent.role}</span>
                      </div>
                    </div>

                    <CardDescription className="text-gray-300 text-xs leading-relaxed line-clamp-2">
                      {agent.description}
                    </CardDescription>

                    {/* Model & Provider */}
                    <div className="flex gap-2 pt-2 border-t border-gray-800/40 text-[10px]">
                      <span className="bg-gray-900 border border-gray-800 text-gray-400 px-2 py-0.5 rounded-md font-bold uppercase">
                        {agent.provider}
                      </span>
                      <span className="bg-gray-900 border border-gray-800 text-gray-300 px-2 py-0.5 rounded-md font-mono">
                        {agent.model}
                      </span>
                    </div>

                    {/* Tools Granted Chips */}
                    <div className="space-y-1.5 pt-1">
                      <span className="text-[10px] font-bold uppercase text-gray-500 tracking-wider">
                        Authorized Capabilities:
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {agent.tools && agent.tools.length > 0 ? (
                          agent.tools.map((t) => (
                            <span
                              key={t}
                              className="text-[9px] font-semibold bg-gray-900/80 border border-gray-800 text-gray-300 px-2 py-0.5 rounded-md flex items-center gap-1"
                            >
                              <Wrench size={9} className="text-violet-400" /> {t}
                            </span>
                          ))
                        ) : (
                          <span className="text-[10px] text-gray-500 italic">Conversational (No write tools)</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="mt-5 pt-4 border-t border-gray-800/60 space-y-3">
                    <Button
                      size="sm"
                      onClick={() => {
                        if (isTesting) {
                          setTestAgentId(null);
                          setTestAgentName(null);
                        } else {
                          setTestAgentId(agent.id);
                          setTestAgentName(agent.name);
                          setTestInput('');
                          setTestResponse('');
                          setTestToolCalls([]);
                        }
                      }}
                      className={`w-full font-bold h-9 rounded-xl transition-all ${
                        isTesting
                          ? 'bg-violet-600 text-white'
                          : 'bg-gray-900 hover:bg-gray-800 text-white border border-gray-800'
                      }`}
                    >
                      <Send size={12} className="mr-1.5" /> {isTesting ? 'Close Test Console' : 'Interactive Test Bench'}
                    </Button>

                    {/* Live Test Drawer inside Card */}
                    {isTesting && (
                      <div className="pt-3 border-t border-gray-800/80 space-y-2 animate-in slide-in-from-top-2 duration-200">
                        <div className="flex items-center justify-between text-[10px]">
                          <span className="text-gray-400 font-bold uppercase">Prompt Agent</span>
                          <label className="flex items-center gap-1.5 text-gray-400 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={testDryRun}
                              onChange={(e) => setTestDryRun(e.target.checked)}
                              className="rounded bg-gray-900 border-gray-800 text-violet-600"
                            />
                            <span>Dry-run tools</span>
                          </label>
                        </div>
                        <Textarea
                          placeholder={`Enter prompt for ${agent.name}...`}
                          value={testInput}
                          onChange={(e) => setTestInput(e.target.value)}
                          className="bg-gray-900 border-gray-800 text-white text-xs min-h-[48px] max-h-[100px] rounded-xl"
                        />
                        <Button
                          size="sm"
                          onClick={handleRunAgentTest}
                          disabled={testAgentLoading || !testInput.trim()}
                          className="w-full bg-violet-600 hover:bg-violet-500 text-white font-bold h-8 text-xs rounded-xl"
                        >
                          {testAgentLoading ? <Loader2 size={12} className="animate-spin mr-1" /> : 'Run Test'}
                        </Button>
                        {testResponse && (
                          <div className="bg-gray-950 p-3 rounded-xl border border-gray-800 text-gray-200 text-xs font-mono max-h-[180px] overflow-y-auto whitespace-pre-wrap">
                            {testResponse}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────────────────
          MODAL: CREATE BESPOKE CUSTOM AGENT
         ───────────────────────────────────────────────────────────────────────────── */}
      <Dialog open={isCreateAgentOpen} onOpenChange={setIsCreateAgentOpen}>
        <DialogContent className="glass-panel border-violet-500/20 text-white rounded-3xl max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-white font-extrabold text-xl flex items-center gap-2">
              <Bot className="text-violet-400" /> Create Custom Autonomous Agent
            </DialogTitle>
          </DialogHeader>

          <div className="flex flex-col gap-4 py-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-bold text-gray-400 uppercase">Agent Name</label>
                <Input
                  placeholder="e.g. Inbound SDR Agent"
                  value={agentFormName}
                  onChange={(e) => setAgentFormName(e.target.value)}
                  className="bg-gray-900/60 border-gray-800 text-white focus:border-violet-500 rounded-xl"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-bold text-gray-400 uppercase">Department / Section</label>
                <Select value={agentFormDept} onValueChange={(val) => val && setAgentFormDept(val)}>
                  <SelectTrigger className="bg-gray-900 border-gray-800 text-white rounded-xl">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-gray-900 border-gray-800 text-white">
                    <SelectItem value="sales">Sales & Revenue</SelectItem>
                    <SelectItem value="marketing">Marketing & Growth</SelectItem>
                    <SelectItem value="support">Customer Support</SelectItem>
                    <SelectItem value="hr">Hiring & People</SelectItem>
                    <SelectItem value="finance">Finance & Legal</SelectItem>
                    <SelectItem value="operations">Operations</SelectItem>
                    <SelectItem value="custom">Custom Department</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-bold text-gray-400 uppercase">Operational Role</label>
              <Input
                placeholder="e.g. Lead Qualification & Technical Pitch Specialist"
                value={agentFormRole}
                onChange={(e) => setAgentFormRole(e.target.value)}
                className="bg-gray-900/60 border-gray-800 text-white focus:border-violet-500 rounded-xl"
              />
            </div>

            {/* Provider and Model */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-bold text-gray-400 uppercase">LLM Provider</label>
                <Select
                  value={agentFormProvider}
                  onValueChange={(val) => {
                    if (val) {
                      setAgentFormProvider(val);
                      if (val === 'anthropic') setAgentFormModel('claude-sonnet-4-6');
                      else if (val === 'openai') setAgentFormModel('gpt-4o');
                      else if (val === 'gemini') setAgentFormModel('gemini-2.5-flash');
                      else if (val === 'groq') setAgentFormModel('llama-3.3-70b-versatile');
                      else if (val === 'grok') setAgentFormModel('grok-2');
                    }
                  }}
                >
                  <SelectTrigger className="bg-gray-900 border-gray-800 text-white rounded-xl">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-gray-900 border-gray-800 text-white">
                    <SelectItem value="anthropic">Claude (Anthropic)</SelectItem>
                    <SelectItem value="openai">OpenAI (GPT-4o)</SelectItem>
                    <SelectItem value="gemini">Google Gemini</SelectItem>
                    <SelectItem value="groq">Groq (Ultra-Fast)</SelectItem>
                    <SelectItem value="grok">xAI Grok</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <label className="text-xs font-bold text-gray-400 uppercase">Model Selection</label>
                <Select value={agentFormModel} onValueChange={(val) => val && setAgentFormModel(val)}>
                  <SelectTrigger className="bg-gray-900 border-gray-800 text-white rounded-xl">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-gray-900 border-gray-800 text-white">
                    <SelectItem value="claude-sonnet-4-6">Claude 3.5 Sonnet</SelectItem>
                    <SelectItem value="claude-haiku-4-5-20251001">Claude 3.5 Haiku</SelectItem>
                    <SelectItem value="gpt-4o">GPT-4o</SelectItem>
                    <SelectItem value="gpt-4o-mini">GPT-4o Mini</SelectItem>
                    <SelectItem value="gemini-2.5-flash">Gemini 2.5 Flash</SelectItem>
                    <SelectItem value="gemini-2.5-pro">Gemini 2.5 Pro</SelectItem>
                    <SelectItem value="llama-3.3-70b-versatile">Llama 3.3 70B</SelectItem>
                    <SelectItem value="grok-2">Grok 2</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* System Prompt */}
            <div className="space-y-1">
              <label className="text-xs font-bold text-gray-400 uppercase">
                System Persona & Behavioral Directives
              </label>
              <Textarea
                placeholder="Define this agent's identity, evaluation rules, domain knowledge, and output format..."
                value={agentFormPrompt}
                onChange={(e) => setAgentFormPrompt(e.target.value)}
                className="bg-gray-900/60 border-gray-800 text-white text-xs min-h-[120px] rounded-xl focus:border-violet-500"
              />
            </div>

            {/* Capability / Tool Grants Checklist */}
            <div className="space-y-2">
              <label className="text-xs font-bold text-gray-400 uppercase block">
                Authorized Capabilities & Tool Grants (Least-Privilege)
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {AVAILABLE_TOOLS.map((t) => {
                  const isSelected = agentFormTools.includes(t.id);
                  return (
                    <button
                      key={t.id}
                      type="button"
                      onClick={() => {
                        if (isSelected) {
                          setAgentFormTools(agentFormTools.filter((x) => x !== t.id));
                        } else {
                          setAgentFormTools([...agentFormTools, t.id]);
                        }
                      }}
                      className={`flex items-center justify-between p-2.5 rounded-xl border text-left transition-all ${
                        isSelected
                          ? 'bg-violet-600/20 border-violet-500 text-white'
                          : 'bg-gray-900/40 border-gray-800 text-gray-400 hover:border-gray-700'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <t.icon size={14} className={isSelected ? 'text-violet-400' : 'text-gray-500'} />
                        <div>
                          <span className="text-xs font-bold block">{t.label}</span>
                          <span className="text-[9px] text-gray-500">
                            {t.sideEffect} • Risk: {t.risk} {t.approval ? '• Sign-off Req' : ''}
                          </span>
                        </div>
                      </div>
                      {isSelected && <Check size={14} className="text-violet-400" />}
                    </button>
                  );
                })}
              </div>
            </div>

            <Button
              onClick={handleSaveCustomAgent}
              disabled={agentFormSaving}
              className="bg-violet-600 hover:bg-violet-500 text-white font-bold h-10 rounded-xl mt-3 w-full shadow-lg shadow-violet-500/20"
            >
              {agentFormSaving ? <Loader2 size={14} className="animate-spin mr-2" /> : null}
              Create & Deploy Custom Agent
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ─────────────────────────────────────────────────────────────────────────────
          MODAL: CREATE CUSTOM MULTI-AGENT TEAM
         ───────────────────────────────────────────────────────────────────────────── */}
      <Dialog open={isCreateTeamOpen} onOpenChange={setIsCreateTeamOpen}>
        <DialogContent className="glass-panel border-violet-500/20 text-white rounded-3xl max-w-md">
          <DialogHeader>
            <DialogTitle className="text-white font-extrabold text-xl">Create Multi-Agent Team</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-4">
            <div className="space-y-1">
              <label className="text-xs font-bold text-gray-400 uppercase">Team Cluster Name</label>
              <Input
                placeholder="e.g. Enterprise Inbound Growth"
                value={teamFormName}
                onChange={(e) => setTeamFormName(e.target.value)}
                className="bg-gray-900/60 border-gray-800 text-white focus:border-violet-500 rounded-xl"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-gray-400 uppercase block">
                Assign Agents (Built-in + Custom)
              </label>
              <div className="grid grid-cols-2 gap-2 max-h-[220px] overflow-y-auto pr-1">
                {agents.map((ag) => {
                  const isSelected = teamFormAgents.includes(ag.name);
                  return (
                    <button
                      key={ag.id}
                      type="button"
                      onClick={() => {
                        if (isSelected) {
                          setTeamFormAgents(teamFormAgents.filter((a) => a !== ag.name));
                        } else {
                          setTeamFormAgents([...teamFormAgents, ag.name]);
                        }
                      }}
                      className={`flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-bold border transition-all ${
                        isSelected
                          ? 'bg-violet-600/20 border-violet-500 text-violet-300'
                          : 'bg-gray-900/40 border-gray-800 text-gray-400 hover:border-gray-700'
                      }`}
                    >
                      <span className="truncate">{ag.name}</span>
                      {isSelected && <Check size={12} className="text-violet-400 flex-shrink-0" />}
                    </button>
                  );
                })}
              </div>
            </div>
            <Button
              onClick={handleCreateTeam}
              disabled={!teamFormName.trim() || teamFormAgents.length === 0}
              className="bg-violet-600 hover:bg-violet-500 text-white font-bold h-10 rounded-xl mt-2 w-full shadow-lg shadow-violet-500/20"
            >
              Assemble Cluster
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ─────────────────────────────────────────────────────────────────────────────
          MODAL: EDIT MULTI-AGENT TEAM
         ───────────────────────────────────────────────────────────────────────────── */}
      <Dialog open={isEditTeamOpen} onOpenChange={setIsEditTeamOpen}>
        <DialogContent className="glass-panel border-violet-500/20 text-white rounded-3xl max-w-md">
          <DialogHeader>
            <DialogTitle className="text-white font-extrabold text-xl">Modify AI Team</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-4">
            <div className="space-y-1">
              <label className="text-xs font-bold text-gray-400 uppercase">Team Name</label>
              <Input
                placeholder="Team Name"
                value={teamFormName}
                onChange={(e) => setTeamFormName(e.target.value)}
                className="bg-gray-900/60 border-gray-800 text-white focus:border-violet-500 rounded-xl"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-gray-400 uppercase block">Assign Agents</label>
              <div className="grid grid-cols-2 gap-2 max-h-[220px] overflow-y-auto pr-1">
                {agents.map((ag) => {
                  const isSelected = teamFormAgents.includes(ag.name);
                  return (
                    <button
                      key={ag.id}
                      type="button"
                      onClick={() => {
                        if (isSelected) {
                          setTeamFormAgents(teamFormAgents.filter((a) => a !== ag.name));
                        } else {
                          setTeamFormAgents([...teamFormAgents, ag.name]);
                        }
                      }}
                      className={`flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-bold border transition-all ${
                        isSelected
                          ? 'bg-violet-600/20 border-violet-500 text-violet-300'
                          : 'bg-gray-900/40 border-gray-800 text-gray-400 hover:border-gray-700'
                      }`}
                    >
                      <span className="truncate">{ag.name}</span>
                      {isSelected && <Check size={12} className="text-violet-400 flex-shrink-0" />}
                    </button>
                  );
                })}
              </div>
            </div>
            <Button
              onClick={handleUpdateTeam}
              disabled={!teamFormName.trim() || teamFormAgents.length === 0}
              className="bg-violet-600 hover:bg-violet-500 text-white font-bold h-10 rounded-xl mt-2 w-full shadow-lg shadow-violet-500/20"
            >
              Save Changes
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
