import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { CheckCircle, Circle, Upload, FileText, AlertCircle, Clock, ArrowRight, HelpCircle, XCircle } from 'lucide-react';
import api from '@/api/client';

const STATUS_ICONS = {
  missing: Circle, submitted: Clock, auto_passed: CheckCircle, needs_review: Clock, approved: CheckCircle, waived: CheckCircle, rejected: XCircle
};
const STATUS_COLORS = {
  missing: 'text-gray-400', submitted: 'text-blue-500', auto_passed: 'text-green-500', needs_review: 'text-amber-500', approved: 'text-green-500', waived: 'text-purple-500', rejected: 'text-red-500'
};
const STATUS_BG = {
  missing: 'bg-gray-100 text-gray-700', submitted: 'bg-blue-100 text-blue-700', auto_passed: 'bg-green-100 text-green-700', needs_review: 'bg-amber-100 text-amber-700', approved: 'bg-green-100 text-green-700', waived: 'bg-purple-100 text-purple-700', rejected: 'bg-red-100 text-red-700'
};

// Help tooltips for each requirement type
const REQUIREMENT_HELP = {
  identity_doc: "A valid, government-issued photo ID such as passport or national identity card. Must not be expired.",
  proof_of_address: "A recent utility bill, bank statement, or official document showing your name and current residential address. Must be issued within the last 3 months for individuals.",
  utility_bill: "Recent utility bill (electricity, gas, water, internet) or equivalent document. Tax returns and police reports are also accepted. Must be within 3 months.",
  tax_return: "Your latest tax return or tax assessment notice. This document also satisfies the utility bill / proof of address requirement.",
  police_report: "An official police clearance certificate or report. Also accepted as proof of address.",
  sanctions_screening: "Automated check against international sanctions lists. No action required from you.",
  pep_screening: "Automated check for Politically Exposed Person status. No action required from you.",
  adverse_media: "Automated adverse media screening. No action required from you.",
  sof_sow: "Documentation showing the source of your funds and/or source of wealth. Bank statements, salary slips, investment records, or business financials.",
  video_ident: "A live video identification session with our verification agent. You'll receive a link to join when scheduled.",
  registry_extract: "Official company registry extract or certificate of incorporation. Must be current and issued by the relevant authority.",
  ownership_chart: "A clear ownership structure chart showing all shareholders with percentages, including intermediate holding entities.",
  articles_of_association: "The company's articles of association, memorandum, or equivalent constitutional documents.",
  board_resolution: "A board resolution or power of attorney authorizing the signatories for this business relationship.",
  proof_of_address_entity: "Official proof of registered business address. Registry extract or utility bill in company name. Valid within 12 months.",
  financial_statements: "Latest audited financial statements or annual report of the company.",
  sanctions_screening_entity: "Automated entity sanctions check. No action required.",
  adverse_media_entity: "Automated entity adverse media check. No action required.",
};

// Document type options per requirement
const DOC_TYPE_OPTIONS = {
  proof_of_address: ["utility_bill", "bank_statement", "tax_return", "police_report", "other"],
  identity_doc: ["id_passport", "id_national", "driving_license", "other"],
  sof_sow: ["bank_statement", "salary_slip", "investment_statement", "business_financials", "other"],
  financial_statements: ["annual_report", "audited_accounts", "other"],
};

export default function CustomerDashboard() {
  const navigate = useNavigate();
  const [caseData, setCaseData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(null);
  const fileRef = useRef(null);
  const [selectedReq, setSelectedReq] = useState(null);
  const [selectedDocType, setSelectedDocType] = useState('other');

  // Get case from either invite flow or legacy flow
  const caseId = localStorage.getItem('ddys_customer_case_id');
  const caseRef = localStorage.getItem('ddys_customer_case_ref');
  const tenantId = localStorage.getItem('ddys_customer_tenant');

  useEffect(() => { loadCase(); }, []);

  const loadCase = () => {
    if (caseId) {
      // Invite-based flow: use case_id directly
      api.get(`/customer/case-by-id/${caseId}`).then(r => setCaseData(r.data)).catch(e => {
        // Fallback to old flow
        loadCaseByRef();
      }).finally(() => setLoading(false));
    } else {
      loadCaseByRef();
    }
  };

  const loadCaseByRef = () => {
    const params = new URLSearchParams();
    if (caseRef) params.set('case_ref', caseRef);
    if (tenantId) params.set('tenant_id', tenantId);
    api.get(`/customer/case?${params}`).then(r => setCaseData(r.data)).catch(() => setCaseData(null)).finally(() => setLoading(false));
  };

  const handleUpload = (reqId, reqKey) => {
    setSelectedReq(reqId);
    // Determine doc_type based on requirement
    const docTypes = DOC_TYPE_OPTIONS[reqKey];
    setSelectedDocType(docTypes ? docTypes[0] : reqKey);
    fileRef.current?.click();
  };

  const onFileSelected = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !selectedReq) return;
    setUploading(selectedReq);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('case_id', caseData.case.id);
    formData.append('tenant_id', caseData.case.tenant_id);
    formData.append('requirement_item_id', selectedReq);
    formData.append('doc_type', selectedDocType);

    // Find party_id from requirement
    const req = caseData.requirements.find(r => r.id === selectedReq);
    if (req?.party_id) formData.append('party_id', req.party_id);

    try {
      await api.post('/documents/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      loadCase();
    } catch (err) { alert(err.response?.data?.detail || 'Upload failed'); }
    finally { setUploading(null); setSelectedReq(null); e.target.value = ''; }
  };

  const handleSubmit = async () => {
    try {
      await api.post('/customer/submit', { case_id: caseData.case.id });
      loadCase();
    } catch (err) { alert(err.response?.data?.detail || 'Submit failed'); }
  };

  if (loading) return <div className="text-sm text-[#64748B] text-center py-12">Loading your case...</div>;
  if (!caseData?.case) return (
    <div className="text-center py-12">
      <p className="text-sm text-[#64748B] mb-4">No case found. Please use the invitation link sent to your email.</p>
      <Button onClick={() => navigate('/portal')} data-testid="back-to-portal">Back to Portal</Button>
    </div>
  );

  const { case: c, requirements, documents, parties, questionnaire, reminders } = caseData;
  const docReqs = requirements.filter(r => !['sanctions', 'pep', 'adverse_media', 'video_ident'].includes(r.requirement_category));
  const autoReqs = requirements.filter(r => ['sanctions', 'pep', 'adverse_media'].includes(r.requirement_category));
  const videoReqs = requirements.filter(r => r.requirement_category === 'video_ident');
  const totalReqs = docReqs.length;
  const completedReqs = docReqs.filter(r => ['approved', 'auto_passed', 'waived', 'submitted'].includes(r.status)).length;
  const progress = totalReqs > 0 ? Math.round((completedReqs / totalReqs) * 100) : 0;

  const caseStatus = c.status;
  const isSubmitted = ['customer_submitted', 'automated_checks', 'maker_review', 'checker_review', 'business_approval', 'compliance_approval', 'mlro_approval', 'completed'].includes(caseStatus);

  // Group requirements by party
  const partyMap = {};
  parties.forEach(p => { partyMap[p.id] = p; });
  const reqsByParty = {};
  docReqs.forEach(r => {
    const pid = r.party_id || 'general';
    if (!reqsByParty[pid]) reqsByParty[pid] = [];
    reqsByParty[pid].push(r);
  });

  return (
    <TooltipProvider>
      <div data-testid="customer-dashboard">
        <input type="file" ref={fileRef} className="hidden" onChange={onFileSelected} accept=".pdf,.jpg,.jpeg,.png" />

        <div className="mb-6">
          <h1 className="text-2xl font-semibold tracking-tight font-['IBM_Plex_Sans']">Your KYC Checklist</h1>
          <p className="text-sm text-[#64748B] mt-1">Case: <span className="font-['JetBrains_Mono']">{c.case_ref}</span></p>
        </div>

        {/* Progress Card */}
        <Card className="border-[#E2E8F0] mb-6">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="text-sm font-medium">Overall Progress</p>
                <Badge className={`mt-1 ${isSubmitted ? 'bg-green-100 text-green-700' : caseStatus === 'completed' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'} border-transparent capitalize`}>
                  {caseStatus?.replace(/_/g, ' ')}
                </Badge>
              </div>
              <div className="text-right">
                <p className="text-2xl font-semibold font-['JetBrains_Mono']">{completedReqs}/{totalReqs}</p>
                <p className="text-xs text-[#64748B]">items completed</p>
              </div>
            </div>
            <div className="w-full h-2 bg-gray-200 rounded-full">
              <div className="h-2 bg-[#0F172A] rounded-full transition-all duration-500" style={{ width: `${progress}%` }} />
            </div>
          </CardContent>
        </Card>

        {/* Questionnaire CTA */}
        {!questionnaire?.completed_at && !isSubmitted && (
          <Card className="border-[#E2E8F0] border-l-4 border-l-blue-500 mb-6">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">Step 1: Complete Your Questionnaire</p>
                  <p className="text-xs text-[#64748B] mt-1">Provide entity details and identify relevant parties</p>
                </div>
                <Button size="sm" onClick={() => navigate('/portal/questionnaire')} data-testid="start-questionnaire-btn">
                  Start <ArrowRight size={14} className="ml-1" />
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Document Requirements grouped by Party */}
        <h2 className="text-lg font-medium font-['IBM_Plex_Sans'] mb-3">
          {questionnaire?.completed_at ? 'Step 2: Upload Documents' : 'Required Documents'}
        </h2>

        {Object.entries(reqsByParty).map(([partyId, reqs]) => {
          const party = partyMap[partyId];
          const partyName = party ? (party.legal_name || `${party.first_name} ${party.last_name}`.trim()) : 'General';
          const partyType = party?.party_type || '';
          const partyRole = party?.role_in_case || '';

          return (
            <div key={partyId} className="mb-6">
              <div className="flex items-center gap-2 mb-2">
                <h3 className="text-sm font-semibold text-[#0F172A]">{partyName}</h3>
                {partyRole && <Badge variant="outline" className="text-[10px] capitalize">{partyRole}</Badge>}
                {partyType && <Badge variant="outline" className="text-[10px]">{partyType.replace(/_/g,' ')}</Badge>}
              </div>
              <div className="space-y-2">
                {reqs.map(r => {
                  const Icon = STATUS_ICONS[r.status] || Circle;
                  const doc = documents.find(d => d.requirement_item_id === r.id);
                  const helpText = REQUIREMENT_HELP[r.requirement_key] || `Please provide: ${r.requirement_label || r.requirement_key}`;

                  return (
                    <Card key={r.id} className={`border-[#E2E8F0] ${r.status === 'rejected' ? 'border-l-2 border-l-red-500' : r.status === 'auto_passed' || r.status === 'approved' ? 'border-l-2 border-l-green-500' : ''}`}>
                      <CardContent className="p-3">
                        <div className="flex items-center gap-3">
                          <Icon size={18} className={STATUS_COLORS[r.status]} />
                          <div className="flex-1">
                            <div className="flex items-center gap-1.5">
                              <p className="text-sm font-medium">{r.requirement_label || r.requirement_key}</p>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <button className="w-4 h-4 rounded-full bg-[#E2E8F0] flex items-center justify-center hover:bg-[#CBD5E1] transition-colors" data-testid={`help-${r.requirement_key}`}>
                                    <HelpCircle size={10} className="text-[#64748B]" />
                                  </button>
                                </TooltipTrigger>
                                <TooltipContent side="right" className="max-w-xs text-xs">
                                  {helpText}
                                </TooltipContent>
                              </Tooltip>
                            </div>
                            <div className="flex items-center gap-2 mt-0.5">
                              <Badge className={`${STATUS_BG[r.status]} border-transparent text-[10px]`}>{r.status?.replace(/_/g,' ')}</Badge>
                            </div>
                            {doc && <p className="text-xs text-[#64748B] mt-1 flex items-center gap-1"><FileText size={10} /> {doc.original_filename}</p>}
                            {r.status === 'rejected' && (
                              <p className="text-xs text-red-600 mt-1 flex items-center gap-1">
                                <AlertCircle size={10} /> {r.notes || 'Document was rejected. Please re-upload a valid document.'}
                              </p>
                            )}
                            {r.status === 'auto_passed' && r.notes?.includes('Auto-satisfied') && (
                              <p className="text-xs text-green-600 mt-1 flex items-center gap-1">
                                <CheckCircle size={10} /> {r.notes}
                              </p>
                            )}
                          </div>
                          {!isSubmitted && !['approved', 'auto_passed', 'waived'].includes(r.status) && (
                            <Button size="sm" variant="outline" onClick={() => handleUpload(r.id, r.requirement_key)} disabled={uploading === r.id} data-testid={`upload-${r.id}`}>
                              <Upload size={14} className="mr-1" /> {uploading === r.id ? 'Uploading...' : r.status === 'rejected' ? 'Re-upload' : 'Upload'}
                            </Button>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>
          );
        })}

        {/* Automated checks */}
        {autoReqs.length > 0 && (
          <>
            <h2 className="text-lg font-medium font-['IBM_Plex_Sans'] mb-3 mt-6">Automated Checks</h2>
            <div className="space-y-2 mb-6">
              {autoReqs.map(r => {
                const Icon = STATUS_ICONS[r.status] || Circle;
                return (
                  <Card key={r.id} className="border-[#E2E8F0]">
                    <CardContent className="p-3 flex items-center gap-3">
                      <Icon size={18} className={STATUS_COLORS[r.status]} />
                      <div className="flex-1">
                        <p className="text-sm">{r.requirement_label || r.requirement_key}</p>
                        <Badge className={`${STATUS_BG[r.status]} border-transparent text-[10px] mt-0.5`}>{r.status?.replace(/_/g,' ')}</Badge>
                      </div>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button className="w-4 h-4 rounded-full bg-[#E2E8F0] flex items-center justify-center">
                            <HelpCircle size={10} className="text-[#64748B]" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent side="left" className="max-w-xs text-xs">
                          {REQUIREMENT_HELP[r.requirement_key] || 'This check is performed automatically.'}
                        </TooltipContent>
                      </Tooltip>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </>
        )}

        {/* Video Ident */}
        {videoReqs.length > 0 && (
          <>
            <h2 className="text-lg font-medium font-['IBM_Plex_Sans'] mb-3 mt-6">Video Identification</h2>
            <div className="space-y-2 mb-6">
              {videoReqs.map(r => {
                const Icon = STATUS_ICONS[r.status] || Circle;
                return (
                  <Card key={r.id} className="border-[#E2E8F0]">
                    <CardContent className="p-3 flex items-center gap-3">
                      <Icon size={18} className={STATUS_COLORS[r.status]} />
                      <div className="flex-1">
                        <p className="text-sm">{r.requirement_label || r.requirement_key}</p>
                        <Badge className={`${STATUS_BG[r.status]} border-transparent text-[10px] mt-0.5`}>{r.status?.replace(/_/g,' ')}</Badge>
                        <p className="text-xs text-[#64748B] mt-1">You will be contacted to schedule a video verification session.</p>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </>
        )}

        {/* Submit */}
        {!isSubmitted && (
          <Button className="w-full bg-[#0F172A] hover:bg-[#1E293B] mt-4" onClick={handleSubmit} data-testid="submit-case-btn">
            Submit for Review
          </Button>
        )}

        {caseStatus === 'completed' && (
          <Card className="border-[#E2E8F0] border-l-4 border-l-green-500 mt-4">
            <CardContent className="p-6 text-center">
              <CheckCircle size={40} className="mx-auto text-green-500 mb-3" />
              <p className="text-lg font-medium text-green-700">Onboarding Complete</p>
              <p className="text-sm text-[#64748B] mt-1">Your KYC review has been approved. Thank you.</p>
            </CardContent>
          </Card>
        )}

        {isSubmitted && caseStatus !== 'completed' && (
          <Card className="border-[#E2E8F0] border-l-4 border-l-blue-500 mt-4">
            <CardContent className="p-6 text-center">
              <Clock size={40} className="mx-auto text-blue-500 mb-3" />
              <p className="text-lg font-medium text-blue-700">Under Review</p>
              <p className="text-sm text-[#64748B] mt-1">Your documents are being reviewed by our compliance team. We'll notify you of any updates.</p>
            </CardContent>
          </Card>
        )}
      </div>
    </TooltipProvider>
  );
}
