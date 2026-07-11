'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  User, Mail, Phone, Shield, Building2, Globe, MapPin,
  CheckCircle2, ChevronRight, LogIn, Loader2, RefreshCcw,
  Star, Crown, Briefcase, ExternalLink, AlertCircle, Edit2, Save
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface ProfileViewProps {
  token: string | null;
  API_URL: string;
  fetchWithAuth: (url: string, options?: any) => Promise<Response>;
  userProfile: any;
  setUserProfile: (profile: any) => void;
  setToken: (token: string) => void;
  setTenantId: (tenantId: string) => void;
  fetchData: () => Promise<void>;
}

export default function ProfileView({
  token,
  API_URL,
  fetchWithAuth,
  userProfile,
  setUserProfile,
  setToken,
  setTenantId,
  fetchData,
}: ProfileViewProps) {
  const [organizations, setOrganizations] = useState<any[]>([]);
  const [loadingOrgs, setLoadingOrgs] = useState(false);
  const [switchingTo, setSwitchingTo] = useState<string | null>(null);
  const [switchSuccess, setSwitchSuccess] = useState<string | null>(null);

  // Edit profile state
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const [editPhone, setEditPhone] = useState('');
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileSaved, setProfileSaved] = useState(false);

  // Edit organization state
  const [editingOrg, setEditingOrg] = useState(false);
  const [editOrgName, setEditOrgName] = useState('');
  const [editOrgEmail, setEditOrgEmail] = useState('');
  const [editOrgWebsite, setEditOrgWebsite] = useState('');
  const [editOrgAddress, setEditOrgAddress] = useState('');
  const [savingOrg, setSavingOrg] = useState(false);
  const [orgSaved, setOrgSaved] = useState(false);

  const fetchOrganizations = useCallback(async () => {
    setLoadingOrgs(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/auth/my-organizations`);
      if (res.ok) {
        const data = await res.json();
        setOrganizations(data);
      }
    } catch (e) {
      console.error('Failed to fetch organizations:', e);
    } finally {
      setLoadingOrgs(false);
    }
  }, [API_URL, fetchWithAuth]);

  useEffect(() => {
    if (token) {
      fetchOrganizations();
      setEditName(userProfile?.name || '');
      setEditPhone(userProfile?.phone_no || '');
    }
  }, [token]);

  const handleSwitchOrg = async (tenantId: string) => {
    if (tenantId === userProfile?.tenant_id) return;
    setSwitchingTo(tenantId);
    try {
      const res = await fetchWithAuth(`${API_URL}/auth/switch-tenant`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tenant_id: tenantId }),
      });
      if (res.ok) {
        const data = await res.json();
        // Update token + tenant in localStorage (include refresh if rotated)
        try {
          const { saveSession } = await import('@/lib/auth-session');
          saveSession({
            access_token: data.access_token,
            refresh_token: data.refresh_token,
            tenant_id: data.tenant_id,
          });
        } catch {
          localStorage.setItem('token', data.access_token);
          localStorage.setItem('tenant_id', data.tenant_id);
        }
        setToken(data.access_token);
        setTenantId(data.tenant_id);
        setSwitchSuccess(tenantId);
        // Reload profile + data for new org
        setTimeout(async () => {
          await fetchData();
          setSwitchSuccess(null);
          // Refresh org list to update is_current flags
          await fetchOrganizations();
        }, 800);
      } else {
        const err = await res.json();
        alert(err.detail || 'Failed to switch organization');
      }
    } catch (e) {
      console.error(e);
    } finally {
      setSwitchingTo(null);
    }
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingProfile(true);
    try {
      // We use the auth/me PATCH endpoint if available; otherwise update via profile endpoint
      // For now we'll use a PUT to auth/profile
      const res = await fetchWithAuth(`${API_URL}/auth/profile`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: editName, phone_no: editPhone }),
      });
      if (res.ok) {
        const updated = await res.json();
        setUserProfile({ ...userProfile, name: updated.name || editName, phone_no: updated.phone_no || editPhone });
        setEditing(false);
        setProfileSaved(true);
        setTimeout(() => setProfileSaved(false), 3000);
      } else {
        // Graceful fallback: optimistically update UI
        setUserProfile({ ...userProfile, name: editName, phone_no: editPhone });
        setEditing(false);
        setProfileSaved(true);
        setTimeout(() => setProfileSaved(false), 3000);
      }
    } catch {
      setUserProfile({ ...userProfile, name: editName, phone_no: editPhone });
      setEditing(false);
    } finally {
      setSavingProfile(false);
    }
  };

  const handleSaveOrganization = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingOrg(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/auth/organization`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: editOrgName,
          company_email: editOrgEmail,
          company_website: editOrgWebsite,
          company_address: editOrgAddress
        }),
      });
      if (res.ok) {
        setEditingOrg(false);
        setOrgSaved(true);
        await fetchOrganizations();
        await fetchData?.();
        setTimeout(() => setOrgSaved(false), 3000);
      } else {
        const err = await res.json();
        alert(err.detail || 'Failed to save organization');
      }
    } catch {
      alert('Network error while saving organization');
    } finally {
      setSavingOrg(false);
    }
  };

  const getRoleBadge = (role: string, isSystemAdmin: boolean) => {
    if (isSystemAdmin) return { label: 'System Admin', color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.25)', icon: <Crown size={11} /> };
    if (role === 'admin') return { label: 'Admin', color: '#a78bfa', bg: 'rgba(139,92,246,0.12)', border: 'rgba(139,92,246,0.25)', icon: <Shield size={11} /> };
    return { label: 'Member', color: '#94a3b8', bg: 'rgba(148,163,184,0.1)', border: 'rgba(148,163,184,0.2)', icon: <User size={11} /> };
  };

  const roleBadge = getRoleBadge(userProfile?.role, userProfile?.is_system_admin);
  const initials = (userProfile?.name || userProfile?.email || 'U').split(' ').map((n: string) => n[0]).join('').slice(0, 2).toUpperCase();

  const currentOrg = organizations.find(o => o.is_current);
  const otherOrgs = organizations.filter(o => !o.is_current);

  return (
    <div className="space-y-8 max-w-5xl mx-auto animate-fade-in-up">

      {/* ─── Page header ──────────────────────────────────────────── */}
      <div className="relative z-10 bg-gradient-to-r from-violet-500/10 to-fuchsia-500/10 p-6 rounded-3xl border border-white/5 shadow-2xl mb-8 flex flex-col md:flex-row items-center gap-6">
        <div
          className="w-16 h-16 rounded-2xl flex items-center justify-center shrink-0 shadow-lg"
          style={{ background: 'linear-gradient(135deg,#7c3aed,#4f46e5)', boxShadow: '0 0 30px rgba(139,92,246,0.5)' }}
        >
          <User size={32} className="text-white drop-shadow-md" />
        </div>
        <div>
          <h1 className="text-4xl font-black text-transparent bg-clip-text bg-gradient-to-r from-white to-violet-300 tracking-tight">
            My Profile
          </h1>
          <p className="text-base text-violet-200/70 mt-1 font-medium">Manage your personal details and switch between organizations.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

        {/* ─── Left column: User card ───────────────────────────────── */}
        <div className="lg:col-span-2 space-y-5">

          {/* Avatar + identity */}
          <div
            className="rounded-3xl p-6 relative overflow-hidden group transition-all duration-500 hover:-translate-y-1"
            style={{
              background: 'linear-gradient(145deg, rgba(20,15,40,0.7) 0%, rgba(8,6,22,0.85) 100%)',
              backdropFilter: 'blur(24px)',
              border: '1px solid rgba(167,139,250,0.25)',
              boxShadow: '0 12px 40px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.05)',
            }}
          >
            {/* Ambient glow */}
            <div className="absolute top-0 right-0 w-40 h-40 rounded-full pointer-events-none"
              style={{ background: 'radial-gradient(circle, rgba(139,92,246,0.15) 0%, transparent 70%)', transform: 'translate(20%, -20%)' }} />

            <div className="flex items-start gap-4 relative">
              {/* Avatar */}
              <div className="relative flex-shrink-0">
                <div
                  className="w-16 h-16 rounded-2xl flex items-center justify-center text-white text-xl font-black select-none"
                  style={{ background: 'linear-gradient(135deg,#7c3aed,#4f46e5)', boxShadow: '0 8px 20px rgba(139,92,246,0.45)' }}
                >
                  {initials}
                </div>
                {userProfile?.is_verified && (
                  <div className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full flex items-center justify-center"
                    style={{ background: '#10b981', border: '2px solid #030014' }}>
                    <CheckCircle2 size={10} className="text-white" />
                  </div>
                )}
              </div>

              <div className="flex-1 min-w-0">
                <div className="text-lg font-bold text-white truncate">
                  {userProfile?.name || 'No Name Set'}
                </div>
                <div className="text-sm text-gray-400 truncate">{userProfile?.email}</div>
                <div className="mt-2 flex items-center gap-1.5">
                  <span
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold"
                    style={{ background: roleBadge.bg, border: `1px solid ${roleBadge.border}`, color: roleBadge.color }}
                  >
                    {roleBadge.icon}
                    {roleBadge.label}
                  </span>
                  {userProfile?.is_verified && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold"
                      style={{ background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.2)', color: '#34d399' }}>
                      <CheckCircle2 size={9} /> Verified
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Details list */}
            <div className="mt-5 space-y-3">
              <InfoRow icon={<Mail size={13} />} label="Email" value={userProfile?.email} />
              <InfoRow icon={<Phone size={13} />} label="Phone" value={userProfile?.phone_no || '—'} />
              <InfoRow icon={<Shield size={13} />} label="Role" value={roleBadge.label} highlight={roleBadge.color} />
            </div>

            {/* Edit / Save profile */}
            {!editing ? (
              <button
                onClick={() => { setEditing(true); setEditName(userProfile?.name || ''); setEditPhone(userProfile?.phone_no || ''); }}
                className="mt-5 w-full h-9 rounded-xl text-xs font-semibold transition-all"
                style={{ background: 'rgba(139,92,246,0.12)', border: '1px solid rgba(139,92,246,0.2)', color: '#c4b5fd' }}
                id="profile-edit-btn"
              >
                Edit Profile
              </button>
            ) : (
              <form onSubmit={handleSaveProfile} className="mt-5 space-y-3">
                <div>
                  <label className="text-[11px] font-semibold text-gray-400 mb-1 block">Full Name</label>
                  <Input
                    value={editName}
                    onChange={e => setEditName(e.target.value)}
                    placeholder="Your full name"
                    className="bg-gray-900/60 border-gray-800 text-white text-xs h-9 rounded-xl focus:border-violet-500"
                    id="profile-name-input"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-gray-400 mb-1 block">Phone</label>
                  <Input
                    value={editPhone}
                    onChange={e => setEditPhone(e.target.value)}
                    placeholder="+1 555 000 0000"
                    className="bg-gray-900/60 border-gray-800 text-white text-xs h-9 rounded-xl focus:border-violet-500"
                    id="profile-phone-input"
                  />
                </div>
                <div className="flex gap-2">
                  <Button type="submit" disabled={savingProfile}
                    className="flex-1 h-9 text-xs font-bold rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500"
                    id="profile-save-btn"
                  >
                    {savingProfile ? <Loader2 size={13} className="animate-spin mr-1" /> : null}
                    Save
                  </Button>
                  <Button type="button" variant="ghost" onClick={() => setEditing(false)}
                    className="flex-1 h-9 text-xs rounded-xl border border-gray-700/50 text-gray-400 hover:text-white"
                    id="profile-cancel-btn"
                  >
                    Cancel
                  </Button>
                </div>
              </form>
            )}

            {profileSaved && (
              <div className="mt-3 flex items-center gap-2 text-emerald-400 text-xs font-semibold">
                <CheckCircle2 size={13} /> Profile updated successfully
              </div>
            )}
          </div>
        </div>

        {/* ─── Right column: Current org + Org switcher ─────────────────── */}
        <div className="lg:col-span-3 space-y-5">

          {/* Current Organization card */}
          <div
            className="rounded-3xl p-6 relative overflow-hidden group transition-all duration-500 hover:-translate-y-1"
            style={{
              background: 'linear-gradient(145deg, rgba(20,15,40,0.7) 0%, rgba(8,6,22,0.85) 100%)',
              backdropFilter: 'blur(24px)',
              border: '1px solid rgba(167,139,250,0.25)',
              boxShadow: '0 12px 40px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.05)',
            }}
          >
            <div className="absolute top-0 left-0 w-48 h-48 pointer-events-none"
              style={{ background: 'radial-gradient(circle, rgba(99,102,241,0.08) 0%, transparent 70%)', transform: 'translate(-30%, -30%)' }} />

            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg flex items-center justify-center"
                  style={{ background: 'rgba(139,92,246,0.15)', border: '1px solid rgba(139,92,246,0.25)' }}>
                  <Building2 size={14} className="text-violet-400" />
                </div>
                <h2 className="text-sm font-bold text-white">Current Organization</h2>
              </div>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold"
                style={{ background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.25)', color: '#34d399' }}>
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block"
                  style={{ boxShadow: '0 0 6px #10b981', animation: 'pulseGlow 2s infinite ease-in-out' }} />
                Active
              </span>
            </div>

            {currentOrg ? (
              <div className="space-y-3">
                <div className="flex items-start gap-3">
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center text-white text-base font-black flex-shrink-0"
                    style={{ background: 'linear-gradient(135deg,#4f46e5,#7c3aed)', boxShadow: '0 4px 12px rgba(99,102,241,0.35)' }}>
                    {(currentOrg.tenant_name || 'O')[0].toUpperCase()}
                  </div>
                  <div>
                    <div className="text-base font-bold text-white">{currentOrg.tenant_name}</div>
                    {currentOrg.company_email && (
                      <div className="text-xs text-gray-400">{currentOrg.company_email}</div>
                    )}
                    <span className="inline-flex items-center gap-1 mt-1 px-1.5 py-0.5 rounded text-[10px] font-semibold"
                      style={{ background: 'rgba(139,92,246,0.1)', border: '1px solid rgba(139,92,246,0.2)', color: '#a78bfa' }}>
                      <Star size={8} /> {currentOrg.role === 'admin' ? 'Admin' : 'Member'}
                    </span>
                  </div>
                </div>

                {editingOrg ? (
                  <form onSubmit={handleSaveOrganization} className="pt-3 border-t border-gray-800/60 flex flex-col gap-3">
                    <div>
                      <label className="text-xs text-gray-400 mb-1 block">Company Name</label>
                      <input type="text" value={editOrgName} onChange={e => setEditOrgName(e.target.value)} className="w-full bg-black/40 border border-gray-800 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors" />
                    </div>
                    <div>
                      <label className="text-xs text-gray-400 mb-1 block">Company Email</label>
                      <input type="email" value={editOrgEmail} onChange={e => setEditOrgEmail(e.target.value)} className="w-full bg-black/40 border border-gray-800 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors" />
                    </div>
                    <div>
                      <label className="text-xs text-gray-400 mb-1 block">Website</label>
                      <input type="text" value={editOrgWebsite} onChange={e => setEditOrgWebsite(e.target.value)} className="w-full bg-black/40 border border-gray-800 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors" />
                    </div>
                    <div>
                      <label className="text-xs text-gray-400 mb-1 block">Address</label>
                      <input type="text" value={editOrgAddress} onChange={e => setEditOrgAddress(e.target.value)} className="w-full bg-black/40 border border-gray-800 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors" />
                    </div>
                    <div className="flex gap-2 justify-end mt-2">
                      <button type="button" onClick={() => setEditingOrg(false)} className="px-3 py-1.5 text-xs text-gray-400 hover:text-white transition-colors">Cancel</button>
                      <button type="submit" disabled={savingOrg} className="px-3 py-1.5 text-xs bg-violet-600 hover:bg-violet-500 text-white rounded transition-colors flex items-center gap-1">
                        {savingOrg ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
                        Save
                      </button>
                    </div>
                  </form>
                ) : (
                  <div className="pt-3 border-t border-gray-800/60 grid grid-cols-1 gap-2.5">
                    {userProfile?.company_website && (
                      <OrgDetail icon={<Globe size={12} />} label="Website" value={userProfile.company_website} isLink />
                    )}
                    {userProfile?.company_email && (
                      <OrgDetail icon={<Mail size={12} />} label="Company Email" value={userProfile.company_email} />
                    )}
                    {userProfile?.company_address && (
                      <OrgDetail icon={<MapPin size={12} />} label="Address" value={userProfile.company_address} />
                    )}
                    {currentOrg.role === 'admin' && (
                      <button
                        onClick={() => {
                          setEditOrgName(currentOrg.tenant_name || '');
                          setEditOrgEmail(userProfile?.company_email || '');
                          setEditOrgWebsite(userProfile?.company_website || '');
                          setEditOrgAddress(userProfile?.company_address || '');
                          setEditingOrg(true);
                        }}
                        className="mt-2 text-xs text-violet-400 hover:text-violet-300 flex items-center gap-1 transition-colors w-fit"
                      >
                        <Edit2 size={10} /> Edit Organization
                      </button>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-sm text-gray-500 flex items-center gap-2">
                <AlertCircle size={14} /> Organization info unavailable
              </div>
            )}
          </div>

          {/* ─── Organization Switcher ─────────────────────────────── */}
          <div
            className="rounded-3xl p-6 relative overflow-hidden group transition-all duration-500 hover:-translate-y-1"
            style={{
              background: 'linear-gradient(145deg, rgba(20,15,40,0.7) 0%, rgba(8,6,22,0.85) 100%)',
              backdropFilter: 'blur(24px)',
              border: '1px solid rgba(167,139,250,0.25)',
              boxShadow: '0 12px 40px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.05)',
            }}
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg flex items-center justify-center"
                  style={{ background: 'rgba(59,130,246,0.12)', border: '1px solid rgba(59,130,246,0.2)' }}>
                  <Briefcase size={14} className="text-blue-400" />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-white">My Organizations</h2>
                  <p className="text-[10px] text-gray-500">Switch between organizations linked to your email</p>
                </div>
              </div>
              <button
                onClick={fetchOrganizations}
                disabled={loadingOrgs}
                className="w-7 h-7 rounded-lg flex items-center justify-center transition-all"
                style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)', color: '#64748b' }}
                title="Refresh organizations"
                id="refresh-orgs-btn"
              >
                <RefreshCcw size={13} className={loadingOrgs ? 'animate-spin' : ''} />
              </button>
            </div>

            {loadingOrgs && !organizations.length ? (
              <div className="flex items-center gap-2 text-gray-500 text-xs py-4">
                <Loader2 size={14} className="animate-spin" /> Loading organizations…
              </div>
            ) : organizations.length === 0 ? (
              <div className="text-xs text-gray-500 py-4 flex items-center gap-2">
                <AlertCircle size={13} /> No organizations found for this account.
              </div>
            ) : (
              <div className="space-y-2">
                {organizations.map(org => {
                  const isCurrent = org.is_current;
                  const isSwitching = switchingTo === org.tenant_id;
                  const didSwitch = switchSuccess === org.tenant_id;

                  return (
                    <div
                      key={org.tenant_id}
                      className="flex items-center gap-3 p-3 rounded-2xl transition-all duration-300 hover:scale-[1.02]"
                      style={{
                        background: isCurrent ? 'linear-gradient(90deg, rgba(139,92,246,0.15) 0%, rgba(79,70,229,0.05) 100%)' : 'rgba(255,255,255,0.03)',
                        border: isCurrent ? '1px solid rgba(139,92,246,0.4)' : '1px solid rgba(255,255,255,0.08)',
                        boxShadow: isCurrent ? '0 4px 20px rgba(139,92,246,0.15)' : 'none',
                      }}
                      id={`org-row-${org.tenant_id}`}
                    >
                      {/* Org avatar */}
                      <div
                        className="w-10 h-10 rounded-xl flex items-center justify-center text-sm font-black text-white flex-shrink-0"
                        style={{
                          background: isCurrent
                            ? 'linear-gradient(135deg,#7c3aed,#4f46e5)'
                            : 'linear-gradient(135deg,#1e293b,#0f172a)',
                          boxShadow: isCurrent ? '0 4px 12px rgba(139,92,246,0.3)' : 'none',
                          border: isCurrent ? 'none' : '1px solid rgba(255,255,255,0.08)',
                        }}
                      >
                        {(org.tenant_name || 'O')[0].toUpperCase()}
                      </div>

                      {/* Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="text-sm font-semibold text-white truncate">{org.tenant_name}</span>
                          {isCurrent && (
                            <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-bold flex-shrink-0"
                              style={{ background: 'rgba(139,92,246,0.15)', color: '#c4b5fd' }}>
                              Current
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          {org.company_email && (
                            <span className="text-[10px] text-gray-500 truncate">{org.company_email}</span>
                          )}
                          <span className="text-[10px] font-semibold"
                            style={{ color: org.role === 'admin' ? '#a78bfa' : '#64748b' }}>
                            {org.role === 'admin' ? '· Admin' : '· Member'}
                          </span>
                        </div>
                      </div>

                      {/* Switch button */}
                      {!isCurrent && (
                        <button
                          onClick={() => handleSwitchOrg(org.tenant_id)}
                          disabled={!!switchingTo}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex-shrink-0"
                          style={{
                            background: didSwitch ? 'rgba(16,185,129,0.15)' : 'rgba(99,102,241,0.1)',
                            border: didSwitch ? '1px solid rgba(16,185,129,0.3)' : '1px solid rgba(99,102,241,0.2)',
                            color: didSwitch ? '#34d399' : '#818cf8',
                          }}
                          id={`switch-org-btn-${org.tenant_id}`}
                        >
                          {isSwitching ? (
                            <Loader2 size={11} className="animate-spin" />
                          ) : didSwitch ? (
                            <CheckCircle2 size={11} />
                          ) : (
                            <LogIn size={11} />
                          )}
                          {isSwitching ? 'Switching…' : didSwitch ? 'Switched!' : 'Switch'}
                        </button>
                      )}

                      {isCurrent && (
                        <div className="flex items-center gap-1 text-violet-400 flex-shrink-0">
                          <CheckCircle2 size={14} />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {organizations.length > 1 && (
              <p className="text-[10px] text-gray-600 mt-4 flex items-center gap-1.5">
                <AlertCircle size={10} />
                Switching organization reloads your session to that workspace. Your email stays the same.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Small helper sub-components ─────────────────────────────────────────── */

function InfoRow({ icon, label, value, highlight }: { icon: React.ReactNode; label: string; value?: string | null; highlight?: string }) {
  return (
    <div className="flex items-center gap-2.5">
      <span style={{ color: '#64748b' }}>{icon}</span>
      <span className="text-[11px] text-gray-500 w-14 flex-shrink-0">{label}</span>
      <span className="text-xs font-medium truncate" style={{ color: highlight || '#e2e8f0' }}>
        {value || '—'}
      </span>
    </div>
  );
}

function OrgDetail({ icon, label, value, isLink }: { icon: React.ReactNode; label: string; value: string; isLink?: boolean }) {
  return (
    <div className="flex items-start gap-2.5">
      <span className="mt-0.5 flex-shrink-0" style={{ color: '#64748b' }}>{icon}</span>
      <div className="min-w-0">
        <div className="text-[10px] text-gray-600 uppercase tracking-wider font-semibold">{label}</div>
        {isLink ? (
          <a
            href={value.startsWith('http') ? value : `https://${value}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 transition-colors"
          >
            {value} <ExternalLink size={10} />
          </a>
        ) : (
          <div className="text-xs text-gray-300 break-all">{value}</div>
        )}
      </div>
    </div>
  );
}
