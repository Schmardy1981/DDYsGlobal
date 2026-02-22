import { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Clock, Play, AlertTriangle, RefreshCw, Activity, Save, Shield } from 'lucide-react';
import api from '@/api/client';

const INTERVAL_OPTIONS = [
  { value: '24', label: 'Every 24 hours', hint: 'Daily' },
  { value: '48', label: 'Every 48 hours', hint: '2 days' },
  { value: '72', label: 'Every 72 hours', hint: '3 days' },
  { value: '168', label: 'Every 7 days', hint: 'Weekly' },
  { value: '336', label: 'Every 14 days', hint: 'Bi-weekly' },
  { value: '720', label: 'Every 30 days', hint: 'Monthly' },
];

const JOBS = [
  {
    key: 'nrd_rr_check',
    label: 'Regular Review Generation',
    desc: 'Auto-creates RR cases when NRD approaches (High: 12mo, Medium: 24mo). Triggers 60 days before NRD.',
    icon: Clock,
    recommended: '24',
    reason: 'Daily check ensures no NRD deadline is missed. Low cost — only queries cases with upcoming NRD.',
  },
  {
    key: 'edr_deadlines',
    label: 'EDR Deadline Monitor',
    desc: 'Monitors 28-day review SLA and 90-day completion SLA. Auto-restricts cases on breach. Escalates to MLRO.',
    icon: AlertTriangle,
    recommended: '24',
    reason: 'Daily is critical — SLA breaches have regulatory consequences. Very low cost per run.',
  },
  {
    key: 'waiver_expiry',
    label: 'Waiver Expiry Monitor',
    desc: 'Alerts at 30/14/7/1 days before expiry. Auto-expires and restricts cases. Reverts waived requirements.',
    icon: Clock,
    recommended: '24',
    reason: 'Daily keeps waiver alerts accurate (1-day warning needs daily check). Minimal DB queries.',
  },
  {
    key: 'document_expiry',
    label: 'Document Expiry Check',
    desc: 'Flags expired documents. Creates EDR alerts for document expiry triggers.',
    icon: RefreshCw,
    recommended: '72',
    reason: 'Every 3 days is sufficient — documents expire on specific dates, a 3-day window is acceptable.',
  },
  {
    key: 'screening_refresh',
    label: 'Ongoing Screening Refresh',
    desc: 'Re-screening of active completed clients against sanctions/PEP lists.',
    icon: Shield,
    recommended: '168',
    reason: 'Weekly is industry standard for ongoing monitoring. Reduces API costs significantly vs daily.',
  },
];

export default function PeriodicJobsPage() {
  const [status, setStatus] = useState(null);
  const [intervals, setIntervals] = useState({});
  const [running, setRunning] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [changed, setChanged] = useState(false);

  useEffect(() => { loadData(); }, []);

  const loadData = () => {
    api.get('/jobs/status').then(r => {
      setStatus(r.data);
      setIntervals(r.data.intervals || {
        nrd_rr_check: 24,
        edr_deadlines: 24,
        waiver_expiry: 24,
        document_expiry: 72,
        screening_refresh: 168,
      });
    }).catch(console.error).finally(() => setLoading(false));
  };

  const handleRunNow = async () => {
    setRunning(true);
    try {
      const res = await api.post('/jobs/run-now');
      const results = Object.entries(res.data.jobs).map(([k, v]) => `${k}: ${v}`).join('\n');
      alert(`Jobs completed:\n${results}`);
      loadData();
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
    finally { setRunning(false); }
  };

  const handleIntervalChange = (jobKey, value) => {
    setIntervals(prev => ({ ...prev, [jobKey]: parseInt(value) }));
    setChanged(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put('/jobs/intervals', intervals);
      setChanged(false);
      alert('Intervals saved successfully');
      loadData();
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
    finally { setSaving(false); }
  };

  const formatInterval = (hours) => {
    if (hours < 48) return `${hours}h`;
    if (hours < 168) return `${Math.round(hours / 24)}d`;
    if (hours < 720) return `${Math.round(hours / 168)}w`;
    return `${Math.round(hours / 720)}mo`;
  };

  if (loading) return <div className="text-sm text-[#64748B]">Loading...</div>;

  return (
    <div data-testid="periodic-jobs-page">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight font-['IBM_Plex_Sans']">Periodic Jobs</h1>
          <p className="text-sm text-[#64748B] mt-1">Configure scan intervals and run compliance monitoring jobs</p>
        </div>
        <div className="flex items-center gap-2">
          {changed && (
            <Button className="bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleSave} disabled={saving} data-testid="save-intervals-btn">
              <Save size={14} className="mr-1" /> {saving ? 'Saving...' : 'Save Intervals'}
            </Button>
          )}
          <Button variant="outline" onClick={handleRunNow} disabled={running} data-testid="run-jobs-btn">
            <Play size={14} className="mr-1" /> {running ? 'Running...' : 'Run All Now'}
          </Button>
        </div>
      </div>

      {/* Status */}
      <Card className="border-[#E2E8F0] mb-6">
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full ${status?.status === 'healthy' || status?.status === 'manual_run_complete' ? 'bg-green-500' : status?.status?.startsWith('error') ? 'bg-red-500' : 'bg-amber-500'}`} />
              <div>
                <p className="text-sm font-medium">Job Runner Status</p>
                <p className="text-xs text-[#64748B]">{status?.status || 'Initializing...'}</p>
              </div>
            </div>
            <div className="text-right text-xs text-[#64748B]">
              <p>Last Run: <span className="font-['JetBrains_Mono']">{status?.last_run ? new Date(status.last_run).toLocaleString() : 'Never'}</span></p>
              {status?.next_run && <p>Next Run: <span className="font-['JetBrains_Mono']">{new Date(status.next_run).toLocaleString()}</span></p>}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Jobs with interval selector */}
      <div className="space-y-3">
        {JOBS.map(job => {
          const Icon = job.icon;
          const currentInterval = intervals[job.key] || 24;
          const isRecommended = String(currentInterval) === job.recommended;

          return (
            <Card key={job.key} className="border-[#E2E8F0]" data-testid={`job-${job.key}`}>
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-lg bg-[#F1F5F9] flex items-center justify-center shrink-0">
                    <Icon size={18} className="text-[#64748B]" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium">{job.label}</span>
                      <Badge className="bg-green-100 text-green-700 border-transparent text-[10px]">Active</Badge>
                    </div>
                    <p className="text-xs text-[#64748B]">{job.desc}</p>
                    <p className="text-[11px] text-blue-600 mt-1.5 italic">{job.reason}</p>
                  </div>
                  <div className="flex flex-col items-end gap-2 shrink-0">
                    <Select
                      value={String(currentInterval)}
                      onValueChange={(v) => handleIntervalChange(job.key, v)}
                    >
                      <SelectTrigger className="w-48 h-9 text-xs" data-testid={`interval-${job.key}`}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {INTERVAL_OPTIONS.map(opt => (
                          <SelectItem key={opt.value} value={opt.value}>
                            <span className="flex items-center justify-between w-full gap-3">
                              <span>{opt.label}</span>
                              <span className="text-[10px] text-[#64748B]">{opt.hint}</span>
                            </span>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {isRecommended && (
                      <Badge variant="outline" className="text-[10px] text-green-600 border-green-200">Recommended</Badge>
                    )}
                    {!isRecommended && (
                      <button
                        className="text-[10px] text-blue-500 hover:text-blue-700 underline"
                        onClick={() => handleIntervalChange(job.key, job.recommended)}
                      >
                        Reset to recommended
                      </button>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Cost estimation */}
      <Card className="border-[#E2E8F0] mt-6 border-l-2 border-l-blue-500">
        <CardContent className="p-4">
          <p className="text-xs font-semibold text-[#64748B] uppercase tracking-wider mb-2">Estimated Monthly Runs</p>
          <div className="grid grid-cols-5 gap-4">
            {JOBS.map(job => {
              const hrs = intervals[job.key] || 24;
              const runsPerMonth = Math.round(720 / hrs);
              return (
                <div key={job.key} className="text-center">
                  <p className="text-lg font-semibold font-['JetBrains_Mono']">{runsPerMonth}</p>
                  <p className="text-[10px] text-[#64748B] leading-tight">{job.label.split(' ').slice(0, 2).join(' ')}</p>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
