'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { 
  Calendar, Film, Image as ImageIcon, Edit2, MessageSquare, Send, Clock, 
  ChevronDown, ChevronUp, Sparkles, LayoutGrid, CalendarRange, Trash2, 
  Loader2, Cpu, Check, X, Plus, TrendingUp 
} from 'lucide-react';

interface CampaignsViewProps {
  token: string | null;
  activeView?: string;
  API_URL: string;
  fetchWithAuth: (url: string, options?: any) => Promise<Response>;
  fetchData: () => Promise<void>;
  configuredProviders: string[];
}

export default function CampaignsView({
  token,
  activeView,
  API_URL,
  fetchWithAuth,
  fetchData,
  configuredProviders,
}: CampaignsViewProps) {
  // State variables relocated here
  const [campaignTopic, setCampaignTopic] = useState('');
  const [campaignDays, setCampaignDays] = useState(30);
  const [campaignPlatforms, setCampaignPlatforms] = useState<string[]>(['linkedin', 'instagram', 'facebook']);
  const [textProvider, setTextProvider] = useState('auto');
  const [imageProvider, setImageProvider] = useState('openai');
  const [videoProvider, setVideoProvider] = useState('pika');
  const [generateImages, setGenerateImages] = useState(true);
  // In-app video generation not ready — keep state but force off / hide UI
  const ENABLE_IN_APP_VIDEO = false;
  const [generateVideos, setGenerateVideos] = useState(false);
  const [generateRemotion, setGenerateRemotion] = useState(false);
  const [campaignPosts, setCampaignPosts] = useState<any[]>([]);
  const [campaignFilterPlatform, setCampaignFilterPlatform] = useState<string>('all');
  const [campaignFilterStatus, setCampaignFilterStatus] = useState<string>('all');
  const [textModel, setTextModel] = useState<string>('gemini-2.5-flash');
  const [isGeneratorExpanded, setIsGeneratorExpanded] = useState<boolean>(true);
  const [campaignViewMode, setCampaignViewMode] = useState<'timeline' | 'kanban' | 'analytics'>('timeline');
  const [loading, setLoading] = useState(false);
  const [analyticsDash, setAnalyticsDash] = useState<any>(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsSyncing, setAnalyticsSyncing] = useState(false);

  const [editingPostId, setEditingPostId] = useState<string | null>(null);
  const [editingContent, setEditingContent] = useState('');
  const [editingImageUrl, setEditingImageUrl] = useState('');
  const [editingVideoUrl, setEditingVideoUrl] = useState('');
  const [editingImagePrompt, setEditingImagePrompt] = useState('');
  const [editingImagePromptEnabled, setEditingImagePromptEnabled] = useState(false);
  const [editingVideoPrompt, setEditingVideoPrompt] = useState('');
  const [editingVideoPromptEnabled, setEditingVideoPromptEnabled] = useState(false);
  const [editingRemotionPrompt, setEditingRemotionPrompt] = useState('');
  const [editingRemotionPromptEnabled, setEditingRemotionPromptEnabled] = useState(false);
  const [editingIsManualMedia, setEditingIsManualMedia] = useState(false);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [generatingMedia, setGeneratingMedia] = useState(false);
  const [suggestingPrompt, setSuggestingPrompt] = useState(false);

  const fetchAnalyticsDashboard = async () => {
    if (!token) return;
    setAnalyticsLoading(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/marketing/analytics/dashboard`);
      if (res.ok) setAnalyticsDash(await res.json());
    } catch (e) {
      console.error(e);
    } finally {
      setAnalyticsLoading(false);
    }
  };

  const syncAnalytics = async () => {
    if (!token) return;
    setAnalyticsSyncing(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/marketing/analytics/sync?background=false&limit=50`, {
        method: 'POST',
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        alert(`Synced: ${data.synced ?? 0} posts · Patterns updated: ${data.patterns_updated ?? 0}`);
        await fetchAnalyticsDashboard();
        await fetchData();
      } else {
        alert(data.detail || 'Analytics sync failed — ensure Meta/LinkedIn OAuth and published posts have external IDs.');
      }
    } catch (e) {
      console.error(e);
      alert('Analytics sync failed');
    } finally {
      setAnalyticsSyncing(false);
    }
  };

  useEffect(() => {
    if (token && campaignViewMode === 'analytics') {
      fetchAnalyticsDashboard();
    }
  }, [token, campaignViewMode]);

  const [isCreatePostOpen, setIsCreatePostOpen] = useState(false);
  const [createPostPlatform, setCreatePostPlatform] = useState('linkedin');
  const [createPostContent, setCreatePostContent] = useState('');
  const [createPostDay, setCreatePostDay] = useState(1);
  const [createPostImageUrl, setCreatePostImageUrl] = useState('');
  const [createPostVideoUrl, setCreatePostVideoUrl] = useState('');
  const [createPostImagePrompt, setCreatePostImagePrompt] = useState('');
  const [createPostImagePromptEnabled, setCreatePostImagePromptEnabled] = useState(false);
  const [createPostVideoPrompt, setCreatePostVideoPrompt] = useState('');
  const [createPostVideoPromptEnabled, setCreatePostVideoPromptEnabled] = useState(false);
  const [createPostRemotionPrompt, setCreatePostRemotionPrompt] = useState('');
  const [createPostRemotionPromptEnabled, setCreatePostRemotionPromptEnabled] = useState(false);
  const [createPostIsManualMedia, setCreatePostIsManualMedia] = useState(false);
  const [creatingPost, setCreatingPost] = useState(false);
  const [editingScheduledAt, setEditingScheduledAt] = useState('');
  const [createPostScheduledAt, setCreatePostScheduledAt] = useState('');

  const [isBulkScheduleOpen, setIsBulkScheduleOpen] = useState(false);
  const [bulkStartDate, setBulkStartDate] = useState('');
  const [bulkEndDate, setBulkEndDate] = useState('');
  const [bulkPostingTime, setBulkPostingTime] = useState('09:00');
  const [bulkScheduling, setBulkScheduling] = useState(false);

  const [publishingPostId, setPublishingPostId] = useState<string | null>(null);
  const [publishResult, setPublishResult] = useState<{success: boolean; message: string} | null>(null);
  const [isMetaModalOpen, setIsMetaModalOpen] = useState(false);
  const [pendingPublishPostId, setPendingPublishPostId] = useState<string | null>(null);
  const [metaTokenInput, setMetaTokenInput] = useState('');
  const [savingMetaToken, setSavingMetaToken] = useState(false);

  // Fetch campaign posts periodically when active
  useEffect(() => {
    if (token && activeView === 'campaigns') {
      fetchCampaignPosts(true);
      const interval = setInterval(() => {
        fetchCampaignPosts(false);
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [token, activeView]);

  // Handler functions
    const fetchCampaignPosts = async (collapseIfHasData = false) => {
    if (!token) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/marketing/`);
      if (res.ok) {
        const data = await res.json();
        setCampaignPosts(data);
        if (collapseIfHasData && data && data.length > 0) {
          setIsGeneratorExpanded(false);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

    const handleLaunchCampaign = async () => {
    if (!campaignTopic) return;
    if (campaignDays < 1 || campaignDays > 30) {
      alert("You can schedule up to 30 days at a time.");
      return;
    }
    setLoading(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/marketing/campaign`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: campaignTopic,
          days: campaignDays,
          platforms: campaignPlatforms,
          text_provider: textProvider === 'auto' ? undefined : textProvider,
          text_model: textProvider === 'auto' ? undefined : textModel,
          image_provider: imageProvider,
          video_provider: videoProvider,
          generate_images: generateImages,
          generate_videos: ENABLE_IN_APP_VIDEO && generateVideos,
          generate_remotion: ENABLE_IN_APP_VIDEO && generateRemotion
        })
      });
      const data = await res.json();
      if (res.ok) {
        alert(`${campaignDays}-Day Marketing Campaign has been scheduled for generation! You can monitor progress in the AI Activity Feed.`);
        setCampaignTopic('');
        fetchCampaignPosts(true);
      } else {
        alert(`Error: ${data.detail || 'Failed to trigger campaign'}`);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

    const handleApprovePost = async (postId: string) => {
    try {
      const res = await fetchWithAuth(`${API_URL}/marketing/posts/${postId}/approve`, {
        method: 'POST'
      });
      if (res.ok) {
        fetchCampaignPosts();
        fetchData();
        alert('✅ Post approved and scheduled!\n\nTo publish immediately to Instagram/Facebook, click the "Publish Now" button on the post card. Make sure your Meta API key is configured in Settings → Integrations.');
      }
    } catch (e) {
      console.error(e);
    }
  };

    const handlePublishNow = async (postId: string) => {
    const post = campaignPosts.find(p => p.id === postId);
    const platform = (post?.platform || '').toLowerCase();
    const needsMeta = platform === 'instagram' || platform === 'facebook';
    const needsLinkedIn = platform === 'linkedin';

    // Check if the required credential is configured
    if (needsMeta && !configuredProviders.includes('meta')) {
      setPendingPublishPostId(postId);
      setIsMetaModalOpen(true);
      return;
    }
    if (needsLinkedIn && !configuredProviders.includes('linkedin')) {
      alert('LinkedIn API key is not configured.\n\nGo to Settings → Integrations → Social Media and follow the steps to connect your LinkedIn account.');
      return;
    }

    setPublishingPostId(postId);
    setPublishResult(null);
    try {
      const res = await fetchWithAuth(`${API_URL}/marketing/posts/${postId}/publish-now`, {
        method: 'POST'
      });
      const data = await res.json();
      if (res.ok) {
        setPublishResult({ success: true, message: `✅ Published successfully to ${platform}!` });
        fetchCampaignPosts();
        fetchData();
      } else {
        setPublishResult({ success: false, message: `❌ Publish failed: ${data.detail || 'Unknown error. Check activity logs.'}` });
      }
    } catch (e) {
      setPublishResult({ success: false, message: '❌ Network error. Could not reach the server.' });
      console.error(e);
    } finally {
      setPublishingPostId(null);
    }
  };

    const handleSaveMetaTokenAndPublish = async () => {
    if (!metaTokenInput.trim()) return;
    setSavingMetaToken(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/commands/keys`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: 'meta', key: metaTokenInput.trim() })
      });
      if (res.ok) {
        setMetaTokenInput('');
        setIsMetaModalOpen(false);
        await fetchData(); // refresh configuredProviders
        // Now attempt publish with the newly saved key
        if (pendingPublishPostId) {
          const postId = pendingPublishPostId;
          setPendingPublishPostId(null);
          await handlePublishNow(postId);
        }
      } else {
        const data = await res.json();
        alert(`Failed to save Meta token: ${data.detail || 'Unknown error'}`);
      }
    } catch (e) {
      console.error(e);
      alert('Network error saving Meta token.');
    } finally {
      setSavingMetaToken(false);
    }
  };

    const handleRejectPost = async (postId: string) => {
    try {
      const res = await fetchWithAuth(`${API_URL}/marketing/posts/${postId}/reject`, {
        method: 'POST'
      });
      if (res.ok) {
        fetchCampaignPosts();
        fetchData();
      }
    } catch (e) {
      console.error(e);
    }
  };

    const handleApproveAll = async () => {
    try {
      const res = await fetchWithAuth(`${API_URL}/marketing/posts/approve-all`, {
        method: 'POST'
      });
      if (res.ok) {
        alert("All pending campaign posts have been approved and scheduled!");
        fetchCampaignPosts();
        fetchData();
      }
    } catch (e) {
      console.error(e);
    }
  };

    const handleBulkSchedule = async () => {
    if (!bulkStartDate || !bulkEndDate || !bulkPostingTime) {
      alert("Please fill in all bulk scheduling details.");
      return;
    }
    setBulkScheduling(true);
    try {
      const startDateTimeStr = `${bulkStartDate}T${bulkPostingTime}:00`;
      const endDateTimeStr = `${bulkEndDate}T${bulkPostingTime}:00`;

      const res = await fetchWithAuth(`${API_URL}/marketing/posts/bulk-schedule`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start_date: new Date(startDateTimeStr).toISOString(),
          end_date: new Date(endDateTimeStr).toISOString(),
          posting_time: bulkPostingTime
        })
      });
      const data = await res.json();
      if (res.ok) {
        setIsBulkScheduleOpen(false);
        fetchCampaignPosts();
        fetchData();
        alert(`✅ Campaign scheduled successfully!\n${data.message}`);
      } else {
        alert(`Error: ${data.detail || 'Failed to bulk schedule campaign'}`);
      }
    } catch (e) {
      console.error(e);
      alert("Network error bulk scheduling campaign posts.");
    } finally {
      setBulkScheduling(false);
    }
  };

    const handleSavePostEdit = async (postId: string) => {
    try {
      const post = campaignPosts.find(p => p.id === postId);
      if (!post) return;
      const res = await fetchWithAuth(`${API_URL}/marketing/posts/${postId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          platform: post.platform,
          content: editingContent,
          image_url: editingImageUrl || null,
          video_url: editingVideoUrl || null,
          scheduled_at: editingScheduledAt ? new Date(editingScheduledAt).toISOString() : null,
          image_prompt: editingImagePrompt || null,
          image_prompt_enabled: editingImagePromptEnabled,
          video_prompt: editingVideoPrompt || null,
          video_prompt_enabled: editingVideoPromptEnabled,
          remotion_prompt: editingRemotionPrompt || null,
          remotion_prompt_enabled: editingRemotionPromptEnabled,
          is_manual_media: editingIsManualMedia,
        })
      });
      if (res.ok) {
        setEditingPostId(null);
        fetchCampaignPosts();
        fetchData();
      } else {
        const data = await res.json();
        alert(`Error saving post: ${data.detail || 'Unknown error'}`);
      }
    } catch (e) {
      console.error(e);
      alert("Network error saving post edits.");
    }
  };

    const formatForDatetimeLocal = (dateStr: string | null) => {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return '';
      const pad = (n: number) => n.toString().padStart(2, '0');
      const yyyy = d.getFullYear();
      const mm = pad(d.getMonth() + 1);
      const dd = pad(d.getDate());
      const hh = pad(d.getHours());
      const min = pad(d.getMinutes());
      return `${yyyy}-${mm}-${dd}T${hh}:${min}`;
    } catch (e) {
      return '';
    }
  };

    const startEditing = (post: any) => {
    setEditingPostId(post.id);
    setEditingContent(post.content);
    setEditingImageUrl(post.image_url || '');
    setEditingVideoUrl(post.video_url || '');
    setEditingImagePrompt(post.image_prompt || '');
    setEditingImagePromptEnabled(post.image_prompt_enabled || false);
    setEditingVideoPrompt(post.video_prompt || '');
    setEditingVideoPromptEnabled(post.video_prompt_enabled || false);
    setEditingRemotionPrompt(post.remotion_prompt || '');
    setEditingRemotionPromptEnabled(post.remotion_prompt_enabled || false);
    setEditingIsManualMedia(post.is_manual_media || false);
    setEditingScheduledAt(formatForDatetimeLocal(post.scheduled_at));
  };

    const handleFileUpload = async (file: File, isEditing: boolean) => {
    setUploadingFile(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetchWithAuth(`${API_URL}/marketing/upload-media`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (res.ok && data.url) {
        if (isEditing) {
          if (file.type.startsWith('video/')) {
            setEditingVideoUrl(data.url);
            setEditingImageUrl('');
          } else {
            setEditingImageUrl(data.url);
            setEditingVideoUrl('');
          }
          setEditingIsManualMedia(true);
        } else {
          if (file.type.startsWith('video/')) {
            setCreatePostVideoUrl(data.url);
            setCreatePostImageUrl('');
          } else {
            setCreatePostImageUrl(data.url);
            setCreatePostVideoUrl('');
          }
          setCreatePostIsManualMedia(true);
        }
      } else {
        alert(`Upload failed: ${data.detail || 'Unknown error'}`);
      }
    } catch (e) {
      console.error(e);
      alert("Network error uploading file.");
    } finally {
      setUploadingFile(false);
    }
  };

    const handleGenerateMedia = async (postId: string, mediaType: 'image' | 'video' | 'remotion', customPrompt: string) => {
    if (!customPrompt) {
      alert("Please enter a media prompt first.");
      return;
    }
    setGeneratingMedia(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/marketing/posts/${postId}/generate-media`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          media_type: mediaType,
          prompt: customPrompt,
          provider: mediaType === 'video' ? videoProvider : imageProvider
        })
      });
      const data = await res.json();
      if (res.ok) {
        if (mediaType === 'video') {
          setEditingVideoUrl(data.video_url || '');
          setEditingImageUrl('');
          setEditingVideoPrompt(data.video_prompt || '');
          setEditingVideoPromptEnabled(true);
        } else if (mediaType === 'remotion') {
          setEditingVideoUrl(data.video_url || '');
          setEditingImageUrl('');
          setEditingRemotionPrompt(data.remotion_prompt || customPrompt);
          setEditingRemotionPromptEnabled(true);
        } else {
          setEditingImageUrl(data.image_url || '');
          setEditingVideoUrl('');
          setEditingImagePrompt(data.image_prompt || '');
          setEditingImagePromptEnabled(true);
        }
        setEditingIsManualMedia(false);
        fetchCampaignPosts();
        alert("✅ Media successfully generated and updated via AI!");
      } else {
        const errData = await res.json().catch(() => ({}));
        alert(`Media generation failed: ${errData.detail || data.detail || 'Unknown error'}`);
      }
    } catch (e) {
      console.error(e);
      alert("Network error generating media.");
    } finally {
      setGeneratingMedia(false);
    }
  };

    const handleSuggestPrompt = async (content: string, mediaType: 'image' | 'video', isEditing: boolean) => {
    if (!content) {
      alert("Please enter post content first so AI can suggest a matching prompt.");
      return;
    }
    setSuggestingPrompt(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/marketing/suggest-prompt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, media_type: mediaType })
      });
      const data = await res.json();
      if (res.ok && data.prompt) {
        if (isEditing) {
          if (mediaType === 'image') {
            setEditingImagePrompt(data.prompt);
            setEditingImagePromptEnabled(true);
          } else if (mediaType === 'video') {
            setEditingVideoPrompt(data.prompt);
            setEditingVideoPromptEnabled(true);
          } else {
            setEditingRemotionPrompt(data.prompt);
            setEditingRemotionPromptEnabled(true);
          }
        } else {
          if (mediaType === 'image') {
            setCreatePostImagePrompt(data.prompt);
            setCreatePostImagePromptEnabled(true);
          } else if (mediaType === 'video') {
            setCreatePostVideoPrompt(data.prompt);
            setCreatePostVideoPromptEnabled(true);
          } else {
            setCreatePostRemotionPrompt(data.prompt);
            setCreatePostRemotionPromptEnabled(true);
          }
        }
      } else {
        alert(`Failed to suggest prompt: ${data.detail || 'Unknown error'}`);
      }
    } catch (e) {
      console.error(e);
      alert("Network error suggesting prompt.");
    } finally {
      setSuggestingPrompt(false);
    }
  };

    const renderPostCard = (post: any) => {
    const isEditing = editingPostId === post.id;
    const hasVideo = !!post.video_url;
    const hasImage = !!post.image_url;

    let platformColor = 'bg-blue-500/10 text-blue-400 border-blue-500/20';
    let borderAccent = 'border-l-4 border-l-blue-500';
    if (post.platform === 'instagram') {
      platformColor = 'bg-pink-500/10 text-pink-400 border-pink-500/20';
      borderAccent = 'border-l-4 border-l-pink-500';
    } else if (post.platform === 'facebook') {
      platformColor = 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20';
      borderAccent = 'border-l-4 border-l-indigo-500';
    }

    let statusColor = 'bg-amber-500/10 text-amber-400 border-amber-500/20';
    if (post.approval_status === 'approved' || post.approval_status === 'scheduled') {
      statusColor = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    }
    if (post.approval_status === 'published') {
      statusColor = 'bg-blue-500/10 text-blue-400 border-blue-500/20';
    }
    if (post.approval_status === 'rejected') {
      statusColor = 'bg-rose-500/10 text-rose-455 border-rose-500/20';
    }

    return (
      <Card key={post.id} className={`glass-panel border-gray-800/80 hover:border-violet-500/40 hover:shadow-violet-500/10 transition-all duration-300 flex flex-col justify-between overflow-hidden rounded-2xl shadow-xl ${borderAccent} bg-gray-950/20`}>
        <div>
          {/* Card Header */}
          <div className="flex items-center justify-between border-b border-gray-805 px-4 py-3 bg-gray-950/40">
            <div className="flex items-center gap-2">
              <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase border ${platformColor}`}>
                {post.platform}
              </span>
              <span className="text-xs font-extrabold text-gray-400">Day {post.day}</span>
            </div>
            <span className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase ${statusColor}`}>
              {post.approval_status}
            </span>
          </div>

          {/* Card Body */}
          <div className="p-4 space-y-4">
            {isEditing ? (
              <div className="space-y-4 animate-in fade-in duration-200">
                <div>
                  <label className="text-[10px] font-bold text-gray-405 uppercase tracking-wider block">Post Text Content</label>
                  <Textarea
                    className="bg-gray-900/60 border-gray-850 text-white focus:border-violet-500 focus:ring-violet-500/20 rounded-xl text-sm min-h-[100px] mt-1"
                    value={editingContent}
                    onChange={e => setEditingContent(e.target.value)}
                  />
                </div>

                <div>
                  <label className="text-[10px] font-bold text-gray-405 uppercase tracking-wider block">Scheduled Date & Time</label>
                  <Input
                    type="datetime-local"
                    className="bg-gray-900/60 border-gray-850 text-white focus:border-violet-500 rounded-xl text-sm mt-1"
                    value={editingScheduledAt}
                    onChange={e => setEditingScheduledAt(e.target.value)}
                  />
                </div>

                {/* Upload Media Section */}
                <div className="bg-gray-950/40 border border-gray-850 rounded-2xl p-3 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-gray-300">Media Content</span>
                    <span className={`text-[9px] font-bold border px-2 py-0.5 rounded-full ${
                      editingIsManualMedia 
                        ? 'bg-emerald-500/10 text-emerald-450 border-emerald-500/20' 
                        : 'bg-violet-500/10 text-violet-405 border-violet-500/20'
                    }`}>
                      {editingIsManualMedia ? "Manual Upload" : "AI Generated"}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <input
                        type="file"
                        accept="image/*"
                        className="hidden"
                        id={`edit-image-upload-${post.id}`}
                        onChange={e => {
                          const file = e.target.files?.[0];
                          if (file) handleFileUpload(file, true);
                        }}
                      />
                      <Button
                        type="button"
                        variant="outline"
                        disabled={uploadingFile}
                        onClick={() => document.getElementById(`edit-image-upload-${post.id}`)?.click()}
                        className="w-full h-9 rounded-xl text-xs border-gray-855 hover:bg-gray-800 hover:text-white bg-transparent flex items-center justify-center gap-1.5"
                      >
                        <ImageIcon size={13} className="text-violet-400" />
                        {uploadingFile ? "Upload Image" : "Upload Image"}
                      </Button>
                    </div>

                    <div>
                      <input
                        type="file"
                        accept="video/*"
                        className="hidden"
                        id={`edit-video-upload-${post.id}`}
                        onChange={e => {
                          const file = e.target.files?.[0];
                          if (file) handleFileUpload(file, true);
                        }}
                      />
                      <Button
                        type="button"
                        variant="outline"
                        disabled={uploadingFile}
                        onClick={() => document.getElementById(`edit-video-upload-${post.id}`)?.click()}
                        className="w-full h-9 rounded-xl text-xs border-gray-855 hover:bg-gray-800 hover:text-white bg-transparent flex items-center justify-center gap-1.5"
                      >
                        <Film size={13} className="text-violet-400" />
                        {uploadingFile ? "Upload Video" : "Upload Video"}
                      </Button>
                    </div>
                  </div>

                  {/* Direct URLs inputs */}
                  <div className="space-y-2 pt-1.5 border-t border-gray-850">
                    <div>
                      <label className="text-[9px] font-bold text-gray-500 uppercase tracking-wider">Direct Image URL</label>
                      <Input
                        type="text"
                        placeholder="https://..."
                        className="bg-gray-900/40 border-gray-855 text-white focus:border-violet-500 rounded-xl h-7 text-[11px] mt-0.5"
                        value={editingImageUrl}
                        onChange={e => {
                          setEditingImageUrl(e.target.value);
                          if (e.target.value) {
                            setEditingVideoUrl('');
                            setEditingIsManualMedia(false);
                          }
                        }}
                      />
                    </div>
                    <div>
                      <label className="text-[9px] font-bold text-gray-500 uppercase tracking-wider">Direct Video URL</label>
                      <Input
                        type="text"
                        placeholder="https://..."
                        className="bg-gray-900/40 border-gray-855 text-white focus:border-violet-500 rounded-xl h-7 text-[11px] mt-0.5"
                        value={editingVideoUrl}
                        onChange={e => {
                          setEditingVideoUrl(e.target.value);
                          if (e.target.value) {
                            setEditingImageUrl('');
                            setEditingIsManualMedia(false);
                          }
                        }}
                      />
                    </div>
                  </div>
                </div>

                {/* AI Prompt Tool Selector */}
                <div className="bg-gray-950/40 border border-gray-850 rounded-2xl p-3.5 space-y-3">
                  <div className="flex flex-col gap-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-bold text-gray-305">Generation Prompt Options</label>
                      <span className="text-[9px] text-gray-500">Save instructions locally</span>
                    </div>
                    <Select
                      value={editingImagePromptEnabled ? "image" : editingVideoPromptEnabled ? "video" : editingRemotionPromptEnabled ? "remotion" : "none"}
                      onValueChange={(val) => {
                        if (val === "image") {
                          setEditingImagePromptEnabled(true);
                          setEditingVideoPromptEnabled(false);
                          setEditingRemotionPromptEnabled(false);
                        } else if (val === "video") {
                          setEditingImagePromptEnabled(false);
                          setEditingVideoPromptEnabled(true);
                          setEditingRemotionPromptEnabled(false);
                        } else if (val === "remotion") {
                          setEditingImagePromptEnabled(false);
                          setEditingVideoPromptEnabled(false);
                          setEditingRemotionPromptEnabled(true);
                        } else {
                          setEditingImagePromptEnabled(false);
                          setEditingVideoPromptEnabled(false);
                          setEditingRemotionPromptEnabled(false);
                        }
                      }}
                    >
                      <SelectTrigger className="h-9 bg-gray-900/60 border-gray-850 text-white rounded-xl text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-gray-900 border-gray-850 text-white">
                        <SelectItem value="none">None (No prompt attachment)</SelectItem>
                        <SelectItem value="image">Image Prompt (For AI Graphics)</SelectItem>
                        {ENABLE_IN_APP_VIDEO && <SelectItem value="video">Video Prompt (For AI Video loops)</SelectItem>}
                        {ENABLE_IN_APP_VIDEO && <SelectItem value="remotion">Remotion Video Prompt (For Code-based Video)</SelectItem>}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Image Prompt Section */}
                  {editingImagePromptEnabled && (
                    <div className="space-y-2 pt-2 border-t border-gray-900 animate-in fade-in duration-200">
                      <label className="text-[10px] font-bold text-violet-400 uppercase tracking-wider block">Image Generation Prompt</label>
                      <Textarea
                        placeholder="Describe image to generate or click suggest"
                        className="bg-gray-900/60 border-gray-800 text-white focus:border-violet-500 focus:ring-violet-500/20 rounded-xl text-xs min-h-[60px]"
                        value={editingImagePrompt}
                        onChange={e => setEditingImagePrompt(e.target.value)}
                      />
                      <div className="flex gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={suggestingPrompt}
                          onClick={() => handleSuggestPrompt(editingContent || post.content, 'image', true)}
                          className="flex-1 h-8 rounded-lg text-xs font-semibold border-gray-855 hover:bg-gray-800 hover:text-white bg-transparent text-gray-305 disabled:opacity-50"
                        >
                          {suggestingPrompt ? "Suggesting..." : "🪄 Suggest Prompt"}
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          disabled={generatingMedia || !editingImagePrompt}
                          onClick={() => handleGenerateMedia(post.id, 'image', editingImagePrompt)}
                          className="flex-1 h-8 rounded-lg text-xs font-semibold bg-violet-650 hover:bg-violet-600 text-white disabled:opacity-50"
                        >
                          {generatingMedia ? "Generating..." : "Generate AI Image"}
                        </Button>
                      </div>
                    </div>
                  )}

                  {/* Video Prompt Section */}
                  {ENABLE_IN_APP_VIDEO && editingVideoPromptEnabled && (
                    <div className="space-y-2 pt-2 border-t border-gray-900 animate-in fade-in duration-200">
                      <label className="text-[10px] font-bold text-indigo-405 uppercase tracking-wider block">Video Generation Prompt</label>
                      <Textarea
                        placeholder="Describe video loop to generate or click suggest"
                        className="bg-gray-900/60 border-gray-805 text-white focus:border-indigo-500 focus:ring-indigo-500/20 rounded-xl text-xs min-h-[60px]"
                        value={editingVideoPrompt}
                        onChange={e => setEditingVideoPrompt(e.target.value)}
                      />
                      <div className="flex gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={suggestingPrompt}
                          onClick={() => handleSuggestPrompt(editingContent || post.content, 'video', true)}
                          className="flex-1 h-8 rounded-lg text-xs font-semibold border-gray-855 hover:bg-gray-800 hover:text-white bg-transparent text-gray-305 disabled:opacity-50"
                        >
                          {suggestingPrompt ? "Suggesting..." : "🪄 Suggest Prompt"}
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          disabled={generatingMedia || !editingVideoPrompt}
                          onClick={() => handleGenerateMedia(post.id, 'video', editingVideoPrompt)}
                          className="flex-1 h-8 rounded-lg text-xs font-semibold bg-indigo-650 hover:bg-indigo-600 text-white disabled:opacity-50"
                        >
                          {generatingMedia ? "Generating..." : "Generate AI Video"}
                        </Button>
                      </div>
                    </div>
                  )}

                  {/* Remotion Prompt Section */}
                  {ENABLE_IN_APP_VIDEO && editingRemotionPromptEnabled && (
                    <div className="space-y-2 pt-2 border-t border-gray-900 animate-in fade-in duration-200">
                      <label className="text-[10px] font-bold text-blue-405 uppercase tracking-wider block">Remotion Generation Prompt</label>
                      <Textarea
                        placeholder="Describe code-based video loop to generate or click suggest"
                        className="bg-gray-900/60 border-gray-805 text-white focus:border-blue-500 focus:ring-blue-500/20 rounded-xl text-xs min-h-[60px]"
                        value={editingRemotionPrompt}
                        onChange={e => setEditingRemotionPrompt(e.target.value)}
                      />
                      <div className="flex gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={suggestingPrompt}
                          onClick={() => handleSuggestPrompt(editingContent || post.content, 'video', true)}
                          className="flex-1 h-8 rounded-lg text-xs font-semibold border-gray-855 hover:bg-gray-800 hover:text-white bg-transparent text-gray-305 disabled:opacity-50"
                        >
                          {suggestingPrompt ? "Suggesting..." : "🪄 Suggest Prompt"}
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          disabled={generatingMedia || !editingRemotionPrompt}
                          onClick={() => handleGenerateMedia(post.id, 'remotion', editingRemotionPrompt)}
                          className="flex-1 h-8 rounded-lg text-xs font-semibold bg-blue-650 hover:bg-blue-600 text-white disabled:opacity-50"
                        >
                          {generatingMedia ? "Generating..." : "Generate Remotion"}
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <>
                <p className="text-xs text-gray-305 whitespace-pre-wrap leading-relaxed">
                  {post.content}
                </p>
                
                {/* Visual preview */}
                {hasVideo ? (
                  <div className="relative rounded-xl overflow-hidden border border-gray-800/80 shadow-2xl group mt-3 aspect-video">
                    <video
                      src={post.video_url}
                      controls
                      loop
                      muted
                      className="w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-500"
                    />
                    <div className="absolute top-2.5 left-2.5 bg-black/75 text-white rounded-full px-2.5 py-1 text-[9px] font-bold flex items-center gap-1.5 border border-white/10 backdrop-blur-md">
                      <Film size={10} className={post.is_manual_media ? "text-emerald-400" : "text-violet-405"} />
                      {post.is_manual_media ? "Manual Video" : "AI Video Loop"}
                    </div>
                  </div>
                ) : hasImage ? (
                  post.image_url?.startsWith('error:') ? (
                    <div className="rounded-xl border border-rose-955 bg-rose-950/20 px-4 py-3 flex items-start gap-3 mt-3 shadow-inner">
                      <div className="text-rose-455 mt-0.5 shrink-0">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                      </div>
                      <div>
                        <p className="text-[10px] font-bold text-rose-455 uppercase tracking-wider mb-0.5">Image Generation Error</p>
                        <p className="text-[11px] text-rose-300 leading-relaxed">{post.image_url.replace(/^error:/, '')}</p>
                      </div>
                    </div>
                  ) : (
                    <div className="relative rounded-xl overflow-hidden border border-gray-800/80 shadow-2xl group mt-3 aspect-video">
                      <img
                        src={post.image_url}
                        alt="Graphic preview"
                        className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                      />
                      <div className="absolute top-2.5 left-2.5 bg-black/75 text-white rounded-full px-2.5 py-1 text-[9px] font-bold flex items-center gap-1.5 border border-white/10 backdrop-blur-md">
                        <ImageIcon size={10} className={post.is_manual_media ? "text-emerald-400" : "text-violet-405"} />
                        {post.is_manual_media ? "Manual Graphic" : "AI Graphic"}
                      </div>
                    </div>
                  )
                ) : null}

                {/* Local Attached Image Prompt Alert Section */}
                {post.image_prompt_enabled && post.image_prompt && (
                  <div className="mt-3.5 p-3 rounded-xl border border-violet-900/30 bg-violet-955/20 text-xs animate-in fade-in duration-200">
                    <div className="flex items-center gap-1.5 text-violet-455 font-extrabold mb-1">
                      <span>🖼️</span> Image Prompt (Local Only)
                    </div>
                    <p className="text-gray-305 italic text-[11px] leading-relaxed">"{post.image_prompt}"</p>
                  </div>
                )}

                {/* Local Attached Video Prompt Alert Section */}
                {post.video_prompt_enabled && post.video_prompt && (
                  <div className="mt-3.5 p-3 rounded-xl border border-indigo-900/30 bg-indigo-955/20 text-xs animate-in fade-in duration-200">
                    <div className="flex items-center gap-1.5 text-indigo-405 font-extrabold mb-1">
                      <span>🎥</span> Video Prompt (Local Only)
                    </div>
                    <p className="text-gray-305 italic text-[11px] leading-relaxed">"{post.video_prompt}"</p>
                  </div>
                )}

                {/* Scheduled Date/Time Badge */}
                {post.scheduled_at && (
                  <div className="mt-3.5 flex items-center gap-1.5 text-xs text-gray-300 bg-gray-900/60 border border-gray-800 px-3 py-2 rounded-xl">
                    <Calendar size={12} className="text-violet-400" />
                    <span>Scheduled: {new Date(post.scheduled_at).toLocaleString()}</span>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Card Footer Actions */}
        <div className="border-t border-gray-850 px-4 py-3 bg-gray-950/30 flex gap-2 justify-end items-center min-h-[52px]">
          {isEditing ? (
            <>
              <Button 
                size="sm" 
                variant="outline" 
                onClick={() => setEditingPostId(null)}
                className="h-8 px-3.5 rounded-lg text-xs font-semibold text-gray-400 border-gray-855 hover:bg-gray-800 hover:text-white bg-transparent"
              >
                Cancel
              </Button>
              <Button 
                size="sm" 
                onClick={() => handleSavePostEdit(post.id)}
                className="h-8 px-3.5 rounded-lg text-xs font-semibold bg-violet-650 hover:bg-violet-600 text-white"
              >
                Save Changes
              </Button>
            </>
          ) : (
            <>
              <Button 
                size="sm" 
                variant="outline" 
                onClick={() => startEditing(post)}
                className="h-8 px-3 rounded-lg text-xs font-semibold text-gray-350 hover:bg-gray-850 hover:text-white border-gray-850 bg-transparent flex items-center gap-1"
              >
                <Edit2 size={11} /> Edit
              </Button>
              
              {post.approval_status === 'pending' && (
                <>
                  <Button 
                    size="sm" 
                    variant="outline" 
                    onClick={() => handleRejectPost(post.id)}
                    className="h-8 px-3 rounded-lg text-xs font-semibold text-rose-455 hover:bg-rose-955/20 border-rose-955 bg-transparent"
                  >
                    Reject
                  </Button>
                  <Button 
                    size="sm" 
                    onClick={() => handleApprovePost(post.id)}
                    className="h-8 px-3 rounded-lg text-xs font-semibold bg-emerald-650 hover:bg-emerald-600 text-white"
                  >
                    Approve
                  </Button>
                </>
              )}

              {(post.approval_status === 'approved' || post.approval_status === 'scheduled') && (
                <>
                  <Button 
                    size="sm" 
                    variant="outline" 
                    onClick={() => handleRejectPost(post.id)}
                    className="h-8 px-3 rounded-lg text-xs font-semibold text-rose-455 hover:bg-rose-955/20 border-rose-955 bg-transparent"
                  >
                    Reject
                  </Button>
                  {(post.platform === 'instagram' || post.platform === 'facebook' || post.platform === 'linkedin') && (
                    <Button
                      size="sm"
                      onClick={() => handlePublishNow(post.id)}
                      disabled={publishingPostId === post.id}
                      className="h-8 px-3 rounded-lg text-xs font-semibold bg-gradient-to-r from-pink-650 to-rose-650 hover:from-pink-600 hover:to-rose-600 text-white shadow-md shadow-pink-500/10 disabled:opacity-50 flex items-center gap-1.5"
                    >
                      {publishingPostId === post.id ? (
                        <>
                          <span className="animate-spin inline-block w-3 h-3 border-2 border-white/30 border-t-white rounded-full" />
                          Publishing...
                        </>
                      ) : (
                        <>
                          <Send size={11} />
                          Publish Now
                        </>
                      )}
                    </Button>
                  )}
                </>
              )}

              {publishResult && publishingPostId === null && post.id === campaignPosts.find(p => p.approval_status === 'published')?.id && (
                <span className={`text-[10px] font-semibold ${
                  publishResult.success ? 'text-emerald-400' : 'text-rose-450'
                }`}>
                  {publishResult.message}
                </span>
              )}
            </>
          )}
        </div>
      </Card>
    );
  };

    const handleCreateManualPost = async () => {
    if (!createPostContent) {
      alert("Please enter post content.");
      return;
    }
    setCreatingPost(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/marketing/posts/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          platform: createPostPlatform,
          content: createPostContent,
          day: createPostDay,
          image_url: createPostImageUrl || null,
          video_url: createPostVideoUrl || null,
          image_prompt: createPostImagePrompt || null,
          image_prompt_enabled: createPostImagePromptEnabled,
          video_prompt: createPostVideoPrompt || null,
          video_prompt_enabled: createPostVideoPromptEnabled,
          remotion_prompt: createPostRemotionPrompt || null,
          remotion_prompt_enabled: createPostRemotionPromptEnabled,
          is_manual_media: createPostIsManualMedia,
          scheduled_at: createPostScheduledAt ? new Date(createPostScheduledAt).toISOString() : null,
        })
      });
      if (res.ok) {
        setIsCreatePostOpen(false);
        setCreatePostContent('');
        setCreatePostImageUrl('');
        setCreatePostVideoUrl('');
        setCreatePostImagePrompt('');
        setCreatePostImagePromptEnabled(false);
        setCreatePostVideoPrompt('');
        setCreatePostVideoPromptEnabled(false);
        setCreatePostRemotionPrompt('');
        setCreatePostRemotionPromptEnabled(false);
        setCreatePostIsManualMedia(false);
        setCreatePostScheduledAt('');
        fetchCampaignPosts();
        fetchData();
        alert("✅ Manual post created successfully as draft!");
      } else {
        const data = await res.json();
        alert(`Error: ${data.detail || 'Failed to create post'}`);
      }
    } catch (e) {
      console.error(e);
      alert("Network error creating manual post.");
    } finally {
      setCreatingPost(false);
    }
  };


  return (
    <>
            <div className="space-y-8 max-w-7xl mx-auto animate-in fade-in duration-300">
              {/* Header section with brand info and global actions */}
              <div className="flex flex-col gap-6 lg:flex-row lg:items-center justify-between border-b border-gray-800/80 pb-6">
                <div className="space-y-1.5">
                  <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20 text-[10px] font-bold tracking-wider uppercase">
                    ⚡ Autonomous Marketing Pipeline
                  </div>
                  <h1 className="text-4xl font-extrabold text-white tracking-tight flex items-center gap-2">
                    <Calendar className="text-violet-400 h-8 w-8" /> Campaign Planner & Review Board
                  </h1>
                  <p className="text-gray-400 text-sm leading-relaxed max-w-2xl">
                    Design and monitor multi-platform marketing timelines. Customize AI prompt templates, review generated post contents, and schedule live publishing.
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <Button 
                    onClick={() => setIsGeneratorExpanded(!isGeneratorExpanded)}
                    className="bg-gray-900 border border-gray-800 hover:bg-gray-800 hover:text-white text-gray-300 font-bold rounded-xl transition-all h-11 px-5 flex items-center gap-2"
                  >
                    <Sparkles className="text-violet-400 h-4 w-4 animate-pulse" />
                    {isGeneratorExpanded ? "Hide Settings" : "Configure AI Generator"}
                    {isGeneratorExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </Button>
                  <Button 
                    onClick={() => setIsCreatePostOpen(true)}
                    className="bg-gray-900 border border-gray-850 hover:bg-gray-800 hover:text-white text-gray-300 font-bold rounded-xl transition-all h-11 px-5 flex items-center gap-2"
                  >
                    <Plus size={14} className="text-violet-400" /> Create Manual Post
                  </Button>
                  {campaignPosts.length > 0 && (
                    <Button 
                      onClick={() => {
                        const start = new Date();
                        const end = new Date();
                        end.setDate(end.getDate() + 30);
                        setBulkStartDate(start.toISOString().split('T')[0]);
                        setBulkEndDate(end.toISOString().split('T')[0]);
                        setIsBulkScheduleOpen(true);
                      }}
                      className="bg-gray-900 border border-gray-850 hover:bg-gray-800 hover:text-white text-gray-300 font-bold rounded-xl transition-all h-11 px-5 flex items-center gap-2"
                    >
                      <Calendar className="text-violet-400" size={14} /> Bulk Schedule Campaign
                    </Button>
                  )}
                  {campaignPosts.length > 0 && (
                    <Button 
                      onClick={handleApproveAll} 
                      className="bg-gradient-to-r from-emerald-600 to-green-600 hover:from-emerald-500 hover:to-green-500 text-white font-bold rounded-xl shadow-lg shadow-emerald-500/25 hover:scale-[1.02] active:scale-95 transition-all h-11 px-5"
                    >
                      Approve &amp; Schedule All ({campaignPosts.filter(p => p.approval_status === 'pending').length} pending)
                    </Button>
                  )}
                </div>
              </div>

              {/* Dynamic Campaign Stats Row */}
              {campaignPosts.length > 0 && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 animate-in fade-in duration-500">
                  <div className="relative overflow-hidden glass-panel border-gray-850 p-5 rounded-2xl bg-gradient-to-br from-gray-900/40 via-gray-950/20 to-violet-950/10 flex items-center justify-between shadow-lg group">
                    <div className="absolute -right-4 -bottom-4 w-20 h-20 rounded-full bg-violet-500/5 blur-xl group-hover:bg-violet-500/10 transition-all duration-500" />
                    <div>
                      <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Total Schedule</p>
                      <h3 className="text-2xl font-extrabold text-white mt-1.5">{campaignPosts.length} Posts</h3>
                      <p className="text-[10px] text-gray-400 mt-1">Timeline active</p>
                    </div>
                    <div className="h-10 w-10 rounded-xl bg-violet-500/10 flex items-center justify-center border border-violet-500/20">
                      <CalendarRange className="text-violet-400 h-5 w-5" />
                    </div>
                  </div>
                  <div className="relative overflow-hidden glass-panel border-gray-850 p-5 rounded-2xl bg-gradient-to-br from-gray-900/40 via-gray-950/20 to-amber-950/10 flex items-center justify-between shadow-lg group">
                    <div className="absolute -right-4 -bottom-4 w-20 h-20 rounded-full bg-amber-500/5 blur-xl group-hover:bg-amber-500/10 transition-all duration-500" />
                    <div>
                      <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Pending Review</p>
                      <h3 className="text-2xl font-extrabold text-amber-400 mt-1.5">
                        {campaignPosts.filter(p => p.approval_status === 'pending').length} Drafts
                      </h3>
                      <p className="text-[10px] text-amber-500/70 mt-1">Requires approval</p>
                    </div>
                    <div className="h-10 w-10 rounded-xl bg-amber-500/10 flex items-center justify-center border border-amber-500/20">
                      <Clock className="text-amber-450 h-5 w-5 animate-pulse" />
                    </div>
                  </div>
                  <div className="relative overflow-hidden glass-panel border-gray-850 p-5 rounded-2xl bg-gradient-to-br from-gray-900/40 via-gray-950/20 to-emerald-950/10 flex items-center justify-between shadow-lg group">
                    <div className="absolute -right-4 -bottom-4 w-20 h-20 rounded-full bg-emerald-500/5 blur-xl group-hover:bg-emerald-500/10 transition-all duration-500" />
                    <div>
                      <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Approved &amp; Ready</p>
                      <h3 className="text-2xl font-extrabold text-emerald-400 mt-1.5">
                        {campaignPosts.filter(p => p.approval_status === 'approved' || p.approval_status === 'scheduled').length} Scheduled
                      </h3>
                      <p className="text-[10px] text-emerald-400/70 mt-1">Ready to auto-post</p>
                    </div>
                    <div className="h-10 w-10 rounded-xl bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20">
                      <Check className="text-emerald-400 h-5 w-5" />
                    </div>
                  </div>
                  <div className="relative overflow-hidden glass-panel border-gray-850 p-5 rounded-2xl bg-gradient-to-br from-gray-900/40 via-gray-950/20 to-blue-950/10 flex items-center justify-between shadow-lg group">
                    <div className="absolute -right-4 -bottom-4 w-20 h-20 rounded-full bg-blue-500/5 blur-xl group-hover:bg-blue-500/10 transition-all duration-500" />
                    <div>
                      <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Sent to Socials</p>
                      <h3 className="text-2xl font-extrabold text-blue-400 mt-1.5">
                        {campaignPosts.filter(p => p.approval_status === 'published').length} Active
                      </h3>
                      <p className="text-[10px] text-blue-400/70 mt-1">Outreach live</p>
                    </div>
                    <div className="h-10 w-10 rounded-xl bg-blue-500/10 flex items-center justify-center border border-blue-500/20">
                      <Send className="text-blue-450 h-5 w-5" />
                    </div>
                  </div>
                </div>
              )}

              {/* Collapsible Campaign Generator Panel */}
              {isGeneratorExpanded && (
                <Card className="glass-panel border-transparent glow-marketing rounded-3xl overflow-hidden shadow-2xl relative bg-gray-950/20 w-full animate-in slide-in-from-top duration-300">
                  <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-violet-500 to-transparent" />
                  <CardHeader className="flex flex-row items-center justify-between border-b border-gray-900/80 pb-4">
                    <div>
                      <CardTitle className="text-lg text-white font-extrabold tracking-tight">AI Campaign Generation Engine</CardTitle>
                      <CardDescription className="text-gray-400 text-xs mt-1">Configure your marketing objective. AI will automatically generate optimized post copywriting and layout structures.</CardDescription>
                    </div>
                    {campaignPosts.length > 0 && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setIsGeneratorExpanded(false)}
                        className="text-gray-400 hover:text-white"
                      >
                        <ChevronUp size={20} />
                      </Button>
                    )}
                  </CardHeader>
                  <CardContent className="space-y-6 pt-5">
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                      
                      {/* Left: Topic and Duration (7 cols) */}
                      <div className="lg:col-span-6 space-y-4">
                        <div className="flex flex-col gap-2">
                          <label className="text-xs font-semibold text-gray-300">Brand Context, website, topic or campaign ideas</label>
                          <Textarea
                            placeholder="e.g. 'Generate marketing posts for BlueBottle Cafe. Highlight our organic roast and friendly workspace vibes.'"
                            className="bg-gray-900/50 border-gray-850 text-white focus:border-violet-500 focus:ring-violet-500/20 rounded-xl min-h-[110px] text-sm"
                            value={campaignTopic}
                            onChange={e => setCampaignTopic(e.target.value)}
                          />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                          <div className="flex flex-col gap-2">
                            <label className="text-xs font-semibold text-gray-300">Duration (Days)</label>
                            <Input
                              type="number"
                              value={campaignDays}
                              onChange={e => setCampaignDays(parseInt(e.target.value) || 0)}
                              className="bg-gray-900/50 border-gray-850 text-white focus:border-violet-500 focus:ring-violet-500/20 rounded-xl h-10 text-sm"
                            />
                          </div>

                          <div className="flex flex-col gap-2">
                            <label className="text-xs font-semibold text-gray-300 block">Target Platforms</label>
                            <div className="flex flex-wrap gap-1.5 mt-1">
                              {['linkedin', 'instagram', 'facebook'].map(p => {
                                const isSelected = campaignPlatforms.includes(p);
                                return (
                                  <button
                                    key={p}
                                    type="button"
                                    onClick={() => {
                                      if (isSelected) {
                                        setCampaignPlatforms(campaignPlatforms.filter(x => x !== p));
                                      } else {
                                        setCampaignPlatforms([...campaignPlatforms, p]);
                                      }
                                    }}
                                    className={`px-3 py-1.5 rounded-xl text-[10px] font-bold border transition-all ${
                                      isSelected 
                                        ? 'bg-violet-650 border-violet-500 text-white shadow-lg shadow-violet-500/20 scale-[1.02]' 
                                        : 'bg-gray-900/40 border-gray-850 text-gray-450 hover:bg-gray-800 hover:text-white'
                                    }`}
                                  >
                                    {p.toUpperCase()}
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Right: AI Pipeline settings (6 cols) */}
                      <div className="lg:col-span-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="space-y-4">
                          <div className="flex flex-col gap-1.5">
                            <label className="text-xs font-semibold text-gray-300">Copywriting Model Provider</label>
                            <Select value={textProvider} onValueChange={(val) => {
                              if (val) {
                                setTextProvider(val);
                                if (val === 'gemini') setTextModel('gemini-2.5-flash');
                                else if (val === 'openai') setTextModel('gpt-4o');
                                else if (val === 'anthropic') setTextModel('claude-sonnet-4-6');
                                else if (val === 'grok') setTextModel('grok-2');
                                else if (val === 'auto') setTextModel('');
                              }
                            }}>
                              <SelectTrigger className="h-9 bg-gray-900/50 border-gray-850 text-white text-xs rounded-xl"><SelectValue /></SelectTrigger>
                              <SelectContent className="bg-gray-900 border-gray-850 text-white">
                                <SelectItem value="auto">Auto (AI Choice)</SelectItem>
                                <SelectItem value="gemini">Google Gemini</SelectItem>
                                <SelectItem value="openai">OpenAI GPT</SelectItem>
                                <SelectItem value="anthropic">Anthropic Claude</SelectItem>
                                <SelectItem value="grok">xAI Grok</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>

                          {textProvider !== 'auto' && (
                            <div className="flex flex-col gap-1.5">
                              <label className="text-xs font-semibold text-gray-300">Copywriting Sub-model</label>
                            <Select value={textModel} onValueChange={(val) => val && setTextModel(val)}>
                              <SelectTrigger className="h-9 bg-gray-900/50 border-gray-850 text-white text-xs rounded-xl"><SelectValue /></SelectTrigger>
                              <SelectContent className="bg-gray-900 border-gray-850 text-white">
                                {textProvider === 'gemini' && (
                                  <>
                                    <SelectItem value="gemini-2.5-flash">Gemini 2.5 Flash (Recommended, Cheap)</SelectItem>
                                    <SelectItem value="gemini-2.5-pro">Gemini 2.5 Pro (Deep context, creative)</SelectItem>
                                    <SelectItem value="gemini-2.0-flash">Gemini 2.0 Flash (High speed)</SelectItem>
                                    <SelectItem value="gemini-2.0-flash-lite">Gemini 2.0 Flash Lite (Lowest cost)</SelectItem>
                                    <SelectItem value="gemini-1.5-flash">Gemini 1.5 Flash (Legacy flash)</SelectItem>
                                    <SelectItem value="gemini-1.5-pro">Gemini 1.5 Pro (Legacy pro)</SelectItem>
                                  </>
                                )}
                                {textProvider === 'openai' && (
                                  <>
                                    <SelectItem value="gpt-4o">GPT-4o (High reasoning copywriter)</SelectItem>
                                    <SelectItem value="gpt-4o-mini">GPT-4o mini (Fast &amp; cost-efficient)</SelectItem>
                                  </>
                                )}
                                {textProvider === 'anthropic' && (
                                  <>
                                    <SelectItem value="claude-sonnet-4-6">Claude 3.5 Sonnet (Premium copy)</SelectItem>
                                    <SelectItem value="claude-haiku-4-5-20251001">Claude 3.5/4.5 Haiku (Fast, low-cost)</SelectItem>
                                    <SelectItem value="claude-opus-4-8">Claude 3.5 Opus (Advanced logic)</SelectItem>
                                  </>
                                )}
                                {textProvider === 'grok' && (
                                  <SelectItem value="grok-2">Grok 2 (Social expert)</SelectItem>
                                )}
                              </SelectContent>
                            </Select>
                            <span className="text-[10px] text-gray-500 italic mt-0.5 leading-relaxed">
                              {textModel.includes("mini") || textModel.includes("flash") || textModel.includes("haiku")
                                ? "💡 Haiku and Flash models consume less token credit with excellent conversational quality."
                                : "🚀 Pro & Sonnet models provide deep brand logic and advanced wordplay."}
                            </span>
                          </div>
                          )}
                        </div>

                        <div className="space-y-4 bg-gray-900/10 border border-gray-850 p-3.5 rounded-2xl">
                          {/* Image Settings */}
                          <div className="space-y-2">
                            <div className="flex items-center justify-between">
                              <div className="flex flex-col">
                                <span className="text-xs font-semibold text-gray-300">Generate Custom Images</span>
                                <span className="text-[10px] text-gray-500">Inject AI graphic assets</span>
                              </div>
                              <input 
                                type="checkbox" 
                                checked={generateImages} 
                                onChange={e => setGenerateImages(e.target.checked)}
                                className="h-4 w-4 rounded border-gray-805 bg-gray-950 text-violet-605 focus:ring-violet-500/20"
                              />
                            </div>

                            {generateImages && (
                              <div className="flex flex-col gap-1 pl-3 border-l-2 border-violet-500/30 animate-in slide-in-from-left duration-200">
                                <label className="text-[9px] font-semibold text-gray-455">Image Generation Engine</label>
                                <Select value={imageProvider} onValueChange={(val) => val && setImageProvider(val)}>
                                  <SelectTrigger className="h-8 bg-gray-900/50 border-gray-850 text-white text-xs rounded-xl"><SelectValue /></SelectTrigger>
                                  <SelectContent className="bg-gray-900 border-gray-850 text-white">
                                    <SelectItem value="openai">OpenAI DALL-E 3 (Recommended)</SelectItem>
                                    <SelectItem value="gemini">Google Imagen 4 (Gemini)</SelectItem>
                                    <SelectItem value="stability">Stability AI SDXL</SelectItem>
                                    <SelectItem value="grok">xAI Grok-2 Image Gen</SelectItem>
                                    <SelectItem value="anthropic">Anthropic (via DALL-E 3)</SelectItem>
                                  </SelectContent>
                                </Select>
                              </div>
                            )}
                          </div>

{ENABLE_IN_APP_VIDEO && (
<>
                          {/* Video Settings */}
                          <div className="space-y-2 border-t border-gray-850 pt-2">
                            <div className="flex items-center justify-between">
                              <div className="flex flex-col">
                                <span className="text-xs font-semibold text-gray-300">Generate Video Loops</span>
                                <span className="text-[10px] text-gray-500">Create cinemagraph loops</span>
                              </div>
                              <input 
                                type="checkbox" 
                                checked={generateVideos} 
                                onChange={e => setGenerateVideos(e.target.checked)}
                                className="h-4 w-4 rounded border-gray-805 bg-gray-950 text-violet-605 focus:ring-violet-500/20"
                              />
                            </div>

                            {generateVideos && (
                              <div className="flex flex-col gap-1 pl-3 border-l-2 border-violet-500/30 animate-in slide-in-from-left duration-200">
                                <label className="text-[9px] font-semibold text-gray-455">Video Generation Engine</label>
                                <Select value={videoProvider} onValueChange={(val) => val && setVideoProvider(val)}>
                                  <SelectTrigger className="h-8 bg-gray-900/50 border-gray-850 text-white text-xs rounded-xl"><SelectValue /></SelectTrigger>
                                  <SelectContent className="bg-gray-900 border-gray-850 text-white">
                                    <SelectItem value="pika">Pika AI (Recommended)</SelectItem>
                                    <SelectItem value="stable_diffusion">Stable Diffusion Video</SelectItem>
                                    <SelectItem value="gemini">Google Veo (Mocked)</SelectItem>
                                    <SelectItem value="grok">Grok Video (Mocked)</SelectItem>
                                  </SelectContent>
                                </Select>
                              </div>
                            )}
                          </div>

                          {/* Remotion Settings */}
                          <div className="space-y-2 border-t border-gray-850 pt-2">
                            <div className="flex items-center justify-between">
                              <div className="flex flex-col">
                                <span className="text-xs font-semibold text-gray-300">Generate Remotion Videos</span>
                                <span className="text-[10px] text-gray-500">Create programmatic data-driven videos</span>
                              </div>
                              <input 
                                type="checkbox" 
                                checked={generateRemotion} 
                                onChange={e => setGenerateRemotion(e.target.checked)}
                                className="h-4 w-4 rounded border-gray-805 bg-gray-950 text-violet-605 focus:ring-violet-500/20"
                              />
                            </div>
                          </div>
</>
)}
                        </div>
                      </div>

                    </div>

                    <div className="flex justify-end gap-3 border-t border-gray-900 pt-4">
                      {campaignPosts.length > 0 && (
                        <Button
                          variant="outline"
                          onClick={() => setIsGeneratorExpanded(false)}
                          className="h-10 px-5 rounded-xl text-xs font-semibold text-gray-400 border-gray-850 hover:bg-gray-800 hover:text-white bg-transparent"
                        >
                          Cancel
                        </Button>
                      )}
                      <Button 
                        onClick={handleLaunchCampaign} 
                        disabled={loading || !campaignTopic} 
                        className="h-10 px-6 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-bold text-xs rounded-xl shadow-lg shadow-violet-500/20 hover:shadow-violet-500/30 transition-all hover:scale-[1.01] active:scale-95 disabled:opacity-50"
                      >
                        {loading ? 'Generating Timeline...' : `Launch ${campaignDays}-Day Campaign`}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Main Content Area */}
              {campaignPosts.length === 0 && (
                <Card className="glass-panel border-dashed border-gray-805/80 p-12 text-center flex flex-col items-center justify-center rounded-3xl min-h-[420px] shadow-2xl bg-gray-950/10">
                  <div className="text-5xl mb-4 animate-bounce">🗓️</div>
                  <h3 className="text-lg font-extrabold text-white tracking-tight">No active campaign posts</h3>
                  <p className="text-gray-400 max-w-sm mt-2 text-xs leading-relaxed">Configure your brand topic and AI model settings above to launch your automated timeline. Generated post schedules will populate here.</p>
                </Card>
              )}

              {campaignPosts.length > 0 && (
                <div className="space-y-6">
                  {/* Segmented Tab controls for Board Views */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-800 pb-4">
                    <div className="flex gap-1.5 bg-gray-950/40 p-1.5 rounded-2xl border border-gray-850">
                      <button
                        onClick={() => setCampaignViewMode('timeline')}
                        className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${
                          campaignViewMode === 'timeline'
                            ? 'bg-violet-650 text-white shadow-lg shadow-violet-500/10'
                            : 'text-gray-400 hover:text-white hover:bg-gray-900/60'
                        }`}
                      >
                        <CalendarRange size={14} /> Chronological Timeline
                      </button>
                      <button
                        onClick={() => setCampaignViewMode('kanban')}
                        className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${
                          campaignViewMode === 'kanban'
                            ? 'bg-violet-650 text-white shadow-lg shadow-violet-500/10'
                            : 'text-gray-400 hover:text-white hover:bg-gray-900/60'
                        }`}
                      >
                        <LayoutGrid size={14} /> Review Kanban Board
                      </button>
                      <button
                        onClick={() => setCampaignViewMode('analytics')}
                        className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${
                          campaignViewMode === 'analytics'
                            ? 'bg-violet-650 text-white shadow-lg shadow-violet-500/10'
                            : 'text-gray-400 hover:text-white hover:bg-gray-900/60'
                        }`}
                      >
                        <TrendingUp size={14} /> Campaign Analytics
                      </button>
                    </div>

                    {/* Filters bar */}
                    {campaignViewMode !== 'analytics' && (
                      <div className="flex flex-wrap items-center gap-3">
                        <div className="flex items-center gap-2 bg-gray-950/20 px-3 py-1.5 rounded-xl border border-gray-850">
                          <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Platform:</span>
                          <div className="flex gap-1">
                            {['all', 'linkedin', 'instagram', 'facebook'].map(plat => (
                              <button
                                key={plat}
                                onClick={() => setCampaignFilterPlatform(plat)}
                                className={`px-2.5 py-1 rounded-lg text-[10px] font-bold border uppercase transition-all ${
                                  campaignFilterPlatform === plat
                                    ? 'bg-violet-650/20 border-violet-500 text-violet-300'
                                    : 'bg-transparent border-transparent text-gray-550 hover:text-gray-300'
                                }`}
                              >
                                {plat}
                              </button>
                            ))}
                          </div>
                        </div>

                        {campaignViewMode === 'timeline' && (
                          <div className="flex items-center gap-2 bg-gray-950/20 px-3 py-1.5 rounded-xl border border-gray-850">
                            <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Status:</span>
                            <div className="flex gap-1">
                              {['all', 'pending', 'approved', 'published'].map(st => (
                                <button
                                  key={st}
                                  onClick={() => setCampaignFilterStatus(st)}
                                  className={`px-2.5 py-1 rounded-lg text-[10px] font-bold border uppercase transition-all ${
                                    campaignFilterStatus === st
                                      ? 'bg-emerald-650/20 border-emerald-500 text-emerald-300'
                                      : 'bg-transparent border-transparent text-gray-550 hover:text-gray-300'
                                  }`}
                                >
                                  {st}
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Render view content depending on campaignViewMode */}
                  {campaignViewMode === 'timeline' && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 animate-in fade-in duration-300">
                      {campaignPosts
                        .filter(post => {
                          const matchesPlatform = campaignFilterPlatform === 'all' || post.platform === campaignFilterPlatform;
                          const matchesStatus = campaignFilterStatus === 'all' || post.approval_status === campaignFilterStatus;
                          return matchesPlatform && matchesStatus;
                        })
                        .map(post => renderPostCard(post))}
                    </div>
                  )}

                  {campaignViewMode === 'kanban' && (
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-in fade-in duration-300">
                      {/* Column 1: Pending Review */}
                      <div className="space-y-4 bg-gray-900/10 border border-gray-855/60 p-4 rounded-3xl min-h-[500px]">
                        <div className="flex items-center justify-between border-b border-gray-850 pb-2">
                          <div className="flex items-center gap-2">
                            <span className="h-2.5 w-2.5 rounded-full bg-amber-500 animate-pulse" />
                            <h3 className="font-extrabold text-sm text-gray-200">Pending Review</h3>
                          </div>
                          <span className="text-xs bg-amber-500/10 text-amber-405 px-2 py-0.5 rounded-full font-bold">
                            {campaignPosts.filter(p => p.approval_status === 'pending' && (campaignFilterPlatform === 'all' || p.platform === campaignFilterPlatform)).length}
                          </span>
                        </div>
                        <div className="space-y-4 animate-in fade-in duration-200">
                          {campaignPosts
                            .filter(p => p.approval_status === 'pending' && (campaignFilterPlatform === 'all' || p.platform === campaignFilterPlatform))
                            .map(post => renderPostCard(post))}
                        </div>
                      </div>

                      {/* Column 2: Scheduled & Approved */}
                      <div className="space-y-4 bg-gray-900/10 border border-gray-855/60 p-4 rounded-3xl min-h-[500px]">
                        <div className="flex items-center justify-between border-b border-gray-850 pb-2">
                          <div className="flex items-center gap-2">
                            <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                            <h3 className="font-extrabold text-sm text-gray-200">Scheduled &amp; Approved</h3>
                          </div>
                          <span className="text-xs bg-emerald-500/10 text-emerald-450 px-2 py-0.5 rounded-full font-bold">
                            {campaignPosts.filter(p => (p.approval_status === 'approved' || p.approval_status === 'scheduled') && (campaignFilterPlatform === 'all' || p.platform === campaignFilterPlatform)).length}
                          </span>
                        </div>
                        <div className="space-y-4 animate-in fade-in duration-200">
                          {campaignPosts
                            .filter(p => (p.approval_status === 'approved' || p.approval_status === 'scheduled') && (campaignFilterPlatform === 'all' || p.platform === campaignFilterPlatform))
                            .map(post => renderPostCard(post))}
                        </div>
                      </div>

                      {/* Column 3: Sent / Published */}
                      <div className="space-y-4 bg-gray-900/10 border border-gray-855/60 p-4 rounded-3xl min-h-[500px]">
                        <div className="flex items-center justify-between border-b border-gray-850 pb-2">
                          <div className="flex items-center gap-2">
                            <span className="h-2.5 w-2.5 rounded-full bg-blue-500 animate-pulse" />
                            <h3 className="font-extrabold text-sm text-gray-200">Sent / Published</h3>
                          </div>
                          <span className="text-xs bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-full font-bold">
                            {campaignPosts.filter(p => p.approval_status === 'published' && (campaignFilterPlatform === 'all' || p.platform === campaignFilterPlatform)).length}
                          </span>
                        </div>
                        <div className="space-y-4 animate-in fade-in duration-200">
                          {campaignPosts
                            .filter(p => p.approval_status === 'published' && (campaignFilterPlatform === 'all' || p.platform === campaignFilterPlatform))
                            .map(post => renderPostCard(post))}
                        </div>
                      </div>
                    </div>
                  )}

                  {campaignViewMode === 'analytics' && (
                    <div className="space-y-6 animate-in fade-in duration-300">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <h3 className="text-sm font-extrabold text-white">Live Performance &amp; Learning Loop</h3>
                          <p className="text-[11px] text-gray-400 mt-0.5">
                            Pulls FB / IG / LinkedIn insights · rebuilds what works · feeds next campaign generation
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <Button size="sm" variant="outline" disabled={analyticsLoading} onClick={() => fetchAnalyticsDashboard()}>
                            {analyticsLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Refresh'}
                          </Button>
                          <Button size="sm" disabled={analyticsSyncing} onClick={() => syncAnalytics()}>
                            {analyticsSyncing ? (<><Loader2 className="h-3 w-3 animate-spin mr-1" /> Syncing…</>) : 'Sync platform insights'}
                          </Button>
                        </div>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        <Card className="glass-panel border-gray-850 p-4 rounded-2xl bg-gray-950/20">
                          <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Avg Engagement Rate</p>
                          <h3 className="text-xl font-extrabold text-white mt-1">
                            {analyticsDash ? `${((analyticsDash.totals?.avg_engagement_rate || 0) * 100).toFixed(2)}%` : '—'}
                          </h3>
                          <p className="text-[10px] text-gray-500 mt-2">From {analyticsDash?.totals?.with_metrics ?? 0} posts with metrics</p>
                        </Card>
                        <Card className="glass-panel border-gray-850 p-4 rounded-2xl bg-gray-950/20">
                          <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Total Impressions</p>
                          <h3 className="text-xl font-extrabold text-white mt-1">
                            {analyticsDash ? Math.round(analyticsDash.totals?.impressions || 0).toLocaleString() : '—'}
                          </h3>
                          <p className="text-[10px] text-gray-500 mt-2">Published: {analyticsDash?.totals?.published ?? 0}</p>
                        </Card>
                        <Card className="glass-panel border-gray-850 p-4 rounded-2xl bg-gray-950/20">
                          <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Total Engagement</p>
                          <h3 className="text-xl font-extrabold text-white mt-1">
                            {analyticsDash ? Math.round(analyticsDash.totals?.engagement || 0).toLocaleString() : '—'}
                          </h3>
                          <p className="text-[10px] text-gray-500 mt-2">Clicks: {Math.round(analyticsDash?.totals?.clicks || 0).toLocaleString()}</p>
                        </Card>
                        <Card className="glass-panel border-gray-850 p-4 rounded-2xl bg-gray-950/20">
                          <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Avg CTR</p>
                          <h3 className="text-xl font-extrabold text-white mt-1">
                            {analyticsDash ? `${((analyticsDash.totals?.avg_ctr || 0) * 100).toFixed(2)}%` : '—'}
                          </h3>
                          <p className="text-[10px] text-gray-500 mt-2">Clicks ÷ impressions</p>
                        </Card>
                      </div>

                      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                        <div className="lg:col-span-7 bg-gray-950/20 border border-gray-850 p-5 rounded-3xl space-y-3">
                          <h4 className="text-xs font-bold text-white uppercase tracking-wider">Top posts by performance score</h4>
                          {(!analyticsDash?.top_posts || analyticsDash.top_posts.length === 0) && (
                            <p className="text-xs text-gray-500 py-6 text-center">
                              No metrics yet. Publish posts, then click <b>Sync platform insights</b>.
                            </p>
                          )}
                          {(analyticsDash?.top_posts || []).map((p: any) => (
                            <div key={p.id} className="border border-gray-800 rounded-xl p-3 space-y-1">
                              <div className="flex justify-between gap-2 text-[10px] uppercase font-bold text-gray-400">
                                <span>{p.platform}</span>
                                <span className="text-emerald-400">Score {p.performance_score ?? 0}</span>
                              </div>
                              <p className="text-xs text-gray-200 line-clamp-2">{p.content}</p>
                              <div className="flex flex-wrap gap-3 text-[10px] text-gray-500">
                                <span>Impr {Math.round(p.impressions || 0)}</span>
                                <span>Eng {Math.round(p.engagement || 0)}</span>
                                <span>ER {((p.engagement_rate || 0) * 100).toFixed(2)}%</span>
                                <span>CTR {((p.ctr || 0) * 100).toFixed(2)}%</span>
                              </div>
                              {p.learning_tags?.length > 0 && (
                                <div className="flex flex-wrap gap-1 pt-1">
                                  {p.learning_tags.map((t: string) => (
                                    <span key={t} className="text-[9px] px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-300 border border-violet-500/20">{t}</span>
                                  ))}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>

                        <div className="lg:col-span-5 bg-gray-950/20 border border-gray-850 p-5 rounded-3xl space-y-3">
                          <h4 className="text-xs font-bold text-white uppercase tracking-wider">Learning patterns (auto)</h4>
                          <p className="text-[10px] text-gray-500">Boosted patterns are injected into the next campaign generation prompts.</p>
                          {(!analyticsDash?.learning_patterns || analyticsDash.learning_patterns.length === 0) && (
                            <p className="text-xs text-gray-500 py-4">Sync insights after publishing to build patterns.</p>
                          )}
                          {(analyticsDash?.learning_patterns || []).slice(0, 12).map((pat: any, i: number) => (
                            <div key={`${pat.pattern_key}-${i}`} className="flex justify-between gap-2 text-xs border-b border-gray-900 pb-2">
                              <div>
                                <span className={pat.banned ? 'text-rose-400' : pat.weight > 0 ? 'text-emerald-400' : 'text-gray-300'}>
                                  {pat.banned ? 'AVOID' : pat.weight > 0 ? 'DO MORE' : 'neutral'} · {pat.pattern_key}
                                </span>
                                <div className="text-[10px] text-gray-500">
                                  n={pat.sample_count} · ER {((pat.avg_engagement_rate || 0) * 100).toFixed(2)}% · w={Number(pat.weight || 0).toFixed(2)}
                                </div>
                              </div>
                              <span className="text-[10px] text-gray-500 uppercase">{pat.platform || 'all'}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                </div>
              )}
              </div>

              {isMetaModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
                  <div className="bg-gray-950 border border-gray-800 rounded-3xl shadow-2xl shadow-black/50 w-full max-w-lg overflow-hidden">
                    {/* Header */}
                    <div className="relative px-6 pt-6 pb-4 border-b border-gray-800 bg-gradient-to-r from-pink-950/40 to-rose-950/30">
                      <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-pink-500 to-transparent" />
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 rounded-2xl bg-gradient-to-br from-pink-600 to-rose-600 flex items-center justify-center shadow-lg shadow-pink-500/30">
                          <span className="text-xl">📲</span>
                        </div>
                        <div>
                          <h2 className="text-white font-extrabold text-lg tracking-tight">Connect Meta to Publish</h2>
                          <p className="text-gray-400 text-xs mt-0.5">Required to post on Instagram &amp; Facebook</p>
                        </div>
                      </div>
                    </div>

                    {/* Body */}
                    <div className="px-6 py-5 space-y-5">
                    <div className="bg-blue-950/30 border border-blue-900/40 rounded-xl p-4 text-xs text-blue-200 leading-relaxed space-y-1">
                      <p className="font-bold text-blue-100 text-sm">How to get your Meta Page Access Token:</p>
                      <ol className="list-decimal pl-4 space-y-1 text-blue-300">
                        <li>Go to <a href="https://developers.facebook.com/tools/explorer/" target="_blank" rel="noreferrer" className="text-pink-400 hover:text-pink-300 underline font-medium">Meta Graph API Explorer</a></li>
                        <li>Select your App &amp; generate a <strong>Page Access Token</strong></li>
                        <li>Add permissions: <code className="bg-blue-950/60 px-1 rounded">instagram_content_publish</code>, <code className="bg-blue-950/60 px-1 rounded">pages_show_list</code>, <code className="bg-blue-950/60 px-1 rounded">instagram_basic</code></li>
                        <li>Use the <strong>Access Token Debugger</strong> to extend it to a 60-day long-lived token</li>
                        <li>Paste the token below</li>
                      </ol>
                    </div>

                    <div className="space-y-2">
                      <label className="text-xs font-bold text-gray-300 uppercase tracking-wider">Meta Page Access Token</label>
                      <input
                        type="password"
                        placeholder="EAAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx..."
                        value={metaTokenInput}
                        onChange={e => setMetaTokenInput(e.target.value)}
                        className="w-full bg-gray-900 border border-gray-700 focus:border-pink-500 focus:ring-1 focus:ring-pink-500/20 rounded-xl px-4 py-3 text-white text-sm outline-none transition-all font-mono placeholder:text-gray-600"
                        autoComplete="off"
                      />
                      <p className="text-[10px] text-gray-500">Your token is encrypted and stored securely. It is never logged or shared.</p>
                    </div>
                  </div>

                  {/* Footer */}
                  <div className="px-6 pb-6 flex gap-3 justify-end">
                    <button
                      onClick={() => { setIsMetaModalOpen(false); setPendingPublishPostId(null); setMetaTokenInput(''); }}
                      className="px-4 py-2 rounded-xl text-sm font-semibold text-gray-400 hover:text-white hover:bg-gray-800 transition-all"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleSaveMetaTokenAndPublish}
                      disabled={!metaTokenInput.trim() || savingMetaToken}
                      className="px-5 py-2 rounded-xl text-sm font-bold bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-500 hover:to-rose-500 text-white shadow-lg shadow-pink-500/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2"
                    >
                      {savingMetaToken ? (
                        <>
                          <span className="animate-spin inline-block w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full" />
                          Saving &amp; Publishing...
                        </>
                      ) : (
                        'Save Token &amp; Publish Now'
                      )}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Bulk Schedule Dialog */}
            {isBulkScheduleOpen && (
              <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
                <div className="bg-gray-950 border border-gray-800 rounded-3xl shadow-2xl shadow-black/50 w-full max-w-md overflow-hidden relative">
                  <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-violet-500 to-transparent" />
                  
                  {/* Header */}
                  <div className="px-6 pt-6 pb-4 border-b border-gray-800 bg-gradient-to-r from-violet-950/20 to-indigo-950/10 flex items-center justify-between">
                    <div>
                      <h2 className="text-white font-extrabold text-lg tracking-tight flex items-center gap-2">
                        <span>📅</span> Bulk Schedule Campaign
                      </h2>
                      <p className="text-gray-400 text-xs mt-0.5">Distribute pending posts evenly over a date range.</p>
                    </div>
                    <button 
                      onClick={() => setIsBulkScheduleOpen(false)}
                      className="text-gray-450 hover:text-white transition-colors"
                    >
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    </button>
                  </div>

                  {/* Body */}
                  <div className="px-6 py-5 space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="flex flex-col gap-1.5">
                        <label className="text-xs font-semibold text-gray-400">Start Date</label>
                        <Input
                          type="date"
                          value={bulkStartDate}
                          onChange={e => setBulkStartDate(e.target.value)}
                          className="bg-gray-900/60 border-gray-800 text-white focus:border-violet-500 rounded-xl h-10"
                        />
                      </div>

                      <div className="flex flex-col gap-1.5">
                        <label className="text-xs font-semibold text-gray-400">End Date</label>
                        <Input
                          type="date"
                          value={bulkEndDate}
                          onChange={e => setBulkEndDate(e.target.value)}
                          className="bg-gray-900/60 border-gray-800 text-white focus:border-violet-500 rounded-xl h-10"
                        />
                      </div>
                    </div>

                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-semibold text-gray-400">Posting Time (Daily)</label>
                      <Input
                        type="time"
                        value={bulkPostingTime}
                        onChange={e => setBulkPostingTime(e.target.value)}
                        className="bg-gray-900/60 border-gray-800 text-white focus:border-violet-500 rounded-xl h-10"
                      />
                    </div>
                  </div>

                  {/* Footer */}
                  <div className="px-6 py-4 border-t border-gray-800 bg-gray-950/40 flex gap-3 justify-end">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setIsBulkScheduleOpen(false)}
                      className="h-10 px-4 rounded-xl text-xs font-semibold text-gray-400 border-gray-800 hover:bg-gray-800 hover:text-white bg-transparent"
                    >
                      Cancel
                    </Button>
                    <Button
                      type="button"
                      disabled={bulkScheduling || !bulkStartDate || !bulkEndDate || !bulkPostingTime}
                      onClick={handleBulkSchedule}
                      className="h-10 px-4 rounded-xl text-xs font-semibold bg-violet-650 hover:bg-violet-600 text-white disabled:opacity-50"
                    >
                      {bulkScheduling ? "Scheduling..." : "Schedule Posts"}
                    </Button>
                  </div>
                </div>
              </div>
            )}



            {/* Create Manual Post Dialog */}
            {isCreatePostOpen && (
              <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
                <div className="bg-gray-950 border border-gray-800 rounded-3xl shadow-2xl shadow-black/50 w-full max-w-xl overflow-hidden relative">
                  <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-violet-500 to-transparent" />
                  
                  {/* Header */}
                  <div className="px-6 pt-6 pb-4 border-b border-gray-800 bg-gradient-to-r from-violet-950/20 to-indigo-950/10 flex items-center justify-between">
                    <div>
                      <h2 className="text-white font-extrabold text-lg tracking-tight flex items-center gap-2">
                        <span>📝</span> Create Manual Post Draft
                      </h2>
                      <p className="text-gray-400 text-xs mt-0.5">Add a new manual post to your marketing campaign timeline.</p>
                    </div>
                    <button 
                      onClick={() => setIsCreatePostOpen(false)}
                      className="text-gray-450 hover:text-white transition-colors"
                    >
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    </button>
                  </div>

                  {/* Body */}
                  <div className="px-6 py-5 space-y-4 max-h-[70vh] overflow-y-auto">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="flex flex-col gap-1.5">
                        <label className="text-xs font-semibold text-gray-400">Platform</label>
                        <Select value={createPostPlatform} onValueChange={(val) => val && setCreatePostPlatform(val)}>
                          <SelectTrigger className="h-10 bg-gray-900/60 border-gray-800 text-white rounded-xl">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent className="bg-gray-900 border-gray-800 text-white">
                            <SelectItem value="linkedin">LinkedIn</SelectItem>
                            <SelectItem value="instagram">Instagram</SelectItem>
                            <SelectItem value="facebook">Facebook</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="flex flex-col gap-1.5">
                        <label className="text-xs font-semibold text-gray-400">Timeline Day</label>
                        <Input
                          type="number"
                          min={1}
                          value={createPostDay}
                          onChange={e => setCreatePostDay(parseInt(e.target.value) || 1)}
                          className="bg-gray-900/60 border-gray-800 text-white focus:border-violet-500 rounded-xl h-10"
                        />
                      </div>
                    </div>

                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-semibold text-gray-400">Post Text Content</label>
                      <Textarea
                        placeholder="Write your post content here..."
                        className="bg-gray-900/60 border-gray-800 text-white focus:border-violet-500 rounded-xl min-h-[100px] text-sm"
                        value={createPostContent}
                        onChange={e => setCreatePostContent(e.target.value)}
                      />
                    </div>

                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-semibold text-gray-400">Scheduled Date & Time (Optional)</label>
                      <Input
                        type="datetime-local"
                        className="bg-gray-900/60 border-gray-800 text-white focus:border-violet-500 rounded-xl h-10"
                        value={createPostScheduledAt}
                        onChange={e => setCreatePostScheduledAt(e.target.value)}
                      />
                    </div>

                    {/* Upload Media section */}
                    <div className="bg-gray-950/40 border border-gray-900 rounded-2xl p-3.5 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-gray-300">Upload Post Media</span>
                        {createPostIsManualMedia && (
                          <span className="text-[9px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-full">
                            Manual Upload Active
                          </span>
                        )}
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <input
                            type="file"
                            accept="image/*"
                            className="hidden"
                            id="create-image-upload"
                            onChange={e => {
                              const file = e.target.files?.[0];
                              if (file) handleFileUpload(file, false);
                            }}
                          />
                          <Button
                            type="button"
                            variant="outline"
                            disabled={uploadingFile}
                            onClick={() => document.getElementById("create-image-upload")?.click()}
                            className="w-full h-10 rounded-xl text-xs border-gray-805 hover:bg-gray-800 hover:text-white bg-transparent flex items-center justify-center gap-1.5"
                          >
                            <ImageIcon size={14} className="text-violet-400" />
                            {uploadingFile ? "Uploading..." : "Upload Image File"}
                          </Button>
                        </div>

                        <div>
                          <input
                            type="file"
                            accept="video/*"
                            className="hidden"
                            id="create-video-upload"
                            onChange={e => {
                              const file = e.target.files?.[0];
                              if (file) handleFileUpload(file, false);
                            }}
                          />
                          <Button
                            type="button"
                            variant="outline"
                            disabled={uploadingFile}
                            onClick={() => document.getElementById("create-video-upload")?.click()}
                            className="w-full h-10 rounded-xl text-xs border-gray-805 hover:bg-gray-800 hover:text-white bg-transparent flex items-center justify-center gap-1.5"
                          >
                            <Film size={14} className="text-violet-400" />
                            {uploadingFile ? "Uploading..." : "Upload Video File"}
                          </Button>
                        </div>
                      </div>

                      {(createPostImageUrl || createPostVideoUrl) && (
                        <div className="pt-2 border-t border-gray-900 animate-in fade-in duration-200">
                          <label className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block mb-1">Uploaded Preview URL</label>
                          <div className="text-xs text-gray-400 bg-gray-900/60 p-2 rounded-xl border border-gray-850 truncate">
                            {createPostImageUrl || createPostVideoUrl}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* AI Prompt Tool Selector */}
                    <div className="bg-gray-950/40 border border-gray-900 rounded-2xl p-3.5 space-y-3">
                      <div className="flex flex-col gap-1.5">
                        <div className="flex items-center justify-between">
                          <label className="text-xs font-bold text-gray-300">Generation Prompt Options</label>
                          <span className="text-[9px] text-gray-500">Choose if you want to attach a prompt</span>
                        </div>
                        <Select
                          value={createPostImagePromptEnabled ? "image" : createPostVideoPromptEnabled ? "video" : "none"}
                          onValueChange={(val) => {
                            if (val === "image") {
                              setCreatePostImagePromptEnabled(true);
                              setCreatePostVideoPromptEnabled(false);
                            } else if (val === "video") {
                              setCreatePostImagePromptEnabled(false);
                              setCreatePostVideoPromptEnabled(true);
                            } else {
                              setCreatePostImagePromptEnabled(false);
                              setCreatePostVideoPromptEnabled(false);
                            }
                          }}
                        >
                          <SelectTrigger className="h-10 bg-gray-900/60 border-gray-800 text-white rounded-xl text-xs">
                            <SelectValue placeholder="Select Prompt Option" />
                          </SelectTrigger>
                          <SelectContent className="bg-gray-900 border-gray-800 text-white">
                            <SelectItem value="none">None (No prompt attachment)</SelectItem>
                            <SelectItem value="image">Image Prompt (For AI Graphics)</SelectItem>
                            {ENABLE_IN_APP_VIDEO && <SelectItem value="video">Video Prompt (For AI Video loops)</SelectItem>}
                          </SelectContent>
                        </Select>
                      </div>

                      {/* Image Prompt */}
                      {createPostImagePromptEnabled && (
                        <div className="space-y-2 pt-2 border-t border-gray-900 animate-in fade-in duration-200">
                          <label className="text-[10px] font-bold text-violet-400 uppercase tracking-wider block">Image Generation Prompt</label>
                          <Textarea
                            placeholder="Describe image (e.g. 'Warm grading, clean workspace')"
                            className="bg-gray-900/60 border-gray-800 text-white focus:border-violet-500 rounded-xl text-xs min-h-[60px]"
                            value={createPostImagePrompt}
                            onChange={e => setCreatePostImagePrompt(e.target.value)}
                          />
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            disabled={suggestingPrompt}
                            onClick={() => handleSuggestPrompt(createPostContent, 'image', false)}
                            className="w-full h-8 rounded-lg text-xs font-semibold border-gray-800 hover:bg-gray-800 hover:text-white bg-transparent text-gray-300 disabled:opacity-50"
                          >
                            {suggestingPrompt ? "Suggesting..." : "🪄 Suggest Image Prompt"}
                          </Button>
                        </div>
                      )}

                      {/* Video Prompt */}
                      {ENABLE_IN_APP_VIDEO && createPostVideoPromptEnabled && (
                        <div className="space-y-2 pt-2 border-t border-gray-900 animate-in fade-in duration-200">
                          <label className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider block">Video Generation Prompt</label>
                          <Textarea
                            placeholder="Describe video loop (e.g. 'Sun rays shifting, loop video')"
                            className="bg-gray-900/60 border-gray-800 text-white focus:border-indigo-500 rounded-xl text-xs min-h-[60px]"
                            value={createPostVideoPrompt}
                            onChange={e => setCreatePostVideoPrompt(e.target.value)}
                          />
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            disabled={suggestingPrompt}
                            onClick={() => handleSuggestPrompt(createPostContent, 'video', false)}
                            className="w-full h-8 rounded-lg text-xs font-semibold border-gray-800 hover:bg-gray-800 hover:text-white bg-transparent text-gray-300 disabled:opacity-50"
                          >
                            {suggestingPrompt ? "Suggesting..." : "🪄 Suggest Video Prompt"}
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Footer */}
                  <div className="px-6 py-4 border-t border-gray-800 bg-gray-950/40 flex gap-3 justify-end">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setIsCreatePostOpen(false)}
                      className="h-10 px-4 rounded-xl text-xs font-semibold text-gray-400 border-gray-800 hover:bg-gray-800 hover:text-white bg-transparent"
                    >
                      Cancel
                    </Button>
                    <Button
                      type="button"
                      disabled={creatingPost || !createPostContent}
                      onClick={handleCreateManualPost}
                      className="h-10 px-4 rounded-xl text-xs font-semibold bg-violet-650 hover:bg-violet-600 text-white disabled:opacity-50"
                    >
                      {creatingPost ? "Creating..." : "Create Post Draft"}
                    </Button>
                  </div>
                </div>
              </div>
            )}
            </>
  );
}
