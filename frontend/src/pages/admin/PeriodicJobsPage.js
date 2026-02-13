import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Clock, Play, CheckCircle, AlertTriangle, RefreshCw, Activity } from 'lucide-react';
import api from '@/api/client';

export default function PeriodicJobsPage() {
  const [status, setStatus] = useState(null);
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => { loadStatus(); }, []);

  const loadStatus = () => {
    api.get('/jobs/status').then(r => setStatus(r.data)).catch(console.error).finally(() => setLoading(false));
  };

  const handleRunNow = async () => {
    setRunning(true);
    try {
      const res = await api.post('/jobs/run-now');
      alert(`Jobs completed: ${JSON.stringify(res.data.jobs, null, 2)}`);
      loadStatus();
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
    finally { setRunning(false); }
  };

  const JOBS = [
    { key: 'nrd_rr_check', label: 'Regular Review Generation', desc: 'Auto-creates RR cases when NRD approaches (High: 12mo, Medium: 24mo, Low: 60mo). Triggers 60 days before NRD.', icon: Clock },
    { key: 'edr_deadlines', label: 'EDR Deadline Monitor', desc: 'Monitors 28-day review SLA and 90-day completion SLA. Auto-restricts cases on breach. Escalates to MLRO.', icon: AlertTriangle },
    { key: 'waiver_expiry', label: 'Waiver Expiry Monitor', desc: 'Alerts at 30/14/7/1 days before expiry. Auto-expires and restricts cases. Reverts waived requirements.', icon: Clock },
    { key: 'document_expiry', label: 'Document Expiry Check', desc: 'Flags expired documents. Creates EDR alerts for document expiry triggers.', icon: RefreshCw },
    { key: 'screening_refresh', label: 'Ongoing Screening', desc: 'Weekly re-screening of active clients (sanctions). Creates alerts for new hits.', icon: Activity },
  ];

  return (
    <div data-testid="periodic-jobs-page">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight font-['IBM_Plex_Sans']">Periodic Jobs</h1>
          <p className="text-sm text-[#64748B] mt-1">Background automation for compliance monitoring</p>
        </div>
        <Button className="bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleRunNow} disabled={running} data-testid="run-jobs-btn">
          <Play size={14} className="mr-1" /> {running ? 'Running...' : 'Run All Jobs Now'}
        </Button>
      </div>

      {/* Status Card */}
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

      {/* Job descriptions */}
      <div className="space-y-3">
        {JOBS.map(job => {
          const Icon = job.icon;
          return (
            <Card key={job.key} className="border-[#E2E8F0]">
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-md bg-[#F1F5F9] flex items-center justify-center shrink-0">
                    <Icon size={18} className="text-[#64748B]" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{job.label}</span>
                      <Badge className="bg-green-100 text-green-700 border-transparent text-xs">Active</Badge>
                    </div>
                    <p className="text-xs text-[#64748B] mt-1">{job.desc}</p>
                  </div>
                  <Badge variant="outline" className="text-xs shrink-0">Every 1h</Badge>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
