'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { DollarSign, Cpu, TrendingUp, BarChart4, BarChart3, Loader2, Bot, Plus, Zap, Clock } from 'lucide-react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

interface AIOptimizationViewProps {
  token: string | null;
  API_URL: string;
  fetchWithAuth: (url: string, options?: any) => Promise<Response>;
  fetchData: () => Promise<void>;
  metrics: any;
}

export default function AIOptimizationView({
  token,
  API_URL,
  fetchWithAuth,
  fetchData,
  metrics,
}: AIOptimizationViewProps) {
  // Optimization states relocated here
  const [optimizationMetrics, setOptimizationMetrics] = useState<any>(null);
  const [optimizationLoading, setOptimizationLoading] = useState(false);
  const [tasksPerDay, setTasksPerDay] = useState(60);
  const [hourlyRate, setHourlyRate] = useState(35);
  const [activePreviewAgent, setActivePreviewAgent] = useState('marketing');

  useEffect(() => {
    if (token) {
      fetchOptimizationMetrics();
    }
  }, [token]);

  // AI Optimization functions
    const fetchOptimizationMetrics = async () => {
    if (!token) return;
    setOptimizationLoading(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/llm/optimization-metrics`);
      if (res.ok) {
        const data = await res.json();
        setOptimizationMetrics(data);
      }
    } catch (e) {
      console.error("Failed to fetch optimization metrics:", e);
    } finally {
      setOptimizationLoading(false);
    }
  };



  return (
    <div className="space-y-8 max-w-7xl mx-auto animate-in fade-in duration-300">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <h1 className="text-4xl font-extrabold text-white tracking-tight flex items-center gap-2">
                    <DollarSign className="text-emerald-400 h-8 w-8 animate-pulse" /> AI Cost Control Center
                  </h1>
                  <p className="text-gray-400 mt-1">Standardise provider APIs, optimize token usage, route workloads dynamically, and track latency savings.</p>
                </div>
                <div className="flex items-center gap-2 bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.06)] px-4 py-2 rounded-xl text-xs text-gray-400 font-semibold shadow-inner">
                  <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                  <span>AI Cost Optimization Layer Active</span>
                </div>
              </div>

              {/* Top stats */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <Card className="glass-panel border-emerald-500/20 relative overflow-hidden transition-all duration-300 hover:scale-[1.03] rounded-2xl shadow-lg">
                  <div className="absolute top-0 left-0 w-1.5 h-full bg-emerald-500" />
                  <CardHeader className="pb-2 flex flex-row items-center justify-between">
                    <CardTitle className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Total Optimised Spend</CardTitle>
                    <DollarSign className="h-4 w-4 text-emerald-450" />
                  </CardHeader>
                  <CardContent className="space-y-1">
                    <div className="text-3xl font-black text-white">${optimizationMetrics?.total_spend?.toFixed(4) || "0.0000"}</div>
                    <p className="text-[10px] text-gray-500 font-medium">{optimizationMetrics?.active_providers?.length || 0} active providers connected</p>
                  </CardContent>
                </Card>

                <Card className="glass-panel border-violet-500/20 relative overflow-hidden transition-all duration-300 hover:scale-[1.03] rounded-2xl shadow-lg">
                  <div className="absolute top-0 left-0 w-1.5 h-full bg-violet-500" />
                  <CardHeader className="pb-2 flex flex-row items-center justify-between">
                    <CardTitle className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Universal Cache Hit Rate</CardTitle>
                    <Zap className="h-4 w-4 text-violet-400" />
                  </CardHeader>
                  <CardContent className="space-y-1">
                    <div className="text-3xl font-black text-white">{optimizationMetrics?.cache_metrics?.hit_rate || 0}%</div>
                    <p className="text-[10px] text-gray-500 font-medium">{optimizationMetrics?.cache_metrics?.hits || 0} hits out of {optimizationMetrics?.cache_metrics?.total_calls || 0} requests</p>
                  </CardContent>
                </Card>

                <Card className="glass-panel border-blue-500/20 relative overflow-hidden transition-all duration-300 hover:scale-[1.03] rounded-2xl shadow-lg">
                  <div className="absolute top-0 left-0 w-1.5 h-full bg-blue-500" />
                  <CardHeader className="pb-2 flex flex-row items-center justify-between">
                    <CardTitle className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Latency Saved</CardTitle>
                    <Clock className="h-4 w-4 text-blue-400" />
                  </CardHeader>
                  <CardContent className="space-y-1">
                    <div className="text-3xl font-black text-white">{optimizationMetrics?.cache_metrics?.latency_saved || 0}s</div>
                    <p className="text-[10px] text-gray-500 font-medium">Bypassed LLM processing delays</p>
                  </CardContent>
                </Card>

                <Card className="glass-panel border-amber-500/20 relative overflow-hidden transition-all duration-300 hover:scale-[1.03] rounded-2xl shadow-lg">
                  <div className="absolute top-0 left-0 w-1.5 h-full bg-amber-500" />
                  <CardHeader className="pb-2 flex flex-row items-center justify-between">
                    <CardTitle className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Estimated Cost Savings</CardTitle>
                    <BarChart3 className="h-4 w-4 text-amber-400" />
                  </CardHeader>
                  <CardContent className="space-y-1">
                    <div className="text-3xl font-black text-emerald-400">+${((optimizationMetrics?.cache_metrics?.savings || 0) + (optimizationMetrics?.batch_metrics?.async_savings || 0)).toFixed(4)}</div>
                    <p className="text-[10px] text-gray-500 font-medium">From cache hits and batch runs</p>
                  </CardContent>
                </Card>
              </div>

              {/* Providers Status & Telemetry */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
                <Card className="lg:col-span-8 glass-panel border-[rgba(255,255,255,0.06)] rounded-3xl p-6 shadow-2xl relative overflow-hidden flex flex-col justify-between">
                  <div className="flex items-center justify-between mb-4 border-b border-gray-800 pb-4">
                    <div>
                      <h3 className="font-extrabold text-lg text-white">Universal AI Providers Gateway</h3>
                      <p className="text-xs text-gray-400">Standardised provider telemetry, average latency, and configuration state.</p>
                    </div>
                    <span className="text-[10px] text-violet-400 font-bold uppercase tracking-wider font-mono">Dynamic Fallback Active</span>
                  </div>

                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader className="bg-gray-950/40 border-b border-gray-800">
                        <TableRow className="border-gray-800 hover:bg-transparent">
                          <TableHead className="text-gray-400 font-bold text-xs p-4">Provider</TableHead>
                          <TableHead className="text-gray-400 font-bold text-xs p-4">Status</TableHead>
                          <TableHead className="text-gray-400 font-bold text-xs p-4">Avg Latency</TableHead>
                          <TableHead className="text-gray-400 font-bold text-xs p-4">Uptime / Health</TableHead>
                          <TableHead className="text-gray-400 font-bold text-xs p-4 text-right">Failover Count</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody className="divide-y divide-gray-800">
                        {Object.entries(optimizationMetrics?.provider_metrics || {}).map(([p, metrics]: [string, any]) => {
                          const isConfigured = optimizationMetrics?.active_providers?.includes(p.toLowerCase()) || p === "mock";
                          return (
                            <TableRow key={p} className="border-gray-800 hover:bg-gray-900/20">
                              <TableCell className="p-4 whitespace-nowrap">
                                <div className="flex items-center gap-2">
                                  <div className="bg-gradient-to-tr from-violet-600 to-indigo-600 p-1 rounded text-white text-[10px] font-bold uppercase w-16 text-center">
                                    {p}
                                  </div>
                                  <span className="text-xs text-white capitalize font-semibold">{p}</span>
                                </div>
                              </TableCell>
                              <TableCell className="p-4">
                                <span className={`inline-flex items-center gap-1 border px-2 py-0.5 rounded text-[10px] font-bold ${
                                  isConfigured 
                                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                                    : 'bg-gray-800/60 text-gray-500 border-gray-700/60'
                                }`}>
                                  {isConfigured ? "● Connected" : "○ Not Configured"}
                                </span>
                              </TableCell>
                              <TableCell className="p-4 text-xs font-mono text-gray-300">
                                {isConfigured ? `${metrics.avg_latency || "0.0"}s` : "N/A"}
                              </TableCell>
                              <TableCell className="p-4 text-xs font-semibold text-gray-300">
                                {metrics.uptime}%
                              </TableCell>
                              <TableCell className="p-4 text-right text-xs font-mono text-rose-400">
                                {metrics.failed_calls + metrics.failover_calls}
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </div>
                </Card>

                {/* Cache Metrics */}
                <Card className="lg:col-span-4 glass-panel border-[rgba(255,255,255,0.06)] rounded-3xl p-6 shadow-2xl relative overflow-hidden flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
                      <h3 className="font-extrabold text-lg text-white">Universal Cache</h3>
                      <Zap className="text-violet-400 h-5 w-5" />
                    </div>

                    <div className="space-y-4">
                      <div>
                        <div className="flex justify-between text-xs font-semibold text-gray-400 mb-1.5">
                          <span>Prompt Hit Rate</span>
                          <span className="text-violet-400 font-bold">{optimizationMetrics?.cache_metrics?.hit_rate || 0}%</span>
                        </div>
                        <div className="w-full bg-gray-800 h-2 rounded-full overflow-hidden">
                          <div 
                            className="bg-gradient-to-r from-violet-600 to-indigo-600 h-full rounded-full transition-all duration-500"
                            style={{ width: `${optimizationMetrics?.cache_metrics?.hit_rate || 0}%` }}
                          />
                        </div>
                      </div>

                      <div className="bg-[rgba(0,0,0,0.15)] border border-gray-800 p-4 rounded-xl space-y-3 shadow-inner">
                        <div className="flex justify-between text-xs">
                          <span className="text-gray-400">Cache Hits Count:</span>
                          <span className="font-mono text-white font-bold">{optimizationMetrics?.cache_metrics?.hits || 0}</span>
                        </div>
                        <div className="flex justify-between text-xs">
                          <span className="text-gray-400">Token Reuse (Saved):</span>
                          <span className="font-mono text-emerald-400 font-bold">{(optimizationMetrics?.cache_metrics?.token_reuse || 0).toLocaleString()}</span>
                        </div>
                        <div className="flex justify-between text-xs">
                          <span className="text-gray-400">Cache Caching Layer:</span>
                          <span className="text-violet-400 font-bold font-mono">Redis DB 1</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="text-[11px] text-violet-300/80 bg-violet-500/5 border border-violet-500/10 p-3 rounded-lg flex items-start gap-2 mt-4">
                    <Zap size={14} className="mt-0.5 flex-shrink-0" />
                    <p>
                      <strong>Optimize logic:</strong> Prompts matching Global, Department or Workflow templates bypass LLM endpoints. Saves 100% tokens and execution lag.
                    </p>
                  </div>
                </Card>
              </div>

              {/* Workload Routing & Batching */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
                {/* Routing Distribution */}
                <Card className="lg:col-span-6 glass-panel border-[rgba(255,255,255,0.06)] rounded-3xl p-6 shadow-2xl relative overflow-hidden">
                  <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
                    <h3 className="font-extrabold text-lg text-white">Dynamic Department Workload Routing</h3>
                    <span className="text-[10px] text-emerald-400 font-bold uppercase tracking-wider font-mono">Routing Analytics</span>
                  </div>

                  <div className="space-y-4">
                    {Object.entries(optimizationMetrics?.routing_analytics || {}).map(([dept, providers]: [string, any]) => {
                      const totalDeptCalls = Object.values(providers).reduce((a: any, b: any) => a + b, 0) as number;
                      return (
                        <div key={dept} className="space-y-1.5">
                          <div className="flex justify-between text-xs">
                            <span className="font-bold text-white capitalize">{dept} tasks</span>
                            <span className="text-gray-400 text-[10px]">{totalDeptCalls} requests</span>
                          </div>
                          
                          {totalDeptCalls > 0 ? (
                            <div className="w-full bg-gray-800 h-3 rounded-md overflow-hidden flex">
                              {Object.entries(providers).map(([provider, count]: [string, any]) => {
                                const pct = (count / totalDeptCalls) * 100;
                                const colors: any = {
                                  openrouter: "bg-sky-500",
                                  together: "bg-pink-500",
                                  openai: "bg-emerald-500",
                                  anthropic: "bg-violet-600",
                                  gemini: "bg-blue-500",
                                  groq: "bg-orange-500",
                                  grok: "bg-purple-600",
                                  local: "bg-teal-500",
                                  mock: "bg-gray-600"
                                };
                                const bgClass = colors[provider.toLowerCase()] || "bg-indigo-600";
                                return (
                                  <div 
                                    key={provider} 
                                    className={`${bgClass} h-full transition-all`}
                                    style={{ width: `${pct}%` }}
                                    title={`${provider}: ${pct.toFixed(0)}%`}
                                  />
                                );
                              })}
                            </div>
                          ) : (
                            <div className="w-full bg-gray-800 h-3 rounded-md text-[9px] text-center text-gray-500 font-bold flex items-center justify-center">
                              No calls routed yet
                            </div>
                          )}

                          {/* Percentages row */}
                          <div className="flex gap-2.5 flex-wrap text-[9px] font-semibold text-gray-400 mt-1">
                            {Object.entries(providers).map(([provider, count]: [string, any]) => {
                              const pct = ((count / totalDeptCalls) * 100).toFixed(0);
                              return (
                                <span key={provider} className="flex items-center gap-1">
                                  <span className={`h-1.5 w-1.5 rounded-full ${
                                    provider === 'openrouter' ? 'bg-sky-500' :
                                    provider === 'together' ? 'bg-pink-500' :
                                    provider === 'openai' ? 'bg-emerald-500' :
                                    provider === 'anthropic' ? 'bg-violet-600' :
                                    provider === 'gemini' ? 'bg-blue-500' :
                                    provider === 'groq' ? 'bg-orange-500' :
                                    provider === 'grok' ? 'bg-purple-600' : 'bg-gray-450'
                                  }`} />
                                  <span className="capitalize text-[10px]">{provider}</span> ({pct}%)
                                </span>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </Card>

                {/* Batch Jobs */}
                <Card className="lg:col-span-6 glass-panel border-[rgba(255,255,255,0.06)] rounded-3xl p-6 shadow-2xl relative overflow-hidden flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
                      <h3 className="font-extrabold text-lg text-white">Batch Orchestration System</h3>
                      <span className="text-[10px] text-amber-400 font-bold uppercase tracking-wider font-mono">Async Batch Telemetry</span>
                    </div>

                    <div className="grid grid-cols-3 gap-4 mb-6">
                      <div className="p-3 border border-gray-800 rounded-xl bg-gray-950/20 text-center shadow-inner">
                        <span className="text-[9px] font-bold text-gray-500 uppercase tracking-wider block">Jobs Processed</span>
                        <div className="text-xl font-black text-white mt-1">{optimizationMetrics?.batch_metrics?.total_jobs || 0}</div>
                      </div>
                      <div className="p-3 border border-gray-800 rounded-xl bg-gray-950/20 text-center shadow-inner">
                        <span className="text-[9px] font-bold text-gray-500 uppercase tracking-wider block">Tasks Completed</span>
                        <div className="text-xl font-black text-white mt-1">{optimizationMetrics?.batch_metrics?.total_tasks_processed || 0}</div>
                      </div>
                      <div className="p-3 border border-gray-800 rounded-xl bg-gray-950/20 text-center shadow-inner bg-emerald-500/5 border-emerald-500/10">
                        <span className="text-[9px] font-bold text-emerald-450 uppercase tracking-wider block">Batch Savings</span>
                        <div className="text-xl font-black text-emerald-400 mt-1">${optimizationMetrics?.batch_metrics?.async_savings?.toFixed(2) || "0.00"}</div>
                      </div>
                    </div>

                    <div className="bg-[rgba(0,0,0,0.15)] border border-gray-800 p-4 rounded-xl space-y-3 shadow-inner">
                      <div className="flex justify-between text-xs">
                        <span className="text-gray-400">Processing Jobs:</span>
                        <span className="font-mono text-white font-bold flex items-center gap-1.5">
                          {optimizationMetrics?.batch_metrics?.processing_jobs || 0}
                          {optimizationMetrics?.batch_metrics?.processing_jobs > 0 && (
                            <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-ping" />
                          )}
                        </span>
                      </div>
                      <div className="flex justify-between text-xs">
                        <span className="text-gray-400">Completed Jobs:</span>
                        <span className="font-mono text-white font-bold">{optimizationMetrics?.batch_metrics?.completed_jobs || 0}</span>
                      </div>
                      <div className="flex justify-between text-xs">
                        <span className="text-gray-400">Failed Jobs:</span>
                        <span className="font-mono text-rose-450 font-bold">{optimizationMetrics?.batch_metrics?.failed_jobs || 0}</span>
                      </div>
                    </div>
                  </div>

                  <div className="text-[11px] text-amber-300/80 bg-amber-500/5 border border-amber-500/10 p-3 rounded-lg flex items-start gap-2 mt-4">
                    <Clock size={14} className="mt-0.5 flex-shrink-0" />
                    <p>
                      <strong>Batch API integration:</strong> Supports native API batch submission (e.g. OpenAI/Anthropic 50% discount) or falls back to Celery background processing.
                    </p>
                  </div>
                </Card>
              </div>
            </div>
  );
}
