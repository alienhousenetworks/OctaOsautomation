'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Bot, Loader2, Send, Clock, Plus, Cpu, Zap, Activity, Users, FileText, Trash2, Sparkles, Check } from 'lucide-react';
import { Textarea } from '@/components/ui/textarea';

interface OrchestratorViewProps {
  token: string | null;
  API_URL: string;
  fetchWithAuth: (url: string, options?: any) => Promise<Response>;
  fetchData: () => Promise<void>;
  apps: any[];
  configuredProviders: string[];
  timeline: any[];
  queue: { posts: any[]; leads: any[] };
  handleApprovePost: (postId: string) => Promise<void>;
  handleRejectPost: (postId: string) => Promise<void>;
}

export default function OrchestratorView({
  token,
  API_URL,
  fetchWithAuth,
  fetchData,
  apps,
  configuredProviders,
  timeline,
  queue,
  handleApprovePost,
  handleRejectPost,
}: OrchestratorViewProps) {
  // Orchestrator states relocated here
  const [orchMessages, setOrchMessages] = useState<any[]>([]);
  const [orchInput, setOrchInput] = useState('');
  const [prompt, setPrompt] = useState(''); // dummy prompt state for handleRunCommand backwards compatibility
  const [orchInlineKeyValue, setOrchInlineKeyValue] = useState('');
  const [orchModel, setOrchModel] = useState('claude-sonnet-4-6');
  const [orchProvider, setOrchProvider] = useState('anthropic');
  const [loading, setLoading] = useState(false);

  const orchChatEndRef = useRef<HTMLDivElement>(null);

  // Orchestrator chat: load from localStorage on mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('orchestrator_chat_messages');
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          if (parsed.length > 0) {
            setOrchMessages(parsed);
            return;
          }
        } catch (_e) { /* ignore parse errors */ }
      }
      setOrchMessages([{
        id: 'welcome',
        role: 'assistant',
        content: "Welcome to the Orchestrator AI Console. I coordinate your Marketing, Sales, Support, and HR teams to accomplish complex business goals.\n\nTell me what you'd like to achieve, or click a suggested prompt below.",
        timestamp: new Date().toISOString()
      }]);
    }
  }, []);

  // Persist orchestrator chat to localStorage
  useEffect(() => {
    if (orchMessages.length > 0) {
      localStorage.setItem('orchestrator_chat_messages', JSON.stringify(orchMessages));
    }
  }, [orchMessages]);

  // Auto-scroll orchestrator chat to bottom
  useEffect(() => {
    orchChatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [orchMessages]);

  // Handler functions
    const handleRunCommand = async () => {
    const inputText = orchInput.trim() || prompt.trim();
    if (!inputText) return;

    const userMsg = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: inputText,
      timestamp: new Date().toISOString()
    };
    setOrchMessages(prev => [...prev, userMsg]);
    setOrchInput('');
    setPrompt('');
    setLoading(true);

    try {
      const res = await fetchWithAuth(`${API_URL}/commands/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: inputText, provider: orchProvider, model: orchModel })
      });
      const data = await res.json();

      const assistantMsg = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: data.results?.map((r: any) => r.message || r.status).join('\n') || 'Task delegated to agents.',
        plan: data.plan,
        results: data.results,
        timestamp: new Date().toISOString()
      };
      setOrchMessages(prev => [...prev, assistantMsg]);

      if (res.ok) {
        fetchData();
      }
    } catch (e) {
      console.error(e);
      const errorMsg = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your request. Please try again.',
        timestamp: new Date().toISOString()
      };
      setOrchMessages(prev => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const clearOrchestratorChat = () => {

      const welcome = [{
      id: 'welcome',
      role: 'assistant',
      content: "Welcome to the Orchestrator AI Console. I coordinate your Marketing, Sales, Support, and HR teams to accomplish complex business goals.\n\nTell me what you'd like to achieve, or click a suggested prompt below.",
      timestamp: new Date().toISOString()
    }];
    setOrchMessages(welcome);
    localStorage.setItem('orchestrator_chat_messages', JSON.stringify(welcome));
  };



  const handleSaveInlineApiKey = async (provider: string) => {
    if (!orchInlineKeyValue) return;
    try {
      await fetchWithAuth(`${API_URL}/commands/keys`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, key: orchInlineKeyValue })
      });
      setOrchInlineKeyValue('');
      alert(`${provider} API key saved successfully!`);
      fetchData();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 max-w-[1600px] mx-auto animate-in fade-in duration-300" style={{ height: 'calc(100vh - 140px)' }}>
              {/* LEFT: Chat Console - 8 cols */}
              <div className="lg:col-span-8 flex flex-col h-full min-h-0">
                <Card className="flex-1 flex flex-col glass-panel border-transparent rounded-3xl overflow-hidden shadow-2xl relative min-h-0">
                  {/* Decorative top gradient */}
                  <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-violet-500 via-purple-500 to-indigo-500" />

                  {/* HEADER */}
                  <div className="px-5 py-3 border-b border-gray-800/60 bg-gray-950/40 flex items-center justify-between gap-3 flex-wrap flex-shrink-0">
                    <div className="flex items-center gap-3">
                      <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/20">
                        <Cpu size={18} className="text-white" />
                      </div>
                      <div>
                        <h3 className="font-extrabold text-white text-sm tracking-tight">Orchestrator AI</h3>
                        <p className="text-[10px] text-gray-400 font-medium">Multi-agent task coordinator</p>
                      </div>
                      <span className="ml-1 flex items-center gap-1.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-full text-[10px] font-bold">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" /> Online
                      </span>
                    </div>

                    <div className="flex items-center gap-2 flex-wrap">
                      {/* Integration Status Pills */}
                      <div className="hidden md:flex items-center gap-1">
                        {['openrouter', 'together', 'anthropic', 'openai', 'gemini', 'groq', 'meta', 'linkedin', 'smtp', 'apollo'].map(prov => (
                          <span key={prov} className={`text-[9px] font-bold px-1.5 py-0.5 rounded-md border transition-colors ${
                            configuredProviders.includes(prov)
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                              : 'bg-gray-900/40 text-gray-600 border-gray-800'
                          }`}>
                            {prov === 'openrouter' ? 'OpenRouter' : prov === 'together' ? 'Together' : prov === 'groq' ? 'Groq' : prov === 'anthropic' ? 'Claude' : prov === 'openai' ? 'GPT' : prov === 'gemini' ? 'Gemini' : prov === 'meta' ? 'Meta' : prov === 'linkedin' ? 'LinkedIn' : prov === 'smtp' ? 'SMTP' : 'Apollo'}
                          </span>
                        ))}
                      </div>

                      {/* Model Selectors */}
                      <Select value={orchProvider} onValueChange={(val) => {
                        if (val) {
                          setOrchProvider(val);
                          if (val === 'openrouter') setOrchModel('google/gemini-2.5-flash');
                          else if (val === 'together') setOrchModel('meta-llama/Llama-3.3-70B-Instruct-Turbo');
                          else if (val === 'groq') setOrchModel('llama-3.3-70b-versatile');
                          else if (val === 'grok') setOrchModel('grok-2-latest');
                          else if (val === 'anthropic') setOrchModel('claude-sonnet-4-6');
                          else if (val === 'openai') setOrchModel('gpt-4o');
                          else if (val === 'gemini') setOrchModel('gemini-2.5-pro');
                        }
                      }}>
                        <SelectTrigger className="bg-gray-900/60 border-gray-800 text-white rounded-lg h-7 text-[10px] w-[110px] focus:border-violet-500 focus:ring-0">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-gray-900 border-gray-800 text-white">
                          <SelectItem value="openrouter">OpenRouter</SelectItem>
                          <SelectItem value="together">Together AI</SelectItem>
                          <SelectItem value="groq">Groq</SelectItem>
                          <SelectItem value="anthropic">Claude</SelectItem>
                          <SelectItem value="openai">OpenAI</SelectItem>
                          <SelectItem value="gemini">Gemini</SelectItem>
                          <SelectItem value="grok">Grok</SelectItem>
                        </SelectContent>
                      </Select>

                      <Select value={orchModel} onValueChange={(val) => val && setOrchModel(val)}>
                        <SelectTrigger className="bg-gray-900/60 border-gray-800 text-white rounded-lg h-7 text-[10px] w-[140px] focus:border-violet-500 focus:ring-0">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-gray-900 border-gray-800 text-white">
                          {orchProvider === 'openrouter' && (
                            <>
                              <SelectItem value="google/gemini-2.5-flash">Gemini 2.5 Flash</SelectItem>
                              <SelectItem value="google/gemini-2.5-pro">Gemini 2.5 Pro</SelectItem>
                              <SelectItem value="anthropic/claude-3.5-sonnet">Claude 3.5 Sonnet</SelectItem>
                              <SelectItem value="openai/gpt-4o">GPT-4o</SelectItem>
                              <SelectItem value="openai/gpt-4o-mini">GPT-4o-mini</SelectItem>
                              <SelectItem value="deepseek/deepseek-chat">DeepSeek Chat</SelectItem>
                              <SelectItem value="deepseek/deepseek-r1">DeepSeek R1</SelectItem>
                              <SelectItem value="meta-llama/llama-3.3-70b-instruct">Llama 3.3 70B</SelectItem>
                              <SelectItem value="qwen/qwen-2.5-72b-instruct">Qwen 2.5 72B</SelectItem>
                            </>
                          )}
                          {orchProvider === 'together' && (
                            <>
                              <SelectItem value="meta-llama/Llama-3.3-70B-Instruct-Turbo">Llama 3.3 70B Turbo</SelectItem>
                              <SelectItem value="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo">Llama 3.1 8B Turbo</SelectItem>
                              <SelectItem value="deepseek-ai/DeepSeek-V3">DeepSeek V3</SelectItem>
                              <SelectItem value="deepseek-ai/DeepSeek-R1">DeepSeek R1</SelectItem>
                              <SelectItem value="Qwen/Qwen2.5-72B-Instruct-Turbo">Qwen 2.5 72B Turbo</SelectItem>
                            </>
                          )}
                          {orchProvider === 'groq' && (
                            <>
                              <SelectItem value="llama-3.3-70b-versatile">Llama 3.3 70B</SelectItem>
                              <SelectItem value="llama-3.1-8b-instant">Llama 3.1 8B Instant</SelectItem>
                              <SelectItem value="mixtral-8x7b-32768">Mixtral 8x7B</SelectItem>
                            </>
                          )}
                          {orchProvider === 'anthropic' && (
                            <>
                              <SelectItem value="claude-sonnet-4-6">Sonnet 4.6</SelectItem>
                              <SelectItem value="claude-opus-4-8">Opus 4.8</SelectItem>
                              <SelectItem value="claude-haiku-4-5-20251001">Haiku 4.5</SelectItem>
                            </>
                          )}
                          {orchProvider === 'openai' && (
                            <>
                              <SelectItem value="gpt-4o">GPT-4o</SelectItem>
                              <SelectItem value="gpt-4o-mini">GPT-4o-mini</SelectItem>
                            </>
                          )}
                          {orchProvider === 'gemini' && (
                            <>
                              <SelectItem value="gemini-2.5-pro">2.5 Pro</SelectItem>
                              <SelectItem value="gemini-2.5-flash">2.5 Flash</SelectItem>
                              <SelectItem value="gemini-2.0-flash">2.0 Flash</SelectItem>
                            </>
                          )}
                          {orchProvider === 'grok' && (
                            <>
                              <SelectItem value="grok-2-latest">Grok 2 Latest</SelectItem>
                              <SelectItem value="grok-2-vision-latest">Grok 2 Vision</SelectItem>
                              <SelectItem value="grok-beta">Grok Beta</SelectItem>
                            </>
                          )}
                        </SelectContent>
                      </Select>

                      {/* Clear Chat */}
                      <button
                        onClick={clearOrchestratorChat}
                        className="h-7 w-7 rounded-lg bg-gray-900/60 border border-gray-800 text-gray-400 hover:text-rose-400 hover:border-rose-500/30 hover:bg-rose-950/20 flex items-center justify-center transition-all"
                        title="Clear chat history"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>

                  {/* MESSAGES AREA */}
                  <div className="flex-1 overflow-y-auto p-5 space-y-5 min-h-0">
                    {orchMessages.map((msg: any) => (
                      <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-2 duration-300`}>
                        {msg.role !== 'user' && (
                          <div className="h-8 w-8 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center mr-3 mt-1 flex-shrink-0 shadow-lg shadow-violet-500/20">
                            <Bot size={14} className="text-white" />
                          </div>
                        )}
                        <div className={`max-w-[80%] ${
                          msg.role === 'user'
                            ? 'bg-gradient-to-br from-violet-600 to-indigo-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 shadow-lg shadow-violet-500/15'
                            : 'bg-gray-900/60 border border-gray-800/60 text-gray-100 rounded-2xl rounded-tl-sm px-4 py-3'
                        }`}>
                          <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>

                          {/* Execution Blueprint */}
                          {msg.plan?.tasks && msg.plan.tasks.length > 0 && (
                            <div className="mt-3 pt-3 border-t border-gray-700/40 space-y-2">
                              <span className="text-[10px] uppercase font-black tracking-widest text-violet-400 flex items-center gap-1.5">
                                <Sparkles size={10} /> Execution Blueprint
                              </span>
                              {msg.plan.tasks.map((task: any, idx: number) => (
                                <div key={idx} className="flex items-center gap-2.5 bg-gray-950/50 rounded-xl px-3 py-2 border border-gray-800/40">
                                  <span className={`h-2 w-2 rounded-full flex-shrink-0 ${
                                    task.department === 'Marketing' ? 'bg-violet-500' :
                                    task.department === 'Sales' ? 'bg-emerald-500' :
                                    task.department === 'Support' ? 'bg-blue-500' :
                                    task.department === 'HR' ? 'bg-amber-500' :
                                    task.department === 'System' ? 'bg-rose-500' :
                                    'bg-gray-500'
                                  }`} />
                                  <span className="text-[11px] font-bold text-white">{task.department}</span>
                                  <span className="text-[10px] text-gray-400 font-medium">→ {task.action}</span>
                                  {task.parameters && Object.keys(task.parameters).length > 0 && (
                                    <span className="text-[9px] text-gray-500 ml-auto hidden sm:inline truncate max-w-[180px]">
                                      {JSON.stringify(task.parameters).slice(0, 60)}
                                    </span>
                                  )}
                                  <Check size={11} className="text-emerald-400 ml-auto flex-shrink-0" />
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Inline API Key Config for action_required responses */}
                          {msg.results?.some((r: any) => r.status === 'action_required') && (
                            <div className="mt-3 pt-3 border-t border-gray-700/40">
                              <div className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-3 space-y-2.5">
                                <span className="text-[10px] uppercase font-black tracking-widest text-amber-400 flex items-center gap-1">
                                  <Zap size={10} /> Quick Connect
                                </span>
                                <div className="flex gap-2">
                                  <Input
                                    type="text"
                                    placeholder="Paste your API key here..."
                                    value={orchInlineKeyValue}
                                    onChange={e => setOrchInlineKeyValue(e.target.value)}
                                    className="bg-gray-950/60 border-gray-800 text-white focus:border-amber-500 focus:ring-amber-500/20 rounded-lg h-8 text-xs flex-1"
                                  />
                                  <Button
                                    onClick={async () => {
                                      if (!orchInlineKeyValue) return;
                                      let detectedProvider = 'anthropic';
                                      if (orchInlineKeyValue.startsWith('sk-ant')) detectedProvider = 'anthropic';
                                      else if (orchInlineKeyValue.startsWith('sk-or-')) detectedProvider = 'openrouter';
                                      else if (orchInlineKeyValue.startsWith('sk-')) detectedProvider = 'openai';
                                      else if (orchInlineKeyValue.startsWith('AIza')) detectedProvider = 'gemini';
                                      else if (orchInlineKeyValue.startsWith('gsk_')) detectedProvider = 'groq';
                                      else if (orchInlineKeyValue.startsWith('xai-')) detectedProvider = 'grok';
                                      try {
                                        await fetchWithAuth(`${API_URL}/commands/keys`, {
                                          method: 'POST',
                                          headers: { 'Content-Type': 'application/json' },
                                          body: JSON.stringify({ provider: detectedProvider, key: orchInlineKeyValue })
                                        });
                                        setOrchInlineKeyValue('');
                                        fetchData();
                                        const successMsg = {
                                          id: `system-${Date.now()}`,
                                          role: 'assistant' as const,
                                          content: `✅ ${detectedProvider} API key saved successfully. I'm now fully operational — what would you like me to do?`,
                                          timestamp: new Date().toISOString()
                                        };
                                        setOrchMessages(prev => [...prev, successMsg]);
                                      } catch (err) {
                                        console.error(err);
                                      }
                                    }}
                                    className="h-8 px-3 bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold rounded-lg shadow-lg shadow-amber-500/20 transition-all hover:scale-[1.02] active:scale-95"
                                  >
                                    Save
                                  </Button>
                                </div>
                              </div>
                            </div>
                          )}

                          <span className={`text-[9px] mt-2 block text-right font-medium ${
                            msg.role === 'user' ? 'text-violet-200' : 'text-gray-500'
                          }`}>
                            {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>
                      </div>
                    ))}

                    {/* Typing Indicator */}
                    {loading && (
                      <div className="flex justify-start animate-in fade-in duration-300">
                        <div className="h-8 w-8 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center mr-3 mt-1 flex-shrink-0 shadow-lg shadow-violet-500/20">
                          <Bot size={14} className="text-white" />
                        </div>
                        <div className="bg-gray-900/60 border border-gray-800/60 rounded-2xl rounded-tl-sm px-5 py-4">
                          <div className="flex items-center gap-2">
                            <div className="flex gap-1">
                              <span className="h-2 w-2 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                              <span className="h-2 w-2 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                              <span className="h-2 w-2 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: '300ms' }} />
                            </div>
                            <span className="text-xs text-gray-400 font-medium ml-1">Orchestrating teams...</span>
                          </div>
                        </div>
                      </div>
                    )}

                    <div ref={orchChatEndRef} />
                  </div>

                  {/* QUICK PROMPT CHIPS */}
                  <div className="px-5 py-2.5 border-t border-gray-800/30 bg-gray-950/20 flex-shrink-0">
                    <div className="flex flex-wrap gap-2">
                      {apps.some((a: any) => a.app_name === 'Restaurant Growth Pack') && (
                        <button
                          onClick={() => setOrchInput("Trigger the daily special post for Restaurant Pack. Create a draft of today's specials for Instagram.")}
                          className="text-[11px] font-semibold px-3 py-1.5 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20 hover:bg-violet-500/20 hover:border-violet-500/40 transition-all hover:scale-[1.03] active:scale-95"
                        >
                          🍔 Post daily specials
                        </button>
                      )}
                      {apps.some((a: any) => a.app_name === 'SaaS Outreach System') && (
                        <button
                          onClick={() => setOrchInput("Execute the SaaS Outreach System. Source 5 CTOs at early-stage AI startups in New York.")}
                          className="text-[11px] font-semibold px-3 py-1.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 hover:border-emerald-500/40 transition-all hover:scale-[1.03] active:scale-95"
                        >
                          🚀 Source SaaS leads
                        </button>
                      )}
                      {apps.some((a: any) => a.app_name === 'Real Estate Lead Engine') && (
                        <button
                          onClick={() => setOrchInput("Generate property descriptions using the Real Estate Lead Engine for 456 Oak Ave. Premium luxury pool description.")}
                          className="text-[11px] font-semibold px-3 py-1.5 rounded-full bg-pink-500/10 text-pink-400 border border-pink-500/20 hover:bg-pink-500/20 hover:border-pink-500/40 transition-all hover:scale-[1.03] active:scale-95"
                        >
                          🏡 Generate listings
                        </button>
                      )}
                      {apps.some((a: any) => a.app_name === 'Creative Content Lab') && (
                        <button
                          onClick={() => setOrchInput("Create an SEO Blog Outline with the Creative Content Lab on 'How AI employees are transforming small businesses'.")}
                          className="text-[11px] font-semibold px-3 py-1.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 hover:bg-amber-500/20 hover:border-amber-500/40 transition-all hover:scale-[1.03] active:scale-95"
                        >
                          ✨ Write blog outline
                        </button>
                      )}
                      {apps.length === 0 && (
                        <>
                          <button
                            onClick={() => setOrchInput("Find 5 marketing agencies in San Francisco and email them a partnership proposal.")}
                            className="text-[11px] font-semibold px-3 py-1.5 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20 hover:bg-violet-500/20 hover:border-violet-500/40 transition-all hover:scale-[1.03] active:scale-95"
                          >
                            🔍 Find leads & email
                          </button>
                          <button
                            onClick={() => setOrchInput("Create a 7-day Instagram content campaign about healthy meal prep tips.")}
                            className="text-[11px] font-semibold px-3 py-1.5 rounded-full bg-pink-500/10 text-pink-400 border border-pink-500/20 hover:bg-pink-500/20 hover:border-pink-500/40 transition-all hover:scale-[1.03] active:scale-95"
                          >
                            📸 Create content campaign
                          </button>
                          <button
                            onClick={() => setOrchInput("Source 5 senior React developers with 4+ years experience, salary $130k/year.")}
                            className="text-[11px] font-semibold px-3 py-1.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 hover:bg-amber-500/20 hover:border-amber-500/40 transition-all hover:scale-[1.03] active:scale-95"
                          >
                            👨‍💻 Hire developers
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  {/* INPUT AREA */}
                  <div className="px-5 py-4 border-t border-gray-800/60 bg-gray-950/40 flex-shrink-0">
                    <div className="flex gap-3 items-end">
                      <div className="flex-1 relative">
                        <Textarea
                          placeholder="Tell me what your business needs..."
                          value={orchInput}
                          onChange={e => setOrchInput(e.target.value)}
                          onKeyDown={e => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                              e.preventDefault();
                              handleRunCommand();
                            }
                          }}
                          className="bg-gray-900/60 border-gray-800 text-white focus:border-violet-500 focus:ring-violet-500/20 rounded-xl text-sm min-h-[48px] max-h-[120px] resize-none pr-4 py-3"
                          rows={1}
                        />
                      </div>
                      <Button
                        onClick={handleRunCommand}
                        disabled={loading || !orchInput.trim()}
                        className="h-12 w-12 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white shadow-lg shadow-violet-500/20 hover:shadow-violet-500/30 transition-all hover:scale-105 active:scale-95 disabled:opacity-40 disabled:scale-100 flex items-center justify-center flex-shrink-0"
                      >
                        {loading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
                      </Button>
                    </div>
                  </div>
                </Card>
              </div>

              {/* RIGHT: Sidebar - 4 cols */}
              <div className="lg:col-span-4 flex flex-col gap-5 h-full min-h-0">
                {/* Activity Feed */}
                <Card className="flex-1 glass-panel border-[rgba(255,255,255,0.06)] rounded-3xl overflow-hidden shadow-2xl relative flex flex-col min-h-0">
                  <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-violet-500 to-transparent" />
                  <CardHeader className="pb-2 border-b border-gray-800/60 flex-shrink-0">
                    <CardTitle className="text-sm font-bold text-white flex items-center gap-2">
                      <Activity size={14} className="text-violet-400" />
                      Live Activity Feed
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-3 space-y-3 overflow-y-auto flex-1 min-h-0">
                    {timeline.length === 0 && <p className="text-xs text-gray-500 text-center mt-10">No recent activity.</p>}
                    {timeline.slice(0, 20).map((log: any) => (
                      <div key={log.id} className="flex gap-2.5 text-xs border-l-2 border-violet-500/30 pl-2.5 pb-2 relative">
                        <span className="absolute left-[-4px] top-1.5 h-2 w-2 rounded-full bg-violet-500 border border-gray-950 shadow-md" />
                        <div className="flex flex-col w-full">
                          <div className="flex justify-between w-full">
                            <span className="font-semibold text-white text-[11px]">{log.agent_name}</span>
                            <span className="text-[9px] text-gray-500">{new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                          </div>
                          <span className="text-violet-400 font-medium text-[10px] mt-0.5">{log.action}</span>
                          <span className="text-gray-400 text-[10px] mt-0.5 leading-relaxed" style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{log.description}</span>
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>

                {/* Quick Approvals */}
                <Card className="glass-panel border-[rgba(255,255,255,0.06)] rounded-3xl overflow-hidden shadow-2xl relative flex flex-col flex-shrink-0" style={{ maxHeight: '340px' }}>
                  <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-emerald-500 to-transparent" />
                  <CardHeader className="pb-2 border-b border-gray-800/60 flex-shrink-0">
                    <CardTitle className="text-sm font-bold text-white flex items-center justify-between">
                      <span className="flex items-center gap-2">
                        <Check size={14} className="text-emerald-400" />
                        Approvals
                      </span>
                      {((queue.posts?.length || 0) + (queue.leads?.length || 0)) > 0 && (
                        <span className="text-[10px] bg-violet-500/10 text-violet-400 border border-violet-500/20 px-2 py-0.5 rounded-full font-bold">
                          {(queue.posts?.length || 0) + (queue.leads?.length || 0)} pending
                        </span>
                      )}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-3 space-y-2 overflow-y-auto flex-1 min-h-0">
                    {(!queue.posts || queue.posts.length === 0) && (!queue.leads || queue.leads.length === 0) && (
                      <p className="text-xs text-gray-500 text-center py-6">No pending approvals.</p>
                    )}
                    {queue.posts?.slice(0, 5).map((post: any) => (
                      <div key={post.id} className="bg-gray-950/40 border border-gray-800/40 rounded-xl p-3 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-extrabold uppercase text-violet-400">{post.platform}</span>
                          <span className="text-[9px] text-gray-500 font-bold">Day {post.day}</span>
                        </div>
                        <p className="text-[11px] text-gray-300 leading-relaxed" style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{post.content}</p>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleRejectPost(post.id)}
                            className="h-6 text-[10px] font-semibold text-rose-400 border-rose-900/30 hover:bg-rose-950/20 flex-1 rounded-lg"
                          >
                            Reject
                          </Button>
                          <Button
                            size="sm"
                            onClick={() => handleApprovePost(post.id)}
                            className="h-6 text-[10px] font-semibold bg-emerald-600 hover:bg-emerald-500 text-white flex-1 rounded-lg"
                          >
                            Approve
                          </Button>
                        </div>
                      </div>
                    ))}
                    {queue.leads?.slice(0, 4).map((lead: any) => (
                      <div key={lead.id} className="bg-gray-950/40 border border-gray-800/40 rounded-xl p-3 flex items-center justify-between">
                        <div className="flex flex-col">
                          <span className="text-[11px] font-bold text-white">{lead.name}</span>
                          <span className="text-[10px] text-gray-400">{lead.company}</span>
                        </div>
                        <span className="text-[9px] font-bold bg-blue-500/10 text-blue-400 border border-blue-500/20 px-1.5 py-0.5 rounded uppercase">{lead.source}</span>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              </div>
            </div>
  );
}
