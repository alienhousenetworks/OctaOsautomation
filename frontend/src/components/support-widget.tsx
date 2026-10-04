'use client';

import React, { useState, useEffect, useRef } from 'react';
import { 
  MessageSquare, 
  Bot, 
  User, 
  Send, 
  X, 
  FileText, 
  CheckCircle2, 
  AlertCircle, 
  Phone, 
  Mail, 
  Sparkles, 
  Clock, 
  ChevronRight,
  Headphones
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';

interface SupportWidgetProps {
  tenantId: string | null;
  API_URL: string;
  defaultOpen?: boolean;
}

interface MessageItem {
  id?: string;
  sender: 'customer' | 'agent' | 'system';
  content: string;
  citations?: string[];
  created_at?: string;
}

export default function SupportWidget({
  tenantId,
  API_URL,
  defaultOpen = false,
}: SupportWidgetProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const [activeTab, setActiveTab] = useState<'chat' | 'ticket'>('chat');
  const [sessionId, setSessionId] = useState<string>('');
  const [config, setConfig] = useState<{
    title: string;
    welcome_message: string;
    brand_color: string;
    live_chat_available: boolean;
  }>({
    title: 'Customer Support',
    welcome_message: 'Hi there! How can we assist you today?',
    brand_color: '#2563eb',
    live_chat_available: false,
  });

  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [inputText, setInputText] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [suggestLiveChat, setSuggestLiveChat] = useState<{
    suggested: boolean;
    reason?: string;
    available?: boolean;
  }>({ suggested: false });
  const [ticketStatus, setTicketStatus] = useState<string>('open');
  const [agentName, setAgentName] = useState<string | null>(null);

  // Ticket Form States
  const [ticketForm, setTicketForm] = useState({
    problem: '',
    name: '',
    email: '',
    phone: '',
  });
  const [ticketSubmitting, setTicketSubmitting] = useState(false);
  const [ticketSuccessMsg, setTicketSuccessMsg] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Initialize Session
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem(`octaos_widget_session_${tenantId || 'default'}`);
      if (stored) {
        setSessionId(stored);
      } else {
        const newId = `sess_${Math.random().toString(36).substring(2, 10)}_${Date.now()}`;
        localStorage.setItem(`octaos_widget_session_${tenantId || 'default'}`, newId);
        setSessionId(newId);
      }
    }
  }, [tenantId]);

  // Fetch Config
  useEffect(() => {
    if (!tenantId) return;
    const fetchConfig = async () => {
      try {
        const res = await fetch(`${API_URL}/support/widget/config/${tenantId}`);
        if (res.ok) {
          const data = await res.json();
          setConfig(data);
          if (messages.length === 0) {
            setMessages([
              {
                sender: 'agent',
                content: data.welcome_message || 'Hi there! How can we assist you today?',
              },
            ]);
          }
        }
      } catch (e) {
        console.error('Widget config fetch error:', e);
      }
    };
    fetchConfig();
  }, [tenantId, API_URL]);

  // Scroll to bottom
  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isOpen]);

  // Poll for agent messages when open
  useEffect(() => {
    if (!isOpen || !tenantId || !sessionId) return;

    const poll = async () => {
      try {
        const res = await fetch(`${API_URL}/support/widget/poll/${tenantId}/${sessionId}`);
        if (res.ok) {
          const data = await res.json();
          if (data.ticket) {
            setTicketStatus(data.ticket.status);
            setAgentName(data.ticket.agent_name || null);
          }
          if (data.live_chat_available !== undefined) {
            setConfig(prev => ({ ...prev, live_chat_available: data.live_chat_available }));
          }
          if (data.messages && data.messages.length > 0) {
            setMessages(prev => {
              const citationsByContent: Record<string, string[]> = {};
              prev.forEach(p => {
                if (p.citations && p.citations.length) citationsByContent[p.content] = p.citations;
              });
              const welcome = prev.length > 0 && !prev[0].id && prev[0].sender === 'agent' ? [prev[0]] : [];
              const incoming = data.messages.map((m: any) => ({
                id: m.id,
                sender: m.sender,
                content: m.content,
                created_at: m.created_at,
                citations: citationsByContent[m.content],
              }));
              return [...welcome, ...incoming];
            });
          }
        }
      } catch (e) {
        // ignore polling errors
      }
    };

    poll();
    const interval = setInterval(poll, 3000);
    return () => clearInterval(interval);
  }, [isOpen, tenantId, sessionId, API_URL]);

  const handleSendMessage = async (customText?: string, action?: string) => {
    const textToSend = (customText || inputText).trim();
    if (!textToSend && !action) return;

    if (textToSend) {
      setMessages(prev => [
        ...prev,
        { sender: 'customer', content: textToSend }
      ]);
      setInputText('');
    }

    setIsSending(true);
    setSuggestLiveChat({ suggested: false });

    try {
      const res = await fetch(`${API_URL}/support/widget/message/${tenantId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message: textToSend,
          action: action || 'chat',
        })
      });

      if (res.ok) {
        const data = await res.json();
        if (data.reply) {
          setMessages(prev => [
            ...prev,
            {
              sender: 'agent',
              content: data.reply,
              citations: data.citations || [],
            }
          ]);
        }

        if (data.suggest_live_chat) {
          setSuggestLiveChat({
            suggested: true,
            reason: data.reason,
            available: data.live_chat_available,
          });
        }

        if (data.action_required === 'raise_ticket') {
          if (data.prefill) {
            setTicketForm(prev => ({
              ...prev,
              problem: data.prefill.problem || prev.problem,
              name: data.prefill.name || prev.name,
              email: data.prefill.email || prev.email,
            }));
          }
          setTimeout(() => setActiveTab('ticket'), 1200);
        }

        if (data.status === 'handoff_queued') {
          setTicketStatus('pending_human');
        }
      } else {
        setMessages(prev => [
          ...prev,
          { sender: 'system', content: 'Could not send message. Please retry.' }
        ]);
      }
    } catch (e) {
      setMessages(prev => [
        ...prev,
        { sender: 'system', content: 'Connection error. Please try again.' }
      ]);
    } finally {
      setIsSending(false);
    }
  };

  const handleRaiseTicket = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticketForm.problem || !ticketForm.name || !ticketForm.email || !ticketForm.phone) {
      alert('Please fill out all fields.');
      return;
    }

    setTicketSubmitting(true);
    try {
      const res = await fetch(`${API_URL}/support/widget/raise-ticket/${tenantId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          problem: ticketForm.problem,
          name: ticketForm.name,
          email: ticketForm.email,
          mobile_no: ticketForm.phone,
        })
      });

      if (res.ok) {
        const data = await res.json();
        setTicketSuccessMsg(data.message || 'Ticket submitted successfully!');
        setTimeout(() => {
          setActiveTab('chat');
          setTicketSuccessMsg(null);
          setMessages(prev => [
            ...prev,
            {
              sender: 'system',
              content: `✅ Ticket #${data.ticket_id ? data.ticket_id.substring(0, 8) : ''} submitted. We will contact you at ${ticketForm.email} or ${ticketForm.phone} shortly.`
            }
          ]);
          setTicketForm({ problem: '', name: '', email: '', phone: '' });
        }, 1800);
      } else {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || 'Failed to submit ticket');
      }
    } catch (e) {
      alert('Network error while submitting ticket.');
    } finally {
      setTicketSubmitting(false);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 font-sans">
      {/* Expandable Chat Window */}
      {isOpen && (
        <div className="absolute bottom-16 right-0 w-[380px] sm:w-[410px] h-[580px] max-h-[calc(100vh-6rem)] bg-gray-950/95 backdrop-blur-xl border border-white/10 rounded-3xl shadow-2xl flex flex-col overflow-hidden animate-in fade-in slide-in-from-bottom-5 duration-300">
          
          {/* Header */}
          <div className="p-4 bg-gradient-to-r from-gray-900 via-gray-900/90 to-blue-950/40 border-b border-white/10 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400 shadow-inner">
                {ticketStatus === 'human_handling' ? (
                  <Headphones size={18} className="animate-pulse" />
                ) : (
                  <Bot size={18} />
                )}
              </div>
              <div>
                <h4 className="text-sm font-bold text-white tracking-tight flex items-center gap-1.5">
                  {config.title}
                  <span className="text-[10px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 px-1.5 py-0.2 rounded-full">
                    AI + Live
                  </span>
                </h4>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className={`w-2 h-2 rounded-full ${
                    ticketStatus === 'human_handling' ? 'bg-emerald-400 animate-ping' :
                    ticketStatus === 'pending_human' ? 'bg-amber-400 animate-pulse' :
                    config.live_chat_available ? 'bg-emerald-500' : 'bg-blue-400'
                  }`} />
                  <span className="text-[11px] text-gray-400 font-medium">
                    {ticketStatus === 'human_handling'
                      ? (agentName ? `Live with ${agentName}` : 'Live Agent Active')
                      : ticketStatus === 'pending_human'
                      ? 'Connecting to Agent...'
                      : config.live_chat_available
                      ? 'Live Support Available'
                      : 'AI Assistant Ready'}
                  </span>
                </div>
              </div>
            </div>

            <button
              onClick={() => setIsOpen(false)}
              className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
              title="Close Chat"
            >
              <X size={18} />
            </button>
          </div>

          {/* Navigation Bar: Chat vs Ticket */}
          <div className="flex bg-gray-900/80 border-b border-white/5 p-1 gap-1">
            <button
              onClick={() => setActiveTab('chat')}
              className={`flex-1 py-1.5 text-xs font-semibold rounded-xl transition-all flex items-center justify-center gap-1.5 ${
                activeTab === 'chat'
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-500/20'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
              }`}
            >
              <MessageSquare size={13} /> Live Assistant
            </button>
            <button
              onClick={() => setActiveTab('ticket')}
              className={`flex-1 py-1.5 text-xs font-semibold rounded-xl transition-all flex items-center justify-center gap-1.5 ${
                activeTab === 'ticket'
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-500/20'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
              }`}
            >
              <FileText size={13} /> Raise Ticket
            </button>
          </div>

          {/* Tab 1: Chat Stream */}
          {activeTab === 'chat' && (
            <div className="flex-1 flex flex-col min-h-0 bg-gray-950/40">
              <div className="flex-1 overflow-y-auto p-4 space-y-3.5 text-xs">
                {messages.map((m, idx) => {
                  const isUser = m.sender === 'customer';
                  const isSys = m.sender === 'system';

                  if (isSys) {
                    return (
                      <div key={idx} className="flex justify-center my-1.5">
                        <span className="bg-gray-900/80 border border-gray-800 text-gray-400 text-[10px] px-3 py-1 rounded-full text-center max-w-[90%] leading-relaxed">
                          {m.content}
                        </span>
                      </div>
                    );
                  }

                  return (
                    <div
                      key={idx}
                      className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}
                    >
                      <div
                        className={`max-w-[85%] rounded-2xl p-3 leading-relaxed shadow-sm ${
                          isUser
                            ? 'bg-blue-600 text-white rounded-tr-none shadow-blue-500/10'
                            : 'bg-gray-900 border border-white/10 text-gray-200 rounded-tl-none'
                        }`}
                      >
                        <p className="whitespace-pre-wrap">{m.content}</p>

                        {/* Knowledge Base Citations */}
                        {m.citations && m.citations.length > 0 && (
                          <div className="mt-2 pt-2 border-t border-white/10 text-[10px] text-gray-400 flex flex-wrap gap-1 items-center">
                            <span className="font-semibold text-blue-400">Sources:</span>
                            {m.citations.map((c, cIdx) => (
                              <span
                                key={cIdx}
                                className="bg-gray-800 border border-gray-700 px-1.5 py-0.5 rounded text-[9px]"
                              >
                                {c}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}

                {/* Suggest Live Chat Banner */}
                {suggestLiveChat.suggested && (
                  <div className="p-3 rounded-2xl bg-indigo-950/40 border border-indigo-500/30 text-indigo-200 space-y-2 animate-in fade-in">
                    <p className="text-[11px] leading-relaxed">
                      {suggestLiveChat.reason === 'loop_detected'
                        ? "It looks like we're having trouble resolving this. Would you like to connect with a live support agent?"
                        : "I don't have enough details in our knowledge base for this question. Would you like to speak to a specialist?"}
                    </p>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={() => {
                          if (suggestLiveChat.available) {
                            handleSendMessage('Connect to live chat', 'request_handoff');
                          } else {
                            setActiveTab('ticket');
                          }
                        }}
                        className="bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] h-7 px-3 rounded-lg flex items-center gap-1 shadow-md shadow-indigo-600/20"
                      >
                        <Headphones size={12} />
                        {suggestLiveChat.available ? 'Connect to Live Chat' : 'Raise Support Ticket'}
                      </Button>
                    </div>
                  </div>
                )}

                {isSending && (
                  <div className="flex items-center gap-2 text-gray-500 text-xs italic">
                    <Bot size={13} className="animate-spin text-blue-400" />
                    <span>Thinking with Knowledge Base...</span>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>

              {/* Quick Action Chips */}
              <div className="px-3 py-1.5 bg-gray-900/60 border-t border-white/5 flex gap-1.5 overflow-x-auto">
                <button
                  type="button"
                  onClick={() => handleSendMessage('I would like to speak with a human support agent.', 'request_handoff')}
                  className="px-2.5 py-1 rounded-full bg-blue-600/10 border border-blue-500/20 text-blue-300 hover:bg-blue-600/20 text-[10px] font-medium whitespace-nowrap transition-colors flex items-center gap-1"
                >
                  <Headphones size={10} /> Talk to Human
                </button>
                <button
                  type="button"
                  onClick={() => handleSendMessage('Can you explain pricing and plan features?')}
                  className="px-2.5 py-1 rounded-full bg-gray-800 hover:bg-gray-700 text-gray-300 text-[10px] whitespace-nowrap transition-colors"
                >
                  Pricing
                </button>
                <button
                  type="button"
                  onClick={() => handleSendMessage('What are your company refund and cancellation policies?')}
                  className="px-2.5 py-1 rounded-full bg-gray-800 hover:bg-gray-700 text-gray-300 text-[10px] whitespace-nowrap transition-colors"
                >
                  Policies
                </button>
              </div>

              {/* Input Area */}
              <div className="p-3 bg-gray-950 border-t border-white/10 flex gap-2 items-center">
                <Input
                  type="text"
                  placeholder="Ask a question or request human..."
                  value={inputText}
                  onChange={e => setInputText(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter') handleSendMessage();
                  }}
                  disabled={isSending}
                  className="bg-gray-900 border-gray-800 text-white text-xs h-9 focus:border-blue-500 rounded-xl"
                />
                <Button
                  onClick={() => handleSendMessage()}
                  disabled={isSending || !inputText.trim()}
                  className="bg-blue-600 hover:bg-blue-500 text-white h-9 w-9 p-0 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/20 transition-all active:scale-95"
                >
                  <Send size={14} />
                </Button>
              </div>
            </div>
          )}

          {/* Tab 2: Raise Ticket Form */}
          {activeTab === 'ticket' && (
            <form onSubmit={handleRaiseTicket} className="flex-1 p-5 overflow-y-auto space-y-3.5 text-xs bg-gray-950/40">
              <div className="bg-gray-900/60 p-3 rounded-2xl border border-white/5 space-y-1">
                <h5 className="font-bold text-white text-xs flex items-center gap-1.5">
                  <FileText size={13} className="text-blue-400" /> Need Human Follow-up?
                </h5>
                <p className="text-[11px] text-gray-400 leading-relaxed">
                  Submit your problem description and contact information. A specialist will review and respond directly.
                </p>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-gray-300 mb-1">
                  Problem Description *
                </label>
                <Textarea
                  required
                  placeholder="Describe your question or issue in detail..."
                  value={ticketForm.problem}
                  onChange={e => setTicketForm({ ...ticketForm, problem: e.target.value })}
                  className="bg-gray-900 border-gray-800 text-white text-xs min-h-[80px] rounded-xl focus:border-blue-500 resize-none"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-gray-300 mb-1 flex items-center gap-1">
                  <User size={11} className="text-gray-400" /> Full Name *
                </label>
                <Input
                  required
                  type="text"
                  placeholder="Your full name"
                  value={ticketForm.name}
                  onChange={e => setTicketForm({ ...ticketForm, name: e.target.value })}
                  className="bg-gray-900 border-gray-800 text-white text-xs h-8 rounded-xl focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-gray-300 mb-1 flex items-center gap-1">
                  <Mail size={11} className="text-gray-400" /> Email Address *
                </label>
                <Input
                  required
                  type="email"
                  placeholder="name@company.com"
                  value={ticketForm.email}
                  onChange={e => setTicketForm({ ...ticketForm, email: e.target.value })}
                  className="bg-gray-900 border-gray-800 text-white text-xs h-8 rounded-xl focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-gray-300 mb-1 flex items-center gap-1">
                  <Phone size={11} className="text-gray-400" /> Mobile Number *
                </label>
                <Input
                  required
                  type="tel"
                  placeholder="+1 (555) 000-0000"
                  value={ticketForm.phone}
                  onChange={e => setTicketForm({ ...ticketForm, phone: e.target.value })}
                  className="bg-gray-900 border-gray-800 text-white text-xs h-8 rounded-xl focus:border-blue-500"
                />
              </div>

              {ticketSuccessMsg && (
                <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-center font-medium">
                  {ticketSuccessMsg}
                </div>
              )}

              <Button
                type="submit"
                disabled={ticketSubmitting}
                className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-bold h-9 rounded-xl shadow-lg shadow-emerald-600/20 transition-all hover:scale-[1.01]"
              >
                {ticketSubmitting ? 'Submitting Ticket...' : 'Submit Priority Ticket'}
              </Button>
            </form>
          )}
        </div>
      )}

      {/* Floating Launcher Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-14 h-14 rounded-full bg-gradient-to-tr from-blue-700 via-blue-600 to-indigo-600 text-white flex items-center justify-center shadow-xl shadow-blue-500/30 border border-white/20 transition-all hover:scale-110 active:scale-95 group relative"
        title="Support & Live Chat"
      >
        <span className={`absolute top-0 right-0 w-3.5 h-3.5 rounded-full border-2 border-gray-950 ${
          ticketStatus === 'human_handling' ? 'bg-emerald-400 animate-ping' :
          config.live_chat_available ? 'bg-emerald-500' : 'bg-blue-400'
        }`} />
        {isOpen ? (
          <X size={24} className="transition-transform group-hover:rotate-90 duration-200" />
        ) : (
          <MessageSquare size={24} className="transition-transform group-hover:-translate-y-0.5 duration-200" />
        )}
      </button>
    </div>
  );
}
