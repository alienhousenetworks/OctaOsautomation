'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Zap, Loader2 } from 'lucide-react';
import { saveSession } from '@/lib/auth-session';

interface AuthFormsProps {
  appState: 'login' | 'signup';
  setAppState: (state: 'landing' | 'login' | 'signup' | 'app') => void;
  API_URL: string;
  setToken: (token: string | null) => void;
  setTenantId: (tenantId: string | null) => void;
  inviteToken?: string | null;
  setInviteToken?: (token: string | null) => void;
  logoUrl?: string | null;
}

export default function AuthForms({
  appState,
  setAppState,
  API_URL,
  setToken,
  setTenantId,
  inviteToken,
  setInviteToken,
  logoUrl,
}: AuthFormsProps) {
  // Form input states
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [fullName, setFullName] = useState('');
  const [phoneNo, setPhoneNo] = useState('');
  const [companyWebsite, setCompanyWebsite] = useState('');
  const [companyEmail, setCompanyEmail] = useState('');
  const [companyAddress, setCompanyAddress] = useState('');
  
  // OTP flow states
  const [otp, setOtp] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [otpTimer, setOtpTimer] = useState(0);
  const [otpMethod, setOtpMethod] = useState<'signup' | 'login'>('signup');
  const [tempEmail, setTempEmail] = useState('');
  const [loginMode, setLoginMode] = useState<'password' | 'otp'>('password');
  const [tenantSelection, setTenantSelection] = useState<{id: string, name: string}[] | null>(null);

  // Invitation verify & accept states
  const [invitationDetails, setInvitationDetails] = useState<{company_name: string, email?: string} | null>(null);
  const [invitationError, setInvitationError] = useState<string | null>(null);
  const [verifyingInvite, setVerifyingInvite] = useState(false);

  useEffect(() => {
    if (inviteToken) {
      const verifyToken = async () => {
        setVerifyingInvite(true);
        setInvitationError(null);
        try {
          const res = await fetch(`${API_URL}/auth/invite/verify?token=${inviteToken}`);
          const data = await res.json();
          if (res.ok) {
            setInvitationDetails(data);
            if (data.email) {
              setEmail(data.email);
            }
          } else {
            setInvitationError(data.detail || "Invalid or expired invitation token");
          }
        } catch (e) {
          console.error(e);
          setInvitationError("Failed to verify invitation token");
        } finally {
          setVerifyingInvite(false);
        }
      };
      verifyToken();
    }
  }, [inviteToken]);

  const handleAcceptInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_URL}/auth/invite/accept`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token: inviteToken,
          name: fullName,
          email,
          password
        })
      });
      const data = await res.json();
      if (res.ok) {
        saveSession({
          access_token: data.access_token,
          refresh_token: data.refresh_token,
          tenant_id: data.tenant_id,
        });
        setToken(data.access_token);
        if (data.tenant_id) setTenantId(data.tenant_id);
        setInviteToken?.(null);
        setAppState('app');
      } else {
        alert(data.detail || "Failed to accept invitation");
      }
    } catch (e) {
      console.error(e);
      alert("Error accepting invitation");
    }
  };

  // Countdown timer for OTP resend
  useEffect(() => {
    if (otpTimer > 0) {
      const timer = setTimeout(() => setOtpTimer(otpTimer - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [otpTimer]);

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_URL}/auth/signup/initiate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: fullName,
          email,
          phone_no: phoneNo,
          company: companyName || null,
          company_website: companyWebsite || null,
          company_email: companyEmail || null,
          company_address: companyAddress || null,
          password
        })
      });
      const data = await res.json();
      if (res.ok) {
        setTempEmail(email);
        setOtpSent(true);
        setOtpMethod('signup');
        setOtpTimer(60);
        setOtp('');
      } else {
        alert(data.detail || "Signup failed");
      }
    } catch (e) {
      console.error(e);
      alert("Failed to connect to the backend server. Please verify that the backend is running at " + API_URL);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload: any = { email };
      if (loginMode === 'password') {
        if (!password) {
          alert("Please enter your password");
          return;
        }
        payload.password = password;
      }
      
      const res = await fetch(`${API_URL}/auth/login/initiate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok) {
        if (data.needs_tenant_selection) {
          setTenantSelection(data.tenants);
          setTempEmail(email);
        } else if (data.otp_required === false) {
          saveSession({
            access_token: data.access_token,
            refresh_token: data.refresh_token,
            tenant_id: data.tenant_id,
          });
          setToken(data.access_token);
          if (data.tenant_id) setTenantId(data.tenant_id);
          // Reset states
          setOtpSent(false);
          setOtp('');
          setTempEmail('');
          setEmail('');
          setPassword('');
          setTenantSelection(null);
          setAppState('app');
        } else {
          setTempEmail(email);
          setOtpSent(true);
          setOtpMethod('login');
          setOtpTimer(60);
          setOtp('');
        }
      } else {
        alert(data.detail || "Login failed");
      }
    } catch (e) {
      console.error(e);
      alert("Failed to connect to the backend server. Please verify that the backend is running at " + API_URL);
    }
  };

  const handleOtpVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    const endpoint = otpMethod === 'signup' ? 'signup/verify' : 'login/verify';
    try {
      const res = await fetch(`${API_URL}/auth/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: tempEmail, otp })
      });
      const data = await res.json();
      if (res.ok) {
        if (data.needs_tenant_selection) {
           setTenantSelection(data.tenants);
           setOtpSent(false);
        } else {
          saveSession({
            access_token: data.access_token,
            refresh_token: data.refresh_token,
            tenant_id: data.tenant_id,
          });
          setToken(data.access_token);
          if (data.tenant_id) setTenantId(data.tenant_id);
          // Reset states
          setOtpSent(false);
          setOtp('');
          setTempEmail('');
          setFullName('');
          setPhoneNo('');
          setCompanyName('');
          setCompanyWebsite('');
          setCompanyEmail('');
          setCompanyAddress('');
          setEmail('');
          setPassword('');
          setTenantSelection(null);
          setAppState('app');
        }
      } else {
        alert(data.detail || "OTP verification failed");
      }
    } catch (e) {
      console.error(e);
      alert("Error during OTP verification");
    }
  };


  const handleSelectCompany = async (tenantId: string) => {
    try {
      const endpoint = otpMethod === 'signup' ? 'signup/verify' : 'login/initiate';
      const payload: any = { email: tempEmail, tenant_id: tenantId };
      if (loginMode === 'password') {
        payload.password = password;
      } else if (otp) {
        payload.otp = otp;
      }
      
      const res = await fetch(`${API_URL}/auth/${loginMode === 'password' ? 'login/initiate' : 'login/verify'}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok) {
        saveSession({
          access_token: data.access_token,
          refresh_token: data.refresh_token,
          tenant_id: data.tenant_id,
        });
        setToken(data.access_token);
        if (data.tenant_id) setTenantId(data.tenant_id);
        // Reset states
        setOtpSent(false);
        setOtp('');
        setTempEmail('');
        setEmail('');
        setPassword('');
        setTenantSelection(null);
        setAppState('app');
      } else {
        alert(data.detail || "Failed to switch company");
      }
    } catch (e) {
      console.error(e);
      alert("Error selecting company");
    }
  };

  const handleResendOtp = async () => {
    if (otpTimer > 0) return;
    const endpoint = otpMethod === 'signup' ? 'signup/resend-otp' : 'login/resend-otp';
    try {
      const res = await fetch(`${API_URL}/auth/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: tempEmail })
      });
      const data = await res.json();
      if (res.ok) {
        alert("A new OTP code has been sent to " + tempEmail);
        setOtpTimer(60);
      } else {
        alert(data.detail || "Failed to resend OTP");
      }
    } catch (e) {
      console.error(e);
      alert('Network error resending OTP.');
    }
  };

  if (inviteToken) {
    return (
      <div className="min-h-screen bg-[#030014] text-[#f4f4f7] relative overflow-hidden font-sans flex flex-col justify-center items-center px-4">
        {/* Ambient background glows */}
        <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-[rgba(139,92,246,0.12)] rounded-full blur-[100px] pointer-events-none" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-[rgba(59,130,246,0.12)] rounded-full blur-[100px] pointer-events-none" />
        <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.01)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.01)_1px,transparent_1px)] bg-[size:4rem_4rem] pointer-events-none" />

        <Card className="w-full max-w-md glass-panel border-violet-500/20 shadow-2xl relative overflow-hidden rounded-3xl animate-in fade-in zoom-in-95 duration-300">
          <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-violet-500 to-transparent" />
          <CardHeader className="space-y-2 pt-8">
            <div className="flex justify-center items-center gap-3 mb-2">
              {logoUrl ? (
                <img src={logoUrl} alt="OctaOS Logo" className="h-12 w-auto max-w-[160px] object-contain" />
              ) : (
                <div className="bg-gradient-to-tr from-violet-600 to-indigo-600 p-2.5 rounded-xl shadow-lg shadow-violet-500/20">
                  <Zap className="text-white fill-white h-5 w-5 animate-pulse" />
                </div>
              )}
              <span className="text-white font-extrabold text-2xl tracking-tight">OctaOs</span>
            </div>
            <CardTitle className="text-2xl text-center text-white font-extrabold tracking-tight">
              {verifyingInvite ? "Verifying invitation..." : `Join ${invitationDetails?.company_name || 'Organization'}`}
            </CardTitle>
            <CardDescription className="text-center text-gray-400 text-xs">
              {invitationError ? (
                <span className="text-rose-400 font-bold">{invitationError}</span>
              ) : (
                "Complete your profile to accept the invitation and join the workspace."
              )}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6 pb-8">
            {invitationError ? (
              <Button 
                onClick={() => {
                  setInviteToken?.(null);
                  setAppState('login');
                }}
                className="w-full bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-bold h-11 rounded-xl shadow-lg shadow-violet-500/20 transition-all text-xs"
              >
                Go to Login
              </Button>
            ) : verifyingInvite ? (
              <div className="flex justify-center py-8">
                <Loader2 className="animate-spin h-8 w-8 text-violet-500" />
              </div>
            ) : (
              <form onSubmit={handleAcceptInvite} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-gray-400">Full Name</label>
                  <Input 
                    placeholder="Jane Doe" 
                    required
                    value={fullName} 
                    onChange={e => setFullName(e.target.value)} 
                    className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-violet-500 focus:ring-violet-500/20 h-11 text-sm"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-gray-400">Email Address</label>
                  <Input 
                    placeholder="name@company.com" 
                    type="email" 
                    required
                    value={email} 
                    onChange={e => setEmail(e.target.value)} 
                    className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-violet-500 focus:ring-violet-500/20 h-11 text-sm"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-gray-400">Password</label>
                  <Input 
                    placeholder="••••••••" 
                    type="password" 
                    required
                    value={password} 
                    onChange={e => setPassword(e.target.value)} 
                    className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-violet-500 focus:ring-violet-500/20 h-11 text-sm"
                  />
                </div>

                <div className="pt-2">
                  <button 
                    className="w-full bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-bold py-3.5 rounded-xl shadow-lg shadow-violet-500/20 hover:shadow-violet-500/30 transition-all hover:scale-[1.01] active:scale-95 cursor-pointer flex justify-center items-center text-sm" 
                    type="submit"
                  >
                    Accept Invite & Sign Up
                  </button>
                </div>

                <div className="text-center text-xs text-gray-400">
                  Already have an account? <span className="text-violet-400 hover:text-violet-300 cursor-pointer font-bold transition-colors" onClick={() => {
                    setInviteToken?.(null);
                    setAppState('login');
                  }}>Log in</span>
                </div>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  if (tenantSelection) {
    return (
      <div className="min-h-screen bg-[#030014] text-[#f4f4f7] relative overflow-hidden font-sans flex flex-col justify-center items-center px-4">
        {/* Ambient background glows */}
        <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-[rgba(139,92,246,0.12)] rounded-full blur-[100px] pointer-events-none" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-[rgba(59,130,246,0.12)] rounded-full blur-[100px] pointer-events-none" />
        <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.01)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.01)_1px,transparent_1px)] bg-[size:4rem_4rem] pointer-events-none" />

        <Card className="w-full max-w-md glass-panel border-violet-500/20 shadow-2xl relative overflow-hidden rounded-3xl animate-in fade-in zoom-in-95 duration-300">
          <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-violet-500 to-transparent" />
          <CardHeader className="space-y-2 pt-8">
            <div className="flex justify-center items-center gap-3 mb-2">
              {logoUrl ? (
                <img src={logoUrl} alt="OctaOS Logo" className="h-12 w-auto max-w-[160px] object-contain" />
              ) : (
                <div className="bg-gradient-to-tr from-violet-600 to-indigo-600 p-2.5 rounded-xl shadow-lg shadow-violet-500/20">
                  <Zap className="text-white fill-white h-5 w-5 animate-pulse" />
                </div>
              )}
              <span className="text-white font-extrabold text-2xl tracking-tight">OctaOs</span>
            </div>
            <CardTitle className="text-2xl text-center text-white font-extrabold tracking-tight">Select Workspace</CardTitle>
            <CardDescription className="text-center text-gray-400 text-xs">
              You are associated with multiple companies. Select which one to manage.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 pb-8">
            <div className="space-y-3">
              {tenantSelection.map((tenant) => (
                <button
                  key={tenant.id}
                  onClick={() => handleSelectCompany(tenant.id)}
                  className="w-full bg-gray-900/60 border border-gray-800 hover:border-violet-500 text-white font-bold py-3.5 rounded-xl shadow-lg hover:shadow-violet-500/20 transition-all hover:scale-[1.01] active:scale-95 flex items-center justify-between px-4 text-sm text-left"
                >
                  <span>{tenant.name}</span>
                  <span className="text-violet-400">&rarr;</span>
                </button>
              ))}
            </div>
            <div className="text-center text-xs text-gray-400 pt-4">
              <span className="text-violet-400 hover:text-violet-300 cursor-pointer font-bold transition-colors" onClick={() => setTenantSelection(null)}>Back to Login</span>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (otpSent) {
    return (
      <div className="min-h-screen bg-[#030014] text-[#f4f4f7] relative overflow-hidden font-sans flex flex-col justify-center items-center px-4">
        {/* Ambient background glows */}
        <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-[rgba(139,92,246,0.12)] rounded-full blur-[100px] pointer-events-none" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-[rgba(59,130,246,0.12)] rounded-full blur-[100px] pointer-events-none" />
        <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.01)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.01)_1px,transparent_1px)] bg-[size:4rem_4rem] pointer-events-none" />

        <Card className="w-full max-w-md glass-panel border-violet-500/20 shadow-2xl relative overflow-hidden rounded-3xl">
          <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-violet-500 to-transparent" />
          <CardHeader className="space-y-2 pt-8">
            <div className="flex justify-center items-center gap-3 mb-2">
              {logoUrl ? (
                <img src={logoUrl} alt="OctaOS Logo" className="h-12 w-auto max-w-[160px] object-contain" />
              ) : (
                <div className="bg-gradient-to-tr from-violet-600 to-indigo-600 p-2.5 rounded-xl shadow-lg shadow-violet-500/20">
                  <Zap className="text-white fill-white h-5 w-5 animate-pulse" />
                </div>
              )}
              <span className="text-white font-extrabold text-2xl tracking-tight">OctaOs</span>
            </div>
            <CardTitle className="text-2xl text-center text-white font-extrabold tracking-tight">
              {otpMethod === 'signup' ? "Confirm Verification Code" : "Security Verification"}
            </CardTitle>
            <CardDescription className="text-center text-gray-400 text-xs">
              We sent a 6-digit verification code to <strong className="text-violet-300">{tempEmail}</strong>.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6 pb-8">
            <form onSubmit={handleOtpVerify} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-gray-400">Verification OTP Code</label>
                <Input 
                  placeholder="Enter 6-digit OTP code" 
                  maxLength={6}
                  value={otp} 
                  onChange={e => setOtp(e.target.value)} 
                  className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-violet-500 focus:ring-violet-500/20 text-center tracking-widest text-lg font-bold"
                />
              </div>

              <div className="flex gap-4">
                <Button 
                  type="submit" 
                  className="flex-1 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-bold h-11 rounded-xl shadow-lg shadow-violet-500/20 transition-all hover:scale-[1.01] active:scale-95 text-xs"
                >
                  Verify & {otpMethod === 'signup' ? "Create Account" : "Access"}
                </Button>
                <Button 
                  type="button" 
                  variant="outline"
                  onClick={handleResendOtp}
                  disabled={otpTimer > 0}
                  className="flex-1 h-11 rounded-xl text-xs font-bold border-gray-800 text-gray-300 hover:text-white bg-[rgba(255,255,255,0.01)] hover:bg-[rgba(255,255,255,0.03)]"
                >
                  {otpTimer > 0 ? `Resend in ${otpTimer}s` : "Resend Code"}
                </Button>
              </div>

              <div className="text-center text-xs text-gray-400 pt-2">
                Want to use a different email? <span className="text-violet-400 hover:text-violet-300 cursor-pointer font-bold transition-colors" onClick={() => setOtpSent(false)}>Go Back</span>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (appState === 'login') {
    return (
      <div className="min-h-screen bg-[#030014] text-[#f4f4f7] relative overflow-hidden font-sans flex flex-col justify-center items-center px-4">
        {/* Ambient background glows */}
        <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-[rgba(139,92,246,0.12)] rounded-full blur-[100px] pointer-events-none" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-[rgba(59,130,246,0.12)] rounded-full blur-[100px] pointer-events-none" />
        <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.01)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.01)_1px,transparent_1px)] bg-[size:4rem_4rem] pointer-events-none" />

        <Card className="w-full max-w-md glass-panel border-violet-500/20 shadow-2xl relative overflow-hidden rounded-3xl animate-in fade-in zoom-in-95 duration-300">
          <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-violet-500 to-transparent" />
          <CardHeader className="space-y-2 pt-8">
            <div className="flex justify-center items-center gap-3 mb-2">
              {logoUrl ? (
                <img src={logoUrl} alt="OctaOS Logo" className="h-12 w-auto max-w-[160px] object-contain" />
              ) : (
                <div className="bg-gradient-to-tr from-violet-600 to-indigo-600 p-2.5 rounded-xl shadow-lg shadow-violet-500/20">
                  <Zap className="text-white fill-white h-5 w-5 animate-pulse" />
                </div>
              )}
              <span className="text-white font-extrabold text-2xl tracking-tight">OctaOs</span>
            </div>
            <CardTitle className="text-2xl text-center text-white font-extrabold tracking-tight">Access Your Workspace</CardTitle>
            <CardDescription className="text-center text-gray-400 text-xs">
              {loginMode === 'password' 
                ? "Enter your email and password to log in directly." 
                : "Enter your email. A one-time code (OTP) will be sent."}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6 pb-8">
            {/* Tabs Toggle */}
            <div className="flex bg-gray-950/60 p-1 rounded-xl border border-gray-800">
              <button
                type="button"
                onClick={() => setLoginMode('password')}
                className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${
                  loginMode === 'password'
                    ? 'bg-[rgba(255,255,255,0.06)] text-white shadow'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                Password Login
              </button>
              <button
                type="button"
                onClick={() => setLoginMode('otp')}
                className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${
                  loginMode === 'otp'
                    ? 'bg-[rgba(255,255,255,0.06)] text-white shadow'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                OTP Login
              </button>
            </div>

            <form onSubmit={handleLogin} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-gray-400">Email Address</label>
                <Input 
                  placeholder="name@company.com" 
                  type="email" 
                  value={email} 
                  onChange={e => setEmail(e.target.value)} 
                  className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-violet-500 focus:ring-violet-500/20 h-11 text-sm"
                />
              </div>
              
              {loginMode === 'password' && (
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-gray-400">Password</label>
                  <Input 
                    placeholder="••••••••" 
                    type="password" 
                    required={loginMode === 'password'}
                    value={password} 
                    onChange={e => setPassword(e.target.value)} 
                    className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-violet-500 focus:ring-violet-500/20 h-11 text-sm"
                  />
                </div>
              )}

              <div className="pt-2">
                <button 
                  className="w-full bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-bold py-3.5 rounded-xl shadow-lg shadow-violet-500/20 hover:shadow-violet-500/30 transition-all hover:scale-[1.01] active:scale-95 cursor-pointer flex justify-center items-center text-sm" 
                  type="submit"
                >
                  {loginMode === 'password' ? "Log In" : "Send Login OTP"}
                </button>
              </div>

              <div className="text-center text-xs text-gray-400">
                Don't have an account? <span className="text-violet-400 hover:text-violet-300 cursor-pointer font-bold transition-colors" onClick={() => setAppState('signup')}>Sign up</span>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    );
  }

  // signup
  return (
    <div className="min-h-screen bg-[#030014] text-[#f4f4f7] relative overflow-hidden font-sans flex flex-col justify-center items-center px-4 py-12">
      {/* Ambient background glows */}
      <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-[rgba(139,92,246,0.12)] rounded-full blur-[100px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-[rgba(59,130,246,0.12)] rounded-full blur-[100px] pointer-events-none" />
      <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.01)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.01)_1px,transparent_1px)] bg-[size:4rem_4rem] pointer-events-none" />

      <Card className="w-full max-w-2xl glass-panel border-violet-500/20 shadow-2xl relative overflow-hidden rounded-3xl animate-in fade-in zoom-in-95 duration-300">
        <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-violet-500 to-transparent" />
        <CardHeader className="space-y-2 pt-8">
          <div className="flex justify-center items-center gap-3 mb-2">
              {logoUrl ? (
                <img src={logoUrl} alt="OctaOS Logo" className="h-12 w-auto max-w-[160px] object-contain" />
              ) : (
                <div className="bg-gradient-to-tr from-violet-600 to-indigo-600 p-2.5 rounded-xl shadow-lg shadow-violet-500/20">
                  <Zap className="text-white fill-white h-5 w-5 animate-pulse" />
                </div>
              )}
              <span className="text-white font-extrabold text-2xl tracking-tight">OctaOs</span>
            </div>
          <CardTitle className="text-2xl text-center text-white font-extrabold tracking-tight">Deploy Your Workspace</CardTitle>
          <CardDescription className="text-center text-gray-400 text-xs">Create your admin profile and company details. Setup takes 30 seconds.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6 pb-8">
          <form onSubmit={handleSignup} className="space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              
              {/* Left side: Admin details */}
              <div className="space-y-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-violet-400">Admin Account Info</h3>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-gray-400">Full Name</label>
                  <Input 
                    placeholder="Jane Doe" 
                    required
                    value={fullName} 
                    onChange={e => setFullName(e.target.value)} 
                    className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-violet-500 focus:ring-violet-500/20"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-gray-400">Email Address</label>
                  <Input 
                    placeholder="jane@company.com" 
                    type="email" 
                    required
                    value={email} 
                    onChange={e => setEmail(e.target.value)} 
                    className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-violet-500 focus:ring-violet-500/20"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-gray-400">Phone Number (For WhatsApp AI)</label>
                  <Input 
                    placeholder="+1 (555) 012-3456" 
                    required
                    value={phoneNo} 
                    onChange={e => setPhoneNo(e.target.value)} 
                    className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-violet-500 focus:ring-violet-500/20"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-gray-400">Account Password</label>
                  <Input 
                    placeholder="••••••••" 
                    type="password" 
                    required
                    value={password} 
                    onChange={e => setPassword(e.target.value)} 
                    className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-violet-500 focus:ring-violet-500/20"
                  />
                </div>
              </div>

              {/* Right side: Company details */}
              <div className="space-y-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-violet-400">Company / Workspace Details</h3>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-gray-400">Company Name</label>
                  <Input 
                    placeholder="Acme Corp" 
                    required
                    value={companyName} 
                    onChange={e => setCompanyName(e.target.value)} 
                    className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-violet-500 focus:ring-violet-500/20"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-gray-400">Company Website</label>
                  <Input 
                    placeholder="https://acme.com" 
                    type="url"
                    value={companyWebsite} 
                    onChange={e => setCompanyWebsite(e.target.value)} 
                    className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-violet-500 focus:ring-violet-500/20"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-gray-400">Company Email</label>
                  <Input 
                    placeholder="info@acme.com" 
                    type="email"
                    value={companyEmail} 
                    onChange={e => setCompanyEmail(e.target.value)} 
                    className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-violet-500 focus:ring-violet-500/20"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-gray-400">Company Address</label>
                  <Input 
                    placeholder="123 Business Rd, Suite 100" 
                    value={companyAddress} 
                    onChange={e => setCompanyAddress(e.target.value)} 
                    className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-violet-500 focus:ring-violet-500/20"
                  />
                </div>
              </div>

            </div>

            <div className="pt-2">
              <button 
                className="w-full bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-bold py-3.5 rounded-xl shadow-lg shadow-violet-500/20 hover:shadow-violet-500/30 transition-all hover:scale-[1.01] active:scale-95 cursor-pointer flex justify-center items-center text-sm" 
                type="submit"
              >
                Send Verification OTP
              </button>
            </div>

            <div className="text-center text-xs text-gray-400">
              Already have an account? <span className="text-violet-400 hover:text-violet-300 cursor-pointer font-bold transition-colors" onClick={() => setAppState('login')}>Log in</span>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
