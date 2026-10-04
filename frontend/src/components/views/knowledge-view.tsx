'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  FileText, Search, Trash2, Upload, Loader2, Globe, RefreshCw,
  Building2, Sparkles, CheckCircle2, XCircle, AlertTriangle,
  BookOpen, Cpu, Brain, Plus, ChevronRight, Clock, BarChart3,
  FileImage, FileSpreadsheet, Presentation, X, Link2, Zap,
  TrendingUp, Database, Info
} from 'lucide-react';

interface KnowledgeViewProps {
  token: string | null;
  API_URL: string;
  fetchWithAuth: (url: string, options?: any) => Promise<Response>;
  fetchData: () => Promise<void>;
  knowledge: any[];
}

// ── Toast Notification System ──────────────────────────────────────────────
type ToastType = 'success' | 'error' | 'warning' | 'info';
interface Toast { id: string; type: ToastType; title: string; message?: string; }

function ToastContainer({ toasts, dismiss }: { toasts: Toast[]; dismiss: (id: string) => void }) {
  return (
    <div className="fixed top-5 right-5 z-[999] flex flex-col gap-3 pointer-events-none" style={{ maxWidth: 380 }}>
      {toasts.map(t => (
        <div
          key={t.id}
          className={`pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-2xl shadow-2xl border backdrop-blur-xl transition-all duration-300 animate-in slide-in-from-right-8 ${
            t.type === 'success' ? 'bg-emerald-950/90 border-emerald-700/50 text-emerald-100' :
            t.type === 'error'   ? 'bg-rose-950/90 border-rose-700/50 text-rose-100' :
            t.type === 'warning' ? 'bg-amber-950/90 border-amber-700/50 text-amber-100' :
                                   'bg-gray-900/95 border-gray-700/50 text-gray-100'
          }`}
        >
          <div className="mt-0.5 flex-shrink-0">
            {t.type === 'success' && <CheckCircle2 size={16} className="text-emerald-400" />}
            {t.type === 'error'   && <XCircle size={16} className="text-rose-400" />}
            {t.type === 'warning' && <AlertTriangle size={16} className="text-amber-400" />}
            {t.type === 'info'    && <Info size={16} className="text-blue-400" />}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-bold">{t.title}</p>
            {t.message && <p className="text-[11px] opacity-80 mt-0.5 leading-snug">{t.message}</p>}
          </div>
          <button onClick={() => dismiss(t.id)} className="flex-shrink-0 opacity-50 hover:opacity-100 mt-0.5">
            <X size={13} />
          </button>
        </div>
      ))}
    </div>
  );
}

// ── File type helper ───────────────────────────────────────────────────────
function FileIcon({ name, className = '' }: { name: string; className?: string }) {
  const ext = name.split('.').pop()?.toLowerCase() ?? '';
  if (['png', 'jpg', 'jpeg', 'webp', 'bmp', 'gif', 'tif'].includes(ext))
    return <FileImage size={14} className={className} />;
  if (['xlsx', 'xls', 'csv', 'tsv'].includes(ext))
    return <FileSpreadsheet size={14} className={className} />;
  if (['pptx', 'ppt'].includes(ext))
    return <Presentation size={14} className={className} />;
  return <FileText size={14} className={className} />;
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

function timeSince(dateStr?: string) {
  if (!dateStr) return 'Never';
  const diff = Date.now() - new Date(dateStr).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'Just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

// ── Stats Bar ──────────────────────────────────────────────────────────────
function StatsBar({ knowledge, sources }: { knowledge: any[]; sources: any[] }) {
  const fileCount = knowledge.filter(d => d.source_type === 'file' || d.content?.startsWith('Source Document:')).length;
  const webCount  = knowledge.filter(d => d.source_type === 'web').length;
  const dirCount  = knowledge.filter(d => d.doc_type === 'Prompt Directives').length;
  const textCount = knowledge.length - fileCount - webCount - dirCount;
  const totalPages = sources.reduce((acc, s) => acc + (s.pages_indexed || 0), 0);

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 flex-shrink-0">
      {[
        { label: 'Total Documents', value: knowledge.length, icon: Database, color: 'violet' },
        { label: 'Web Pages Indexed', value: totalPages, icon: Globe, color: 'emerald' },
        { label: 'AI Directives', value: dirCount, icon: Brain, color: 'amber' },
        { label: 'Active Sources', value: sources.length, icon: TrendingUp, color: 'sky' },
      ].map(stat => (
        <div key={stat.label} className={`flex items-center gap-3 p-3 rounded-2xl border bg-${stat.color}-950/20 border-${stat.color}-900/30`}>
          <div className={`p-2 rounded-xl bg-${stat.color}-500/10`}>
            <stat.icon size={14} className={`text-${stat.color}-400`} />
          </div>
          <div>
            <p className="text-lg font-extrabold text-white leading-none">{stat.value}</p>
            <p className="text-[10px] text-gray-500 mt-0.5 leading-none">{stat.label}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Document Row ───────────────────────────────────────────────────────────
function DocRow({ doc, onDelete }: { doc: any; onDelete: () => void }) {
  const isWeb  = doc.source_type === 'web' || (doc.source_url && doc.source_url.startsWith('http'));
  const isFile = doc.source_type === 'file' || doc.content?.startsWith('Source Document:');
  const isDir  = doc.doc_type === 'Prompt Directives';

  const title = isWeb
    ? (doc.source_url || 'Web Page')
    : isFile
      ? doc.content?.match(/^Source Document: ([^\n]+)/)?.[1] || doc.source_url || 'Uploaded File'
      : doc.doc_type;

  const badgeMap: Record<string, { label: string; cls: string }> = {
    directive: { label: 'AI Directive', cls: 'bg-amber-950/30 border-amber-800/40 text-amber-400' },
    web: { label: 'Web', cls: 'bg-emerald-950/30 border-emerald-800/40 text-emerald-400' },
    file: { label: 'File', cls: 'bg-violet-950/30 border-violet-800/40 text-violet-400' },
    text: { label: 'Text', cls: 'bg-blue-950/30 border-blue-800/40 text-blue-400' },
  };
  const badge = isDir ? badgeMap.directive : isWeb ? badgeMap.web : isFile ? badgeMap.file : badgeMap.text;

  const qual = doc.quality_score != null ? Math.round(doc.quality_score * 100) : null;

  return (
    <div className="group flex items-center gap-3 p-3 bg-gray-900/30 hover:bg-gray-800/50 border border-gray-800/40 hover:border-gray-700/60 rounded-xl transition-all duration-150 cursor-default">
      {/* Icon */}
      <div className={`flex-shrink-0 p-1.5 rounded-lg ${
        isDir ? 'bg-amber-500/10 text-amber-400' : isWeb ? 'bg-emerald-500/10 text-emerald-400' : 'bg-violet-500/10 text-violet-400'
      }`}>
        {isDir ? <Cpu size={13} /> : isWeb ? <Globe size={13} /> : <FileText size={13} />}
      </div>

      {/* Main info */}
      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold text-white truncate max-w-[220px]" title={title}>{title}</p>
        <div className="flex items-center gap-1.5 mt-1 flex-wrap">
          <span className="text-[9px] px-1.5 py-0.5 rounded-md bg-gray-950 border border-gray-800/60 text-gray-500 font-medium">{doc.department}</span>
          <span className={`text-[9px] px-1.5 py-0.5 rounded-md border font-bold ${badge.cls}`}>{badge.label}</span>
          {qual !== null && (
            <span className={`text-[9px] font-medium ${qual >= 80 ? 'text-emerald-500' : qual >= 50 ? 'text-amber-500' : 'text-rose-500'}`}>
              {qual}% quality
            </span>
          )}
        </div>
      </div>

      {/* Delete */}
      <button
        onClick={onDelete}
        className="opacity-0 group-hover:opacity-100 flex-shrink-0 p-1.5 rounded-lg text-gray-600 hover:text-rose-400 hover:bg-rose-950/20 transition-all"
        title="Delete document"
      >
        <Trash2 size={12} />
      </button>
    </div>
  );
}

// ── Source Row ─────────────────────────────────────────────────────────────
function SourceRow({ source, onRecrawl, onDelete }: { source: any; onRecrawl: () => void; onDelete: () => void }) {
  const statusMap: Record<string, { cls: string; dot: string }> = {
    completed: { cls: 'text-emerald-400', dot: 'bg-emerald-400' },
    running:   { cls: 'text-blue-400',    dot: 'bg-blue-400 animate-pulse' },
    failed:    { cls: 'text-rose-400',    dot: 'bg-rose-400' },
    idle:      { cls: 'text-gray-400',    dot: 'bg-gray-600' },
  };
  const s = statusMap[source.last_status] ?? statusMap.idle;

  return (
    <div className="flex items-center gap-3 p-3 bg-gray-950/50 border border-gray-800/50 rounded-xl hover:border-gray-700/60 transition-all">
      <Globe size={13} className="flex-shrink-0 text-emerald-400" />
      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold text-white truncate" title={source.url}>{source.url}</p>
        <div className="flex items-center gap-2 mt-0.5 text-[10px] text-gray-500">
          <span className="text-emerald-400 font-bold">{source.pages_indexed || 0} pages</span>
          <span>·</span>
          <span className="capitalize">{source.schedule}</span>
          <span>·</span>
          <span className={`flex items-center gap-1 ${s.cls}`}>
            <span className={`w-1.5 h-1.5 rounded-full inline-block ${s.dot}`} />
            {source.last_status || 'idle'}
          </span>
          <span>·</span>
          <span className="flex items-center gap-0.5"><Clock size={9} className="mr-0.5" />{timeSince(source.last_crawled_at)}</span>
        </div>
      </div>
      <div className="flex items-center gap-1 flex-shrink-0">
        <button onClick={onRecrawl} title="Re-crawl" className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800 transition-all">
          <RefreshCw size={12} />
        </button>
        <button onClick={onDelete} title="Delete source" className="p-1.5 rounded-lg text-gray-500 hover:text-rose-400 hover:bg-rose-950/20 transition-all">
          <Trash2 size={12} />
        </button>
      </div>
    </div>
  );
}

// ── DepartmentSelect + TypeSelect helpers ─────────────────────────────────
function DeptSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="space-y-1">
      <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Department</label>
      <Select value={value} onValueChange={v => v && onChange(v)}>
        <SelectTrigger className="w-full bg-gray-900/60 border-gray-800 text-xs text-white rounded-xl h-9">
          <SelectValue />
        </SelectTrigger>
        <SelectContent className="bg-gray-900 border-gray-800 text-white text-xs">
          <SelectItem value="General">General / All Teams</SelectItem>
          <SelectItem value="Marketing">Marketing AI</SelectItem>
          <SelectItem value="Sales">Sales CRM</SelectItem>
          <SelectItem value="HR">Hiring &amp; HR</SelectItem>
          <SelectItem value="Support">Customer Support</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
function TypeSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="space-y-1">
      <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Category</label>
      <Select value={value} onValueChange={v => v && onChange(v)}>
        <SelectTrigger className="w-full bg-gray-900/60 border-gray-800 text-xs text-white rounded-xl h-9">
          <SelectValue />
        </SelectTrigger>
        <SelectContent className="bg-gray-900 border-gray-800 text-white text-xs">
          <SelectItem value="Brand Guidelines">Brand &amp; Tone</SelectItem>
          <SelectItem value="FAQ">FAQ &amp; Support Runbook</SelectItem>
          <SelectItem value="Pricing">Pricing &amp; Sourcing Rules</SelectItem>
          <SelectItem value="Sales Playbook">Sales Playbook &amp; Battlecards</SelectItem>
          <SelectItem value="Case Study">Case Studies &amp; Customer Proof</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────
export default function KnowledgeView({ token, API_URL, fetchWithAuth, fetchData, knowledge }: KnowledgeViewProps) {
  const [kbDept, setKbDept] = useState('Marketing');
  const [kbType, setKbType] = useState('Brand Guidelines');
  const [kbSearch, setKbSearch] = useState('');
  const [kbContent, setKbContent] = useState('');
  const [kbFile, setKbFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [activeTab, setActiveTab] = useState<'upload' | 'website' | 'text' | 'directives'>('upload');

  const [crawlUrl, setCrawlUrl] = useState('');
  const [crawlMaxPages, setCrawlMaxPages] = useState(25);
  const [crawlDepth, setCrawlDepth] = useState(2);
  const [crawlIncludePaths, setCrawlIncludePaths] = useState('');
  const [crawlExcludePaths, setCrawlExcludePaths] = useState('');
  const [crawlSchedule, setCrawlSchedule] = useState('manual');
  const [isCrawling, setIsCrawling] = useState(false);
  const [isSyncingCompany, setIsSyncingCompany] = useState(false);
  const [sources, setSources] = useState<any[]>([]);
  const [isLoadingSources, setIsLoadingSources] = useState(false);

  const [toasts, setToasts] = useState<Toast[]>([]);
  const dropRef = useRef<HTMLDivElement>(null);

  // Toast helpers
  const toast = useCallback((type: ToastType, title: string, message?: string) => {
    const id = Math.random().toString(36).slice(2);
    setToasts(prev => [...prev, { id, type, title, message }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 5000);
  }, []);
  const dismissToast = (id: string) => setToasts(prev => prev.filter(t => t.id !== id));

  // Fetch sources when website tab is active
  const fetchSources = useCallback(async () => {
    setIsLoadingSources(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/commands/knowledge/sources`);
      if (res.ok) setSources(await res.json());
    } catch { /* silent */ }
    finally { setIsLoadingSources(false); }
  }, [fetchWithAuth, API_URL]);

  useEffect(() => {
    if (activeTab === 'website') fetchSources();
  }, [activeTab, fetchSources]);

  // Drag-and-drop
  const onDragOver = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(true); };
  const onDragLeave = () => setIsDragging(false);
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) setKbFile(file);
  };

  // Upload handler
  const uploadKnowledgeFile = async () => {
    if (!kbFile) return;
    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', kbFile);
      formData.append('department', kbDept);
      formData.append('doc_type', kbType);
      const res = await fetchWithAuth(`${API_URL}/commands/knowledge/upload`, { method: 'POST', body: formData });
      if (res.ok) {
        const data = await res.json();
        setKbFile(null);
        fetchData();
        toast('success', 'Document Ingested', `${data.chunks_indexed} chunks extracted via ${data.method || 'parser'}`);
      } else {
        const err = await res.json();
        toast('error', 'Upload Failed', err.detail || 'Could not process the document.');
      }
    } catch {
      toast('error', 'Network Error', 'Could not reach the server. Please try again.');
    } finally {
      setIsUploading(false);
    }
  };

  // Add text / directive
  const addKnowledge = async () => {
    if (!kbContent.trim()) return;
    const isDirective = activeTab === 'directives';
    try {
      const res = await fetchWithAuth(`${API_URL}/commands/knowledge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          department: isDirective ? 'General' : kbDept,
          doc_type: isDirective ? 'Prompt Directives' : kbType,
          content: kbContent,
        }),
      });
      if (res.ok) {
        setKbContent('');
        fetchData();
        toast('success', isDirective ? 'Directive Saved' : 'Content Added', 'Now available to all AI agents.');
      } else {
        const err = await res.json();
        toast('error', 'Save Failed', err.detail);
      }
    } catch {
      toast('error', 'Network Error', 'Could not reach the server.');
    }
  };

  // Crawl website
  const handleCrawlWebsite = async () => {
    if (!crawlUrl) return;
    setIsCrawling(true);
    try {
      const includeArr = crawlIncludePaths ? crawlIncludePaths.split(',').map(s => s.trim()).filter(Boolean) : [];
      const excludeArr = crawlExcludePaths ? crawlExcludePaths.split(',').map(s => s.trim()).filter(Boolean) : [];
      const res = await fetchWithAuth(`${API_URL}/commands/knowledge/web`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: crawlUrl, max_pages: crawlMaxPages, crawl_depth: crawlDepth, include_paths: includeArr, exclude_paths: excludeArr, schedule: crawlSchedule }),
      });
      if (res.ok) {
        const data = await res.json();
        setCrawlUrl('');
        fetchData();
        fetchSources();
        toast('success', 'Website Crawled', data.message || 'Pages indexed successfully.');
      } else {
        const err = await res.json();
        toast('error', 'Crawl Failed', err.detail || 'Could not crawl the URL.');
      }
    } catch {
      toast('error', 'Network Error', 'Could not reach the crawl service.');
    } finally {
      setIsCrawling(false);
    }
  };

  // Company sync
  const handleSyncCompanyWebsite = async () => {
    setIsSyncingCompany(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/commands/knowledge/web/company-sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ max_pages: crawlMaxPages, crawl_depth: crawlDepth }),
      });
      if (res.ok) {
        const data = await res.json();
        fetchData();
        fetchSources();
        toast('success', 'Company Site Synced', data.message || 'Synchronization complete.');
      } else {
        const err = await res.json();
        toast('error', 'Sync Failed', err.detail);
      }
    } catch {
      toast('error', 'Network Error', 'Could not reach the sync service.');
    } finally {
      setIsSyncingCompany(false);
    }
  };

  const handleRecrawlSource = async (id: string) => {
    try {
      const res = await fetchWithAuth(`${API_URL}/commands/knowledge/sources/${id}/recrawl`, { method: 'POST' });
      if (res.ok) { fetchData(); fetchSources(); toast('success', 'Re-crawl Started', 'Pages will be updated shortly.'); }
      else { const err = await res.json(); toast('error', 'Re-crawl Failed', err.detail); }
    } catch { toast('error', 'Network Error', 'Could not trigger re-crawl.'); }
  };

  const handleDeleteSource = async (id: string) => {
    if (!confirm('Delete this crawl source and all its indexed pages?')) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/commands/knowledge/sources/${id}`, { method: 'DELETE' });
      if (res.ok) { fetchData(); fetchSources(); toast('success', 'Source Deleted', 'All associated pages removed.'); }
      else toast('error', 'Delete Failed', 'Could not remove the source.');
    } catch { toast('error', 'Network Error', 'Could not reach the server.'); }
  };

  const deleteKnowledge = async (docId: string) => {
    if (!confirm('Delete this document from the knowledge base?')) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/commands/knowledge/${docId}`, { method: 'DELETE' });
      if (res.ok) { fetchData(); toast('success', 'Deleted', 'Document removed.'); }
      else toast('error', 'Delete Failed', 'Could not remove the document.');
    } catch { toast('error', 'Network Error', 'Could not reach the server.'); }
  };

  // Filtered documents
  const filteredDocs = knowledge.filter(doc => {
    const isWeb = doc.source_type === 'web' || doc.source_url?.startsWith('http');
    const isFile = doc.source_type === 'file' || doc.content?.startsWith('Source Document:');
    const title = isWeb ? (doc.source_url || '') : isFile
      ? (doc.content?.match(/^Source Document: ([^\n]+)/)?.[1] || '')
      : doc.doc_type;
    return (title + ' ' + (doc.department || '') + ' ' + (doc.doc_type || '')).toLowerCase().includes(kbSearch.toLowerCase());
  });

  // Tab configs
  const tabs: { id: typeof activeTab; label: string; icon: React.ReactNode; color: string }[] = [
    { id: 'upload',     label: 'Files',     icon: <Upload size={12} />,     color: 'violet' },
    { id: 'website',    label: 'Website',   icon: <Globe size={12} />,      color: 'emerald' },
    { id: 'text',       label: 'Text',      icon: <BookOpen size={12} />,   color: 'blue' },
    { id: 'directives', label: 'Directives',icon: <Brain size={12} />,      color: 'amber' },
  ];

  return (
    <>
      <ToastContainer toasts={toasts} dismiss={dismissToast} />

      <div className="space-y-5 max-w-7xl mx-auto flex flex-col h-[calc(100vh-130px)]">

        {/* ── Header ────────────────────────────────────────────────────── */}
        <div className="flex-shrink-0 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
              <div className="p-2 bg-violet-600/15 rounded-2xl">
                <Database size={20} className="text-violet-400" />
              </div>
              Knowledge Base
            </h1>
            <p className="text-gray-500 text-sm mt-1.5 max-w-xl">
              Ingest documents, crawl websites, and write AI directives — agents retrieve only what's relevant to each task.
            </p>
          </div>
          <div className="flex items-center gap-2 text-[10px] text-gray-600 bg-gray-900/60 border border-gray-800/50 rounded-2xl px-4 py-2.5">
            <Zap size={12} className="text-violet-400" />
            <span className="text-gray-400 font-medium">Hybrid RAG</span>
            <span className="text-gray-700">·</span>
            <span>pgvector + BM25 RRF</span>
          </div>
        </div>

        {/* ── Stats ─────────────────────────────────────────────────────── */}
        <StatsBar knowledge={knowledge} sources={sources} />

        {/* ── Main two-column panel ──────────────────────────────────────── */}
        <div className="flex-1 min-h-0 grid grid-cols-1 md:grid-cols-12 gap-6">

          {/* ── Left: Indexed Documents ───────────────────────────────────── */}
          <div className="md:col-span-5 flex flex-col min-h-0 bg-gray-900/30 border border-gray-800/50 rounded-3xl overflow-hidden">

            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800/50 flex-shrink-0">
              <div className="flex items-center gap-2">
                <BookOpen size={14} className="text-gray-400" />
                <span className="text-sm font-bold text-white">Indexed Documents</span>
                <span className="text-xs font-bold px-2 py-0.5 bg-gray-800 text-gray-400 rounded-full">{filteredDocs.length}</span>
              </div>
            </div>

            {/* Search */}
            <div className="px-4 py-3 flex-shrink-0">
              <div className="relative">
                <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600" />
                <Input
                  placeholder="Search documents, URLs, categories…"
                  value={kbSearch}
                  onChange={e => setKbSearch(e.target.value)}
                  className="pl-8 h-9 bg-gray-950/60 border-gray-800/60 text-xs text-white rounded-xl placeholder-gray-600 focus:border-violet-500 focus:ring-1 focus:ring-violet-500/20"
                />
                {kbSearch && (
                  <button onClick={() => setKbSearch('')} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-600 hover:text-white">
                    <X size={12} />
                  </button>
                )}
              </div>
            </div>

            {/* Doc list */}
            <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-1.5 custom-scrollbar min-h-0">
              {filteredDocs.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full gap-3 py-12 text-center">
                  <div className="p-4 bg-gray-800/40 rounded-2xl">
                    <Database size={22} className="text-gray-600" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-gray-500">
                      {kbSearch ? 'No matches found' : 'No documents yet'}
                    </p>
                    <p className="text-[11px] text-gray-700 mt-0.5">
                      {kbSearch ? 'Try a different search term' : 'Add files, web pages, or text on the right →'}
                    </p>
                  </div>
                </div>
              ) : (
                filteredDocs.map(doc => (
                  <DocRow key={doc.id} doc={doc} onDelete={() => deleteKnowledge(doc.id)} />
                ))
              )}
            </div>
          </div>

          {/* ── Right: Add Knowledge ──────────────────────────────────────── */}
          <div className="md:col-span-7 flex flex-col min-h-0 bg-gray-900/30 border border-gray-800/50 rounded-3xl overflow-hidden">

            {/* Tab bar */}
            <div className="flex items-center gap-0.5 px-4 pt-4 flex-shrink-0">
              {tabs.map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-[11px] font-bold transition-all duration-200 ${
                    activeTab === tab.id
                      ? tab.id === 'upload'     ? 'bg-violet-600 text-white shadow-lg shadow-violet-600/20'
                      : tab.id === 'website'    ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-600/20'
                      : tab.id === 'text'       ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
                      :                          'bg-amber-600 text-white shadow-lg shadow-amber-600/20'
                      : 'text-gray-500 hover:text-gray-300 hover:bg-gray-800/50'
                  }`}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="w-full h-px bg-gray-800/50 mt-3 flex-shrink-0" />

            {/* Tab content */}
            <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-5 flex flex-col gap-4">

              {/* ── File Upload Tab ── */}
              {activeTab === 'upload' && (
                <>
                  <div className="grid grid-cols-2 gap-3">
                    <DeptSelect value={kbDept} onChange={setKbDept} />
                    <TypeSelect value={kbType} onChange={setKbType} />
                  </div>

                  {/* Drop zone */}
                  <div
                    ref={dropRef}
                    onDragOver={onDragOver}
                    onDragLeave={onDragLeave}
                    onDrop={onDrop}
                    className={`relative flex-1 min-h-[180px] border-2 border-dashed rounded-2xl flex flex-col items-center justify-center p-6 text-center transition-all duration-200 cursor-pointer group ${
                      isDragging
                        ? 'border-violet-500 bg-violet-950/15 scale-[1.01]'
                        : kbFile
                          ? 'border-violet-500/40 bg-violet-950/5'
                          : 'border-gray-800 hover:border-gray-700 bg-gray-950/30 hover:bg-gray-900/40'
                    }`}
                  >
                    <input
                      type="file"
                      accept=".pdf,.docx,.doc,.pptx,.ppt,.xlsx,.xls,.csv,.tsv,.txt,.md,.json,.html,.png,.jpg,.jpeg,.webp,.bmp,.gif,.tif,.tiff,.rtf"
                      onChange={e => e.target.files?.[0] && setKbFile(e.target.files[0])}
                      className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    />

                    {kbFile ? (
                      <div className="space-y-2">
                        <div className="mx-auto w-12 h-12 bg-violet-600/15 rounded-2xl flex items-center justify-center">
                          <FileIcon name={kbFile.name} className="text-violet-400 w-5 h-5" />
                        </div>
                        <div>
                          <p className="text-sm font-bold text-white truncate max-w-[260px]">{kbFile.name}</p>
                          <p className="text-[11px] text-gray-500 mt-0.5">{formatBytes(kbFile.size)} · Click to change</p>
                        </div>
                        <button
                          onClick={e => { e.stopPropagation(); setKbFile(null); }}
                          className="text-[10px] text-gray-600 hover:text-rose-400 transition-colors"
                        >
                          Remove file
                        </button>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        <div className={`mx-auto w-12 h-12 bg-gray-800/60 rounded-2xl flex items-center justify-center transition-transform group-hover:scale-110 ${isDragging ? 'scale-110' : ''}`}>
                          <Upload size={20} className="text-gray-500 group-hover:text-violet-400 transition-colors" />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-gray-300">
                            {isDragging ? 'Drop to upload' : 'Drag & drop or click to browse'}
                          </p>
                          <p className="text-[11px] text-gray-600 mt-1 max-w-[300px]">
                            PDF (tables &amp; scans), DOCX, PPTX, XLSX, CSV, Images (OCR), TXT, Markdown
                          </p>
                        </div>
                        {/* File type badges */}
                        <div className="flex flex-wrap justify-center gap-1.5">
                          {['PDF', 'DOCX', 'PPTX', 'XLSX', 'CSV', 'Images', 'TXT'].map(ft => (
                            <span key={ft} className="text-[9px] px-2 py-0.5 rounded-full bg-gray-800/80 text-gray-500 border border-gray-700/40">{ft}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  <Button
                    onClick={uploadKnowledgeFile}
                    disabled={!kbFile || isUploading}
                    className="w-full h-11 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-bold rounded-xl shadow-lg shadow-violet-600/20 flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {isUploading ? (
                      <><Loader2 size={15} className="animate-spin" /> Parsing layout, tables &amp; OCR…</>
                    ) : (
                      <><Upload size={15} /> Upload &amp; Ingest Document</>
                    )}
                  </Button>
                </>
              )}

              {/* ── Website Tab ── */}
              {activeTab === 'website' && (
                <>
                  {/* Company sync hero card */}
                  <div className="relative overflow-hidden bg-gradient-to-br from-emerald-950/40 to-teal-950/30 border border-emerald-800/40 rounded-2xl p-4">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-600/5 rounded-full -translate-y-8 translate-x-8" />
                    <div className="flex items-center justify-between gap-4 relative">
                      <div className="flex items-start gap-3">
                        <div className="p-2 bg-emerald-600/15 rounded-xl flex-shrink-0 mt-0.5">
                          <Building2 size={16} className="text-emerald-400" />
                        </div>
                        <div>
                          <p className="text-sm font-bold text-emerald-300">Sync Company Website</p>
                          <p className="text-[11px] text-gray-500 mt-0.5 leading-snug">
                            One-click sync of your registered domain with auto change detection.
                          </p>
                        </div>
                      </div>
                      <Button
                        onClick={handleSyncCompanyWebsite}
                        disabled={isSyncingCompany}
                        className="flex-shrink-0 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs h-9 px-4 rounded-xl shadow-lg shadow-emerald-600/20 disabled:opacity-50"
                      >
                        {isSyncingCompany ? <><Loader2 size={12} className="animate-spin mr-1.5" />Syncing…</> : 'Sync Now'}
                      </Button>
                    </div>
                  </div>

                  {/* Custom crawl form */}
                  <div className="space-y-3 bg-gray-950/40 border border-gray-800/50 rounded-2xl p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <Link2 size={13} className="text-violet-400" />
                      <h4 className="text-xs font-bold text-gray-300">Crawl Any Website</h4>
                    </div>

                    <div className="relative">
                      <Globe size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600" />
                      <Input
                        placeholder="https://docs.example.com or https://yoursite.com"
                        value={crawlUrl}
                        onChange={e => setCrawlUrl(e.target.value)}
                        className="pl-8 h-9 bg-gray-900/60 border-gray-800 text-xs text-white rounded-xl placeholder-gray-600 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/20"
                      />
                    </div>

                    <div className="grid grid-cols-3 gap-3">
                      <div className="space-y-1">
                        <label className="text-[10px] font-bold text-gray-600 uppercase tracking-widest">Max Pages</label>
                        <Input
                          type="number" min={1} max={100}
                          value={crawlMaxPages}
                          onChange={e => setCrawlMaxPages(parseInt(e.target.value) || 25)}
                          className="h-9 bg-gray-900/60 border-gray-800 text-xs text-white rounded-xl"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-[10px] font-bold text-gray-600 uppercase tracking-widest">Depth</label>
                        <Input
                          type="number" min={1} max={5}
                          value={crawlDepth}
                          onChange={e => setCrawlDepth(parseInt(e.target.value) || 2)}
                          className="h-9 bg-gray-900/60 border-gray-800 text-xs text-white rounded-xl"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-[10px] font-bold text-gray-600 uppercase tracking-widest">Schedule</label>
                        <Select value={crawlSchedule} onValueChange={val => setCrawlSchedule(val || 'manual')}>
                          <SelectTrigger className="h-9 w-full bg-gray-900/60 border-gray-800 text-xs text-white rounded-xl">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent className="bg-gray-900 border-gray-800 text-white text-xs">
                            <SelectItem value="manual">Manual</SelectItem>
                            <SelectItem value="daily">Daily</SelectItem>
                            <SelectItem value="weekly">Weekly</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <Input
                        placeholder="Include: /docs, /pricing"
                        value={crawlIncludePaths}
                        onChange={e => setCrawlIncludePaths(e.target.value)}
                        className="h-9 bg-gray-900/60 border-gray-800 text-xs text-white rounded-xl placeholder-gray-700"
                      />
                      <Input
                        placeholder="Exclude: /blog, /tag"
                        value={crawlExcludePaths}
                        onChange={e => setCrawlExcludePaths(e.target.value)}
                        className="h-9 bg-gray-900/60 border-gray-800 text-xs text-white rounded-xl placeholder-gray-700"
                      />
                    </div>

                    <Button
                      onClick={handleCrawlWebsite}
                      disabled={!crawlUrl || isCrawling}
                      className="w-full h-10 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold rounded-xl text-xs flex items-center justify-center gap-2 shadow-lg shadow-emerald-600/15 disabled:opacity-40"
                    >
                      {isCrawling
                        ? <><Loader2 size={13} className="animate-spin" />Crawling &amp; indexing pages…</>
                        : <><Globe size={13} />Crawl &amp; Ingest Website</>}
                    </Button>
                  </div>

                  {/* Managed sources */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-gray-400 flex items-center gap-1.5">
                        <BarChart3 size={12} className="text-gray-600" />
                        Managed Sources ({sources.length})
                      </span>
                      <button
                        onClick={fetchSources}
                        className="flex items-center gap-1 text-[10px] text-gray-600 hover:text-white px-2 py-1 rounded-lg hover:bg-gray-800/50 transition-all"
                      >
                        <RefreshCw size={10} className={isLoadingSources ? 'animate-spin' : ''} />
                        Refresh
                      </button>
                    </div>

                    {sources.length > 0 ? (
                      <div className="space-y-1.5">
                        {sources.map(s => (
                          <SourceRow
                            key={s.id}
                            source={s}
                            onRecrawl={() => handleRecrawlSource(s.id)}
                            onDelete={() => handleDeleteSource(s.id)}
                          />
                        ))}
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center gap-2 py-8 border border-dashed border-gray-800/60 rounded-2xl">
                        <Globe size={18} className="text-gray-700" />
                        <p className="text-[11px] text-gray-600">No website sources yet. Crawl a URL above.</p>
                      </div>
                    )}
                  </div>
                </>
              )}

              {/* ── Text Tab ── */}
              {activeTab === 'text' && (
                <>
                  <div className="grid grid-cols-2 gap-3">
                    <DeptSelect value={kbDept} onChange={setKbDept} />
                    <TypeSelect value={kbType} onChange={setKbType} />
                  </div>

                  <div className="flex-1 flex flex-col gap-3">
                    <div className="flex items-center gap-2">
                      <BookOpen size={13} className="text-blue-400" />
                      <p className="text-xs font-semibold text-gray-400">Paste text content below</p>
                    </div>
                    <Textarea
                      placeholder="Paste guidelines, FAQ answers, product descriptions, pricing rules, or any reference text here…"
                      value={kbContent}
                      onChange={e => setKbContent(e.target.value)}
                      className="flex-1 min-h-[200px] bg-gray-950/40 border-gray-800 text-xs text-white focus:border-blue-500 focus:ring-1 focus:ring-blue-500/20 placeholder-gray-700 resize-none rounded-2xl leading-relaxed"
                    />
                    <div className="flex items-center justify-between text-[10px] text-gray-700">
                      <span>{kbContent.length} characters</span>
                      {kbContent.length > 0 && (
                        <button onClick={() => setKbContent('')} className="hover:text-rose-400 transition-colors">Clear</button>
                      )}
                    </div>
                    <Button
                      onClick={addKnowledge}
                      disabled={!kbContent.trim()}
                      className="w-full h-11 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold rounded-xl shadow-lg shadow-blue-600/20 flex items-center justify-center gap-2 disabled:opacity-40"
                    >
                      <Plus size={15} />Add Text to Knowledge Base
                    </Button>
                  </div>
                </>
              )}

              {/* ── Directives Tab ── */}
              {activeTab === 'directives' && (
                <>
                  {/* Info banner */}
                  <div className="flex items-start gap-3 bg-amber-950/20 border border-amber-900/30 rounded-2xl p-4">
                    <div className="p-1.5 bg-amber-500/10 rounded-lg flex-shrink-0 mt-0.5">
                      <Brain size={14} className="text-amber-400" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-amber-300">Pinned AI Directives</p>
                      <p className="text-[11px] text-gray-500 mt-1 leading-relaxed">
                        Directives are <strong className="text-amber-400/80">permanently injected</strong> into every agent invocation — brand tone, contact links, compliance rules, and legal disclaimers. Keep them concise.
                      </p>
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {['Brand Tone', 'Contact Email', 'Legal Disclaimer', 'Competitor Rules', 'Taglines'].map(ex => (
                          <span key={ex} className="text-[9px] px-2 py-0.5 rounded-full bg-amber-900/20 border border-amber-800/30 text-amber-500/80">{ex}</span>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="flex-1 flex flex-col gap-3">
                    <Textarea
                      placeholder={`e.g., "Always end marketing posts with: 📧 hello@acme.com | 🌐 www.acme.com — Write in an authoritative, uplifting voice. Never mention competitor brands by name."`}
                      value={kbContent}
                      onChange={e => setKbContent(e.target.value)}
                      className="flex-1 min-h-[180px] bg-gray-950/40 border-gray-800 text-xs text-white focus:border-amber-500 focus:ring-1 focus:ring-amber-500/20 placeholder-gray-700 resize-none rounded-2xl leading-relaxed"
                    />
                    <div className="flex items-center justify-between text-[10px] text-gray-700">
                      <span>{kbContent.length} characters</span>
                      {kbContent.length > 0 && (
                        <button onClick={() => setKbContent('')} className="hover:text-rose-400 transition-colors">Clear</button>
                      )}
                    </div>
                    <Button
                      onClick={addKnowledge}
                      disabled={!kbContent.trim()}
                      className="w-full h-11 bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 text-white font-bold rounded-xl shadow-lg shadow-amber-600/20 flex items-center justify-center gap-2 disabled:opacity-40"
                    >
                      <Sparkles size={15} />Save AI Directive
                    </Button>
                  </div>
                </>
              )}

            </div>
          </div>
        </div>
      </div>
    </>
  );
}
