import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Shield, Building2, User, CheckCircle, ArrowRight, ArrowLeft } from 'lucide-react';
import api from '@/api/client';

export default function IntakeForm() {
  const [step, setStep] = useState(1);
  const [submitted, setSubmitted] = useState(false);
  const [reference, setReference] = useState('');
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    client_type: 'legal_entity',
    company_name: '', legal_name: '', first_name: '', last_name: '',
    email: '', phone: '', address: '', city: '', country: '', nationality: '',
    registration_number: '',
    bank_name: '', bank_address: '', bank_country: '', bank_reference: '',
    product_requested: '', notes: ''
  });

  const set = (key, val) => setForm(prev => ({ ...prev, [key]: val }));

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const res = await api.post('/intake/submit', form);
      setReference(res.data.reference);
      setSubmitted(true);
    } catch (err) { alert(err.response?.data?.detail || 'Submission failed'); }
    finally { setLoading(false); }
  };

  if (submitted) {
    return (
      <div className="min-h-screen bg-[#F8FAFC] flex items-center justify-center p-4">
        <Card className="w-full max-w-md border-[#E2E8F0] shadow-sm">
          <CardContent className="p-8 text-center">
            <CheckCircle size={48} className="mx-auto text-green-500 mb-4" />
            <h2 className="text-xl font-semibold font-['IBM_Plex_Sans'] mb-2">Request Submitted</h2>
            <p className="text-sm text-[#64748B] mb-4">Your KYC onboarding request has been received. Our compliance team will review it and send you an invitation link.</p>
            <div className="p-3 bg-[#F1F5F9] rounded-md">
              <p className="text-xs text-[#64748B]">Your Reference</p>
              <p className="text-lg font-bold font-['JetBrains_Mono']">{reference}</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F8FAFC]" data-testid="intake-form">
      <header className="h-14 bg-white border-b border-[#E2E8F0] flex items-center px-6">
        <Shield size={18} className="text-[#0F172A] mr-2" />
        <span className="text-sm font-semibold font-['IBM_Plex_Sans']">DDYs</span>
        <span className="text-sm text-[#64748B] ml-2">KYC Onboarding Request</span>
      </header>

      <div className="max-w-2xl mx-auto py-8 px-4">
        {/* Progress */}
        <div className="flex items-center gap-2 mb-6">
          {[1, 2, 3].map(s => (
            <div key={s} className="flex items-center gap-2 flex-1">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${step >= s ? 'bg-[#0F172A] text-white' : 'bg-[#E2E8F0] text-[#64748B]'}`}>{s}</div>
              <span className={`text-xs ${step >= s ? 'font-medium' : 'text-[#64748B]'}`}>{['Your Details', 'Bank Details', 'Review'][s-1]}</span>
              {s < 3 && <div className={`flex-1 h-0.5 ${step > s ? 'bg-[#0F172A]' : 'bg-[#E2E8F0]'}`} />}
            </div>
          ))}
        </div>

        {/* Step 1: Client Details */}
        {step === 1 && (
          <Card className="border-[#E2E8F0]">
            <CardHeader><CardTitle className="text-lg font-['IBM_Plex_Sans']">Your Details</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">I am a</Label>
                <div className="flex gap-3 mt-1.5">
                  {[{v: 'legal_entity', l: 'Company', i: Building2}, {v: 'natural_person', l: 'Individual', i: User}].map(({v, l, i: Icon}) => (
                    <button key={v} onClick={() => set('client_type', v)} className={`flex-1 p-3 rounded-lg border-2 transition-colors text-center ${form.client_type === v ? 'border-[#0F172A] bg-[#F1F5F9]' : 'border-[#E2E8F0]'}`} data-testid={`type-${v}`}>
                      <Icon size={20} className="mx-auto mb-1" /><span className="text-sm">{l}</span>
                    </button>
                  ))}
                </div>
              </div>
              {form.client_type === 'legal_entity' ? (
                <>
                  <div><Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Company Name</Label><Input className="mt-1.5" value={form.company_name} onChange={e => set('company_name', e.target.value)} placeholder="Acme Trading GmbH" data-testid="company-name" /></div>
                  <div><Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Registration Number</Label><Input className="mt-1.5" value={form.registration_number} onChange={e => set('registration_number', e.target.value)} placeholder="HRB 123456" /></div>
                </>
              ) : (
                <div className="grid grid-cols-2 gap-3">
                  <div><Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">First Name</Label><Input className="mt-1.5" value={form.first_name} onChange={e => set('first_name', e.target.value)} /></div>
                  <div><Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Last Name</Label><Input className="mt-1.5" value={form.last_name} onChange={e => set('last_name', e.target.value)} /></div>
                </div>
              )}
              <div className="grid grid-cols-2 gap-3">
                <div><Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Email</Label><Input className="mt-1.5" type="email" value={form.email} onChange={e => set('email', e.target.value)} placeholder="your@email.com" data-testid="email" /></div>
                <div><Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Phone</Label><Input className="mt-1.5" value={form.phone} onChange={e => set('phone', e.target.value)} placeholder="+49..." /></div>
              </div>
              <div><Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Address</Label><Input className="mt-1.5" value={form.address} onChange={e => set('address', e.target.value)} placeholder="Street and number" /></div>
              <div className="grid grid-cols-3 gap-3">
                <div><Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">City</Label><Input className="mt-1.5" value={form.city} onChange={e => set('city', e.target.value)} /></div>
                <div><Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Country</Label><Input className="mt-1.5" value={form.country} onChange={e => set('country', e.target.value)} placeholder="DE" /></div>
                <div><Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Nationality</Label><Input className="mt-1.5" value={form.nationality} onChange={e => set('nationality', e.target.value)} placeholder="DE" /></div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Step 2: Bank Details */}
        {step === 2 && (
          <Card className="border-[#E2E8F0]">
            <CardHeader><CardTitle className="text-lg font-['IBM_Plex_Sans']">Which bank is this for?</CardTitle>
              <p className="text-sm text-[#64748B]">Tell us which financial institution you need the KYC onboarding for.</p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div><Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Bank / Institution Name</Label><Input className="mt-1.5" value={form.bank_name} onChange={e => set('bank_name', e.target.value)} placeholder="e.g. Demo Bank AG" data-testid="bank-name" /></div>
              <div><Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Bank Address</Label><Input className="mt-1.5" value={form.bank_address} onChange={e => set('bank_address', e.target.value)} placeholder="Bank street address" /></div>
              <div className="grid grid-cols-2 gap-3">
                <div><Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Bank Country</Label><Input className="mt-1.5" value={form.bank_country} onChange={e => set('bank_country', e.target.value)} placeholder="DE" /></div>
                <div><Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Reference / Account Nr.</Label><Input className="mt-1.5" value={form.bank_reference} onChange={e => set('bank_reference', e.target.value)} placeholder="Optional" /></div>
              </div>
              <div><Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Product / Service Requested</Label><Input className="mt-1.5" value={form.product_requested} onChange={e => set('product_requested', e.target.value)} placeholder="e.g. Corporate Banking, Custody, Payment Account" /></div>
              <div><Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Additional Notes</Label><Textarea className="mt-1.5" value={form.notes} onChange={e => set('notes', e.target.value)} placeholder="Any additional information..." rows={3} /></div>
            </CardContent>
          </Card>
        )}

        {/* Step 3: Review */}
        {step === 3 && (
          <Card className="border-[#E2E8F0]">
            <CardHeader><CardTitle className="text-lg font-['IBM_Plex_Sans']">Review & Submit</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="p-3 bg-[#F8FAFC] rounded-md">
                <p className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B] mb-1">{form.client_type === 'legal_entity' ? 'Company' : 'Individual'}</p>
                <p className="text-sm font-semibold">{form.company_name || `${form.first_name} ${form.last_name}`}</p>
                <p className="text-xs text-[#64748B]">{form.email} | {form.phone}</p>
                <p className="text-xs text-[#64748B]">{[form.address, form.city, form.country].filter(Boolean).join(', ')}</p>
              </div>
              <div className="p-3 bg-blue-50 rounded-md border border-blue-200">
                <p className="text-[10px] uppercase tracking-wider font-semibold text-blue-700 mb-1">Bank / Institution</p>
                <p className="text-sm font-semibold">{form.bank_name || 'Not specified'}</p>
                <p className="text-xs text-[#64748B]">{[form.bank_address, form.bank_country].filter(Boolean).join(', ')}</p>
                {form.product_requested && <p className="text-xs text-[#64748B]">Product: {form.product_requested}</p>}
              </div>
              <p className="text-xs text-[#64748B]">By submitting, you confirm the information is accurate. Our compliance team will review and contact you.</p>
            </CardContent>
          </Card>
        )}

        {/* Navigation */}
        <div className="flex justify-between mt-6">
          {step > 1 ? (
            <Button variant="outline" onClick={() => setStep(s => s - 1)}><ArrowLeft size={14} className="mr-1" /> Back</Button>
          ) : <div />}
          {step < 3 ? (
            <Button className="bg-[#0F172A] hover:bg-[#1E293B]" onClick={() => setStep(s => s + 1)} data-testid="next-step">
              Next <ArrowRight size={14} className="ml-1" />
            </Button>
          ) : (
            <Button className="bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleSubmit} disabled={loading} data-testid="submit-intake">
              {loading ? 'Submitting...' : 'Submit Request'} <CheckCircle size={14} className="ml-1" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
