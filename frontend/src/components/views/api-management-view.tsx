'use client';

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import {
  Key, Trash2, Plus, RefreshCw, CheckCircle2, XCircle,
  Eye, EyeOff, AlertTriangle, Zap, ChevronRight, Sparkles, Server, ShieldCheck,
} from 'lucide-react';

interface ApiManagementViewProps {
  token: string | null;
  API_URL: string;
  fetchWithAuth: (url: string, options?: any) => Promise<Response>;
  fetchData: () => Promise<void>;
  configuredProviders: string[];
  tenantId: string | null;
}

// ─── Provider catalogue ────────────────────────────────────────────────────────
const PROVIDER_GROUPS = [
  {
    group: '🧠 AI Brains',
    color: 'violet',
    description: 'Core LLM providers powering every AI agent',
    required: true,
    providers: [
      { id: 'openrouter', label: 'OpenRouter (Meta-Hub)', hint: 'sk-or-v1-...', url: 'https://openrouter.ai/keys', placeholder: 'sk-or-v1-...' },
      { id: 'together', label: 'Together AI (Meta-Hub)', hint: '64-hex / key', url: 'https://api.together.ai/settings/api-keys', placeholder: 'together_api_key...' },
      { id: 'groq', label: 'Groq (Ultra-Fast LPU)', hint: 'gsk_...', url: 'https://console.groq.com/keys', placeholder: 'gsk_...' },
      { id: 'anthropic', label: 'Claude (Anthropic)', hint: 'sk-ant-...', url: 'https://console.anthropic.com/', placeholder: 'sk-ant-api03-...' },
      { id: 'openai', label: 'OpenAI (GPT-4o)', hint: 'sk-proj-...', url: 'https://platform.openai.com/api-keys', placeholder: 'sk-proj-...' },
      { id: 'gemini', label: 'Google Gemini', hint: 'AIza...', url: 'https://aistudio.google.com/app/apikey', placeholder: 'AIzaSy...' },
      { id: 'grok', label: 'Grok (xAI)', hint: 'xai-...', url: 'https://console.x.ai/', placeholder: 'xai-...' },
    ],
  },
  {
    group: '📣 Social Media',
    color: 'blue',
    description: 'Publishing posts on Instagram, Facebook, LinkedIn',
    providers: [
      { id: 'meta', label: 'Meta Graph API (Instagram / FB)', hint: 'Page Access Token', url: 'https://developers.facebook.com/', placeholder: 'EAABsbCS...' },
      { id: 'linkedin', label: 'LinkedIn Share API', hint: 'OAuth Access Token', url: 'https://developer.linkedin.com/', placeholder: 'AQXTs...' },
    ],
  },
  {
    group: '💬 Messaging',
    color: 'emerald',
    description: 'Customer support and outreach via chat',
    providers: [
      { id: 'whatsapp', label: 'WhatsApp Business API', hint: 'Bearer Token | Phone ID', url: 'https://developers.facebook.com/', placeholder: 'EAABx... | 1234567890' },
      { id: 'telegram', label: 'Telegram Bot API', hint: '123456:ABCDEF...', url: 'https://t.me/BotFather', placeholder: '7123456789:AAFtq...' },
    ],
  },
  {
    group: '📧 Email & Calendar',
    color: 'orange',
    description: 'Sending emails, booking meetings',
    providers: [
      { id: 'gmail', label: 'Gmail API (OAuth)', hint: 'OAuth Token (use Connect button)', url: '', placeholder: 'ya29...' },
      { id: 'google_calendar', label: 'Google Calendar API', hint: 'OAuth Token', url: '', placeholder: 'ya29...' },
      { id: 'smtp_marketing', label: 'SMTP (Marketing)', hint: 'smtp://user:pass@host:port', url: '', placeholder: 'smtp://you@gmail.com:app_pass@smtp.gmail.com:587' },
      { id: 'smtp_hr', label: 'SMTP (HR)', hint: 'smtp://user:pass@host:port', url: '', placeholder: 'smtp://you@gmail.com:app_pass@smtp.gmail.com:587' },
      { id: 'smtp_sales', label: 'SMTP (Sales)', hint: 'smtp://user:pass@host:port', url: '', placeholder: 'smtp://you@gmail.com:app_pass@smtp.gmail.com:587' },
    ],
  },
  {
    group: '🎯 Lead Generation',
    color: 'indigo',
    description: 'B2B data enrichment & local business discovery',
    providers: [
      { id: 'apollo', label: 'Apollo.io', hint: 'API Key', url: 'https://app.apollo.io/#/settings/integrations/api', placeholder: 'API_KEY...' },
      { id: 'hunter', label: 'Hunter.io', hint: 'API Key', url: 'https://hunter.io/api-keys', placeholder: 'abc123...' },
      { id: 'google_places', label: 'Google Places API', hint: 'GCP API Key', url: 'https://console.cloud.google.com/', placeholder: 'AIzaSy...' },
      { id: 'apify', label: 'Apify', hint: 'API Token', url: 'https://console.apify.com/account/integrations', placeholder: 'apify_api_...' },
      { id: 'firecrawl', label: 'Firecrawl (Web Crawler)', hint: 'API Key', url: 'https://www.firecrawl.dev/app/api-keys', placeholder: 'fc-...' },
      { id: 'zoominfo', label: 'ZoomInfo', hint: 'API Key', url: 'https://www.zoominfo.com/', placeholder: 'API_KEY...' },
      { id: 'cognism', label: 'Cognism', hint: 'API Key', url: 'https://www.cognism.com/', placeholder: 'API_KEY...' },
      { id: 'people_data_labs', label: 'People Data Labs', hint: 'API Key', url: 'https://www.peopledatalabs.com/', placeholder: 'API_KEY...' },
      { id: 'clearbit', label: 'Clearbit', hint: 'API Key', url: 'https://clearbit.com/', placeholder: 'sk_...' },
      { id: 'crunchbase', label: 'Crunchbase', hint: 'API Key', url: 'https://data.crunchbase.com/', placeholder: 'API_KEY...' },
    ],
  },
];

const COLOR_MAP: Record<string, string> = {
  violet: 'from-violet-600/15 to-violet-600/5 border-violet-500/20',
  blue: 'from-blue-600/15 to-blue-600/5 border-blue-500/20',
  emerald: 'from-emerald-600/15 to-emerald-600/5 border-emerald-500/20',
  orange: 'from-orange-600/15 to-orange-600/5 border-orange-500/20',
  indigo: 'from-indigo-600/15 to-indigo-600/5 border-indigo-500/20',
};

const DOT_COLOR: Record<string, string> = {
  violet: 'bg-violet-400',
  blue: 'bg-blue-400',
  emerald: 'bg-emerald-400',
  orange: 'bg-orange-400',
  indigo: 'bg-indigo-400',
};

export default function ApiManagementView({
  token, API_URL, fetchWithAuth, fetchData, configuredProviders, tenantId,
}: ApiManagementViewProps) {
  const [configured, setConfigured] = useState<string[]>(configuredProviders);
  const [mainProvider, setMainProvider] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [aiMode, setAiMode] = useState<'inbuilt' | 'byok'>('inbuilt');
  const [inbuiltAvailable, setInbuiltAvailable] = useState<boolean>(true);
  const [defaultProvider, setDefaultProvider] = useState<string>('openrouter');
  const [modeLoading, setModeLoading] = useState(false);

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogProvider, setDialogProvider] = useState<{ id: string; label: string; placeholder: string } | null>(null);
  const [keyValue, setKeyValue] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [saving, setSaving] = useState(false);

  // Delete confirm state
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Toast
  const [toast, setToast] = useState<{ msg: string; type: 'ok' | 'err' } | null>(null);

  const showToast = (msg: string, type: 'ok' | 'err' = 'ok') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };

  const refresh = async () => {
    setRefreshing(true);
    try {
      const [keysRes, modeRes] = await Promise.allSettled([
        fetchWithAuth(`${API_URL}/commands/keys`),
        fetchWithAuth(`${API_URL}/commands/ai-mode`),
      ]);

      if (keysRes.status === 'fulfilled' && keysRes.value.ok) {
        const data = await keysRes.value.json();
        const providers = data.configured_providers || [];
        setConfigured(providers.map((p: any) => p.provider));
        const main = providers.find((p: any) => p.is_main);
        if (main) setMainProvider(main.provider);
      }

      if (modeRes.status === 'fulfilled' && modeRes.value.ok) {
        const modeData = await modeRes.value.json();
        if (modeData.mode) setAiMode(modeData.mode);
        if (modeData.inbuilt_available !== undefined) setInbuiltAvailable(modeData.inbuilt_available);
        if (modeData.default_provider) setDefaultProvider(modeData.default_provider);
      }
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const handleModeChange = async (newMode: 'inbuilt' | 'byok') => {
    if (newMode === aiMode || modeLoading) return;
    setModeLoading(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/commands/ai-mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: newMode }),
      });
      if (res.ok) {
        const data = await res.json();
        setAiMode(data.mode);
        showToast(
          data.mode === 'inbuilt'
            ? '✨ Switched to Inbuilt Platform AI mode (Server-managed failover).'
            : '🔐 Switched to BYOK mode (Bring Your Own Key).'
        );
        fetchData();
        refresh();
      } else {
        showToast('❌ Failed to update AI mode.', 'err');
      }
    } catch {
      showToast('❌ Network error updating AI mode.', 'err');
    } finally {
      setModeLoading(false);
    }
  };

  const openAddDialog = (p: { id: string; label: string; placeholder: string }) => {
    setDialogProvider(p);
    setKeyValue('');
    setShowKey(false);
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!dialogProvider || !keyValue.trim()) return;
    setSaving(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/commands/keys`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: dialogProvider.id, key: keyValue.trim() }),
      });
      if (res.ok) {
        setConfigured(prev => prev.includes(dialogProvider.id) ? prev : [...prev, dialogProvider.id]);
        setDialogOpen(false);
        fetchData();
        showToast(`✅ ${dialogProvider.label} key saved successfully!`);
      } else {
        const err = await res.json();
        showToast(`❌ ${err.detail || 'Invalid key format. Please check and retry.'}`, 'err');
      }
    } catch {
      showToast('❌ Network error saving key.', 'err');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (providerId: string) => {
    setDeleting(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/commands/keys/${providerId}`, { method: 'DELETE' });
      if (res.ok) {
        setConfigured(prev => prev.filter(p => p !== providerId));
        setDeleteConfirm(null);
        fetchData();
        showToast(`🗑️ Key removed successfully.`);
      } else {
        showToast('❌ Failed to remove key.', 'err');
      }
    } catch {
      showToast('❌ Network error removing key.', 'err');
    } finally {
      setDeleting(false);
    }
  };

  const handleSetMain = async (providerId: string) => {
    try {
      const res = await fetchWithAuth(`${API_URL}/commands/keys/${providerId}/set-main`, { method: 'POST' });
      if (res.ok) {
        setMainProvider(providerId);
        showToast(`⭐ ${providerId} set as main AI provider.`);
      } else {
        showToast('❌ Failed to set main provider.', 'err');
      }
    } catch {
      showToast('❌ Network error.', 'err');
    }
  };

  const totalConfigured = configured.length;
  const totalProviders = PROVIDER_GROUPS.reduce((acc, g) => acc + g.providers.length, 0);
  const hasPrimaryAI = (aiMode === 'inbuilt' && inbuiltAvailable) || configured.some(p => ['anthropic', 'openai', 'gemini', 'grok', 'openrouter', 'together', 'groq'].includes(p));

  return (
    <div className="max-w-6xl mx-auto space-y-8 pb-16 animate-in fade-in duration-300">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-6 right-6 z-50 px-5 py-3 rounded-2xl shadow-2xl text-sm font-semibold border transition-all animate-in slide-in-from-top-4 duration-300 ${toast.type === 'ok'
            ? 'bg-emerald-950/90 border-emerald-500/30 text-emerald-300'
            : 'bg-rose-950/90 border-rose-500/30 text-rose-300'
          }`}>
          {toast.msg}
        </div>
      )}

      {/* Page Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-4xl font-extrabold text-white tracking-tight flex items-center gap-3">
            <div className="p-2.5 rounded-2xl bg-gradient-to-br from-violet-600/30 to-indigo-600/20 border border-violet-500/20">
              <Key className="text-violet-400 h-8 w-8" />
            </div>
            API & Model Operations
          </h1>
          <p className="text-gray-400 mt-2 text-sm">
            Toggle between server-managed Inbuilt AI and BYOK (Bring Your Own Key), or configure custom integration tokens.
          </p>
        </div>
        <Button
          onClick={refresh}
          disabled={refreshing}
          className="bg-gray-900 hover:bg-gray-800 border border-gray-800 text-gray-300 rounded-xl h-10 px-4 flex items-center gap-2 text-xs font-bold"
        >
          <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
          Refresh Status
        </Button>
      </div>

      {/* AI Mode Selector Card */}
      <div className="glass-panel border-violet-500/30 rounded-3xl p-6 relative overflow-hidden bg-gradient-to-br from-violet-950/30 via-gray-900/50 to-indigo-950/20 shadow-2xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-5 border-b border-gray-800/80">
          <div>
            <div className="flex items-center gap-2.5">
              <Sparkles className="text-violet-400 h-5 w-5" />
              <h2 className="text-white font-extrabold text-lg">AI Execution Architecture</h2>
              <span className="text-[10px] font-bold uppercase tracking-wider bg-violet-500/15 text-violet-300 border border-violet-500/30 px-2.5 py-0.5 rounded-full">
                Mode: {aiMode.toUpperCase()}
              </span>
            </div>
            <p className="text-gray-400 text-xs mt-1">
              Choose whether agents consume platform-level redundant AI hubs (OpenRouter/Together) or your own BYOK credentials.
            </p>
          </div>
          <div className="flex items-center gap-2 bg-gray-950/70 border border-gray-800 p-1 rounded-2xl">
            <button
              onClick={() => handleModeChange('inbuilt')}
              disabled={modeLoading}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                aiMode === 'inbuilt'
                  ? 'bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-lg shadow-violet-500/25'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <Server size={13} />
              Inbuilt Platform AI
            </button>
            <button
              onClick={() => handleModeChange('byok')}
              disabled={modeLoading}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                aiMode === 'byok'
                  ? 'bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-lg shadow-indigo-500/25'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <ShieldCheck size={13} />
              BYOK (Your Keys)
            </button>
          </div>
        </div>

        {/* Dual Mode Description Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-5">
          {/* Inbuilt Mode Card */}
          <div
            onClick={() => handleModeChange('inbuilt')}
            className={`p-4 rounded-2xl border transition-all cursor-pointer ${
              aiMode === 'inbuilt'
                ? 'bg-violet-950/40 border-violet-500/50 shadow-inner'
                : 'bg-gray-950/40 border-gray-850 hover:border-gray-700'
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className={`p-2 rounded-xl ${aiMode === 'inbuilt' ? 'bg-violet-500/20 text-violet-300' : 'bg-gray-850 text-gray-400'}`}>
                  <Server size={16} />
                </div>
                <div>
                  <h3 className="text-white text-sm font-bold flex items-center gap-2">
                    Inbuilt Platform AI
                    {aiMode === 'inbuilt' && <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />}
                  </h3>
                  <span className="text-[10px] text-gray-400">Zero Setup • Server-Configured Multi-Vendor</span>
                </div>
              </div>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                inbuiltAvailable
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                  : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
              }`}>
                {inbuiltAvailable ? 'Online' : 'Unconfigured'}
              </span>
            </div>
            <p className="text-gray-400 text-xs mt-3 leading-relaxed">
              Leverages server environment keys for <strong className="text-gray-200">OpenRouter</strong>, <strong className="text-gray-200">Together AI</strong>, and <strong className="text-gray-200">Groq</strong> with automatic multi-vendor failover safety. No personal keys required to run agents.
            </p>
            <div className="mt-3 flex items-center gap-2 text-[11px] text-violet-300/80 font-mono">
              <Zap size={11} className="text-amber-400" />
              Default Hub: <span className="text-white font-bold">{defaultProvider.toUpperCase()}</span>
            </div>
          </div>

          {/* BYOK Mode Card */}
          <div
            onClick={() => handleModeChange('byok')}
            className={`p-4 rounded-2xl border transition-all cursor-pointer ${
              aiMode === 'byok'
                ? 'bg-indigo-950/40 border-indigo-500/50 shadow-inner'
                : 'bg-gray-950/40 border-gray-850 hover:border-gray-700'
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className={`p-2 rounded-xl ${aiMode === 'byok' ? 'bg-indigo-500/20 text-indigo-300' : 'bg-gray-850 text-gray-400'}`}>
                  <ShieldCheck size={16} />
                </div>
                <div>
                  <h3 className="text-white text-sm font-bold flex items-center gap-2">
                    BYOK (Bring Your Own Key)
                    {aiMode === 'byok' && <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />}
                  </h3>
                  <span className="text-[10px] text-gray-400">Strict Isolation • Custom Quotas</span>
                </div>
              </div>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full border bg-gray-800 text-gray-400 border-gray-700">
                {configured.length} Keys Configured
              </span>
            </div>
            <p className="text-gray-400 text-xs mt-3 leading-relaxed">
              Agents use your own encrypted workspace credentials. Complete isolation with direct billing from Anthropic, OpenAI, OpenRouter, or Together AI.
            </p>
            <div className="mt-3 flex items-center gap-2 text-[11px] text-indigo-300/80 font-mono">
              <Key size={11} className="text-indigo-400" />
              Keys Stored: <span className="text-white font-bold">{configured.length > 0 ? configured.join(', ') : 'None yet'}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="glass-panel border-transparent rounded-2xl p-5 relative overflow-hidden">
          <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-violet-500 to-transparent" />
          <div className="text-3xl font-black text-white">{totalConfigured}</div>
          <div className="text-xs text-gray-400 mt-1 font-medium">of {totalProviders} providers configured in BYOK</div>
          <div className="mt-3 w-full bg-gray-800 rounded-full h-1.5">
            <div
              className="bg-gradient-to-r from-violet-500 to-indigo-500 h-1.5 rounded-full transition-all duration-700"
              style={{ width: `${Math.round((totalConfigured / totalProviders) * 100)}%` }}
            />
          </div>
        </div>

        <div className={`glass-panel border rounded-2xl p-5 relative overflow-hidden ${hasPrimaryAI ? 'border-emerald-500/20' : 'border-rose-500/30'
          }`}>
          <div className={`flex items-center gap-2 text-sm font-bold ${hasPrimaryAI ? 'text-emerald-400' : 'text-rose-400 animate-pulse'}`}>
            {hasPrimaryAI ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
            {hasPrimaryAI ? (aiMode === 'inbuilt' ? 'AI Brain: Ready (Inbuilt)' : 'AI Brain: Active (BYOK)') : 'AI Brain: Missing!'}
          </div>
          <p className="text-xs text-gray-400 mt-2 leading-relaxed">
            {hasPrimaryAI
              ? (aiMode === 'inbuilt'
                ? `Platform AI is operational with server multi-vendor routing (${defaultProvider}). Agents are ready.`
                : 'Custom LLM credentials verified — agents are operational.')
              : 'No operational AI found. Configure a BYOK key below or ensure server environment keys are set.'}
          </p>
        </div>

        <div className="glass-panel border-transparent rounded-2xl p-5">
          <div className="flex items-center gap-2 text-sm font-bold text-gray-300 mb-2">
            <Zap size={15} className="text-amber-400" />
            Quick Actions
          </div>
          <div className="space-y-2">
            <button
              onClick={() => {
                const p = PROVIDER_GROUPS[0].providers[0];
                openAddDialog(p);
              }}
              className="w-full text-left text-xs text-violet-400 hover:text-violet-300 flex items-center gap-1.5 transition-colors"
            >
              <ChevronRight size={12} /> Add Claude (Anthropic)
            </button>
            <button
              onClick={() => {
                const p = PROVIDER_GROUPS[0].providers[2];
                openAddDialog(p);
              }}
              className="w-full text-left text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1.5 transition-colors"
            >
              <ChevronRight size={12} /> Add Google Gemini
            </button>
          </div>
        </div>
      </div>

      {/* Provider Groups */}
      <div className="space-y-6">
        {PROVIDER_GROUPS.map((group) => {
          const groupConfiguredCount = group.providers.filter(p => configured.includes(p.id)).length;
          return (
            <div key={group.group} className={`rounded-3xl border bg-gradient-to-br p-6 shadow-xl ${COLOR_MAP[group.color]}`}>
              {/* Group Header */}
              <div className="flex items-center justify-between mb-5">
                <div>
                  <h2 className="text-white font-extrabold text-lg flex items-center gap-2">
                    {group.group}
                    {group.required && (
                      <span className="text-[10px] font-bold bg-rose-500/15 text-rose-400 border border-rose-500/20 px-2 py-0.5 rounded-full">
                        REQUIRED
                      </span>
                    )}
                  </h2>
                  <p className="text-gray-400 text-xs mt-0.5">{group.description}</p>
                </div>
                <span className="text-xs font-bold text-gray-300 bg-gray-900/60 border border-gray-700/50 px-3 py-1 rounded-full">
                  {groupConfiguredCount}/{group.providers.length} active
                </span>
              </div>

              {/* Provider Cards Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {group.providers.map((provider) => {
                  const isConfigured = configured.includes(provider.id);
                  const isConfirmingDelete = deleteConfirm === provider.id;
                  return (
                    <div
                      key={provider.id}
                      className={`rounded-2xl border p-4 flex items-center justify-between gap-4 transition-all duration-200 ${isConfigured
                          ? 'bg-gray-900/70 border-gray-700/40 hover:border-gray-600/60'
                          : 'bg-gray-950/40 border-gray-800/50 hover:border-gray-700/50'
                        }`}
                    >
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        {/* Status dot */}
                        <div className="flex-shrink-0 relative">
                          <div className={`w-8 h-8 rounded-xl flex items-center justify-center ${isConfigured ? 'bg-emerald-500/15 border border-emerald-500/30' : 'bg-gray-800/60 border border-gray-700/40'
                            }`}>
                            <Key size={13} className={isConfigured ? 'text-emerald-400' : 'text-gray-500'} />
                          </div>
                          <span className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-gray-900 ${isConfigured ? 'bg-emerald-400' : 'bg-gray-600'
                            }`} />
                        </div>

                        <div className="min-w-0">
                          <div className="text-white font-bold text-sm truncate flex items-center gap-2">
                            {provider.label}
                            {isConfigured && mainProvider === provider.id && (
                              <span className="text-[10px] bg-amber-500/20 text-amber-400 border border-amber-500/30 px-1.5 py-0.5 rounded-md flex items-center gap-1">
                                ⭐ Main AI
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-1.5 mt-0.5">
                            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full border ${isConfigured
                                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                                : 'bg-gray-800 text-gray-500 border-gray-700/50'
                              }`}>
                              {isConfigured ? '● Connected' : '○ Not set'}
                            </span>
                            {provider.hint && (
                              <span className="text-[10px] text-gray-500 font-mono truncate">{provider.hint}</span>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex-shrink-0 flex items-center gap-2">
                        {isConfirmingDelete ? (
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-rose-400 font-semibold">Remove?</span>
                            <button
                              onClick={() => handleDelete(provider.id)}
                              disabled={deleting}
                              className="text-[11px] font-bold text-white bg-rose-600 hover:bg-rose-500 px-2.5 py-1 rounded-lg transition-colors disabled:opacity-50"
                            >
                              {deleting ? '...' : 'Yes'}
                            </button>
                            <button
                              onClick={() => setDeleteConfirm(null)}
                              className="text-[11px] font-bold text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700 px-2.5 py-1 rounded-lg transition-colors"
                            >
                              No
                            </button>
                          </div>
                        ) : (
                          <>
                            <button
                              onClick={() => openAddDialog(provider)}
                              className={`flex items-center gap-1.5 text-[11px] font-bold px-3 py-1.5 rounded-lg border transition-all ${isConfigured
                                  ? 'bg-gray-800 hover:bg-gray-700 text-gray-300 border-gray-700/50'
                                  : 'bg-violet-600 hover:bg-violet-500 text-white border-transparent shadow-lg shadow-violet-500/20'
                                }`}
                            >
                              <Plus size={11} />
                              {isConfigured ? 'Replace' : 'Add Key'}
                            </button>
                            {isConfigured && ['anthropic', 'openai', 'gemini', 'grok', 'openrouter', 'together', 'groq'].includes(provider.id) && mainProvider !== provider.id && (
                              <button
                                onClick={() => handleSetMain(provider.id)}
                                className="text-[11px] font-bold px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-amber-500/20 hover:text-amber-400 border border-gray-700/50 text-gray-400 transition-all"
                              >
                                Set as Main
                              </button>
                            )}
                            {isConfigured && (
                              <button
                                onClick={() => setDeleteConfirm(provider.id)}
                                className="w-7 h-7 flex items-center justify-center rounded-lg bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 text-rose-400 hover:text-rose-300 transition-all"
                                title="Remove key"
                              >
                                <Trash2 size={12} />
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Add/Replace Key Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="glass-panel border-violet-500/20 text-white rounded-3xl max-w-md">
          <DialogHeader>
            <DialogTitle className="text-white font-extrabold text-xl flex items-center gap-2">
              <Key size={18} className="text-violet-400" />
              {dialogProvider ? `${configured.includes(dialogProvider.id) ? 'Replace' : 'Add'} ${dialogProvider.label}` : ''}
            </DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-5 py-2">
            {configured.includes(dialogProvider?.id || '') && (
              <div className="flex items-center gap-2 text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-xl px-4 py-3">
                <AlertTriangle size={13} />
                You already have a key configured. Saving will replace it immediately.
              </div>
            )}

            <div className="space-y-2">
              <label className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">
                API Key / Token
              </label>
              <div className="relative">
                <Input
                  type={showKey ? 'text' : 'password'}
                  placeholder={dialogProvider?.placeholder || 'Paste your key here...'}
                  value={keyValue}
                  onChange={e => setKeyValue(e.target.value)}
                  className="bg-gray-900/80 border-gray-700 text-white pr-10 rounded-xl h-11 focus:border-violet-500 focus:ring-violet-500/20 font-mono text-sm"
                  onKeyDown={e => e.key === 'Enter' && handleSave()}
                />
                <button
                  type="button"
                  onClick={() => setShowKey(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors"
                >
                  {showKey ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
              {dialogProvider?.id.startsWith('smtp') && (
                <p className="text-[11px] text-gray-500 font-mono leading-relaxed">
                  Format: <span className="text-gray-400">smtp://email@host.com:password@smtp.host.com:587</span>
                </p>
              )}
            </div>

            <div className="flex gap-3 pt-1">
              <Button
                onClick={() => setDialogOpen(false)}
                className="flex-1 bg-gray-900 hover:bg-gray-800 border border-gray-800 text-gray-300 rounded-xl h-11"
              >
                Cancel
              </Button>
              <Button
                onClick={handleSave}
                disabled={saving || !keyValue.trim()}
                className="flex-1 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-bold rounded-xl h-11 shadow-lg shadow-violet-500/25 disabled:opacity-50"
              >
                {saving ? (
                  <span className="flex items-center gap-2">
                    <RefreshCw size={14} className="animate-spin" /> Saving...
                  </span>
                ) : 'Save Key'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Footer note */}
      <div className="flex items-start gap-3 bg-gray-900/40 border border-gray-800/60 rounded-2xl p-5 text-xs text-gray-400 leading-relaxed">
        <span className="text-xl flex-shrink-0">🔒</span>
        <div>
          <strong className="text-white block mb-1">Your keys are secure</strong>
          All API keys are encrypted with AES-256 before being stored. Keys are tenant-isolated — only your workspace can use them. You can revoke any key at any time by clicking the <strong className="text-rose-400">delete</strong> button.
        </div>
      </div>
    </div>
  );
}
