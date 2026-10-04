'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { BookOpen, Zap, Search, Users, Cpu, MessageSquare, Briefcase, FileText, ChevronRight } from 'lucide-react';

interface InstructionsViewProps {
  configuredProviders: string[];
  setIsKeyDialogOpen: (open: boolean) => void;
  setKeyProvider: (provider: string) => void;
  API_URL: string;
  tenantId: string | null;
}

export default function InstructionsView({
  configuredProviders,
  setIsKeyDialogOpen,
  setKeyProvider,
  API_URL,
  tenantId,
}: InstructionsViewProps) {
  return (
    <div className="max-w-5xl mx-auto space-y-8 pb-16 animate-in fade-in duration-300">
      <div>
        <h1 className="text-4xl font-extrabold text-white tracking-tight flex items-center gap-3">
          <BookOpen className="text-violet-500 h-9 w-9" /> Platform Setup & API Connection Guide
        </h1>
        <p className="text-gray-400 mt-1">Get your autonomous AI workspace connected, configured, and running in minutes.</p>
      </div>

      <Tabs defaultValue="marketplace_guide" className="w-full">
        <TabsList className="grid w-full max-w-[650px] grid-cols-3 bg-gray-950/60 p-1 border border-gray-800 rounded-2xl mb-8">
          <TabsTrigger value="marketplace_guide" className="rounded-xl text-xs font-semibold py-2.5 text-gray-400 data-[state=active]:bg-violet-600 data-[state=active]:text-white transition-all">
            🛒 Marketplace & Autopilot Guide
          </TabsTrigger>
          <TabsTrigger value="api_setup" className="rounded-xl text-xs font-semibold py-2.5 text-gray-400 data-[state=active]:bg-violet-600 data-[state=active]:text-white transition-all">
            🔑 API Provider Setup
          </TabsTrigger>
          <TabsTrigger value="quick_prompts" className="rounded-xl text-xs font-semibold py-2.5 text-gray-400 data-[state=active]:bg-violet-600 data-[state=active]:text-white transition-all">
            ⚡ Quick-Start Prompts
          </TabsTrigger>
        </TabsList>

        {/* TAB CONTENT: MARKETPLACE GUIDE */}
        <TabsContent value="marketplace_guide" className="space-y-6 animate-in fade-in duration-200">
          <Card className="glass-panel border-transparent p-8 rounded-3xl shadow-2xl relative overflow-hidden">
            <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-violet-500 to-transparent" />
            <h3 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
              <Zap className="text-pink-500 animate-pulse" size={20} />
              How to Use Marketplace Automations (Non-Tech Friendly)
            </h3>

            <div className="space-y-8 relative before:absolute before:left-[17px] before:top-2 before:bottom-2 before:w-[2px] before:bg-gradient-to-b before:from-violet-500 before:via-pink-500 before:to-gray-800">

              {/* Step 1 */}
              <div className="flex gap-6 relative">
                <div className="h-9 w-9 rounded-full bg-violet-600 border-2 border-gray-950 flex items-center justify-center font-extrabold text-white text-sm shadow-lg z-10">
                  1
                </div>
                <div className="flex-1 space-y-1.5 pt-0.5">
                  <h4 className="font-bold text-white text-base">Select & Install Your Autopilot Pack</h4>
                  <p className="text-gray-300 text-xs leading-relaxed">
                    Click the <strong className="text-violet-400">Workflow Marketplace</strong> in the sidebar. Choose the pack that aligns with your industry (e.g., <strong className="text-violet-400">Restaurant Growth Pack</strong> or <strong className="text-violet-400">SaaS Outreach System</strong>). Click <strong className="bg-pink-600/35 border border-pink-500/30 px-2 py-0.5 rounded text-white font-bold">Install Pack</strong>. Once installed, it instantly shows up under "Installed Automations" on your Operating Dashboard.
                  </p>
                </div>
              </div>

              {/* Step 2 */}
              <div className="flex gap-6 relative">
                <div className="h-9 w-9 rounded-full bg-violet-600 border-2 border-gray-950 flex items-center justify-center font-extrabold text-white text-sm shadow-lg z-10">
                  2
                </div>
                <div className="flex-1 space-y-1.5 pt-0.5">
                  <h4 className="font-bold text-white text-base">Connect Your API Keys</h4>
                  <p className="text-gray-300 text-xs leading-relaxed">
                    Open the <strong className="text-violet-400">API Provider Setup</strong> tab above. Check which services your pack needs (e.g. Meta Graph for Instagram, Apollo.io for B2B sales email). Click <strong className="text-violet-400 font-bold">API Settings</strong> in the top-right header, select the provider, paste your key, and click Save. Check if the status badge on the provider card turns <span className="inline-flex items-center gap-1 bg-emerald-500/10 text-emerald-450 border border-emerald-500/20 px-2 py-0.5 rounded text-[10px] font-bold">● Connected</span>.
                  </p>
                </div>
              </div>

              {/* Step 3 */}
              <div className="flex gap-6 relative">
                <div className="h-9 w-9 rounded-full bg-pink-600 border-2 border-gray-950 flex items-center justify-center font-extrabold text-white text-sm shadow-lg z-10">
                  3
                </div>
                <div className="flex-1 space-y-1.5 pt-0.5">
                  <h4 className="font-bold text-white text-base">Instruct the Orchestrator AI</h4>
                  <p className="text-gray-300 text-xs leading-relaxed">
                    Navigate to <strong className="text-violet-400">Orchestrator AI</strong> from the sidebar. Ask the AI to perform a task utilizing your installed pack. For example: <code className="bg-gray-950 px-2 py-1 rounded text-pink-400 text-[11px] font-mono">"Run the Restaurant Growth Pack to post our specials on Instagram today"</code>. The AI will look at your active integrations, generate the content draft, and process the request!
                  </p>
                </div>
              </div>

              {/* Step 4 */}
              <div className="flex gap-6 relative">
                <div className="h-9 w-9 rounded-full bg-pink-600 border-2 border-gray-950 flex items-center justify-center font-extrabold text-white text-sm shadow-lg z-10">
                  4
                </div>
                <div className="flex-1 space-y-1.5 pt-0.5">
                  <h4 className="font-bold text-white text-base">Review & Approve in the Operating Dashboard</h4>
                  <p className="text-gray-300 text-xs leading-relaxed">
                    Open your <strong className="text-violet-400">Operating Dashboard</strong>. Scroll down to the <strong className="text-violet-400">Approvals Pipeline</strong>. You'll see the AI's generated output (e.g. daily specials posts, outbound leads) sitting in the queue. Click <strong className="text-emerald-400 font-bold">Approve</strong> to publish or send them, or <strong className="text-rose-400 font-bold">Reject</strong> to request changes. You are always in control!
                  </p>
                </div>
              </div>

            </div>
          </Card>

          {/* Operational Details Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card className="glass-panel border-transparent p-6 rounded-3xl relative overflow-hidden">
              <h4 className="text-white font-bold text-base mb-3 flex items-center gap-2">🤖 Autonomous Auto-Reply delays</h4>
              <p className="text-gray-300 text-xs leading-relaxed">
                To maintain a natural, human-like appearance, when the AI agent handles incoming messages (e.g. WhatsApp, Email Tickets), it uses natural delays:
              </p>
              <ul className="text-gray-400 text-xs space-y-2 mt-3 pl-4 list-disc">
                <li><strong>WhatsApp:</strong> 4-5 minutes wait window before automated response.</li>
                <li><strong>Email Tickets:</strong> 20 minutes wait window.</li>
                <li><strong>Human Interception:</strong> If you write a manual reply in the support tab before the delay timer runs out, the AI will step back and cancel its scheduled response automatically.</li>
              </ul>
            </Card>

            <Card className="glass-panel border-transparent p-6 rounded-3xl relative overflow-hidden">
              <h4 className="text-white font-bold text-base mb-3 flex items-center gap-2"> Knowledge Base Integration</h4>
              <p className="text-gray-300 text-xs leading-relaxed">
                Before the AI generates any marketing posts, replies to customer support emails, or scores candidates, it reads files uploaded to your <strong className="text-violet-400">Knowledge Base</strong> (found in the header).
              </p>
              <p className="text-gray-300 text-xs leading-relaxed mt-2">
                For best results, upload your <strong>Brand Guidelines</strong>, <strong>FAQs & Policies</strong>, <strong>Pricing Tables</strong>, or <strong>Job Descriptions</strong>. This guarantees the AI behaves in complete alignment with your brand rules!
              </p>
            </Card>
          </div>
        </TabsContent>

        {/* TAB CONTENT: API SETUP CARD GRID */}
        <TabsContent value="api_setup" className="space-y-6 animate-in fade-in duration-200">
          <div className="grid grid-cols-1 gap-6">

            {/* AI Brains & Generators Card */}
            <Card className="glass-panel border-transparent rounded-3xl overflow-hidden shadow-2xl relative p-6">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-800 pb-4 mb-4">
                <div>
                  <h3 className="text-white font-extrabold text-lg flex items-center gap-2">1. AI Brains & Generators</h3>
                  <p className="text-gray-400 text-xs mt-1">Powers the core thinking, writing, image creation, and video generation for your AI employees.</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${configuredProviders.includes('anthropic') || configuredProviders.includes('openai') || configuredProviders.includes('gemini') || configuredProviders.includes('openrouter') || configuredProviders.includes('together') || configuredProviders.includes('groq') || configuredProviders.includes('grok')
                      ? 'bg-emerald-500/10 text-emerald-455 border-emerald-500/20'
                      : 'bg-rose-500/10 text-rose-455 border-rose-500/20 animate-pulse'
                    }`}>
                    <span className={`h-1.5 w-1.5 rounded-full ${configuredProviders.includes('anthropic') || configuredProviders.includes('openai') || configuredProviders.includes('gemini') || configuredProviders.includes('openrouter') || configuredProviders.includes('together') || configuredProviders.includes('groq') || configuredProviders.includes('grok') ? 'bg-emerald-450' : 'bg-rose-450'
                      }`} />
                    {configuredProviders.includes('anthropic') || configuredProviders.includes('openai') || configuredProviders.includes('gemini') || configuredProviders.includes('openrouter') || configuredProviders.includes('together') || configuredProviders.includes('groq') || configuredProviders.includes('grok') ? 'Active' : 'Missing Primary Key'}
                  </span>
                  <Button
                    onClick={() => { setKeyProvider('openrouter'); setIsKeyDialogOpen(true); }}
                    className="bg-violet-600 hover:bg-violet-500 text-white text-xs font-bold h-8 rounded-xl px-4"
                  >
                    Configure
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8 text-gray-300 text-xs">
                {/* OpenRouter */}
                <div className="space-y-2">
                  <p className="font-bold text-white flex items-center gap-1.5 text-sm pb-1 border-b border-gray-800">
                    <span className="h-2 w-2 rounded-full bg-sky-400" /> OpenRouter (Meta-Hub — All Models)
                  </p>
                  <ol className="list-decimal pl-4 space-y-1.5 text-gray-400">
                    <li>Go to <a href="https://openrouter.ai/keys" target="_blank" rel="noreferrer" className="text-violet-400 hover:text-violet-300 transition-colors hover:underline font-medium">openrouter.ai/keys</a> and sign in.</li>
                    <li>Click <strong>Create Key</strong> and give it a label (e.g. "OctaOS").</li>
                    <li>Copy your API key starting with <code>sk-or-v1-</code>.</li>
                    <li>Provides access to Claude 3.5, GPT-4o, Gemini 2.5, DeepSeek, and Llama from a single balance.</li>
                  </ol>
                </div>

                {/* Together AI */}
                <div className="space-y-2">
                  <p className="font-bold text-white flex items-center gap-1.5 text-sm pb-1 border-b border-gray-800">
                    <span className="h-2 w-2 rounded-full bg-pink-400" /> Together AI (Open Source & Fast Inference)
                  </p>
                  <ol className="list-decimal pl-4 space-y-1.5 text-gray-400">
                    <li>Go to <a href="https://api.together.ai/settings/api-keys" target="_blank" rel="noreferrer" className="text-violet-400 hover:text-violet-300 transition-colors hover:underline font-medium">api.together.ai</a> and create an account.</li>
                    <li>Navigate to <strong>Settings &gt; API Keys</strong>.</li>
                    <li>Copy your API key and save it in OctaOS to run Llama 3.3 70B, DeepSeek V3, and Qwen at ultra-low latency.</li>
                  </ol>
                </div>

                {/* Claude */}
                <div className="space-y-2">
                  <p className="font-bold text-white flex items-center gap-1.5 text-sm pb-1 border-b border-gray-800">
                    <span className="h-2 w-2 rounded-full bg-violet-400" /> Claude (Anthropic API)
                  </p>
                  <ol className="list-decimal pl-4 space-y-1.5 text-gray-400">
                    <li>Go to <a href="https://console.anthropic.com/" target="_blank" rel="noreferrer" className="text-violet-400 hover:text-violet-300 transition-colors hover:underline font-medium">console.anthropic.com</a> and sign in.</li>
                    <li>Navigate to <strong>API Keys</strong> in the left dashboard menu.</li>
                    <li>Click the <strong>Create Key</strong> button.</li>
                    <li>Name it (e.g. "OctaOS") and copy the new key starting with <code>sk-ant-</code>.</li>
                    <li>Click the <strong>Configure</strong> button above and paste this key to activate.</li>
                  </ol>
                </div>

                {/* OpenAI */}
                <div className="space-y-2">
                  <p className="font-bold text-white flex items-center gap-1.5 text-sm pb-1 border-b border-gray-800">
                    <span className="h-2 w-2 rounded-full bg-emerald-400" /> OpenAI (ChatGPT API)
                  </p>
                  <ol className="list-decimal pl-4 space-y-1.5 text-gray-400">
                    <li>Go to <a href="https://platform.openai.com/api-keys" target="_blank" rel="noreferrer" className="text-violet-400 hover:text-violet-300 transition-colors hover:underline font-medium">platform.openai.com/api-keys</a> and sign in.</li>
                    <li>Click the <strong>Create new secret key</strong> button.</li>
                    <li>Provide a name (e.g., "OctaOS Default") and create the key.</li>
                    <li>Copy the generated key (it usually starts with <code>sk-proj-</code>).</li>
                    <li>Save it in OctaOS to give your agents access to GPT-4o.</li>
                  </ol>
                </div>

                {/* Gemini */}
                <div className="space-y-2">
                  <p className="font-bold text-white flex items-center gap-1.5 text-sm pb-1 border-b border-gray-800">
                    <span className="h-2 w-2 rounded-full bg-blue-400" /> Google Gemini API
                  </p>
                  <ol className="list-decimal pl-4 space-y-1.5 text-gray-400">
                    <li>Go to <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noreferrer" className="text-violet-400 hover:text-violet-300 transition-colors hover:underline font-medium">Google AI Studio</a> and sign in with your Google account.</li>
                    <li>Click <strong>Get API Key</strong> on the left sidebar.</li>
                    <li>Click the blue <strong>Create API Key in new project</strong> button.</li>
                    <li>Once generated, copy the long alphanumeric string.</li>
                    <li>Paste the key into the OctaOS configuration panel to enable Google's models.</li>
                  </ol>
                </div>

                {/* Stable Diffusion */}
                <div className="space-y-2">
                  <p className="font-bold text-white flex items-center gap-1.5 text-sm pb-1 border-b border-gray-800">
                    <span className="h-2 w-2 rounded-full bg-fuchsia-400" /> Stable Diffusion (Stability AI)
                  </p>
                  <ol className="list-decimal pl-4 space-y-1.5 text-gray-400">
                    <li>Go to <a href="https://platform.stability.ai/" target="_blank" rel="noreferrer" className="text-violet-400 hover:text-violet-300 transition-colors hover:underline font-medium">platform.stability.ai</a> and log in.</li>
                    <li>Click on your profile avatar in the top right, then select <strong>API Keys</strong>.</li>
                    <li>Click the copy icon next to your default API key (starting with <code>sk-</code>).</li>
                    <li>Provide this key to OctaOS to enable high-quality AI image generation for Marketing.</li>
                  </ol>
                </div>

                {/* Pika AI */}
                <div className="space-y-2">
                  <p className="font-bold text-white flex items-center gap-1.5 text-sm pb-1 border-b border-gray-800">
                    <span className="h-2 w-2 rounded-full bg-amber-400" /> Pika AI (Video Generation)
                  </p>
                  <ol className="list-decimal pl-4 space-y-1.5 text-gray-400">
                    <li>Visit <a href="https://pika.art/login" target="_blank" rel="noreferrer" className="text-violet-400 hover:text-violet-300 transition-colors hover:underline font-medium">pika.art</a> and create an account or sign in.</li>
                    <li>Navigate to the API section or developer settings (if you have API access enabled).</li>
                    <li>Generate a new API token.</li>
                    <li>Enter this token into OctaOS so your Marketing AI can generate and publish video content directly.</li>
                  </ol>
                </div>
              </div>

              <div className="bg-violet-950/25 border border-violet-900/30 p-4 rounded-xl text-xs text-violet-300 mt-6 leading-relaxed font-mono flex items-start gap-3 shadow-inner">
                <span className="text-lg">💡</span>
                <div>
                  <strong className="text-white block mb-1">Pro-Tip for Non-Tech Users:</strong>
                  You can bypass the manual "Configure" button entirely! Just type or paste your key directly into the Orchestrator AI Chat window on the left. For example: <code>"Here is my Gemini key: AIzaSyB..."</code> and the AI will securely save and configure it for you automatically!
                </div>
              </div>
            </Card>

            {/* Social Media Card */}
            <Card className="glass-panel border-transparent rounded-3xl overflow-hidden shadow-2xl relative p-6">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-800 pb-4 mb-4">
                <div>
                  <h3 className="text-white font-extrabold text-lg flex items-center gap-2">2. Social Media (Meta & LinkedIn)</h3>
                  <p className="text-gray-400 text-xs mt-1">Allows the Marketing AI to draft and automatically publish campaigns on your profiles.</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${configuredProviders.includes('meta') || configuredProviders.includes('linkedin')
                      ? 'bg-emerald-500/10 text-emerald-455 border-emerald-500/20'
                      : 'bg-gray-800 text-gray-400 border-gray-700/60'
                    }`}>
                    <span className={`h-1.5 w-1.5 rounded-full ${configuredProviders.includes('meta') || configuredProviders.includes('linkedin') ? 'bg-emerald-450' : 'bg-gray-500'
                      }`} />
                    {configuredProviders.includes('meta') || configuredProviders.includes('linkedin') ? 'Configured' : 'Not Connected'}
                  </span>
                  <Button
                    onClick={() => { setKeyProvider('linkedin'); setIsKeyDialogOpen(true); }}
                    className="bg-violet-600 hover:bg-violet-500 text-white text-xs font-bold h-8 rounded-xl px-4"
                  >
                    Configure
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8 text-gray-300 text-xs">
                {/* Meta Graph API */}
                <div className="space-y-2">
                  <p className="font-bold text-white flex items-center gap-1.5 text-sm pb-1 border-b border-gray-800">
                    <span className="h-2 w-2 rounded-full bg-blue-500" /> Meta Graph API (Instagram & Facebook)
                  </p>
                  <ol className="list-decimal pl-4 space-y-1.5 text-gray-400">
                    <li>Log into <a href="https://developers.facebook.com/" target="_blank" rel="noreferrer" className="text-violet-400 hover:text-violet-300 transition-colors hover:underline font-medium">Meta for Developers</a> and click <strong>Create App</strong>.</li>
                    <li>Select <strong>Other</strong> then <strong>Business</strong> as the app type.</li>
                    <li>Scroll down to add the <strong>Instagram Graph API</strong> product to your newly created app.</li>
                    <li>Navigate to the <strong>Tools &gt; Graph API Explorer</strong> in the top menu.</li>
                    <li>Select your app and generate a <strong>Page Access Token</strong>, ensuring you add the <code>instagram_content_publish</code>, <code>pages_show_list</code>, and <code>instagram_basic</code> permissions.</li>
                    <li>Click "Generate Access Token". Use the <strong>Access Token Tool</strong> to extend it into a long-lived (60-day) token, then paste it into OctaOS. <em className="text-gray-500 text-[10px] block mt-1">(Make sure your Instagram Business Account is properly linked to your Facebook Page!)</em></li>
                  </ol>
                </div>

                {/* LinkedIn */}
                <div className="space-y-2">
                  <p className="font-bold text-white flex items-center gap-1.5 text-sm pb-1 border-b border-gray-800">
                    <span className="h-2 w-2 rounded-full bg-sky-500" /> LinkedIn Share API
                  </p>
                  <ol className="list-decimal pl-4 space-y-1.5 text-gray-400">
                    <li>Sign in to the <a href="https://developer.linkedin.com/" target="_blank" rel="noreferrer" className="text-violet-400 hover:text-violet-300 transition-colors hover:underline font-medium">LinkedIn Developer Portal</a> and click <strong>Create App</strong>.</li>
                    <li>Fill in the required details (Name, LinkedIn Page URL, Privacy Policy URL) and verify your app.</li>
                    <li>Under the <strong>Products</strong> tab, request access to <strong>"Share on LinkedIn"</strong> and <strong>"Sign In with LinkedIn v2"</strong>. Wait for approval.</li>
                    <li>Navigate to the <strong>Auth</strong> tab and use the <strong>OAuth 2.0 Token Generator</strong> tool.</li>
                    <li>Select the products you requested and generate a <strong>Personal Access Token</strong> (usually valid for 2 months).</li>
                    <li>Copy the generated token and paste it here to authorize OctaOS to post on your behalf.</li>
                  </ol>
                </div>
              </div>
            </Card>

            {/* Messaging Card */}
            <Card className="glass-panel border-transparent rounded-3xl overflow-hidden shadow-2xl relative p-6">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-800 pb-4 mb-4">
                <div>
                  <h3 className="text-white font-extrabold text-lg flex items-center gap-2">3. Chat Messaging (WhatsApp & Telegram)</h3>
                  <p className="text-gray-400 text-xs mt-1">Connects customer chat channels so the Support & Lead Gen AI can respond automatically.</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${configuredProviders.includes('whatsapp') || configuredProviders.includes('telegram')
                      ? 'bg-emerald-500/10 text-emerald-455 border-emerald-500/20'
                      : 'bg-gray-800 text-gray-400 border-gray-700/60'
                    }`}>
                    <span className={`h-1.5 w-1.5 rounded-full ${configuredProviders.includes('whatsapp') || configuredProviders.includes('telegram') ? 'bg-emerald-450' : 'bg-gray-500'
                      }`} />
                    {configuredProviders.includes('whatsapp') || configuredProviders.includes('telegram') ? 'Configured' : 'Not Connected'}
                  </span>
                  <Button
                    onClick={() => { setKeyProvider('whatsapp'); setIsKeyDialogOpen(true); }}
                    className="bg-violet-600 hover:bg-violet-500 text-white text-xs font-bold h-8 rounded-xl px-4"
                  >
                    Configure
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8 text-gray-300 text-xs">
                {/* WhatsApp */}
                <div className="space-y-2">
                  <p className="font-bold text-white flex items-center gap-1.5 text-sm pb-1 border-b border-gray-800">
                    <span className="h-2 w-2 rounded-full bg-emerald-500" /> WhatsApp Cloud Business API
                  </p>
                  <ol className="list-decimal pl-4 space-y-1.5 text-gray-400">
                    <li>Inside your <a href="https://developers.facebook.com/" target="_blank" rel="noreferrer" className="text-violet-400 hover:text-violet-300 transition-colors hover:underline font-medium">Meta Developer Console</a>, open your existing app or create a new Business App.</li>
                    <li>Scroll down to add the <strong>WhatsApp</strong> product to your app.</li>
                    <li>Navigate to <strong>WhatsApp &gt; API Setup</strong> in the left sidebar.</li>
                    <li>Copy your <strong>Phone Number ID</strong> and your temporary <strong>Access Token</strong> (or generate a permanent System User token in Business Settings).</li>
                    <li>Paste the Token and Phone ID in the OctaOS settings.</li>
                    <li>Finally, configure the <strong>Webhook URL</strong> in Meta to point to your OctaOS backend (usually <code>/api/v1/webhooks/whatsapp</code>) with a verify token so your AI can receive incoming customer messages.</li>
                  </ol>
                </div>

                {/* Telegram */}
                <div className="space-y-2">
                  <p className="font-bold text-white flex items-center gap-1.5 text-sm pb-1 border-b border-gray-800">
                    <span className="h-2 w-2 rounded-full bg-blue-400" /> Telegram Bot API
                  </p>
                  <ol className="list-decimal pl-4 space-y-1.5 text-gray-400">
                    <li>Open your Telegram app on your phone or desktop.</li>
                    <li>Search for <code>@BotFather</code> in the global search bar and press <strong>Start</strong>.</li>
                    <li>Send the command <code>/newbot</code> to initiate the creation process.</li>
                    <li>Choose a display name for your AI Assistant, and then a unique username that must end in "bot" (e.g. <code>SupportAgentBot</code>).</li>
                    <li>BotFather will reply with a success message containing your <strong>HTTP API Token</strong> (looks like <code>123456789:ABCDEF...</code>).</li>
                    <li>Copy this exact token and save it in OctaOS. The system will automatically register a webhook to receive messages.</li>
                  </ol>
                </div>
              </div>
            </Card>

            {/* Google Workspace Card */}
            <Card className="glass-panel border-transparent rounded-3xl overflow-hidden shadow-2xl relative p-6">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-800 pb-4 mb-4">
                <div>
                  <h3 className="text-white font-extrabold text-lg flex items-center gap-2">4. Email & Bookings (Google Workspace / Gmail / Calendar)</h3>
                  <p className="text-gray-400 text-xs mt-1">Allows agents to coordinate and send cold email campaigns or book meetings on your calendar.</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${configuredProviders.includes('gmail') || configuredProviders.includes('google_calendar') || configuredProviders.includes('smtp')
                      ? 'bg-emerald-500/10 text-emerald-455 border-emerald-500/20'
                      : 'bg-gray-800 text-gray-400 border-gray-700/60'
                    }`}>
                    <span className={`h-1.5 w-1.5 rounded-full ${configuredProviders.includes('gmail') || configuredProviders.includes('google_calendar') || configuredProviders.includes('smtp') ? 'bg-emerald-450' : 'bg-gray-500'
                      }`} />
                    {configuredProviders.includes('gmail') || configuredProviders.includes('google_calendar') || configuredProviders.includes('smtp') ? 'Configured' : 'Not Connected'}
                  </span>
                  <Button
                    onClick={() => { window.location.href = `${API_URL}/google/auth?tenant_id=${tenantId}`; }}
                    className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold h-8 rounded-xl px-4"
                  >
                    Connect Google Account
                  </Button>
                  <Button
                    onClick={() => { setKeyProvider('smtp'); setIsKeyDialogOpen(true); }}
                    className="bg-violet-600 hover:bg-violet-500 text-white text-xs font-bold h-8 rounded-xl px-4"
                  >
                    Configure SMTP
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8 text-gray-300 text-xs">
                {/* Google Cloud */}
                <div className="space-y-2">
                  <p className="font-bold text-white flex items-center gap-1.5 text-sm pb-1 border-b border-gray-800">
                    <span className="h-2 w-2 rounded-full bg-red-500" /> Google Cloud OAuth Setup (Gmail & Calendar)
                  </p>
                  <ol className="list-decimal pl-4 space-y-1.5 text-gray-400">
                    <li>Go to the <a href="https://console.cloud.google.com/" target="_blank" rel="noreferrer" className="text-violet-400 hover:text-violet-300 transition-colors hover:underline font-medium">Google Cloud Console</a> and create a new Project (e.g., "OctaOS Workspace").</li>
                    <li>Navigate to <strong>APIs &amp; Services &gt; Library</strong> using the left menu.</li>
                    <li>Search for and enable both the <strong>Gmail API</strong> and <strong>Google Calendar API</strong>.</li>
                    <li>Go to the <strong>OAuth consent screen</strong> tab and configure it (Internal for organizations, or External for general use). Add the necessary scopes for Mail and Calendar.</li>
                    <li>Navigate to <strong>Credentials</strong>, click <strong>Create Credentials &gt; OAuth client ID</strong>. Choose "Web application" or "Desktop app".</li>
                    <li>Download the resulting JSON secret file and upload or connect it in OctaOS to grant your AI full calendar and email drafting capabilities.</li>
                  </ol>
                </div>

                {/* SMTP */}
                <div className="space-y-2">
                  <p className="font-bold text-white flex items-center gap-1.5 text-sm pb-1 border-b border-gray-800">
                    <span className="h-2 w-2 rounded-full bg-orange-400" /> Standard Outgoing Mail (SMTP Alternative)
                  </p>
                  <p className="text-gray-400 leading-relaxed mb-3">
                    If you do not want to set up a full Google Cloud OAuth project, you can allow the AI to send emails via a standard SMTP connection using an App Password.
                  </p>
                  <ol className="list-decimal pl-4 space-y-1.5 text-gray-400">
                    <li>Go to your Google Account's <a href="https://myaccount.google.com/security" target="_blank" rel="noreferrer" className="text-violet-400 hover:text-violet-300 transition-colors hover:underline font-medium">Security settings</a>.</li>
                    <li>Ensure <strong>2-Step Verification</strong> is enabled.</li>
                    <li>Search for <strong>App Passwords</strong> in the security search bar.</li>
                    <li>Create a new app password named "OctaOS AI". Copy the generated 16-character password.</li>
                    <li>Provide your SMTP string in the OctaOS settings formatted like this: <br /><code className="bg-gray-900 px-1.5 py-0.5 rounded text-gray-300 mt-1 inline-block border border-gray-800">smtp://your.email@gmail.com:app-password@smtp.gmail.com:587</code></li>
                  </ol>
                </div>
              </div>
            </Card>

            {/* Lead Gen Card */}
            <Card className="glass-panel border-transparent rounded-3xl overflow-hidden shadow-2xl relative p-6">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-800 pb-4 mb-4">
                <div>
                  <h3 className="text-white font-extrabold text-lg flex items-center gap-2">5. Sales Lead Generation (Apollo / Hunter / Google Maps / Apify)</h3>
                  <p className="text-gray-400 text-xs mt-1">Powers the Sales AI to extract and identify high-value contacts or local businesses.</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${configuredProviders.includes('apollo') || configuredProviders.includes('hunter') || configuredProviders.includes('google_places') || configuredProviders.includes('apify')
                      ? 'bg-emerald-500/10 text-emerald-455 border-emerald-500/20'
                      : 'bg-gray-800 text-gray-400 border-gray-700/60'
                    }`}>
                    <span className={`h-1.5 w-1.5 rounded-full ${configuredProviders.includes('apollo') || configuredProviders.includes('hunter') || configuredProviders.includes('google_places') || configuredProviders.includes('apify') ? 'bg-emerald-450' : 'bg-gray-500'
                      }`} />
                    {configuredProviders.includes('apollo') || configuredProviders.includes('hunter') || configuredProviders.includes('google_places') || configuredProviders.includes('apify') ? 'Configured' : 'Not Connected'}
                  </span>
                  <Button
                    onClick={() => { setKeyProvider('apify'); setIsKeyDialogOpen(true); }}
                    className="bg-violet-600 hover:bg-violet-500 text-white text-xs font-bold h-8 rounded-xl px-4"
                  >
                    Configure
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 text-gray-300 text-xs">
                {/* Apollo / Hunter */}
                <div className="space-y-2">
                  <p className="font-bold text-white flex items-center gap-1.5 text-sm pb-1 border-b border-gray-800">
                    <span className="h-2 w-2 rounded-full bg-indigo-500" /> Apollo.io / Hunter.io (B2B Enrichment)
                  </p>
                  <ol className="list-decimal pl-4 space-y-1.5 text-gray-400">
                    <li>Create a free or paid account at <a href="https://www.apollo.io/" target="_blank" rel="noreferrer" className="text-violet-400 hover:text-violet-300 transition-colors hover:underline font-medium">Apollo.io</a> or <a href="https://hunter.io/" target="_blank" rel="noreferrer" className="text-violet-400 hover:text-violet-300 transition-colors hover:underline font-medium">Hunter.io</a>.</li>
                    <li>For Apollo: Go to <strong>Settings &gt; Integrations &gt; API</strong> and click <strong>Generate New API Key</strong>.</li>
                    <li>For Hunter: Go to <strong>Account &gt; API</strong> and copy your API key.</li>
                    <li>Paste the respective API key into the OctaOS configuration panel.</li>
                    <li>Your Sales AI Agent is now instantly capable of enriching company names into verified employee contact lists, emails, and phone numbers!</li>
                  </ol>
                </div>

                {/* Google Places */}
                <div className="space-y-2">
                  <p className="font-bold text-white flex items-center gap-1.5 text-sm pb-1 border-b border-gray-800">
                    <span className="h-2 w-2 rounded-full bg-teal-500" /> Google Places API (Local Business Scraper)
                  </p>
                  <ol className="list-decimal pl-4 space-y-1.5 text-gray-400">
                    <li>Log into the <a href="https://console.cloud.google.com/" target="_blank" rel="noreferrer" className="text-violet-400 hover:text-violet-300 transition-colors hover:underline font-medium">Google Cloud Console</a> and select your project.</li>
                    <li>In the search bar, type <strong>Places API (New)</strong> and click Enable.</li>
                    <li>Make sure you have an active billing account linked to your Google Cloud project (Google provides $200 free credit monthly).</li>
                    <li>Go to <strong>APIs &amp; Services &gt; Credentials</strong>, click <strong>Create Credentials</strong>, and select <strong>API Key</strong>.</li>
                    <li>(Strongly Recommended) Edit the API Key to restrict it specifically to the "Places API" to prevent unauthorized usage.</li>
                    <li>Copy the generated key and save it in OctaOS to allow your AI to map local business targets.</li>
                  </ol>
                </div>

                {/* Apify */}
                <div className="space-y-2">
                  <p className="font-bold text-white flex items-center gap-1.5 text-sm pb-1 border-b border-gray-800">
                    <span className="h-2 w-2 rounded-full bg-yellow-500" /> Apify (Data Extraction &amp; Scraping)
                  </p>
                  <ol className="list-decimal pl-4 space-y-1.5 text-gray-400">
                    <li>Log into the <a href="https://console.apify.com/" target="_blank" rel="noreferrer" className="text-violet-400 hover:text-violet-300 transition-colors hover:underline font-medium">Apify Console</a>.</li>
                    <li>Navigate to <strong>Settings &gt; API</strong> in the left sidebar.</li>
                    <li>Copy your personal API token.</li>
                    <li>Paste the API token into the OctaOS configuration panel under Apify.</li>
                    <li>Your Sales AI Agent is now capable of running dynamic web scrapers!</li>
                  </ol>
                </div>
              </div>
            </Card>

          </div>
        </TabsContent>

        {/* TAB CONTENT: QUICK PROMPTS */}
        <TabsContent value="quick_prompts" className="space-y-6 animate-in fade-in duration-200">
          <Card className="glass-panel border-transparent p-6 rounded-3xl shadow-2xl relative">
            <h3 className="text-white font-extrabold text-lg mb-4 flex items-center gap-2">⚡ Autopilot Launch Commands</h3>
            <p className="text-gray-300 text-xs leading-relaxed mb-6">
              Once you have installed a Marketplace Pack and configured its API keys, you can trigger its operation. Go to the <strong className="text-violet-400">Orchestrator AI</strong> chat tab and copy-paste any of the ready-to-run prompts below:
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Prompt 1 */}
              <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-4 flex flex-col justify-between space-y-4 hover:border-pink-500/30 transition-all">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-pink-400 font-bold uppercase tracking-wider bg-pink-500/10 border border-pink-500/20 px-2 py-0.5 rounded-md">Restaurant Pack</span>
                    <span className="text-[10px] text-gray-500">Local Marketing</span>
                  </div>
                  <p className="text-white text-xs font-semibold">"Trigger the daily special post for Restaurant Pack. Create a draft of today's specials (Steak & Potatoes with red wine) for Instagram."</p>
                </div>
                <Button
                  onClick={() => {
                    navigator.clipboard.writeText("Trigger the daily special post for Restaurant Pack. Create a draft of today's specials (Steak & Potatoes with red wine) for Instagram.");
                    alert("Copied to clipboard! Go to Orchestrator AI to paste.");
                  }}
                  className="bg-gray-850 hover:bg-gray-800 text-gray-300 text-xs font-bold w-full h-8 rounded-xl"
                >
                  Copy Prompt
                </Button>
              </div>

              {/* Prompt 2 */}
              <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-4 flex flex-col justify-between space-y-4 hover:border-pink-500/30 transition-all">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-pink-400 font-bold uppercase tracking-wider bg-pink-500/10 border border-pink-500/20 px-2 py-0.5 rounded-md">SaaS Outreach</span>
                    <span className="text-[10px] text-gray-500">B2B Outbound</span>
                  </div>
                  <p className="text-white text-xs font-semibold">"Execute the SaaS Outreach System. Sourcing 5 CTOs at early-stage AI startups in New York, and write personalized outbound LinkedIn DMs."</p>
                </div>
                <Button
                  onClick={() => {
                    navigator.clipboard.writeText("Execute the SaaS Outreach System. Sourcing 5 CTOs at early-stage AI startups in New York, and write personalized outbound LinkedIn DMs.");
                    alert("Copied to clipboard! Go to Orchestrator AI to paste.");
                  }}
                  className="bg-gray-850 hover:bg-gray-800 text-gray-300 text-xs font-bold w-full h-8 rounded-xl"
                >
                  Copy Prompt
                </Button>
              </div>

              {/* Prompt 3 */}
              <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-4 flex flex-col justify-between space-y-4 hover:border-pink-500/30 transition-all">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-pink-400 font-bold uppercase tracking-wider bg-pink-500/10 border border-pink-500/20 px-2 py-0.5 rounded-md">Real Estate Pack</span>
                    <span className="text-[10px] text-gray-500">Real Estate</span>
                  </div>
                  <p className="text-white text-xs font-semibold">"Generate property descriptions using the Real Estate Lead Engine for 456 Oak Ave. Make it sound premium with a luxury pool description."</p>
                </div>
                <Button
                  onClick={() => {
                    navigator.clipboard.writeText("Generate property descriptions using the Real Estate Lead Engine for 456 Oak Ave. Make it sound premium with a luxury pool description.");
                    alert("Copied to clipboard! Go to Orchestrator AI to paste.");
                  }}
                  className="bg-gray-850 hover:bg-gray-800 text-gray-300 text-xs font-bold w-full h-8 rounded-xl"
                >
                  Copy Prompt
                </Button>
              </div>

              {/* Prompt 4 */}
              <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-4 flex flex-col justify-between space-y-4 hover:border-pink-500/30 transition-all">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-pink-400 font-bold uppercase tracking-wider bg-pink-500/10 border border-pink-500/20 px-2 py-0.5 rounded-md">Creative Content</span>
                    <span className="text-[10px] text-gray-500">Creative Agency</span>
                  </div>
                  <p className="text-white text-xs font-semibold">"Create an SEO Blog Outline Writer task with the Creative Content Lab. Write a outline on 'How AI employees are transforming small businesses'."</p>
                </div>
                <Button
                  onClick={() => {
                    navigator.clipboard.writeText("Create an SEO Blog Outline Writer task with the Creative Content Lab. Write a outline on 'How AI employees are transforming small businesses'.");
                    alert("Copied to clipboard! Go to Orchestrator AI to paste.");
                  }}
                  className="bg-gray-850 hover:bg-gray-800 text-gray-300 text-xs font-bold w-full h-8 rounded-xl"
                >
                  Copy Prompt
                </Button>
              </div>
            </div>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
