import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Shield, ArrowRight, CheckCircle, Lock } from 'lucide-react';
import api from '@/api/client';

export default function CustomerInvitePage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [invite, setInvite] = useState(null);
  const [loading, setLoading] = useState(true);
  const [step, setStep] = useState('verify'); // verify, otp
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get(`/customer/invite/${token}`).then(r => {
      setInvite(r.data);
      setEmail(r.data.invite?.email || '');
    }).catch(err => {
      setError('This invitation link is invalid or has expired.');
    }).finally(() => setLoading(false));
  }, [token]);

  const handleRequestOtp = async () => {
    setError('');
    setSubmitting(true);
    try {
      await api.post(`/customer/invite/${token}/accept`, { email });
      setStep('otp');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to verify. Check your email matches the invitation.');
    } finally { setSubmitting(false); }
  };

  const handleVerifyOtp = async () => {
    setError('');
    setSubmitting(true);
    try {
      const res = await api.post(`/customer/invite/${token}/verify`, { code: otp });
      localStorage.setItem('ddys_token', res.data.token);
      localStorage.setItem('ddys_user', JSON.stringify(res.data.user));
      localStorage.setItem('ddys_customer_case_id', res.data.case_id);
      localStorage.setItem('ddys_customer_tenant', res.data.tenant_id);
      navigate('/portal/dashboard');
      window.location.reload();
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid code');
    } finally { setSubmitting(false); }
  };

  if (loading) return <div className="min-h-screen flex items-center justify-center text-sm text-[#64748B]">Loading invitation...</div>;

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex items-center justify-center p-4" data-testid="customer-invite-page">
      <Card className="w-full max-w-md border-[#E2E8F0] shadow-sm">
        <CardHeader className="text-center pb-4">
          <Shield size={32} className="mx-auto text-[#0F172A] mb-2" />
          {invite?.tenant_name && (
            <p className="text-lg font-semibold font-['IBM_Plex_Sans'] text-[#0F172A]">{invite.tenant_name}</p>
          )}
          <CardTitle className="text-base font-['IBM_Plex_Sans'] text-[#64748B]">KYC Onboarding Portal</CardTitle>
          {invite?.case_ref && (
            <p className="text-xs font-['JetBrains_Mono'] text-[#64748B] mt-1">Case: {invite.case_ref}</p>
          )}
        </CardHeader>
        <CardContent>
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700" data-testid="invite-error">
              {error}
            </div>
          )}

          {!invite && !error && <p className="text-sm text-center text-[#64748B]">Invalid invitation</p>}

          {invite && step === 'verify' && (
            <div className="space-y-4">
              <div className="p-3 bg-[#F1F5F9] rounded-md text-sm text-[#0F172A]">
                You've been invited to complete your KYC documentation. Please verify your email to proceed.
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Your Email</Label>
                <Input
                  className="mt-1.5"
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="your@email.com"
                  data-testid="invite-email"
                />
              </div>
              <Button className="w-full bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleRequestOtp} disabled={!email || submitting} data-testid="invite-verify-btn">
                {submitting ? 'Verifying...' : 'Verify & Get Code'} <ArrowRight size={14} className="ml-1" />
              </Button>
            </div>
          )}

          {invite && step === 'otp' && (
            <div className="space-y-4">
              <div className="p-3 bg-[#F1F5F9] rounded-md text-sm text-[#0F172A]">
                A verification code has been sent to <strong>{email}</strong>
              </div>
              <p className="text-xs text-center text-amber-600">(Demo: use code 123456)</p>
              <div>
                <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Access Code</Label>
                <Input
                  className="mt-1.5 text-center tracking-[0.3em] text-lg"
                  value={otp}
                  onChange={e => setOtp(e.target.value)}
                  maxLength={6}
                  placeholder="------"
                  data-testid="invite-otp"
                />
              </div>
              <Button className="w-full bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleVerifyOtp} disabled={!otp || submitting} data-testid="invite-otp-verify-btn">
                {submitting ? 'Verifying...' : 'Enter Portal'} <CheckCircle size={14} className="ml-1" />
              </Button>
              <Button variant="ghost" className="w-full" onClick={() => { setStep('verify'); setError(''); }}>Back</Button>
            </div>
          )}

          <div className="mt-6 pt-4 border-t border-[#E2E8F0]">
            <p className="text-[11px] text-[#64748B] text-center">
              <Lock size={10} className="inline mr-1" />
              Secured connection. All data is encrypted and access is logged.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
