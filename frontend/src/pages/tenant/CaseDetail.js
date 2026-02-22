import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import {
  ArrowLeft, Building2, User, Users, FileText, Search, Shield, Scale, CheckCircle, XCircle,
  Clock, Download, Play, AlertTriangle, Mail, UserPlus, Send, Bell, Eye, MapPin, CreditCard,
  Calendar, Globe, Percent, ChevronRight, CircleDot, File, Image, ExternalLink
} from 'lucide-react';
import api from '@/api/client';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const STATUS_COLORS = {
  missing: 'bg-gray-100 text-gray-700', submitted: 'bg-blue-100 text-blue-700', auto_passed: 'bg-green-100 text-green-700',
  needs_review: 'bg-amber-100 text-amber-700', rejected: 'bg-red-100 text-red-700', waived: 'bg-purple-100 text-purple-700', approved: 'bg-green-100 text-green-700'
};
const STATUS_ICONS = {
  missing: CircleDot, submitted: Clock, auto_passed: CheckCircle, needs_review: Clock, rejected: XCircle, waived: Shield, approved: CheckCircle
};
const RISK_COLORS = { low: 'bg-green-100 text-green-700', medium: 'bg-amber-100 text-amber-700', high: 'bg-red-100 text-red-700' };
const ROLE_COLORS = {
  client: 'bg-blue-100 text-blue-700', ubo: 'bg-purple-100 text-purple-700', director: 'bg-teal-100 text-teal-700',
  signatory: 'bg-indigo-100 text-indigo-700', trustee: 'bg-amber-100 text-amber-700', beneficiary: 'bg-green-100 text-green-700'
};

export default function CaseDetail() {
  const { caseId } = useParams();
  const navigate = useNavigate();
  const [caseData, setCaseData] = useState(null);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('dossier');
  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteResult, setInviteResult] = useState(null);
  const [reminders, setReminders] = useState([]);
  const [sendingReminder, setSendingReminder] = useState(false);
  const [viewDoc, setViewDoc] = useState(null);
  const [editParty, setEditParty] = useState(null);
  const [addParty, setAddParty] = useState(null); // {parentId, role}
  const [osintResults, setOsintResults] = useState([]);
  const [runningOsint, setRunningOsint] = useState(null);

  useEffect(() => { loadCase(); }, [caseId]);

  const loadCase = () => {
    Promise.all([
      api.get(`/cases/${caseId}`),
      api.get(`/audit/case/${caseId}`),
      api.get(`/reminders?case_id=${caseId}`),
      api.get(`/screening/osint-results?case_id=${caseId}`)
    ]).then(([caseRes, auditRes, remRes, osintRes]) => {
      setCaseData(caseRes.data);
      setAuditLogs(auditRes.data);
      setReminders(remRes.data);
      setOsintResults(osintRes.data);
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
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  const handleRiskAssess = async () => {
    try {
      await api.post('/risk/assess', { case_id: caseId, inputs: {} });
      loadCase();
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  const handleOsint = async (partyId) => {
    try {
      await api.post('/osint/analyze', { case_id: caseId, party_id: partyId });
      loadCase();
      alert('OSINT analysis complete');
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  const handleExport = async () => {
    try {
      const res = await api.post(`/export/kyc/${caseId}`);
      alert(`Export created: ${res.data.filename}`);
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  const handleRequirementUpdate = async (reqId, status) => {
    try {
      await api.put(`/cases/${caseId}/requirements/${reqId}`, { status });
      loadCase();
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  const handleSaveParty = async (partyId, data) => {
    try {
      await api.put(`/cases/${caseId}/parties/${partyId}`, data);
      setEditParty(null);
      loadCase();
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  const handleAddParty = async (data) => {
    try {
      await api.post(`/cases/${caseId}/parties`, data);
      setAddParty(null);
      loadCase();
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  const handleOsintScreening = async (partyId) => {
    setRunningOsint(partyId);
    try {
      const res = await api.post('/screening/osint', { case_id: caseId, party_id: partyId });
      loadCase();
      alert('OSINT screening complete');
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
    finally { setRunningOsint(null); }
  };

  const openDocViewer = (doc) => {
    const token = localStorage.getItem('ddys_token');
    const url = `${BACKEND_URL}/api/documents/view/${doc.id}`;
    window.open(url + `?token=${token}`, '_blank');
  };

  if (loading) return <div className="text-sm text-[#64748B] flex items-center justify-center h-64">Loading case...</div>;
  if (!caseData) return <div className="text-sm text-red-600">Case not found</div>;

  const c = caseData;
  const parties = c.parties || [];
  const requirements = c.requirements || [];
  const documents = c.documents || [];
  const screeningRuns = c.screening_runs || [];
  const riskAssessments = c.risk_assessments || [];
  const approvalTasks = c.approval_tasks || [];
  const waivers = c.waivers || [];

  // Organize parties
  const clientParty = parties.find(p => p.role_in_case === 'client');
  const ubos = parties.filter(p => p.role_in_case === 'ubo');
  const directors = parties.filter(p => ['director', 'signatory'].includes(p.role_in_case));
  const otherParties = parties.filter(p => !['client', 'ubo', 'director', 'signatory'].includes(p.role_in_case));

  // Requirement stats
  const reqStats = {};
  requirements.forEach(r => { reqStats[r.status] = (reqStats[r.status] || 0) + 1; });
  const totalReqs = requirements.length;
  const doneReqs = (reqStats.approved || 0) + (reqStats.auto_passed || 0) + (reqStats.waived || 0);
  const progress = totalReqs > 0 ? Math.round((doneReqs / totalReqs) * 100) : 0;

  const nextTransitions = {
    draft: ['customer_in_progress'], customer_in_progress: ['customer_submitted'],
    customer_submitted: ['automated_checks'], automated_checks: ['maker_review'],
    maker_review: ['checker_review'], checker_review: ['business_approval', 'compliance_approval', 'completed'],
    business_approval: ['compliance_approval', 'mlro_approval', 'completed'],
    compliance_approval: ['mlro_approval', 'completed'], mlro_approval: ['completed'],
  };

  // Helper: get requirements + docs for a party
  const getPartyReqs = (partyId) => requirements.filter(r => r.party_id === partyId);
  const getPartyDocs = (partyId) => documents.filter(d => d.party_id === partyId);
  const getDocForReq = (reqId) => documents.find(d => d.requirement_item_id === reqId);

  return (
    <TooltipProvider>
      <div data-testid="case-detail">
        {/* Header */}
        <div className="flex items-center gap-3 mb-4">
          <Button variant="ghost" size="sm" onClick={() => navigate('/workspace/cases')} data-testid="back-to-cases"><ArrowLeft size={16} /></Button>
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold tracking-tight font-['IBM_Plex_Sans']">{c.case_ref}</h1>
              <Badge className={`${STATUS_COLORS[c.status] || 'bg-gray-100'} border-transparent`}>{c.status?.replace(/_/g, ' ')}</Badge>
              {c.risk_rating && <Badge className={`${RISK_COLORS[c.risk_rating]} border-transparent capitalize`}>{c.risk_rating}</Badge>}
              {c.due_diligence_level && <Badge variant="outline" className="text-xs uppercase">{c.due_diligence_level}</Badge>}
            </div>
            <p className="text-sm text-[#64748B] mt-0.5">{c.case_type?.replace(/_/g, ' ')} | {c.jurisdiction} | {c.product_scope || 'N/A'}</p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Dialog open={showInvite} onOpenChange={setShowInvite}>
              <DialogTrigger asChild><Button size="sm" variant="outline" data-testid="invite-customer-btn"><UserPlus size={14} className="mr-1" /> Invite</Button></DialogTrigger>
              <DialogContent>
                <DialogHeader><DialogTitle>Invite Customer</DialogTitle></DialogHeader>
                <div className="space-y-4 pt-2">
                  <p className="text-sm text-[#64748B]">Send a secure KYC portal link to the customer.</p>
                  <div><Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Email</Label>
                  <Input className="mt-1.5" type="email" value={inviteEmail} onChange={e => setInviteEmail(e.target.value)} placeholder="customer@example.com" data-testid="invite-email-input" /></div>
                  {inviteResult && <div className="p-3 bg-green-50 border border-green-200 rounded-md text-sm text-green-700">{inviteResult.message}<br/><span className="font-['JetBrains_Mono'] text-xs">{window.location.origin}{inviteResult.invite_url}</span></div>}
                  <Button className="w-full bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleInviteCustomer} disabled={!inviteEmail} data-testid="send-invite-btn"><Send size={14} className="mr-1" /> Send</Button>
                </div>
              </DialogContent>
            </Dialog>
            <Button size="sm" variant="outline" onClick={handleSendReminder} disabled={sendingReminder} data-testid="send-reminder-btn"><Bell size={14} className="mr-1" /> Remind</Button>
            {(nextTransitions[c.status] || []).map(t => (
              <Button key={t} size="sm" variant="outline" onClick={() => handleTransition(t)} data-testid={`transition-${t}`}>{t.replace(/_/g, ' ')}</Button>
            ))}
            <Button size="sm" variant="outline" onClick={handleExport} data-testid="export-kyc-btn"><Download size={14} className="mr-1" /> Export</Button>
          </div>
        </div>

        {/* Progress bar */}
        <div className="mb-4 flex items-center gap-3">
          <div className="flex-1 h-2 bg-gray-200 rounded-full"><div className="h-2 bg-[#0F172A] rounded-full transition-all" style={{ width: `${progress}%` }} /></div>
          <span className="text-xs font-['JetBrains_Mono'] text-[#64748B] shrink-0">{doneReqs}/{totalReqs} requirements done</span>
        </div>

        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="mb-4">
            <TabsTrigger value="dossier" data-testid="tab-dossier">Dossier</TabsTrigger>
            <TabsTrigger value="status" data-testid="tab-status">Document Status</TabsTrigger>
            <TabsTrigger value="structure" data-testid="tab-structure">Company Structure</TabsTrigger>
            <TabsTrigger value="screening" data-testid="tab-screening">Screening</TabsTrigger>
            <TabsTrigger value="risk" data-testid="tab-risk">Risk</TabsTrigger>
            <TabsTrigger value="approvals" data-testid="tab-approvals">Approvals</TabsTrigger>
            <TabsTrigger value="audit" data-testid="tab-audit">Audit</TabsTrigger>
          </TabsList>

          {/* ===== TAB: DOSSIER (One-Pager) ===== */}
          <TabsContent value="dossier">
            <div className="space-y-4">
              {/* Client / Company */}
              {clientParty && (
                <Card className="border-[#E2E8F0] border-l-4 border-l-blue-500">
                  <CardContent className="p-5">
                    <div className="flex items-start gap-4">
                      <div className="w-12 h-12 rounded-lg bg-blue-50 flex items-center justify-center shrink-0">
                        {clientParty.party_type === 'legal_entity' ? <Building2 size={24} className="text-blue-600" /> : <User size={24} className="text-blue-600" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2">
                          <h2 className="text-lg font-semibold font-['IBM_Plex_Sans']">{clientParty.legal_name || `${clientParty.first_name} ${clientParty.last_name}`}</h2>
                          <Badge className="bg-blue-100 text-blue-700 border-transparent">Client</Badge>
                          <Badge variant="outline" className="text-xs">{clientParty.party_type?.replace(/_/g, ' ')}</Badge>
                        </div>
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                          {clientParty.nationality && <InfoField icon={Globe} label="Nationality" value={clientParty.nationality} />}
                          {clientParty.dob && <InfoField icon={Calendar} label="Date of Birth" value={clientParty.dob} />}
                          {clientParty.identifiers_json?.registration_number && <InfoField icon={CreditCard} label="Reg. Number" value={clientParty.identifiers_json.registration_number} />}
                          {clientParty.identifiers_json?.lei && <InfoField icon={CreditCard} label="LEI" value={clientParty.identifiers_json.lei} />}
                          {clientParty.identifiers_json?.passport && <InfoField icon={CreditCard} label="Passport" value={clientParty.identifiers_json.passport} />}
                          {typeof clientParty.addresses_json === 'object' && Object.entries(clientParty.addresses_json).map(([k, v]) => (
                            <InfoField key={k} icon={MapPin} label={k} value={String(v)} />
                          ))}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* UBOs */}
              {ubos.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-[#64748B] uppercase tracking-wider mb-2 flex items-center gap-2"><Users size={14} /> Ultimate Beneficial Owners ({ubos.length})</h3>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                    {ubos.map(p => <PersonCard key={p.id} party={p} requirements={getPartyReqs(p.id)} documents={getPartyDocs(p.id)} allDocs={documents} onOsint={() => handleOsint(p.id)} onViewDoc={openDocViewer} getDocForReq={getDocForReq} />)}
                  </div>
                </div>
              )}

              {/* Directors */}
              {directors.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-[#64748B] uppercase tracking-wider mb-2 flex items-center gap-2"><User size={14} /> Directors & Signatories ({directors.length})</h3>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                    {directors.map(p => <PersonCard key={p.id} party={p} requirements={getPartyReqs(p.id)} documents={getPartyDocs(p.id)} allDocs={documents} onOsint={() => handleOsint(p.id)} onViewDoc={openDocViewer} getDocForReq={getDocForReq} />)}
                  </div>
                </div>
              )}

              {/* Other parties */}
              {otherParties.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-[#64748B] uppercase tracking-wider mb-2">Other Parties ({otherParties.length})</h3>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                    {otherParties.map(p => <PersonCard key={p.id} party={p} requirements={getPartyReqs(p.id)} documents={getPartyDocs(p.id)} allDocs={documents} onOsint={() => handleOsint(p.id)} onViewDoc={openDocViewer} getDocForReq={getDocForReq} />)}
                  </div>
                </div>
              )}

              {/* Key dates */}
              <Card className="border-[#E2E8F0]">
                <CardContent className="p-4">
                  <h3 className="text-xs font-semibold text-[#64748B] uppercase tracking-wider mb-2">Key Dates & Case Info</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <InfoField icon={Calendar} label="Created" value={c.created_at?.slice(0,10)} />
                    <InfoField icon={Clock} label="Last Action" value={c.last_action_at?.slice(0,10)} />
                    <InfoField icon={Calendar} label="NRD" value={c.nrd_date?.slice(0,10) || 'Not set'} />
                    <InfoField icon={Globe} label="Jurisdiction" value={c.jurisdiction} />
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* ===== TAB: DOCUMENT STATUS (One-Pager) ===== */}
          <TabsContent value="status">
            <div className="space-y-6">
              {parties.map(party => {
                const partyReqs = getPartyReqs(party.id);
                if (!partyReqs.length) return null;
                const pName = party.legal_name || `${party.first_name} ${party.last_name}`.trim();
                const done = partyReqs.filter(r => ['approved','auto_passed','waived'].includes(r.status)).length;

                return (
                  <div key={party.id}>
                    <div className="flex items-center gap-2 mb-2">
                      <h3 className="text-sm font-semibold">{pName}</h3>
                      <Badge className={`${ROLE_COLORS[party.role_in_case] || 'bg-gray-100'} border-transparent text-[10px] capitalize`}>{party.role_in_case}</Badge>
                      <span className="text-xs text-[#64748B] font-['JetBrains_Mono']">{done}/{partyReqs.length}</span>
                    </div>
                    <div className="bg-white border border-[#E2E8F0] rounded-md overflow-hidden">
                      <table className="w-full">
                        <thead>
                          <tr className="border-b bg-[#F8FAFC]">
                            <th className="h-8 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Requirement</th>
                            <th className="h-8 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Status</th>
                            <th className="h-8 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Document</th>
                            <th className="h-8 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Feedback</th>
                            <th className="h-8 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {partyReqs.map(r => {
                            const Icon = STATUS_ICONS[r.status] || CircleDot;
                            const doc = getDocForReq(r.id);
                            return (
                              <tr key={r.id} className="border-b hover:bg-[#F8FAFC]">
                                <td className="px-3 py-2 text-sm">{r.requirement_label || r.requirement_key}</td>
                                <td className="px-3 py-2"><div className="flex items-center gap-1.5"><Icon size={14} className={STATUS_COLORS[r.status]?.replace('bg-', 'text-').replace('100', '600').replace(' text-', ' ').split(' ')[0] || 'text-gray-400'} /><Badge className={`${STATUS_COLORS[r.status]} border-transparent text-[10px]`}>{r.status?.replace(/_/g,' ')}</Badge></div></td>
                                <td className="px-3 py-2">{doc ? (
                                  <button onClick={() => openDocViewer(doc)} className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 hover:underline" data-testid={`view-doc-${doc.id}`}>
                                    <File size={12} /> {doc.original_filename?.slice(0,25)}{doc.original_filename?.length > 25 ? '...' : ''}
                                  </button>
                                ) : <span className="text-xs text-[#64748B]">-</span>}</td>
                                <td className="px-3 py-2 text-xs text-[#64748B] max-w-xs truncate">{r.notes || '-'}</td>
                                <td className="px-3 py-2">
                                  <div className="flex gap-1">
                                    {r.status === 'needs_review' && <>
                                      <Button size="sm" variant="ghost" className="h-6 text-[10px] text-green-600 px-2" onClick={() => handleRequirementUpdate(r.id, 'approved')}>Approve</Button>
                                      <Button size="sm" variant="ghost" className="h-6 text-[10px] text-red-600 px-2" onClick={() => handleRequirementUpdate(r.id, 'rejected')}>Reject</Button>
                                    </>}
                                    {r.status === 'submitted' && <Button size="sm" variant="ghost" className="h-6 text-[10px] text-green-600 px-2" onClick={() => handleRequirementUpdate(r.id, 'approved')}>Approve</Button>}
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                );
              })}
            </div>
          </TabsContent>

          {/* ===== TAB: COMPANY STRUCTURE ===== */}
          <TabsContent value="structure">
            <Card className="border-[#E2E8F0]">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="text-sm font-semibold text-[#64748B] uppercase tracking-wider">Ownership & Control Structure</h3>
                  <Button size="sm" variant="outline" onClick={() => setAddParty({ parentId: clientParty?.id, role: 'ubo' })} data-testid="add-owner-btn">
                    <UserPlus size={14} className="mr-1" /> Add Owner / Entity
                  </Button>
                </div>
                <div className="flex flex-col items-center">
                  {clientParty && (
                    <div className="bg-blue-50 border-2 border-blue-300 rounded-lg p-4 text-center mb-2 min-w-[280px] cursor-pointer hover:border-blue-500 transition-colors" onClick={() => setEditParty(clientParty)} data-testid="structure-client">
                      <Building2 size={24} className="mx-auto text-blue-600 mb-1" />
                      <p className="text-sm font-semibold">{clientParty.legal_name || `${clientParty.first_name} ${clientParty.last_name}`}</p>
                      <p className="text-[10px] text-[#64748B]">{clientParty.party_type?.replace(/_/g, ' ')} | {clientParty.nationality}</p>
                      {clientParty.identifiers_json?.registration_number && <p className="text-[10px] font-['JetBrains_Mono'] text-[#64748B]">Reg: {clientParty.identifiers_json.registration_number}</p>}
                      <p className="text-[9px] text-blue-500 mt-1">Click to edit</p>
                    </div>
                  )}
                  {(ubos.length > 0 || directors.length > 0) && <div className="w-0.5 h-8 bg-[#CBD5E1]" />}
                  {ubos.length > 0 && (
                    <div className="mb-6 w-full">
                      <p className="text-center text-[10px] text-[#64748B] uppercase tracking-wider mb-3">Beneficial Owners</p>
                      <div className="flex justify-center gap-4 flex-wrap">
                        {ubos.map(p => {
                          const pReqs = getPartyReqs(p.id); const pDone = pReqs.filter(r => ['approved','auto_passed','waived'].includes(r.status)).length;
                          // Check if this UBO is a company (needs sub-owners)
                          const subOwners = parties.filter(sp => sp.parent_party_id === p.id);
                          return (
                            <div key={p.id} className="flex flex-col items-center">
                              <div className={`${p.party_type === 'legal_entity' ? 'bg-blue-50 border-blue-300' : 'bg-purple-50 border-purple-300'} border-2 rounded-lg p-3 text-center min-w-[200px] relative cursor-pointer hover:shadow-md transition-shadow`} onClick={() => setEditParty(p)} data-testid={`structure-ubo-${p.id}`}>
                                <div className="absolute -top-3 left-1/2 -translate-x-1/2 w-0.5 h-3 bg-[#CBD5E1]" />
                                {p.party_type === 'legal_entity' ? <Building2 size={20} className="mx-auto text-blue-600 mb-1" /> : <User size={20} className="mx-auto text-purple-600 mb-1" />}
                                <p className="text-sm font-semibold">{p.legal_name || `${p.first_name} ${p.last_name}`}</p>
                                {p.ownership_percent && <div className="flex items-center justify-center gap-1 mt-1"><Percent size={12} className="text-purple-600" /><span className="text-lg font-bold font-['JetBrains_Mono'] text-purple-700">{p.ownership_percent}%</span></div>}
                                <div className="text-[10px] text-[#64748B] mt-1 space-y-0.5">{p.nationality && <p>{p.nationality}</p>}{p.dob && <p>DOB: {p.dob}</p>}</div>
                                <div className="mt-2 flex items-center justify-center gap-1"><div className="w-12 h-1.5 bg-gray-200 rounded-full"><div className={`h-1.5 ${p.party_type === 'legal_entity' ? 'bg-blue-500' : 'bg-purple-500'} rounded-full`} style={{ width: `${pReqs.length ? (pDone/pReqs.length)*100 : 0}%` }} /></div><span className="text-[9px] text-[#64748B]">{pDone}/{pReqs.length}</span></div>
                                <p className="text-[9px] text-blue-500 mt-1">Click to edit</p>
                                {p.party_type === 'legal_entity' && (
                                  <Button size="sm" variant="ghost" className="mt-1 h-6 text-[10px]" onClick={(e) => { e.stopPropagation(); setAddParty({ parentId: p.id, role: 'ubo' }); }}>
                                    <UserPlus size={10} className="mr-1" /> Add Sub-Owner
                                  </Button>
                                )}
                              </div>
                              {/* Sub-owners */}
                              {subOwners.length > 0 && (
                                <div className="mt-2">
                                  <div className="w-0.5 h-4 bg-[#CBD5E1] mx-auto" />
                                  <div className="flex gap-2">
                                    {subOwners.map(so => (
                                      <div key={so.id} className="bg-gray-50 border border-gray-300 rounded-lg p-2 text-center min-w-[140px] cursor-pointer hover:shadow-sm" onClick={() => setEditParty(so)}>
                                        {so.party_type === 'legal_entity' ? <Building2 size={14} className="mx-auto text-gray-600 mb-0.5" /> : <User size={14} className="mx-auto text-gray-600 mb-0.5" />}
                                        <p className="text-xs font-medium">{so.legal_name || `${so.first_name} ${so.last_name}`}</p>
                                        {so.ownership_percent && <p className="text-xs font-bold font-['JetBrains_Mono']">{so.ownership_percent}%</p>}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                  {directors.length > 0 && (
                    <div className="w-full">
                      <p className="text-center text-[10px] text-[#64748B] uppercase tracking-wider mb-3">Directors & Signatories</p>
                      <div className="flex justify-center gap-4 flex-wrap">
                        {directors.map(p => (
                          <div key={p.id} className="bg-teal-50 border-2 border-teal-300 rounded-lg p-3 text-center min-w-[200px] cursor-pointer hover:shadow-md transition-shadow" onClick={() => setEditParty(p)} data-testid={`structure-director-${p.id}`}>
                            <User size={20} className="mx-auto text-teal-600 mb-1" /><p className="text-sm font-semibold">{p.first_name} {p.last_name}</p><Badge className="bg-teal-100 text-teal-700 border-transparent text-[9px] mt-1">{p.role_in_case}</Badge>
                            <p className="text-[9px] text-blue-500 mt-1">Click to edit</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Edit Party Dialog */}
            <Dialog open={!!editParty} onOpenChange={(o) => { if (!o) setEditParty(null); }}>
              <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
                <DialogHeader><DialogTitle>Edit: {editParty?.legal_name || `${editParty?.first_name} ${editParty?.last_name}`}</DialogTitle></DialogHeader>
                {editParty && <PartyEditForm party={editParty} onSave={(data) => handleSaveParty(editParty.id, data)} onClose={() => setEditParty(null)} />}
              </DialogContent>
            </Dialog>

            {/* Add Party Dialog */}
            <Dialog open={!!addParty} onOpenChange={(o) => { if (!o) setAddParty(null); }}>
              <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
                <DialogHeader><DialogTitle>Add Owner / Related Party</DialogTitle></DialogHeader>
                {addParty && <PartyAddForm parentId={addParty.parentId} defaultRole={addParty.role} onAdd={handleAddParty} onClose={() => setAddParty(null)} />}
              </DialogContent>
            </Dialog>
          </TabsContent>

          {/* ===== TAB: SCREENING (with OSINT) ===== */}
          <TabsContent value="screening">
            <div className="space-y-6">
              {/* Batch screening */}
              <div>
                <h3 className="text-xs font-semibold text-[#64748B] uppercase tracking-wider mb-2">Batch Screening (All Parties)</h3>
                <div className="flex gap-2">
                  <Button size="sm" onClick={() => handleScreening('sanctions')} data-testid="run-sanctions"><Shield size={14} className="mr-1" /> Sanctions</Button>
                  <Button size="sm" onClick={() => handleScreening('pep')} data-testid="run-pep"><Users size={14} className="mr-1" /> PEP</Button>
                  <Button size="sm" onClick={() => handleScreening('adverse_media')} data-testid="run-adverse"><AlertTriangle size={14} className="mr-1" /> Adverse Media</Button>
                </div>
              </div>

              {/* OSINT per party */}
              <div>
                <h3 className="text-xs font-semibold text-[#64748B] uppercase tracking-wider mb-2">OSINT Screening (Per Party)</h3>
                <div className="space-y-2">
                  {parties.map(p => {
                    const pName = p.legal_name || `${p.first_name} ${p.last_name}`.trim();
                    const pOsint = osintResults.filter(r => r.party_id === p.id);
                    return (
                      <Card key={p.id} className="border-[#E2E8F0]">
                        <CardContent className="p-3">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              {p.party_type === 'legal_entity' ? <Building2 size={14} className="text-blue-600" /> : <User size={14} className="text-purple-600" />}
                              <span className="text-sm font-medium">{pName}</span>
                              <Badge className={`${ROLE_COLORS[p.role_in_case] || 'bg-gray-100'} border-transparent text-[10px] capitalize`}>{p.role_in_case}</Badge>
                              {pOsint.length > 0 && (
                                <Badge className={
                                  pOsint[0]?.result_json?.overall_risk_assessment === 'high' ? 'bg-red-100 text-red-700 border-transparent text-[10px]' :
                                  pOsint[0]?.result_json?.overall_risk_assessment === 'medium' ? 'bg-amber-100 text-amber-700 border-transparent text-[10px]' :
                                  'bg-green-100 text-green-700 border-transparent text-[10px]'
                                }>{pOsint[0]?.result_json?.overall_risk_assessment || 'checked'}</Badge>
                              )}
                            </div>
                            <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => handleOsintScreening(p.id)} disabled={runningOsint === p.id} data-testid={`osint-screen-${p.id}`}>
                              <Search size={12} className="mr-1" /> {runningOsint === p.id ? 'Running...' : 'Run OSINT'}
                            </Button>
                          </div>
                          {pOsint.length > 0 && (
                            <div className="mt-2 p-2 bg-[#F8FAFC] rounded-md text-xs space-y-1">
                              <div className="grid grid-cols-4 gap-2">
                                <div><span className="text-[#64748B]">PEP:</span> <span className="font-medium">{pOsint[0]?.result_json?.pep_likelihood}</span></div>
                                <div><span className="text-[#64748B]">Sanctions:</span> <span className="font-medium">{pOsint[0]?.result_json?.sanctions_risk}</span></div>
                                <div><span className="text-[#64748B]">Country:</span> <span className="font-medium">{pOsint[0]?.result_json?.country_risk}</span></div>
                                <div><span className="text-[#64748B]">Overall:</span> <span className="font-semibold">{pOsint[0]?.result_json?.overall_risk_assessment}</span></div>
                              </div>
                              {pOsint[0]?.result_json?.adverse_media_summary && (
                                <p className="text-[#64748B]"><span className="font-medium">Adverse Media:</span> {pOsint[0].result_json.adverse_media_summary}</p>
                              )}
                              {pOsint[0]?.result_json?.recommendations?.length > 0 && (
                                <div><span className="font-medium text-[#64748B]">Recommendations:</span> {pOsint[0].result_json.recommendations.join('; ')}</div>
                              )}
                              <p className="text-[10px] text-[#64748B] font-['JetBrains_Mono']">Run: {new Date(pOsint[0].created_at).toLocaleString()}</p>
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              </div>

              {/* Screening runs log */}
              <div>
                <h3 className="text-xs font-semibold text-[#64748B] uppercase tracking-wider mb-2">Screening Run History</h3>
                {screeningRuns.map(run => (
                  <Card key={run.id} className="border-[#E2E8F0] mb-2"><CardContent className="p-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2"><Badge variant="outline" className="text-xs uppercase">{run.run_type}</Badge><Badge className={run.status === 'completed' ? 'bg-green-100 text-green-700 border-transparent' : run.status === 'error' ? 'bg-red-100 text-red-700 border-transparent' : 'bg-amber-100 text-amber-700 border-transparent'}>{run.status}</Badge><span className="text-xs text-[#64748B] font-['JetBrains_Mono']">{run.started_at?.slice(0,19)}</span></div>
                      <span className="text-xs text-[#64748B]">{run.run_type === 'osint' ? run.parameters_json?.party_name : `Hits: ${run.parameters_json?.hits_count ?? '?'}`}</span>
                    </div>
                  </CardContent></Card>
                ))}
                {!screeningRuns.length && <p className="text-sm text-[#64748B] text-center py-4">No screening runs yet.</p>}
              </div>
            </div>
          </TabsContent>

          {/* ===== TAB: RISK ===== */}
          <TabsContent value="risk">
            <div className="space-y-4">
              <Button size="sm" onClick={handleRiskAssess} data-testid="run-risk-assess"><Scale size={14} className="mr-1" /> Run Risk Assessment</Button>
              {riskAssessments.map(ra => (
                <Card key={ra.id} className="border-[#E2E8F0]"><CardContent className="p-4">
                  <div className="flex items-center gap-3 mb-2"><Badge className={`${RISK_COLORS[ra.computed_rating] || ''} border-transparent capitalize text-sm`}>{ra.computed_rating}</Badge><span className="text-sm font-['JetBrains_Mono']">Score: {ra.computed_score}</span><Badge variant="outline" className="uppercase text-xs">{ra.due_diligence_level}</Badge>{ra.challenged && <Badge className="bg-amber-100 text-amber-700 border-transparent">Challenged</Badge>}</div>
                  <div className="text-xs text-[#64748B]">Methodology: {ra.methodology} | {ra.created_at?.slice(0,10)}</div>
                  {Object.entries(ra.per_se_flags_json || {}).some(([,v]) => v) && <div className="mt-2 flex gap-1">{Object.entries(ra.per_se_flags_json || {}).filter(([,v]) => v).map(([k]) => <Badge key={k} className="bg-red-100 text-red-700 border-transparent text-xs">{k.replace(/_/g,' ')}</Badge>)}</div>}
                </CardContent></Card>
              ))}
            </div>
          </TabsContent>

          {/* ===== TAB: APPROVALS ===== */}
          <TabsContent value="approvals">
            <div className="bg-white border border-[#E2E8F0] rounded-md overflow-hidden">
              <table className="w-full"><thead><tr className="border-b bg-[#F8FAFC]">
                <th className="h-8 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Task</th>
                <th className="h-8 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Status</th>
                <th className="h-8 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Decision</th>
                <th className="h-8 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Date</th>
              </tr></thead><tbody>
                {approvalTasks.map(t => (
                  <tr key={t.id} className="border-b hover:bg-[#F8FAFC]">
                    <td className="px-3 py-2 text-sm capitalize">{t.task_type?.replace(/_/g,' ')}</td>
                    <td className="px-3 py-2"><Badge className={t.status === 'completed' ? 'bg-green-100 text-green-700 border-transparent' : 'bg-amber-100 text-amber-700 border-transparent'}>{t.status}</Badge></td>
                    <td className="px-3 py-2"><Badge className={t.decision === 'approved' ? 'bg-green-100 text-green-700 border-transparent' : t.decision === 'rejected' ? 'bg-red-100 text-red-700 border-transparent' : 'bg-gray-100 border-transparent'}>{t.decision || 'pending'}</Badge></td>
                    <td className="px-3 py-2 text-xs font-['JetBrains_Mono'] text-[#64748B]">{t.created_at?.slice(0,10)}</td>
                  </tr>
                ))}
                {!approvalTasks.length && <tr><td colSpan={4} className="px-3 py-8 text-center text-sm text-[#64748B]">No approval tasks</td></tr>}
              </tbody></table>
            </div>
          </TabsContent>

          {/* ===== TAB: AUDIT ===== */}
          <TabsContent value="audit">
            <div className="bg-white border border-[#E2E8F0] rounded-md overflow-hidden max-h-[500px] overflow-y-auto">
              <table className="w-full"><thead className="sticky top-0 bg-[#F8FAFC]"><tr className="border-b">
                <th className="h-8 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Time</th>
                <th className="h-8 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Action</th>
                <th className="h-8 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Actor</th>
                <th className="h-8 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Entity</th>
              </tr></thead><tbody>
                {auditLogs.map(l => (
                  <tr key={l.id} className="border-b hover:bg-[#F8FAFC]">
                    <td className="px-3 py-1.5 text-[11px] font-['JetBrains_Mono'] text-[#64748B]">{l.timestamp?.slice(0,19)}</td>
                    <td className="px-3 py-1.5 text-xs font-medium">{l.action_key}</td>
                    <td className="px-3 py-1.5 text-xs text-[#64748B]">{l.actor_role}</td>
                    <td className="px-3 py-1.5 text-[11px] font-['JetBrains_Mono'] text-[#64748B]">{l.entity_type}/{l.entity_id?.slice(0,8)}</td>
                  </tr>
                ))}
              </tbody></table>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </TooltipProvider>
  );
}

// ===== Sub-Components =====

function InfoField({ icon: Icon, label, value }) {
  return (
    <div className="flex items-start gap-2">
      <Icon size={12} className="text-[#64748B] mt-0.5 shrink-0" />
      <div>
        <p className="text-[10px] text-[#64748B] uppercase tracking-wider">{label}</p>
        <p className="text-sm font-medium font-['JetBrains_Mono'] leading-tight">{value || '-'}</p>
      </div>
    </div>
  );
}

function PersonCard({ party, requirements, documents, allDocs, onOsint, onViewDoc, getDocForReq }) {
  const p = party;
  const name = `${p.first_name} ${p.last_name}`.trim() || p.legal_name;
  const done = requirements.filter(r => ['approved','auto_passed','waived'].includes(r.status)).length;
  const total = requirements.length;

  return (
    <Card className="border-[#E2E8F0]">
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-[#F1F5F9] flex items-center justify-center text-xs font-semibold text-[#64748B]">{name.charAt(0)}</div>
            <div>
              <p className="text-sm font-semibold">{name}</p>
              <div className="flex items-center gap-1">
                <Badge className={`${ROLE_COLORS[p.role_in_case] || 'bg-gray-100'} border-transparent text-[9px] capitalize`}>{p.role_in_case}</Badge>
                {p.ownership_percent && <span className="text-xs font-['JetBrains_Mono'] text-purple-700 font-bold">{p.ownership_percent}%</span>}
              </div>
            </div>
          </div>
          <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={onOsint} data-testid={`osint-${p.id}`}><Search size={12} className="mr-1" /> OSINT</Button>
        </div>
        {/* Personal data */}
        <div className="grid grid-cols-2 gap-2 mb-3 text-xs">
          {p.nationality && <div><span className="text-[#64748B]">Nationality:</span> <span className="font-medium">{p.nationality}</span></div>}
          {p.dob && <div><span className="text-[#64748B]">DOB:</span> <span className="font-['JetBrains_Mono']">{p.dob}</span></div>}
          {p.identifiers_json?.place_of_birth && <div><span className="text-[#64748B]">Birth Place:</span> <span>{p.identifiers_json.place_of_birth}</span></div>}
          {p.identifiers_json?.middle_names && <div><span className="text-[#64748B]">Middle Names:</span> <span>{p.identifiers_json.middle_names}</span></div>}
          {p.identifiers_json?.passport && <div><span className="text-[#64748B]">Passport:</span> <span className="font-['JetBrains_Mono'] font-medium">{p.identifiers_json.passport}</span></div>}
          {p.identifiers_json?.passport_expiry && <div><span className="text-[#64748B]">Passport Exp:</span> <span className="font-['JetBrains_Mono']">{p.identifiers_json.passport_expiry}</span></div>}
          {p.identifiers_json?.passport_issuing_authority && <div className="col-span-2"><span className="text-[#64748B]">Issuing Authority:</span> <span>{p.identifiers_json.passport_issuing_authority}</span></div>}
          {p.identifiers_json?.passport_mrz && <div className="col-span-2"><span className="text-[#64748B]">MRZ:</span> <span className="font-['JetBrains_Mono'] text-[10px] break-all">{p.identifiers_json.passport_mrz}</span></div>}
          {p.identifiers_json?.national_id && <div><span className="text-[#64748B]">National ID:</span> <span className="font-['JetBrains_Mono']">{p.identifiers_json.national_id}</span></div>}
          {p.identifiers_json?.national_id_expiry && <div><span className="text-[#64748B]">ID Exp:</span> <span className="font-['JetBrains_Mono']">{p.identifiers_json.national_id_expiry}</span></div>}
          {typeof p.addresses_json === 'object' && Object.entries(p.addresses_json).map(([k,v]) => (
            <div key={k} className="col-span-2"><span className="text-[#64748B]">{k}:</span> <span>{String(v)}</span></div>
          ))}
        </div>
        {/* Requirement status mini-list */}
        <div className="border-t border-[#F1F5F9] pt-2">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-[#64748B] uppercase tracking-wider">Documents</span>
            <span className="text-[10px] font-['JetBrains_Mono'] text-[#64748B]">{done}/{total}</span>
          </div>
          <div className="space-y-1">
            {requirements.map(r => {
              const SIcon = STATUS_ICONS[r.status] || CircleDot;
              const doc = getDocForReq(r.id);
              return (
                <div key={r.id} className="flex items-center gap-2 text-xs">
                  <SIcon size={12} className={r.status === 'approved' || r.status === 'auto_passed' ? 'text-green-500' : r.status === 'rejected' ? 'text-red-500' : r.status === 'submitted' || r.status === 'needs_review' ? 'text-amber-500' : 'text-gray-400'} />
                  <span className="flex-1 truncate">{r.requirement_label || r.requirement_key}</span>
                  {doc && (
                    <button onClick={() => onViewDoc(doc)} className="text-blue-500 hover:text-blue-700 shrink-0" data-testid={`view-${doc.id}`}>
                      <Eye size={12} />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}


function PartyEditForm({ party, onSave, onClose }) {
  const [form, setForm] = useState({
    party_type: party.party_type || 'natural_person',
    role_in_case: party.role_in_case || '',
    first_name: party.first_name || '',
    last_name: party.last_name || '',
    middle_names: party.identifiers_json?.middle_names || '',
    legal_name: party.legal_name || '',
    dob: party.dob || '',
    place_of_birth: party.identifiers_json?.place_of_birth || '',
    nationality: party.nationality || '',
    ownership_percent: party.ownership_percent || '',
    address: typeof party.addresses_json === 'object' ? Object.values(party.addresses_json)[0] || '' : '',
    // ID Document fields
    passport_number: party.identifiers_json?.passport || '',
    passport_expiry: party.identifiers_json?.passport_expiry || '',
    passport_issued: party.identifiers_json?.passport_issued || '',
    passport_issuing_authority: party.identifiers_json?.passport_issuing_authority || '',
    passport_mrz: party.identifiers_json?.passport_mrz || '',
    national_id: party.identifiers_json?.national_id || '',
    national_id_expiry: party.identifiers_json?.national_id_expiry || '',
    // Company fields
    registration_number: party.identifiers_json?.registration_number || '',
    lei: party.identifiers_json?.lei || '',
  });

  const handleSave = () => {
    const addrKey = form.party_type === 'legal_entity' ? 'registered' : 'residential';
    const identifiers = {};
    if (form.passport_number) identifiers.passport = form.passport_number;
    if (form.passport_expiry) identifiers.passport_expiry = form.passport_expiry;
    if (form.passport_issued) identifiers.passport_issued = form.passport_issued;
    if (form.passport_issuing_authority) identifiers.passport_issuing_authority = form.passport_issuing_authority;
    if (form.passport_mrz) identifiers.passport_mrz = form.passport_mrz;
    if (form.middle_names) identifiers.middle_names = form.middle_names;
    if (form.place_of_birth) identifiers.place_of_birth = form.place_of_birth;
    if (form.national_id) identifiers.national_id = form.national_id;
    if (form.national_id_expiry) identifiers.national_id_expiry = form.national_id_expiry;
    if (form.registration_number) identifiers.registration_number = form.registration_number;
    if (form.lei) identifiers.lei = form.lei;

    onSave({
      party_type: form.party_type, role_in_case: form.role_in_case,
      first_name: form.first_name, last_name: form.last_name, legal_name: form.legal_name,
      dob: form.dob || null, nationality: form.nationality,
      ownership_percent: form.ownership_percent ? parseFloat(form.ownership_percent) : null,
      addresses_json: form.address ? { [addrKey]: form.address } : {},
      identifiers_json: identifiers
    });
  };

  const isCompany = form.party_type === 'legal_entity';
  const s = (k, v) => setForm(prev => ({ ...prev, [k]: v }));

  return (
    <div className="space-y-3 pt-2" data-testid="party-edit-form">
      <div className="grid grid-cols-2 gap-3">
        <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Type</Label>
          <select className="mt-1 w-full h-9 rounded-md border border-input px-3 text-sm" value={form.party_type} onChange={e => s('party_type', e.target.value)}>
            <option value="natural_person">Individual</option><option value="legal_entity">Company</option><option value="trust">Trust</option>
          </select>
        </div>
        <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Role</Label>
          <select className="mt-1 w-full h-9 rounded-md border border-input px-3 text-sm" value={form.role_in_case} onChange={e => s('role_in_case', e.target.value)}>
            <option value="client">Client</option><option value="ubo">UBO</option><option value="director">Director</option><option value="signatory">Signatory</option><option value="beneficiary">Beneficiary</option>
          </select>
        </div>
      </div>

      {isCompany ? (
        <>
          <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Company Name</Label><Input className="mt-1" value={form.legal_name} onChange={e => s('legal_name', e.target.value)} /></div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Reg. Number</Label><Input className="mt-1" value={form.registration_number} onChange={e => s('registration_number', e.target.value)} /></div>
            <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">LEI</Label><Input className="mt-1" value={form.lei} onChange={e => s('lei', e.target.value)} /></div>
          </div>
        </>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-3">
            <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">First Name</Label><Input className="mt-1" value={form.first_name} onChange={e => s('first_name', e.target.value)} /></div>
            <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Middle Names</Label><Input className="mt-1" value={form.middle_names} onChange={e => s('middle_names', e.target.value)} placeholder="If applicable" /></div>
            <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Last Name</Label><Input className="mt-1" value={form.last_name} onChange={e => s('last_name', e.target.value)} /></div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Date of Birth</Label><Input className="mt-1" type="date" value={form.dob} onChange={e => s('dob', e.target.value)} /></div>
            <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Place of Birth</Label><Input className="mt-1" value={form.place_of_birth} onChange={e => s('place_of_birth', e.target.value)} placeholder="City, Country" /></div>
            <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Nationality</Label><Input className="mt-1" value={form.nationality} onChange={e => s('nationality', e.target.value)} /></div>
          </div>

          {/* Passport / ID Section */}
          <div className="border border-[#E2E8F0] rounded-md p-3 space-y-3">
            <p className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Passport / ID Document</p>
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Passport Number</Label><Input className="mt-1 font-['JetBrains_Mono']" value={form.passport_number} onChange={e => s('passport_number', e.target.value)} placeholder="C01X00T47" /></div>
              <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">National ID Number</Label><Input className="mt-1 font-['JetBrains_Mono']" value={form.national_id} onChange={e => s('national_id', e.target.value)} /></div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Issue Date</Label><Input className="mt-1" type="date" value={form.passport_issued} onChange={e => s('passport_issued', e.target.value)} /></div>
              <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Expiry Date</Label><Input className="mt-1" type="date" value={form.passport_expiry} onChange={e => s('passport_expiry', e.target.value)} /></div>
              <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">ID Expiry</Label><Input className="mt-1" type="date" value={form.national_id_expiry} onChange={e => s('national_id_expiry', e.target.value)} /></div>
            </div>
            <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Issuing Authority</Label><Input className="mt-1" value={form.passport_issuing_authority} onChange={e => s('passport_issuing_authority', e.target.value)} placeholder="e.g. Bundesrepublik Deutschland" /></div>
            <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">MRZ (Machine Readable Zone)</Label><Input className="mt-1 font-['JetBrains_Mono'] text-xs" value={form.passport_mrz} onChange={e => s('passport_mrz', e.target.value)} placeholder="P<DEUMUELLER<<HANS<<<<<<<<<<<<<<..." /></div>
          </div>
        </>
      )}

      <div className="grid grid-cols-2 gap-3">
        {!isCompany && <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Ownership %</Label><Input className="mt-1" type="number" value={form.ownership_percent} onChange={e => s('ownership_percent', e.target.value)} /></div>}
        {isCompany && <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Nationality / Jurisdiction</Label><Input className="mt-1" value={form.nationality} onChange={e => s('nationality', e.target.value)} /></div>}
        {isCompany && <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Ownership %</Label><Input className="mt-1" type="number" value={form.ownership_percent} onChange={e => s('ownership_percent', e.target.value)} /></div>}
      </div>
      <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Address</Label><Input className="mt-1" value={form.address} onChange={e => s('address', e.target.value)} /></div>
      <div className="flex gap-2">
        <Button className="flex-1 bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleSave} data-testid="save-party-btn">Save</Button>
        <Button variant="outline" onClick={onClose}>Cancel</Button>
      </div>
    </div>
  );
}

function PartyAddForm({ parentId, defaultRole, onAdd, onClose }) {
  const [form, setForm] = useState({
    party_type: 'natural_person',
    role_in_case: defaultRole || 'ubo',
    first_name: '', last_name: '', legal_name: '',
    dob: '', nationality: '', ownership_percent: '',
    address: '', passport: '', registration_number: '',
  });

  const handleSubmit = () => {
    const addrKey = form.party_type === 'legal_entity' ? 'registered' : 'residential';
    onAdd({
      party_type: form.party_type,
      role_in_case: form.role_in_case,
      first_name: form.first_name,
      last_name: form.last_name,
      legal_name: form.legal_name,
      dob: form.dob || null,
      nationality: form.nationality,
      ownership_percent: form.ownership_percent ? parseFloat(form.ownership_percent) : null,
      addresses_json: form.address ? { [addrKey]: form.address } : {},
      identifiers_json: {
        ...(form.passport && { passport: form.passport }),
        ...(form.registration_number && { registration_number: form.registration_number }),
      },
      parent_party_id: parentId || null,
    });
  };

  const isCompany = form.party_type === 'legal_entity';
  const s = (k, v) => setForm(prev => ({ ...prev, [k]: v }));

  return (
    <div className="space-y-3 pt-2" data-testid="party-add-form">
      <div className="grid grid-cols-2 gap-3">
        <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Type</Label>
          <select className="mt-1 w-full h-9 rounded-md border border-input px-3 text-sm" value={form.party_type} onChange={e => s('party_type', e.target.value)}>
            <option value="natural_person">Individual</option><option value="legal_entity">Company</option>
          </select>
        </div>
        <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Role</Label>
          <select className="mt-1 w-full h-9 rounded-md border border-input px-3 text-sm" value={form.role_in_case} onChange={e => s('role_in_case', e.target.value)}>
            <option value="ubo">UBO</option><option value="director">Director</option><option value="signatory">Signatory</option><option value="client">Client</option>
          </select>
        </div>
      </div>
      {isCompany ? (
        <>
          <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Company Name</Label><Input className="mt-1" value={form.legal_name} onChange={e => s('legal_name', e.target.value)} placeholder="Company name" /></div>
          <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Registration Number</Label><Input className="mt-1" value={form.registration_number} onChange={e => s('registration_number', e.target.value)} /></div>
        </>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3">
            <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">First Name</Label><Input className="mt-1" value={form.first_name} onChange={e => s('first_name', e.target.value)} /></div>
            <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Last Name</Label><Input className="mt-1" value={form.last_name} onChange={e => s('last_name', e.target.value)} /></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">DOB</Label><Input className="mt-1" type="date" value={form.dob} onChange={e => s('dob', e.target.value)} /></div>
            <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Passport</Label><Input className="mt-1" value={form.passport} onChange={e => s('passport', e.target.value)} /></div>
          </div>
        </>
      )}
      <div className="grid grid-cols-2 gap-3">
        <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Nationality</Label><Input className="mt-1" value={form.nationality} onChange={e => s('nationality', e.target.value)} placeholder="DE" /></div>
        <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Ownership %</Label><Input className="mt-1" type="number" value={form.ownership_percent} onChange={e => s('ownership_percent', e.target.value)} placeholder="25" /></div>
      </div>
      <div><Label className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Address</Label><Input className="mt-1" value={form.address} onChange={e => s('address', e.target.value)} placeholder="Full address" /></div>
      <Button className="w-full bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleSubmit} data-testid="add-party-btn">Add Party</Button>
    </div>
  );
}

