'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';

type Tab = 'approvals' | 'policy' | 'billing' | 'employees' | 'roi' | 'crm' | 'compliance' | 'ops';

export default function EnterpriseView({ token }: { token: string }) {
  const [tab, setTab] = useState<Tab>('approvals');
  const [approvals, setApprovals] = useState<any[]>([]);
  const [policy, setPolicy] = useState<any>(null);
  const [entitlements, setEntitlements] = useState<any>(null);
  const [plans, setPlans] = useState<any[]>([]);
  const [employees, setEmployees] = useState<any[]>([]);
  const [standup, setStandup] = useState<any>(null);
  const [roi, setRoi] = useState<any>(null);
  const [dlq, setDlq] = useState<any[]>([]);
  const [crm, setCrm] = useState<any[]>([]);
  const [gdprEmail, setGdprEmail] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  const headers = {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  };

  const load = async () => {
    setLoading(true);
    setMessage('');
    try {
      if (tab === 'approvals') {
        const r = await fetch(`${API_URL}/enterprise/approvals`, { headers });
        if (r.ok) setApprovals(await r.json());
      }
      if (tab === 'policy') {
        const r = await fetch(`${API_URL}/enterprise/policy`, { headers });
        if (r.ok) setPolicy(await r.json());
      }
      if (tab === 'billing') {
        const [e, p] = await Promise.all([
          fetch(`${API_URL}/enterprise/billing/entitlements`, { headers }),
          fetch(`${API_URL}/enterprise/billing/plans`),
        ]);
        if (e.ok) setEntitlements(await e.json());
        if (p.ok) setPlans(await p.json());
      }
      if (tab === 'employees') {
        const [emp, st] = await Promise.all([
          fetch(`${API_URL}/enterprise/ai-employees`, { headers }),
          fetch(`${API_URL}/enterprise/ai-employees/standup`, { headers }),
        ]);
        if (emp.ok) setEmployees(await emp.json());
        if (st.ok) setStandup(await st.json());
      }
      if (tab === 'roi') {
        const r = await fetch(`${API_URL}/enterprise/roi/dashboard`, { headers });
        if (r.ok) setRoi(await r.json());
      }
      if (tab === 'crm') {
        const r = await fetch(`${API_URL}/enterprise/crm/connections`, { headers });
        if (r.ok) setCrm(await r.json());
      }
      if (tab === 'ops') {
        const r = await fetch(`${API_URL}/enterprise/ops/dlq`, { headers });
        if (r.ok) setDlq(await r.json());
      }
    } catch (e: any) {
      setMessage(e.message || 'Load failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, token]);

  const review = async (id: string, approve: boolean) => {
    const r = await fetch(`${API_URL}/enterprise/approvals/${id}/review`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ approve, note: approve ? 'Approved from UI' : 'Rejected from UI' }),
    });
    if (r.ok) {
      setMessage(approve ? 'Approved' : 'Rejected');
      load();
    } else {
      setMessage(await r.text());
    }
  };

  const savePolicy = async () => {
    if (!policy) return;
    const r = await fetch(`${API_URL}/enterprise/policy`, {
      method: 'PUT',
      headers,
      body: JSON.stringify({
        default_mode: policy.default_mode,
        min_confidence: Number(policy.min_confidence),
        max_auto_amount: Number(policy.max_auto_amount),
        support_refuse_if_not_in_kb: !!policy.support_refuse_if_not_in_kb,
        channel_kill_switches: policy.channel_kill_switches || {},
        agent_kill_switches: policy.agent_kill_switches || {},
      }),
    });
    setMessage(r.ok ? 'Policy saved' : await r.text());
    load();
  };

  const changePlan = async (code: string) => {
    const r = await fetch(`${API_URL}/enterprise/billing/plan`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ plan_code: code }),
    });
    setMessage(r.ok ? `Plan set to ${code}` : await r.text());
    load();
  };

  const loadRazorpayScript = (): Promise<boolean> =>
    new Promise((resolve) => {
      if (typeof window !== 'undefined' && (window as any).Razorpay) {
        resolve(true);
        return;
      }
      const s = document.createElement('script');
      s.src = 'https://checkout.razorpay.com/v1/checkout.js';
      s.onload = () => resolve(true);
      s.onerror = () => resolve(false);
      document.body.appendChild(s);
    });

  const payWithRazorpay = async (planCode: string) => {
    setMessage('');
    try {
      const orderRes = await fetch(`${API_URL}/enterprise/billing/razorpay/create-order`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ plan_code: planCode }),
      });
      if (!orderRes.ok) {
        setMessage(await orderRes.text());
        return;
      }
      const order = await orderRes.json();
      const ok = await loadRazorpayScript();
      if (!ok) {
        setMessage('Failed to load Razorpay checkout script');
        return;
      }
      const rzp = new (window as any).Razorpay({
        key: order.key_id,
        amount: order.amount_paise,
        currency: order.currency,
        name: order.name || 'OctaOS',
        description: order.description,
        order_id: order.razorpay_order_id,
        prefill: order.prefill || {},
        notes: order.notes || {},
        theme: order.theme || { color: '#8b5cf6' },
        handler: async (response: any) => {
          const v = await fetch(`${API_URL}/enterprise/billing/razorpay/verify`, {
            method: 'POST',
            headers,
            body: JSON.stringify({
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
            }),
          });
          if (v.ok) {
            setMessage(`Payment successful — plan ${planCode} activated`);
            load();
          } else {
            setMessage(await v.text());
          }
        },
      });
      rzp.on('payment.failed', (resp: any) => {
        setMessage(resp?.error?.description || 'Payment failed');
      });
      rzp.open();
    } catch (e: any) {
      setMessage(e.message || 'Razorpay error');
    }
  };

  const gdpr = async (type: 'export' | 'delete') => {
    const r = await fetch(`${API_URL}/enterprise/compliance/gdpr/${type}`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ subject_email: gdprEmail }),
    });
    if (r.ok) {
      const data = await r.json();
      setMessage(`${type} completed: ${data.id}`);
    } else setMessage(await r.text());
  };

  const replayDlq = async (id: string) => {
    const r = await fetch(`${API_URL}/enterprise/ops/dlq/${id}/replay`, { method: 'POST', headers });
    setMessage(r.ok ? 'Replay queued' : await r.text());
    load();
  };

  const tabs: { id: Tab; label: string }[] = [
    { id: 'approvals', label: 'Approvals' },
    { id: 'policy', label: 'Policy' },
    { id: 'billing', label: 'Billing' },
    { id: 'employees', label: 'AI Employees' },
    { id: 'roi', label: 'ROI' },
    { id: 'crm', label: 'CRM Sync' },
    { id: 'compliance', label: 'Compliance' },
    { id: 'ops', label: 'Ops / DLQ' },
  ];

  return (
    <div className="space-y-4 p-1">
      <div className="flex flex-wrap gap-2">
        {tabs.map((t) => (
          <Button
            key={t.id}
            size="sm"
            variant={tab === t.id ? 'default' : 'outline'}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </Button>
        ))}
      </div>

      {message && (
        <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded px-3 py-2">
          {message}
        </div>
      )}
      {loading && <div className="text-xs text-muted-foreground">Loading…</div>}

      {tab === 'approvals' && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-white">Pending HITL approvals</h3>
          {approvals.length === 0 && <p className="text-xs text-muted-foreground">No pending approvals.</p>}
          {approvals.map((a) => (
            <Card key={a.id} className="p-4 bg-black/40 border-white/10 space-y-2">
              <div className="flex justify-between gap-2">
                <div>
                  <div className="text-sm font-medium text-white">{a.title}</div>
                  <div className="text-[11px] text-muted-foreground">
                    {a.action_type} · {a.channel || '—'} · conf {(a.confidence ?? 0).toFixed?.(2) ?? a.confidence}
                  </div>
                  <div className="text-[11px] text-amber-300/80 mt-1">{a.policy_reason}</div>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" onClick={() => review(a.id, true)}>Approve</Button>
                  <Button size="sm" variant="outline" onClick={() => review(a.id, false)}>Reject</Button>
                </div>
              </div>
              {a.payload?.draft && (
                <pre className="text-[11px] whitespace-pre-wrap text-zinc-300 bg-black/50 p-2 rounded max-h-40 overflow-auto">
                  {a.payload.draft}
                </pre>
              )}
            </Card>
          ))}
        </div>
      )}

      {tab === 'policy' && policy && (
        <Card className="p-4 bg-black/40 border-white/10 space-y-3">
          <h3 className="text-sm font-semibold text-white">Outbound / HITL policy</h3>
          <label className="text-xs block">
            Default mode
            <select
              className="mt-1 w-full bg-black/60 border border-white/10 rounded px-2 py-1 text-sm"
              value={policy.default_mode}
              onChange={(e) => setPolicy({ ...policy, default_mode: e.target.value })}
            >
              <option value="draft_only">Draft only (recommended)</option>
              <option value="auto_with_rules">Auto with rules</option>
            </select>
          </label>
          <label className="text-xs block">
            Min confidence
            <Input
              type="number"
              step="0.05"
              value={policy.min_confidence ?? 0.85}
              onChange={(e) => setPolicy({ ...policy, min_confidence: e.target.value })}
            />
          </label>
          <label className="text-xs block">
            Max auto amount
            <Input
              type="number"
              value={policy.max_auto_amount ?? 0}
              onChange={(e) => setPolicy({ ...policy, max_auto_amount: e.target.value })}
            />
          </label>
          <label className="text-xs flex items-center gap-2">
            <input
              type="checkbox"
              checked={!!policy.support_refuse_if_not_in_kb}
              onChange={(e) => setPolicy({ ...policy, support_refuse_if_not_in_kb: e.target.checked })}
            />
            Support: refuse if not in knowledge base
          </label>
          <Button onClick={savePolicy}>Save policy</Button>
        </Card>
      )}

      {tab === 'billing' && (
        <div className="space-y-4">
          {entitlements && (
            <Card className="p-4 bg-black/40 border-white/10 text-sm space-y-1">
              <div className="font-semibold text-white">Current plan: {entitlements.plan?.name}</div>
              <div className="text-xs text-muted-foreground">Status: {entitlements.status}</div>
              <div className="text-xs">
                Seats {entitlements.seats_used}/{entitlements.seat_limit ?? '∞'} · Actions{' '}
                {entitlements.actions_used_period}/{entitlements.action_quota_monthly}
              </div>
              <div className="text-xs">
                USD ${entitlements.plan?.price_usd_monthly}/mo · INR ₹{entitlements.plan?.price_inr_monthly}/mo
              </div>
              <div className="text-[11px] text-zinc-400 pt-1 space-y-0.5">
                <div>
                  Monthly actions: {entitlements.actions_used_period ?? 0}/{entitlements.action_quota_monthly ?? '—'} (resets each month)
                </div>
                <div>
                  Weekly actions: {entitlements.actions_used_weekly ?? 0}/{entitlements.weekly_action_quota ?? '—'} (resets each week)
                </div>
              </div>
            </Card>
          )}
          <div className="grid md:grid-cols-2 gap-3">
            {plans.map((p) => (
              <Card key={p.code} className="p-4 bg-black/40 border-white/10 space-y-2">
                <div className="font-medium text-white">{p.name}</div>
                <div className="text-xs text-muted-foreground">
                  Full product access · high exploratory rate limits
                </div>
                <div className="text-[11px] text-zinc-400">
                  Agents: {(p.allowed_agents || []).join(', ') || 'all'}
                </div>
                <div className="flex flex-wrap gap-2">
                  {Number(p.price_inr_monthly) > 0 && (
                    <Button size="sm" onClick={() => payWithRazorpay(p.code)}>
                      Pay with Razorpay (₹)
                    </Button>
                  )}
                  <Button size="sm" variant="outline" onClick={() => changePlan(p.code)}>
                    Activate plan
                  </Button>
                </div>
              </Card>
            ))}
          </div>
          {plans.length === 0 && (
            <p className="text-xs text-muted-foreground">No active plans configured.</p>
          )}
          <p className="text-[11px] text-muted-foreground">
            Only the Full Access plan is active. Other tiers remain in code but are deactivated.
          </p>
        </div>
      )}

      {tab === 'employees' && (
        <div className="space-y-4">
          <div className="grid md:grid-cols-3 gap-3">
            {employees.map((e) => (
              <Card key={e.id} className="p-4 bg-black/40 border-white/10">
                <div className="font-medium text-white">{e.name}</div>
                <div className="text-[11px] text-muted-foreground">{e.role_key} · {e.status}</div>
                <div className="text-xs mt-2">Quota {e.used_today}/{e.quota_daily}</div>
              </Card>
            ))}
          </div>
          {standup?.standups && (
            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-white">Daily stand-up</h3>
              {standup.standups.map((s: any) => (
                <Card key={s.employee_id} className="p-3 bg-black/40 border-white/10 text-xs space-y-1">
                  <div className="font-medium text-white">{s.name}</div>
                  <div>Needs approval: {s.needs_approval}</div>
                  <div>Did: {s.did?.length || 0} actions · Failed: {s.failed?.length || 0}</div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'roi' && roi && (
        <div className="grid md:grid-cols-3 gap-3">
          <Card className="p-4 bg-black/40 border-white/10">
            <div className="text-[11px] text-muted-foreground">AI spend</div>
            <div className="text-xl font-semibold text-white">${(roi.ai_spend_usd || 0).toFixed(2)}</div>
          </Card>
          <Card className="p-4 bg-black/40 border-white/10">
            <div className="text-[11px] text-muted-foreground">Hours saved</div>
            <div className="text-xl font-semibold text-white">{roi.hours_saved}</div>
          </Card>
          <Card className="p-4 bg-black/40 border-white/10">
            <div className="text-[11px] text-muted-foreground">Net ROI</div>
            <div className="text-xl font-semibold text-emerald-400">${(roi.net_roi_usd || 0).toFixed(2)}</div>
          </Card>
          <Card className="p-4 bg-black/40 border-white/10 md:col-span-3 text-xs space-y-1">
            <div>Cost / meeting: {roi.cost_per_meeting_usd != null ? `$${roi.cost_per_meeting_usd.toFixed(2)}` : '—'}</div>
            <div>Cost / ticket: {roi.cost_per_resolved_ticket_usd != null ? `$${roi.cost_per_resolved_ticket_usd.toFixed(2)}` : '—'}</div>
            <div>ROI multiple: {roi.roi_multiple ?? '—'}</div>
            <div className="pt-2 font-medium text-white">Quality samples</div>
            {(roi.quality_samples || []).slice(0, 5).map((s: any) => (
              <div key={s.id} className="text-zinc-400">
                {s.agent} · {s.task_type} · conf {s.confidence} · {s.result_status || 'pending'}
              </div>
            ))}
          </Card>
        </div>
      )}

      {tab === 'crm' && (
        <div className="space-y-2 text-sm">
          <p className="text-xs text-muted-foreground">
            Connect HubSpot / Salesforce / Zendesk / Freshdesk via API (POST /enterprise/crm/connect).
          </p>
          {crm.length === 0 && <p className="text-xs">No CRM connections yet.</p>}
          {crm.map((c) => (
            <Card key={c.id} className="p-3 bg-black/40 border-white/10 text-xs">
              {c.provider} · {c.sync_status} · last {c.last_sync_at || 'never'}
            </Card>
          ))}
        </div>
      )}

      {tab === 'compliance' && (
        <Card className="p-4 bg-black/40 border-white/10 space-y-3">
          <h3 className="text-sm font-semibold text-white">GDPR subject requests</h3>
          <Input placeholder="subject@email.com" value={gdprEmail} onChange={(e) => setGdprEmail(e.target.value)} />
          <div className="flex gap-2">
            <Button size="sm" onClick={() => gdpr('export')}>Export</Button>
            <Button size="sm" variant="outline" onClick={() => gdpr('delete')}>Delete / anonymize</Button>
          </div>
        </Card>
      )}

      {tab === 'ops' && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-white">Dead-letter queue</h3>
          {dlq.length === 0 && <p className="text-xs text-muted-foreground">No failed jobs.</p>}
          {dlq.map((j) => (
            <Card key={j.id} className="p-3 bg-black/40 border-white/10 text-xs flex justify-between gap-2">
              <div>
                <div className="text-white">{j.task_name}</div>
                <div className="text-red-300/80">{j.error_message}</div>
              </div>
              <Button size="sm" onClick={() => replayDlq(j.id)}>Replay</Button>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
