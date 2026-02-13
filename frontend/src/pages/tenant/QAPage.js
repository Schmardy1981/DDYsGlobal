import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { ClipboardCheck, Download, Play, Plus, CheckCircle, AlertCircle } from 'lucide-react';
import api from '@/api/client';

export default function QAPage() {
  const { getActiveTenantId } = useAuth();
  const tenantId = getActiveTenantId();
  const [reviews, setReviews] = useState([]);
  const [pack, setPack] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('reviews');
  const [sampling, setSampling] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({ case_id: '', qa_type: 'first_line', severity: 'low', findings: '' });

  useEffect(() => { loadData(); }, [tenantId]);

  const loadData = () => {
    if (!tenantId) return;
    Promise.all([
      api.get(`/qa/reviews?tenant_id=${tenantId}`),
      api.get(`/qa/governance-pack?tenant_id=${tenantId}`)
    ]).then(([rRes, pRes]) => {
      setReviews(rRes.data);
      setPack(pRes.data);
    }).catch(console.error).finally(() => setLoading(false));
  };

  const handleSample = async () => {
    setSampling(true);
    try {
      const res = await api.post('/qa/sample', { tenant_id: tenantId, sample_percent: 5, qa_type: 'first_line' });
      alert(`${res.data.samples_created} QA samples created from ${res.data.total_completed} completed cases`);
      loadData();
    } catch (err) { alert(err.response?.data?.detail || 'Sampling failed'); }
    finally { setSampling(false); }
  };

  const handleCreate = async () => {
    try {
      const findings = createForm.findings ? createForm.findings.split('\n').filter(Boolean) : [];
      await api.post('/qa/reviews', {
        tenant_id: tenantId,
        case_id: createForm.case_id,
        qa_type: createForm.qa_type,
        severity: createForm.severity,
        findings,
        remediation_required: createForm.severity !== 'low'
      });
      setShowCreate(false);
      setCreateForm({ case_id: '', qa_type: 'first_line', severity: 'low', findings: '' });
      loadData();
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  const handleCloseReview = async (id) => {
    try {
      await api.put(`/qa/reviews/${id}`, { status: 'closed' });
      loadData();
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  const sevColor = (s) => {
    if (s === 'critical') return 'bg-red-100 text-red-700 border-transparent';
    if (s === 'high') return 'bg-red-100 text-red-700 border-transparent';
    if (s === 'medium') return 'bg-amber-100 text-amber-700 border-transparent';
    return 'bg-green-100 text-green-700 border-transparent';
  };

  return (
    <div data-testid="qa-page">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight font-['IBM_Plex_Sans']">Quality Assurance</h1>
          <p className="text-sm text-[#64748B] mt-1">QA reviews, sampling, and governance council</p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={handleSample} disabled={sampling} data-testid="generate-sample-btn">
            <Play size={14} className="mr-1" /> {sampling ? 'Sampling...' : 'Generate Sample'}
          </Button>
          <Dialog open={showCreate} onOpenChange={setShowCreate}>
            <DialogTrigger asChild>
              <Button size="sm" className="bg-[#0F172A] hover:bg-[#1E293B]" data-testid="create-qa-btn">
                <Plus size={14} className="mr-1" /> New Review
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>Create QA Review</DialogTitle></DialogHeader>
              <div className="space-y-4 pt-2">
                <div>
                  <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Case ID</Label>
                  <Input className="mt-1.5" value={createForm.case_id} onChange={e => setCreateForm({...createForm, case_id: e.target.value})} placeholder="Paste case ID" data-testid="qa-case-id" />
                </div>
                <div>
                  <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">QA Type</Label>
                  <Select value={createForm.qa_type} onValueChange={v => setCreateForm({...createForm, qa_type: v})}>
                    <SelectTrigger className="mt-1.5"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="first_line">First Line</SelectItem>
                      <SelectItem value="second_line">Second Line</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Severity</Label>
                  <Select value={createForm.severity} onValueChange={v => setCreateForm({...createForm, severity: v})}>
                    <SelectTrigger className="mt-1.5"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="low">Low</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="high">High</SelectItem>
                      <SelectItem value="critical">Critical</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Findings (one per line)</Label>
                  <Textarea className="mt-1.5" value={createForm.findings} onChange={e => setCreateForm({...createForm, findings: e.target.value})} rows={4} placeholder="Enter findings..." />
                </div>
                <Button className="w-full bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleCreate} data-testid="submit-qa-btn">Create Review</Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="mb-4">
          <TabsTrigger value="reviews" data-testid="tab-qa-reviews">Reviews ({reviews.length})</TabsTrigger>
          <TabsTrigger value="governance" data-testid="tab-governance">Governance Pack</TabsTrigger>
        </TabsList>

        <TabsContent value="reviews">
          <div className="bg-white border border-[#E2E8F0] rounded-md overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-[#F8FAFC]">
                  <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Case</th>
                  <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Type</th>
                  <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Severity</th>
                  <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Findings</th>
                  <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Remediation</th>
                  <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Status</th>
                  <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Actions</th>
                </tr>
              </thead>
              <tbody>
                {reviews.map(r => (
                  <tr key={r.id} className="border-b hover:bg-[#F8FAFC]" data-testid={`qa-row-${r.id}`}>
                    <td className="px-4 py-3 text-xs font-['JetBrains_Mono']">{r.case_ref || r.case_id?.slice(0,8)}</td>
                    <td className="px-4 py-3"><Badge variant="outline" className="text-xs">{r.qa_type?.replace('_',' ')}</Badge></td>
                    <td className="px-4 py-3">{r.severity ? <Badge className={`${sevColor(r.severity)} text-xs`}>{r.severity}</Badge> : <span className="text-xs text-[#64748B]">Unrated</span>}</td>
                    <td className="px-4 py-3 text-xs text-[#64748B] max-w-xs truncate">{(r.findings_json || []).length} finding(s)</td>
                    <td className="px-4 py-3">{r.remediation_required ? <Badge className="bg-amber-100 text-amber-700 border-transparent text-xs">Required</Badge> : <span className="text-xs text-[#64748B]">No</span>}</td>
                    <td className="px-4 py-3"><Badge className={r.status === 'closed' ? 'bg-green-100 text-green-700 border-transparent' : r.status === 'open' ? 'bg-blue-100 text-blue-700 border-transparent' : 'bg-gray-100 text-gray-700 border-transparent'}>{r.status}</Badge></td>
                    <td className="px-4 py-3">
                      {r.status !== 'closed' && <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => handleCloseReview(r.id)}>Close</Button>}
                    </td>
                  </tr>
                ))}
                {!reviews.length && <tr><td colSpan={7} className="px-4 py-8 text-center text-sm text-[#64748B]">{loading ? 'Loading...' : 'No QA reviews yet. Generate a sample or create manually.'}</td></tr>}
              </tbody>
            </table>
          </div>
        </TabsContent>

        <TabsContent value="governance">
          {pack ? (
            <div className="space-y-6">
              <Card className="border-[#E2E8F0]">
                <CardHeader className="pb-2"><CardTitle className="text-sm font-['IBM_Plex_Sans']">Monthly Governance Pack</CardTitle></CardHeader>
                <CardContent>
                  <p className="text-xs text-[#64748B] mb-3">Period: {pack.period}</p>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="p-3 bg-[#F8FAFC] rounded-md">
                      <p className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Total Reviews</p>
                      <p className="text-xl font-semibold font-['JetBrains_Mono']">{pack.summary?.total_reviews || 0}</p>
                    </div>
                    <div className="p-3 bg-[#F8FAFC] rounded-md">
                      <p className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Remediation Required</p>
                      <p className="text-xl font-semibold font-['JetBrains_Mono'] text-amber-600">{pack.summary?.remediation_required || 0}</p>
                    </div>
                    <div className="p-3 bg-[#F8FAFC] rounded-md">
                      <p className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Prior Month</p>
                      <p className="text-xl font-semibold font-['JetBrains_Mono']">{pack.trends?.prior_month_reviews || 0}</p>
                    </div>
                    <div className="p-3 bg-[#F8FAFC] rounded-md">
                      <p className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Trend</p>
                      <p className={`text-xl font-semibold font-['JetBrains_Mono'] ${(pack.trends?.change || 0) > 0 ? 'text-red-600' : 'text-green-600'}`}>
                        {(pack.trends?.change || 0) > 0 ? '+' : ''}{pack.trends?.change || 0}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {pack.summary?.by_severity && Object.keys(pack.summary.by_severity).length > 0 && (
                <Card className="border-[#E2E8F0]">
                  <CardHeader className="pb-2"><CardTitle className="text-sm font-['IBM_Plex_Sans']">By Severity</CardTitle></CardHeader>
                  <CardContent>
                    <div className="flex gap-3">
                      {Object.entries(pack.summary.by_severity).map(([sev, count]) => (
                        <div key={sev} className="flex items-center gap-1">
                          <Badge className={`${sevColor(sev)} text-xs`}>{sev}</Badge>
                          <span className="text-sm font-['JetBrains_Mono']">{count}</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {(pack.findings || []).length > 0 && (
                <Card className="border-[#E2E8F0]">
                  <CardHeader className="pb-2"><CardTitle className="text-sm font-['IBM_Plex_Sans']">Findings Summary</CardTitle></CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {pack.findings.map((f, i) => (
                        <div key={i} className="flex items-start gap-2 text-sm">
                          <AlertCircle size={14} className="text-amber-500 mt-0.5 shrink-0" />
                          <div>
                            <span>{f.finding}</span>
                            <span className="text-xs text-[#64748B] ml-2">Case: {f.case_id?.slice(0,8)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {(pack.remediation_tracker || []).length > 0 && (
                <Card className="border-[#E2E8F0]">
                  <CardHeader className="pb-2"><CardTitle className="text-sm font-['IBM_Plex_Sans']">Open Remediation Actions</CardTitle></CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {pack.remediation_tracker.map(r => (
                        <div key={r.id} className="flex items-center justify-between p-2 bg-[#F8FAFC] rounded-md">
                          <div>
                            <span className="text-sm">{r.case_ref || r.case_id?.slice(0,8)}</span>
                            <Badge className={`${sevColor(r.severity)} text-xs ml-2`}>{r.severity}</Badge>
                          </div>
                          <Badge className="bg-amber-100 text-amber-700 border-transparent text-xs">{r.status}</Badge>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          ) : (
            <div className="text-sm text-[#64748B] text-center py-8">No governance pack data available. Generate QA samples first.</div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
