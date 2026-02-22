import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Shield, Building2, User, CheckCircle, ArrowRight, ArrowLeft, HelpCircle, AlertCircle, Phone, Mail } from 'lucide-react';
import api from '@/api/client';

const COUNTRY_CODES = [
  { code: '+49', flag: 'DE', label: 'Germany' }, { code: '+41', flag: 'CH', label: 'Switzerland' },
  { code: '+43', flag: 'AT', label: 'Austria' }, { code: '+423', flag: 'LI', label: 'Liechtenstein' },
  { code: '+44', flag: 'UK', label: 'United Kingdom' }, { code: '+1', flag: 'US', label: 'United States' },
  { code: '+33', flag: 'FR', label: 'France' }, { code: '+39', flag: 'IT', label: 'Italy' },
  { code: '+34', flag: 'ES', label: 'Spain' }, { code: '+31', flag: 'NL', label: 'Netherlands' },
  { code: '+352', flag: 'LU', label: 'Luxembourg' }, { code: '+32', flag: 'BE', label: 'Belgium' },
  { code: '+353', flag: 'IE', label: 'Ireland' }, { code: '+46', flag: 'SE', label: 'Sweden' },
  { code: '+47', flag: 'NO', label: 'Norway' }, { code: '+45', flag: 'DK', label: 'Denmark' },
  { code: '+358', flag: 'FI', label: 'Finland' }, { code: '+48', flag: 'PL', label: 'Poland' },
  { code: '+420', flag: 'CZ', label: 'Czech Republic' }, { code: '+351', flag: 'PT', label: 'Portugal' },
  { code: '+30', flag: 'GR', label: 'Greece' }, { code: '+971', flag: 'AE', label: 'UAE' },
  { code: '+65', flag: 'SG', label: 'Singapore' }, { code: '+852', flag: 'HK', label: 'Hong Kong' },
  { code: '+81', flag: 'JP', label: 'Japan' },
];

const COUNTRIES = [
  'Germany', 'Switzerland', 'Austria', 'Liechtenstein', 'United Kingdom', 'United States',
  'France', 'Italy', 'Spain', 'Netherlands', 'Luxembourg', 'Belgium', 'Ireland',
  'Sweden', 'Norway', 'Denmark', 'Finland', 'Poland', 'Czech Republic', 'Portugal',
  'Greece', 'UAE', 'Singapore', 'Hong Kong', 'Japan', 'Other'
];

export default function IntakeForm({ previewMode = false }) {
  const [step, setStep] = useState(1);
  const [submitted, setSubmitted] = useState(false);
  const [reference, setReference] = useState('');
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});
  const [form, setForm] = useState({
    client_type: 'legal_entity',
    company_name: '', legal_name: '', first_name: '', last_name: '',
    email: '', confirm_email: '',
    phone_code: '+49', phone_number: '',
    mobile_code: '+49', mobile_number: '',
    street: '', street_number: '', postal_code: '', city: '', country: '',
    nationality: '', registration_number: '',
    bank_name: '', bank_street: '', bank_city: '', bank_country: '', bank_reference: '',
    product_requested: '', notes: ''
  });

  const set = (key, val) => { setForm(prev => ({ ...prev, [key]: val })); setErrors(prev => ({ ...prev, [key]: '' })); };

  const validateStep1 = () => {
    const errs = {};
    if (form.client_type === 'legal_entity') {
      if (!form.company_name.trim()) errs.company_name = 'Company name is required';
    } else {
      if (!form.first_name.trim()) errs.first_name = 'First name is required';
      if (!form.last_name.trim()) errs.last_name = 'Last name is required';
    }
    if (!form.email.trim()) errs.email = 'Email is required';
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) errs.email = 'Please enter a valid email';
    if (form.email && form.confirm_email && form.email !== form.confirm_email) errs.confirm_email = 'Emails do not match';
    if (!form.confirm_email.trim()) errs.confirm_email = 'Please confirm your email';
    if (!form.phone_number.trim() && !form.mobile_number.trim()) {
      errs.phone_number = 'At least one phone number is required';
      errs.mobile_number = 'At least one phone number is required';
    }
    if (form.phone_number && !/^\d{4,15}$/.test(form.phone_number.replace(/[\s-]/g, ''))) errs.phone_number = 'Enter digits only (4-15 digits)';
    if (form.mobile_number && !/^\d{4,15}$/.test(form.mobile_number.replace(/[\s-]/g, ''))) errs.mobile_number = 'Enter digits only (4-15 digits)';
    if (!form.street.trim()) errs.street = 'Street is required';
    if (!form.city.trim()) errs.city = 'City is required';
    if (!form.country) errs.country = 'Country is required';
    if (!form.nationality) errs.nationality = 'Nationality is required';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const validateStep2 = () => {
    const errs = {};
    if (!form.bank_name.trim()) errs.bank_name = 'Bank name is required';
    if (!form.bank_country) errs.bank_country = 'Bank country is required';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const nextStep = () => {
    if (step === 1 && !validateStep1()) return;
    if (step === 2 && !validateStep2()) return;
    setStep(s => Math.min(s + 1, 3));
  };

  const handleSubmit = async () => {
    if (previewMode) { alert('This is a preview. In production, the form would be submitted.'); return; }
    setLoading(true);
    try {
      const phone = form.phone_number ? `${form.phone_code} ${form.phone_number}` : '';
      const mobile = form.mobile_number ? `${form.mobile_code} ${form.mobile_number}` : '';
      const address = [form.street, form.street_number].filter(Boolean).join(' ');
      const res = await api.post('/intake/submit', {
        ...form,
        phone: phone || mobile, address,
        phone_full: phone, mobile_full: mobile,
      });
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
            <p className="text-sm text-[#64748B] mb-4">Your KYC onboarding request has been received. Our compliance team will review it and send you an invitation link to your email.</p>
            <div className="p-3 bg-[#F1F5F9] rounded-md"><p className="text-xs text-[#64748B]">Your Reference</p><p className="text-lg font-bold font-['JetBrains_Mono']">{reference}</p></div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const isCompany = form.client_type === 'legal_entity';

  return (
    <TooltipProvider>
      <div className={previewMode ? '' : 'min-h-screen bg-[#F8FAFC]'} data-testid="intake-form">
        {!previewMode && (
          <header className="h-14 bg-white border-b border-[#E2E8F0] flex items-center px-6">
            <Shield size={18} className="text-[#0F172A] mr-2" /><span className="text-sm font-semibold font-['IBM_Plex_Sans']">DDYs</span><span className="text-sm text-[#64748B] ml-2">KYC Onboarding Request</span>
          </header>
        )}
        {previewMode && (
          <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-md">
            <p className="text-sm text-amber-800 font-medium">Preview Mode — This is what the customer sees when they open the intake link.</p>
          </div>
        )}

        <div className={previewMode ? '' : 'max-w-2xl mx-auto py-8 px-4'}>
          {/* Progress */}
          <div className="flex items-center gap-2 mb-6">
            {[{n:1,l:'Your Details'},{n:2,l:'Bank Details'},{n:3,l:'Review & Submit'}].map((s, i) => (
              <div key={s.n} className="flex items-center gap-2 flex-1">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${step >= s.n ? 'bg-[#0F172A] text-white' : 'bg-[#E2E8F0] text-[#64748B]'}`}>{s.n}</div>
                <span className={`text-xs ${step >= s.n ? 'font-medium' : 'text-[#64748B]'}`}>{s.l}</span>
                {i < 2 && <div className={`flex-1 h-0.5 ${step > s.n ? 'bg-[#0F172A]' : 'bg-[#E2E8F0]'}`} />}
              </div>
            ))}
          </div>

          {/* Step 1 */}
          {step === 1 && (
            <Card className="border-[#E2E8F0]">
              <CardHeader><CardTitle className="text-lg font-['IBM_Plex_Sans']">Your Details</CardTitle>
                <p className="text-sm text-[#64748B]">Please provide accurate information. All fields marked with * are mandatory.</p>
              </CardHeader>
              <CardContent className="space-y-5">
                {/* Entity type */}
                <div>
                  <FieldLabel label="I am a *" hint="Select whether you are registering as a company or as an individual person." />
                  <div className="flex gap-3 mt-1.5">
                    {[{v:'legal_entity',l:'Company / Legal Entity',i:Building2},{v:'natural_person',l:'Individual / Natural Person',i:User}].map(({v,l,i:Icon}) => (
                      <button key={v} onClick={() => set('client_type', v)} className={`flex-1 p-4 rounded-lg border-2 transition-colors text-center ${form.client_type === v ? 'border-[#0F172A] bg-[#F1F5F9]' : 'border-[#E2E8F0] hover:border-[#CBD5E1]'}`} data-testid={`type-${v}`}>
                        <Icon size={24} className="mx-auto mb-1" /><span className="text-sm font-medium">{l}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Name fields */}
                {isCompany ? (
                  <div className="space-y-3">
                    <FormField label="Company Name *" hint="Full legal name as registered." error={errors.company_name}>
                      <Input value={form.company_name} onChange={e => set('company_name', e.target.value)} placeholder="e.g. Acme Trading GmbH" data-testid="company-name" />
                    </FormField>
                    <FormField label="Registration Number" hint="Commercial register number (e.g. HRB 123456).">
                      <Input value={form.registration_number} onChange={e => set('registration_number', e.target.value)} placeholder="e.g. HRB 123456" />
                    </FormField>
                    <div className="grid grid-cols-2 gap-3">
                      <FormField label="Contact First Name *" hint="First name of the contact person." error={errors.first_name}>
                        <Input value={form.first_name} onChange={e => set('first_name', e.target.value)} placeholder="Max" />
                      </FormField>
                      <FormField label="Contact Last Name *" hint="Last name of the contact person." error={errors.last_name}>
                        <Input value={form.last_name} onChange={e => set('last_name', e.target.value)} placeholder="Mustermann" />
                      </FormField>
                    </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-3">
                    <FormField label="First Name *" hint="As shown on your passport or ID." error={errors.first_name}>
                      <Input value={form.first_name} onChange={e => set('first_name', e.target.value)} placeholder="Max" />
                    </FormField>
                    <FormField label="Last Name *" hint="As shown on your passport or ID." error={errors.last_name}>
                      <Input value={form.last_name} onChange={e => set('last_name', e.target.value)} placeholder="Mustermann" />
                    </FormField>
                  </div>
                )}

                {/* Email */}
                <div className="grid grid-cols-2 gap-3">
                  <FormField label="Email Address *" hint="We will send all correspondence to this email." error={errors.email}>
                    <Input type="email" value={form.email} onChange={e => set('email', e.target.value)} placeholder="your@email.com" data-testid="email" />
                  </FormField>
                  <FormField label="Confirm Email *" hint="Please re-enter to avoid typos." error={errors.confirm_email}>
                    <Input type="email" value={form.confirm_email} onChange={e => set('confirm_email', e.target.value)} placeholder="your@email.com" />
                  </FormField>
                </div>

                {/* Phone numbers */}
                <div className="p-3 bg-[#F8FAFC] rounded-md border border-[#E2E8F0]">
                  <p className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B] mb-2 flex items-center gap-1"><Phone size={10} /> Contact Numbers (at least one is mandatory *)</p>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Label className="text-xs text-[#64748B]">Landline Phone</Label>
                      <div className="flex gap-1 mt-1">
                        <Select value={form.phone_code} onValueChange={v => set('phone_code', v)}>
                          <SelectTrigger className="w-24 shrink-0 text-xs"><SelectValue /></SelectTrigger>
                          <SelectContent>{COUNTRY_CODES.map(c => <SelectItem key={c.code} value={c.code}>{c.flag} {c.code}</SelectItem>)}</SelectContent>
                        </Select>
                        <Input value={form.phone_number} onChange={e => set('phone_number', e.target.value.replace(/[^\d\s-]/g, ''))} placeholder="30 123456" className={errors.phone_number ? 'border-red-300' : ''} />
                      </div>
                      {errors.phone_number && <p className="text-[10px] text-red-600 mt-0.5">{errors.phone_number}</p>}
                    </div>
                    <div>
                      <Label className="text-xs text-[#64748B]">Mobile Phone</Label>
                      <div className="flex gap-1 mt-1">
                        <Select value={form.mobile_code} onValueChange={v => set('mobile_code', v)}>
                          <SelectTrigger className="w-24 shrink-0 text-xs"><SelectValue /></SelectTrigger>
                          <SelectContent>{COUNTRY_CODES.map(c => <SelectItem key={c.code+'-m'} value={c.code}>{c.flag} {c.code}</SelectItem>)}</SelectContent>
                        </Select>
                        <Input value={form.mobile_number} onChange={e => set('mobile_number', e.target.value.replace(/[^\d\s-]/g, ''))} placeholder="170 1234567" className={errors.mobile_number ? 'border-red-300' : ''} />
                      </div>
                      {errors.mobile_number && <p className="text-[10px] text-red-600 mt-0.5">{errors.mobile_number}</p>}
                    </div>
                  </div>
                </div>

                {/* Address */}
                <div className="space-y-3">
                  <div className="grid grid-cols-4 gap-3">
                    <div className="col-span-3"><FormField label="Street *" error={errors.street}><Input value={form.street} onChange={e => set('street', e.target.value)} placeholder="Friedrichstrasse" /></FormField></div>
                    <FormField label="Number"><Input value={form.street_number} onChange={e => set('street_number', e.target.value)} placeholder="100" /></FormField>
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    <FormField label="Postal Code"><Input value={form.postal_code} onChange={e => set('postal_code', e.target.value)} placeholder="10117" /></FormField>
                    <FormField label="City *" error={errors.city}><Input value={form.city} onChange={e => set('city', e.target.value)} placeholder="Berlin" /></FormField>
                    <FormField label="Country *" error={errors.country}>
                      <Select value={form.country} onValueChange={v => set('country', v)}>
                        <SelectTrigger className={errors.country ? 'border-red-300' : ''}><SelectValue placeholder="Select..." /></SelectTrigger>
                        <SelectContent>{COUNTRIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
                      </Select>
                    </FormField>
                  </div>
                  <FormField label="Nationality *" hint="Country of citizenship." error={errors.nationality}>
                    <Select value={form.nationality} onValueChange={v => set('nationality', v)}>
                      <SelectTrigger className={errors.nationality ? 'border-red-300' : ''}><SelectValue placeholder="Select..." /></SelectTrigger>
                      <SelectContent>{COUNTRIES.map(c => <SelectItem key={c+'-nat'} value={c}>{c}</SelectItem>)}</SelectContent>
                    </Select>
                  </FormField>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Step 2 */}
          {step === 2 && (
            <Card className="border-[#E2E8F0]">
              <CardHeader><CardTitle className="text-lg font-['IBM_Plex_Sans']">Which bank is this for?</CardTitle>
                <p className="text-sm text-[#64748B]">Please provide the details of the financial institution you need KYC onboarding for.</p>
              </CardHeader>
              <CardContent className="space-y-4">
                <FormField label="Bank / Institution Name *" hint="The full legal name of the bank or financial institution." error={errors.bank_name}>
                  <Input value={form.bank_name} onChange={e => set('bank_name', e.target.value)} placeholder="e.g. Demo Bank AG" data-testid="bank-name" />
                </FormField>
                <div className="grid grid-cols-4 gap-3">
                  <div className="col-span-2"><FormField label="Bank Street"><Input value={form.bank_street} onChange={e => set('bank_street', e.target.value)} placeholder="Street address" /></FormField></div>
                  <FormField label="Bank City"><Input value={form.bank_city} onChange={e => set('bank_city', e.target.value)} placeholder="City" /></FormField>
                  <FormField label="Bank Country *" error={errors.bank_country}>
                    <Select value={form.bank_country} onValueChange={v => set('bank_country', v)}>
                      <SelectTrigger className={errors.bank_country ? 'border-red-300' : ''}><SelectValue placeholder="Select..." /></SelectTrigger>
                      <SelectContent>{COUNTRIES.map(c => <SelectItem key={c+'-bank'} value={c}>{c}</SelectItem>)}</SelectContent>
                    </Select>
                  </FormField>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <FormField label="Account / Reference Number" hint="If you already have a reference from the bank.">
                    <Input value={form.bank_reference} onChange={e => set('bank_reference', e.target.value)} placeholder="Optional" />
                  </FormField>
                  <FormField label="Product / Service" hint="What type of account or service are you applying for?">
                    <Input value={form.product_requested} onChange={e => set('product_requested', e.target.value)} placeholder="e.g. Corporate Account" />
                  </FormField>
                </div>
                <FormField label="Additional Notes" hint="Anything else we should know about your application.">
                  <Textarea value={form.notes} onChange={e => set('notes', e.target.value)} placeholder="Optional..." rows={3} />
                </FormField>
              </CardContent>
            </Card>
          )}

          {/* Step 3: Review */}
          {step === 3 && (
            <Card className="border-[#E2E8F0]">
              <CardHeader><CardTitle className="text-lg font-['IBM_Plex_Sans']">Review & Submit</CardTitle>
                <p className="text-sm text-[#64748B]">Please verify all information before submitting.</p>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="p-4 bg-[#F8FAFC] rounded-md space-y-2">
                  <p className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">{isCompany ? 'Company' : 'Individual'}</p>
                  <p className="text-base font-semibold">{form.company_name || `${form.first_name} ${form.last_name}`}</p>
                  {form.registration_number && <p className="text-xs text-[#64748B]">Reg: {form.registration_number}</p>}
                  <div className="grid grid-cols-2 gap-2 text-xs text-[#64748B]">
                    <p><Mail size={10} className="inline mr-1" />{form.email}</p>
                    {form.phone_number && <p><Phone size={10} className="inline mr-1" />{form.phone_code} {form.phone_number}</p>}
                    {form.mobile_number && <p><Phone size={10} className="inline mr-1" />{form.mobile_code} {form.mobile_number} (mobile)</p>}
                  </div>
                  <p className="text-xs text-[#64748B]">{[form.street, form.street_number, form.postal_code, form.city, form.country].filter(Boolean).join(', ')}</p>
                  <p className="text-xs text-[#64748B]">Nationality: {form.nationality}</p>
                </div>
                <div className="p-4 bg-blue-50 rounded-md border border-blue-200 space-y-1">
                  <p className="text-[10px] uppercase tracking-wider font-semibold text-blue-700">Bank / Institution</p>
                  <p className="text-base font-semibold">{form.bank_name}</p>
                  <p className="text-xs text-[#64748B]">{[form.bank_street, form.bank_city, form.bank_country].filter(Boolean).join(', ')}</p>
                  {form.product_requested && <p className="text-xs text-[#64748B]">Product: {form.product_requested}</p>}
                </div>
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-md">
                  <p className="text-xs text-amber-800"><AlertCircle size={12} className="inline mr-1" />By submitting, you confirm that all information provided is accurate and complete. Providing false information may result in rejection of your application.</p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Navigation */}
          <div className="flex justify-between mt-6">
            {step > 1 ? <Button variant="outline" onClick={() => setStep(s => s - 1)}><ArrowLeft size={14} className="mr-1" /> Back</Button> : <div />}
            {step < 3 ? (
              <Button className="bg-[#0F172A] hover:bg-[#1E293B]" onClick={nextStep} data-testid="next-step">Next <ArrowRight size={14} className="ml-1" /></Button>
            ) : (
              <Button className="bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleSubmit} disabled={loading} data-testid="submit-intake">
                {loading ? 'Submitting...' : previewMode ? 'Submit (Preview)' : 'Submit Request'} <CheckCircle size={14} className="ml-1" />
              </Button>
            )}
          </div>
        </div>
      </div>
    </TooltipProvider>
  );
}

// Helper components
function FieldLabel({ label, hint }) {
  return (
    <div className="flex items-center gap-1 mb-0.5">
      <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">{label}</Label>
      {hint && (
        <Tooltip>
          <TooltipTrigger asChild>
            <button className="w-4 h-4 rounded-full bg-[#E2E8F0] flex items-center justify-center hover:bg-[#CBD5E1]" type="button">
              <HelpCircle size={10} className="text-[#64748B]" />
            </button>
          </TooltipTrigger>
          <TooltipContent side="right" className="max-w-xs text-xs">{hint}</TooltipContent>
        </Tooltip>
      )}
    </div>
  );
}

function FormField({ label, hint, error, children }) {
  return (
    <div>
      {label && <FieldLabel label={label} hint={hint} />}
      <div className="mt-1">{children}</div>
      {error && <p className="text-[10px] text-red-600 mt-0.5 flex items-center gap-0.5"><AlertCircle size={10} /> {error}</p>}
    </div>
  );
}
