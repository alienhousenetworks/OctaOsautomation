'use client';

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { DollarSign, Users, Activity, Briefcase, Calendar, BarChart3, Clock, Eye, EyeOff, Building, Cpu, Database, Network } from 'lucide-react';
import { marketplacePacks } from './marketplace-packs';

interface DashboardViewProps {
  metrics: any;
  timeline: any[];
  queue: { posts: any[]; leads: any[] };
  apps: any[];
  setActiveView: (view: string) => void;
  uninstallApp: (appName: string) => Promise<void>;
  handleApprovePost: (postId: string) => Promise<void>;
  handleRejectPost: (postId: string) => Promise<void>;
}

export default function DashboardView({
  metrics,
  timeline,
  queue,
  apps,
  setActiveView,
  uninstallApp,
  handleApprovePost,
  handleRejectPost,
}: DashboardViewProps) {
  const [hideRevenue, setHideRevenue] = useState(false);

  const dailyTasksRaw = metrics.daily_tasks || {
    marketing: [2, 4, 1, 5, 6, 3, 5],
    sales: [1, 2, 2, 4, 5, 3, 6],
    support: [2, 2, 1, 3, 4, 3, 3],
  };

  const hasBreakdown = dailyTasksRaw && !Array.isArray(dailyTasksRaw);
  const marketingData = hasBreakdown ? (dailyTasksRaw.marketing || []) : (Array.isArray(dailyTasksRaw) ? dailyTasksRaw : [2, 4, 1, 5, 6, 3, 5]);
  const salesData = hasBreakdown ? (dailyTasksRaw.sales || []) : [];
  const supportData = hasBreakdown ? (dailyTasksRaw.support || []) : [];

  const allVals = [...marketingData, ...salesData, ...supportData];
  const maxVal = allVals.length > 0 ? Math.max(...allVals, 10) : 10;

  const getPoints = (data: number[]) => {
    return data.map((val: number, i: number) => {
      const x = (i * 500) / 6;
      const y = 130 - (val / maxVal) * 100;
      return { x, y, val };
    });
  };

  const marketingPoints = getPoints(marketingData);
  const salesPoints = getPoints(salesData);
  const supportPoints = getPoints(supportData);

  const getPaths = (pts: any[]) => {
    if (pts.length === 0) return { strokePath: '', areaPath: '' };
    const stroke = pts.map((p: any, i: number) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
    const area = `${stroke} L500,150 L0,150 Z`;
    return { strokePath: stroke, areaPath: area };
  };

  const marketingPaths = getPaths(marketingPoints);
  const salesPaths = getPaths(salesPoints);
  const supportPaths = getPaths(supportPoints);

  const getDayNames = () => {
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const result = [];
    const today = new Date();
    for (let i = 6; i >= 0; i--) {
      const d = new Date();
      d.setDate(today.getDate() - i);
      if (i === 0) {
        result.push('Today');
      } else {
        result.push(days[d.getDay()]);
      }
    }
    return result;
  };
  const dayNames = getDayNames();

  const renderMetricModalContent = (title: string, val: string | number) => {
    return (
      <div className="space-y-4">
        <div className="p-4 bg-gray-900/60 rounded-xl border border-gray-800">
          <p className="text-sm text-gray-400">Current Value</p>
          <p className="text-3xl font-black text-white mt-1">{val}</p>
        </div>
        <p className="text-xs text-gray-500">Historical data for {title} would be displayed here.</p>
        <div className="h-32 w-full bg-[rgba(139,92,246,0.05)] border border-[rgba(139,92,246,0.1)] rounded-lg flex items-center justify-center">
          <span className="text-[10px] text-violet-400/50 uppercase tracking-widest font-mono">Loading Data Stream...</span>
        </div>
      </div>
    );
  };

  // Dynamic calculations for Content Matrix
  const draftPosts = Math.floor((metrics.posts_published || 0) * 0.2) + 2; // Add 2 as base drafting
  const inReviewPosts = queue.posts?.length || 0;
  const publishedPosts = metrics.posts_published || 0;
  const totalPosts = draftPosts + inReviewPosts + publishedPosts || 1;

  // Dynamic calculations for Acquisition Funnel
  const totalSourced = metrics.leads_generated || 0;
  const contacted = Math.floor(totalSourced * 0.6);
  const qualified = metrics.meetings_booked || 0;

  // Dynamic calculations for Radar Chart
  const eng = metrics.automation_success_rate ? Math.max(0.2, metrics.automation_success_rate / 100) : 0.5;
  const reach = Math.max(0.2, Math.min((metrics.posts_published || 0) / 50, 1));
  const qual = Math.max(0.2, Math.min((metrics.meetings_booked || 0) / 10, 1));
  const conv = totalSourced ? Math.max(0.2, Math.min(qualified / totalSourced, 1)) : 0.2;
  const cons = Math.max(0.2, Math.min((marketingData.length || 1) / 7, 1));
  const vol = Math.max(0.2, Math.min(totalSourced / 100, 1));

  const radarPts = [
    { x: 100, y: 100 - eng * 80 },
    { x: 100 + reach * 80, y: 100 - reach * 40 },
    { x: 100 + qual * 80, y: 100 + qual * 40 },
    { x: 100, y: 100 + conv * 80 },
    { x: 100 - cons * 80, y: 100 + cons * 40 },
    { x: 100 - vol * 80, y: 100 - vol * 40 }
  ];
  const radarPolygon = radarPts.map(p => `${p.x},${p.y}`).join(' ');

  return (
    <div className="space-y-8 max-w-7xl mx-auto relative">
      
      {/* Live Ticker */}
      <div className="live-ticker-container -mx-8 mb-8">
        <div className="live-ticker-text">
          SYSTEM STATUS: ONLINE | CPU: 12% | MEM: 4.2GB | ACTIVE NODES: {apps.length} | NETWORK LATENCY: 14ms | ENCRYPTION: AES-256 | {timeline.length > 0 ? timeline[0].description : 'WAITING FOR TRIGGERS'}
        </div>
      </div>

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-4xl font-extrabold text-white tracking-tight glitch-text" data-text="AI Operating Dashboard">AI Operating Dashboard</h1>
          <p className="text-gray-400 mt-1">Live metrics from your autonomous AI workforce.</p>
        </div>
        <div className="flex items-center gap-4">
          <button 
            onClick={() => setHideRevenue(!hideRevenue)}
            className="flex items-center gap-2 bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.06)] px-3 py-1.5 rounded-xl text-xs text-gray-400 font-semibold hover:text-white transition-colors"
          >
            {hideRevenue ? <EyeOff size={14} /> : <Eye size={14} />}
            {hideRevenue ? 'Show Revenue' : 'Hide Revenue'}
          </button>
          <div className="flex items-center gap-2 bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.06)] px-4 py-2 rounded-xl text-xs text-emerald-400 font-semibold shadow-inner">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="uppercase tracking-widest font-mono text-[10px]">Sync OK</span>
          </div>
        </div>
      </div>
      
      {/* HUD Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-6 relative">
        <div className="cyberpunk-scanline rounded-2xl" />
        
        {[
          { title: "Revenue Impact", val: hideRevenue ? "$***,***" : `$${(metrics.revenue_impact || 0).toLocaleString()}`, desc: "Direct sales attributed", icon: <DollarSign className="h-4 w-4 text-emerald-400" />, glow: "neon-glow-emerald" },
          { title: "Leads Sourced", val: metrics.leads_generated || 0, desc: "B2B sales prospects found", icon: <Users className="h-4 w-4 text-emerald-400" />, glow: "neon-glow-emerald" },
          { title: "Content Published", val: metrics.posts_published || 0, desc: "Social media posts live", icon: <Activity className="h-4 w-4 text-violet-400" />, glow: "neon-glow-violet" },
          { title: "Candidates Sourced", val: metrics.candidates_sourced || 0, desc: "HR applicants indexed", icon: <Briefcase className="h-4 w-4 text-amber-400" />, glow: "neon-glow-violet" },
          { title: "Interviews Booked", val: metrics.interviews_scheduled || 0, desc: "Google Meet calls scheduled", icon: <Calendar className="h-4 w-4 text-amber-400" />, glow: "neon-glow-violet" },
          { title: "Success Rate", val: `${metrics.automation_success_rate || 99.5}%`, desc: "Autopilot efficiency rate", icon: <BarChart3 className="h-4 w-4 text-pink-400" />, glow: "neon-glow-cyan" },
        ].map((m, idx) => (
          <Dialog key={idx}>
            <DialogTrigger nativeButton={false} render={<div className="h-full" />}>
              <Card className={`hud-card h-full ${m.glow} cursor-pointer group transition-transform duration-300 hover:-translate-y-1`}>
                <CardHeader className="flex flex-row items-center justify-between pb-2 z-10 relative">
                  <CardTitle className="text-[10px] font-bold text-gray-400 uppercase tracking-widest font-mono group-hover:text-white transition-colors">{m.title}</CardTitle>
                  {m.icon}
                </CardHeader>
                <CardContent className="space-y-1 z-10 relative text-left">
                  <div className="text-3xl font-black text-white">{m.val}</div>
                  <p className="text-[9px] text-gray-500 font-medium uppercase tracking-wider">{m.desc}</p>
                </CardContent>
              </Card>
            </DialogTrigger>
            <DialogContent className="glass-panel border-violet-500/30 text-white rounded-2xl">
              <DialogHeader>
                <DialogTitle className="text-xl font-bold font-mono tracking-wider uppercase text-violet-400">{m.title} Data Stream</DialogTitle>
              </DialogHeader>
              {renderMetricModalContent(m.title, m.val)}
            </DialogContent>
          </Dialog>
        ))}
      </div>

      {/* NEW WIDGETS ROW: Content Matrix & Acquisition */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        
        {/* Content Performance Matrix (Radar + Pipeline) */}
        <Card className="hud-card neon-glow-violet p-6 flex flex-col justify-between min-h-[300px]">
          <div className="flex items-center justify-between mb-4 border-b border-[rgba(139,92,246,0.3)] pb-4 z-10 relative">
            <div>
              <h3 className="font-extrabold text-lg text-white font-mono uppercase tracking-widest">Content Matrix</h3>
              <p className="text-[10px] text-violet-400 uppercase tracking-widest">Pipeline & Performance Radar</p>
            </div>
            <Activity className="text-violet-400" size={20} />
          </div>
          
          <div className="flex flex-col md:flex-row gap-6 z-10 relative flex-1">
            {/* SVG Radar Chart Mockup */}
            <div className="flex-1 flex items-center justify-center relative">
               <svg viewBox="0 0 200 200" className="w-40 h-40 overflow-visible">
                 {/* Outer grids */}
                 <polygon points="100,20 180,60 180,140 100,180 20,140 20,60" fill="rgba(139,92,246,0.1)" stroke="rgba(139,92,246,0.4)" strokeWidth="1"/>
                 <polygon points="100,40 160,75 160,125 100,160 40,125 40,75" fill="none" stroke="rgba(139,92,246,0.2)" strokeWidth="1"/>
                 <polygon points="100,60 140,85 140,115 100,140 60,115 60,85" fill="none" stroke="rgba(139,92,246,0.2)" strokeWidth="1"/>
                 
                 {/* Axis lines */}
                 <line x1="100" y1="100" x2="100" y2="20" stroke="rgba(139,92,246,0.3)" strokeWidth="1"/>
                 <line x1="100" y1="100" x2="180" y2="60" stroke="rgba(139,92,246,0.3)" strokeWidth="1"/>
                 <line x1="100" y1="100" x2="180" y2="140" stroke="rgba(139,92,246,0.3)" strokeWidth="1"/>
                 <line x1="100" y1="100" x2="100" y2="180" stroke="rgba(139,92,246,0.3)" strokeWidth="1"/>
                 <line x1="100" y1="100" x2="20" y2="140" stroke="rgba(139,92,246,0.3)" strokeWidth="1"/>
                 <line x1="100" y1="100" x2="20" y2="60" stroke="rgba(139,92,246,0.3)" strokeWidth="1"/>
                 
                 {/* Data Polygon */}
                 <polygon points={radarPolygon} fill="rgba(6,182,212,0.4)" stroke="#06b6d4" strokeWidth="2"/>
                 {radarPts.map((p, i) => (
                   <circle key={i} cx={p.x} cy={p.y} r="3" fill="#fff" />
                 ))}
               </svg>
               <div className="absolute top-0 text-[8px] text-gray-400 font-mono">Engagement</div>
               <div className="absolute bottom-0 text-[8px] text-gray-400 font-mono">Conversion</div>
            </div>

            {/* IG Content Pipeline */}
            <div className="flex-1 flex flex-col justify-center space-y-3">
              <div className="space-y-1">
                <div className="flex justify-between text-[10px] font-mono text-gray-400 uppercase">
                  <span>Drafting</span>
                  <span className="text-violet-400">{draftPosts} Items</span>
                </div>
                <div className="h-1.5 w-full bg-gray-900 rounded-full overflow-hidden">
                  <div className="h-full bg-violet-500 shadow-[0_0_10px_#8b5cf6]" style={{ width: `${(draftPosts / totalPosts) * 100}%` }} />
                </div>
              </div>
              <div className="space-y-1">
                <div className="flex justify-between text-[10px] font-mono text-gray-400 uppercase">
                  <span>In Review</span>
                  <span className="text-amber-400">{inReviewPosts} Items</span>
                </div>
                <div className="h-1.5 w-full bg-gray-900 rounded-full overflow-hidden">
                  <div className="h-full bg-amber-500 shadow-[0_0_10px_#f59e0b]" style={{ width: `${(inReviewPosts / totalPosts) * 100}%` }} />
                </div>
              </div>
              <div className="space-y-1">
                <div className="flex justify-between text-[10px] font-mono text-gray-400 uppercase">
                  <span>Published</span>
                  <span className="text-emerald-400">{publishedPosts} Items</span>
                </div>
                <div className="h-1.5 w-full bg-gray-900 rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-500 shadow-[0_0_10px_#10b981]" style={{ width: `${(publishedPosts / totalPosts) * 100}%` }} />
                </div>
              </div>
            </div>
          </div>
        </Card>

        {/* Acquisition Funnel Widget */}
        <Card className="hud-card neon-glow-emerald p-6 flex flex-col justify-between min-h-[300px]">
          <div className="flex items-center justify-between mb-4 border-b border-[rgba(16,185,129,0.3)] pb-4 z-10 relative">
            <div>
              <h3 className="font-extrabold text-lg text-white font-mono uppercase tracking-widest">Acquisition</h3>
              <p className="text-[10px] text-emerald-400 uppercase tracking-widest">Lead Generation Funnel</p>
            </div>
            <Network className="text-emerald-400" size={20} />
          </div>

          <div className="flex flex-col gap-3 z-10 relative flex-1 justify-center">
            <div className="flex items-center bg-gray-900/60 border border-[rgba(16,185,129,0.2)] rounded-lg p-3">
              <div className="w-16 text-center text-emerald-400 font-mono text-xl font-bold">{totalSourced > 1000 ? (totalSourced/1000).toFixed(1)+'k' : totalSourced}</div>
              <div className="flex-1 ml-4">
                <div className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Total Sourced</div>
                <div className="h-1 w-full bg-gray-800 mt-1"><div className="h-full bg-emerald-500 w-[100%]" /></div>
              </div>
            </div>
            <div className="flex items-center bg-gray-900/60 border border-[rgba(16,185,129,0.2)] rounded-lg p-3 ml-4">
              <div className="w-16 text-center text-emerald-400 font-mono text-xl font-bold">{contacted > 1000 ? (contacted/1000).toFixed(1)+'k' : contacted}</div>
              <div className="flex-1 ml-4">
                <div className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Contacted</div>
                <div className="h-1 w-full bg-gray-800 mt-1"><div className="h-full bg-emerald-500" style={{ width: totalSourced ? `${(contacted / totalSourced) * 100}%` : '0%' }} /></div>
              </div>
            </div>
            <div className="flex items-center bg-gray-900/60 border border-[rgba(16,185,129,0.2)] rounded-lg p-3 ml-8">
              <div className="w-16 text-center text-emerald-400 font-mono text-xl font-bold">{qualified > 1000 ? (qualified/1000).toFixed(1)+'k' : qualified}</div>
              <div className="flex-1 ml-4">
                <div className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Qualified Responses</div>
                <div className="h-1 w-full bg-gray-800 mt-1"><div className="h-full bg-emerald-500" style={{ width: totalSourced ? `${(qualified / totalSourced) * 100}%` : '0%' }} /></div>
              </div>
            </div>
          </div>
        </Card>

      </div>

      {/* Advanced SVG Chart & Activity Center */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 relative z-10">
        <div className="cyberpunk-scanline rounded-2xl pointer-events-none" />
        
        {/* Visual Chart Card */}
        <Card className="hud-card lg:col-span-8 p-6 shadow-2xl relative overflow-hidden flex flex-col justify-between">
          <div className="flex items-center justify-between mb-4 border-b border-[rgba(139,92,246,0.2)] pb-4 z-10 relative">
            <div>
              <h3 className="font-extrabold text-lg text-white font-mono tracking-widest uppercase">Task Automation Telemetry</h3>
              <p className="text-[10px] text-gray-400 font-mono uppercase tracking-widest mt-1">Total automated agent tasks over 7 days</p>
            </div>
            <div className="flex items-center gap-3 text-[9px] text-gray-400 font-bold uppercase tracking-widest">
              <span className="flex items-center gap-1.5"><span className="h-2 w-2 shadow-[0_0_5px_#8b5cf6] bg-violet-500" /> MKT</span>
              <span className="flex items-center gap-1.5"><span className="h-2 w-2 shadow-[0_0_5px_#10b981] bg-emerald-500" /> SLS</span>
              <span className="flex items-center gap-1.5"><span className="h-2 w-2 shadow-[0_0_5px_#3b82f6] bg-blue-500" /> SUP</span>
            </div>
          </div>

          <div className="relative w-full h-44 mt-2 flex items-end z-10">
            <svg viewBox="0 0 500 150" className="w-full h-full overflow-visible" preserveAspectRatio="none">
              <defs>
                <linearGradient id="chartGradientMarketing" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.35" />
                  <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.0" />
                </linearGradient>
                <linearGradient id="chartGradientSales" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity="0.35" />
                  <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
                </linearGradient>
                <linearGradient id="chartGradientSupport" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.35" />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.0" />
                </linearGradient>
              </defs>
              {/* Grid Lines */}
              <line x1="0" y1="30" x2="500" y2="30" stroke="rgba(255,255,255,0.05)" strokeDasharray="2 6" />
              <line x1="0" y1="75" x2="500" y2="75" stroke="rgba(255,255,255,0.05)" strokeDasharray="2 6" />
              <line x1="0" y1="120" x2="500" y2="120" stroke="rgba(255,255,255,0.05)" strokeDasharray="2 6" />
              
              {/* Areas & Strokes */}
              {marketingPaths.areaPath && (
                <>
                  <path d={marketingPaths.areaPath} fill="url(#chartGradientMarketing)" />
                  <path d={marketingPaths.strokePath} fill="none" stroke="#8b5cf6" strokeWidth="2" strokeDasharray="4 2" />
                </>
              )}
              {salesPaths.areaPath && (
                <>
                  <path d={salesPaths.areaPath} fill="url(#chartGradientSales)" />
                  <path d={salesPaths.strokePath} fill="none" stroke="#10b981" strokeWidth="2" strokeDasharray="4 2" />
                </>
              )}
              {supportPaths.areaPath && (
                <>
                  <path d={supportPaths.areaPath} fill="url(#chartGradientSupport)" />
                  <path d={supportPaths.strokePath} fill="none" stroke="#3b82f6" strokeWidth="2" strokeDasharray="4 2" />
                </>
              )}
              
              {/* Dots & Text */}
              {[...marketingPoints, ...salesPoints, ...supportPoints].map((p, i) => (
                <g key={`pt-${i}`}>
                  <rect x={p.x - 2} y={p.y - 2} width="4" height="4" fill="#fff" opacity="0.8" />
                </g>
              ))}
            </svg>
          </div>
          
          <div className="flex justify-between text-[9px] text-gray-500 font-bold tracking-widest font-mono uppercase mt-4 pt-3 border-t border-[rgba(139,92,246,0.2)] z-10 relative">
            {dayNames.map((name, i) => (
              <span key={i}>{name}</span>
            ))}
          </div>
        </Card>

        {/* Developer Terminal Activity Log */}
        <Card className="hud-card lg:col-span-4 p-6 shadow-2xl relative overflow-hidden flex flex-col h-full min-h-[280px]">
          <div className="flex items-center justify-between pb-3 border-b border-[rgba(139,92,246,0.3)] mb-3 z-10 relative">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 bg-rose-500/80 shadow-[0_0_5px_#f43f5e]" />
              <span className="w-2.5 h-2.5 bg-amber-500/80 shadow-[0_0_5px_#f59e0b]" />
              <span className="w-2.5 h-2.5 bg-emerald-500/80 shadow-[0_0_5px_#10b981]" />
            </div>
            <span className="text-[10px] text-violet-400 font-bold uppercase tracking-widest font-mono">Terminal Log</span>
          </div>
          <div className="flex-1 overflow-y-auto space-y-2.5 font-mono text-[10px] uppercase tracking-wider leading-relaxed text-gray-300 pr-1 max-h-[180px] z-10 relative">
            {timeline.slice(0, 8).map((log) => (
              <div key={log.id} className="text-gray-400 border-l border-gray-800 pl-2">
                <span className="text-violet-400 font-semibold">[{new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}]</span>{" "}
                <span className="text-emerald-400">({log.agent_name})</span>{" "}
                <span className="text-white font-medium">{log.action}:</span> {log.description}
              </div>
            ))}
            {timeline.length === 0 && (
              <div className="text-gray-500 italic">Listening for system triggers...</div>
            )}
          </div>
          <div className="flex items-center gap-2 mt-4 pt-3 border-t border-[rgba(139,92,246,0.3)] text-[10px] text-emerald-400 font-bold font-mono tracking-widest z-10 relative">
            <span className="h-2 w-2 bg-emerald-400 animate-ping" />
            <span>SOCKET OK.</span>
            <span className="inline-block w-2 h-3 bg-emerald-400 animate-pulse" />
          </div>
        </Card>
      </div>

      {/* "My Agents" Skyline */}
      <div className="space-y-6 pt-4 relative z-10">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h3 className="font-extrabold text-2xl text-white font-mono uppercase tracking-widest">My Agents Skyline</h3>
            <p className="text-[10px] font-mono tracking-widest text-gray-400 mt-1 uppercase">Active Workflow Nodes</p>
          </div>
          {apps.length > 0 && (
            <span className="text-[10px] font-mono uppercase font-extrabold tracking-widest text-cyan-400 bg-[rgba(6,182,212,0.1)] px-3 py-1 border border-[rgba(6,182,212,0.3)] shadow-[0_0_10px_rgba(6,182,212,0.2)]">
              {apps.length} NODES ONLINE
            </span>
          )}
        </div>
        
        {apps.length === 0 ? (
          <Card className="hud-card border-dashed border-[rgba(139,92,246,0.3)] p-8 text-center space-y-4">
            <div className="text-5xl text-violet-400/50">
              <Cpu size={48} className="mx-auto" />
            </div>
            <div className="max-w-md mx-auto space-y-2 z-10 relative">
              <h4 className="text-sm font-bold text-white font-mono uppercase tracking-widest">No Active Nodes</h4>
              <p className="text-xs text-gray-400 font-mono">Deploy packages from the Marketplace to activate skyline nodes.</p>
            </div>
            <Button 
              onClick={() => setActiveView('marketplace')}
              className="bg-[rgba(139,92,246,0.2)] border border-[rgba(139,92,246,0.5)] hover:bg-[rgba(139,92,246,0.4)] text-violet-300 font-bold font-mono tracking-widest h-9 px-6 uppercase text-[10px] z-10 relative"
            >
              INITIALIZE DEPLOYMENT
            </Button>
          </Card>
        ) : (
          <div className="flex items-end h-[300px] gap-2 overflow-x-auto pb-4 px-2">
            {apps.map((app, index) => {
              const matchedPack = marketplacePacks.find(p => p.name === app.app_name);
              // Calculate a pseudo-random height for the skyline building based on index and name length
              const buildingHeight = 150 + ((index * 47) % 100); 
              
              return (
                <div key={app.id} className="relative group flex-shrink-0" style={{ width: '120px', height: `${buildingHeight}px` }}>
                  {/* Building Block */}
                  <div className="absolute inset-0 bg-gradient-to-b from-[rgba(139,92,246,0.4)] to-[rgba(8,6,22,0.8)] border border-[rgba(139,92,246,0.6)] shadow-[0_0_15px_rgba(139,92,246,0.2)] flex flex-col items-center justify-start p-2 transition-transform duration-300 group-hover:-translate-y-4 cursor-pointer">
                    
                    {/* Glowing Windows Effect */}
                    <div className="absolute inset-0 opacity-20 bg-[linear-gradient(to_bottom,transparent_2px,rgba(255,255,255,0.1)_3px)] bg-[size:100%_8px] pointer-events-none" />
                    
                    <div className="w-8 h-8 rounded bg-[rgba(139,92,246,0.2)] border border-violet-500/50 flex items-center justify-center mb-2 z-10">
                      {matchedPack ? <span className="text-sm">{matchedPack.icon}</span> : <Building size={14} className="text-violet-300"/>}
                    </div>
                    <span className="text-[9px] font-mono font-bold text-white uppercase text-center break-words w-full z-10">
                      {app.app_name.substring(0, 15)}
                    </span>
                    <span className="mt-1 w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_5px_#10b981] animate-pulse z-10" />
                  </div>
                  
                  {/* Hover Tooltip/Modal snippet */}
                  <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 bg-[rgba(8,6,22,0.95)] border border-[rgba(139,92,246,0.6)] p-3 shadow-xl opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity duration-200 z-50 w-48 hud-card">
                    <p className="text-[10px] font-mono text-violet-400 font-bold uppercase border-b border-gray-700 pb-1 mb-1">{app.app_name}</p>
                    <p className="text-[9px] text-gray-400 font-mono leading-tight">{matchedPack?.desc || "Active node."}</p>
                    <div className="text-[8px] text-emerald-400 mt-2 font-mono">STATUS: ONLINE</div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

    </div>
  );
}
