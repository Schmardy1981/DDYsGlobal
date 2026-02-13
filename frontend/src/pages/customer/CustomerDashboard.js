import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { CheckCircle, Circle, Upload, FileText, AlertCircle, Clock, ArrowRight } from 'lucide-react';
import api from '@/api/client';

const STATUS_ICONS = {
  missing: Circle, submitted: Clock, auto_passed: CheckCircle, needs_review: Clock, approved: CheckCircle, waived: CheckCircle, rejected: AlertCircle
};
const STATUS_COLORS = {
  missing: 'text-gray-400', submitted: 'text-blue-500', auto_passed: 'text-green-500', needs_review: 'text-amber-500', approved: 'text-green-500', waived: 'text-purple-500', rejected: 'text-red-500'
};
const STATUS_BG = {
  missing: 'bg-gray-100 text-gray-700', submitted: 'bg-blue-100 text-blue-700', auto_passed: 'bg-green-100 text-green-700', needs_review: 'bg-amber-100 text-amber-700', approved: 'bg-green-100 text-green-700', waived: 'bg-purple-100 text-purple-700', rejected: 'bg-red-100 text-red-700'
};

export default function CustomerDashboard() {
  const navigate = useNavigate();
  const [caseData, setCaseData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(null);
  const fileRef = useRef(null);
  const [selectedReq, setSelectedReq] = useState(null);

  const caseRef = localStorage.getItem('ddys_customer_case_ref');
  const tenantId = localStorage.getItem('ddys_customer_tenant');

  useEffect(() => { loadCase(); }, []);

  const loadCase = () => {
    const params = new URLSearchParams();
    if (caseRef) params.set('case_ref', caseRef);
    if (tenantId) params.set('tenant_id', tenantId);
    api.get(`/customer/case?${params}`).then(r => setCaseData(r.data)).catch(e => {
      console.error(e);
      setCaseData(null);
    }).finally(() => setLoading(false));
  };

  const handleUpload = async (reqId, reqKey) => {
    setSelectedReq(reqId);
    fileRef.current?.click();
  };

  const onFileSelected = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !selectedReq) return;
    setUploading(selectedReq);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('case_id', caseData.case.id);
    formData.append('tenant_id', tenantId);
    formData.append('requirement_item_id', selectedReq);
    formData.append('doc_type', 'other');

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
      <p className="text-sm text-[#64748B] mb-4">No case found for the provided reference.</p>
      <Button onClick={() => navigate('/portal')} data-testid="back-to-portal">Back to Portal</Button>
    </div>
  );

  const { case: c, requirements, documents, parties, questionnaire } = caseData;
  const docReqs = requirements.filter(r => !['sanctions', 'pep', 'adverse_media', 'video_ident'].includes(r.requirement_category));
  const autoReqs = requirements.filter(r => ['sanctions', 'pep', 'adverse_media'].includes(r.requirement_category));
  const totalReqs = docReqs.length;
  const completedReqs = docReqs.filter(r => ['approved', 'auto_passed', 'waived', 'submitted'].includes(r.status)).length;
  const progress = totalReqs > 0 ? Math.round((completedReqs / totalReqs) * 100) : 0;

  const caseStatus = c.status;
  const isSubmitted = ['customer_submitted', 'automated_checks', 'maker_review', 'checker_review', 'business_approval', 'compliance_approval', 'mlro_approval', 'completed'].includes(caseStatus);

  return (
    <div data-testid="customer-dashboard">
      <input type="file" ref={fileRef} className="hidden" onChange={onFileSelected} accept=".pdf,.jpg,.jpeg,.png" />

      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight font-['IBM_Plex_Sans']">Your KYC Checklist</h1>
        <p className="text-sm text-[#64748B] mt-1">Case: <span className="font-['JetBrains_Mono']">{c.case_ref}</span></p>
      </div>

      {/* Status Card */}
      <Card className="border-[#E2E8F0] mb-6">
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Overall Status</p>
              <Badge className={`mt-1 ${isSubmitted ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'} border-transparent capitalize`}>
                {caseStatus?.replace(/_/g, ' ')}
              </Badge>
            </div>
            <div className="text-right">
              <p className="text-sm font-medium">{completedReqs}/{totalReqs} items completed</p>
              <div className="w-32 h-2 bg-gray-200 rounded-full mt-2">
                <div className="h-2 bg-[#0F172A] rounded-full transition-all" style={{ width: `${progress}%` }} />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Questionnaire */}
      {!questionnaire?.completed_at && !isSubmitted && (
        <Card className="border-[#E2E8F0] border-l-4 border-l-blue-500 mb-6">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">Complete Your Questionnaire</p>
                <p className="text-xs text-[#64748B] mt-1">Provide your entity details and relevant parties</p>
              </div>
              <Button size="sm" onClick={() => navigate('/portal/questionnaire')} data-testid="start-questionnaire-btn">
                Start <ArrowRight size={14} className="ml-1" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Document Requirements */}
      <h2 className="text-lg font-medium font-['IBM_Plex_Sans'] mb-3">Document Requirements</h2>
      <div className="space-y-2 mb-6">
        {docReqs.map(r => {
          const Icon = STATUS_ICONS[r.status] || Circle;
          const doc = documents.find(d => d.requirement_item_id === r.id);
          const partyName = parties.find(p => p.id === r.party_id);
          const name = partyName ? (partyName.legal_name || `${partyName.first_name} ${partyName.last_name}`) : '';

          return (
            <Card key={r.id} className="border-[#E2E8F0]">
              <CardContent className="p-3">
                <div className="flex items-center gap-3">
                  <Icon size={18} className={STATUS_COLORS[r.status]} />
                  <div className="flex-1">
                    <p className="text-sm font-medium">{r.requirement_label || r.requirement_key}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      {name && <span className="text-xs text-[#64748B]">{name}</span>}
                      <Badge className={`${STATUS_BG[r.status]} border-transparent text-[10px]`}>{r.status?.replace(/_/g,' ')}</Badge>
                    </div>
                    {doc && <p className="text-xs text-[#64748B] mt-1 flex items-center gap-1"><FileText size={10} /> {doc.original_filename}</p>}
                    {r.status === 'rejected' && <p className="text-xs text-red-600 mt-1">{r.notes || 'Document was rejected. Please re-upload.'}</p>}
                  </div>
                  {!isSubmitted && r.status !== 'approved' && r.status !== 'auto_passed' && r.status !== 'waived' && (
                    <Button size="sm" variant="outline" onClick={() => handleUpload(r.id, r.requirement_key)} disabled={uploading === r.id} data-testid={`upload-${r.id}`}>
                      <Upload size={14} className="mr-1" /> {uploading === r.id ? 'Uploading...' : 'Upload'}
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Auto checks */}
      {autoReqs.length > 0 && (
        <>
          <h2 className="text-lg font-medium font-['IBM_Plex_Sans'] mb-3">Automated Checks</h2>
          <div className="space-y-2 mb-6">
            {autoReqs.map(r => {
              const Icon = STATUS_ICONS[r.status] || Circle;
              return (
                <Card key={r.id} className="border-[#E2E8F0]">
                  <CardContent className="p-3 flex items-center gap-3">
                    <Icon size={18} className={STATUS_COLORS[r.status]} />
                    <div>
                      <p className="text-sm">{r.requirement_label || r.requirement_key}</p>
                      <Badge className={`${STATUS_BG[r.status]} border-transparent text-[10px] mt-0.5`}>{r.status?.replace(/_/g,' ')}</Badge>
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
        <Button className="w-full bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleSubmit} data-testid="submit-case-btn">
          Submit for Review
        </Button>
      )}

      {isSubmitted && caseStatus === 'completed' && (
        <Card className="border-[#E2E8F0] border-l-4 border-l-green-500">
          <CardContent className="p-4 text-center">
            <CheckCircle size={32} className="mx-auto text-green-500 mb-2" />
            <p className="text-lg font-medium text-green-700">Onboarding Complete</p>
            <p className="text-sm text-[#64748B]">Your KYC review has been approved.</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
