import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Shield, ArrowRight } from 'lucide-react';
import api from '@/api/client';

export default function CustomerLanding() {
  const navigate = useNavigate();
  const [tenants, setTenants] = useState([]);
  const [selectedTenant, setSelectedTenant] = useState('');
  const [email, setEmail] = useState('');
  const [caseRef, setCaseRef] = useState('');
  const [step, setStep] = useState('select'); // select, otp, verify
  const [otp, setOtp] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get('/tenants/public/list').then(r => setTenants(r.data)).catch(console.error);
  }, []);

  const handleRequestOtp = async () => {
    setError('');
    setLoading(true);
    try {
      const res = await api.post('/auth/customer/otp-request', { email, tenant_id: selectedTenant, case_ref: caseRef });
      setStep('verify');
    } catch (err) { setError(err.response?.data?.detail || 'Failed'); }
    finally { setLoading(false); }
  };

  const handleVerifyOtp = async () => {
    setError('');
    setLoading(true);
    try {
      const res = await api.post('/auth/customer/otp-verify', { email, code: otp, tenant_id: selectedTenant });
      localStorage.setItem('ddys_token', res.data.token);
      localStorage.setItem('ddys_user', JSON.stringify(res.data.user));
      localStorage.setItem('ddys_customer_case_ref', caseRef);
      localStorage.setItem('ddys_customer_tenant', selectedTenant);
      navigate('/portal/dashboard');
      window.location.reload();
    } catch (err) { setError(err.response?.data?.detail || 'Invalid OTP'); }
    finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex items-center justify-center p-4" data-testid="customer-landing">
      <Card className="w-full max-w-md border-[#E2E8F0] shadow-sm">
        <CardHeader className="text-center pb-4">
          <Shield size={32} className="mx-auto text-[#0F172A] mb-2" />
          <CardTitle className="text-xl font-['IBM_Plex_Sans']">Client Portal</CardTitle>
          <p className="text-sm text-[#64748B]">Complete your KYC requirements</p>
        </CardHeader>
        <CardContent>
          {error && <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">{error}</div>}

          {step === 'select' && (
            <div className="space-y-4">
              <div>
                <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Select Your Bank</Label>
                <Select value={selectedTenant} onValueChange={setSelectedTenant}>
                  <SelectTrigger className="mt-1.5" data-testid="bank-select">
                    <SelectValue placeholder="Choose your bank" />
                  </SelectTrigger>
                  <SelectContent>
                    {tenants.map(t => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Case Reference</Label>
                <Input className="mt-1.5" value={caseRef} onChange={e => setCaseRef(e.target.value)} placeholder="DDY-YYYYMMDD-XXXXXX" data-testid="case-ref-input" />
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Your Email</Label>
                <Input className="mt-1.5" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="your@email.com" data-testid="customer-email-input" />
              </div>
              <Button className="w-full bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleRequestOtp} disabled={!selectedTenant || !email || loading} data-testid="request-otp-btn">
                {loading ? 'Sending...' : 'Get Access Code'} <ArrowRight size={14} className="ml-1" />
              </Button>
            </div>
          )}

          {step === 'verify' && (
            <div className="space-y-4">
              <p className="text-sm text-[#64748B] text-center">Enter the code sent to <strong>{email}</strong></p>
              <p className="text-xs text-center text-amber-600">(Demo: use code 123456)</p>
              <div>
                <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Access Code</Label>
                <Input className="mt-1.5 text-center tracking-[0.3em] text-lg" value={otp} onChange={e => setOtp(e.target.value)} maxLength={6} placeholder="------" data-testid="otp-input" />
              </div>
              <Button className="w-full bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleVerifyOtp} disabled={!otp || loading} data-testid="verify-otp-btn">
                {loading ? 'Verifying...' : 'Verify & Continue'}
              </Button>
              <Button variant="ghost" className="w-full" onClick={() => setStep('select')}>Back</Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
