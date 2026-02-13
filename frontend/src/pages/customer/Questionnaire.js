import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ArrowLeft, ArrowRight, CheckCircle, Plus, Trash2 } from 'lucide-react';
import api from '@/api/client';

const ENTITY_TYPES = [
  { value: 'legal_entity', label: 'Company / Legal Entity' },
  { value: 'natural_person', label: 'Individual / Natural Person' },
  { value: 'trust', label: 'Trust' },
  { value: 'foundation', label: 'Foundation' },
];

const STEPS = ['entity_type', 'basic_info', 'ubos', 'review'];

export default function Questionnaire() {
  const navigate = useNavigate();
  const [session, setSession] = useState(null);
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState({
    entity_type: 'legal_entity',
    company_name: '', legal_name: '', jurisdiction: 'EU',
    first_name: '', last_name: '', dob: '', nationality: '',
    address_street: '', address_city: '', address_country: '',
    ubos: [{ first_name: '', last_name: '', dob: '', nationality: '', ownership_percent: '' }]
  });
  const [loading, setLoading] = useState(false);

  const caseRef = localStorage.getItem('ddys_customer_case_ref');
  const tenantId = localStorage.getItem('ddys_customer_tenant');

  useEffect(() => {
    // Load existing case to get case_id
    const params = new URLSearchParams();
    if (caseRef) params.set('case_ref', caseRef);
    if (tenantId) params.set('tenant_id', tenantId);
    api.get(`/customer/case?${params}`).then(r => {
      if (r.data?.case?.id) {
        // Start or resume questionnaire
        api.post('/customer/questionnaire/start', { case_id: r.data.case.id }).then(s => {
          setSession(s.data);
          if (s.data.answers_json && Object.keys(s.data.answers_json).length > 0) {
            setAnswers(prev => ({ ...prev, ...s.data.answers_json }));
          }
        });
      }
    }).catch(console.error);
  }, []);

  const handleNext = async () => {
    if (session) {
      await api.put(`/customer/questionnaire/${session.id}`, {
        current_step: STEPS[step + 1] || 'review',
        answers_json: answers,
        entity_type_determined: answers.entity_type
      });
    }
    setStep(s => Math.min(s + 1, STEPS.length - 1));
  };

  const handleBack = () => setStep(s => Math.max(s - 1, 0));

  const handleComplete = async () => {
    setLoading(true);
    try {
      if (session) {
        await api.put(`/customer/questionnaire/${session.id}`, { answers_json: answers, entity_type_determined: answers.entity_type });
        await api.post(`/customer/questionnaire/${session.id}/complete`);
      }
      navigate('/portal/dashboard');
    } catch (err) { alert(err.response?.data?.detail || 'Failed to complete'); }
    finally { setLoading(false); }
  };

  const addUbo = () => setAnswers({ ...answers, ubos: [...answers.ubos, { first_name: '', last_name: '', dob: '', nationality: '', ownership_percent: '' }] });
  const removeUbo = (i) => setAnswers({ ...answers, ubos: answers.ubos.filter((_, idx) => idx !== i) });
  const updateUbo = (i, field, val) => {
    const ubos = [...answers.ubos];
    ubos[i] = { ...ubos[i], [field]: val };
    setAnswers({ ...answers, ubos });
  };

  return (
    <div data-testid="questionnaire">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight font-['IBM_Plex_Sans']">KYC Questionnaire</h1>
        <p className="text-sm text-[#64748B] mt-1">Step {step + 1} of {STEPS.length}</p>
        <div className="flex gap-1 mt-3">
          {STEPS.map((_, i) => <div key={i} className={`h-1 flex-1 rounded-full ${i <= step ? 'bg-[#0F172A]' : 'bg-gray-200'}`} />)}
        </div>
      </div>

      {step === 0 && (
        <Card className="border-[#E2E8F0]">
          <CardHeader><CardTitle className="text-base font-['IBM_Plex_Sans']">What type of entity are you?</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {ENTITY_TYPES.map(et => (
              <button
                key={et.value}
                onClick={() => setAnswers({ ...answers, entity_type: et.value })}
                className={`w-full text-left p-4 rounded-md border transition-colors ${answers.entity_type === et.value ? 'border-[#0F172A] bg-[#F1F5F9]' : 'border-[#E2E8F0] hover:bg-[#F8FAFC]'}`}
                data-testid={`entity-type-${et.value}`}
              >
                <span className="text-sm font-medium">{et.label}</span>
              </button>
            ))}
          </CardContent>
        </Card>
      )}

      {step === 1 && (
        <Card className="border-[#E2E8F0]">
          <CardHeader><CardTitle className="text-base font-['IBM_Plex_Sans']">Basic Information</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            {answers.entity_type === 'legal_entity' ? (
              <>
                <div>
                  <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Company Name</Label>
                  <Input className="mt-1.5" value={answers.company_name} onChange={e => setAnswers({...answers, company_name: e.target.value})} data-testid="company-name" />
                </div>
                <div>
                  <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Jurisdiction</Label>
                  <Input className="mt-1.5" value={answers.jurisdiction} onChange={e => setAnswers({...answers, jurisdiction: e.target.value})} data-testid="jurisdiction" />
                </div>
              </>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">First Name</Label>
                    <Input className="mt-1.5" value={answers.first_name} onChange={e => setAnswers({...answers, first_name: e.target.value})} />
                  </div>
                  <div>
                    <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Last Name</Label>
                    <Input className="mt-1.5" value={answers.last_name} onChange={e => setAnswers({...answers, last_name: e.target.value})} />
                  </div>
                </div>
                <div>
                  <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Date of Birth</Label>
                  <Input className="mt-1.5" type="date" value={answers.dob} onChange={e => setAnswers({...answers, dob: e.target.value})} />
                </div>
                <div>
                  <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Nationality</Label>
                  <Input className="mt-1.5" value={answers.nationality} onChange={e => setAnswers({...answers, nationality: e.target.value})} placeholder="e.g. DE" />
                </div>
              </>
            )}
            <div>
              <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Address</Label>
              <Input className="mt-1.5" value={answers.address_street} onChange={e => setAnswers({...answers, address_street: e.target.value})} placeholder="Street" />
              <div className="grid grid-cols-2 gap-4 mt-2">
                <Input value={answers.address_city} onChange={e => setAnswers({...answers, address_city: e.target.value})} placeholder="City" />
                <Input value={answers.address_country} onChange={e => setAnswers({...answers, address_country: e.target.value})} placeholder="Country" />
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {step === 2 && (
        <Card className="border-[#E2E8F0]">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base font-['IBM_Plex_Sans']">Ultimate Beneficial Owners (UBOs)</CardTitle>
              <Button size="sm" variant="outline" onClick={addUbo} data-testid="add-ubo-btn"><Plus size={14} className="mr-1" /> Add UBO</Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {answers.ubos.map((ubo, i) => (
              <div key={i} className="p-3 border border-[#E2E8F0] rounded-md space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-[#64748B]">UBO #{i+1}</span>
                  {answers.ubos.length > 1 && <button onClick={() => removeUbo(i)} className="text-red-400 hover:text-red-600"><Trash2 size={14} /></button>}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <Input placeholder="First Name" value={ubo.first_name} onChange={e => updateUbo(i, 'first_name', e.target.value)} data-testid={`ubo-${i}-first-name`} />
                  <Input placeholder="Last Name" value={ubo.last_name} onChange={e => updateUbo(i, 'last_name', e.target.value)} data-testid={`ubo-${i}-last-name`} />
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <Input type="date" placeholder="DOB" value={ubo.dob} onChange={e => updateUbo(i, 'dob', e.target.value)} />
                  <Input placeholder="Nationality" value={ubo.nationality} onChange={e => updateUbo(i, 'nationality', e.target.value)} />
                  <Input placeholder="Ownership %" type="number" value={ubo.ownership_percent} onChange={e => updateUbo(i, 'ownership_percent', e.target.value)} />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {step === 3 && (
        <Card className="border-[#E2E8F0]">
          <CardHeader><CardTitle className="text-base font-['IBM_Plex_Sans']">Review & Submit</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="p-3 bg-[#F8FAFC] rounded-md">
              <p className="text-xs text-[#64748B] uppercase font-semibold">Entity Type</p>
              <p className="text-sm capitalize">{answers.entity_type?.replace(/_/g, ' ')}</p>
            </div>
            <div className="p-3 bg-[#F8FAFC] rounded-md">
              <p className="text-xs text-[#64748B] uppercase font-semibold">Name</p>
              <p className="text-sm">{answers.company_name || `${answers.first_name} ${answers.last_name}`}</p>
            </div>
            <div className="p-3 bg-[#F8FAFC] rounded-md">
              <p className="text-xs text-[#64748B] uppercase font-semibold">UBOs</p>
              {answers.ubos.map((u, i) => <p key={i} className="text-sm">{u.first_name} {u.last_name} ({u.ownership_percent}%)</p>)}
            </div>
            <p className="text-xs text-[#64748B]">By submitting, you confirm the information provided is accurate. You will be asked to upload supporting documents next.</p>
          </CardContent>
        </Card>
      )}

      <div className="flex justify-between mt-6">
        <Button variant="outline" onClick={step === 0 ? () => navigate('/portal/dashboard') : handleBack} data-testid="questionnaire-back">
          <ArrowLeft size={14} className="mr-1" /> Back
        </Button>
        {step < STEPS.length - 1 ? (
          <Button className="bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleNext} data-testid="questionnaire-next">
            Next <ArrowRight size={14} className="ml-1" />
          </Button>
        ) : (
          <Button className="bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleComplete} disabled={loading} data-testid="questionnaire-submit">
            <CheckCircle size={14} className="mr-1" /> {loading ? 'Submitting...' : 'Complete Questionnaire'}
          </Button>
        )}
      </div>
    </div>
  );
}
