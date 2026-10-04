'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { 
  MessageSquare, 
  Mail, 
  Phone, 
  Bot, 
  Loader2, 
  Send, 
  Clock, 
  Headphones, 
  CheckCircle2, 
  Copy, 
  Code, 
  Sparkles, 
  UserCheck, 
  Radio, 
  Eye, 
  RefreshCw,
  ExternalLink,
  ShieldAlert
} from 'lucide-react';
import SupportWidget from '@/components/support-widget';

interface SupportViewProps {
  token: string | null;
  API_URL: string;
  fetchWithAuth: (url: string, options?: any) => Promise<Response>;
  fetchData: () => Promise<void>;
  tenantId?: string | null;
}

export default function SupportView({
  token,
  API_URL,
  fetchWithAuth,
  fetchData,
  tenantId,
}: SupportViewProps) {
  const [activeMainTab, setActiveMainTab] = useState<'tickets' | 'widget'>('tickets');
  const [ticketFilter, setTicketFilter] = useState<'all' | 'pending_human' | 'human_handling' | 'resolved'>('all');
  
  // Support states
  const [tickets, setTickets] = useState<any[]>([]);
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [replyText, setReplyText] = useState('');
  const [sendingReply, setSendingReply] = useState(false);
  const [actionInProgress, setActionInProgress] = useState(false);

  // Agent Presence States
  const [isAgentOnline, setIsAgentOnline] = useState<boolean>(true);
  const [presenceSaving, setPresenceSaving] = useState(false);

  // Widget & Support Settings
  const [supportSettings, setSupportSettings] = useState({
    whatsapp_auto_reply: true,
    email_auto_reply: true,
    widget_auto_reply: true,
    live_chat_enabled: true,
    widget_title: 'Customer Support',
    widget_welcome: 'Hi there! How can we assist you today?',
    widget_color: '#2563eb',
    reply_mode: 'review_first' as 'review_first' | 'auto_send',
  });
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [copiedCode, setCopiedCode] = useState(false);

  useEffect(() => {
    if (token) {
      fetchTickets();
      fetchSupportSettings();
      fetchAgentPresence();
    }
  }, [token]);

  // Heartbeat interval for Agent Presence (every 45s when online)
  useEffect(() => {
    if (!token || !isAgentOnline) return;
    const interval = setInterval(() => {
      fetchWithAuth(`${API_URL}/support/agent/presence`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_online: true }),
      }).catch(() => {});
    }, 45000);
    return () => clearInterval(interval);
  }, [token, isAgentOnline, API_URL]);

  // Auto-refresh tickets every 6s
  useEffect(() => {
    if (!token) return;
    const interval = setInterval(() => {
      fetchTickets();
    }, 6000);
    return () => clearInterval(interval);
  }, [token]);

  // Auto-refresh selected ticket messages every 3s
  useEffect(() => {
    if (selectedTicketId && token) {
      fetchMessages(selectedTicketId);
      const interval = setInterval(() => {
        fetchMessages(selectedTicketId);
      }, 3000);
      return () => clearInterval(interval);
    }
  }, [selectedTicketId, token]);

  const fetchTickets = async () => {
    if (!token) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/support/tickets`);
      if (res.ok) {
        const data = await res.json();
        setTickets(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchMessages = async (ticketId: string) => {
    if (!token) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/support/tickets/${ticketId}/messages`);
      if (res.ok) {
        const data = await res.json();
        setMessages(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchSupportSettings = async () => {
    if (!token) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/support/settings`);
      if (res.ok) {
        const data = await res.json();
        setSupportSettings({
          whatsapp_auto_reply: data.whatsapp_auto_reply ?? true,
          email_auto_reply: data.email_auto_reply ?? true,
          widget_auto_reply: data.widget_auto_reply ?? true,
          live_chat_enabled: data.live_chat_enabled ?? true,
          widget_title: data.widget_title || 'Customer Support',
          widget_welcome: data.widget_welcome || 'Hi there! How can we assist you today?',
          widget_color: data.widget_color || '#2563eb',
          reply_mode: data.reply_mode === 'auto_send' ? 'auto_send' : 'review_first',
        });
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchAgentPresence = async () => {
    if (!token) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/support/agent/presence`);
      if (res.ok) {
        const data = await res.json();
        if (data.available !== undefined) {
          setIsAgentOnline(data.available);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  const toggleAgentPresence = async () => {
    if (!token) return;
    setPresenceSaving(true);
    const nextState = !isAgentOnline;
    try {
      const res = await fetchWithAuth(`${API_URL}/support/agent/presence`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_online: nextState }),
      });
      if (res.ok) {
        setIsAgentOnline(nextState);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setPresenceSaving(false);
    }
  };

  const saveSupportSettings = async (newSettings: typeof supportSettings) => {
    if (!token) return;
    setSettingsSaving(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/support/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newSettings),
      });
      if (res.ok) {
        const data = await res.json();
        setSupportSettings(prev => ({
          ...prev,
          ...(data.settings || newSettings),
        }));
      }
    } catch (e) {
      console.error(e);
    } finally {
      setSettingsSaving(false);
    }
  };

  const handleClaimTicket = async (ticketId: string) => {
    if (!token) return;
    setActionInProgress(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/support/tickets/${ticketId}/claim`, {
        method: 'POST',
      });
      if (res.ok) {
        await fetchTickets();
        await fetchMessages(ticketId);
      } else {
        const err = await res.json();
        alert(err.detail || 'Could not claim ticket.');
      }
    } catch (e) {
      console.error(e);
    } finally {
      setActionInProgress(false);
    }
  };

  const handleResolveTicket = async (ticketId: string) => {
    if (!token) return;
    setActionInProgress(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/support/tickets/${ticketId}/resolve`, {
        method: 'POST',
      });
      if (res.ok) {
        await fetchTickets();
        await fetchMessages(ticketId);
      } else {
        const err = await res.json();
        alert(err.detail || 'Could not resolve ticket.');
      }
    } catch (e) {
      console.error(e);
    } finally {
      setActionInProgress(false);
    }
  };

  const handleSendManualReply = async () => {
    if (!selectedTicketId || !replyText.trim()) return;
    setSendingReply(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/support/tickets/${selectedTicketId}/reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: replyText })
      });
      if (res.ok) {
        setReplyText('');
        fetchMessages(selectedTicketId);
        fetchTickets();
      } else {
        const data = await res.json();
        alert(`Failed to send reply: ${data.detail || 'Unknown error'}`);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setSendingReply(false);
    }
  };

  // Filtered tickets
  const filteredTickets = tickets.filter(t => {
    if (ticketFilter === 'pending_human') return t.status === 'pending_human';
    if (ticketFilter === 'human_handling') return t.status === 'human_handling';
    if (ticketFilter === 'resolved') return t.status === 'resolved' || t.status === 'closed';
    return true;
  });

  const pendingHandoffCount = tickets.filter(t => t.status === 'pending_human').length;
  const activeHumanCount = tickets.filter(t => t.status === 'human_handling').length;
  const selectedTicket = tickets.find(t => t.id === selectedTicketId);

  // Embed script snippet
  const embedCodeSnippet = `<!-- OctaOS Support & AI Live Chat Widget -->
<script
  src="${API_URL}/support/widget/embed.js"
  data-tenant-id="${tenantId || 'YOUR_TENANT_ID'}"
  async>
</script>`;

  const copyEmbedCode = () => {
    navigator.clipboard.writeText(embedCodeSnippet);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto h-[calc(100vh-8rem)] flex flex-col animate-in fade-in duration-300">
      
      {/* Header Panel with Live Presence, Mode & Navigation */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-800 pb-4">
        <div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
            <MessageSquare className="text-blue-400 h-8 w-8" /> Customer Support Center
            {pendingHandoffCount > 0 && (
              <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 animate-pulse">
                <Headphones size={13} /> {pendingHandoffCount} Waiting for Human
              </span>
            )}
          </h1>
          <p className="text-gray-400 mt-1 text-xs">
            Omnichannel Support · Knowledge Base RAG · Live Agent Handoff · Embeddable Web Widget
          </p>
        </div>

        {/* Header Right Actions */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Presence Toggle */}
          <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-2xl bg-gray-900/60 border border-gray-800 shadow-sm">
            <span className={`w-2.5 h-2.5 rounded-full ${isAgentOnline ? 'bg-emerald-400 animate-ping' : 'bg-gray-500'}`} />
            <div className="flex flex-col">
              <span className="text-[11px] font-bold text-white">
                {isAgentOnline ? 'Online for Live Chat' : 'Away / Offline'}
              </span>
              <span className="text-[9px] text-gray-400">
                {isAgentOnline ? 'Receiving handoffs' : 'Tickets auto-escalate'}
              </span>
            </div>
            <button
              onClick={toggleAgentPresence}
              disabled={presenceSaving}
              className={`relative ml-1 inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                isAgentOnline ? 'bg-emerald-600' : 'bg-gray-800'
              }`}
            >
              <span
                className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                  isAgentOnline ? 'translate-x-4' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          {/* Main View Switcher Tabs */}
          <div className="flex rounded-2xl bg-gray-900/90 border border-gray-800 p-1">
            <button
              onClick={() => setActiveMainTab('tickets')}
              className={`px-3.5 py-1.5 text-xs font-bold rounded-xl transition-all flex items-center gap-1.5 ${
                activeMainTab === 'tickets'
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-500/20'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <MessageSquare size={13} /> Tickets & Queue
            </button>
            <button
              onClick={() => setActiveMainTab('widget')}
              className={`px-3.5 py-1.5 text-xs font-bold rounded-xl transition-all flex items-center gap-1.5 ${
                activeMainTab === 'widget'
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-500/20'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <Code size={13} /> Embed Widget
            </button>
          </div>
        </div>
      </div>

      {/* VIEW 1: TICKETS & LIVE CHAT QUEUE */}
      {activeMainTab === 'tickets' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-1 min-h-0 overflow-hidden">
          
          {/* 1. Ticket List - 4 Cols */}
          <Card className="lg:col-span-4 flex flex-col h-full overflow-hidden glass-panel border-[rgba(255,255,255,0.06)] rounded-3xl p-2 shadow-2xl relative">
            {/* Filter Pills */}
            <div className="p-2 border-b border-gray-800/80 flex flex-wrap gap-1.5">
              <button
                onClick={() => setTicketFilter('all')}
                className={`px-2.5 py-1 text-[11px] font-semibold rounded-lg transition-colors ${
                  ticketFilter === 'all' ? 'bg-gray-800 text-white' : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                All ({tickets.length})
              </button>
              <button
                onClick={() => setTicketFilter('pending_human')}
                className={`px-2.5 py-1 text-[11px] font-semibold rounded-lg transition-colors flex items-center gap-1 ${
                  ticketFilter === 'pending_human'
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                    : pendingHandoffCount > 0
                    ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20 animate-pulse'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                <Headphones size={11} /> Live Requests ({pendingHandoffCount})
              </button>
              <button
                onClick={() => setTicketFilter('human_handling')}
                className={`px-2.5 py-1 text-[11px] font-semibold rounded-lg transition-colors ${
                  ticketFilter === 'human_handling' ? 'bg-blue-600/20 text-blue-300 border border-blue-500/40' : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                Claimed ({activeHumanCount})
              </button>
              <button
                onClick={() => setTicketFilter('resolved')}
                className={`px-2.5 py-1 text-[11px] font-semibold rounded-lg transition-colors ${
                  ticketFilter === 'resolved' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                Resolved
              </button>
            </div>

            {/* Ticket Cards Stream */}
            <div className="flex-1 overflow-y-auto p-2 space-y-2">
              {filteredTickets.length === 0 && (
                <div className="text-center py-16 text-gray-500 space-y-2">
                  <Bot size={28} className="mx-auto text-gray-600" />
                  <p className="text-xs">No tickets match this filter.</p>
                </div>
              )}
              {filteredTickets.map(t => {
                const isSelected = selectedTicketId === t.id;
                let channelIcon = "💬";
                if (t.channel === "whatsapp") channelIcon = "🟢";
                if (t.channel === "email") channelIcon = "✉️";
                if (t.channel === "widget") channelIcon = "🌐";

                const isPendingHuman = t.status === "pending_human";
                const isHumanHandling = t.status === "human_handling";

                return (
                  <div
                    key={t.id}
                    onClick={() => setSelectedTicketId(t.id)}
                    className={`p-3.5 rounded-2xl border text-left cursor-pointer transition-all ${
                      isSelected 
                        ? 'bg-blue-600/10 border-blue-500/50 shadow-lg glow-support' 
                        : isPendingHuman
                        ? 'bg-amber-500/10 hover:bg-amber-500/15 border-amber-500/30'
                        : 'bg-gray-900/30 hover:bg-gray-800/40 border-gray-800/80 text-gray-300'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-[11px] font-bold text-gray-400 flex items-center gap-1">
                        {channelIcon} {(t.channel || 'widget').toUpperCase()}
                      </span>
                      {isPendingHuman ? (
                        <span className="text-[9px] font-extrabold px-2 py-0.5 rounded-full bg-amber-500 text-black animate-pulse flex items-center gap-1">
                          <Headphones size={9} /> CLAIM WAITING
                        </span>
                      ) : isHumanHandling ? (
                        <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">
                          LIVE CHAT
                        </span>
                      ) : (
                        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase ${
                          t.priority === 'high' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 'bg-gray-800 text-gray-400'
                        }`}>
                          {t.priority}
                        </span>
                      )}
                    </div>

                    <h4 className="font-bold text-xs text-white truncate mb-1">{t.subject}</h4>
                    
                    {/* Customer Info Snippet */}
                    <div className="text-[11px] text-gray-400 truncate mb-2">
                      {t.customer_name ? `${t.customer_name} · ` : ''}{t.customer_contact || t.customer_email || 'Visitor'}
                    </div>

                    <div className="flex items-center justify-between pt-1 border-t border-white/5">
                      <span className={`text-[9px] font-extrabold px-1.5 py-0.5 rounded-full ${
                        t.status === 'open' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
                        t.status === 'resolved' ? 'bg-gray-500/20 text-gray-400' :
                        'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                      }`}>
                        {t.status.toUpperCase()}
                      </span>
                      <span className="text-[9px] text-gray-500">
                        {new Date(t.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>

          {/* 2. Conversation Thread & Claim/Resolve Controls - 8 Cols */}
          <Card className="lg:col-span-8 flex flex-col h-full overflow-hidden glass-panel border-[rgba(255,255,255,0.06)] rounded-3xl p-0 shadow-2xl relative">
            {selectedTicketId && selectedTicket ? (
              <>
                {/* Thread Header with Claim & Resolve CTA */}
                <div className="px-5 py-3.5 bg-gray-950/60 border-b border-gray-800 flex items-center justify-between gap-4">
                  <div className="truncate flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="font-bold text-white text-sm truncate">
                        {selectedTicket.subject}
                      </h3>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 uppercase">
                        {selectedTicket.channel}
                      </span>
                    </div>
                    <div className="text-[11px] text-gray-400 mt-1 flex flex-wrap gap-3">
                      {selectedTicket.customer_name && (
                        <span>👤 <strong className="text-gray-300">{selectedTicket.customer_name}</strong></span>
                      )}
                      {selectedTicket.customer_email && (
                        <span>✉️ {selectedTicket.customer_email}</span>
                      )}
                      {selectedTicket.customer_phone && (
                        <span>📱 {selectedTicket.customer_phone}</span>
                      )}
                    </div>
                  </div>

                  {/* Actions Bar */}
                  <div className="flex items-center gap-2">
                    {selectedTicket.status === 'pending_human' && (
                      <Button
                        size="sm"
                        disabled={actionInProgress}
                        onClick={() => handleClaimTicket(selectedTicket.id)}
                        className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs h-8 px-3.5 rounded-xl shadow-lg shadow-emerald-600/20 flex items-center gap-1.5 transition-all hover:scale-[1.02]"
                      >
                        <UserCheck size={14} /> Claim & Join Live Chat
                      </Button>
                    )}

                    {selectedTicket.status === 'human_handling' && (
                      <Button
                        size="sm"
                        disabled={actionInProgress}
                        onClick={() => handleResolveTicket(selectedTicket.id)}
                        className="bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs h-8 px-3.5 rounded-xl shadow-lg shadow-blue-600/20 flex items-center gap-1.5 transition-all hover:scale-[1.02]"
                      >
                        <CheckCircle2 size={14} /> Resolve & Return to AI
                      </Button>
                    )}

                    {selectedTicket.status === 'resolved' && (
                      <span className="text-xs bg-gray-800 text-gray-300 border border-gray-700 px-2.5 py-1 rounded-lg font-semibold flex items-center gap-1">
                        <CheckCircle2 size={13} className="text-emerald-400" /> Resolved
                      </span>
                    )}
                  </div>
                </div>

                {/* Chat Messages Stream */}
                <div className="flex-1 overflow-y-auto p-4 space-y-3.5 bg-gray-950/20">
                  {messages.length === 0 && (
                    <p className="text-xs text-gray-500 text-center py-10">No messages in this ticket.</p>
                  )}
                  {messages.map(m => {
                    const isAgent = m.sender === "agent";
                    const isSys = m.sender === "system";

                    if (isSys) {
                      return (
                        <div key={m.id} className="flex justify-center my-2">
                          <span className="bg-gray-900/90 border border-gray-800 text-gray-400 text-[10px] px-3.5 py-1 rounded-full text-center max-w-[85%] leading-relaxed">
                            {m.content}
                          </span>
                        </div>
                      );
                    }

                    return (
                      <div
                        key={m.id}
                        className={`flex ${isAgent ? 'justify-end' : 'justify-start'}`}
                      >
                        <div
                          className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-xs leading-relaxed shadow-sm ${
                            isAgent
                              ? 'bg-blue-600 text-white rounded-tr-none shadow-lg shadow-blue-500/15'
                              : 'bg-gray-900 border border-gray-800 text-gray-100 rounded-tl-none'
                            }`}
                        >
                          <p className="whitespace-pre-wrap">{m.content}</p>
                          <span
                            className={`text-[8px] mt-1 block text-right font-medium ${
                              isAgent ? 'text-blue-200' : 'text-gray-500'
                            }`}
                          >
                            {m.created_at ? new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Reply Input Box */}
                <div className="p-3 border-t border-gray-800 bg-gray-950/40">
                  <div className="flex gap-2">
                    <Textarea
                      placeholder={
                        selectedTicket.status === 'human_handling'
                          ? "Type live reply directly to customer..."
                          : "Type a response to send back to customer..."
                      }
                      value={replyText}
                      onChange={e => setReplyText(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          handleSendManualReply();
                        }
                      }}
                      className="bg-gray-900/80 border-gray-800 text-white focus:border-blue-500 rounded-xl min-h-[50px] text-xs resize-none flex-1"
                    />
                    <Button
                      onClick={handleSendManualReply}
                      disabled={sendingReply || !replyText.trim()}
                      className="bg-blue-600 hover:bg-blue-500 text-white rounded-xl h-auto self-stretch px-4 flex flex-col justify-center items-center shadow-lg shadow-blue-500/20 transition-all hover:scale-[1.02] active:scale-95"
                    >
                      <Send size={15} className="mb-0.5" />
                      <span className="text-[10px] font-bold">Reply</span>
                    </Button>
                  </div>
                </div>
              </>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-center p-8 text-gray-500">
                <div className="text-4xl mb-3 animate-bounce">💬</div>
                <h4 className="font-bold text-white text-sm">Select a ticket from the left</h4>
                <p className="text-xs text-gray-400 max-w-xs mt-1">
                  Claim waiting live chat requests or respond to customer tickets.
                </p>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* VIEW 2: EMBED WIDGET GENERATOR & LIVE PREVIEW */}
      {activeMainTab === 'widget' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-1 min-h-0 overflow-y-auto">
          
          {/* Left Panel: Configuration & Code Copy - 7 Cols */}
          <div className="lg:col-span-7 space-y-5">
            <Card className="glass-panel border-white/5 p-6 rounded-3xl space-y-5">
              <div>
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <Code size={18} className="text-blue-400" /> Website & App Widget Integration
                </h3>
                <p className="text-xs text-gray-400 mt-1">
                  Embed this floating AI Support & Live Chat button into any website, web application, WordPress, or Shopify site with a single script tag.
                </p>
              </div>

              {/* Code Snippet Box */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-gray-300 flex items-center gap-1.5">
                    <Sparkles size={12} className="text-amber-400" /> Embed Code Snippet
                  </span>
                  <Button
                    size="sm"
                    onClick={copyEmbedCode}
                    className="h-7 text-xs bg-blue-600 hover:bg-blue-500 text-white rounded-lg flex items-center gap-1.5 shadow-md shadow-blue-500/20"
                  >
                    {copiedCode ? <CheckCircle2 size={13} className="text-emerald-300" /> : <Copy size={13} />}
                    {copiedCode ? 'Copied!' : 'Copy Code'}
                  </Button>
                </div>

                <div className="bg-gray-950 border border-gray-800 rounded-2xl p-4 font-mono text-xs text-blue-300 overflow-x-auto relative">
                  <pre className="whitespace-pre-wrap">{embedCodeSnippet}</pre>
                </div>
              </div>

              {/* Widget Customization Form */}
              <div className="border-t border-gray-800/80 pt-4 space-y-4">
                <h4 className="text-xs font-bold text-white uppercase tracking-wider text-gray-400">
                  Widget Branding & Behavior
                </h4>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-gray-300 mb-1">Widget Title</label>
                    <Input
                      type="text"
                      value={supportSettings.widget_title}
                      onChange={e => setSupportSettings({ ...supportSettings, widget_title: e.target.value })}
                      className="bg-gray-900 border-gray-800 text-white text-xs rounded-xl"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-300 mb-1">Brand Color (Hex)</label>
                    <div className="flex gap-2">
                      <input
                        type="color"
                        value={supportSettings.widget_color}
                        onChange={e => setSupportSettings({ ...supportSettings, widget_color: e.target.value })}
                        className="w-9 h-9 rounded-xl bg-transparent border-0 cursor-pointer"
                      />
                      <Input
                        type="text"
                        value={supportSettings.widget_color}
                        onChange={e => setSupportSettings({ ...supportSettings, widget_color: e.target.value })}
                        className="bg-gray-900 border-gray-800 text-white text-xs rounded-xl flex-1"
                      />
                    </div>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-300 mb-1">Welcome Message</label>
                  <Textarea
                    value={supportSettings.widget_welcome}
                    onChange={e => setSupportSettings({ ...supportSettings, widget_welcome: e.target.value })}
                    className="bg-gray-900 border-gray-800 text-white text-xs rounded-xl min-h-[60px] resize-none"
                  />
                </div>

                <div className="flex items-center justify-between pt-2">
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-bold text-white">Live Chat Handoff Enabled</span>
                    <button
                      onClick={() => setSupportSettings({ ...supportSettings, live_chat_enabled: !supportSettings.live_chat_enabled })}
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                        supportSettings.live_chat_enabled ? 'bg-emerald-600' : 'bg-gray-800'
                      }`}
                    >
                      <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                        supportSettings.live_chat_enabled ? 'translate-x-4' : 'translate-x-1'
                      }`} />
                    </button>
                  </div>

                  <Button
                    onClick={() => saveSupportSettings(supportSettings)}
                    disabled={settingsSaving}
                    className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold h-8 px-4 rounded-xl shadow-lg shadow-emerald-600/20"
                  >
                    {settingsSaving ? 'Saving...' : 'Save Settings'}
                  </Button>
                </div>
              </div>
            </Card>
          </div>

          {/* Right Panel: Interactive Sandbox Preview - 5 Cols */}
          <div className="lg:col-span-5 flex flex-col">
            <Card className="glass-panel border-white/5 p-6 rounded-3xl flex-1 flex flex-col relative overflow-hidden bg-gradient-to-b from-gray-950/80 to-blue-950/10">
              <div className="flex items-center justify-between mb-4 border-b border-gray-800/80 pb-3">
                <span className="text-xs font-bold text-white flex items-center gap-1.5">
                  <Eye size={14} className="text-blue-400" /> Interactive Live Preview
                </span>
                <span className="text-[10px] text-gray-500">Click the floating button below</span>
              </div>

              <div className="flex-1 border border-dashed border-gray-800 rounded-2xl relative min-h-[460px] flex items-center justify-center p-6 text-center text-gray-500">
                <div className="space-y-2 max-w-xs">
                  <p className="text-xs text-gray-400 font-semibold">Your Website Preview Area</p>
                  <p className="text-[11px] text-gray-500">
                    The support button floats in the bottom right corner of this sandbox. You can click to open and test the full AI chat, RAG, and ticket escalation experience!
                  </p>
                </div>

                {/* Mount Interactive Widget inside Preview */}
                <SupportWidget
                  tenantId={tenantId || 'test-tenant'}
                  API_URL={API_URL}
                  defaultOpen={true}
                />
              </div>
            </Card>
          </div>

        </div>
      )}

    </div>
  );
}
