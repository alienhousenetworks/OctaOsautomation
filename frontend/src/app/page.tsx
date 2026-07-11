'use client';

import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import {
  Activity, Users, DollarSign, BarChart3, Briefcase, Zap, BookOpen,
  LogOut, Calendar, MessageSquare, Clock, TrendingUp, Target, FileText, Key, Video,
  Menu, X, ChevronRight, Settings2, UserCircle, Shield
} from 'lucide-react';

import KnowledgeView from '@/components/views/knowledge-view';
import DashboardView from '@/components/views/dashboard-view';
import CampaignsView from '@/components/views/campaigns-view';
import SupportView from '@/components/views/support-view';
import OrchestratorView from '@/components/views/orchestrator-view';
import TeamsView from '@/components/views/teams-view';
import MarketplaceView from '@/components/views/marketplace-view';
import InstructionsView from '@/components/views/instructions-view';
import HRView from '@/components/views/hr-view';
import CEOView from '@/components/views/ceo-view';
import CoordinationView from '@/components/views/coordination-view';
import SalesView from '@/components/views/sales-view';
import AIOptimizationView from '@/components/views/ai-optimization-view';
import MembersView from '@/components/views/members-view';
import SystemAdminView from '@/components/views/system-admin-view';
import ApiManagementView from '@/components/views/api-management-view';
import VideoStudioView from '@/components/views/video-studio-view';
import ProfileView from '@/components/views/profile-view';
import EnterpriseView from '@/components/views/enterprise-view';

import LandingPage from '@/components/landing-page';
import AuthForms from '@/components/auth-forms';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';

// ─── Nav Groups ──────────────────────────────────────────────────────────────
const NAV_GROUPS = [
  {
    label: 'Overview',
    items: [
      { id: 'dashboard', name: 'Operating Dashboard', icon: BarChart3, color: '#8b5cf6', section: 'dashboard' },
      { id: 'knowledge', name: 'Knowledge Base', icon: FileText, color: '#a78bfa', section: 'knowledge' },
    ],
  },
  {
    label: 'Growth',
    items: [
      { id: 'campaigns', name: 'Campaign Planner', icon: Calendar, color: '#6366f1', section: 'marketing' },
      { id: 'video_studio', name: 'Video Studio AI', icon: Video, color: '#f43f5e', section: 'marketing' },
      { id: 'sales', name: 'Sales CRM', icon: TrendingUp, color: '#10b981', section: 'sales' },
      { id: 'support', name: 'Customer Support', icon: MessageSquare, color: '#3b82f6', section: 'support' },
    ],
  },
  {
    label: 'AI Operations',
    items: [
      { id: 'coordination', name: 'Agent Boardroom', icon: Users, color: '#f59e0b', section: 'coordination' },
      { id: 'ceo', name: 'CEO Workspace', icon: Target, color: '#0ea5e9', section: 'ceo' },
      { id: 'orchestrator', name: 'Orchestrator AI', icon: Activity, color: '#a855f7', section: 'orchestrator' },
      { id: 'teams', name: 'AI Teams', icon: Users, color: '#22d3ee', section: 'teams' },
      { id: 'marketplace', name: 'App Marketplace', icon: Briefcase, color: '#ec4899', section: 'marketplace' },
    ],
  },
  {
    label: 'People & Finance',
    items: [
      { id: 'hr', name: 'Hiring & HR', icon: Briefcase, color: '#f59e0b', section: 'hr' },
      { id: 'ai_optimization', name: 'AI Cost Control', icon: DollarSign, color: '#34d399', section: 'ai_optimization' },
    ],
  },
  {
    label: 'System',
    items: [
      { id: 'api_management', name: 'API Management', icon: Key, color: '#8b5cf6', section: 'system' },
      { id: 'enterprise', name: 'Enterprise Control', icon: Shield, color: '#fbbf24', section: 'system' },
    ],
  },
  {
    label: 'Account',
    items: [
      { id: 'profile', name: 'My Profile', icon: UserCircle, color: '#c084fc', section: 'profile' },
    ],
  },
];

export default function Home() {
  const [appState, setAppState] = useState<'landing' | 'login' | 'signup' | 'app'>('landing');
  const [token, setToken] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [inviteToken, setInviteToken] = useState<string | null>(null);
  const [userProfile, setUserProfile] = useState<any>(null);
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [faviconUrl, setFaviconUrl] = useState<string | null>(null);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  const getFilteredNavGroups = () => {
    let groups = NAV_GROUPS.map(g => ({ ...g, items: [...g.items] }));

    if (userProfile && userProfile.role !== 'admin' && !userProfile.is_system_admin) {
      const allowed = userProfile.allowed_sections;
      if (allowed && !allowed.includes('all')) {
        groups = groups.map(g => ({
          ...g,
          items: g.items.filter(item => item.id === 'dashboard' || item.id === 'profile' || allowed.includes(item.section)),
        })).filter(g => g.items.length > 0);
      }
    }

    if (userProfile?.role === 'admin' || userProfile?.is_system_admin) {
      const systemGroup = groups.find(g => g.label === 'System');
      if (systemGroup) {
        systemGroup.items.push({
          id: 'members', name: 'Members & Access', icon: Users, color: '#fb7185', section: 'members'
        });
      }
    }

    if (userProfile?.is_system_admin) {
      const systemGroup = groups.find(g => g.label === 'System');
      if (systemGroup) {
        systemGroup.items.push({
          id: 'system_admin', name: 'System Admin', icon: Zap, color: '#fbbf24', section: 'system_admin'
        });
      }
    }

    return groups;
  };

  // Key configurations
  const [keyProvider, setKeyProvider] = useState('anthropic');
  const [keyValue, setKeyValue] = useState('');
  const [isKeyDialogOpen, setIsKeyDialogOpen] = useState(false);

  // App Dashboard States
  const [activeView, setActiveView] = useState('dashboard');
  const [queue, setQueue] = useState<{ posts: any[], leads: any[] }>({ posts: [], leads: [] });
  const [timeline, setTimeline] = useState<any[]>([]);
  const [knowledge, setKnowledge] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<any>({});
  const [teams, setTeams] = useState<any[]>([]);
  const [apps, setApps] = useState<any[]>([]);
  const [configuredProviders, setConfiguredProviders] = useState<string[]>([]);

  // Fetch branding settings on mount
  useEffect(() => {
    const fetchBranding = async () => {
      try {
        const res = await fetch(`${API_URL}/auth/settings`);
        if (res.ok) {
          const data = await res.json();
          if (data.logo_url) setLogoUrl(data.logo_url);
          if (data.favicon_url) setFaviconUrl(data.favicon_url);
        }
      } catch (e) {
        // Non-critical; ignore branding fetch errors
      }
    };
    fetchBranding();
  }, []);

  // Apply dynamic favicon whenever faviconUrl changes
  useEffect(() => {
    if (typeof document !== 'undefined' && faviconUrl) {
      try {
        const parsed = new URL(faviconUrl);
        if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') return;
      } catch {
        return;
      }
      let link: HTMLLinkElement | null = document.querySelector("link[rel~='icon']");
      if (!link) {
        link = document.createElement('link');
        link.rel = 'icon';
        document.head.appendChild(link);
      }
      link.href = faviconUrl;
    }
  }, [faviconUrl]);

  // Restore session from localStorage on mount & check for invite token
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const tokenParam = params.get('token');
      if (tokenParam) {
        setInviteToken(tokenParam);
        setAppState('signup');
      } else {
        const savedToken = localStorage.getItem('token');
        const savedTenantId = localStorage.getItem('tenant_id');
        if (savedToken) {
          setToken(savedToken);
          if (savedTenantId) setTenantId(savedTenantId);
          setAppState('app');
        }
      }
    }
  }, []);

  const fetchWithAuth = async (url: string, options: any = {}) => {
    const headers = {
      ...options.headers,
      'Authorization': `Bearer ${token}`
    };
    const res = await fetch(url, { ...options, headers });
    if (res.status === 401) handleLogout();
    return res;
  };

  const fetchData = async () => {
    if (!token) return;
    try {
      if (!userProfile) {
        const meRes = await fetchWithAuth(`${API_URL}/auth/me`);
        if (meRes.ok) {
          const meData = await meRes.json();
          setUserProfile(meData);
          if (meData.tenant_id) {
            localStorage.setItem('tenant_id', meData.tenant_id);
            setTenantId(meData.tenant_id);
          }
        }
      } else if (!tenantId) {
        const meRes = await fetchWithAuth(`${API_URL}/auth/me`);
        if (meRes.ok) {
          const meData = await meRes.json();
          if (meData.tenant_id) {
            localStorage.setItem('tenant_id', meData.tenant_id);
            setTenantId(meData.tenant_id);
          }
        }
      }

      const [qRes, tRes, kRes, mRes, tmRes, aRes, keyStatusRes] = await Promise.all([
        fetchWithAuth(`${API_URL}/commands/queue`),
        fetchWithAuth(`${API_URL}/commands/timeline`),
        fetchWithAuth(`${API_URL}/commands/knowledge`),
        fetchWithAuth(`${API_URL}/dashboard/metrics`),
        fetchWithAuth(`${API_URL}/dashboard/teams`),
        fetchWithAuth(`${API_URL}/dashboard/marketplace/installed`),
        fetchWithAuth(`${API_URL}/commands/keys`)
      ]);
      setQueue(await qRes.json());
      setTimeline(await tRes.json());
      setKnowledge(await kRes.json());
      setMetrics(await mRes.json());
      setTeams(await tmRes.json());
      setApps(await aRes.json());

      const keyStatusData = await keyStatusRes.json();
      setConfiguredProviders(keyStatusData.configured_providers || []);
    } catch (e) {
      console.error(e);
    }
  };

  // Poll global data periodically
  useEffect(() => {
    if (appState === 'app') {
      fetchData();
      const interval = setInterval(() => { fetchData(); }, 5000);
      return () => clearInterval(interval);
    }
  }, [appState, token]);

  // Close mobile sidebar on route change
  const handleNavClick = (viewId: string) => {
    setActiveView(viewId);
    setIsMobileSidebarOpen(false);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('tenant_id');
    setToken(null);
    setTenantId(null);
    setUserProfile(null);
    setInviteToken(null);
    setAppState('landing');
  };

  const saveApiKey = async () => {
    if (!keyValue) return;
    try {
      await fetchWithAuth(`${API_URL}/commands/keys`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: keyProvider, key: keyValue })
      });
      setKeyValue('');
      setIsKeyDialogOpen(false);
      alert(`${keyProvider} API key saved successfully!`);
      fetchData();
    } catch (e) {
      console.error(e);
    }
  };

  const uninstallApp = async (appName: string) => {
    try {
      const res = await fetchWithAuth(`${API_URL}/dashboard/marketplace/uninstall`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ app_name: appName })
      });
      if (res.ok) {
        fetchData();
        alert(`${appName} deactivated successfully.`);
      } else {
        alert(`Failed to deactivate ${appName}.`);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleApprovePost = async (postId: string) => {
    try {
      const res = await fetchWithAuth(`${API_URL}/marketing/posts/${postId}/approve`, { method: 'POST' });
      if (res.ok) {
        fetchData();
        alert('✅ Post approved and scheduled!\n\nTo publish immediately to Instagram/Facebook, click the "Publish Now" button on the post card. Make sure your Meta API key is configured in Settings → Integrations.');
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleRejectPost = async (postId: string) => {
    try {
      const res = await fetchWithAuth(`${API_URL}/marketing/posts/${postId}/reject`, { method: 'POST' });
      if (res.ok) fetchData();
    } catch (e) {
      console.error(e);
    }
  };

  // Get active view display name
  const getActiveViewName = () => {
    for (const group of NAV_GROUPS) {
      const item = group.items.find(i => i.id === activeView);
      if (item) return item.name;
    }
    if (activeView === 'instructions') return 'Setup & API Guide';
    if (activeView === 'profile') return 'My Profile';
    return 'Dashboard';
  };

  const getActiveViewColor = () => {
    for (const group of NAV_GROUPS) {
      const item = group.items.find(i => i.id === activeView);
      if (item) return item.color;
    }
    return '#8b5cf6';
  };

  const getActiveViewIcon = () => {
    for (const group of NAV_GROUPS) {
      const item = group.items.find(i => i.id === activeView);
      if (item) {
        const Icon = item.icon;
        return <Icon size={14} />;
      }
    }
    return <BarChart3 size={14} />;
  };

  // ─── Sidebar Component ────────────────────────────────────────────────────
  const SidebarContent = () => {
    const filteredGroups = getFilteredNavGroups();
    return (
      <div className="sidebar-root" style={{ height: '100%' }}>
        {/* Logo */}
        <div className="sidebar-logo">
          <div className="flex items-center gap-2.5">
            {logoUrl ? (
              <img src={logoUrl} alt="OctaOS Logo" className="h-8 w-auto max-w-[130px] object-contain" />
            ) : (
              <div className="flex items-center gap-2.5">
                <div
                  className="flex items-center justify-center w-8 h-8 rounded-xl"
                  style={{
                    background: 'linear-gradient(135deg, #7c3aed, #4f46e5)',
                    boxShadow: '0 4px 12px rgba(139,92,246,0.35)'
                  }}
                >
                  <Zap className="text-white fill-white" size={15} />
                </div>
                <span className="text-[17px] font-black text-white tracking-tight">
                  Octa<span style={{ color: '#a78bfa' }}>Os</span>
                </span>
              </div>
            )}
          </div>
          {/* System status */}
          <div className="mt-3">
            <span className="status-badge status-badge-online">All systems operational</span>
          </div>
        </div>

        {/* Scrollable nav */}
        <nav className="sidebar-nav-scroll">
          {filteredGroups.map((group) => (
            <div key={group.label} className="mb-1">
              <div className="nav-section-label">{group.label}</div>
              {group.items.map((item) => {
                const isActive = activeView === item.id;
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    onClick={() => handleNavClick(item.id)}
                    className={`nav-item ${isActive ? 'active' : ''}`}
                    id={`nav-${item.id}`}
                  >
                    <span
                      className="flex-shrink-0"
                      style={{ color: isActive ? item.color : undefined }}
                    >
                      <Icon size={16} />
                    </span>
                    <span className="truncate">{item.name}</span>
                    {isActive && (
                      <ChevronRight size={12} className="ml-auto flex-shrink-0 opacity-60" />
                    )}
                  </button>
                );
              })}
            </div>
          ))}
          {/* Extra padding at bottom of scroll area */}
          <div className="h-3" />
        </nav>

        {/* Footer (non-scrolling) */}
        <div className="sidebar-footer">
          <button
            onClick={() => handleNavClick('instructions')}
            className={`nav-item ${activeView === 'instructions' ? 'active' : ''}`}
            id="nav-instructions"
          >
            <BookOpen size={16} style={{ color: activeView === 'instructions' ? '#a78bfa' : undefined }} />
            <span className="truncate">Setup & API Guide</span>
          </button>
          <button
            onClick={handleLogout}
            className="nav-item nav-item-danger mt-1"
            id="nav-logout"
          >
            <LogOut size={16} />
            <span>Log out</span>
          </button>
        </div>
      </div>
    );
  };

  // ─── Render guards ────────────────────────────────────────────────────────
  if (appState === 'landing') {
    return <LandingPage setAppState={setAppState} logoUrl={logoUrl} />;
  }

  if (appState === 'login' || appState === 'signup') {
    return (
      <AuthForms
        appState={appState}
        setAppState={setAppState}
        API_URL={API_URL}
        setToken={setToken}
        setTenantId={setTenantId}
        inviteToken={inviteToken}
        setInviteToken={setInviteToken}
        logoUrl={logoUrl}
      />
    );
  }

  // ─── MAIN APP DASHBOARD ───────────────────────────────────────────────────
  return (
    <div className="flex h-screen bg-[#030014] text-[#f4f4f7] font-sans relative overflow-hidden">
      {/* Ambient background glows */}
      <div className="absolute top-[-10%] left-[-5%] w-[45%] h-[55%] rounded-full pointer-events-none"
        style={{ background: 'rgba(139,92,246,0.07)', filter: 'blur(120px)' }} />
      <div className="absolute bottom-[-10%] right-[-5%] w-[45%] h-[55%] rounded-full pointer-events-none"
        style={{ background: 'rgba(59,130,246,0.07)', filter: 'blur(120px)' }} />
      <div className="absolute top-[35%] left-[25%] w-[400px] h-[400px] rounded-full pointer-events-none"
        style={{ background: 'rgba(16,185,129,0.03)', filter: 'blur(150px)' }} />
      <div className="absolute inset-0 pointer-events-none"
        style={{ backgroundImage: 'linear-gradient(to right,rgba(255,255,255,0.012) 1px,transparent 1px),linear-gradient(to bottom,rgba(255,255,255,0.012) 1px,transparent 1px)', backgroundSize: '4rem 4rem' }} />

      {/* ── Desktop Sidebar ─────────────────────────────────────────────── */}
      <div className="sidebar-desktop h-full flex-shrink-0" style={{ width: 'var(--sidebar-width)' }}>
        <SidebarContent />
      </div>

      {/* ── Mobile Sidebar Overlay ──────────────────────────────────────── */}
      {isMobileSidebarOpen && (
        <div
          className="mobile-overlay open"
          onClick={() => setIsMobileSidebarOpen(false)}
          aria-label="Close sidebar overlay"
        />
      )}

      {/* ── Mobile Sidebar Drawer ───────────────────────────────────────── */}
      <div className={`sidebar-mobile-drawer ${isMobileSidebarOpen ? 'open' : ''}`}>
        <SidebarContent />
        <button
          className="mobile-close-btn"
          onClick={() => setIsMobileSidebarOpen(false)}
          aria-label="Close sidebar"
        >
          <X size={16} />
        </button>
      </div>

      {/* ── Main Content ────────────────────────────────────────────────── */}
      <div className="main-content-area flex-1 flex flex-col h-full overflow-hidden relative z-10" style={{ minWidth: 0 }}>

        {/* Header */}
        <header className="top-header">
          {/* Left: Hamburger (mobile) + Page title */}
          <div className="flex items-center gap-3">
            <button
              id="hamburger-btn"
              className="hamburger-btn"
              onClick={() => setIsMobileSidebarOpen(true)}
              aria-label="Open navigation menu"
            >
              <Menu size={18} />
            </button>

            {/* Current page indicator */}
            <div className="page-title-chip">
              <span style={{ color: getActiveViewColor() }}>{getActiveViewIcon()}</span>
              <span>{getActiveViewName()}</span>
            </div>
          </div>

          {/* Right: Actions */}
          <div className="flex items-center gap-2.5">
            {/* Knowledge Base shortcut — hidden on smallest screens */}
            <Button
              variant="secondary"
              onClick={() => handleNavClick('knowledge')}
              className="header-desktop-only bg-[rgba(255,255,255,0.04)] border border-gray-700/50 hover:bg-[rgba(139,92,246,0.1)] hover:border-violet-700/40 text-gray-300 hover:text-violet-300 text-xs h-9 px-3 rounded-xl transition-all duration-200"
              id="header-kb-btn"
            >
              <FileText size={13} className="mr-1.5" />
              Knowledge Base
            </Button>

            {/* API Settings */}
            <Dialog open={isKeyDialogOpen} onOpenChange={setIsKeyDialogOpen}>
              <DialogTrigger
                render={
                  <Button
                    variant="outline"
                    id="header-api-settings-btn"
                    className="bg-transparent border-gray-700/50 hover:bg-[rgba(139,92,246,0.1)] hover:border-violet-700/40 text-gray-300 hover:text-violet-300 text-xs h-9 px-3 rounded-xl transition-all duration-200"
                  />
                }
              >
                <Settings2 size={13} className="mr-1.5" />
                <span className="header-desktop-only">API Settings</span>
              </DialogTrigger>
              <DialogContent className="glass-panel border-violet-500/20 text-white rounded-3xl">
                <DialogHeader>
                  <DialogTitle className="text-white font-extrabold text-xl">Configure API Keys</DialogTitle>
                </DialogHeader>
                <div className="flex flex-col gap-4 py-4">
                  <p className="text-xs text-gray-400">
                    Select a provider and enter your API key. You can also paste keys directly into the Orchestrator chat!
                  </p>
                  <Select value={keyProvider} onValueChange={(val) => val && setKeyProvider(val)}>
                    <SelectTrigger className="bg-gray-900/60 border-gray-800 text-white">
                      <SelectValue placeholder="Select Provider" />
                    </SelectTrigger>
                    <SelectContent className="bg-gray-900 border-gray-800 text-white">
                      <SelectItem value="anthropic">Claude (Anthropic)</SelectItem>
                      <SelectItem value="openai">OpenAI</SelectItem>
                      <SelectItem value="gemini">Google Gemini</SelectItem>
                      <SelectItem value="grok">Grok</SelectItem>
                      <SelectItem value="meta">Meta Graph (Instagram/FB)</SelectItem>
                      <SelectItem value="linkedin">LinkedIn</SelectItem>
                      <SelectItem value="apollo">Apollo.io</SelectItem>
                      <SelectItem value="hunter">Hunter.io</SelectItem>
                      <SelectItem value="google_places">Google Places API</SelectItem>
                      <SelectItem value="gmail">Gmail API</SelectItem>
                      <SelectItem value="whatsapp">WhatsApp Business</SelectItem>
                      <SelectItem value="google_calendar">Google Calendar API</SelectItem>
                      <SelectItem value="smtp_marketing">SMTP (Marketing)</SelectItem>
                      <SelectItem value="smtp_hr">SMTP (HR)</SelectItem>
                      <SelectItem value="smtp_sales">SMTP (Sales)</SelectItem>
                    </SelectContent>
                  </Select>
                  <Input
                    type="password"
                    placeholder={keyProvider.startsWith('smtp') ? 'smtp://username:password@smtp.mailtrap.io:2525' : 'Enter API Key / Token'}
                    value={keyValue}
                    onChange={e => setKeyValue(e.target.value)}
                    className="bg-gray-900/60 border-gray-800 text-white focus:border-violet-500 focus:ring-violet-500/20"
                    id="api-key-input"
                  />
                  <Button
                    onClick={saveApiKey}
                    className="bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-semibold hover:from-violet-500 hover:to-indigo-500 transition-all"
                    id="save-api-key-btn"
                  >
                    Save Configuration
                  </Button>
                </div>
              </DialogContent>
            </Dialog>

            {/* User avatar chip */}
            {userProfile && (
              <button
                onClick={() => handleNavClick('profile')}
                className="header-desktop-only flex items-center gap-2 px-3 py-1.5 rounded-xl border text-xs font-semibold transition-all"
                style={{ background: 'rgba(139,92,246,0.08)', borderColor: activeView === 'profile' ? 'rgba(139,92,246,0.4)' : 'rgba(139,92,246,0.2)', color: '#c4b5fd' }}
                id="header-profile-btn"
                title="My Profile"
              >
                <div
                  className="w-5 h-5 rounded-full flex items-center justify-center text-white text-[10px] font-bold flex-shrink-0"
                  style={{ background: 'linear-gradient(135deg,#7c3aed,#4f46e5)' }}
                >
                  {(userProfile.name || userProfile.email)?.[0]?.toUpperCase() ?? 'U'}
                </div>
                <span className="max-w-[100px] truncate">{userProfile.name || userProfile.email}</span>
              </button>
            )}
          </div>
        </header>

        {/* Main scrollable view */}
        <main className="main-scroll-area flex-1 overflow-auto p-8 relative z-10">

          <div className={activeView === 'dashboard' ? 'block animate-fade-in-up' : 'hidden'}>
            <DashboardView
              metrics={metrics}
              timeline={timeline}
              queue={queue}
              apps={apps}
              setActiveView={setActiveView}
              uninstallApp={uninstallApp}
              handleApprovePost={handleApprovePost}
              handleRejectPost={handleRejectPost}
            />
          </div>

          <div className={activeView === 'knowledge' ? 'block animate-fade-in-up' : 'hidden'}>
            <KnowledgeView
              token={token}
              API_URL={API_URL}
              fetchWithAuth={fetchWithAuth}
              fetchData={fetchData}
              knowledge={knowledge}
            />
          </div>

          <div className={activeView === 'campaigns' ? 'block animate-fade-in-up' : 'hidden'}>
            <CampaignsView
              token={token}
              activeView={activeView}
              API_URL={API_URL}
              fetchWithAuth={fetchWithAuth}
              fetchData={fetchData}
              configuredProviders={configuredProviders}
            />
          </div>

          <div className={activeView === 'support' ? 'block animate-fade-in-up' : 'hidden'}>
            <SupportView
              token={token}
              API_URL={API_URL}
              fetchWithAuth={fetchWithAuth}
              fetchData={fetchData}
            />
          </div>

          <div className={activeView === 'orchestrator' ? 'block animate-fade-in-up' : 'hidden'}>
            <OrchestratorView
              token={token}
              API_URL={API_URL}
              fetchWithAuth={fetchWithAuth}
              fetchData={fetchData}
              apps={apps}
              configuredProviders={configuredProviders}
              timeline={timeline}
              queue={queue}
              handleApprovePost={handleApprovePost}
              handleRejectPost={handleRejectPost}
            />
          </div>

          <div className={activeView === 'teams' ? 'block animate-fade-in-up' : 'hidden'}>
            <TeamsView
              token={token}
              API_URL={API_URL}
              fetchWithAuth={fetchWithAuth}
              fetchData={fetchData}
              teams={teams}
              setTeams={setTeams}
            />
          </div>

          <div className={activeView === 'marketplace' ? 'block animate-fade-in-up' : 'hidden'}>
            <MarketplaceView
              token={token}
              API_URL={API_URL}
              fetchWithAuth={fetchWithAuth}
              fetchData={fetchData}
              apps={apps}
            />
          </div>

          <div className={activeView === 'instructions' ? 'block animate-fade-in-up' : 'hidden'}>
            <InstructionsView
              configuredProviders={configuredProviders}
              setIsKeyDialogOpen={setIsKeyDialogOpen}
              setKeyProvider={setKeyProvider}
              API_URL={API_URL}
              tenantId={tenantId}
            />
          </div>

          <div className={activeView === 'hr' ? 'block animate-fade-in-up' : 'hidden'}>
            <HRView
              token={token}
              API_URL={API_URL}
              fetchWithAuth={fetchWithAuth}
              fetchData={fetchData}
            />
          </div>

          <div className={activeView === 'ceo' ? 'block animate-fade-in-up' : 'hidden'}>
            <CEOView
              token={token}
              API_URL={API_URL}
              fetchWithAuth={fetchWithAuth}
              fetchData={fetchData}
              timeline={timeline}
              setActiveView={setActiveView}
            />
          </div>

          <div className={activeView === 'coordination' ? 'block animate-fade-in-up' : 'hidden'}>
            <CoordinationView
              token={token}
              API_URL={API_URL}
              fetchWithAuth={fetchWithAuth}
              fetchData={fetchData}
            />
          </div>

          <div className={activeView === 'sales' ? 'block animate-fade-in-up' : 'hidden'}>
            <SalesView
              token={token}
              API_URL={API_URL}
              fetchWithAuth={fetchWithAuth}
              fetchData={fetchData}
              timeline={timeline}
            />
          </div>

          <div className={activeView === 'profile' ? 'block animate-fade-in-up' : 'hidden'}>
            <ProfileView
              token={token}
              API_URL={API_URL}
              fetchWithAuth={fetchWithAuth}
              userProfile={userProfile}
              setUserProfile={setUserProfile}
              setToken={(t) => { setToken(t); localStorage.setItem('token', t); }}
              setTenantId={(id) => { setTenantId(id); localStorage.setItem('tenant_id', id); }}
              fetchData={fetchData}
            />
          </div>

          <div className={activeView === 'video_studio' ? 'block animate-fade-in-up' : 'hidden'}>
            <VideoStudioView
              token={token}
              API_URL={API_URL}
              fetchWithAuth={fetchWithAuth}
            />
          </div>

          <div className={activeView === 'ai_optimization' ? 'block animate-fade-in-up' : 'hidden'}>
            <AIOptimizationView
              token={token}
              API_URL={API_URL}
              fetchWithAuth={fetchWithAuth}
              fetchData={fetchData}
              metrics={metrics}
            />
          </div>

          <div className={activeView === 'enterprise' ? 'block animate-fade-in-up' : 'hidden'}>
            {token && <EnterpriseView token={token} />}
          </div>

          <div className={activeView === 'api_management' ? 'block animate-fade-in-up' : 'hidden'}>
            <ApiManagementView
              token={token}
              API_URL={API_URL}
              fetchWithAuth={fetchWithAuth}
              fetchData={fetchData}
              configuredProviders={configuredProviders}
              tenantId={tenantId}
            />
          </div>

          {(userProfile?.role === 'admin' || userProfile?.is_system_admin) && (
            <div className={activeView === 'members' ? 'block animate-fade-in-up' : 'hidden'}>
              <MembersView
                token={token}
                API_URL={API_URL}
                fetchWithAuth={fetchWithAuth}
                fetchData={fetchData}
              />
            </div>
          )}

          {userProfile?.is_system_admin && (
            <div className={activeView === 'system_admin' ? 'block animate-fade-in-up' : 'hidden'}>
              <SystemAdminView
                token={token}
                API_URL={API_URL}
                fetchWithAuth={fetchWithAuth}
                onBrandingUpdate={(newLogoUrl, newFaviconUrl) => {
                  if (newLogoUrl !== undefined) setLogoUrl(newLogoUrl);
                  if (newFaviconUrl !== undefined) setFaviconUrl(newFaviconUrl);
                }}
              />
            </div>
          )}

        </main>
      </div>
    </div>
  );
}
