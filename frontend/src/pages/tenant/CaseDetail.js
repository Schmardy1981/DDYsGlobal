import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { ArrowLeft, Users, FileText, Search, Shield, Scale, CheckCircle, Clock, Download, Play, AlertTriangle, Mail, UserPlus, Send, Bell } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import api from '@/api/client';

const STATUS_COLORS = {
  missing: 'bg-gray-100 text-gray-700', submitted: 'bg-blue-100 text-blue-700', auto_passed: 'bg-green-100 text-green-700',
  needs_review: 'bg-amber-100 text-amber-700', rejected: 'bg-red-100 text-red-700', waived: 'bg-purple-100 text-purple-700', approved: 'bg-green-100 text-green-700'
};

const RISK_COLORS = { low: 'bg-green-100 text-green-700', medium: 'bg-amber-100 text-amber-700', high: 'bg-red-100 text-red-700' };

export default function CaseDetail() {
  const { caseId } = useParams();
  const navigate = useNavigate();
  const [caseData, setCaseData] = useState(null);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('overview');
  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteResult, setInviteResult] = useState(null);
  const [reminders, setReminders] = useState([]);
  const [sendingReminder, setSendingReminder] = useState(false);

  useEffect(() => { loadCase(); }, [caseId]);

  const loadCase = () => {
    Promise.all([
      api.get(`/cases/${caseId}`),
      api.get(`/audit/case/${caseId}`),
      api.get(`/reminders?case_id=${caseId}`)
    ]).then(([caseRes, auditRes, remRes]) => {
      setCaseData(caseRes.data);
      setAuditLogs(auditRes.data);
      setReminders(remRes.data);
    }).catch(console.error).finally(() => setLoading(false));
  };

  const handleInviteCustomer = async () => {
    try {
      const res = await api.post('/reminders/invite-customer', { case_id: caseId, email: inviteEmail });
      setInviteResult(res.data);
      loadCase();
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  const handleSendReminder = async () => {
    setSendingReminder(true);
    try {
      const res = await api.post('/reminders/send', { case_id: caseId });
      alert(res.data.message);
      loadCase();
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
    finally { setSendingReminder(false); }
  };

  const handleTransition = async (target) => {
    try {
      await api.post(`/cases/${caseId}/transition`, { target_status: target });
      loadCase();
    } catch (err) { alert(err.response?.data?.detail || 'Transition failed'); }
  };

  const handleScreening = async (runType) => {
    try {
      await api.post('/screening/run', { case_id: caseId, run_type: runType });
      loadCase();
    } catch (err) { alert(err.response?.data?.detail || 'Screening failed'); }
  };

  const handleRiskAssess = async () => {
    try {
      await api.post('/risk/assess', { case_id: caseId, inputs: {} });
      loadCase();
    } catch (err) { alert(err.response?.data?.detail || 'Risk assessment failed'); }
  };

  const handleOsint = async (partyId) => {
    try {
      await api.post('/osint/analyze', { case_id: caseId, party_id: partyId });
      loadCase();
      alert('OSINT analysis complete');
    } catch (err) { alert(err.response?.data?.detail || 'OSINT failed'); }
  };

  const handleExport = async () => {
    try {
      const res = await api.post(`/export/kyc/${caseId}`);
      alert(`Export created: ${res.data.filename}`);
    } catch (err) { alert(err.response?.data?.detail || 'Export failed'); }
  };

  const handleRequirementUpdate = async (reqId, status) => {
    try {
      await api.put(`/cases/${caseId}/requirements/${reqId}`, { status });
      loadCase();
    } catch (err) { alert(err.response?.data?.detail || 'Update failed'); }
  };

  if (loading) return <div className="text-sm text-[#64748B]">Loading case...</div>;
  if (!caseData) return <div className="text-sm text-red-600">Case not found</div>;

  const c = caseData;
  const parties = c.parties || [];
  const requirements = c.requirements || [];
  const documents = c.documents || [];
  const screeningRuns = c.screening_runs || [];
  const riskAssessments = c.risk_assessments || [];
  const approvalTasks = c.approval_tasks || [];
  const waivers = c.waivers || [];

  const nextTransitions = {
    draft: ['customer_in_progress'],
    customer_in_progress: ['customer_submitted'],
    customer_submitted: ['automated_checks'],
    automated_checks: ['maker_review'],
    maker_review: ['checker_review'],
    checker_review: ['business_approval', 'compliance_approval', 'completed'],
    business_approval: ['compliance_approval', 'mlro_approval', 'completed'],
    compliance_approval: ['mlro_approval', 'completed'],
    mlro_approval: ['completed'],
  };

  return (
    <div data-testid="case-detail">
      <div className="flex items-center gap-3 mb-6">
        <Button variant="ghost" size="sm" onClick={() => navigate('/workspace/cases')} data-testid="back-to-cases"><ArrowLeft size={16} /></Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight font-['IBM_Plex_Sans']">{c.case_ref}</h1>
            <Badge className={`${STATUS_COLORS[c.status] || 'bg-gray-100'} border-transparent`}>{c.status?.replace(/_/g, ' ')}</Badge>
            {c.risk_rating && <Badge className={`${RISK_COLORS[c.risk_rating]} border-transparent capitalize`}>{c.risk_rating}</Badge>}
            {c.due_diligence_level && <Badge variant="outline" className="text-xs uppercase">{c.due_diligence_level}</Badge>}
          </div>
          <p className="text-sm text-[#64748B] mt-1">{c.case_type?.replace(/_/g, ' ')} | {c.jurisdiction} | {c.product_scope || 'N/A'}</p>
        </div>
        <div className="flex items-center gap-2">
          {(nextTransitions[c.status] || []).map(t => (
            <Button key={t} size="sm" variant="outline" onClick={() => handleTransition(t)} data-testid={`transition-${t}`}>
              {t.replace(/_/g, ' ')}
            </Button>
          ))}
          <Button size="sm" variant="outline" onClick={handleExport} data-testid="export-kyc-btn"><Download size={14} className="mr-1" /> Export KYC</Button>
        </div>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="mb-4">
          <TabsTrigger value="overview" data-testid="tab-overview">Overview</TabsTrigger>
          <TabsTrigger value="parties" data-testid="tab-parties">Parties ({parties.length})</TabsTrigger>
          <TabsTrigger value="requirements" data-testid="tab-requirements">Requirements ({requirements.length})</TabsTrigger>
          <TabsTrigger value="documents" data-testid="tab-documents">Documents ({documents.length})</TabsTrigger>
          <TabsTrigger value="screening" data-testid="tab-screening">Screening</TabsTrigger>
          <TabsTrigger value="risk" data-testid="tab-risk">Risk</TabsTrigger>
          <TabsTrigger value="approvals" data-testid="tab-approvals">Approvals</TabsTrigger>
          <TabsTrigger value="audit" data-testid="tab-audit">Audit Log</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <Card className="border-[#E2E8F0]"><CardHeader className="pb-2"><CardTitle className="text-sm font-['IBM_Plex_Sans']">Requirements Summary</CardTitle></CardHeader>
              <CardContent>
                {['missing','submitted','auto_passed','needs_review','approved','waived','rejected'].map(s => {
                  const count = requirements.filter(r => r.status === s).length;
                  return count > 0 ? <div key={s} className="flex justify-between py-1"><span className="text-xs text-[#64748B] capitalize">{s.replace(/_/g,' ')}</span><Badge className={`${STATUS_COLORS[s]} border-transparent text-xs`}>{count}</Badge></div> : null;
                })}
              </CardContent>
            </Card>
            <Card className="border-[#E2E8F0]"><CardHeader className="pb-2"><CardTitle className="text-sm font-['IBM_Plex_Sans']">Parties</CardTitle></CardHeader>
              <CardContent>
                {parties.map(p => (
                  <div key={p.id} className="flex justify-between py-1">
                    <span className="text-sm">{p.legal_name || `${p.first_name} ${p.last_name}`}</span>
                    <Badge variant="outline" className="text-xs capitalize">{p.role_in_case}</Badge>
                  </div>
                ))}
              </CardContent>
            </Card>
            <Card className="border-[#E2E8F0]"><CardHeader className="pb-2"><CardTitle className="text-sm font-['IBM_Plex_Sans']">Key Dates</CardTitle></CardHeader>
              <CardContent className="space-y-1">
                <div className="flex justify-between py-1"><span className="text-xs text-[#64748B]">Created</span><span className="text-xs font-['JetBrains_Mono']">{c.created_at?.slice(0,10)}</span></div>
                <div className="flex justify-between py-1"><span className="text-xs text-[#64748B]">Last Action</span><span className="text-xs font-['JetBrains_Mono']">{c.last_action_at?.slice(0,10)}</span></div>
                <div className="flex justify-between py-1"><span className="text-xs text-[#64748B]">NRD</span><span className="text-xs font-['JetBrains_Mono']">{c.nrd_date?.slice(0,10) || 'Not set'}</span></div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="parties">
          <div className="space-y-3">
            {parties.map(p => (
              <Card key={p.id} className="border-[#E2E8F0]">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{p.legal_name || `${p.first_name} ${p.last_name}`}</span>
                        <Badge variant="outline" className="text-xs capitalize">{p.role_in_case}</Badge>
                        <Badge variant="outline" className="text-xs">{p.party_type?.replace(/_/g, ' ')}</Badge>
                      </div>
                      <div className="flex gap-4 mt-1 text-xs text-[#64748B]">
                        {p.nationality && <span>Nationality: {p.nationality}</span>}
                        {p.dob && <span>DOB: {p.dob}</span>}
                        {p.ownership_percent && <span>Ownership: {p.ownership_percent}%</span>}
                      </div>
                    </div>
                    <Button size="sm" variant="outline" onClick={() => handleOsint(p.id)} data-testid={`osint-${p.id}`}>
                      <Search size={14} className="mr-1" /> OSINT
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="requirements">
          <div className="bg-white border border-[#E2E8F0] rounded-md overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-[#F8FAFC]">
                  <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Requirement</th>
                  <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Category</th>
                  <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Status</th>
                  <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Source</th>
                  <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Actions</th>
                </tr>
              </thead>
              <tbody>
                {requirements.map(r => (
                  <tr key={r.id} className="border-b hover:bg-[#F8FAFC]">
                    <td className="px-4 py-3 text-sm">{r.requirement_label || r.requirement_key}</td>
                    <td className="px-4 py-3"><Badge variant="outline" className="text-xs">{r.requirement_category}</Badge></td>
                    <td className="px-4 py-3"><Badge className={`${STATUS_COLORS[r.status] || ''} border-transparent text-xs`}>{r.status?.replace(/_/g,' ')}</Badge></td>
                    <td className="px-4 py-3 text-xs text-[#64748B] uppercase">{r.rule_source}</td>
                    <td className="px-4 py-3">
                      <div className="flex gap-1">
                        {r.status === 'needs_review' && (
                          <>
                            <Button size="sm" variant="ghost" className="h-7 text-xs text-green-600" onClick={() => handleRequirementUpdate(r.id, 'approved')}>Approve</Button>
                            <Button size="sm" variant="ghost" className="h-7 text-xs text-red-600" onClick={() => handleRequirementUpdate(r.id, 'rejected')}>Reject</Button>
                          </>
                        )}
                        {r.status === 'submitted' && (
                          <Button size="sm" variant="ghost" className="h-7 text-xs text-green-600" onClick={() => handleRequirementUpdate(r.id, 'approved')}>Approve</Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </TabsContent>

        <TabsContent value="documents">
          <div className="bg-white border border-[#E2E8F0] rounded-md overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-[#F8FAFC]">
                  <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Filename</th>
                  <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Type</th>
                  <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Status</th>
                  <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Uploaded</th>
                </tr>
              </thead>
              <tbody>
                {documents.map(d => (
                  <tr key={d.id} className="border-b hover:bg-[#F8FAFC]">
                    <td className="px-4 py-3 text-sm font-['JetBrains_Mono']">{d.original_filename}</td>
                    <td className="px-4 py-3"><Badge variant="outline" className="text-xs">{d.doc_type}</Badge></td>
                    <td className="px-4 py-3"><Badge className={`${STATUS_COLORS[d.status] || 'bg-gray-100'} border-transparent text-xs`}>{d.status}</Badge></td>
                    <td className="px-4 py-3 text-xs font-['JetBrains_Mono'] text-[#64748B]">{d.created_at?.slice(0,10)}</td>
                  </tr>
                ))}
                {!documents.length && <tr><td colSpan={4} className="px-4 py-8 text-center text-sm text-[#64748B]">No documents uploaded yet</td></tr>}
              </tbody>
            </table>
          </div>
        </TabsContent>

        <TabsContent value="screening">
          <div className="space-y-4">
            <div className="flex gap-2">
              <Button size="sm" onClick={() => handleScreening('sanctions')} data-testid="run-sanctions"><Shield size={14} className="mr-1" /> Run Sanctions</Button>
              <Button size="sm" onClick={() => handleScreening('pep')} data-testid="run-pep"><Users size={14} className="mr-1" /> Run PEP</Button>
              <Button size="sm" onClick={() => handleScreening('adverse_media')} data-testid="run-adverse"><AlertTriangle size={14} className="mr-1" /> Run Adverse Media</Button>
            </div>
            {screeningRuns.map(run => (
              <Card key={run.id} className="border-[#E2E8F0]">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="text-xs uppercase">{run.run_type}</Badge>
                      <Badge className={run.status === 'completed' ? 'bg-green-100 text-green-700 border-transparent' : 'bg-amber-100 text-amber-700 border-transparent'}>{run.status}</Badge>
                      <span className="text-xs text-[#64748B] font-['JetBrains_Mono']">{run.started_at?.slice(0,19)}</span>
                    </div>
                    <span className="text-xs text-[#64748B]">Hits: {run.parameters_json?.hits_count ?? '?'}</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="risk">
          <div className="space-y-4">
            <Button size="sm" onClick={handleRiskAssess} data-testid="run-risk-assess"><Scale size={14} className="mr-1" /> Run Risk Assessment</Button>
            {riskAssessments.map(ra => (
              <Card key={ra.id} className="border-[#E2E8F0]">
                <CardContent className="p-4">
                  <div className="flex items-center gap-3 mb-2">
                    <Badge className={`${RISK_COLORS[ra.computed_rating] || ''} border-transparent capitalize text-sm`}>{ra.computed_rating}</Badge>
                    <span className="text-sm font-['JetBrains_Mono']">Score: {ra.computed_score}</span>
                    <Badge variant="outline" className="uppercase text-xs">{ra.due_diligence_level}</Badge>
                    {ra.challenged && <Badge className="bg-amber-100 text-amber-700 border-transparent">Challenged</Badge>}
                  </div>
                  <div className="text-xs text-[#64748B]">
                    Methodology: {ra.methodology} | Created: {ra.created_at?.slice(0,10)}
                  </div>
                  {Object.entries(ra.per_se_flags_json || {}).some(([,v]) => v) && (
                    <div className="mt-2 flex gap-1">
                      {Object.entries(ra.per_se_flags_json || {}).filter(([,v]) => v).map(([k]) => (
                        <Badge key={k} className="bg-red-100 text-red-700 border-transparent text-xs">{k.replace(/_/g,' ')}</Badge>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="approvals">
          <div className="bg-white border border-[#E2E8F0] rounded-md overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-[#F8FAFC]">
                  <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Task Type</th>
                  <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Status</th>
                  <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Decision</th>
                  <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Created</th>
                </tr>
              </thead>
              <tbody>
                {approvalTasks.map(t => (
                  <tr key={t.id} className="border-b hover:bg-[#F8FAFC]">
                    <td className="px-4 py-3 text-sm capitalize">{t.task_type?.replace(/_/g,' ')}</td>
                    <td className="px-4 py-3"><Badge className={t.status === 'completed' ? 'bg-green-100 text-green-700 border-transparent' : 'bg-amber-100 text-amber-700 border-transparent'}>{t.status}</Badge></td>
                    <td className="px-4 py-3"><Badge className={t.decision === 'approved' ? 'bg-green-100 text-green-700 border-transparent' : t.decision === 'rejected' ? 'bg-red-100 text-red-700 border-transparent' : 'bg-gray-100 border-transparent'}>{t.decision || 'pending'}</Badge></td>
                    <td className="px-4 py-3 text-xs font-['JetBrains_Mono'] text-[#64748B]">{t.created_at?.slice(0,10)}</td>
                  </tr>
                ))}
                {!approvalTasks.length && <tr><td colSpan={4} className="px-4 py-8 text-center text-sm text-[#64748B]">No approval tasks</td></tr>}
              </tbody>
            </table>
          </div>
        </TabsContent>

        <TabsContent value="audit">
          <div className="bg-white border border-[#E2E8F0] rounded-md overflow-hidden max-h-[600px] overflow-y-auto">
            <table className="w-full">
              <thead className="sticky top-0 bg-[#F8FAFC]">
                <tr className="border-b">
                  <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Timestamp</th>
                  <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Action</th>
                  <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Actor</th>
                  <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Entity</th>
                </tr>
              </thead>
              <tbody>
                {auditLogs.map(l => (
                  <tr key={l.id} className="border-b hover:bg-[#F8FAFC]">
                    <td className="px-4 py-2 text-xs font-['JetBrains_Mono'] text-[#64748B]">{l.timestamp?.slice(0,19)}</td>
                    <td className="px-4 py-2 text-xs font-medium">{l.action_key}</td>
                    <td className="px-4 py-2 text-xs text-[#64748B]">{l.actor_role}</td>
                    <td className="px-4 py-2 text-xs font-['JetBrains_Mono'] text-[#64748B]">{l.entity_type}/{l.entity_id?.slice(0,8)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
