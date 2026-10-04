'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger } from '@/components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { 
  Building2, Users, Target, ShieldCheck, AlertTriangle, TrendingUp, Sparkles, 
  Send, RefreshCw, Plus, CheckCircle2, XCircle, Search, FileText, DollarSign,
  ChevronRight, ArrowUpRight, Clock, HelpCircle, Layers, Mail, Check
} from 'lucide-react';

interface DealRoomViewProps {
  token: string | null;
  API_URL: string;
  fetchWithAuth: (url: string, options?: any) => Promise<Response>;
}

export default function DealRoomView({ token, API_URL, fetchWithAuth }: DealRoomViewProps) {
  const [dealRooms, setDealRooms] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [stageFilter, setStageFilter] = useState('all');
  const [selectedRoom, setSelectedRoom] = useState<any | null>(null);
  const [roomDetailLoading, setRoomDetailLoading] = useState(false);

  // Manager Audit State
  const [managerAudit, setManagerAudit] = useState<any | null>(null);
  const [managerLoading, setManagerLoading] = useState(false);
  const [knowledgeGaps, setKnowledgeGaps] = useState<any[]>([]);

  // Action States
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  // New Deal Room Modal State
  const [isNewRoomOpen, setIsNewRoomOpen] = useState(false);
  const [newCompanyName, setNewCompanyName] = useState('');
  const [newDomain, setNewDomain] = useState('');
  const [newIndustry, setNewIndustry] = useState('Technology');
  const [newEmployees, setNewEmployees] = useState('250');

  // New Committee Member Modal State
  const [isNewMemberOpen, setIsNewMemberOpen] = useState(false);
  const [newMemberName, setNewMemberName] = useState('');
  const [newMemberEmail, setNewMemberEmail] = useState('');
  const [newMemberTitle, setNewMemberTitle] = useState('');
  const [newMemberRole, setNewMemberRole] = useState('economic_buyer');

  // Outreach Composer State
  const [composerResult, setComposerResult] = useState<any | null>(null);
  const [isComposerOpen, setIsComposerOpen] = useState(false);

  // Deal Desk Quote State
  const [isQuoteOpen, setIsQuoteOpen] = useState(false);
  const [quoteListPrice, setQuoteListPrice] = useState('25000');
  const [quoteDiscountPct, setQuoteDiscountPct] = useState('10');
  const [quoteResult, setQuoteResult] = useState<any | null>(null);

  const fetchDealRooms = async () => {
    if (!token) return;
    setLoading(true);
    try {
      let url = `${API_URL}/deal-rooms`;
      const queryParams = new URLSearchParams();
      if (search) queryParams.append('search', search);
      if (stageFilter !== 'all') queryParams.append('stage', stageFilter);
      if (queryParams.toString()) url += `?${queryParams.toString()}`;

      const res = await fetchWithAuth(url);
      if (res.ok) {
        const data = await res.json();
        setDealRooms(data);
      }
    } catch (err) {
      console.error('Failed to fetch deal rooms:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchRoomDetails = async (roomId: string) => {
    if (!token) return;
    setRoomDetailLoading(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/deal-rooms/${roomId}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedRoom(data);
      }
    } catch (err) {
      console.error('Failed to fetch deal room details:', err);
    } finally {
      setRoomDetailLoading(false);
    }
  };

  const runManagerAudit = async () => {
    if (!token) return;
    setManagerLoading(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/sales-manager/daily-audit`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setManagerAudit(data);
      }
      // Also fetch gaps
      const gapsRes = await fetchWithAuth(`${API_URL}/sales-manager/knowledge-gaps`);
      if (gapsRes.ok) {
        const gapsData = await gapsRes.json();
        setKnowledgeGaps(gapsData.gaps || []);
      }
    } catch (err) {
      console.error('Manager audit failed:', err);
    } finally {
      setManagerLoading(false);
    }
  };

  useEffect(() => {
    fetchDealRooms();
    runManagerAudit();
  }, [stageFilter]);

  const handleCreateDealRoom = async () => {
    if (!newCompanyName || !newDomain) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/deal-rooms`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_name: newCompanyName,
          domain: newDomain,
          industry: newIndustry,
          employee_count: parseInt(newEmployees) || 100,
        }),
      });
      if (res.ok) {
        setIsNewRoomOpen(false);
        setNewCompanyName('');
        setNewDomain('');
        fetchDealRooms();
      }
    } catch (err) {
      console.error('Create deal room error:', err);
    }
  };

  const handleAddCommitteeMember = async () => {
    if (!selectedRoom || !newMemberEmail || !newMemberName) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/deal-rooms/${selectedRoom.id}/committee`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newMemberName,
          email: newMemberEmail,
          title: newMemberTitle,
          role_type: newMemberRole,
        }),
      });
      if (res.ok) {
        setIsNewMemberOpen(false);
        setNewMemberName('');
        setNewMemberEmail('');
        setNewMemberTitle('');
        fetchRoomDetails(selectedRoom.id);
      }
    } catch (err) {
      console.error('Add committee member error:', err);
    }
  };

  const handleQualifyAccount = async (roomId: string) => {
    setActionLoading(true);
    setActionMessage('Running Multi-Factor Qualifier Agent (Fit × Timing × Evidence)...');
    try {
      const res = await fetchWithAuth(`${API_URL}/deal-rooms/${roomId}/qualify`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setActionMessage(`Qualification: ${data.decision.toUpperCase()} (Confidence: ${(data.confidence * 100).toFixed(0)}%)`);
        fetchRoomDetails(roomId);
        fetchDealRooms();
      }
    } catch (err) {
      setActionMessage('Failed to qualify account.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleResearchAccount = async (roomId: string) => {
    setActionLoading(true);
    setActionMessage('Running Account Researcher Agent (Extracting cited brief)...');
    try {
      const res = await fetchWithAuth(`${API_URL}/deal-rooms/${roomId}/research`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setActionMessage(`Research Complete: ${data.reasoning_summary}`);
        fetchRoomDetails(roomId);
        fetchDealRooms();
      }
    } catch (err) {
      setActionMessage('Failed to research account.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleComposeOutreach = async (roomId: string, memberId?: string) => {
    setActionLoading(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/deal-rooms/${roomId}/compose`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          committee_member_id: memberId,
          channel: 'email',
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setComposerResult(data);
        setIsComposerOpen(true);
      }
    } catch (err) {
      console.error('Compose error:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleGenerateQuote = async (roomId: string) => {
    try {
      const res = await fetchWithAuth(`${API_URL}/deal-rooms/${roomId}/quote`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          list_price: parseFloat(quoteListPrice) || 25000,
          discount_pct: (parseFloat(quoteDiscountPct) || 10) / 100,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setQuoteResult(data);
      }
    } catch (err) {
      console.error('Quote error:', err);
    }
  };

  return (
    <div className="space-y-6">
      {/* 1. Autonomous Sales Manager Header Metric Bar */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-slate-950/70 border-slate-800 shadow-md backdrop-blur">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs uppercase tracking-wider text-slate-400 flex items-center justify-between">
              <span>Active Deal Rooms</span>
              <Building2 className="w-4 h-4 text-cyan-400" />
            </CardDescription>
            <CardTitle className="text-2xl font-bold text-white">
              {dealRooms.length}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-slate-400">
            Persistent account state machines
          </CardContent>
        </Card>

        <Card className="bg-slate-950/70 border-slate-800 shadow-md backdrop-blur">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs uppercase tracking-wider text-slate-400 flex items-center justify-between">
              <span>Calibrated Forecast</span>
              <DollarSign className="w-4 h-4 text-emerald-400" />
            </CardDescription>
            <CardTitle className="text-2xl font-bold text-emerald-400">
              ${(managerAudit?.data?.total_calibrated_pipeline_usd || 0).toLocaleString()}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-slate-400">
            Bayesian probability weighted pipeline
          </CardContent>
        </Card>

        <Card className="bg-slate-950/70 border-slate-800 shadow-md backdrop-blur">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs uppercase tracking-wider text-slate-400 flex items-center justify-between">
              <span>Multi-Threaded Coverage</span>
              <Users className="w-4 h-4 text-indigo-400" />
            </CardDescription>
            <CardTitle className="text-2xl font-bold text-indigo-400">
              {dealRooms.length > 0 
                ? `${Math.round((dealRooms.filter(r => r.is_multi_threaded).length / dealRooms.length) * 100)}%`
                : '0%'}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-slate-400">
            Accounts with &ge; 2 identified personas
          </CardContent>
        </Card>

        <Card className="bg-slate-950/70 border-slate-800 shadow-md backdrop-blur">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs uppercase tracking-wider text-slate-400 flex items-center justify-between">
              <span>Pipeline Inspection</span>
              <AlertTriangle className="w-4 h-4 text-amber-400" />
            </CardDescription>
            <CardTitle className="text-2xl font-bold text-amber-400">
              {managerAudit?.data?.stalled_deals_count || 0} At Risk
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-slate-400 flex items-center justify-between">
            <span>Stalled &gt; 7 days or single-threaded</span>
            <Button variant="ghost" size="sm" onClick={runManagerAudit} disabled={managerLoading} className="h-6 px-2 text-xs text-cyan-400 hover:text-cyan-300">
              <RefreshCw className={`w-3 h-3 mr-1 ${managerLoading ? 'animate-spin' : ''}`} /> Audit
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Action Notification Banner */}
      {actionMessage && (
        <div className="p-3 bg-cyan-950/50 border border-cyan-800/80 rounded-lg text-sm text-cyan-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-cyan-400 animate-pulse" />
            <span>{actionMessage}</span>
          </div>
          <Button variant="ghost" size="sm" onClick={() => setActionMessage(null)} className="h-6 w-6 p-0 text-slate-400 hover:text-white">
            &times;
          </Button>
        </div>
      )}

      {/* 2. Command Center Toolbar & Filters */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 bg-slate-900/60 p-4 rounded-xl border border-slate-800">
        <div className="flex items-center gap-3 w-full sm:w-auto">
          <div className="relative w-full sm:w-72">
            <Search className="w-4 h-4 absolute left-3 top-3 text-slate-500" />
            <Input
              placeholder="Search accounts by name or domain..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && fetchDealRooms()}
              className="pl-9 bg-slate-950/80 border-slate-700 text-sm"
            />
          </div>

          <Select value={stageFilter} onValueChange={(val) => val && setStageFilter(val)}>
            <SelectTrigger className="w-[180px] bg-slate-950/80 border-slate-700 text-sm">
              <SelectValue placeholder="Stage" />
            </SelectTrigger>
            <SelectContent className="bg-slate-900 border-slate-800 text-slate-200">
              <SelectItem value="all">All Stages</SelectItem>
              <SelectItem value="discovered">Discovered</SelectItem>
              <SelectItem value="qualified">Qualified</SelectItem>
              <SelectItem value="outreach_ready">Outreach Ready</SelectItem>
              <SelectItem value="in_cadence">In Cadence</SelectItem>
              <SelectItem value="replied">Replied</SelectItem>
              <SelectItem value="meeting_booked">Meeting Booked</SelectItem>
              <SelectItem value="proposal">Proposal</SelectItem>
              <SelectItem value="closing">Closing</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
          <Dialog open={isNewRoomOpen} onOpenChange={setIsNewRoomOpen}>
            <DialogTrigger
              render={
                <Button className="bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white font-medium text-sm" />
              }
            >
              <Plus className="w-4 h-4 mr-1.5" /> New Deal Room
            </DialogTrigger>
            <DialogContent className="bg-slate-900 border-slate-800 text-slate-100">
              <DialogHeader>
                <DialogTitle>Open Persistent Deal Room</DialogTitle>
                <DialogDescription className="text-slate-400">
                  Initializes a persistent account state machine with buying committee, signals, and deliverability tracking.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 pt-2">
                <div>
                  <label className="text-xs font-semibold text-slate-300">Company Name</label>
                  <Input 
                    placeholder="e.g. Acme Cloud Corp"
                    value={newCompanyName}
                    onChange={(e) => setNewCompanyName(e.target.value)}
                    className="mt-1 bg-slate-950 border-slate-700"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-300">Domain</label>
                  <Input 
                    placeholder="e.g. acmecloud.com"
                    value={newDomain}
                    onChange={(e) => setNewDomain(e.target.value)}
                    className="mt-1 bg-slate-950 border-slate-700"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-semibold text-slate-300">Industry</label>
                    <Input 
                      value={newIndustry}
                      onChange={(e) => setNewIndustry(e.target.value)}
                      className="mt-1 bg-slate-950 border-slate-700"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-slate-300">Employee Count</label>
                    <Input 
                      value={newEmployees}
                      onChange={(e) => setNewEmployees(e.target.value)}
                      className="mt-1 bg-slate-950 border-slate-700"
                    />
                  </div>
                </div>
                <Button onClick={handleCreateDealRoom} className="w-full bg-cyan-600 hover:bg-cyan-500 mt-2">
                  Initialize Deal Room
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* 3. Main Split View: Deal Room Table & Detail Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Deal Rooms List */}
        <div className={selectedRoom ? 'lg:col-span-5 space-y-3' : 'lg:col-span-12 space-y-3'}>
          <div className="bg-slate-900/70 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
            <Table>
              <TableHeader className="bg-slate-950/80">
                <TableRow className="border-slate-800 hover:bg-transparent">
                  <TableHead className="text-slate-400 font-medium">Account</TableHead>
                  <TableHead className="text-slate-400 font-medium">Stage</TableHead>
                  <TableHead className="text-slate-400 font-medium">Threading</TableHead>
                  <TableHead className="text-slate-400 font-medium">Priority Index</TableHead>
                  <TableHead className="text-slate-400 font-medium text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-12 text-slate-500">
                      Loading Deal Rooms...
                    </TableCell>
                  </TableRow>
                ) : dealRooms.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-12 text-slate-500">
                      No Deal Rooms found. Create one to begin autonomous account execution.
                    </TableCell>
                  </TableRow>
                ) : (
                  dealRooms.map((r) => {
                    const isSelected = selectedRoom?.id === r.id;
                    return (
                      <TableRow 
                        key={r.id} 
                        onClick={() => fetchRoomDetails(r.id)}
                        className={`cursor-pointer transition-colors border-slate-800/80 ${
                          isSelected ? 'bg-cyan-950/40 border-l-4 border-l-cyan-500' : 'hover:bg-slate-800/40'
                        }`}
                      >
                        <TableCell>
                          <div className="font-semibold text-slate-100 flex items-center gap-1.5">
                            {r.company_name}
                          </div>
                          <div className="text-xs text-slate-400 font-mono">{r.domain}</div>
                        </TableCell>
                        <TableCell>
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                            r.stage === 'meeting_booked' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' :
                            r.stage === 'in_cadence' ? 'bg-indigo-950 text-indigo-400 border border-indigo-800' :
                            r.stage === 'qualified' ? 'bg-cyan-950 text-cyan-400 border border-cyan-800' :
                            'bg-slate-800 text-slate-300'
                          }`}>
                            {r.stage.replace('_', ' ')}
                          </span>
                        </TableCell>
                        <TableCell>
                          {r.is_multi_threaded ? (
                            <span className="inline-flex items-center gap-1 text-xs text-indigo-400">
                              <ShieldCheck className="w-3.5 h-3.5" /> Multi-Threaded
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-xs text-amber-400">
                              <AlertTriangle className="w-3.5 h-3.5" /> Single-Threaded
                            </span>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <div className="w-12 bg-slate-800 h-2 rounded-full overflow-hidden">
                              <div 
                                className="bg-cyan-500 h-full rounded-full" 
                                style={{ width: `${Math.min(100, Math.round((r.priority_index || 0) * 100))}%` }}
                              />
                            </div>
                            <span className="text-xs font-mono text-slate-300">
                              {((r.priority_index || 0)).toFixed(2)}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            className="h-7 w-7 p-0 text-slate-400 hover:text-white"
                            onClick={(e) => {
                              e.stopPropagation();
                              fetchRoomDetails(r.id);
                            }}
                          >
                            <ChevronRight className="w-4 h-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </div>
        </div>

        {/* Selected Deal Room Detail Inspector */}
        {selectedRoom && (
          <div className="lg:col-span-7 space-y-4">
            <Card className="bg-slate-900/90 border-slate-800 shadow-xl overflow-hidden">
              <CardHeader className="bg-slate-950/60 pb-4 border-b border-slate-800/80">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <CardTitle className="text-xl font-bold text-white">
                        {selectedRoom.company_name}
                      </CardTitle>
                      <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
                        {selectedRoom.domain}
                      </span>
                    </div>
                    <CardDescription className="text-xs text-slate-400 mt-1">
                      {selectedRoom.industry || 'Technology'} &bull; {selectedRoom.employee_count || '100+'} employees &bull; Calibrated Win Prob: {Math.round((selectedRoom.calibrated_win_prob || 0) * 100)}%
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button 
                      variant="outline" 
                      size="sm" 
                      onClick={() => handleQualifyAccount(selectedRoom.id)}
                      disabled={actionLoading}
                      className="border-slate-700 hover:bg-slate-800 text-xs"
                    >
                      <Target className="w-3.5 h-3.5 mr-1 text-cyan-400" /> Qualify
                    </Button>
                    <Button 
                      variant="outline" 
                      size="sm" 
                      onClick={() => handleResearchAccount(selectedRoom.id)}
                      disabled={actionLoading}
                      className="border-slate-700 hover:bg-slate-800 text-xs"
                    >
                      <Sparkles className="w-3.5 h-3.5 mr-1 text-indigo-400" /> Research Brief
                    </Button>
                    <Button 
                      variant="default" 
                      size="sm" 
                      onClick={() => handleComposeOutreach(selectedRoom.id)}
                      disabled={actionLoading}
                      className="bg-cyan-600 hover:bg-cyan-500 text-xs"
                    >
                      <Send className="w-3.5 h-3.5 mr-1" /> Compose Outreach
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-6 pt-4 text-slate-200">
                
                {/* Risk Flags & Next Best Action */}
                <div className="p-3 bg-slate-950/80 rounded-lg border border-slate-800 flex items-center justify-between">
                  <div>
                    <div className="text-xs uppercase tracking-wider font-semibold text-slate-400 flex items-center gap-1.5">
                      <Target className="w-3.5 h-3.5 text-cyan-400" /> Next Best Action
                    </div>
                    <div className="text-sm font-medium text-slate-100 mt-0.5">
                      {selectedRoom.next_best_action?.action 
                        ? selectedRoom.next_best_action.action.replace(/_/g, ' ').toUpperCase()
                        : 'CONDUCT MULTI-THREADING OUTREACH'}
                    </div>
                    <div className="text-xs text-slate-400 mt-0.5">
                      {selectedRoom.next_best_action?.reason || 'Multi-thread to economic buyer and champion personas.'}
                    </div>
                  </div>
                  {selectedRoom.risk_flags && selectedRoom.risk_flags.length > 0 && (
                    <div className="flex flex-wrap gap-1 justify-end max-w-[200px]">
                      {selectedRoom.risk_flags.map((flag: string, idx: number) => (
                        <span key={idx} className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-950/70 border border-amber-800 text-amber-300">
                          {flag.replace(/_/g, ' ')}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Buying Committee Map */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                      <Users className="w-4 h-4 text-indigo-400" /> Buying Committee ({(selectedRoom.committee || []).length} Stakeholders)
                    </h4>
                    <Dialog open={isNewMemberOpen} onOpenChange={setIsNewMemberOpen}>
                      <DialogTrigger
                        render={
                          <Button variant="ghost" size="sm" className="h-7 text-xs text-cyan-400 hover:text-cyan-300" />
                        }
                      >
                        <Plus className="w-3.5 h-3.5 mr-1" /> Add Stakeholder
                      </DialogTrigger>
                      <DialogContent className="bg-slate-900 border-slate-800 text-slate-100">
                        <DialogHeader>
                          <DialogTitle>Add Buying Committee Member</DialogTitle>
                          <DialogDescription className="text-slate-400">
                            Add an executive or influencer to this account's multi-threading committee.
                          </DialogDescription>
                        </DialogHeader>
                        <div className="space-y-3 pt-2">
                          <div>
                            <label className="text-xs font-semibold text-slate-300">Full Name</label>
                            <Input 
                              value={newMemberName} 
                              onChange={(e) => setNewMemberName(e.target.value)} 
                              placeholder="e.g. Sarah Jenkins"
                              className="mt-1 bg-slate-950 border-slate-700"
                            />
                          </div>
                          <div>
                            <label className="text-xs font-semibold text-slate-300">Work Email</label>
                            <Input 
                              value={newMemberEmail} 
                              onChange={(e) => setNewMemberEmail(e.target.value)} 
                              placeholder="e.g. sjenkins@company.com"
                              className="mt-1 bg-slate-950 border-slate-700"
                            />
                          </div>
                          <div>
                            <label className="text-xs font-semibold text-slate-300">Title</label>
                            <Input 
                              value={newMemberTitle} 
                              onChange={(e) => setNewMemberTitle(e.target.value)} 
                              placeholder="e.g. Chief Revenue Officer"
                              className="mt-1 bg-slate-950 border-slate-700"
                            />
                          </div>
                          <div>
                            <label className="text-xs font-semibold text-slate-300">Role Type</label>
                            <Select value={newMemberRole} onValueChange={(val) => val && setNewMemberRole(val)}>
                              <SelectTrigger className="mt-1 bg-slate-950 border-slate-700">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent className="bg-slate-900 border-slate-800 text-slate-200">
                                <SelectItem value="economic_buyer">Economic Buyer (Budget Owner)</SelectItem>
                                <SelectItem value="champion">Champion (Internal Advocate)</SelectItem>
                                <SelectItem value="influencer">Influencer</SelectItem>
                                <SelectItem value="technical">Technical / Security Evaluator</SelectItem>
                                <SelectItem value="gatekeeper">Gatekeeper</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <Button onClick={handleAddCommitteeMember} className="w-full bg-indigo-600 hover:bg-indigo-500 mt-2">
                            Add Stakeholder
                          </Button>
                        </div>
                      </DialogContent>
                    </Dialog>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {(selectedRoom.committee || []).length === 0 ? (
                      <div className="col-span-2 p-6 border border-dashed border-slate-800 rounded-lg text-center text-xs text-slate-500">
                        No committee members mapped yet. Add stakeholders or run Lead Discovery to populate.
                      </div>
                    ) : (
                      selectedRoom.committee.map((m: any) => (
                        <div key={m.id} className="p-3 bg-slate-950/60 rounded-lg border border-slate-800/80 flex items-start justify-between">
                          <div>
                            <div className="font-medium text-sm text-slate-100">{m.name}</div>
                            <div className="text-xs text-slate-400">{m.title}</div>
                            <div className="text-xs text-cyan-400/90 font-mono mt-1">{m.email}</div>
                            <div className="mt-2 flex items-center gap-1.5">
                              <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300">
                                {m.role_type.replace('_', ' ')}
                              </span>
                              <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                                m.engagement_state === 'replied' ? 'bg-emerald-950 text-emerald-400' :
                                m.engagement_state === 'contacted' ? 'bg-indigo-950 text-indigo-400' :
                                'bg-slate-900 text-slate-400'
                              }`}>
                                {m.engagement_state}
                              </span>
                            </div>
                          </div>
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            onClick={() => handleComposeOutreach(selectedRoom.id, m.id)}
                            className="h-7 px-2 text-xs text-cyan-400 hover:text-cyan-300 hover:bg-slate-800"
                          >
                            <Send className="w-3 h-3 mr-1" /> Outreach
                          </Button>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {/* Executive Intelligence Brief & Pain Hypotheses */}
                {selectedRoom.account_brief && (
                  <div className="p-4 bg-slate-950/60 rounded-lg border border-slate-800 space-y-3">
                    <h4 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                      <FileText className="w-4 h-4 text-cyan-400" /> Executive Intelligence Brief
                    </h4>
                    <p className="text-xs text-slate-300 leading-relaxed">
                      {selectedRoom.account_brief.executive_summary || 'Brief compiled from verified primary sources and technographics.'}
                    </p>
                    
                    {selectedRoom.pain_hypotheses && selectedRoom.pain_hypotheses.length > 0 && (
                      <div className="space-y-1.5 pt-2">
                        <div className="text-xs uppercase font-semibold text-slate-400">Identified Pain Hypotheses</div>
                        {selectedRoom.pain_hypotheses.map((p: any, idx: number) => (
                          <div key={idx} className="p-2 bg-slate-900/80 rounded border border-slate-800/80 text-xs">
                            <span className="font-semibold text-slate-200">{p.signal}:</span> {p.inference}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Deal Desk Quoting & Governance */}
                <div className="flex items-center justify-between pt-2">
                  <div className="text-xs text-slate-400">
                    Deal Desk Governance: Max discount cap enforced by policy
                  </div>
                  <Dialog open={isQuoteOpen} onOpenChange={setIsQuoteOpen}>
                    <DialogTrigger
                      render={
                        <Button variant="outline" size="sm" className="border-slate-700 text-xs" />
                      }
                    >
                      <DollarSign className="w-3.5 h-3.5 mr-1 text-emerald-400" /> Generate Quote
                    </DialogTrigger>
                    <DialogContent className="bg-slate-900 border-slate-800 text-slate-100">
                      <DialogHeader>
                        <DialogTitle>Deal Desk Quote Generator</DialogTitle>
                        <DialogDescription className="text-slate-400">
                          Enforces discount caps and policy approval rules.
                        </DialogDescription>
                      </DialogHeader>
                      <div className="space-y-4 pt-2">
                        <div>
                          <label className="text-xs font-semibold text-slate-300">Base List Price ($ USD)</label>
                          <Input 
                            value={quoteListPrice} 
                            onChange={(e) => setQuoteListPrice(e.target.value)} 
                            className="mt-1 bg-slate-950 border-slate-700"
                          />
                        </div>
                        <div>
                          <label className="text-xs font-semibold text-slate-300">Requested Discount (%)</label>
                          <Input 
                            value={quoteDiscountPct} 
                            onChange={(e) => setQuoteDiscountPct(e.target.value)} 
                            className="mt-1 bg-slate-950 border-slate-700"
                          />
                        </div>
                        <Button onClick={() => handleGenerateQuote(selectedRoom.id)} className="w-full bg-emerald-600 hover:bg-emerald-500">
                          Calculate Quote & Check Policy
                        </Button>

                        {quoteResult && (
                          <div className="p-3 bg-slate-950 rounded border border-slate-800 text-xs space-y-1.5">
                            <div className="flex justify-between font-medium">
                              <span>Net Amount:</span>
                              <span className="text-emerald-400 font-bold">${quoteResult.net_amount?.toLocaleString()}</span>
                            </div>
                            <div className="flex justify-between">
                              <span>Approval Status:</span>
                              <span className={quoteResult.status === 'approved' ? 'text-emerald-400' : 'text-amber-400'}>
                                {quoteResult.status?.toUpperCase()}
                              </span>
                            </div>
                          </div>
                        )}
                      </div>
                    </DialogContent>
                  </Dialog>
                </div>

              </CardContent>
            </Card>
          </div>
        )}
      </div>

      {/* 4. Evidence-Grounded Outreach Composer Dialog */}
      <Dialog open={isComposerOpen} onOpenChange={setIsComposerOpen}>
        <DialogContent className="bg-slate-900 border-slate-800 text-slate-100 max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-cyan-400" />
              Evidence-Grounded Outreach Draft
            </DialogTitle>
            <DialogDescription className="text-slate-400">
              Generated copy grounded strictly in verified primary source evidence and decay-calibrated signals.
            </DialogDescription>
          </DialogHeader>

          {composerResult && (
            <div className="space-y-4 pt-2">
              {/* Groundedness Gate Badge */}
              <div className="flex items-center justify-between p-3 bg-slate-950 rounded-lg border border-slate-800">
                <div className="flex items-center gap-2">
                  {composerResult.decision === 'ready' ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  ) : (
                    <AlertTriangle className="w-5 h-5 text-amber-400" />
                  )}
                  <div>
                    <div className="text-xs font-semibold text-slate-200">
                      Groundedness Score: {Math.round((composerResult.confidence || 0) * 100)}%
                    </div>
                    <div className="text-[11px] text-slate-400">
                      {composerResult.decision === 'ready' 
                        ? 'All claims verified against Primary Source evidence. Approved for dispatch.'
                        : 'Ungrounded claims detected. Human review required before sending.'}
                    </div>
                  </div>
                </div>
                <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                  composerResult.decision === 'ready' ? 'bg-emerald-950 text-emerald-300' : 'bg-amber-950 text-amber-300'
                }`}>
                  {composerResult.decision.toUpperCase()}
                </span>
              </div>

              {/* Message Draft */}
              <div className="space-y-2">
                <div>
                  <label className="text-xs font-semibold text-slate-400">Subject</label>
                  <Input 
                    value={composerResult.data?.subject || ''} 
                    readOnly 
                    className="mt-1 bg-slate-950 border-slate-700 text-slate-100 font-medium"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-400">Body</label>
                  <Textarea 
                    value={composerResult.data?.body || ''} 
                    readOnly 
                    rows={6}
                    className="mt-1 bg-slate-950 border-slate-700 text-slate-100 text-sm leading-relaxed"
                  />
                </div>
              </div>

              {/* Citations & Evidence Records */}
              {composerResult.evidence && composerResult.evidence.length > 0 && (
                <div className="space-y-1.5">
                  <div className="text-xs uppercase font-semibold text-slate-400">Evidence Citations</div>
                  <div className="space-y-1 max-h-24 overflow-y-auto pr-1">
                    {composerResult.evidence.map((ev: any, idx: number) => (
                      <div key={idx} className="p-2 bg-slate-950 rounded border border-slate-800/80 text-[11px] text-slate-300">
                        <span className="text-cyan-400 font-mono">[{ev.source || 'Verified Source'}]:</span> {ev.claim}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={() => setIsComposerOpen(false)} className="border-slate-700 text-xs">
                  Close
                </Button>
                <Button 
                  disabled={composerResult.decision !== 'ready'} 
                  className="bg-cyan-600 hover:bg-cyan-500 text-xs font-medium"
                >
                  <Send className="w-3.5 h-3.5 mr-1" /> Dispatch to Cadence
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
