'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import {
  Users,
  Zap,
  MessageSquare,
  ShieldCheck,
  Scale,
  Server,
  DollarSign,
  TrendingUp,
  Database,
  Search,
  Sparkles,
  CheckCircle,
  Clock,
  AlertTriangle,
  ShieldAlert,
  Play,
  RotateCcw,
  Download,
  Check,
  X,
  ChevronDown,
  ChevronRight,
  Headphones,
  Megaphone,
  UserCheck,
  Lock,
  Activity,
  Award,
  Crown,
} from 'lucide-react';

interface CoordinationViewProps {
  token: string | null;
  API_URL: string;
  fetchWithAuth: (url: string, options?: RequestInit) => Promise<Response>;
  fetchData: () => Promise<void>;
}

interface FindingItem {
  claim: string;
  evidence_ids?: string[];
  confidence?: number;
}

interface MeetingMessage {
  sender: string;
  content: string;
  timestamp?: string;
  phase?: string;
  confidence_score?: number;
  confidence_rationale?: string;
  findings?: (string | FindingItem)[];
  assumptions?: string[];
  sources?: string[];
  quality_flags?: string[];
  stance?: 'support' | 'oppose' | 'neutral';
}

interface MeetingEvidence {
  id: string;
  meeting_id: string;
  source_ref: string;
  source_type: string;
  trust_score?: number;
  freshness_score?: number;
  reliability_score?: number;
  completeness_score?: number;
  excerpt?: string;
  created_at?: string;
}

interface MeetingAction {
  id: string;
  meeting_id?: string;
  assigned_to: string;
  description: string;
  risk_tier?: 'low' | 'medium' | 'high';
  status: 'pending' | 'awaiting_approval' | 'executing' | 'completed' | 'failed' | 'rejected';
  approved_by?: string;
  approved_at?: string;
  rejection_reason?: string;
  result?: Record<string, unknown> | null;
  sources?: string[];
  evidence_ids?: string[];
}

interface AgentMeeting {
  id: string;
  title: string;
  status: string;
  current_phase?: string;
  started_at?: string;
  finished_at?: string;
  total_tokens?: number;
  total_cost_usd?: number;
  failure_reason?: string;
  trigger_type: string;
  context_summary?: string;
  participants: string[];
  transcript: MeetingMessage[];
  action_items: MeetingAction[];
  created_at: string;
}

const PHASES_LIST = [
  { key: 'assembly', label: 'Assembly', icon: Users },
  { key: 'evidence', label: 'Evidence', icon: Database },
  { key: 'analysis', label: 'Analysis', icon: Search },
  { key: 'critique', label: 'Critique', icon: MessageSquare },
  { key: 'synthesis', label: 'Synthesis', icon: Sparkles },
  { key: 'approval', label: 'Governance', icon: ShieldCheck },
  { key: 'completed', label: 'Execution', icon: Zap },
];

export default function CoordinationView({
  token,
  API_URL,
  fetchWithAuth,
}: CoordinationViewProps) {
  const [meetings, setMeetings] = useState<AgentMeeting[]>([]);
  const [selectedMeetingId, setSelectedMeetingId] = useState<string | null>(null);
  const [selectedMeeting, setSelectedMeeting] = useState<AgentMeeting | null>(null);
  const [evidenceList, setEvidenceList] = useState<MeetingEvidence[]>([]);
  const [actionList, setActionList] = useState<MeetingAction[]>([]);
  const [actionTab, setActionTab] = useState<'awaiting' | 'completed' | 'all'>('awaiting');

  // Manual meeting dialog state
  const [isCreateMeetingOpen, setIsCreateMeetingOpen] = useState(false);
  const [manualMeetingTitle, setManualMeetingTitle] = useState('');
  const [manualMeetingTopic, setManualMeetingTopic] = useState('');
  const [manualMeetingParticipants, setManualMeetingParticipants] = useState<string[]>([]);
  const [manualMeetingLoading, setManualMeetingLoading] = useState(false);

  // Rejection modal
  const [rejectActionId, setRejectActionId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');

  // Expandable sections
  const [isEvidenceExpanded, setIsEvidenceExpanded] = useState(true);
  const [isTranscriptExpanded, setIsTranscriptExpanded] = useState(true);

  // Fetch all meetings
  const fetchMeetings = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/coordination/meetings`);
      if (res.ok) {
        const data: AgentMeeting[] = await res.json();
        setMeetings(data);
        if (!selectedMeetingId && data.length > 0) {
          setSelectedMeetingId(data[0].id);
        }
      }
    } catch (e) {
      console.error('Error fetching meetings:', e);
    }
  }, [API_URL, fetchWithAuth, token, selectedMeetingId]);

  // Fetch selected meeting details
  const fetchMeetingDetails = useCallback(async (meetingId: string) => {
    if (!token) return;
    try {
      const [resMeeting, resEv, resAct] = await Promise.all([
        fetchWithAuth(`${API_URL}/coordination/meetings/${meetingId}`),
        fetchWithAuth(`${API_URL}/coordination/meetings/${meetingId}/evidence`),
        fetchWithAuth(`${API_URL}/coordination/meetings/${meetingId}/actions`),
      ]);

      if (resMeeting.ok) {
        const data: AgentMeeting = await resMeeting.json();
        setSelectedMeeting(data);
      }
      if (resEv.ok) {
        const evData: MeetingEvidence[] = await resEv.json();
        setEvidenceList(evData);
      }
      if (resAct.ok) {
        const actData: MeetingAction[] = await resAct.json();
        setActionList(actData);
      }
    } catch (e) {
      console.error('Error fetching meeting details:', e);
    }
  }, [API_URL, fetchWithAuth, token]);

  useEffect(() => {
    if (token) {
      void fetchMeetings();
    }
  }, [fetchMeetings, token]);

  useEffect(() => {
    if (selectedMeetingId && token) {
      void fetchMeetingDetails(selectedMeetingId);
    }
  }, [selectedMeetingId, fetchMeetingDetails, token]);

  // SSE Stream with Fallback Polling
  useEffect(() => {
    if (!selectedMeetingId || !token) return;

    let eventSource: EventSource | null = null;
    let pollInterval: NodeJS.Timeout | null = null;

    const streamUrl = `${API_URL}/coordination/meetings/${selectedMeetingId}/stream`;

    try {
      eventSource = new EventSource(streamUrl);

      eventSource.onmessage = (e) => {
        try {
          const payload = JSON.parse(e.data);
          // Refresh details when significant events arrive
          if (payload.event && payload.event !== 'keep-alive') {
            void fetchMeetingDetails(selectedMeetingId);
            void fetchMeetings();
          }
        } catch {
          // ignore keepalive
        }
      };

      eventSource.onerror = () => {
        if (eventSource) {
          eventSource.close();
          eventSource = null;
        }
        if (!pollInterval && (selectedMeeting?.status === 'active' || selectedMeeting?.status === 'awaiting_approval')) {
          pollInterval = setInterval(() => {
            void fetchMeetingDetails(selectedMeetingId);
          }, 3000);
        }
      };
    } catch (err) {
      console.debug('SSE init skipped:', err);
    }

    return () => {
      if (eventSource) eventSource.close();
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [selectedMeetingId, selectedMeeting?.status, token, API_URL, fetchMeetingDetails, fetchMeetings]);

  // Create Meeting
  const handleCreateManualMeeting = async () => {
    if (!manualMeetingTitle || !manualMeetingTopic) return;
    setManualMeetingLoading(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/coordination/meetings/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: manualMeetingTitle,
          topic: manualMeetingTopic,
          participants: manualMeetingParticipants.length > 0 ? manualMeetingParticipants : undefined,
          auto_select_experts: manualMeetingParticipants.length === 0,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setManualMeetingTitle('');
        setManualMeetingTopic('');
        setIsCreateMeetingOpen(false);
        await fetchMeetings();
        if (data.id) {
          setSelectedMeetingId(data.id);
        }
      } else {
        alert(`Error: ${data.detail || 'Failed to start boardroom meeting'}`);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setManualMeetingLoading(false);
    }
  };

  // Action Governance
  const handleApproveAction = async (actionId: string) => {
    if (!selectedMeetingId) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/coordination/meetings/${selectedMeetingId}/actions/${actionId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approved_by: 'Executive Manager' }),
      });
      if (res.ok) {
        await fetchMeetingDetails(selectedMeetingId);
        await fetchMeetings();
      }
    } catch (e) {
      console.error('Approval failed:', e);
    }
  };

  const handleRejectAction = async () => {
    if (!selectedMeetingId || !rejectActionId) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/coordination/meetings/${selectedMeetingId}/actions/${rejectActionId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rejected_by: 'Executive Manager', reason: rejectReason }),
      });
      if (res.ok) {
        setRejectActionId(null);
        setRejectReason('');
        await fetchMeetingDetails(selectedMeetingId);
        await fetchMeetings();
      }
    } catch (e) {
      console.error('Rejection failed:', e);
    }
  };

  const handleCancelMeeting = async () => {
    if (!selectedMeetingId) return;
    if (!confirm('Are you sure you want to cancel this boardroom deliberation?')) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/coordination/meetings/${selectedMeetingId}/cancel`, {
        method: 'POST',
      });
      if (res.ok) {
        await fetchMeetingDetails(selectedMeetingId);
        await fetchMeetings();
      }
    } catch (e) {
      console.error('Cancel failed:', e);
    }
  };

  const handleRerunMeeting = async () => {
    if (!selectedMeetingId) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/coordination/meetings/${selectedMeetingId}/rerun`, {
        method: 'POST',
      });
      if (res.ok) {
        await fetchMeetingDetails(selectedMeetingId);
        await fetchMeetings();
      }
    } catch (e) {
      console.error('Rerun failed:', e);
    }
  };

  const handleExportMeeting = async (format: 'md' | 'json') => {
    if (!selectedMeetingId) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/coordination/meetings/${selectedMeetingId}/export?format=${format}`);
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `boardroom-${selectedMeeting?.title.toLowerCase().replace(/[^a-z0-9]/g, '-') || 'export'}.${format}`;
        a.click();
        window.URL.revokeObjectURL(url);
      }
    } catch (e) {
      console.error('Export failed:', e);
    }
  };

  // Agent Icon Resolver
  const getAgentIcon = (name: string) => {
    if (name.includes('CEO')) return Crown;
    if (name.includes('Finance') || name.includes('CFO')) return DollarSign;
    if (name.includes('Risk')) return ShieldCheck;
    if (name.includes('Legal')) return Scale;
    if (name.includes('Sales')) return TrendingUp;
    if (name.includes('Marketing')) return Megaphone;
    if (name.includes('Support')) return Headphones;
    if (name.includes('Human') || name.includes('HR')) return UserCheck;
    if (name.includes('Cyber') || name.includes('Security')) return Lock;
    if (name.includes('Operations')) return Server;
    if (name.includes('Research')) return Search;
    return Users;
  };

  // Active Phase Helper
  const currentPhaseIndex = useMemo(() => {
    const phaseKey = selectedMeeting?.current_phase || (selectedMeeting?.status === 'completed' ? 'completed' : 'assembly');
    const idx = PHASES_LIST.findIndex(p => p.key === phaseKey);
    return idx >= 0 ? idx : 0;
  }, [selectedMeeting?.current_phase, selectedMeeting?.status]);

  // Governed Actions Counter
  const awaitingCount = useMemo(() => {
    return actionList.filter(a => a.status === 'awaiting_approval' || a.status === 'pending').length;
  }, [actionList]);

  // Derived Confidence from transcript
  const latestConfidence = useMemo(() => {
    if (!selectedMeeting?.transcript || selectedMeeting.transcript.length === 0) return null;
    const rev = [...selectedMeeting.transcript].reverse();
    const entry = rev.find(e => e.confidence_score !== undefined && e.confidence_score !== null);
    return entry ? entry.confidence_score : null;
  }, [selectedMeeting?.transcript]);

  return (
    <div className="space-y-8 max-w-7xl mx-auto animate-in fade-in duration-300">
      {/* 1. Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-800/80 pb-6">
        <div>
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-2xl bg-gradient-to-tr from-amber-500/20 to-yellow-500/20 border border-amber-500/30 flex items-center justify-center">
              <Users className="text-amber-400 h-5 w-5" />
            </div>
            <div>
              <h1 className="text-3xl font-extrabold text-white tracking-tight flex items-center gap-2">
                Executive AI Boardroom
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-300 font-semibold uppercase tracking-wider">
                  Enterprise V2
                </span>
              </h1>
              <p className="text-gray-400 text-xs mt-0.5">
                Parallel multi-agent deliberations, ground truth evidence catalog, and risk-governed automated execution.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <Dialog open={isCreateMeetingOpen} onOpenChange={setIsCreateMeetingOpen}>
            <DialogTrigger render={
              <Button className="bg-gradient-to-r from-amber-600 to-yellow-600 hover:from-amber-500 hover:to-yellow-500 text-white font-bold h-10 px-5 rounded-xl shadow-lg shadow-amber-500/20 text-xs flex items-center gap-2 transition-all hover:scale-[1.02]" />
            }>
              <Users size={15} /> Summon Boardroom
            </DialogTrigger>
            <DialogContent className="glass-panel border border-gray-800 text-white max-w-md rounded-2xl p-6">
              <DialogHeader>
                <DialogTitle className="text-lg font-bold text-white flex items-center gap-2">
                  <Crown className="text-amber-400 h-5 w-5" /> Convene Boardroom Deliberation
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-4 mt-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold text-gray-300">Strategic Objective / Title</label>
                  <Input
                    placeholder="e.g. Enterprise Contract Pricing: 10,000 Seat Quote"
                    value={manualMeetingTitle}
                    onChange={(e) => setManualMeetingTitle(e.target.value)}
                    className="bg-gray-900 border-gray-800 text-white rounded-xl text-xs h-10"
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold text-gray-300">Context & Key Questions</label>
                  <Textarea
                    placeholder="Describe background data, client inquiries, or financial limits..."
                    value={manualMeetingTopic}
                    onChange={(e) => setManualMeetingTopic(e.target.value)}
                    className="bg-gray-900 border-gray-800 text-white rounded-xl text-xs min-h-24"
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold text-gray-400">Assemble Specialists (optional overrides)</label>
                  <div className="grid grid-cols-2 gap-1.5 mt-1">
                    {[
                      'Sales Intelligence Expert',
                      'Finance Expert',
                      'Legal & Compliance Expert',
                      'Human Resources Expert',
                      'Cybersecurity Expert',
                      'Operations Expert',
                      'Marketing Intelligence Expert',
                      'Research Expert',
                    ].map((agentName) => {
                      const isChecked = manualMeetingParticipants.includes(agentName);
                      return (
                        <button
                          key={agentName}
                          type="button"
                          onClick={() => {
                            if (isChecked) {
                              setManualMeetingParticipants(manualMeetingParticipants.filter(p => p !== agentName));
                            } else {
                              setManualMeetingParticipants([...manualMeetingParticipants, agentName]);
                            }
                          }}
                          className={`px-2.5 py-1.5 rounded-lg text-xs font-medium border text-left flex items-center justify-between transition-colors ${
                            isChecked
                              ? 'bg-amber-500/20 border-amber-500 text-amber-200'
                              : 'bg-gray-900/60 border-gray-800 text-gray-400 hover:border-gray-700'
                          }`}
                        >
                          <span className="truncate">{agentName}</span>
                          {isChecked && <Check size={12} className="text-amber-400 shrink-0 ml-1" />}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <Button
                  onClick={handleCreateManualMeeting}
                  disabled={manualMeetingLoading || !manualMeetingTitle || !manualMeetingTopic}
                  className="w-full bg-gradient-to-r from-amber-600 to-yellow-600 hover:from-amber-500 hover:to-yellow-500 text-white font-bold h-10 rounded-xl shadow-lg mt-3 text-xs"
                >
                  {manualMeetingLoading ? 'Assembling Board...' : 'Begin Governed Deliberation'}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* 2. Main 3-Column Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Left Column: Boardroom Sessions Sidebar */}
        <div className="lg:col-span-1 space-y-4">
          <Card className="glass-panel border-gray-800/80 rounded-2xl overflow-hidden shadow-xl bg-gray-950/60 backdrop-blur-md">
            <CardHeader className="p-4 border-b border-gray-800/60">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-bold text-white flex items-center gap-2">
                  <Activity size={16} className="text-amber-400" /> Deliberations ({meetings.length})
                </CardTitle>
              </div>
            </CardHeader>
            <CardContent className="p-2">
              {meetings.length === 0 ? (
                <p className="text-xs text-gray-500 text-center py-8">No boardroom sessions found.</p>
              ) : (
                <div className="flex flex-col gap-1.5 max-h-[640px] overflow-y-auto pr-1">
                  {meetings.map((m) => {
                    const isSelected = selectedMeetingId === m.id;
                    const isAwaiting = m.status === 'awaiting_approval';
                    const isRunning = m.status === 'active';

                    return (
                      <button
                        key={m.id}
                        type="button"
                        onClick={() => setSelectedMeetingId(m.id)}
                        className={`p-3 rounded-xl text-left border transition-all relative ${
                          isSelected
                            ? 'bg-amber-500/10 border-amber-500/50 text-white shadow-md'
                            : 'bg-gray-900/40 border-gray-800/60 text-gray-300 hover:border-gray-700'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full ${
                            isAwaiting
                              ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40 animate-pulse'
                              : isRunning
                              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                              : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                          }`}>
                            {isAwaiting ? 'Approval Required' : isRunning ? 'Deliberating' : 'Resolved'}
                          </span>
                          <span className="text-[10px] text-gray-500">
                            {new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>
                        <h4 className="text-xs font-semibold text-white line-clamp-2 leading-snug">{m.title}</h4>
                        <div className="flex items-center gap-2 mt-2 text-[10px] text-gray-400">
                          <span>{m.participants.length} Experts</span>
                          <span>•</span>
                          <span>{m.action_items?.length || 0} Actions</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Center & Right Columns: Deliberation Deck */}
        <div className="lg:col-span-3 space-y-6">
          {selectedMeeting ? (
            <>
              {/* Meeting Meta Header */}
              <div className="glass-panel border border-gray-800/80 rounded-2xl p-5 bg-gray-950/60 backdrop-blur-md">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="text-xs text-amber-400 font-bold uppercase tracking-wider">
                        {selectedMeeting.trigger_type.replace('_', ' ')}
                      </span>
                      {selectedMeeting.status === 'awaiting_approval' && (
                        <span className="flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/40">
                          <ShieldAlert size={12} /> Action Gate Active
                        </span>
                      )}
                    </div>
                    <h2 className="text-2xl font-extrabold text-white tracking-tight">{selectedMeeting.title}</h2>
                    {selectedMeeting.context_summary && (
                      <p className="text-gray-400 text-xs mt-1.5 line-clamp-2 bg-gray-900/50 p-2 rounded-lg border border-gray-800/60 font-mono">
                        {selectedMeeting.context_summary}
                      </p>
                    )}
                  </div>

                  {/* Executive Actions */}
                  <div className="flex items-center gap-2 shrink-0">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleExportMeeting('md')}
                      className="border-gray-800 text-gray-300 hover:bg-gray-800 text-xs h-8 px-3 rounded-lg"
                    >
                      <Download size={13} className="mr-1.5" /> Export MD
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleExportMeeting('json')}
                      className="border-gray-800 text-gray-300 hover:bg-gray-800 text-xs h-8 px-3 rounded-lg"
                    >
                      <Download size={13} className="mr-1.5" /> JSON
                    </Button>
                    {selectedMeeting.status === 'active' ? (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleCancelMeeting}
                        className="border-rose-900/40 text-rose-400 hover:bg-rose-950/40 text-xs h-8 px-3 rounded-lg"
                      >
                        <X size={13} className="mr-1.5" /> Cancel
                      </Button>
                    ) : (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleRerunMeeting}
                        className="border-amber-900/40 text-amber-400 hover:bg-amber-950/40 text-xs h-8 px-3 rounded-lg"
                      >
                        <RotateCcw size={13} className="mr-1.5" /> Re-run
                      </Button>
                    )}
                  </div>
                </div>

                {/* Phase Stepper */}
                <div className="mt-6 pt-5 border-t border-gray-800/60">
                  <div className="grid grid-cols-7 gap-2">
                    {PHASES_LIST.map((phase, idx) => {
                      const Icon = phase.icon;
                      const isPast = idx < currentPhaseIndex;
                      const isCurrent = idx === currentPhaseIndex;

                      return (
                        <div key={phase.key} className="flex flex-col items-center text-center">
                          <div className={`h-8 w-8 rounded-xl flex items-center justify-center border transition-all ${
                            isCurrent
                              ? 'bg-amber-500 border-amber-400 text-black font-bold shadow-lg shadow-amber-500/30 animate-pulse'
                              : isPast
                              ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400'
                              : 'bg-gray-900/40 border-gray-800 text-gray-500'
                          }`}>
                            {isPast ? <Check size={14} /> : <Icon size={14} />}
                          </div>
                          <span className={`text-[10px] mt-1.5 font-semibold ${
                            isCurrent ? 'text-amber-400' : isPast ? 'text-gray-300' : 'text-gray-600'
                          }`}>
                            {phase.label}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* 3. Interactive Executive Oval Table Visualizer */}
              <div className="glass-panel border border-gray-800/80 rounded-2xl p-6 bg-gradient-to-b from-gray-950/80 to-gray-900/40 relative overflow-hidden">
                <div className="text-center mb-4">
                  <span className="text-[11px] font-bold text-gray-400 uppercase tracking-widest flex items-center justify-center gap-1.5">
                    <Crown size={14} className="text-amber-400" /> Executive Deliberation Chamber
                  </span>
                </div>

                {/* SVG Boardroom Table */}
                <div className="relative w-full max-w-2xl mx-auto h-[280px] flex items-center justify-center">
                  <svg className="absolute inset-0 w-full h-full" viewBox="0 0 500 280">
                    <defs>
                      <linearGradient id="tableGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stopColor="#1e293b" stopOpacity="0.8" />
                        <stop offset="100%" stopColor="#0f172a" stopOpacity="0.9" />
                      </linearGradient>
                      <radialGradient id="amberGlow" cx="50%" cy="50%" r="50%">
                        <stop offset="0%" stopColor="rgba(245, 158, 11, 0.15)" />
                        <stop offset="100%" stopColor="rgba(245, 158, 11, 0)" />
                      </radialGradient>
                    </defs>

                    {/* Table Halo Glow */}
                    <ellipse cx="250" cy="140" rx="195" ry="95" fill="url(#amberGlow)" />
                    {/* Outer Table Rim */}
                    <ellipse cx="250" cy="140" rx="175" ry="85" fill="none" stroke="#334155" strokeWidth="2" strokeDasharray="4 4" />
                    {/* Executive Table Surface */}
                    <ellipse cx="250" cy="140" rx="155" ry="75" fill="url(#tableGrad)" stroke="#475569" strokeWidth="1.5" />
                  </svg>

                  {/* Center Table Dashboard */}
                  <div className="relative z-10 text-center p-3 bg-gray-950/90 rounded-2xl border border-gray-800 shadow-2xl max-w-[200px]">
                    <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-0.5">
                      Decision Status
                    </div>
                    <div className="text-xs font-extrabold text-amber-400 truncate">
                      {selectedMeeting.current_phase?.toUpperCase() || selectedMeeting.status.toUpperCase()}
                    </div>
                    {latestConfidence !== null && (
                      <div className="mt-2 pt-2 border-t border-gray-800">
                        <div className="flex items-center justify-between text-[10px] mb-1">
                          <span className="text-gray-400">Confidence</span>
                          <span className="text-amber-400 font-bold">{latestConfidence}%</span>
                        </div>
                        <div className="w-full bg-gray-800 h-1.5 rounded-full overflow-hidden">
                          <div
                            className="bg-gradient-to-r from-amber-500 to-emerald-400 h-full rounded-full transition-all duration-500"
                            style={{ width: `${latestConfidence}%` }}
                          />
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Dynamic Elliptical Seats */}
                  {selectedMeeting.participants.map((participant, idx) => {
                    const total = selectedMeeting.participants.length;
                    const angle = (2 * Math.PI * idx) / total - Math.PI / 2;
                    const cx = 250;
                    const cy = 140;
                    const rx = 180;
                    const ry = 95;
                    const x = cx + rx * Math.cos(angle);
                    const y = cy + ry * Math.sin(angle);

                    const Icon = getAgentIcon(participant);
                    const isCEO = participant.includes('CEO');

                    return (
                      <div
                        key={participant}
                        style={{
                          left: `${(x / 500) * 100}%`,
                          top: `${(y / 280) * 100}%`,
                          transform: 'translate(-50%, -50%)',
                        }}
                        className="absolute z-20 flex flex-col items-center group cursor-pointer"
                      >
                        <div className={`h-9 w-9 rounded-full flex items-center justify-center border shadow-lg transition-transform group-hover:scale-110 ${
                          isCEO
                            ? 'bg-amber-500 text-black border-yellow-300 font-bold'
                            : 'bg-gray-900/90 text-amber-300 border-gray-700'
                        }`}>
                          <Icon size={16} />
                        </div>
                        <span className="text-[9px] font-semibold text-gray-300 bg-gray-950/80 px-2 py-0.5 rounded-md border border-gray-800 mt-1 max-w-[100px] truncate shadow">
                          {participant.replace(' Expert', '').replace(' AI', '')}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* 4. Governed Action Items Kanban Board */}
              <Card className="glass-panel border-gray-800/80 rounded-2xl overflow-hidden bg-gray-950/60">
                <CardHeader className="p-5 border-b border-gray-800/60">
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                    <div>
                      <CardTitle className="text-base text-white font-bold flex items-center gap-2">
                        <ShieldCheck className="text-amber-400 h-5 w-5" />
                        Governed Action Queue
                        {awaitingCount > 0 && (
                          <span className="text-xs px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/40 font-bold">
                            {awaitingCount} Awaiting Human Review
                          </span>
                        )}
                      </CardTitle>
                      <CardDescription className="text-gray-400 text-xs mt-0.5">
                        High-risk actions require human signoff before execution. Low-risk actions are automated with audit logs.
                      </CardDescription>
                    </div>

                    <div className="flex gap-1 bg-gray-900/80 p-1 rounded-xl border border-gray-800">
                      <button
                        type="button"
                        onClick={() => setActionTab('awaiting')}
                        className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                          actionTab === 'awaiting' ? 'bg-amber-500 text-black font-bold' : 'text-gray-400 hover:text-white'
                        }`}
                      >
                        Awaiting ({awaitingCount})
                      </button>
                      <button
                        type="button"
                        onClick={() => setActionTab('completed')}
                        className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                          actionTab === 'completed' ? 'bg-amber-500 text-black font-bold' : 'text-gray-400 hover:text-white'
                        }`}
                      >
                        Executed
                      </button>
                      <button
                        type="button"
                        onClick={() => setActionTab('all')}
                        className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                          actionTab === 'all' ? 'bg-amber-500 text-black font-bold' : 'text-gray-400 hover:text-white'
                        }`}
                      >
                        All ({actionList.length})
                      </button>
                    </div>
                  </div>
                </CardHeader>

                <CardContent className="p-5">
                  {actionList.length === 0 ? (
                    <div className="text-center py-8 text-gray-500 text-xs">
                      No actions produced yet. Actions are generated upon CEO synthesis.
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {actionList
                        .filter(a => {
                          if (actionTab === 'awaiting') return a.status === 'awaiting_approval' || a.status === 'pending';
                          if (actionTab === 'completed') return a.status === 'completed' || a.status === 'executing';
                          return true;
                        })
                        .map((action) => {
                          const isHigh = action.risk_tier === 'high';
                          const isMedium = action.risk_tier === 'medium';
                          const isAwaiting = action.status === 'awaiting_approval' || action.status === 'pending';
                          const isDone = action.status === 'completed';
                          const isRejected = action.status === 'rejected';

                          return (
                            <div
                              key={action.id}
                              className={`p-4 rounded-xl border flex flex-col justify-between transition-all ${
                                isAwaiting
                                  ? 'bg-rose-950/20 border-rose-800/60 shadow-lg shadow-rose-950/20'
                                  : isDone
                                  ? 'bg-gray-900/40 border-gray-800/60'
                                  : 'bg-gray-900/20 border-gray-800/40'
                              }`}
                            >
                              <div>
                                <div className="flex items-center justify-between mb-2">
                                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider flex items-center gap-1 ${
                                    isHigh
                                      ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                                      : isMedium
                                      ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                                      : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                                  }`}>
                                    {isHigh ? <ShieldAlert size={11} /> : isMedium ? <AlertTriangle size={11} /> : <Zap size={11} />}
                                    {action.risk_tier || 'standard'} Risk
                                  </span>

                                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-md ${
                                    isDone
                                      ? 'bg-emerald-500/10 text-emerald-400'
                                      : isRejected
                                      ? 'bg-rose-500/10 text-rose-400'
                                      : 'bg-amber-500/10 text-amber-400'
                                  }`}>
                                    {action.status.replace('_', ' ')}
                                  </span>
                                </div>

                                <div className="text-xs font-bold text-gray-200 mb-1">
                                  {action.assigned_to}
                                </div>
                                <p className="text-xs text-gray-300 leading-relaxed">
                                  {action.description}
                                </p>

                                {action.rejection_reason && (
                                  <div className="mt-2 text-[11px] text-rose-400 bg-rose-950/30 p-2 rounded-lg border border-rose-900/50">
                                    <strong>Rejection Reason:</strong> {action.rejection_reason}
                                  </div>
                                )}

                                {action.approved_by && (
                                  <div className="mt-2 text-[10px] text-gray-400">
                                    Approved by: <span className="text-gray-300 font-semibold">{action.approved_by}</span>
                                  </div>
                                )}
                              </div>

                              {isAwaiting && (
                                <div className="flex items-center gap-2 mt-4 pt-3 border-t border-gray-800/60">
                                  <Button
                                    size="sm"
                                    onClick={() => handleApproveAction(action.id)}
                                    className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs h-8 px-3 rounded-lg flex items-center gap-1.5 flex-1"
                                  >
                                    <Check size={13} /> Approve & Execute
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => setRejectActionId(action.id)}
                                    className="border-rose-900/40 text-rose-400 hover:bg-rose-950/40 text-xs h-8 px-3 rounded-lg"
                                  >
                                    <X size={13} /> Reject
                                  </Button>
                                </div>
                              )}
                            </div>
                          );
                        })}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* 5. Evidence Catalog Panel */}
              <Card className="glass-panel border-gray-800/80 rounded-2xl overflow-hidden bg-gray-950/60">
                <CardHeader
                  className="p-4 border-b border-gray-800/60 cursor-pointer flex flex-row items-center justify-between"
                  onClick={() => setIsEvidenceExpanded(!isEvidenceExpanded)}
                >
                  <CardTitle className="text-sm text-white font-bold flex items-center gap-2">
                    <Database className="text-amber-400 h-4 w-4" />
                    Verified Evidence Catalog ({evidenceList.length})
                  </CardTitle>
                  {isEvidenceExpanded ? <ChevronDown size={16} className="text-gray-400" /> : <ChevronRight size={16} className="text-gray-400" />}
                </CardHeader>
                {isEvidenceExpanded && (
                  <CardContent className="p-4">
                    {evidenceList.length === 0 ? (
                      <p className="text-xs text-gray-500 py-4 text-center">No ground-truth evidence records cataloged for this deliberation.</p>
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {evidenceList.map((ev) => (
                          <div key={ev.id} className="p-3 rounded-xl bg-gray-900/40 border border-gray-800/60 space-y-2">
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-mono font-bold text-amber-300">
                                {ev.source_ref}
                              </span>
                              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-gray-800 text-gray-300 uppercase">
                                {ev.source_type}
                              </span>
                            </div>
                            {ev.excerpt && (
                              <p className="text-xs text-gray-400 line-clamp-3 font-mono bg-gray-950/50 p-2 rounded-lg border border-gray-800/40">
                                {ev.excerpt}
                              </p>
                            )}
                            {ev.trust_score !== undefined && (
                              <div className="flex items-center justify-between text-[10px] text-gray-400 pt-1">
                                <span>Trust Rating</span>
                                <span className="font-bold text-emerald-400">{ev.trust_score}%</span>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                )}
              </Card>

              {/* 6. Deliberation Transcript */}
              <Card className="glass-panel border-gray-800/80 rounded-2xl overflow-hidden bg-gray-950/60">
                <CardHeader
                  className="p-4 border-b border-gray-800/60 cursor-pointer flex flex-row items-center justify-between"
                  onClick={() => setIsTranscriptExpanded(!isTranscriptExpanded)}
                >
                  <CardTitle className="text-sm text-white font-bold flex items-center gap-2">
                    <MessageSquare className="text-amber-400 h-4 w-4" />
                    Deliberation Transcript ({selectedMeeting.transcript?.length || 0})
                  </CardTitle>
                  {isTranscriptExpanded ? <ChevronDown size={16} className="text-gray-400" /> : <ChevronRight size={16} className="text-gray-400" />}
                </CardHeader>
                {isTranscriptExpanded && (
                  <CardContent className="p-4 space-y-4">
                    {(!selectedMeeting.transcript || selectedMeeting.transcript.length === 0) ? (
                      <p className="text-xs text-gray-500 py-6 text-center">Transcript empty. Waiting for expert turns...</p>
                    ) : (
                      selectedMeeting.transcript.map((msg, i) => {
                        const Icon = getAgentIcon(msg.sender);
                        const isCEO = msg.sender.includes('CEO');

                        return (
                          <div
                            key={i}
                            className={`p-4 rounded-xl border space-y-2 ${
                              isCEO
                                ? 'bg-amber-950/10 border-amber-500/30'
                                : 'bg-gray-900/40 border-gray-800/60'
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <div className={`h-6 w-6 rounded-lg flex items-center justify-center ${
                                  isCEO ? 'bg-amber-500 text-black' : 'bg-gray-800 text-amber-300'
                                }`}>
                                  <Icon size={13} />
                                </div>
                                <span className="text-xs font-bold text-white">{msg.sender}</span>
                                {msg.phase && (
                                  <span className="text-[10px] text-gray-400 px-2 py-0.5 rounded-full bg-gray-800/60 border border-gray-700/40">
                                    {msg.phase}
                                  </span>
                                )}
                              </div>
                              {msg.confidence_score !== undefined && (
                                <span className="text-[10px] font-bold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20">
                                  {msg.confidence_score}% Confidence
                                </span>
                              )}
                            </div>

                            <p className="text-xs text-gray-300 whitespace-pre-wrap leading-relaxed">
                              {msg.content}
                            </p>

                            {/* Findings Chips */}
                            {msg.findings && msg.findings.length > 0 && (
                              <div className="mt-2 pt-2 border-t border-gray-800/40">
                                <span className="text-[10px] text-gray-400 font-semibold uppercase">Findings:</span>
                                <div className="flex flex-wrap gap-1.5 mt-1">
                                  {msg.findings.map((f, idx) => (
                                    <span
                                      key={idx}
                                      className="text-[10px] text-gray-300 bg-gray-950 px-2 py-1 rounded-md border border-gray-800"
                                    >
                                      {typeof f === 'string' ? f : f.claim}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })
                    )}
                  </CardContent>
                )}
              </Card>
            </>
          ) : (
            <div className="glass-panel border border-gray-800 rounded-2xl p-16 text-center text-gray-500 text-xs">
              Select or summon a boardroom deliberation to inspect live events.
            </div>
          )}
        </div>
      </div>

      {/* Rejection Modal Dialog */}
      <Dialog open={!!rejectActionId} onOpenChange={(open) => !open && setRejectActionId(null)}>
        <DialogContent className="glass-panel border border-gray-800 text-white max-w-sm rounded-2xl p-5">
          <DialogHeader>
            <DialogTitle className="text-base font-bold text-white flex items-center gap-2">
              <ShieldAlert className="text-rose-400 h-5 w-5" /> Reject Proposed Action
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 mt-3">
            <p className="text-xs text-gray-400">
              Provide a rationale for blocking this action. The reason is permanently audited.
            </p>
            <Textarea
              placeholder="e.g. Budget limit exceeded; proposed discount violates enterprise policy."
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              className="bg-gray-900 border-gray-800 text-white rounded-xl text-xs min-h-20"
            />
            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setRejectActionId(null)}
                className="border-gray-800 text-gray-400 text-xs h-8"
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleRejectAction}
                className="bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs h-8"
              >
                Confirm Rejection
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
