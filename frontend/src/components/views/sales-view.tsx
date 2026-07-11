'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { 
  TrendingUp, Search, Upload, Plus, Edit2, MessageSquare, Send, Clock, 
  ChevronRight, Calendar, Loader2, Bot, Check, X, Phone, Mail, Building, Users, LayoutGrid, Target, Cpu, Sparkles, Activity,
  Download, CheckSquare, AlertCircle, ListFilter, Trash2
} from 'lucide-react';

interface SalesViewProps {
  token: string | null;
  API_URL: string;
  fetchWithAuth: (url: string, options?: any) => Promise<Response>;
  fetchData: () => Promise<void>;
  timeline: any[];
}

const parseBudget = (budgetString: string | null | undefined): number => {
  if (!budgetString) return 0;
  // standard cleaning: remove spaces, $, commas
  let clean = budgetString.toLowerCase().replace(/[\s\$,]/g, '');
  if (!clean) return 0;
  let multiplier = 1;
  if (clean.includes('k')) {
    multiplier = 1000;
    clean = clean.replace('k', '');
  } else if (clean.includes('m')) {
    multiplier = 1000000;
    clean = clean.replace('m', '');
  }
  // Remove everything except numbers and decimals
  clean = clean.replace(/[^0-9\.]/g, '');
  const numeric = parseFloat(clean);
  return isNaN(numeric) ? 0 : numeric * multiplier;
};

export default function SalesView({
  token,
  API_URL,
  fetchWithAuth,
  fetchData,
  timeline,
}: SalesViewProps) {
  // Sales CRM states relocated here
  const [salesLeads, setSalesLeads] = useState<any[]>([]);
  const [selectedLead, setSelectedLead] = useState<any | null>(null);
  const [salesSearch, setSalesSearch] = useState('');
  const [salesStatusFilter, setSalesStatusFilter] = useState('all');
  const [salesPriorityFilter, setSalesPriorityFilter] = useState('all');
  const [salesTimeFilter, setSalesTimeFilter] = useState('all');
  const [salesAssignedFilter, setSalesAssignedFilter] = useState('all');
  const [members, setMembers] = useState<any[]>([]);
  const [salesLoading, setSalesLoading] = useState(false);
  const [salesActionLoading, setSalesActionLoading] = useState(false);

  // Sales AI V3 States
  const [activeSalesTab, setActiveSalesTab] = useState<'pipeline' | 'config' | 'stepper' | 'analytics'>('pipeline');
  const [salesTextProvider, setSalesTextProvider] = useState('auto');
  const [salesTextModel, setSalesTextModel] = useState('');
  const [salesTargetLeadCount, setSalesTargetLeadCount] = useState<number>(50);
  const [reviewPlanFirst, setReviewPlanFirst] = useState(false);
  const [planReviewData, setPlanReviewData] = useState<any>(null);
  const [isPlanReviewModalOpen, setIsPlanReviewModalOpen] = useState(false);
  const [profileCompanyName, setProfileCompanyName] = useState('');
  const [profileWebsite, setProfileWebsite] = useState('');
  const [profileIndustry, setProfileIndustry] = useState('');
  const [profileServiceDescription, setProfileServiceDescription] = useState('');
  const [profileTargetCountries, setProfileTargetCountries] = useState('India, UAE');
  const [profileTargetIndustries, setProfileTargetIndustries] = useState('Manufacturing, Healthcare, IT Services');
  const [profileTargetCompanySize, setProfileTargetCompanySize] = useState('10-100');
  const [profileTargetBudgetRange, setProfileTargetBudgetRange] = useState('1L-5L');
  const [profileTargetDecisionMakers, setProfileTargetDecisionMakers] = useState('Founder, CEO, CTO');
  const [profileUsp, setProfileUsp] = useState('');
  const [profileCaseStudies, setProfileCaseStudies] = useState('');
  const [profileOfferDetails, setProfileOfferDetails] = useState('');
  const [profileExtraContext, setProfileExtraContext] = useState('');
  const [profilePrimarySource, setProfilePrimarySource] = useState('auto');
  const [profileCalendars, setProfileCalendars] = useState('https://calendly.com/sales');
  const [profileCommunicationChannels, setProfileCommunicationChannels] = useState<string[]>(['email', 'whatsapp', 'linkedin']);
  const [profileSalesEmails, setProfileSalesEmails] = useState('');
  const [profileSupportEmails, setProfileSupportEmails] = useState('');
  
  const [workflowStatus, setWorkflowStatus] = useState<any>({
    status: 'idle',
    current_step: 0,
    steps: {},
    logs: []
  });
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileSaving, setProfileSaving] = useState(false);

  const fetchBusinessProfile = async () => {
    if (!token) return;
    setProfileLoading(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/leads/business-profile`);
      if (res.ok) {
        const data = await res.json();
        setProfileCompanyName(data.company_name || '');
        setProfileWebsite(data.website || '');
        setProfileIndustry(data.industry || '');
        setProfileServiceDescription(data.service_description || '');
        setProfileTargetCountries(Array.isArray(data.target_countries) ? data.target_countries.join(', ') : (data.target_countries || ''));
        setProfileTargetIndustries(Array.isArray(data.target_industries) ? data.target_industries.join(', ') : (data.target_industries || ''));
        setProfileTargetCompanySize(data.target_company_size || '');
        setProfileTargetBudgetRange(data.target_budget_range || '1L-5L');
        setProfileTargetDecisionMakers(Array.isArray(data.target_decision_makers) ? data.target_decision_makers.join(', ') : (data.target_decision_makers || ''));
        setProfileUsp(data.usp || '');
        setProfileCaseStudies(data.case_studies || '');
        setProfileOfferDetails(data.offer_details || '');
        const ec = data.extra_context || '';
        const match = ec.match(/\[MANUAL_SOURCE_OVERRIDE:\s*(.*?)\]/);
        if (match) {
          setProfilePrimarySource(match[1]);
          setProfileExtraContext(ec.replace(/\n*\[MANUAL_SOURCE_OVERRIDE: .*?\]/g, ''));
        } else {
          setProfilePrimarySource('auto');
          setProfileExtraContext(ec);
        }
        setProfileCalendars(Array.isArray(data.calendars) ? data.calendars.join(', ') : (data.calendars || ''));
        setProfileCommunicationChannels(data.communication_channels || ['email', 'whatsapp']);
        setProfileSalesEmails(Array.isArray(data.sales_emails) ? data.sales_emails.join(', ') : (data.sales_emails || ''));
        setProfileSupportEmails(Array.isArray(data.support_emails) ? data.support_emails.join(', ') : (data.support_emails || ''));
        if (data.v3_workflow_status) {
          setWorkflowStatus(data.v3_workflow_status);
        }
      }
    } catch (e) {
      console.error("Failed to fetch business profile:", e);
    } finally {
      setProfileLoading(false);
    }
  };

  const fetchWorkflowStatus = async () => {
    if (!token) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/leads/v3-workflow-status`);
      if (res.ok) {
        const data = await res.json();
        setWorkflowStatus(data);
      }
    } catch (e) {
      console.error("Failed to fetch workflow status:", e);
    }
  };

  useEffect(() => {
    let intervalId: any;
    if (token && workflowStatus.status === 'executing') {
      intervalId = setInterval(() => {
        fetchWorkflowStatus();
        fetchLeads();
      }, 2000);
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [token, workflowStatus.status]);

  const handleSaveProfile = async (silent = false) => {
    if (!token) return false;
    setProfileSaving(true);
    try {
      const countries = profileTargetCountries.split(',').map(s => s.trim()).filter(Boolean);
      const industries = profileTargetIndustries.split(',').map(s => s.trim()).filter(Boolean);
      const decisionMakers = profileTargetDecisionMakers.split(',').map(s => s.trim()).filter(Boolean);
      const calendars = profileCalendars.split(',').map(s => s.trim()).filter(Boolean);
      const salesEmails = profileSalesEmails.split(',').map(s => s.trim()).filter(Boolean);
      const supportEmails = profileSupportEmails.split(',').map(s => s.trim()).filter(Boolean);

      if (salesEmails.length > 5) {
        alert("Maximum 5 Sales Emails allowed.");
        setProfileSaving(false);
        return false;
      }
      if (supportEmails.length > 5) {
        alert("Maximum 5 Support Emails allowed.");
        setProfileSaving(false);
        return false;
      }

      const res = await fetchWithAuth(`${API_URL}/leads/business-profile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_name: profileCompanyName,
          website: profileWebsite,
          industry: profileIndustry,
          service_description: profileServiceDescription,
          target_countries: countries,
          target_industries: industries,
          target_company_size: profileTargetCompanySize,
          target_budget_range: profileTargetBudgetRange,
          target_decision_makers: decisionMakers,
          usp: profileUsp,
          case_studies: profileCaseStudies,
          offer_details: profileOfferDetails,
          extra_context: profilePrimarySource !== 'auto' ? `${profileExtraContext}\n\n[MANUAL_SOURCE_OVERRIDE: ${profilePrimarySource}]`.trim() : profileExtraContext,
          calendars: calendars,
          communication_channels: profileCommunicationChannels,
          sales_emails: salesEmails,
          support_emails: supportEmails
        })
      });
      if (res.ok) {
        if (!silent) alert("✅ Business Profile saved successfully!");
        return true;
      } else {
        alert("Failed to save Business Profile.");
        return false;
      }
    } catch (e) {
      console.error("Save profile error:", e);
      alert("Network error saving Business Profile.");
      return false;
    } finally {
      setProfileSaving(false);
    }
  };

  const handlePreviewPlan = async () => {
    setSalesActionLoading(true);
    try {
      const planRes = await fetchWithAuth(`${API_URL}/llm/plan-task`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          complexity: 'high',
          provider: salesTextProvider !== 'auto' ? salesTextProvider : null,
          model: salesTextModel || null
        })
      });
      if (planRes.ok) {
        const planData = await planRes.json();
        setPlanReviewData(planData);
        setIsPlanReviewModalOpen(true);
      } else {
        const err = await planRes.json();
        alert(`Failed to fetch AI plan: ${err.detail}`);
      }
    } catch (e) {
      alert("Network error fetching AI plan.");
    } finally {
      setSalesActionLoading(false);
    }
  };

  const handleLaunchV3Workflow = async () => {
    const saved = await handleSaveProfile(true);
    if (!saved) return;
    
    setSalesActionLoading(true);
    setIsPlanReviewModalOpen(false);
    try {
      const res = await fetchWithAuth(`${API_URL}/leads/run-v3-workflow`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: salesTextProvider,
          model: salesTextModel || undefined,
          count: salesTargetLeadCount || 50
        })
      });
      if (res.ok) {
        const data = await res.json();
        setWorkflowStatus((prev: any) => ({
          ...prev,
          status: 'executing'
        }));
        setActiveSalesTab('stepper');
        alert(data.message || "🚀 Sales AI V3 Workflow started! Check the Live Agent Stepper tab for real-time logs.");
      } else {
        const data = await res.json();
        alert(`Failed to launch workflow: ${data.detail || 'Unknown error'}`);
      }
    } catch (e) {
      console.error("Launch V3 workflow error:", e);
      alert("Network error starting V3 workflow.");
    } finally {
      setSalesActionLoading(false);
    }
  };


  // Edit Lead Fields
  const [isEditingSalesLead, setIsEditingSalesLead] = useState(false);
  const [editPersonalEmail, setEditPersonalEmail] = useState('');
  const [editCompanyEmail, setEditCompanyEmail] = useState('');
  const [editMobileNo, setEditMobileNo] = useState('');
  const [editCompanyContactNo, setEditCompanyContactNo] = useState('');
  const [editNeedOfWhat, setEditNeedOfWhat] = useState('');
  const [editHowMuch, setEditHowMuch] = useState('');
  const [editWhy, setEditWhy] = useState('');
  const [editTargetContext, setEditTargetContext] = useState('');
  const [editName, setEditName] = useState('');
  const [editCompany, setEditCompany] = useState('');
  const [editPriority, setEditPriority] = useState('medium');
  const [editStatus, setEditStatus] = useState('captured');
  const [editScore, setEditScore] = useState(0);
  const [editAssignedTo, setEditAssignedTo] = useState('Sales AI Agent');
  const [editNextFollowupDate, setEditNextFollowupDate] = useState('');
  const [editFollowupNotes, setEditFollowupNotes] = useState('');

  // Lead Upload & Human updates states
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadWithAI, setUploadWithAI] = useState(false);
  const [uploadingLeads, setUploadingLeads] = useState(false);
  
  const [noteText, setNoteText] = useState('');
  const [noteChannel, setNoteChannel] = useState('note');
  const [noteDirection, setNoteDirection] = useState('internal');
  
  // Timeline activities filter
  const [timelineFilter, setTimelineFilter] = useState('all');
  
  // Action checklist task input
  const [newTaskTitle, setNewTaskTitle] = useState('');

  // Manual Lead Creation and View Mode States (CRM)
  const [salesViewMode, setSalesViewMode] = useState<'pipeline' | 'list'>('pipeline');
  const [isCreateLeadModalOpen, setIsCreateLeadModalOpen] = useState(false);
  const [newLeadName, setNewLeadName] = useState('');
  const [newLeadCompany, setNewLeadCompany] = useState('');
  const [newLeadEmail, setNewLeadEmail] = useState('');
  const [newLeadPhone, setNewLeadPhone] = useState('');
  const [newLeadPersonalEmail, setNewLeadPersonalEmail] = useState('');
  const [newLeadCompanyEmail, setNewLeadCompanyEmail] = useState('');
  const [newLeadMobileNo, setNewLeadMobileNo] = useState('');
  const [newLeadCompanyContactNo, setNewLeadCompanyContactNo] = useState('');
  const [newLeadNeedOfWhat, setNewLeadNeedOfWhat] = useState('');
  const [newLeadHowMuch, setNewLeadHowMuch] = useState('');
  const [newLeadWhy, setNewLeadWhy] = useState('');
  const [newLeadTargetContext, setNewLeadTargetContext] = useState('');
  const [newLeadPriority, setNewLeadPriority] = useState('medium');
  const [newLeadStatus, setNewLeadStatus] = useState('captured');
  const [newLeadScore, setNewLeadScore] = useState(0);
  const [newLeadAssignedTo, setNewLeadAssignedTo] = useState('Sales AI Agent');
  const [newLeadNextFollowupDate, setNewLeadNextFollowupDate] = useState('');
  const [newLeadFollowupNotes, setNewLeadFollowupNotes] = useState('');
  const [creatingLead, setCreatingLead] = useState(false);

  // Email config + reply tracking states
  const [emailConfig, setEmailConfig] = useState<{smtp_configured: boolean; gmail_configured: boolean; any_configured: boolean; recommended_channel: string | null} | null>(null);
  const [checkingReplies, setCheckingReplies] = useState(false);
  const [sendingOutreachSmart, setSendingOutreachSmart] = useState(false);
  const [lastReplyCheckResult, setLastReplyCheckResult] = useState<{queued: number; message: string} | null>(null);
  const [outreachSmartResult, setOutreachSmartResult] = useState<any>(null);

  // Review first vs auto-send for prospect replies
  const [salesSettings, setSalesSettings] = useState({
    sales_auto_reply: true,
    reply_mode: 'review_first' as 'review_first' | 'auto_send',
    auto_book_meetings: true,
  });
  const [salesSettingsSaving, setSalesSettingsSaving] = useState(false);

  const fetchSalesSettings = async () => {
    if (!token) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/leads/sales-settings`);
      if (res.ok) {
        const data = await res.json();
        setSalesSettings({
          sales_auto_reply: data.sales_auto_reply ?? true,
          reply_mode: data.reply_mode === 'auto_send' ? 'auto_send' : 'review_first',
          auto_book_meetings: data.auto_book_meetings ?? true,
        });
      }
    } catch (e) {
      console.error('Failed to fetch sales settings:', e);
    }
  };

  const saveSalesSettings = async (next: typeof salesSettings) => {
    if (!token) return;
    setSalesSettingsSaving(true);
    setSalesSettings(next);
    try {
      const res = await fetchWithAuth(`${API_URL}/leads/sales-settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(next),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.settings) {
          setSalesSettings({
            sales_auto_reply: data.settings.sales_auto_reply ?? next.sales_auto_reply,
            reply_mode: data.settings.reply_mode === 'auto_send' ? 'auto_send' : 'review_first',
            auto_book_meetings: data.settings.auto_book_meetings ?? next.auto_book_meetings,
          });
        }
      } else {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || 'Failed to save sales settings');
      }
    } catch (e) {
      console.error(e);
    } finally {
      setSalesSettingsSaving(false);
    }
  };

  const fetchEmailConfig = async () => {
    if (!token) return;
    try {
      const res = await fetchWithAuth(`${API_URL}/leads/email-config-status`);
      if (res.ok) {
        const data = await res.json();
        setEmailConfig(data);
      }
    } catch (e) {
      console.error('Failed to fetch email config:', e);
    }
  };

  const handleCheckReplies = async () => {
    setCheckingReplies(true);
    setLastReplyCheckResult(null);
    try {
      const res = await fetchWithAuth(`${API_URL}/leads/check-replies`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setLastReplyCheckResult(data);
        if (data.queued > 0) {
          fetchLeads();
        }
      }
    } catch (e) {
      console.error('Check replies error:', e);
    } finally {
      setCheckingReplies(false);
    }
  };

  const handleSendOutreachSmart = async (leadId: string) => {
    setSendingOutreachSmart(true);
    setOutreachSmartResult(null);
    try {
      const res = await fetchWithAuth(`${API_URL}/leads/${leadId}/send-outreach-smart`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setOutreachSmartResult(data);
        fetchLeads();
      }
    } catch (e) {
      console.error('Smart outreach error:', e);
    } finally {
      setSendingOutreachSmart(false);
    }
  };

  // Fetch leads when filters change
  useEffect(() => {
    if (token) {
      fetchLeads();
    }
  }, [salesStatusFilter, salesPriorityFilter, salesSearch, salesTimeFilter, salesAssignedFilter, token]);

  // Fetch members list, business profile and workflow status on mount
  useEffect(() => {
    if (token) {
      fetchMembers();
      fetchBusinessProfile();
      fetchWorkflowStatus();
      fetchEmailConfig();
      fetchSalesSettings();
    }
  }, [token]);


  const fetchMembers = async () => {
    try {
      const res = await fetchWithAuth(`${API_URL}/auth/members`);
      if (res.ok) {
        const data = await res.json();
        setMembers(data);
      }
    } catch (e) {
      console.error("Failed to fetch members:", e);
    }
  };

  // Sync edits if a new lead is selected
  useEffect(() => {
    if (selectedLead) {
      setEditPersonalEmail(selectedLead.personal_email || '');
      setEditCompanyEmail(selectedLead.company_email || '');
      setEditMobileNo(selectedLead.mobile_no || '');
      setEditCompanyContactNo(selectedLead.company_contact_no || '');
      setEditNeedOfWhat(selectedLead.need_of_what || '');
      setEditHowMuch(selectedLead.how_much || '');
      setEditWhy(selectedLead.why || '');
      setEditTargetContext(selectedLead.target_context || '');
      setEditName(selectedLead.name || '');
      setEditCompany(selectedLead.company || '');
      setEditPriority(selectedLead.priority || 'medium');
      setEditStatus(selectedLead.status || 'captured');
      setEditScore(selectedLead.score || 0);
      setEditAssignedTo(selectedLead.assigned_to || 'Sales AI Agent');
      setEditNextFollowupDate(selectedLead.data?.next_followup_date || '');
      setEditFollowupNotes(selectedLead.data?.followup_notes || '');
    } else {
      setIsEditingSalesLead(false);
    }
  }, [selectedLead]);

  // CRM functions
    const fetchLeads = async () => {
    if (!token) return;
    setSalesLoading(true);
    try {
      const queryParams = new URLSearchParams();
      if (salesStatusFilter && salesStatusFilter !== 'all') queryParams.append('status', salesStatusFilter);
      if (salesPriorityFilter && salesPriorityFilter !== 'all') queryParams.append('priority', salesPriorityFilter);
      if (salesSearch) queryParams.append('search', salesSearch);
      if (salesTimeFilter && salesTimeFilter !== 'all') queryParams.append('time_filter', salesTimeFilter);
      if (salesAssignedFilter && salesAssignedFilter !== 'all') queryParams.append('assigned_to', salesAssignedFilter);

      const res = await fetchWithAuth(`${API_URL}/leads/?${queryParams.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setSalesLeads(data);
        if (selectedLead) {
          const updated = data.find((l: any) => l.id === selectedLead.id);
          if (updated) {
            setSelectedLead(updated);
          }
        }
      }
    } catch (e) {
      console.error(e);
    } finally {
      setSalesLoading(false);
    }
  };

  
  const handleSaveLead = async () => {
    if (!selectedLead) return;
    setSalesActionLoading(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/leads/${selectedLead.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: editName,
          company: editCompany,
          personal_email: editPersonalEmail,
          company_email: editCompanyEmail,
          mobile_no: editMobileNo,
          company_contact_no: editCompanyContactNo,
          need_of_what: editNeedOfWhat,
          how_much: editHowMuch,
          why: editWhy,
          target_context: editTargetContext,
          priority: editPriority,
          status: editStatus,
          score: Number(editScore) || 0,
          assigned_to: editAssignedTo,
          data: {
            ...(selectedLead.data || {}),
            next_followup_date: editNextFollowupDate,
            followup_notes: editFollowupNotes
          }
        })
      });
      if (res.ok) {
        const updated = await res.json();
        setSelectedLead(updated);
        setIsEditingSalesLead(false);
        fetchLeads();
        fetchData();
      } else {
        alert('Failed to save lead updates');
      }
    } catch (e) {
      console.error(e);
    } finally {
      setSalesActionLoading(false);
    }
  };


    const handleSendSalesOutreach = async (leadId: string) => {
    setSalesActionLoading(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/leads/${leadId}/outreach`, {
        method: 'POST'
      });
      if (res.ok) {
        alert('Sales outreach email sent and recorded in conversation history!');
        fetchLeads();
        fetchData();
      } else {
        alert('Failed to send sales outreach');
      }
    } catch (e) {
      console.error(e);
    } finally {
      setSalesActionLoading(false);
    }
  };


    const handleBookSalesMeeting = async (leadId: string) => {
    setSalesActionLoading(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/leads/${leadId}/schedule_meeting`, {
        method: 'POST'
      });
      if (res.ok) {
        const data = await res.json();
        alert(`Sales meeting successfully scheduled for ${data.meeting_time}! Meet link: ${data.meeting_link}`);
        fetchLeads();
        fetchData();
      } else {
        alert('Failed to book meeting');
      }
    } catch (e) {
      console.error(e);
    } finally {
      setSalesActionLoading(false);
    }
  };


    const handleLogHumanUpdate = async () => {
    if (!selectedLead || !noteText.trim()) return;
    setSalesActionLoading(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/leads/${selectedLead.id}/timeline-note`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: noteText,
          channel: noteChannel,
          direction: noteDirection
        })
      });
      if (res.ok) {
        const updated = await res.json();
        setSelectedLead(updated);
        setNoteText('');
        fetchLeads();
        fetchData();
      } else {
        alert('Failed to log human update');
      }
    } catch (e) {
      console.error(e);
      alert('Network error logging human update');
    } finally {
      setSalesActionLoading(false);
    }
  };


    const handleUploadLeads = async () => {
    if (!uploadFile) return;
    setUploadingLeads(true);
    try {
      const formData = new FormData();
      formData.append('file', uploadFile);
      formData.append('handle_with_ai', String(uploadWithAI));

      const res = await fetchWithAuth(`${API_URL}/leads/upload`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (res.ok) {
        setIsUploadModalOpen(false);
        setUploadFile(null);
        setUploadWithAI(false);
        fetchLeads();
        fetchData();
        alert(`✅ Leads imported successfully!\n${data.message}`);
      } else {
        alert(`Error uploading leads: ${data.detail || 'Unknown error'}`);
      }
    } catch (e) {
      console.error(e);
      alert("Network error uploading leads.");
    } finally {
      setUploadingLeads(false);
    }
  };


    const handleCreateLead = async () => {
    if (!newLeadName && !newLeadEmail) {
      alert("Please enter at least a Lead Name or Email.");
      return;
    }
    setCreatingLead(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/leads/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newLeadName || null,
          company: newLeadCompany || null,
          email: newLeadEmail || null,
          phone: newLeadPhone || null,
          personal_email: newLeadPersonalEmail || null,
          company_email: newLeadCompanyEmail || null,
          mobile_no: newLeadMobileNo || null,
          company_contact_no: newLeadCompanyContactNo || null,
          need_of_what: newLeadNeedOfWhat || null,
          how_much: newLeadHowMuch || null,
          why: newLeadWhy || null,
          target_context: newLeadTargetContext || null,
          priority: newLeadPriority || 'medium',
          status: newLeadStatus || 'captured',
          score: Number(newLeadScore) || 0,
          source: 'Manual Entry',
          assigned_to: newLeadAssignedTo,
          data: {
            next_followup_date: newLeadNextFollowupDate || null,
            followup_notes: newLeadFollowupNotes || null
          }
        })
      });
      if (res.ok) {
        setIsCreateLeadModalOpen(false);
        setNewLeadName('');
        setNewLeadCompany('');
        setNewLeadEmail('');
        setNewLeadPhone('');
        setNewLeadPersonalEmail('');
        setNewLeadCompanyEmail('');
        setNewLeadMobileNo('');
        setNewLeadCompanyContactNo('');
        setNewLeadNeedOfWhat('');
        setNewLeadHowMuch('');
        setNewLeadWhy('');
        setNewLeadTargetContext('');
        setNewLeadPriority('medium');
        setNewLeadStatus('captured');
        setNewLeadScore(0);
        setNewLeadAssignedTo('Sales AI Agent');
        setNewLeadNextFollowupDate('');
        setNewLeadFollowupNotes('');
        fetchLeads();
        fetchData();
        alert("✅ Lead created successfully!");
      } else {
        const errorData = await res.json();
        alert(`Failed to create lead: ${errorData.detail || 'Unknown error'}`);
      }
    } catch (e) {
      console.error(e);
      alert("Network error creating lead.");
    } finally {
      setCreatingLead(false);
    }
  };

  // CSV Leads Exporter
  const exportLeadsToCSV = () => {
    if (salesLeads.length === 0) {
      alert("No leads to export.");
      return;
    }
    const headers = [
      "ID", "Name", "Company", "Personal Email", "Company Email", "Mobile No", "Company Contact No",
      "Need", "Budget/Valuation", "Why", "Priority", "Status", "Score", "Assigned To", "Source", "Next Follow-up Date", "Follow-up Notes"
    ];
    
    const rows = salesLeads.map(lead => [
      lead.id,
      lead.name || "",
      lead.company || "",
      lead.personal_email || "",
      lead.company_email || lead.email || "",
      lead.mobile_no || lead.phone || "",
      lead.company_contact_no || "",
      lead.need_of_what || "",
      lead.how_much || "",
      lead.why || "",
      lead.priority || "medium",
      lead.status || "captured",
      lead.score || 50,
      lead.assigned_to || "Sales AI Agent",
      lead.source || "Manual Entry",
      lead.data?.next_followup_date || "",
      lead.data?.followup_notes || ""
    ]);

    const csvContent = [
      headers.join(","),
      ...rows.map(e => e.map(val => `"${String(val).replace(/"/g, '""')}"`).join(","))
    ].join("\n");

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `sales_leads_export_${new Date().toISOString().split('T')[0]}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Checklist / Tasks operations
  const handleAddTask = async (title: string) => {
    if (!selectedLead || !title.trim()) return;
    const currentTasks = selectedLead.data?.tasks || [];
    const newTask = {
      id: Math.random().toString(36).substring(2, 9),
      title: title.trim(),
      completed: false,
      created_at: new Date().toISOString()
    };
    const updatedTasks = [...currentTasks, newTask];
    
    setSalesActionLoading(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/leads/${selectedLead.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          data: {
            ...(selectedLead.data || {}),
            tasks: updatedTasks
          }
        })
      });
      if (res.ok) {
        const updated = await res.json();
        setSelectedLead(updated);
        setNewTaskTitle('');
        fetchLeads();
        fetchData();
      } else {
        alert('Failed to add task');
      }
    } catch (e) {
      console.error(e);
    } finally {
      setSalesActionLoading(false);
    }
  };

  const handleToggleTask = async (taskId: string) => {
    if (!selectedLead) return;
    const currentTasks = selectedLead.data?.tasks || [];
    const updatedTasks = currentTasks.map((t: any) => 
      t.id === taskId ? { ...t, completed: !t.completed } : t
    );
    
    try {
      const res = await fetchWithAuth(`${API_URL}/leads/${selectedLead.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          data: {
            ...(selectedLead.data || {}),
            tasks: updatedTasks
          }
        })
      });
      if (res.ok) {
        const updated = await res.json();
        setSelectedLead(updated);
        fetchLeads();
        fetchData();
      } else {
        alert('Failed to toggle task');
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleDeleteTask = async (taskId: string) => {
    if (!selectedLead) return;
    const currentTasks = selectedLead.data?.tasks || [];
    const updatedTasks = currentTasks.filter((t: any) => t.id !== taskId);
    
    try {
      const res = await fetchWithAuth(`${API_URL}/leads/${selectedLead.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          data: {
            ...(selectedLead.data || {}),
            tasks: updatedTasks
          }
        })
      });
      if (res.ok) {
        const updated = await res.json();
        setSelectedLead(updated);
        fetchLeads();
        fetchData();
      } else {
        alert('Failed to delete task');
      }
    } catch (e) {
      console.error(e);
    }
  };


  // Trigger outbound sales sourcing sequence
  const handleRunSequence = async (sequenceType: string) => {
    setSalesActionLoading(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/leads/run-sequence`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sequence_type: sequenceType })
      });
      if (res.ok) {
        alert("Sales AI Outbound outreach sequence launched!");
        fetchLeads();
        fetchData();
      } else {
        alert("Failed to run sequence");
      }
    } catch (e) {
      console.error(e);
    } finally {
      setSalesActionLoading(false);
    }
  };

  // Trigger lead generation auto agent search
  const handleRunAutoSalesAgent = async () => {
    setSalesActionLoading(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/leads/run-auto-agent`, {
        method: 'POST'
      });
      if (res.ok) {
        alert("Sales AI Prospector launched! It will search local places and sync to CRM.");
        fetchLeads();
        fetchData();
      } else {
        alert("Failed to run agent");
      }
    } catch (e) {
      console.error(e);
    } finally {
      setSalesActionLoading(false);
    }
  };

  const handleTriggerScoring = async (leadId: string) => {
    setSalesActionLoading(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/leads/${leadId}/score`, {
        method: 'POST'
      });
      if (res.ok) {
        alert("Scoring triggered successfully!");
        fetchLeads();
        fetchData();
      } else {
        alert("Failed to score lead");
      }
    } catch (e) {
      console.error(e);
    } finally {
      setSalesActionLoading(false);
    }
  };

  const activePipelineValue = salesLeads
    .filter(l => !['won', 'lost'].includes(l.status))
    .reduce((sum, l) => sum + parseBudget(l.how_much), 0);
  const closedRevenue = salesLeads
    .filter(l => l.status === 'won')
    .reduce((sum, l) => sum + parseBudget(l.how_much), 0);
  const wonCount = salesLeads.filter(l => l.status === 'won').length;
  const lostCount = salesLeads.filter(l => l.status === 'lost').length;
  const totalClosed = wonCount + lostCount;
  const winRate = totalClosed > 0 ? Math.round((wonCount / totalClosed) * 100) : 0;

  // Analytics calculations
  const totalLeadsFound = salesLeads.length;
  const qualifiedLeadsCount = salesLeads.filter(l => (l.score || 0) >= 60).length;
  const hotLeadsCount = salesLeads.filter(l => (l.score || 0) >= 85 || l.data?.scoring_breakdown?.category === 'Hot Lead').length;
  const meetingsBookedCount = salesLeads.filter(l => l.status === 'meeting_scheduled').length;

  const contactedLeadsCount = salesLeads.filter(l => ['contacted', 'replied', 'meeting_scheduled', 'won', 'lost'].includes(l.status)).length;
  const respondedLeadsCount = salesLeads.filter(l => ['replied', 'meeting_scheduled', 'won'].includes(l.status) || l.data?.prospect_interested).length;
  
  const responseRatePct = contactedLeadsCount > 0 ? Math.round((respondedLeadsCount / contactedLeadsCount) * 100) : 0;
  const conversionRatePct = contactedLeadsCount > 0 ? Math.round((meetingsBookedCount / contactedLeadsCount) * 100) : 0;

  const totalRevenuePotential = salesLeads.reduce((sum, l) => sum + parseBudget(l.how_much), 0);

  // Sourcing channel counts
  const sourcingChannels: { [key: string]: number } = {};
  salesLeads.forEach(l => {
    const src = (l.source || 'Unknown').split(':')[0].trim();
    sourcingChannels[src] = (sourcingChannels[src] || 0) + 1;
  });

  // Top Industries
  const topIndustries: { [key: string]: number } = {};
  salesLeads.forEach(l => {
    const company = (l.company || '').toLowerCase();
    const source = (l.source || '').toLowerCase();
    let foundInd = '';
    const possible = ['Manufacturing', 'Healthcare', 'IT Services', 'Retail', 'Finance', 'SaaS'];
    for (const p of possible) {
      if (company.includes(p.toLowerCase()) || source.includes(p.toLowerCase())) {
        foundInd = p;
        break;
      }
    }
    if (!foundInd && l.id) {
      const idx = l.id.charCodeAt(0) % possible.length;
      foundInd = possible[idx];
    } else if (!foundInd) {
      foundInd = 'Technology';
    }
    topIndustries[foundInd] = (topIndustries[foundInd] || 0) + 1;
  });

  // Campaigns
  const campaignData: { [key: string]: { leads: number; meetings: number } } = {};
  salesLeads.forEach(l => {
    const campaign = l.source || 'Direct Outreach';
    if (!campaignData[campaign]) {
      campaignData[campaign] = { leads: 0, meetings: 0 };
    }
    campaignData[campaign].leads += 1;
    if (l.status === 'meeting_scheduled') {
      campaignData[campaign].meetings += 1;
    }
  });


  const fmtCurrency = (val: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0
    }).format(val);
  };

  return (
    <>
    <div className="space-y-8 max-w-7xl mx-auto animate-in fade-in duration-300">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <h1 className="text-4xl font-extrabold text-white tracking-tight flex items-center gap-2">
                    <TrendingUp className="text-emerald-400 h-8 w-8 animate-pulse" /> Sales CRM Dashboard
                  </h1>
                  <p className="text-gray-400 mt-1">Autonomous B2B prospect sourcing, outreach sequencing, contact enrichment, and conversion tracking.</p>
                </div>
                 <div className="flex items-center gap-3 flex-wrap">
                  <Button
                    onClick={exportLeadsToCSV}
                    className="bg-gray-900 hover:bg-gray-800 text-white border border-gray-800 hover:border-gray-700 font-bold rounded-xl transition-all h-11 px-5 flex items-center gap-2 shadow-lg"
                  >
                    <Download size={16} /> Export to CSV
                  </Button>
                  <Button
                    onClick={() => setIsCreateLeadModalOpen(true)}
                    className="bg-gray-900 hover:bg-gray-800 text-white border border-gray-800 hover:border-gray-700 font-bold rounded-xl transition-all h-11 px-5 flex items-center gap-2 shadow-lg"
                  >
                    <Plus size={16} /> Add Lead Manually
                  </Button>
                  <Button
                    onClick={() => setIsUploadModalOpen(true)}
                    className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl transition-all h-11 px-5 flex items-center gap-2 shadow-lg shadow-emerald-500/25"
                  >
                    <Upload size={16} /> Upload Leads (CSV/JSON)
                  </Button>
                </div>
              </div>

              {/* Statistics Ribbon */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {[
                  { title: "Total Leads", val: salesLeads.length, desc: "Total B2B leads captured", icon: <Users className="h-4 w-4 text-emerald-400" /> },
                  { title: "Active Pipeline", val: fmtCurrency(activePipelineValue), desc: "Current open opportunities", icon: <TrendingUp className="h-4 w-4 text-blue-400" /> },
                  { title: "Closed Revenue", val: fmtCurrency(closedRevenue), desc: "Total won deal value", icon: <Target className="h-4 w-4 text-violet-400" /> },
                  { title: "Win Rate", val: `${winRate}%`, desc: `${wonCount} won / ${lostCount} lost deals`, icon: <Calendar className="h-4 w-4 text-amber-400" /> },
                ].map((stat, i) => (
                  <Card key={i} className={`hud-card neon-glow-emerald rounded-2xl relative overflow-hidden p-4 group transition-transform duration-300 hover:-translate-y-1`}>
                    <div className="flex justify-between items-start z-10 relative">
                      <div>
                        <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest font-mono group-hover:text-white transition-colors">{stat.title}</p>
                        <h3 className="text-3xl font-black text-white mt-1">{stat.val}</h3>
                        <p className="text-[9px] text-gray-500 font-medium uppercase tracking-wider mt-1">{stat.desc}</p>
                      </div>
                      <div className="p-2 bg-gray-950/40 rounded-lg border border-[rgba(16,185,129,0.2)]">
                        {stat.icon}
                      </div>
                    </div>
                  </Card>
                ))}
              </div>

              {/* AI automation mode — Review first vs Auto-send */}
              <Card className="hud-card border border-emerald-500/20 rounded-2xl p-4 bg-gray-950/40 relative z-10">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-emerald-400/80">
                      Prospect reply mode {salesSettingsSaving ? '· saving…' : ''}
                    </p>
                    <p className="text-xs text-gray-400 mt-1 max-w-xl">
                      {salesSettings.reply_mode === 'review_first'
                        ? 'AI drafts replies to prospects → you approve in Enterprise → Approvals, then send.'
                        : 'AI auto-replies after a short delay when a prospect messages you.'}
                    </p>
                  </div>
                  <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center">
                    <div className="flex rounded-xl overflow-hidden border border-gray-700 min-w-[260px]">
                      <button
                        type="button"
                        onClick={() => saveSalesSettings({ ...salesSettings, reply_mode: 'review_first', sales_auto_reply: true })}
                        className={`flex-1 px-3 py-2.5 text-xs font-bold transition-colors ${
                          salesSettings.reply_mode === 'review_first'
                            ? 'bg-amber-500 text-black'
                            : 'bg-gray-900 text-gray-300 hover:bg-gray-800'
                        }`}
                      >
                        👁 Review first
                      </button>
                      <button
                        type="button"
                        onClick={() => saveSalesSettings({ ...salesSettings, reply_mode: 'auto_send', sales_auto_reply: true })}
                        className={`flex-1 px-3 py-2.5 text-xs font-bold transition-colors border-l border-gray-700 ${
                          salesSettings.reply_mode === 'auto_send'
                            ? 'bg-emerald-500 text-black'
                            : 'bg-gray-900 text-gray-300 hover:bg-gray-800'
                        }`}
                      >
                        ⚡ Auto-reply
                      </button>
                    </div>
                    <label className="flex items-center gap-2 text-xs text-gray-300 cursor-pointer whitespace-nowrap">
                      <input
                        type="checkbox"
                        className="rounded border-gray-600"
                        checked={salesSettings.auto_book_meetings}
                        onChange={(e) =>
                          saveSalesSettings({ ...salesSettings, auto_book_meetings: e.target.checked })
                        }
                      />
                      Auto-book meetings
                    </label>
                  </div>
                </div>
              </Card>

              {/* V3 Sales AI Navigation Tabs */}
              <div className="flex gap-2 p-1 bg-gray-900/60 border border-[rgba(16,185,129,0.2)] rounded-2xl max-w-lg z-10 relative">
                <button
                  onClick={() => setActiveSalesTab('pipeline')}
                  className={`flex-1 py-2 px-4 rounded-xl text-xs font-black tracking-wide transition-all ${
                    activeSalesTab === 'pipeline'
                      ? 'bg-[rgba(16,185,129,0.15)] text-emerald-400 border border-[rgba(16,185,129,0.4)] shadow-[0_0_15px_rgba(16,185,129,0.2)]'
                      : 'text-gray-400 hover:text-white hover:bg-gray-800/40 border border-transparent'
                  }`}
                >
                  🎯 CRM & Pipeline
                </button>
                <button
                  onClick={() => setActiveSalesTab('config')}
                  className={`flex-1 py-2 px-4 rounded-xl text-xs font-black tracking-wide transition-all ${
                    activeSalesTab === 'config'
                      ? 'bg-[rgba(16,185,129,0.15)] text-emerald-400 border border-[rgba(16,185,129,0.4)] shadow-[0_0_15px_rgba(16,185,129,0.2)]'
                      : 'text-gray-400 hover:text-white hover:bg-gray-800/40 border border-transparent'
                  }`}
                >
                  ⚙️ Business Config
                </button>
                <button
                  onClick={() => setActiveSalesTab('stepper')}
                  className={`flex-1 py-2 px-4 rounded-xl text-xs font-black tracking-wide transition-all relative ${
                    activeSalesTab === 'stepper'
                      ? 'bg-[rgba(16,185,129,0.15)] text-emerald-400 border border-[rgba(16,185,129,0.4)] shadow-[0_0_15px_rgba(16,185,129,0.2)]'
                      : 'text-gray-400 hover:text-white hover:bg-gray-800/40 border border-transparent'
                  }`}
                >
                  🤖 Live Stepper
                  {workflowStatus.status === 'executing' && (
                    <span className="absolute -top-1.5 -right-1 flex h-3 w-3">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                    </span>
                  )}
                </button>
                <button
                  onClick={() => setActiveSalesTab('analytics')}
                  className={`flex-1 py-2 px-4 rounded-xl text-xs font-black tracking-wide transition-all ${
                    activeSalesTab === 'analytics'
                      ? 'bg-[rgba(16,185,129,0.15)] text-emerald-400 border border-[rgba(16,185,129,0.4)] shadow-[0_0_15px_rgba(16,185,129,0.2)]'
                      : 'text-gray-400 hover:text-white hover:bg-gray-800/40 border border-transparent'
                  }`}
                >
                  📈 Revenue Analytics
                </button>
              </div>

              {activeSalesTab === 'pipeline' && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                
                {/* Left Pane: Leads List */}
                <div className="lg:col-span-2 space-y-4">
                  <Card className="glass-panel border-transparent rounded-3xl p-6 shadow-2xl relative">
                    <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-emerald-500 to-transparent" />
                    
                    {/* Filter Bar */}
                    <div className="flex flex-col md:flex-row flex-wrap gap-3 items-center mb-6">
                      <div className="relative flex-1 w-full min-w-[250px]">
                        <Search className="absolute left-3 top-3 h-4 w-4 text-gray-400 pointer-events-none" />
                        <Input
                          placeholder="Search leads by name, company, email..."
                          value={salesSearch}
                          onChange={e => setSalesSearch(e.target.value)}
                          className="pl-9 bg-gray-900/60 border-gray-800 text-white rounded-xl h-10 w-full focus:border-emerald-500 focus:ring-emerald-500/20"
                        />
                      </div>
                                         <div className="flex gap-2 w-full md:w-auto flex-wrap">
                        <Select value={salesStatusFilter} onValueChange={val => setSalesStatusFilter(val || 'all')}>
                          <SelectTrigger className="w-[120px] bg-gray-900/60 border-gray-800 text-xs text-gray-305 rounded-xl h-10">
                            <SelectValue placeholder="Status" />
                          </SelectTrigger>
                          <SelectContent className="bg-gray-950 border-gray-800 text-gray-305">
                            <SelectItem value="all">All Statuses</SelectItem>
                            <SelectItem value="captured">Captured</SelectItem>
                            <SelectItem value="enriched">Enriched</SelectItem>
                            <SelectItem value="contacted">Contacted</SelectItem>
                            <SelectItem value="replied">Replied</SelectItem>
                            <SelectItem value="meeting_scheduled">Meetings</SelectItem>
                            <SelectItem value="won">Closed Won</SelectItem>
                            <SelectItem value="lost">Closed Lost</SelectItem>
                          </SelectContent>
                        </Select>

                        <Select value={salesPriorityFilter} onValueChange={val => setSalesPriorityFilter(val || 'all')}>
                          <SelectTrigger className="w-[100px] bg-gray-900/60 border-gray-800 text-xs text-gray-305 rounded-xl h-10">
                            <SelectValue placeholder="Priority" />
                          </SelectTrigger>
                          <SelectContent className="bg-gray-950 border-gray-800 text-gray-350">
                            <SelectItem value="all">All Priorities</SelectItem>
                            <SelectItem value="high">High</SelectItem>
                            <SelectItem value="medium">Medium</SelectItem>
                            <SelectItem value="low">Low</SelectItem>
                          </SelectContent>
                        </Select>

                        <Select value={salesAssignedFilter} onValueChange={val => setSalesAssignedFilter(val || 'all')}>
                          <SelectTrigger className="w-[125px] bg-gray-900/60 border-gray-800 text-xs text-gray-305 rounded-xl h-10">
                            <SelectValue placeholder="Assignee" />
                          </SelectTrigger>
                          <SelectContent className="bg-gray-950 border-gray-800 text-gray-350">
                            <SelectItem value="all">All Assignees</SelectItem>
                            <SelectItem value="Sales AI Agent">Sales AI Agent</SelectItem>
                            {members.map(member => (
                              <SelectItem key={member.id} value={member.name || member.email}>
                                {member.name || member.email}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>

                         <Select value={salesTimeFilter} onValueChange={val => setSalesTimeFilter(val || 'all')}>
                          <SelectTrigger className="w-[90px] bg-gray-900/60 border-gray-800 text-xs text-gray-305 rounded-xl h-10">
                            <SelectValue placeholder="Time" />
                          </SelectTrigger>
                          <SelectContent className="bg-gray-950 border-gray-800 text-gray-350">
                            <SelectItem value="all">All Time</SelectItem>
                            <SelectItem value="day">Past 24h</SelectItem>
                            <SelectItem value="week">Past Week</SelectItem>
                            <SelectItem value="month">Past Month</SelectItem>
                          </SelectContent>
                        </Select>

                        <div className="flex items-center gap-1 bg-gray-950/80 p-1 border border-gray-800 rounded-xl">
                          <button
                            onClick={() => setSalesViewMode('pipeline')}
                            className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                              salesViewMode === 'pipeline'
                                ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/15'
                                : 'text-gray-400 hover:text-white hover:bg-gray-900/40'
                            }`}
                          >
                            <LayoutGrid size={13} /> Pipeline
                          </button>
                          <button
                            onClick={() => setSalesViewMode('list')}
                            className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                              salesViewMode === 'list'
                                ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/15'
                                : 'text-gray-400 hover:text-white hover:bg-gray-900/40'
                            }`}
                          >
                            <Users size={13} /> List
                          </button>
                        </div>
                      </div>
                    </div>

                    {salesViewMode === 'pipeline' ? (
                      /* Pipeline View Container */
                      <div className="relative">
                        <div className="cyberpunk-scanline rounded-2xl z-0" />
                        <div className="flex gap-4 overflow-x-auto pb-4 pt-1 max-w-full custom-scrollbar min-h-[500px] z-10 relative">
                        {[
                          { id: 'captured', label: 'Captured', color: 'border-t-gray-500', glow: 'shadow-gray-500/5' },
                          { id: 'scored', label: 'Scored', color: 'border-t-cyan-500', glow: 'shadow-cyan-500/5' },
                          { id: 'enriched', label: 'Enriched', color: 'border-t-teal-500', glow: 'shadow-teal-500/5' },
                          { id: 'contacted', label: 'Contacted', color: 'border-t-blue-500', glow: 'shadow-blue-500/5' },
                          { id: 'replied', label: 'Replied', color: 'border-t-violet-500', glow: 'shadow-violet-500/5' },
                          { id: 'meeting_scheduled', label: 'Meeting Booked', color: 'border-t-amber-500', glow: 'shadow-amber-500/5' },
                          { id: 'won', label: 'Closed Won', color: 'border-t-emerald-500', glow: 'shadow-emerald-500/5' },
                          { id: 'lost', label: 'Closed Lost', color: 'border-t-rose-500', glow: 'shadow-rose-500/5' },
                        ].map(stage => {
                          const stageLeads = salesLeads.filter(l => l.status === stage.id);
                          const stagePipelineValue = stageLeads.reduce((sum, l) => sum + parseBudget(l.how_much), 0);
                          const stageAvgScore = stageLeads.length > 0 
                            ? Math.round(stageLeads.reduce((sum, l) => sum + (l.score || 0), 0) / stageLeads.length) 
                            : 0;
                          return (
                            <div
                              key={stage.id}
                              onDragOver={e => e.preventDefault()}
                              onDrop={async e => {
                                const leadId = e.dataTransfer.getData('text/plain');
                                if (!leadId) return;
                                
                                try {
                                  const res = await fetchWithAuth(`${API_URL}/leads/${leadId}`, {
                                    method: 'PATCH',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ status: stage.id })
                                  });
                                  if (res.ok) {
                                    const updated = await res.json();
                                    if (selectedLead && selectedLead.id === leadId) {
                                      setSelectedLead(updated);
                                    }
                                    fetchLeads();
                                    fetchData();
                                  } else {
                                    alert('Failed to update stage');
                                  }
                                } catch (err) {
                                  console.error(err);
                                }
                              }}
                              className={`flex-shrink-0 w-64 hud-card ${stage.id === 'won' ? 'neon-glow-emerald' : stage.id === 'lost' ? 'neon-glow-rose' : 'neon-glow-cyan'} rounded-2xl p-3 flex flex-col min-h-[460px] max-h-[580px] overflow-hidden`}
                            >
                              {/* Column Header */}
                              <div className={`border-t-2 ${stage.color} pt-2 pb-1.5 flex flex-col flex-shrink-0 border-b border-gray-900/80 mb-2`}>
                                <div className="flex items-center justify-between">
                                  <span className="text-xs font-bold text-white tracking-wide">{stage.label}</span>
                                  <span className="text-[10px] bg-gray-900 border border-gray-800 text-gray-400 font-bold px-2 py-0.5 rounded-full">
                                    {stageLeads.length}
                                  </span>
                                </div>
                                <div className="flex justify-between items-center text-[9px] text-gray-500 mt-1 font-semibold">
                                  <span>Val: <span className="text-emerald-500">{fmtCurrency(stagePipelineValue)}</span></span>
                                  <span>Avg: <span className="text-amber-400">★ {stageAvgScore}</span></span>
                                </div>
                              </div>
                              
                              {/* Column Scrollable Body */}
                              <div className="flex-1 overflow-y-auto space-y-2.5 pr-1 custom-scrollbar min-h-0">
                                {stageLeads.map(lead => {
                                  const isSelected = selectedLead?.id === lead.id;
                                  const isOverdue = lead.data?.next_followup_date && 
                                    new Date(lead.data.next_followup_date) < new Date(new Date().setHours(0,0,0,0));
                                  return (
                                    <div
                                      key={lead.id}
                                      draggable={true}
                                      onDragStart={e => {
                                        e.dataTransfer.setData('text/plain', lead.id);
                                      }}
                                      onClick={() => {
                                        setSelectedLead(lead);
                                        setIsEditingSalesLead(false);
                                      }}
                                      className={`hud-card bg-[rgba(0,0,0,0.4)] border rounded-xl p-3 cursor-grab active:cursor-grabbing hover:border-emerald-500/40 hover:bg-[rgba(16,185,129,0.05)] transition-all shadow-md ${stage.glow} ${
                                        isSelected
                                          ? 'border-emerald-500 ring-1 ring-emerald-500/25 bg-emerald-950/5'
                                          : 'border-[rgba(255,255,255,0.05)]'
                                      }`}
                                    >
                                      <div className="flex justify-between items-start gap-1 mb-1">
                                        <div className="font-extrabold text-white text-xs leading-tight truncate flex-1">{lead.name || 'Unnamed Lead'}</div>
                                        {isOverdue && (
                                          <span className="flex-shrink-0 text-[8px] font-bold bg-rose-500/10 text-rose-450 border border-rose-500/20 px-1 py-0.5 rounded flex items-center gap-0.5 animate-pulse" title="Follow-up overdue!">
                                            <AlertCircle size={8} /> OVERDUE
                                          </span>
                                        )}
                                      </div>
                                      <div className="text-[10px] text-gray-450 truncate mb-1">{lead.company || 'No Company'}</div>
                                      
                                      <div className="flex flex-col gap-1 mb-2 pt-1 border-t border-gray-800/40">
                                        <div className="flex justify-between items-center text-[9px] text-gray-500">
                                          <span className="truncate max-w-[110px] font-medium" title={lead.assigned_to}>👤 {lead.assigned_to || 'Unassigned'}</span>
                                          <span className="truncate max-w-[95px] text-[8px] bg-gray-950 px-1 py-0.5 rounded text-gray-400" title={lead.source}>{lead.source?.split(':')[0] || lead.source || 'Direct'}</span>
                                        </div>
                                      </div>
                                      
                                      <div className="flex items-center justify-between gap-1.5 pt-1.5 border-t border-gray-800/60">
                                        <span className={`text-[8px] font-extrabold uppercase px-1.5 py-0.5 rounded tracking-wide border ${
                                          lead.priority === 'high' 
                                            ? 'bg-rose-500/10 text-rose-455 border-rose-500/20' 
                                            : lead.priority === 'medium' 
                                              ? 'bg-amber-500/10 text-amber-450 border-amber-500/20' 
                                              : 'bg-gray-500/10 text-gray-400 border-gray-800'
                                        }`}>
                                          {lead.priority || 'medium'}
                                        </span>
                                        
                                        <span className="text-[9px] font-mono text-gray-400 font-semibold bg-gray-950 px-1.5 py-0.5 rounded border border-gray-800">
                                          ★ {lead.score || 50}
                                        </span>
                                      </div>
                                      
                                      <div className="flex flex-wrap gap-1 mt-1.5">
                                        {(lead.data?.email_send_status === 'sent' || lead.data?.sent_actual) && (
                                          <span className="text-[8px] flex items-center gap-0.5 bg-blue-500/10 text-blue-400 px-1.5 py-0.5 rounded border border-blue-500/20">
                                            <Mail size={8} /> Sent
                                          </span>
                                        )}
                                        {lead.data?.email_send_status === 'failed' && (
                                          <span className="text-[8px] flex items-center gap-0.5 bg-rose-500/10 text-rose-450 px-1.5 py-0.5 rounded border border-rose-500/20">
                                            <AlertCircle size={8} /> Failed
                                          </span>
                                        )}
                                        {lead.data?.email_send_status === 'not_configured' && (
                                          <span className="text-[8px] flex items-center gap-0.5 bg-amber-500/10 text-amber-450 px-1.5 py-0.5 rounded border border-amber-500/20" title="SMTP not configured">
                                            <AlertCircle size={8} /> Draft
                                          </span>
                                        )}
                                        {(lead.status === 'replied' || (lead.data?.conversation || []).some((m: any) => m.direction === 'inbound')) && (
                                          <span className="text-[8px] flex items-center gap-0.5 bg-violet-500/10 text-violet-400 px-1.5 py-0.5 rounded border border-violet-500/20">
                                            <MessageSquare size={8} /> Replied
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                  );
                                })}
                                {stageLeads.length === 0 && (
                                  <div className="text-center py-12 text-[10px] text-gray-500 italic border border-dashed border-gray-850 rounded-xl">
                                    Drag leads here
                                  </div>
                                )}
                              </div>
                            </div>
                          );
                        })}
                        </div>
                      </div>
                    ) : (
                      /* Table View Container */
                      <div className="border border-gray-800/80 rounded-2xl overflow-hidden bg-[rgba(0,0,0,0.15)] max-h-[600px] overflow-y-auto custom-scrollbar">
                        <Table>
                          <TableHeader className="bg-gray-950/40 border-b border-gray-800 sticky top-0 z-10">
                            <TableRow className="border-gray-800 hover:bg-transparent">
                              <TableHead className="text-gray-400 font-bold uppercase tracking-wider text-[10px] p-4">Lead</TableHead>
                              <TableHead className="text-gray-400 font-bold uppercase tracking-wider text-[10px] p-4">Source</TableHead>
                              <TableHead className="text-gray-400 font-bold uppercase tracking-wider text-[10px] p-4">Assignee</TableHead>
                              <TableHead className="text-gray-400 font-bold uppercase tracking-wider text-[10px] p-4 text-center">Score</TableHead>
                              <TableHead className="text-gray-400 font-bold uppercase tracking-wider text-[10px] p-4">Priority</TableHead>
                              <TableHead className="text-gray-400 font-bold uppercase tracking-wider text-[10px] p-4">Status</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody className="divide-y divide-gray-850">
                            {salesLoading ? (
                              <TableRow className="hover:bg-transparent">
                                <TableCell colSpan={6} className="text-center py-16">
                                  <Loader2 className="h-6 w-6 animate-spin text-emerald-400 mx-auto" />
                                  <p className="text-xs text-gray-455 mt-2">Loading CRM database...</p>
                                </TableCell>
                              </TableRow>
                            ) : salesLeads.length === 0 ? (
                              <TableRow className="hover:bg-transparent">
                                <TableCell colSpan={6} className="text-center py-16 text-xs text-gray-500 font-medium">
                                  No sales leads found matching these filters.
                                </TableCell>
                              </TableRow>
                            ) : (
                              salesLeads.map(lead => {
                                const isSelected = selectedLead?.id === lead.id;
                                return (
                                  <TableRow
                                    key={lead.id}
                                    onClick={() => {
                                      setSelectedLead(lead);
                                      setIsEditingSalesLead(false);
                                    }}
                                    className={`border-gray-800/60 cursor-pointer transition-colors duration-155 ${
                                      isSelected 
                                        ? 'bg-emerald-500/10 hover:bg-emerald-500/15 border-l-2 border-l-emerald-500' 
                                        : 'hover:bg-gray-900/30'
                                    }`}
                                  >
                                    <TableCell className="p-4">
                                      <div className="font-extrabold text-white text-xs">{lead.name || 'Unnamed Lead'}</div>
                                      <div className="text-[10px] text-gray-455 flex items-center gap-1 mt-0.5">
                                        <Building size={10} /> {lead.company || 'No Company'}
                                      </div>
                                    </TableCell>
                                    <TableCell className="p-4">
                                      <span className="text-[9px] font-bold bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded uppercase tracking-wider max-w-[140px] truncate block text-center">
                                        {lead.source?.split(":")[0] || lead.source || 'Unknown'}
                                      </span>
                                    </TableCell>
                                    <TableCell className="p-4">
                                      <span className="text-[11px] text-gray-300 font-medium flex items-center gap-1">
                                        👤 {lead.assigned_to || 'Unassigned'}
                                      </span>
                                    </TableCell>
                                    <TableCell className="p-4 text-center">
                                      <span className={`text-[10px] font-mono font-black ${
                                        lead.score >= 80 ? 'text-emerald-400' : lead.score >= 60 ? 'text-amber-400' : 'text-gray-400'
                                      }`}>
                                        {lead.score || 50}/100
                                      </span>
                                    </TableCell>
                                    <TableCell className="p-4">
                                      <span className={`text-[9px] font-extrabold uppercase px-2 py-0.5 rounded tracking-wide border ${
                                        lead.priority === 'high' 
                                          ? 'bg-rose-500/10 text-rose-455 border-rose-500/20' 
                                          : lead.priority === 'medium' 
                                            ? 'bg-amber-500/10 text-amber-450 border-amber-500/20' 
                                            : 'bg-gray-500/10 text-gray-400 border-gray-805'
                                      }`}>
                                        {lead.priority || 'medium'}
                                      </span>
                                    </TableCell>
                                    <TableCell className="p-4">
                                      <span className={`text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                                        lead.status === 'meeting_scheduled'
                                          ? 'bg-amber-500/15 text-amber-400 border border-amber-500/20'
                                          : lead.status === 'replied'
                                            ? 'bg-violet-500/15 text-violet-400 border border-violet-500/20'
                                            : lead.status === 'contacted'
                                              ? 'bg-blue-500/15 text-blue-400 border border-blue-500/20'
                                              : lead.status === 'enriched'
                                                ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20'
                                                : lead.status === 'won'
                                                  ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20'
                                                  : lead.status === 'lost'
                                                    ? 'bg-rose-500/15 text-rose-455 border-rose-500/20'
                                                    : 'bg-gray-800/80 text-gray-450 border border-gray-700/40'
                                      }`}>
                                        {lead.status === 'meeting_scheduled' ? 'meeting' : lead.status}
                                      </span>
                                    </TableCell>
                                  </TableRow>
                                );
                              })
                            )}
                          </TableBody>
                        </Table>
                      </div>
                    )}
                  </Card>
                </div>

                {/* Right Pane: Lead Detail Panel */}
                <div className="lg:col-span-1">
                  {!selectedLead ? (
                    <Card className="hud-card neon-glow-emerald rounded-3xl p-8 text-center flex flex-col items-center justify-center h-[550px] relative">
                      <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-gray-700 to-transparent" />
                      <div className="text-5xl mb-4">🎯</div>
                      <h3 className="text-base font-bold text-white">No Lead Selected</h3>
                      <p className="text-xs text-gray-455 max-w-[200px] mt-1 leading-relaxed">
                        Select a sales prospect from the list on the left to view enrichment details and actions.
                      </p>
                    </Card>
                  ) : (
                    <Card className="hud-card neon-glow-emerald rounded-3xl p-6 relative flex flex-col min-h-[600px] overflow-hidden">
                      <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-emerald-500 to-transparent" />
                      
                      {/* Identity Section */}
                      <div className="flex justify-between items-start mb-6">
                        <div>
                          <h2 className="text-xl font-extrabold text-white leading-tight">{selectedLead.name}</h2>
                          <p className="text-xs text-gray-450 flex items-center gap-1.5 mt-0.5">
                            <Building size={11} className="text-emerald-400" /> {selectedLead.company}
                          </p>
                        </div>
                        <div className="flex flex-col items-end gap-1.5">
                          <span className={`text-[10px] font-mono font-black border px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border-emerald-500/20`}>
                            Score: {selectedLead.score || 50}
                          </span>
                        </div>
                      </div>

                      {/* Detail Body */}
                      <div className="flex-1 space-y-5 overflow-y-auto max-h-[460px] pr-1 custom-scrollbar">
                        
                        {/* Edit Mode Toggle */}
                        <div className="flex justify-between items-center border-b border-gray-800/80 pb-3">
                          <span className="text-[10px] text-gray-400 font-extrabold uppercase tracking-widest">Prospect Details</span>
                          <button
                            onClick={() => {
                              if (isEditingSalesLead) {
                                setIsEditingSalesLead(false);
                              } else {
                                setEditName(selectedLead.name || '');
                                setEditCompany(selectedLead.company || '');
                                setEditPersonalEmail(selectedLead.personal_email || '');
                                setEditCompanyEmail(selectedLead.company_email || '');
                                setEditMobileNo(selectedLead.mobile_no || '');
                                setEditCompanyContactNo(selectedLead.company_contact_no || '');
                                setEditNeedOfWhat(selectedLead.need_of_what || '');
                                setEditHowMuch(selectedLead.how_much || '');
                                setEditWhy(selectedLead.why || '');
                                setEditTargetContext(selectedLead.target_context || '');
                                setEditPriority(selectedLead.priority || 'medium');
                                setEditStatus(selectedLead.status || 'captured');
                                setIsEditingSalesLead(true);
                              }
                            }}
                            className="text-xs text-emerald-400 hover:text-emerald-300 font-bold transition-colors flex items-center gap-1"
                          >
                            {isEditingSalesLead ? <><X size={12} /> Cancel</> : <><Edit2 size={12} /> Edit Details</>}
                          </button>
                        </div>

                        {isEditingSalesLead ? (
                          /* Edit Inline Form */
                          <div className="space-y-4 text-xs">
                            <div className="grid grid-cols-2 gap-2">
                              <div className="space-y-1">
                                <label className="text-[10px] font-bold text-gray-450 uppercase">Name</label>
                                <Input value={editName} onChange={e => setEditName(e.target.value)} className="bg-gray-950 border-gray-800 h-8 rounded-lg text-white" />
                              </div>
                              <div className="space-y-1">
                                <label className="text-[10px] font-bold text-gray-450 uppercase">Company</label>
                                <Input value={editCompany} onChange={e => setEditCompany(e.target.value)} className="bg-gray-955 border-gray-800 h-8 rounded-lg text-white" />
                              </div>
                            </div>
                            
                            <div className="grid grid-cols-2 gap-2">
                              <div className="space-y-1">
                                <label className="text-[10px] font-bold text-gray-450 uppercase">Personal Email</label>
                                <Input value={editPersonalEmail} onChange={e => setEditPersonalEmail(e.target.value)} className="bg-gray-950 border-gray-800 h-8 rounded-lg text-white" />
                              </div>
                              <div className="space-y-1">
                                <label className="text-[10px] font-bold text-gray-450 uppercase">Company Email</label>
                                <Input value={editCompanyEmail} onChange={e => setEditCompanyEmail(e.target.value)} className="bg-gray-950 border-gray-800 h-8 rounded-lg text-white" />
                              </div>
                            </div>

                            <div className="grid grid-cols-2 gap-2">
                              <div className="space-y-1">
                                <label className="text-[10px] font-bold text-gray-450 uppercase">Mobile No</label>
                                <Input value={editMobileNo} onChange={e => setEditMobileNo(e.target.value)} className="bg-gray-950 border-gray-800 h-8 rounded-lg text-white" />
                              </div>
                              <div className="space-y-1">
                                <label className="text-[10px] font-bold text-gray-450 uppercase">Company Contact No</label>
                                <Input value={editCompanyContactNo} onChange={e => setEditCompanyContactNo(e.target.value)} className="bg-gray-950 border-gray-800 h-8 rounded-lg text-white" />
                              </div>
                            </div>

                            <div className="space-y-1">
                              <label className="text-[10px] font-bold text-gray-450 uppercase">Need of what</label>
                              <Input value={editNeedOfWhat} onChange={e => setEditNeedOfWhat(e.target.value)} className="bg-gray-950 border-gray-800 h-8 rounded-lg text-white" />
                            </div>

                            <div className="grid grid-cols-2 gap-2">
                              <div className="space-y-1">
                                <label className="text-[10px] font-bold text-gray-450 uppercase">How Much (Budget)</label>
                                <Input value={editHowMuch} onChange={e => setEditHowMuch(e.target.value)} className="bg-gray-950 border-gray-800 h-8 rounded-lg text-white" />
                              </div>
                              <div className="space-y-1">
                                <label className="text-[10px] font-bold text-gray-450 uppercase">Priority</label>
                                <Select value={editPriority} onValueChange={val => setEditPriority(val || 'medium')}>
                                  <SelectTrigger className="bg-gray-955 border-gray-800 h-8 text-xs text-gray-300 rounded-lg">
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent className="bg-gray-950 border-gray-800 text-gray-300">
                                    <SelectItem value="low">Low</SelectItem>
                                    <SelectItem value="medium">Medium</SelectItem>
                                    <SelectItem value="high">High</SelectItem>
                                  </SelectContent>
                                </Select>
                              </div>
                            </div>

                            <div className="grid grid-cols-3 gap-2">
                              <div className="space-y-1">
                                <label className="text-[10px] font-bold text-gray-450 uppercase">Status Stage</label>
                                <Select value={editStatus} onValueChange={val => setEditStatus(val || 'captured')}>
                                  <SelectTrigger className="bg-gray-950 border-gray-800 h-8 text-xs text-gray-305 rounded-lg">
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent className="bg-gray-950 border-gray-800 text-gray-300">
                                    <SelectItem value="captured">Captured</SelectItem>
                                    <SelectItem value="enriched">Enriched</SelectItem>
                                    <SelectItem value="contacted">Contacted</SelectItem>
                                    <SelectItem value="replied">Replied</SelectItem>
                                    <SelectItem value="meeting_scheduled">Meeting Booked</SelectItem>
                                    <SelectItem value="won">Closed Won</SelectItem>
                                    <SelectItem value="lost">Closed Lost</SelectItem>
                                  </SelectContent>
                                </Select>
                              </div>
                              <div className="space-y-1">
                                <label className="text-[10px] font-bold text-gray-450 uppercase">Assigned To</label>
                                <Select value={editAssignedTo} onValueChange={val => setEditAssignedTo(val || 'Sales AI Agent')}>
                                  <SelectTrigger className="bg-gray-955 border-gray-800 h-8 text-xs text-gray-305 rounded-lg">
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent className="bg-gray-950 border-gray-800 text-gray-300">
                                    <SelectItem value="Sales AI Agent">Sales AI Agent</SelectItem>
                                    {members.map(member => (
                                      <SelectItem key={member.id} value={member.name || member.email}>
                                        {member.name || member.email}
                                      </SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                              </div>
                              <div className="space-y-1">
                                <label className="text-[10px] font-bold text-gray-450 uppercase">Score (0-100)</label>
                                <Input 
                                  type="number" 
                                  min={0} 
                                  max={100} 
                                  value={editScore} 
                                  onChange={e => setEditScore(Number(e.target.value) || 0)} 
                                  className="bg-gray-950 border-gray-800 h-8 rounded-lg text-white" 
                                />
                              </div>
                            </div>

                            <div className="grid grid-cols-2 gap-2">
                              <div className="space-y-1">
                                <label className="text-[10px] font-bold text-gray-450 uppercase">Next Follow-up Date</label>
                                <Input 
                                  type="date" 
                                  value={editNextFollowupDate} 
                                  onChange={e => setEditNextFollowupDate(e.target.value)} 
                                  className="bg-gray-950 border-gray-800 h-8 rounded-lg text-white" 
                                />
                              </div>
                              <div className="space-y-1">
                                <label className="text-[10px] font-bold text-gray-455 uppercase">Follow-up Notes / Next Action</label>
                                <Input 
                                  value={editFollowupNotes} 
                                  onChange={e => setEditFollowupNotes(e.target.value)} 
                                  className="bg-gray-950 border-gray-800 h-8 rounded-lg text-white" 
                                />
                              </div>
                            </div>

                            <div className="space-y-1">
                              <label className="text-[10px] font-bold text-gray-455 uppercase">Why (Reason/Pain Point)</label>
                              <Textarea value={editWhy} onChange={e => setEditWhy(e.target.value)} className="bg-gray-950 border-gray-800 text-white rounded-lg text-xs min-h-[60px]" />
                            </div>

                            <div className="space-y-1">
                              <label className="text-[10px] font-bold text-gray-455 uppercase">Target Context</label>
                              <Textarea value={editTargetContext} onChange={e => setEditTargetContext(e.target.value)} className="bg-gray-950 border-gray-800 text-white rounded-lg text-xs min-h-[65px]" />
                            </div>

                            <Button
                              onClick={handleSaveLead}
                              disabled={salesActionLoading}
                              className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-bold h-9 rounded-lg shadow-lg shadow-emerald-500/20"
                            >
                              {salesActionLoading ? 'Saving changes...' : 'Save Prospect Details'}
                            </Button>
                          </div>
                        ) : (
                          /* View Details Mode */
                          <div className="space-y-5">
                            
                            {/* Ownership & Sourcing Card */}
                            <div className="space-y-2.5 bg-gray-900/40 p-4 rounded-2xl border border-gray-850">
                              <div className="flex items-center gap-2 text-xs font-bold text-white border-b border-gray-800/60 pb-1.5">
                                <Users size={13} className="text-emerald-400" /> Ownership & Sourcing
                              </div>
                              <div className="space-y-1.5 text-xs text-gray-350">
                                <div className="flex justify-between items-center">
                                  <span className="text-[10px] text-gray-450 font-semibold">Sourced From:</span>
                                  <span className="font-semibold text-white bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded uppercase text-[9px]">{selectedLead.source || 'Manual Entry'}</span>
                                </div>
                                <div className="flex justify-between items-center">
                                  <span className="text-[10px] text-gray-450 font-semibold">Managed By:</span>
                                  <span className="font-semibold text-white bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded text-[10px] flex items-center gap-1">
                                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-ping"></span>
                                    {selectedLead.assigned_to || 'Sales AI Agent'}
                                  </span>
                                </div>
                              </div>
                            </div>

                            {/* Contact Card */}
                            <div className="space-y-2.5 bg-gray-900/40 p-4 rounded-2xl border border-gray-850">
                              <div className="flex items-center gap-2 text-xs font-bold text-white border-b border-gray-800/60 pb-1.5">
                                <Users size={13} className="text-emerald-400" /> Contact Channels
                              </div>
                              <div className="space-y-1.5 text-xs text-gray-350">
                                <div className="flex justify-between">
                                  <span className="text-[10px] text-gray-450 font-semibold">Personal Email:</span>
                                  <span className="font-mono text-white flex items-center gap-1 select-all">{selectedLead.personal_email || 'Not enriched'}</span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-[10px] text-gray-450 font-semibold">Company Email:</span>
                                  <span className="font-mono text-white flex items-center gap-1 select-all">{selectedLead.company_email || selectedLead.email || 'Not enriched'}</span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-[10px] text-gray-455 font-semibold">Mobile No:</span>
                                  <span className="font-mono text-white select-all">{selectedLead.mobile_no || selectedLead.phone || 'Not enriched'}</span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-[10px] text-gray-455 font-semibold">Company Contact No:</span>
                                  <span className="font-mono text-white select-all">{selectedLead.company_contact_no || 'Not enriched'}</span>
                                </div>
                              </div>
                            </div>

                            {/* Business Opportunity details */}
                            <div className="space-y-3 bg-gray-900/40 p-4 rounded-2xl border border-gray-850">
                              <div className="flex items-center gap-2 text-xs font-bold text-white border-b border-gray-800/60 pb-1.5">
                                <Target size={13} className="text-emerald-400" /> Business Intent
                              </div>
                              
                              <div className="space-y-3 text-xs">
                                <div>
                                  <span className="text-[10px] text-gray-450 font-bold uppercase block tracking-wide">Need Description</span>
                                  <p className="text-gray-200 mt-1 leading-relaxed">{selectedLead.need_of_what || 'Awaiting sales agent analysis'}</p>
                                </div>

                                <div className="grid grid-cols-2 gap-4">
                                  <div>
                                    <span className="text-[10px] text-gray-450 font-bold uppercase block tracking-wide">Deal Valuation</span>
                                    <p className="text-emerald-400 font-extrabold mt-0.5">{selectedLead.how_much || 'Under negotiation'}</p>
                                  </div>
                                  <div>
                                    <span className="text-[10px] text-gray-450 font-bold uppercase block tracking-wide">Priority Setting</span>
                                    <span className={`inline-block text-[9px] font-extrabold uppercase px-2 py-0.5 rounded tracking-wide border mt-0.5 ${
                                      selectedLead.priority === 'high' 
                                        ? 'bg-rose-500/10 text-rose-450 border-rose-500/20' 
                                        : selectedLead.priority === 'medium' 
                                          ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' 
                                          : 'bg-gray-500/10 text-gray-400 border-gray-800'
                                    }`}>
                                      {selectedLead.priority || 'medium'}
                                    </span>
                                  </div>
                                </div>

                                <div>
                                  <span className="text-[10px] text-gray-455 font-bold uppercase block tracking-wide">Pain point context (Why)</span>
                                  <p className="text-gray-300 mt-1 leading-relaxed">{selectedLead.why || 'Awaiting detail enrichment'}</p>
                                </div>

                                <div>
                                  <span className="text-[10px] text-gray-455 font-bold uppercase block tracking-wide">Target Segment Context</span>
                                  <p className="text-gray-300 mt-1 leading-relaxed">{selectedLead.target_context || 'Not enriched yet'}</p>
                                </div>
                              </div>
                            </div>

                            {/* Follow-up Scheduler Card */}
                            <div className="space-y-2.5 bg-gray-900/40 p-4 rounded-2xl border border-gray-850">
                              <div className="flex items-center gap-2 text-xs font-bold text-white border-b border-gray-800/60 pb-1.5">
                                <Calendar size={13} className="text-emerald-400" /> Next Follow-up Schedule
                              </div>
                              <div className="space-y-1.5 text-xs text-gray-350">
                                <div className="flex justify-between items-center">
                                  <span className="text-[10px] text-gray-450 font-semibold">Planned Date:</span>
                                  {selectedLead.data?.next_followup_date ? (
                                    <span className={`font-mono font-bold px-2 py-0.5 rounded text-[10px] ${
                                      new Date(selectedLead.data.next_followup_date) < new Date(new Date().setHours(0,0,0,0))
                                        ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20 flex items-center gap-1'
                                        : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                    }`}>
                                      {new Date(selectedLead.data.next_followup_date) < new Date(new Date().setHours(0,0,0,0)) && <AlertCircle size={10} className="animate-bounce" />}
                                      {selectedLead.data.next_followup_date}
                                      {new Date(selectedLead.data.next_followup_date) < new Date(new Date().setHours(0,0,0,0)) && " (Overdue)"}
                                    </span>
                                  ) : (
                                    <span className="text-gray-500 italic">No follow-up scheduled</span>
                                  )}
                                </div>
                                {selectedLead.data?.followup_notes && (
                                  <div className="mt-1 pt-1.5 border-t border-gray-800/40">
                                    <span className="text-[9px] text-gray-450 font-bold uppercase tracking-wider block">Planned Action / Notes</span>
                                    <p className="text-gray-200 mt-0.5 leading-relaxed text-[11px]">{selectedLead.data.followup_notes}</p>
                                  </div>
                                )}
                              </div>
                            </div>

                            {/* Action Checklist (Tasks) Card */}
                            <div className="space-y-3 bg-gray-900/40 p-4 rounded-2xl border border-gray-850">
                              <div className="flex items-center justify-between text-xs font-bold text-white border-b border-gray-800/60 pb-1.5">
                                <div className="flex items-center gap-2">
                                  <CheckSquare size={13} className="text-emerald-400" /> Action Checklist ({(selectedLead.data?.tasks || []).filter((t: any) => t.completed).length}/{(selectedLead.data?.tasks || []).length})
                                </div>
                              </div>
                              
                              <div className="space-y-2 text-xs">
                                {!(selectedLead.data?.tasks) || selectedLead.data.tasks.length === 0 ? (
                                  <p className="text-gray-500 italic text-[11px] py-1">No action items defined. Add one below!</p>
                                ) : (
                                  <div className="space-y-1.5 max-h-[150px] overflow-y-auto custom-scrollbar pr-1">
                                    {selectedLead.data.tasks.map((task: any) => (
                                      <div key={task.id} className="flex items-center justify-between gap-2 bg-gray-950/30 p-2 rounded-lg border border-gray-850/50 hover:bg-gray-950/60 transition-colors">
                                        <label className="flex items-center gap-2 cursor-pointer flex-1 min-w-0">
                                          <input
                                            type="checkbox"
                                            checked={task.completed}
                                            onChange={() => handleToggleTask(task.id)}
                                            className="rounded border-gray-800 bg-gray-950 text-emerald-500 focus:ring-emerald-500/25 h-3.5 w-3.5 cursor-pointer"
                                          />
                                          <span className={`text-[11px] truncate ${task.completed ? 'line-through text-gray-500' : 'text-gray-200'}`}>
                                            {task.title}
                                          </span>
                                        </label>
                                        <button
                                          onClick={() => handleDeleteTask(task.id)}
                                          className="text-gray-500 hover:text-rose-400 transition-colors p-0.5 rounded"
                                        >
                                          <Trash2 size={12} />
                                        </button>
                                      </div>
                                    ))}
                                  </div>
                                )}
                                
                                <div className="flex gap-2 mt-2 pt-1 border-t border-gray-800/40">
                                  <Input
                                    placeholder="Add custom task..."
                                    value={newTaskTitle}
                                    onChange={e => setNewTaskTitle(e.target.value)}
                                    onKeyDown={e => {
                                      if (e.key === 'Enter') {
                                        handleAddTask(newTaskTitle);
                                      }
                                    }}
                                    className="bg-gray-950 border-gray-800 h-8 rounded-lg text-xs flex-1 text-white placeholder:text-gray-650"
                                  />
                                  <Button
                                    onClick={() => handleAddTask(newTaskTitle)}
                                    className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold h-8 px-3 rounded-lg text-xs"
                                  >
                                    Add
                                  </Button>
                                </div>
                              </div>
                            </div>

                            {/* AI Enrichment Insights */}
                            {selectedLead.data?.enrichment?.llm && (
                              <div className="space-y-3 bg-emerald-950/10 p-4 rounded-2xl border border-emerald-500/20 shadow-lg shadow-emerald-500/5 relative overflow-hidden">
                                <div className="absolute top-0 right-0 p-2 text-emerald-400 opacity-20">
                                  <Cpu size={24} />
                                </div>
                                <div className="flex items-center gap-2 text-xs font-bold text-emerald-400 border-b border-emerald-500/20 pb-1.5">
                                  <Sparkles size={13} /> AI Sourcing & Enrichment
                                </div>
                                <div className="space-y-2.5 text-xs">
                                  <div className="grid grid-cols-2 gap-2 text-gray-300">
                                    <div>
                                      <span className="text-[9px] text-gray-450 font-bold uppercase tracking-wider block">Job Title</span>
                                      <span className="font-semibold text-white">{selectedLead.data.enrichment.llm.title || 'N/A'}</span>
                                    </div>
                                    <div>
                                      <span className="text-[9px] text-gray-450 font-bold uppercase tracking-wider block">Industry</span>
                                      <span className="font-semibold text-white">{selectedLead.data.enrichment.llm.industry || 'N/A'}</span>
                                    </div>
                                    <div>
                                      <span className="text-[9px] text-gray-450 font-bold uppercase tracking-wider block">Company Size</span>
                                      <span className="font-semibold text-white">{selectedLead.data.enrichment.llm.company_size || 'N/A'}</span>
                                    </div>
                                    <div>
                                      <span className="text-[9px] text-gray-450 font-bold uppercase tracking-wider block">Confidence Score</span>
                                      <span className="font-mono text-emerald-400 font-bold">★ {selectedLead.score || 50}/100</span>
                                    </div>
                                  </div>

                                  {selectedLead.data.enrichment.llm.pain_points && selectedLead.data.enrichment.llm.pain_points.length > 0 && (
                                    <div>
                                      <span className="text-[9px] text-gray-455 font-bold uppercase tracking-wider block mb-1">Identified Pain Points</span>
                                      <div className="flex flex-wrap gap-1.5">
                                        {selectedLead.data.enrichment.llm.pain_points.map((pt: string, idx: number) => (
                                          <span key={idx} className="bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 px-2 py-0.5 rounded text-[10px] font-medium">
                                            {pt}
                                          </span>
                                        ))}
                                      </div>
                                    </div>
                                  )}

                                  {selectedLead.data.enrichment.llm.outreach_angle && (
                                    <div className="bg-emerald-950/20 border border-emerald-500/10 p-2.5 rounded-xl">
                                      <span className="text-[9px] text-emerald-400 font-extrabold uppercase tracking-wider block">Recommended Outreach Angle</span>
                                      <p className="text-gray-300 mt-1 leading-relaxed text-[11px] italic">"{selectedLead.data.enrichment.llm.outreach_angle}"</p>
                                    </div>
                                  )}
                                </div>
                              </div>
                            )}

                            {/* AI Conversation Analysis */}
                            {selectedLead.data?.reply_classification && (
                              <div className="space-y-3 bg-violet-950/10 p-4 rounded-2xl border border-violet-500/20 shadow-lg shadow-violet-500/5 relative overflow-hidden">
                                <div className="absolute top-0 right-0 p-2 text-violet-400 opacity-20">
                                  <Bot size={24} />
                                </div>
                                <div className="flex items-center gap-2 text-xs font-bold text-violet-400 border-b border-violet-500/20 pb-1.5">
                                  <MessageSquare size={13} /> AI Conversation Analysis
                                </div>
                                <div className="space-y-3.5 text-xs">
                                  <div className="grid grid-cols-2 gap-2 text-gray-300">
                                    <div>
                                      <span className="text-[9px] text-gray-450 font-bold uppercase tracking-wider block">Response Intent</span>
                                      <span className={`inline-block text-[9px] font-extrabold uppercase px-2 py-0.5 rounded tracking-wide border mt-0.5 ${
                                        selectedLead.data.reply_classification.intent === 'interested'
                                          ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20'
                                          : selectedLead.data.reply_classification.intent === 'decline'
                                            ? 'bg-rose-500/15 text-rose-400 border-rose-500/20'
                                            : 'bg-gray-500/15 text-gray-400 border-gray-800'
                                      }`}>
                                        {selectedLead.data.reply_classification.intent || 'neutral'}
                                      </span>
                                    </div>
                                    {selectedLead.data.reply_classification.suggested_time && (
                                      <div>
                                        <span className="text-[9px] text-gray-455 font-bold uppercase tracking-wider block">Meeting Proposed</span>
                                        <span className="font-semibold text-white flex items-center gap-1 mt-0.5 text-[10px]">
                                          📅 {selectedLead.data.reply_classification.suggested_time}
                                        </span>
                                      </div>
                                    )}
                                  </div>

                                  <div>
                                    <span className="text-[9px] text-gray-450 font-bold uppercase tracking-wider block">Reply Summary</span>
                                    <p className="text-gray-300 mt-1 leading-relaxed">{selectedLead.data.reply_classification.summary || 'N/A'}</p>
                                  </div>

                                  {selectedLead.data.reply_classification.suggested_reply && (
                                    <div className="space-y-2 bg-violet-950/20 border border-violet-500/10 p-3 rounded-xl">
                                      <div className="flex justify-between items-center">
                                        <span className="text-[9px] text-violet-400 font-extrabold uppercase tracking-wider">Suggested AI Auto-Reply</span>
                                        <div className="flex gap-2">
                                          <button
                                            onClick={() => {
                                              navigator.clipboard.writeText(selectedLead.data.reply_classification.suggested_reply);
                                              alert("📋 Suggested reply copied to clipboard!");
                                            }}
                                            className="text-[10px] text-violet-400 hover:text-violet-300 font-bold flex items-center gap-0.5 bg-violet-950/50 px-1.5 py-0.5 rounded border border-violet-800/40"
                                          >
                                            Copy
                                          </button>
                                          <button
                                            onClick={async () => {
                                              if (confirm("Send this suggested AI reply email to the prospect?")) {
                                                setSalesActionLoading(true);
                                                try {
                                                  const res = await fetchWithAuth(`${API_URL}/leads/${selectedLead.id}/timeline-note`, {
                                                    method: 'POST',
                                                    headers: { 'Content-Type': 'application/json' },
                                                    body: JSON.stringify({
                                                      content: selectedLead.data.reply_classification.suggested_reply,
                                                      channel: selectedLead.data.outreach_channel || 'email',
                                                      direction: 'outbound'
                                                    })
                                                  });
                                                  if (res.ok) {
                                                    const updated = await res.json();
                                                    setSelectedLead(updated);
                                                    fetchLeads();
                                                    fetchData();
                                                    alert("🚀 Suggested reply sent/logged successfully!");
                                                  } else {
                                                    alert("Failed to send/log reply");
                                                  }
                                                } catch (err) {
                                                  console.error(err);
                                                } finally {
                                                  setSalesActionLoading(false);
                                                }
                                              }
                                            }}
                                            className="text-[10px] text-emerald-400 hover:text-emerald-300 font-bold flex items-center gap-0.5 bg-emerald-950/50 px-1.5 py-0.5 rounded border border-emerald-800/40"
                                          >
                                            Send
                                          </button>
                                        </div>
                                      </div>
                                      <p className="text-gray-250 leading-relaxed text-[11px] whitespace-pre-wrap">{selectedLead.data.reply_classification.suggested_reply}</p>
                                    </div>
                                  )}
                                </div>
                              </div>
                            )}

                            {/* Outreach Actions Center */}
                            <div className="space-y-3 bg-gray-900/40 p-4 rounded-2xl border border-gray-850">
                              <div className="flex items-center gap-2 text-xs font-bold text-white border-b border-gray-800/60 pb-1.5">
                                <Activity size={13} className="text-emerald-400" /> Outreach Actions
                              </div>
                              
                              {/* Email Config Warning */}
                              {emailConfig && !emailConfig.any_configured && (
                                <div className="bg-amber-500/10 border border-amber-500/20 p-2.5 rounded-xl">
                                  <div className="flex items-center gap-1.5 text-[10px] font-bold text-amber-450 uppercase">
                                    <AlertCircle size={12} /> SMTP / Gmail Not Configured
                                  </div>
                                  <p className="text-[10px] text-gray-400 mt-1 leading-relaxed">
                                    You can draft AI emails, but they won't be sent until you add your email credentials in the Platform Settings.
                                  </p>
                                </div>
                              )}
                              
                              <div className="grid grid-cols-2 gap-2 pt-1">
                                <Button
                                  onClick={() => handleSendOutreachSmart(selectedLead.id)}
                                  disabled={sendingOutreachSmart}
                                  variant="outline"
                                  className={`rounded-xl text-xs h-9 text-white shadow ${emailConfig?.any_configured ? 'border-emerald-600 bg-emerald-950/30 hover:bg-emerald-900/50' : 'border-gray-800 hover:bg-gray-800 bg-transparent'}`}
                                >
                                  {sendingOutreachSmart ? (
                                    <Loader2 size={12} className="animate-spin mr-1" />
                                  ) : emailConfig?.any_configured ? (
                                    '✉️ Send AI Outreach'
                                  ) : (
                                    '📝 Draft AI Email'
                                  )}
                                </Button>
                                
                                <Button
                                  onClick={handleCheckReplies}
                                  disabled={checkingReplies}
                                  variant="outline"
                                  className="border-gray-800 hover:bg-gray-800 text-white rounded-xl text-xs h-9 bg-transparent shadow"
                                >
                                  {checkingReplies ? (
                                    <Loader2 size={12} className="animate-spin mr-1" />
                                  ) : (
                                    '🔄 Check Replies'
                                  )}
                                </Button>
                              </div>
                              
                              {lastReplyCheckResult && (
                                <div className={`text-[10px] p-2 rounded-lg border ${lastReplyCheckResult.queued > 0 ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-gray-800/40 border-gray-800 text-gray-400'}`}>
                                  {lastReplyCheckResult.message}
                                </div>
                              )}
                            </div>

                            {/* Log Human Update Form */}
                            <div className="space-y-3 bg-gray-900/40 p-4 rounded-2xl border border-gray-850">
                              <div className="flex items-center gap-2 text-xs font-bold text-white border-b border-gray-800/60 pb-1.5">
                                <MessageSquare size={13} className="text-emerald-400" /> Log Human Update / Note
                              </div>
                              
                              <div className="space-y-2 text-xs">
                                <div className="grid grid-cols-2 gap-2">
                                  <div className="flex flex-col gap-1">
                                    <label className="text-[9px] font-bold text-gray-500 uppercase tracking-wider">Channel</label>
                                    <Select value={noteChannel} onValueChange={val => setNoteChannel(val || 'note')}>
                                      <SelectTrigger className="h-8 bg-gray-950 border-gray-800 text-[11px] text-gray-300 rounded-lg">
                                        <SelectValue />
                                      </SelectTrigger>
                                      <SelectContent className="bg-gray-950 border-gray-850 text-gray-305">
                                        <SelectItem value="note">Internal Note</SelectItem>
                                        <SelectItem value="call">Phone Call</SelectItem>
                                        <SelectItem value="email">Email Interaction</SelectItem>
                                        <SelectItem value="whatsapp">WhatsApp Text</SelectItem>
                                      </SelectContent>
                                    </Select>
                                  </div>
                                  <div className="flex flex-col gap-1">
                                    <label className="text-[9px] font-bold text-gray-500 uppercase tracking-wider">Direction</label>
                                    <Select value={noteDirection} onValueChange={val => setNoteDirection(val || 'outbound')}>
                                      <SelectTrigger className="h-8 bg-gray-950 border-gray-800 text-[11px] text-gray-300 rounded-lg">
                                        <SelectValue />
                                      </SelectTrigger>
                                      <SelectContent className="bg-gray-950 border-gray-850 text-gray-305">
                                        <SelectItem value="outbound">Outbound Contact</SelectItem>
                                        <SelectItem value="inbound">Inbound Response</SelectItem>
                                        <SelectItem value="internal">Internal Only</SelectItem>
                                      </SelectContent>
                                    </Select>
                                  </div>
                                </div>
                                
                                <div className="space-y-1">
                                  <label className="text-[9px] font-bold text-gray-500 uppercase tracking-wider">Update Details</label>
                                  <Textarea
                                    placeholder="Spoke with prospect, wants demo next week, etc."
                                    value={noteText}
                                    onChange={e => setNoteText(e.target.value)}
                                    className="bg-gray-950 border-gray-800 text-white rounded-lg text-xs min-h-[50px] placeholder:text-gray-600 focus:border-emerald-500 focus:ring-emerald-500/20"
                                  />
                                </div>

                                <Button
                                  onClick={handleLogHumanUpdate}
                                  disabled={salesActionLoading || !noteText.trim()}
                                  className="w-full bg-emerald-650 hover:bg-emerald-600 text-white font-bold h-8 rounded-lg text-xs shadow-md shadow-emerald-500/10"
                                >
                                  {salesActionLoading ? 'Saving...' : 'Log Human Update'}
                                </Button>
                              </div>
                            </div>

                            {/* Conversation timeline history */}
                            <div className="space-y-3">
                              <div className="flex items-center justify-between text-xs font-bold text-white border-b border-gray-800/60 pb-1.5">
                                <span className="text-[10px] text-gray-400 font-extrabold uppercase tracking-widest">Outreach History</span>
                                <div className="flex gap-1 bg-gray-950/60 p-0.5 border border-gray-850 rounded-lg">
                                  {[
                                    { id: 'all', label: 'All' },
                                    { id: 'email', label: 'Emails' },
                                    { id: 'call', label: 'Calls' },
                                    { id: 'note', label: 'Notes' },
                                    { id: 'meeting', label: 'Meetings' }
                                  ].map(t => (
                                    <button
                                      key={t.id}
                                      onClick={() => setTimelineFilter(t.id)}
                                      className={`px-1.5 py-0.5 rounded text-[9px] font-bold transition-all ${
                                        timelineFilter === t.id
                                          ? 'bg-emerald-600 text-white'
                                          : 'text-gray-400 hover:text-white'
                                      }`}
                                    >
                                      {t.label}
                                    </button>
                                  ))}
                                </div>
                              </div>
                              
                              {(() => {
                                const conversation = selectedLead.data?.conversation || [];
                                const filteredConversation = conversation.filter((msg: any) => {
                                  if (timelineFilter === 'all') return true;
                                  const channel = (msg.channel || '').toLowerCase();
                                  if (timelineFilter === 'email') {
                                    return channel === 'email' || channel === 'smtp';
                                  }
                                  if (timelineFilter === 'meeting') {
                                    return channel === 'meeting' || channel.includes('meet') || (msg.subject || '').toLowerCase().includes('meeting') || (msg.content || '').toLowerCase().includes('meeting');
                                  }
                                  return channel === timelineFilter;
                                });
                                
                                return filteredConversation.length === 0 ? (
                                  <div className="text-center py-4 bg-gray-900/10 border border-dashed border-gray-800 rounded-2xl text-xs text-gray-500 font-medium">
                                    No matching outreach history found.
                                  </div>
                                ) : (
                                  <div className="space-y-3 relative before:absolute before:left-3 before:top-2 before:bottom-2 before:w-[1px] before:bg-gray-800">
                                    {filteredConversation.map((msg: any, index: number) => (
                                      <div key={index} className="flex gap-3 relative z-10 text-xs">
                                        <div className={`h-7 w-7 rounded-full flex items-center justify-center text-xs shadow border ${
                                          msg.author?.includes('AI')
                                            ? 'bg-purple-600/15 border-purple-500/20 text-purple-400'
                                            : msg.direction === 'outbound' 
                                              ? 'bg-blue-600/15 border-blue-500/20 text-blue-400' 
                                              : msg.direction === 'inbound'
                                                ? 'bg-emerald-600/15 border-emerald-500/20 text-emerald-400'
                                                : 'bg-amber-600/15 border-amber-500/20 text-amber-450'
                                        }`}>
                                          {msg.author?.includes('AI') ? '🤖' : '👤'}
                                        </div>
                                        <div className="flex-1 bg-gray-900/35 border border-gray-850 p-3 rounded-2xl shadow">
                                          <div className="flex justify-between items-center gap-2">
                                            <span className="font-bold text-white capitalize text-[11px] flex items-center gap-1.5 flex-wrap">
                                              {msg.direction === 'outbound' ? 'Outbound' : msg.direction === 'inbound' ? 'Inbound' : 'Note'}
                                              <span className="text-[9px] bg-gray-800 text-gray-455 border border-gray-750 px-1.5 py-0.5 rounded font-mono uppercase">
                                                {msg.channel || 'smtp'}
                                              </span>
                                              {msg.author && (
                                                <span className={`text-[8px] px-1.5 py-0.5 rounded font-bold border ${
                                                  msg.author.includes('AI') 
                                                    ? 'bg-purple-500/10 text-purple-400 border-purple-500/20' 
                                                    : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                                                }`}>
                                                  {msg.author}
                                                </span>
                                              )}
                                            </span>
                                            <span className="text-[9px] text-gray-450 font-mono">
                                              {msg.at ? new Date(msg.at).toLocaleDateString() : 'Just now'}
                                            </span>
                                          </div>
                                          {msg.subject && (
                                            <div className="text-[10px] text-emerald-400 font-bold mt-1">Subj: {msg.subject}</div>
                                          )}
                                          <p className="text-[11px] text-gray-300 leading-relaxed mt-1.5 whitespace-pre-wrap">{msg.content}</p>
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                );
                              })()}
                            </div>

                          </div>
                        )}

                      </div>
                    </Card>
                  )}
                </div>

              </div>
              )}

              {activeSalesTab === 'config' && (
                <Card className="hud-card neon-glow-emerald rounded-3xl p-8 relative">
                  <div className="cyberpunk-scanline rounded-3xl z-0" />
                  <div className="z-10 relative">
                  <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-emerald-500 to-transparent" />
                  
                  <div className="mb-6">
                    <h2 className="text-xl font-extrabold text-white">⚙️ Sales AI V3 Business Configuration</h2>
                    <p className="text-xs text-gray-400 mt-1">Configure your product/service parameters, unique selling proposition, case studies, and target criteria once. Sales AI will handle discovery and qualification autonomously.</p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    
                    <div className="space-y-4">
                      {/* AI Model Configuration */}
                      <div className="flex flex-col gap-1">
                        <label className="text-[10px] font-bold text-gray-450 uppercase tracking-wider">AI Model Settings</label>
                        <div className="grid grid-cols-2 gap-2">
                          <Select value={salesTextProvider} onValueChange={val => {
                            setSalesTextProvider(val || 'auto');
                            setSalesTextModel(''); // reset model when provider changes
                          }}>
                            <SelectTrigger className="bg-gray-900/60 border-gray-800 text-white rounded-xl h-11">
                              <SelectValue placeholder="Provider" />
                            </SelectTrigger>
                            <SelectContent className="bg-gray-950 border-gray-800 text-white">
                              <SelectItem value="auto" className="font-bold text-amber-400">✨ Auto (AI Choice)</SelectItem>
                              <SelectItem value="gemini">Google Gemini</SelectItem>
                              <SelectItem value="openai">OpenAI</SelectItem>
                              <SelectItem value="anthropic">Anthropic</SelectItem>
                            </SelectContent>
                          </Select>
                          <Select value={salesTextModel} onValueChange={val => setSalesTextModel(val || '')}>
                            <SelectTrigger className="bg-gray-900/60 border-gray-800 text-white rounded-xl h-11">
                              <SelectValue placeholder="Default Model" />
                            </SelectTrigger>
                            <SelectContent className="bg-gray-950 border-gray-800 text-white">
                              <SelectItem value="">Default</SelectItem>
                              {salesTextProvider === 'gemini' && (
                                <>
                                  <SelectItem value="gemini-2.5-flash">Gemini 2.5 Flash</SelectItem>
                                  <SelectItem value="gemini-2.5-pro">Gemini 2.5 Pro</SelectItem>
                                  <SelectItem value="gemini-1.5-flash">Gemini 1.5 Flash</SelectItem>
                                  <SelectItem value="gemini-1.5-pro">Gemini 1.5 Pro</SelectItem>
                                </>
                              )}
                              {salesTextProvider === 'openai' && (
                                <>
                                  <SelectItem value="gpt-4o">GPT-4o</SelectItem>
                                  <SelectItem value="gpt-4o-mini">GPT-4o Mini</SelectItem>
                                  <SelectItem value="o1">o1</SelectItem>
                                  <SelectItem value="o3-mini">o3-mini</SelectItem>
                                </>
                              )}
                              {salesTextProvider === 'anthropic' && (
                                <>
                                  <SelectItem value="claude-3-7-sonnet-20250219">Claude 3.7 Sonnet</SelectItem>
                                  <SelectItem value="claude-3-5-sonnet-20241022">Claude 3.5 Sonnet</SelectItem>
                                  <SelectItem value="claude-3-5-haiku-20241022">Claude 3.5 Haiku</SelectItem>
                                  <SelectItem value="claude-3-haiku-20240307">Claude 3 Haiku</SelectItem>
                                </>
                              )}
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="grid grid-cols-2 gap-2 mt-2">
                          <div className="flex flex-col gap-1">
                            <label className="text-[10px] font-bold text-gray-450 uppercase tracking-wider">Target Lead Count</label>
                            <Input
                              type="number"
                              min={1}
                              max={500}
                              value={salesTargetLeadCount}
                              onChange={(e) => setSalesTargetLeadCount(parseInt(e.target.value) || 50)}
                              className="bg-gray-900/60 border-gray-800 text-white rounded-xl h-11"
                              placeholder="e.g. 50"
                            />
                          </div>
                        </div>
                        
                        <div className="mt-2">
                          <Button
                            onClick={handlePreviewPlan}
                            disabled={salesActionLoading}
                            variant="outline"
                            className="w-full bg-gray-900 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/10 rounded-xl h-10 flex items-center justify-center gap-2"
                          >
                            {salesActionLoading ? <Loader2 className="animate-spin" size={16} /> : <Sparkles size={16} />}
                            Preview AI Routing Plan
                          </Button>
                        </div>

                        <p className="text-[10px] text-emerald-500/80 mt-1 pl-1">
                          The AI engine driving the autonomous 10-step pipeline.
                        </p>
                      </div>

                      {/* AI Plan Review Modal */}
                      <Dialog open={isPlanReviewModalOpen} onOpenChange={setIsPlanReviewModalOpen}>
                        <DialogContent className="glass-panel border-emerald-500/20 text-white rounded-3xl max-w-md">
                          <DialogHeader>
                            <DialogTitle className="text-white font-extrabold text-xl flex items-center gap-2">
                              <Sparkles size={20} className="text-emerald-400" />
                              AI Routing Plan
                            </DialogTitle>
                          </DialogHeader>
                          {planReviewData && (
                            <div className="space-y-4 py-2">
                              <div className="bg-gray-900/50 rounded-xl p-4 border border-gray-800">
                                <div className="text-xs text-gray-400 font-bold uppercase mb-1">Selected Provider</div>
                                <div className="text-lg font-bold text-white capitalize">{planReviewData.selected_provider}</div>
                                
                                <div className="text-xs text-gray-400 font-bold uppercase mb-1 mt-4">Selected Model</div>
                                <div className="text-sm font-mono text-emerald-400">{planReviewData.selected_model}</div>

                                <div className="grid grid-cols-2 gap-4 mt-4 pt-4 border-t border-gray-800">
                                  <div>
                                    <div className="text-xs text-gray-400 font-bold">Estimated Cost (1M tokens)</div>
                                    <div className="text-sm font-bold text-white">{planReviewData.estimated_cost_per_1m_tokens}</div>
                                  </div>
                                  <div>
                                    <div className="text-xs text-gray-400 font-bold">Latency</div>
                                    <div className="text-sm font-bold text-white">{planReviewData.estimated_latency}</div>
                                  </div>
                                </div>
                              </div>
                              <div className="bg-blue-500/10 border border-blue-500/20 p-3 rounded-xl text-sm text-blue-300">
                                <strong className="block mb-1 text-blue-400 text-xs uppercase">Why this model?</strong>
                                {planReviewData.reasoning}
                              </div>
                              <div className="flex gap-3 pt-2">
                                <Button
                                  onClick={() => setIsPlanReviewModalOpen(false)}
                                  className="flex-1 bg-gray-900 hover:bg-gray-800 text-gray-300 rounded-xl h-11"
                                >
                                  Cancel
                                </Button>
                                <Button
                                  onClick={handleLaunchV3Workflow}
                                  className="flex-1 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold rounded-xl h-11"
                                >
                                  Launch Sales AI V3
                                </Button>
                              </div>
                            </div>
                          )}
                        </DialogContent>
                      </Dialog>

                      <div className="flex flex-col gap-1">
                        <label className="text-[10px] font-bold text-gray-450 uppercase tracking-wider">Company Name</label>
                        <Input
                          placeholder="e.g. Acme Agency"
                          value={profileCompanyName}
                          onChange={e => setProfileCompanyName(e.target.value)}
                          className="bg-gray-900/60 border-gray-800 text-white rounded-xl h-11 focus:border-emerald-500 focus:ring-emerald-500/20"
                        />
                      </div>

                      <div className="flex flex-col gap-1">
                        <label className="text-[10px] font-bold text-gray-455 uppercase tracking-wider">Company Website</label>
                        <Input
                          placeholder="e.g. acmeagency.com"
                          value={profileWebsite}
                          onChange={e => setProfileWebsite(e.target.value)}
                          className="bg-gray-900/60 border-gray-800 text-white rounded-xl h-11 focus:border-emerald-500 focus:ring-emerald-500/20"
                        />
                      </div>

                      <div className="flex flex-col gap-1">
                        <label className="text-[10px] font-bold text-gray-455 uppercase tracking-wider">Industry</label>
                        <Input
                          placeholder="e.g. Software Development / Marketing"
                          value={profileIndustry}
                          onChange={e => setProfileIndustry(e.target.value)}
                          className="bg-gray-900/60 border-gray-800 text-white rounded-xl h-11 focus:border-emerald-500 focus:ring-emerald-500/20"
                        />
                      </div>

                      <div className="flex flex-col gap-1">
                        <label className="text-[10px] font-bold text-gray-455 uppercase tracking-wider">Service/Product Description</label>
                        <Textarea
                          placeholder="Describe what your service or product does in detail..."
                          value={profileServiceDescription}
                          onChange={e => setProfileServiceDescription(e.target.value)}
                          className="bg-gray-900/60 border border-gray-800 text-white rounded-xl p-3 text-sm focus:border-emerald-500 focus:outline-none resize-none min-h-[100px] text-gray-105"
                        />
                      </div>

                      <div className="flex flex-col gap-1">
                        <label className="text-[10px] font-bold text-gray-455 uppercase tracking-wider">Unique Selling Proposition (USP)</label>
                        <Textarea
                          placeholder="What sets your company apart from competitors?"
                          value={profileUsp}
                          onChange={e => setProfileUsp(e.target.value)}
                          className="bg-gray-900/60 border border-gray-800 text-white rounded-xl p-3 text-sm focus:border-emerald-500 focus:outline-none resize-none min-h-[80px] text-gray-105"
                        />
                      </div>

                      <div className="flex flex-col gap-1">
                        <label className="text-[10px] font-bold text-gray-455 uppercase tracking-wider">Offer Details</label>
                        <Textarea
                          placeholder="e.g. 15% discount for manufacturing companies, or custom pricing details..."
                          value={profileOfferDetails}
                          onChange={e => setProfileOfferDetails(e.target.value)}
                          className="bg-gray-900/60 border border-gray-800 text-white rounded-xl p-3 text-sm focus:border-emerald-500 focus:outline-none resize-none min-h-[80px] text-gray-105"
                        />
                      </div>

                      <div className="flex flex-col gap-1">
                        <label className="text-[10px] font-bold text-gray-455 uppercase tracking-wider">Extra Context / Notes</label>
                        <Textarea
                          placeholder="Provide any additional instructions, context, prompt overrides, or notes for the Sales AI..."
                          value={profileExtraContext}
                          onChange={e => setProfileExtraContext(e.target.value)}
                          className="bg-gray-900/60 border border-gray-800 text-white rounded-xl p-3 text-sm focus:border-emerald-500 focus:outline-none resize-none min-h-[100px] text-gray-105"
                        />
                      </div>
                    </div>

                    <div className="space-y-4">
                      <div className="flex flex-col gap-1">
                        <label className="text-[10px] font-bold text-gray-455 uppercase tracking-wider">Target Countries (comma separated)</label>
                        <Input
                          placeholder="e.g. India, UAE"
                          value={profileTargetCountries}
                          onChange={e => setProfileTargetCountries(e.target.value)}
                          className="bg-gray-900/60 border-gray-800 text-white rounded-xl h-11 focus:border-emerald-500 focus:ring-emerald-500/20"
                        />
                      </div>

                      <div className="flex flex-col gap-1">
                        <label className="text-[10px] font-bold text-gray-455 uppercase tracking-wider">Target Industries (comma separated)</label>
                        <Input
                          placeholder="e.g. Manufacturing, Healthcare"
                          value={profileTargetIndustries}
                          onChange={e => setProfileTargetIndustries(e.target.value)}
                          className="bg-gray-900/60 border-gray-800 text-white rounded-xl h-11 focus:border-emerald-500 focus:ring-emerald-500/20"
                        />
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div className="flex flex-col gap-1">
                          <label className="text-[10px] font-bold text-gray-455 uppercase tracking-wider">Target Company Size</label>
                          <Input
                            placeholder="e.g. 10-100 employees"
                            value={profileTargetCompanySize}
                            onChange={e => setProfileTargetCompanySize(e.target.value)}
                            className="bg-gray-900/60 border-gray-800 text-white rounded-xl h-11 focus:border-emerald-500 focus:ring-emerald-500/20"
                          />
                        </div>

                        <div className="flex flex-col gap-1">
                          <label className="text-[10px] font-bold text-gray-455 uppercase tracking-wider">Target Budget Range</label>
                          <Select value={profileTargetBudgetRange} onValueChange={val => setProfileTargetBudgetRange(val || '1L-5L')}>
                            <SelectTrigger className="bg-gray-900/60 border-gray-800 text-white rounded-xl h-11">
                              <SelectValue placeholder="Budget" />
                            </SelectTrigger>
                            <SelectContent className="bg-gray-950 border-gray-800 text-white">
                              <SelectItem value="20K–1L">20K – 1L (INR)</SelectItem>
                              <SelectItem value="1L–3L">1L – 3L (INR)</SelectItem>
                              <SelectItem value="3L–7L">3L – 7L (INR)</SelectItem>
                              <SelectItem value="7L–15L">7L – 15L (INR)</SelectItem>
                              <SelectItem value="15L+">15L+ (INR)</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>

                      {/* Lead Discovery Source Configuration */}
                      <div className="flex flex-col gap-1 mt-4 border-t border-gray-800/40 pt-4">
                        <label className="text-[10px] font-bold text-gray-450 uppercase tracking-wider">Lead Discovery Source</label>
                        <Select value={profilePrimarySource} onValueChange={val => setProfilePrimarySource(val || 'auto')}>
                          <SelectTrigger className="bg-gray-900/60 border-gray-800 text-white rounded-xl h-11 w-1/2">
                            <SelectValue placeholder="Auto (System Decide)" />
                          </SelectTrigger>
                          <SelectContent className="bg-gray-950 border-gray-800 text-white">
                            <SelectItem value="auto">Auto (System Decide)</SelectItem>
                            <SelectItem value="apollo">Apollo</SelectItem>
                            <SelectItem value="hunter">Hunter</SelectItem>
                            <SelectItem value="zoominfo">ZoomInfo</SelectItem>
                            <SelectItem value="google_places">Google Places</SelectItem>
                            <SelectItem value="apify">Apify</SelectItem>
                          </SelectContent>
                        </Select>
                        <p className="text-[10px] text-gray-500 mt-1">
                          If set to Auto, the AI will intelligently route to the best provider for your target industry.
                        </p>
                      </div>

                      <div className="flex flex-col gap-1">
                        <label className="text-[10px] font-bold text-gray-455 uppercase tracking-wider">Target Decision Makers (comma separated)</label>
                        <Input
                          placeholder="e.g. Founder, CEO"
                          value={profileTargetDecisionMakers}
                          onChange={e => setProfileTargetDecisionMakers(e.target.value)}
                          className="bg-gray-900/60 border-gray-800 text-white rounded-xl h-11 focus:border-emerald-500 focus:ring-emerald-500/20"
                        />
                      </div>

                      <div className="flex flex-col gap-1">
                        <label className="text-[10px] font-bold text-gray-455 uppercase tracking-wider">Case Studies / Proof Points</label>
                        <Textarea
                          placeholder="e.g. Delivered 30% ROI within 3 months for manufacturing client..."
                          value={profileCaseStudies}
                          onChange={e => setProfileCaseStudies(e.target.value)}
                          className="bg-gray-900/60 border border-gray-800 text-white rounded-xl p-3 text-sm focus:border-emerald-500 focus:outline-none resize-none min-h-[80px] text-gray-105"
                        />
                      </div>

                      <div className="flex flex-col gap-1">
                        <label className="text-[10px] font-bold text-gray-455 uppercase tracking-wider">Calendar Links (comma separated)</label>
                        <Input
                          placeholder="e.g. https://calendly.com/demo"
                          value={profileCalendars}
                          onChange={e => setProfileCalendars(e.target.value)}
                          className="bg-gray-900/60 border-gray-800 text-white rounded-xl h-11 focus:border-emerald-500 focus:ring-emerald-500/20"
                        />
                      </div>

                      <div className="flex flex-col gap-1">
                        <label className="text-[10px] font-bold text-gray-455 uppercase tracking-wider">Sales Emails (Max 5, comma separated)</label>
                        <Input
                          placeholder="e.g. sales@company.com, info@company.com"
                          value={profileSalesEmails}
                          onChange={e => setProfileSalesEmails(e.target.value)}
                          className="bg-gray-900/60 border-gray-800 text-white rounded-xl h-11 focus:border-emerald-500 focus:ring-emerald-500/20"
                        />
                      </div>

                      <div className="flex flex-col gap-1">
                        <label className="text-[10px] font-bold text-gray-455 uppercase tracking-wider">Support Emails (Max 5, comma separated)</label>
                        <Input
                          placeholder="e.g. support@company.com, help@company.com"
                          value={profileSupportEmails}
                          onChange={e => setProfileSupportEmails(e.target.value)}
                          className="bg-gray-900/60 border-gray-800 text-white rounded-xl h-11 focus:border-emerald-500 focus:ring-emerald-500/20"
                        />
                      </div>

                      <div className="flex flex-col gap-1">
                        <label className="text-[10px] font-bold text-gray-455 uppercase tracking-wider">Communication Channels</label>
                        <div className="flex gap-4 items-center bg-gray-900/60 border border-gray-800 rounded-xl p-3">
                          {['email', 'whatsapp', 'linkedin', 'sms', 'telegram'].map(ch => (
                            <label key={ch} className="flex items-center gap-2 cursor-pointer text-xs capitalize text-gray-300">
                              <input
                                type="checkbox"
                                checked={profileCommunicationChannels.includes(ch)}
                                onChange={e => {
                                  if (e.target.checked) {
                                    setProfileCommunicationChannels(prev => [...prev, ch]);
                                  } else {
                                    setProfileCommunicationChannels(prev => prev.filter(c => c !== ch));
                                  }
                                }}
                                className="rounded border-gray-850 bg-gray-950 text-emerald-500 focus:ring-emerald-500/20"
                              />
                              {ch}
                            </label>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="flex gap-4 pt-6 border-t border-gray-800/40 mt-6">
                    <Button
                      onClick={() => handleSaveProfile()}
                      disabled={profileSaving}
                      className="bg-gray-900 hover:bg-gray-800 text-white border border-gray-800 hover:border-gray-750 font-bold rounded-xl h-12 px-6 flex-1 transition-all"
                    >
                      {profileSaving ? 'Saving...' : '💾 Save Profile Configuration'}
                    </Button>
                    <Button
                      onClick={() => handleLaunchV3Workflow()}
                      disabled={salesActionLoading || profileSaving}
                      className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl h-12 px-6 flex-1 transition-all shadow-lg shadow-emerald-500/25"
                    >
                      {salesActionLoading ? 'Starting Agent...' : '🚀 Launch Autonomous Sales AI V3'}
                    </Button>
                  </div>
                  </div>
                </Card>
              )}

              {activeSalesTab === 'stepper' && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                  <Card className="lg:col-span-2 hud-card neon-glow-emerald rounded-3xl p-6 relative">
                    <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-emerald-500 to-transparent" />
                    
                    <div className="mb-6 flex justify-between items-center border-b border-gray-800/60 pb-4">
                      <div>
                        <h2 className="text-xl font-extrabold text-white flex items-center gap-2">
                          <Bot className="text-emerald-400 h-6 w-6 animate-pulse" /> Live Sales AI V3 Stepper
                        </h2>
                        <p className="text-xs text-gray-400 mt-1">Real-time status of the 10-step autonomous pipeline.</p>
                      </div>
                      <div className="flex items-center gap-2">
                        {workflowStatus.status === 'executing' ? (
                          <span className="text-xs font-bold text-emerald-450 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1 rounded-full flex items-center gap-1.5 animate-pulse">
                            <Loader2 size={12} className="animate-spin" /> RUNNING
                          </span>
                        ) : workflowStatus.status === 'completed' ? (
                          <span className="text-xs font-bold text-emerald-400 bg-emerald-500/15 border border-emerald-500/25 px-3 py-1 rounded-full flex items-center gap-1">
                            <Check size={12} /> COMPLETED
                          </span>
                        ) : workflowStatus.status === 'failed' ? (
                          <span className="text-xs font-bold text-rose-400 bg-rose-500/15 border border-rose-500/25 px-3 py-1 rounded-full flex items-center gap-1">
                            <X size={12} /> FAILED
                          </span>
                        ) : (
                          <span className="text-xs font-bold text-gray-400 bg-gray-900 border border-gray-800 px-3 py-1 rounded-full">
                            IDLE / READY
                          </span>
                        )}
                        <Button
                          onClick={() => handleLaunchV3Workflow()}
                          disabled={salesActionLoading}
                          className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl text-xs h-9 px-4 shadow shadow-emerald-500/20"
                        >
                          Restart Agent
                        </Button>
                      </div>
                    </div>

                    <div className="space-y-6 relative before:absolute before:left-5 before:top-2 before:bottom-2 before:w-[2px] before:bg-gray-850">
                      {[
                        { step: "1", name: "Step 1: Understand Service & Generate ICP" },
                        { step: "2", name: "Step 2: Market Discovery (Free/Paid Sources)" },
                        { step: "3", name: "Step 3: Lead Qualification & Budget Fit" },
                        { step: "4", name: "Step 4: Pain Point Discovery & Web Audit" },
                        { step: "5", name: "Step 5: Decision Maker Lookup & Verification" },
                        { step: "6", name: "Step 6: Weighted Quality Lead Scoring" },
                        { step: "7", name: "Step 7: Hyper-Personalized Outreach Generation" },
                        { step: "8", name: "Step 8: Multi-Channel Sequence Activation" },
                        { step: "9", name: "Step 9: Conversation AI Response Engine" },
                        { step: "10", name: "Step 10: Buying Intent & Meeting Conversion" }
                      ].map((s) => {
                        const stepData = workflowStatus.steps?.[s.step] || {};
                        const isActive = workflowStatus.current_step == Number(s.step);
                        const isCompleted = stepData.status === 'completed' || Number(workflowStatus.current_step) > Number(s.step);
                        const isFailed = stepData.status === 'failed';
                        const isExecuting = stepData.status === 'executing' || (isActive && workflowStatus.status === 'executing');

                        return (
                          <div key={s.step} className="flex gap-4 relative items-start animate-in slide-in-from-bottom-5 duration-250">
                            <div className={`h-10 w-10 rounded-full flex items-center justify-center font-bold text-sm border z-10 transition-all ${
                              isCompleted
                                ? 'bg-emerald-600/15 border-emerald-500 text-emerald-450 shadow-md shadow-emerald-500/10'
                                : isFailed
                                  ? 'bg-rose-600/15 border-rose-500 text-rose-455'
                                  : isExecuting
                                    ? 'bg-emerald-500/10 border-emerald-400 text-emerald-400 animate-pulse-glow shadow-md shadow-emerald-500/15'
                                    : 'bg-gray-950 border-gray-850 text-gray-500'
                            }`}>
                              {isCompleted ? <Check size={16} /> : isFailed ? <X size={16} /> : isExecuting ? <Loader2 size={16} className="animate-spin" /> : s.step}
                            </div>

                            <div className={`flex-1 bg-gray-900/35 border rounded-2xl p-4 transition-all duration-300 ${
                              isExecuting ? 'border-emerald-500/40 bg-emerald-950/5 shadow' : 'border-gray-850'
                            }`}>
                              <h3 className={`text-sm font-black flex items-center gap-2 ${
                                isCompleted ? 'text-white' : isExecuting ? 'text-emerald-400' : 'text-gray-400'
                              }`}>
                                {s.name}
                              </h3>
                              
                              {stepData.result && (
                                <div className="mt-2 bg-gray-955/50 rounded-xl p-3 border border-gray-900/80 text-xs leading-relaxed max-h-48 overflow-y-auto custom-scrollbar font-medium">
                                  {stepData.result.startsWith('{') || stepData.result.startsWith('[') ? (
                                    <pre className="text-[10px] font-mono text-emerald-450 whitespace-pre-wrap">{stepData.result}</pre>
                                  ) : (
                                    <p className="text-gray-300">{stepData.result}</p>
                                  )}
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </Card>

                  <Card className="lg:col-span-1 glass-panel border-transparent rounded-3xl p-5 shadow-2xl relative flex flex-col h-[650px] overflow-hidden">
                    <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-gray-700 to-transparent" />
                    
                    <div className="mb-4 pb-3 border-b border-gray-800/60">
                      <h3 className="text-sm font-extrabold text-white flex items-center gap-1.5">
                        <Activity size={14} className="text-emerald-400" /> System Terminal Logs
                      </h3>
                      <p className="text-[10px] text-gray-455 mt-0.5">Autonomous execution logger stream.</p>
                    </div>

                    <div className="flex-1 bg-gray-955 border border-gray-850/80 rounded-2xl p-4 font-mono text-[10px] leading-relaxed text-emerald-400 overflow-y-auto custom-scrollbar flex flex-col-reverse gap-2 shadow-inner">
                      {workflowStatus.logs && workflowStatus.logs.length > 0 ? (
                        [...workflowStatus.logs].reverse().map((log: string, idx: number) => (
                          <div key={idx} className="border-b border-gray-900/60 pb-1.5 last:border-b-0 whitespace-pre-wrap break-words">
                            <span className="text-gray-500 select-none">&gt; </span>
                            {log}
                          </div>
                        ))
                      ) : (
                        <div className="text-gray-650 italic py-12 text-center">
                          Waiting for agent start sequence...
                        </div>
                      )}
                    </div>
                  </Card>
                </div>
              )}

              {activeSalesTab === 'analytics' && (
                <div className="space-y-6">
                  {/* Top Stats Row */}
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <Card className="glass-panel border-transparent rounded-2xl p-5 shadow-xl relative overflow-hidden">
                      <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-emerald-500 to-transparent" />
                      <div className="flex justify-between items-start">
                        <div>
                          <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Leads Sourced</p>
                          <h3 className="text-2xl font-black text-white mt-1">{totalLeadsFound}</h3>
                          <p className="text-[9px] text-gray-400 mt-1">Total ICP matches discovered</p>
                        </div>
                        <div className="p-2 bg-emerald-500/10 rounded-lg border border-emerald-500/20 text-emerald-400">
                          <Users size={16} />
                        </div>
                      </div>
                    </Card>

                    <Card className="glass-panel border-transparent rounded-2xl p-5 shadow-xl relative overflow-hidden">
                      <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-emerald-500 to-transparent" />
                      <div className="flex justify-between items-start">
                        <div>
                          <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Qualified Leads</p>
                          <h3 className="text-2xl font-black text-white mt-1">{qualifiedLeadsCount}</h3>
                          <p className="text-[9px] text-gray-400 mt-1">Sourcing budget range met</p>
                        </div>
                        <div className="p-2 bg-emerald-500/10 rounded-lg border border-emerald-500/20 text-emerald-400">
                          <CheckSquare size={16} />
                        </div>
                      </div>
                    </Card>

                    <Card className="glass-panel border-transparent rounded-2xl p-5 shadow-xl relative overflow-hidden">
                      <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-rose-500 to-transparent" />
                      <div className="flex justify-between items-start">
                        <div>
                          <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Hot Leads</p>
                          <h3 className="text-2xl font-black text-white mt-1">{hotLeadsCount}</h3>
                          <p className="text-[9px] text-gray-400 mt-1">Lead score &gt;= 85 or high intent</p>
                        </div>
                        <div className="p-2 bg-rose-500/10 rounded-lg border border-rose-500/20 text-rose-455">
                          <Target size={16} />
                        </div>
                      </div>
                    </Card>

                    <Card className="glass-panel border-transparent rounded-2xl p-5 shadow-xl relative overflow-hidden">
                      <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-amber-500 to-transparent" />
                      <div className="flex justify-between items-start">
                        <div>
                          <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Meetings Booked</p>
                          <h3 className="text-2xl font-black text-white mt-1">{meetingsBookedCount}</h3>
                          <p className="text-[9px] text-gray-400 mt-1">Calendar invites accepted</p>
                        </div>
                        <div className="p-2 bg-amber-500/10 rounded-lg border border-amber-500/20 text-amber-450">
                          <Calendar size={16} />
                        </div>
                      </div>
                    </Card>
                  </div>

                  {/* Performance Metrics Row */}
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <Card className="glass-panel border-transparent rounded-2xl p-5 shadow-xl relative overflow-hidden">
                      <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-violet-500 to-transparent" />
                      <div className="flex justify-between items-start">
                        <div>
                          <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Response Rate</p>
                          <h3 className="text-2xl font-black text-white mt-1">{responseRatePct}%</h3>
                          <p className="text-[9px] text-gray-400 mt-1">Outbound reply engagement</p>
                        </div>
                        <div className="p-2 bg-violet-500/10 rounded-lg border border-violet-500/20 text-violet-400">
                          <MessageSquare size={16} />
                        </div>
                      </div>
                    </Card>

                    <Card className="glass-panel border-transparent rounded-2xl p-5 shadow-xl relative overflow-hidden">
                      <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-blue-500 to-transparent" />
                      <div className="flex justify-between items-start">
                        <div>
                          <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Meeting Conv. Rate</p>
                          <h3 className="text-2xl font-black text-white mt-1">{conversionRatePct}%</h3>
                          <p className="text-[9px] text-gray-400 mt-1">Total contacted to meeting ratio</p>
                        </div>
                        <div className="p-2 bg-blue-500/10 rounded-lg border border-blue-500/20 text-blue-400">
                          <TrendingUp size={16} />
                        </div>
                      </div>
                    </Card>

                    <Card className="glass-panel border-transparent rounded-2xl p-5 shadow-xl relative overflow-hidden">
                      <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-emerald-500 to-transparent" />
                      <div className="flex justify-between items-start">
                        <div>
                          <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Pipeline Value</p>
                          <h3 className="text-2xl font-black text-emerald-400 mt-1">{fmtCurrency(activePipelineValue)}</h3>
                          <p className="text-[9px] text-gray-400 mt-1">Value of active opportunities</p>
                        </div>
                        <div className="p-2 bg-emerald-500/10 rounded-lg border border-emerald-500/20 text-emerald-400">
                          <Sparkles size={16} />
                        </div>
                      </div>
                    </Card>

                    <Card className="glass-panel border-transparent rounded-2xl p-5 shadow-xl relative overflow-hidden">
                      <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-emerald-400 to-transparent" />
                      <div className="flex justify-between items-start">
                        <div>
                          <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Revenue Potential</p>
                          <h3 className="text-2xl font-black text-emerald-300 mt-1">{fmtCurrency(totalRevenuePotential)}</h3>
                          <p className="text-[9px] text-gray-400 mt-1">Total value of all pipeline leads</p>
                        </div>
                        <div className="p-2 bg-emerald-400/10 rounded-lg border border-emerald-400/20 text-emerald-300">
                          <TrendingUp size={16} />
                        </div>
                      </div>
                    </Card>
                  </div>

                  {/* Breakdown Tables & Lists */}
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Top Industries */}
                    <Card className="glass-panel border-transparent rounded-3xl p-5 shadow-xl relative flex flex-col">
                      <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-gray-700 to-transparent" />
                      <h3 className="text-xs font-bold text-white uppercase tracking-wider mb-4 flex items-center gap-1.5">
                        🏢 Top Sourced Industries
                      </h3>
                      <div className="space-y-3 flex-1 overflow-y-auto max-h-[300px] custom-scrollbar">
                        {Object.entries(topIndustries)
                          .sort((a, b) => b[1] - a[1])
                          .map(([industry, count]) => {
                            const pct = Math.round((count / (totalLeadsFound || 1)) * 100);
                            return (
                              <div key={industry} className="space-y-1">
                                <div className="flex justify-between text-xs">
                                  <span className="font-extrabold text-gray-300">{industry}</span>
                                  <span className="font-mono text-gray-400">{count} ({pct}%)</span>
                                </div>
                                <div className="h-1.5 w-full bg-gray-900 rounded-full overflow-hidden">
                                  <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${pct}%` }} />
                                </div>
                              </div>
                            );
                          })}
                        {Object.keys(topIndustries).length === 0 && (
                          <div className="text-center text-xs text-gray-500 py-12">No industry data available</div>
                        )}
                      </div>
                    </Card>

                    {/* Sourcing Channels */}
                    <Card className="glass-panel border-transparent rounded-3xl p-5 shadow-xl relative flex flex-col">
                      <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-gray-700 to-transparent" />
                      <h3 className="text-xs font-bold text-white uppercase tracking-wider mb-4 flex items-center gap-1.5">
                        📡 Sourcing Channels
                      </h3>
                      <div className="space-y-3 flex-1 overflow-y-auto max-h-[300px] custom-scrollbar">
                        {Object.entries(sourcingChannels)
                          .sort((a, b) => b[1] - a[1])
                          .map(([channel, count]) => {
                            const pct = Math.round((count / (totalLeadsFound || 1)) * 100);
                            return (
                              <div key={channel} className="space-y-1">
                                <div className="flex justify-between text-xs">
                                  <span className="font-extrabold text-gray-350">{channel || 'Other'}</span>
                                  <span className="font-mono text-gray-400">{count} ({pct}%)</span>
                                </div>
                                <div className="h-1.5 w-full bg-gray-900 rounded-full overflow-hidden">
                                  <div className="h-full bg-blue-500 rounded-full" style={{ width: `${pct}%` }} />
                                </div>
                              </div>
                            );
                          })}
                        {Object.keys(sourcingChannels).length === 0 && (
                          <div className="text-center text-xs text-gray-500 py-12">No channel data available</div>
                        )}
                      </div>
                    </Card>

                    {/* Best Campaigns */}
                    <Card className="glass-panel border-transparent rounded-3xl p-5 shadow-xl relative flex flex-col">
                      <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-gray-700 to-transparent" />
                      <h3 className="text-xs font-bold text-white uppercase tracking-wider mb-4 flex items-center gap-1.5">
                        🔥 Best Performing Campaigns
                      </h3>
                      <div className="space-y-4 flex-1 overflow-y-auto max-h-[300px] custom-scrollbar">
                        {Object.entries(campaignData)
                          .sort((a, b) => b[1].meetings - a[1].meetings)
                          .slice(0, 5)
                          .map(([campaign, data]) => {
                            const conv = data.leads > 0 ? Math.round((data.meetings / data.leads) * 100) : 0;
                            return (
                              <div key={campaign} className="p-3 bg-gray-950/40 border border-gray-800 rounded-xl flex items-center justify-between">
                                <div className="min-w-0 flex-1 pr-2">
                                  <h4 className="text-xs font-black text-white truncate">{campaign}</h4>
                                  <p className="text-[9px] text-gray-400 mt-0.5">{data.leads} Leads Sourced</p>
                                </div>
                                <div className="text-right">
                                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                                    conv >= 40 ? 'bg-emerald-500/10 text-emerald-400' : conv >= 20 ? 'bg-blue-500/10 text-blue-400' : 'bg-gray-800 text-gray-400'
                                  }`}>
                                    {conv}% Conv
                                  </span>
                                  <p className="text-[9px] text-gray-400 mt-1">{data.meetings} Meetings</p>
                                </div>
                              </div>
                            );
                          })}
                        {Object.keys(campaignData).length === 0 && (
                          <div className="text-center text-xs text-gray-500 py-12">No campaign data available</div>
                        )}
                      </div>
                    </Card>
                  </div>
                </div>
              )}

            </div>

      {/* ── Add Lead Manually Modal ─────────────────────────────────────── */}
      <Dialog open={isCreateLeadModalOpen} onOpenChange={setIsCreateLeadModalOpen}>
        <DialogContent className="glass-panel border-emerald-500/20 text-white rounded-3xl max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-white font-extrabold text-xl flex items-center gap-2">
              <Plus size={18} className="text-emerald-400" /> Add Lead Manually
            </DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 py-2">
            {/* Name */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Full Name *</label>
              <Input placeholder="Jane Doe" value={newLeadName} onChange={e => setNewLeadName(e.target.value)}
                className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-emerald-500 focus:ring-emerald-500/20" />
            </div>
            {/* Company */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Company</label>
              <Input placeholder="Acme Corp" value={newLeadCompany} onChange={e => setNewLeadCompany(e.target.value)}
                className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-emerald-500 focus:ring-emerald-500/20" />
            </div>
            {/* Personal Email */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Personal Email *</label>
              <Input placeholder="jane@gmail.com" value={newLeadPersonalEmail} onChange={e => setNewLeadPersonalEmail(e.target.value)}
                className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-emerald-500 focus:ring-emerald-500/20" />
            </div>
            {/* Company Email */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Company Email</label>
              <Input placeholder="jane@acme.com" value={newLeadCompanyEmail} onChange={e => setNewLeadCompanyEmail(e.target.value)}
                className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-emerald-500 focus:ring-emerald-500/20" />
            </div>
            {/* Mobile */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Mobile No.</label>
              <Input placeholder="+1 555 0100" value={newLeadMobileNo} onChange={e => setNewLeadMobileNo(e.target.value)}
                className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-emerald-500 focus:ring-emerald-500/20" />
            </div>
            {/* Company Phone */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Company Phone</label>
              <Input placeholder="+1 555 0200" value={newLeadCompanyContactNo} onChange={e => setNewLeadCompanyContactNo(e.target.value)}
                className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-emerald-500 focus:ring-emerald-500/20" />
            </div>
            {/* Need of What */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Need / Pain Point</label>
              <Input placeholder="e.g. Marketing automation" value={newLeadNeedOfWhat} onChange={e => setNewLeadNeedOfWhat(e.target.value)}
                className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-emerald-500 focus:ring-emerald-500/20" />
            </div>
            {/* Budget */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Budget / How Much</label>
              <Input placeholder="e.g. $2,000/mo" value={newLeadHowMuch} onChange={e => setNewLeadHowMuch(e.target.value)}
                className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-emerald-500 focus:ring-emerald-500/20" />
            </div>
            {/* Why */}
            <div className="flex flex-col gap-1 md:col-span-2">
              <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Why are they a lead?</label>
              <Input placeholder="e.g. Replied to cold email campaign" value={newLeadWhy} onChange={e => setNewLeadWhy(e.target.value)}
                className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-emerald-500 focus:ring-emerald-500/20" />
            </div>
            {/* Target Context */}
            <div className="flex flex-col gap-1 md:col-span-2">
              <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Target Context / Notes</label>
              <textarea placeholder="Extra notes about this lead..." value={newLeadTargetContext} onChange={e => setNewLeadTargetContext(e.target.value)} rows={2}
                className="bg-gray-900/60 border border-gray-800 text-white rounded-xl px-3 py-2 text-sm placeholder:text-gray-600 focus:border-emerald-500 focus:outline-none resize-none" />
            </div>
            {/* Priority */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Priority</label>
              <Select value={newLeadPriority} onValueChange={val => setNewLeadPriority(val || 'medium')}>
                <SelectTrigger className="bg-gray-900/60 border-gray-800 text-white rounded-xl h-10">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-gray-950 border-gray-800 text-white">
                  <SelectItem value="high">🔴 High</SelectItem>
                  <SelectItem value="medium">🟡 Medium</SelectItem>
                  <SelectItem value="low">🟢 Low</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {/* Status */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Status</label>
              <Select value={newLeadStatus} onValueChange={val => setNewLeadStatus(val || 'captured')}>
                <SelectTrigger className="bg-gray-900/60 border-gray-800 text-white rounded-xl h-10">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-gray-950 border-gray-800 text-white">
                  <SelectItem value="captured">Captured</SelectItem>
                  <SelectItem value="enriched">Enriched</SelectItem>
                  <SelectItem value="contacted">Contacted</SelectItem>
                  <SelectItem value="replied">Replied</SelectItem>
                  <SelectItem value="meeting_scheduled">Meeting Scheduled</SelectItem>
                  <SelectItem value="won">Won</SelectItem>
                  <SelectItem value="lost">Lost</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {/* Assignee */}
            <div className="flex flex-col gap-1 md:col-span-2">
              <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Assignee</label>
              <Select value={newLeadAssignedTo} onValueChange={val => setNewLeadAssignedTo(val || 'Sales AI Agent')}>
                <SelectTrigger className="bg-gray-900/60 border-gray-800 text-white rounded-xl h-10">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-gray-950 border-gray-800 text-white">
                  <SelectItem value="Sales AI Agent">Sales AI Agent (Automated)</SelectItem>
                  {members.map(member => (
                    <SelectItem key={member.id} value={member.name || member.email}>
                      {member.name || member.email}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {/* Next Follow-up Date */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Next Follow-up Date</label>
              <Input type="date" value={newLeadNextFollowupDate} onChange={e => setNewLeadNextFollowupDate(e.target.value)}
                className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-emerald-500 focus:ring-emerald-500/20" />
            </div>
            {/* Follow-up Notes */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Follow-up Notes / Next Action</label>
              <Input placeholder="Prepare proposal, send agenda..." value={newLeadFollowupNotes} onChange={e => setNewLeadFollowupNotes(e.target.value)}
                className="bg-gray-900/60 border-gray-800 text-white rounded-xl focus:border-emerald-500 focus:ring-emerald-500/20" />
            </div>
          </div>
          <div className="flex gap-3 pt-2">
            <Button onClick={() => setIsCreateLeadModalOpen(false)} variant="outline"
              className="flex-1 border-gray-700 hover:bg-gray-800 text-gray-300 rounded-xl">
              Cancel
            </Button>
            <Button onClick={handleCreateLead} disabled={creatingLead}
              className="flex-1 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold rounded-xl shadow-lg shadow-emerald-500/20">
              {creatingLead ? <><Loader2 size={15} className="animate-spin mr-2" />Creating...</> : '✅ Create Lead'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── Upload Leads CSV/JSON Modal ──────────────────────────────────── */}
      <Dialog open={isUploadModalOpen} onOpenChange={setIsUploadModalOpen}>
        <DialogContent className="glass-panel border-emerald-500/20 text-white rounded-3xl max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-white font-extrabold text-xl flex items-center gap-2">
              <Upload size={18} className="text-emerald-400" /> Upload Leads (CSV / JSON)
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-5 py-2">
            <p className="text-xs text-gray-400 leading-relaxed">
              Upload a <strong className="text-white">.csv</strong> or <strong className="text-white">.json</strong> file. 
              CSV must have headers like: <code className="bg-gray-800 text-emerald-400 px-1 py-0.5 rounded text-[10px]">name, email, company, phone</code>.
            </p>

            {/* File Picker */}
            <div
              onClick={() => document.getElementById('lead-file-input')?.click()}
              className="border-2 border-dashed border-gray-700 hover:border-emerald-500 rounded-2xl p-8 text-center cursor-pointer transition-colors group"
            >
              <Upload size={28} className="mx-auto mb-3 text-gray-500 group-hover:text-emerald-400 transition-colors" />
              <p className="text-sm font-bold text-gray-300">
                {uploadFile ? uploadFile.name : 'Click to select file'}
              </p>
              <p className="text-[10px] text-gray-500 mt-1">CSV or JSON, max 10MB</p>
              <input
                id="lead-file-input"
                type="file"
                accept=".csv,.json"
                className="hidden"
                onChange={e => setUploadFile(e.target.files?.[0] || null)}
              />
            </div>

            {/* AI enrichment toggle */}
            <div className="flex items-center justify-between bg-gray-900/50 border border-gray-800 rounded-xl px-4 py-3">
              <div>
                <p className="text-xs font-bold text-white">AI Enrichment & Scoring</p>
                <p className="text-[10px] text-gray-400 mt-0.5">Auto-score leads and enrich with AI insights after import</p>
              </div>
              <button
                onClick={() => setUploadWithAI(!uploadWithAI)}
                className={`relative w-10 h-5 rounded-full transition-colors ${uploadWithAI ? 'bg-emerald-600' : 'bg-gray-700'}`}
              >
                <span className={`absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${uploadWithAI ? 'translate-x-5' : 'translate-x-0'}`} />
              </button>
            </div>
          </div>
          <div className="flex gap-3 pt-1">
            <Button onClick={() => { setIsUploadModalOpen(false); setUploadFile(null); }} variant="outline"
              className="flex-1 border-gray-700 hover:bg-gray-800 text-gray-300 rounded-xl">
              Cancel
            </Button>
            <Button onClick={handleUploadLeads} disabled={uploadingLeads || !uploadFile}
              className="flex-1 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold rounded-xl shadow-lg shadow-emerald-500/20 disabled:opacity-50">
              {uploadingLeads ? <><Loader2 size={15} className="animate-spin mr-2" />Uploading...</> : '📤 Upload Leads'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

    </>
  );
}
