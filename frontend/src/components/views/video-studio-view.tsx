'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Video, Plus, Loader2, Play, RefreshCw, FileJson, CheckCircle, AlertTriangle, Trash2 } from 'lucide-react';

const FakeProgressBar = () => {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    // Start with a small jump
    setProgress(5);
    
    const interval = setInterval(() => {
      setProgress((prev) => {
        // Slow down progress as it gets higher, capping at 95%
        if (prev >= 95) return 95;
        const increment = prev < 50 ? 5 : prev < 80 ? 2 : 1;
        return prev + increment;
      });
    }, 5000); // Update every 5 seconds

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="w-full max-w-[120px] flex flex-col gap-1 mt-1">
      <div className="h-1.5 w-full bg-gray-800 rounded-full overflow-hidden">
        <div 
          className="h-full bg-violet-500 transition-all duration-1000 ease-in-out" 
          style={{ width: `${progress}%` }} 
        />
      </div>
      <span className="text-[9px] text-gray-500 text-right">{progress}%</span>
    </div>
  );
};

interface VideoStudioViewProps {
  token: string | null;
  API_URL: string;
  fetchWithAuth: (url: string, options?: any) => Promise<Response>;
}

export default function VideoStudioView({ token, API_URL, fetchWithAuth }: VideoStudioViewProps) {
  const [projects, setProjects] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [prompt, setPrompt] = useState('');
  const [title, setTitle] = useState('');
  const [provider, setProvider] = useState('auto');
  const [model, setModel] = useState('gemini-2.5-flash');
  const [selectedProject, setSelectedProject] = useState<any | null>(null);

  const fetchProjects = async () => {
    if (!token) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/videos/`);
      if (res.ok) {
        const data = await res.json();
        setProjects(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchProjects();
    const interval = setInterval(fetchProjects, 5000);
    return () => clearInterval(interval);
  }, [token]);

  const handleCreateProject = async () => {
    if (!prompt || !title) return alert('Please enter title and prompt');
    setLoading(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/videos/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          title, 
          prompt, 
          provider: provider === 'auto' ? undefined : provider, 
          model: provider === 'auto' ? undefined : model
        })
      });
      if (res.ok) {
        setPrompt('');
        setTitle('');
        fetchProjects();
        alert('Video project created! AI is planning the storyboard.');
      } else {
        alert('Failed to create video project.');
      }
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const handleRender = async (projectId: string) => {
    try {
      const res = await fetchWithAuth(`${API_URL}/videos/${projectId}/render`, {
        method: 'POST'
      });
      if (res.ok) {
        alert('Rendering started!');
        fetchProjects();
      } else {
        const data = await res.json();
        alert(`Failed to render: ${data.detail || 'Unknown error'}`);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleDelete = async (projectId: string) => {
    if (!confirm('Are you sure you want to delete this video project? This cannot be undone.')) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/videos/${projectId}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        fetchProjects();
      } else {
        const data = await res.json();
        alert(`Failed to delete: ${data.detail || 'Unknown error'}`);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const getStatusBadge = (status: string) => {
    switch(status) {
      case 'planned': return <span className="bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider">Planned</span>;
      case 'queued': return <span className="bg-purple-500/10 text-purple-400 border border-purple-500/20 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider flex items-center gap-1"><Loader2 className="h-3 w-3 animate-spin"/> Queued</span>;
      case 'rendering': return (
        <div className="flex flex-col gap-1">
          <span className="bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 w-max"><Loader2 className="h-3 w-3 animate-spin"/> Rendering</span>
          <FakeProgressBar />
        </div>
      );
      case 'completed': return <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider flex items-center gap-1"><CheckCircle className="h-3 w-3"/> Ready</span>;
      case 'failed': return <span className="bg-rose-500/10 text-rose-400 border border-rose-500/20 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider flex items-center gap-1"><AlertTriangle className="h-3 w-3"/> Failed</span>;
      default: return <span className="bg-gray-500/10 text-gray-400 border border-gray-500/20 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider flex items-center gap-1"><Loader2 className="h-3 w-3 animate-spin"/> Planning</span>;
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
            <Video className="text-violet-400" /> AI Video Studio
          </h1>
          <p className="text-gray-400 mt-1">Generate programmatic motion graphics for marketing and social media.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="glass-panel border-transparent rounded-2xl p-6 shadow-2xl relative overflow-hidden lg:col-span-1">
          <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-violet-500 to-indigo-500" />
          <CardHeader className="p-0 mb-4">
            <CardTitle className="text-lg font-bold text-white">Create New Video</CardTitle>
          </CardHeader>
          <CardContent className="p-0 space-y-4">
            <div className="space-y-2">
              <label className="text-xs font-semibold text-gray-400">Video Title</label>
              <Input 
                value={title} 
                onChange={(e) => setTitle(e.target.value)} 
                placeholder="e.g. October Product Launch" 
                className="bg-gray-900/50 border-gray-800 text-white"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-semibold text-gray-400">Concept / Prompt</label>
              <Textarea 
                value={prompt} 
                onChange={(e) => setPrompt(e.target.value)} 
                placeholder="Describe the video. e.g. 'A 30-second promo for our new AI agent feature. Include a hero scene, 3 feature highlights, and a final call to action.'" 
                className="bg-gray-900/50 border-gray-800 text-white min-h-[120px] text-sm"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-xs font-semibold text-gray-400">AI Provider</label>
                <Select value={provider} onValueChange={(val) => {
                  if (!val) return;
                  setProvider(val);
                  if (val === 'openrouter') setModel('google/gemini-2.5-flash');
                  else if (val === 'together') setModel('meta-llama/Llama-3.3-70B-Instruct-Turbo');
                  else if (val === 'groq') setModel('llama-3.3-70b-versatile');
                  else if (val === 'gemini') setModel('gemini-2.5-flash');
                  else if (val === 'openai') setModel('gpt-4o');
                  else if (val === 'anthropic') setModel('claude-sonnet-4-6');
                }}>
                  <SelectTrigger className="bg-gray-900/50 border-gray-800 text-white h-9 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-gray-900 border-gray-800 text-white">
                    <SelectItem value="auto">Auto (AI Brain Choice)</SelectItem>
                    <SelectItem value="openrouter">OpenRouter (Meta-Hub)</SelectItem>
                    <SelectItem value="together">Together AI (Meta-Hub)</SelectItem>
                    <SelectItem value="groq">Groq (Ultra-Fast)</SelectItem>
                    <SelectItem value="gemini">Google Gemini</SelectItem>
                    <SelectItem value="openai">OpenAI GPT</SelectItem>
                    <SelectItem value="anthropic">Anthropic Claude</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              {provider !== 'auto' && (
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-gray-400">Model</label>
                  <Select value={model} onValueChange={(val) => val && setModel(val)}>
                    <SelectTrigger className="bg-gray-900/50 border-gray-800 text-white h-9 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-gray-900 border-gray-800 text-white">
                      {provider === 'openrouter' && (
                        <>
                          <SelectItem value="google/gemini-2.5-flash">Gemini 2.5 Flash</SelectItem>
                          <SelectItem value="anthropic/claude-3.5-sonnet">Claude 3.5 Sonnet</SelectItem>
                          <SelectItem value="openai/gpt-4o">GPT-4o</SelectItem>
                        </>
                      )}
                      {provider === 'together' && (
                        <>
                          <SelectItem value="meta-llama/Llama-3.3-70B-Instruct-Turbo">Llama 3.3 70B Turbo</SelectItem>
                          <SelectItem value="deepseek-ai/DeepSeek-V3">DeepSeek V3</SelectItem>
                        </>
                      )}
                      {provider === 'groq' && (
                        <>
                          <SelectItem value="llama-3.3-70b-versatile">Llama 3.3 70B</SelectItem>
                          <SelectItem value="llama-3.1-8b-instant">Llama 3.1 8B</SelectItem>
                        </>
                      )}
                      {provider === 'gemini' && (
                        <>
                          <SelectItem value="gemini-2.5-flash">Gemini 2.5 Flash</SelectItem>
                          <SelectItem value="gemini-2.5-pro">Gemini 2.5 Pro</SelectItem>
                          <SelectItem value="gemini-2.0-flash">Gemini 2.0 Flash</SelectItem>
                        </>
                      )}
                      {provider === 'openai' && (
                        <>
                          <SelectItem value="gpt-4o">GPT-4o</SelectItem>
                          <SelectItem value="gpt-4o-mini">GPT-4o mini</SelectItem>
                        </>
                      )}
                      {provider === 'anthropic' && (
                        <>
                          <SelectItem value="claude-sonnet-4-6">Claude 3.5 Sonnet</SelectItem>
                          <SelectItem value="claude-haiku-4-5-20251001">Claude 3.5 Haiku</SelectItem>
                          <SelectItem value="claude-opus-4-8">Claude 3.5 Opus</SelectItem>
                        </>
                      )}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
            <Button 
              onClick={handleCreateProject} 
              disabled={loading || !title || !prompt}
              className="w-full bg-violet-600 hover:bg-violet-500 text-white font-bold"
            >
              {loading ? <Loader2 className="animate-spin h-4 w-4 mr-2" /> : <Plus className="h-4 w-4 mr-2" />}
              Generate Storyboard
            </Button>
          </CardContent>
        </Card>

        <Card className="glass-panel border-transparent rounded-2xl shadow-2xl relative overflow-hidden lg:col-span-2 flex flex-col h-[600px]">
          <CardHeader className="border-b border-gray-800 pb-4 pt-6 px-6">
            <CardTitle className="text-lg font-bold text-white flex justify-between items-center">
              <span>Video Projects</span>
              <Button variant="ghost" size="sm" onClick={fetchProjects} className="text-gray-400 hover:text-white">
                <RefreshCw className="h-4 w-4" />
              </Button>
            </CardTitle>
          </CardHeader>
          <div className="flex-1 overflow-auto p-0">
            <Table>
              <TableHeader className="bg-gray-900/50 sticky top-0">
                <TableRow className="border-gray-800 hover:bg-transparent">
                  <TableHead className="text-gray-400 text-xs uppercase">Title & Info</TableHead>
                  <TableHead className="text-gray-400 text-xs uppercase">Status</TableHead>
                  <TableHead className="text-right text-gray-400 text-xs uppercase">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {projects.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={3} className="text-center py-12 text-gray-500">No video projects yet. Create your first one.</TableCell>
                  </TableRow>
                )}
                {projects.map((proj) => (
                  <TableRow key={proj.id} className="border-gray-800/50 hover:bg-gray-800/30">
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="font-bold text-white">{proj.title}</span>
                        <span className="text-xs text-gray-500">{new Date(proj.created_at).toLocaleString()} • {proj.duration_seconds}s</span>
                      </div>
                    </TableCell>
                    <TableCell>{getStatusBadge(proj.status)}</TableCell>
                    <TableCell className="text-right space-x-2">
                      <Button variant="outline" size="sm" onClick={() => setSelectedProject(proj)} className="border-gray-700 bg-transparent hover:bg-gray-800 text-xs">
                        <FileJson className="h-3 w-3 mr-1" /> View Blueprint
                      </Button>
                      
                      {proj.status === 'planned' && (
                        <Button size="sm" onClick={() => handleRender(proj.id)} className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs">
                          <Play className="h-3 w-3 mr-1" /> Render
                        </Button>
                      )}

                      {proj.final_video_url && (
                        <Button size="sm" onClick={() => window.open(proj.final_video_url, '_blank')} className="bg-blue-600 hover:bg-blue-500 text-white text-xs">
                          <Play className="h-3 w-3 mr-1" /> Watch
                        </Button>
                      )}

                      <Button variant="outline" size="sm" onClick={() => handleDelete(proj.id)} className="border-rose-900/50 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 text-xs px-2">
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </Card>
      </div>

      {selectedProject && (
        <Card className="glass-panel border-transparent rounded-2xl p-6 shadow-2xl relative overflow-hidden mt-6">
          <CardHeader className="p-0 mb-4 flex flex-row justify-between items-center">
            <CardTitle className="text-lg font-bold text-white">Blueprint JSON: {selectedProject.title}</CardTitle>
            <Button variant="ghost" size="sm" onClick={() => setSelectedProject(null)}>Close</Button>
          </CardHeader>
          <CardContent className="p-0">
            <pre className="bg-gray-950 p-4 rounded-xl text-emerald-400 font-mono text-xs overflow-auto max-h-[400px]">
              {JSON.stringify(selectedProject.blueprint, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
