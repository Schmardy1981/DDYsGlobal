import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Shield, Lock, Eye, EyeOff, AlertCircle, X } from 'lucide-react';

export default function LoginPage() {
  const { login, verifyMfa, completeLogin } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [mfaMode, setMfaMode] = useState(false);
  const [mfaToken, setMfaToken] = useState('');
  const [mfaCode, setMfaCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await login(email, password);
      if (res.requires_mfa) {
        setMfaMode(true);
        setMfaToken(res.mfa_token);
      } else {
        completeLogin(res.token, res.user);
        redirectUser(res.user);
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleMfa = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const u = await verifyMfa(mfaToken, mfaCode);
      redirectUser(u);
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid MFA code');
    } finally {
      setLoading(false);
    }
  };

  const redirectUser = (u) => {
    const role = u?.global_role;
    if (role === 'END_CUSTOMER') navigate('/portal');
    else if (role === 'ADMIN') navigate('/admin');
    else navigate('/workspace/intake');
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#F8FAFC] p-8" data-testid="login-page">
      {error && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" data-testid="login-error-overlay">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-sm mx-4 overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b border-[#E2E8F0]">
              <div className="flex items-center gap-2 text-red-700">
                <AlertCircle size={20} />
                <span className="font-semibold font-['IBM_Plex_Sans']">Error</span>
              </div>
              <button onClick={() => setError('')} className="w-7 h-7 rounded-md flex items-center justify-center hover:bg-[#F1F5F9]" data-testid="close-error-btn">
                <X size={16} className="text-[#64748B]" />
              </button>
            </div>
            <div className="p-4">
              <p className="text-sm text-[#0F172A]" data-testid="login-error">{error}</p>
            </div>
            <div className="px-4 pb-4">
              <Button variant="outline" className="w-full" onClick={() => setError('')}>Close</Button>
            </div>
          </div>
        </div>
      )}

      <Card className="w-full max-w-md shadow-sm border-[#E2E8F0]">
        <CardHeader className="pb-4">
          <div className="flex items-center gap-2 mb-4">
            <Shield size={24} className="text-[#0F172A]" />
            <span className="text-lg font-semibold font-['IBM_Plex_Sans']">DDYs</span>
          </div>
          <CardTitle className="text-xl font-['IBM_Plex_Sans']">
            {mfaMode ? 'Two-Factor Authentication' : 'Sign In'}
          </CardTitle>
          <p className="text-sm text-[#64748B]">
            {mfaMode ? 'Enter your authenticator code' : 'Sign in to your DDYs account'}
          </p>
        </CardHeader>
        <CardContent>
          {!mfaMode ? (
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <Label htmlFor="email" className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Email</Label>
                <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="your@email.com" className="mt-1.5" required data-testid="login-email" />
              </div>
              <div>
                <Label htmlFor="password" className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Password</Label>
                <div className="relative mt-1.5">
                  <Input id="password" type={showPw ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Enter password" required data-testid="login-password" />
                  <button type="button" onClick={() => setShowPw(!showPw)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#64748B]">
                    {showPw ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
              </div>
              <Button type="submit" className="w-full bg-[#0F172A] hover:bg-[#1E293B]" disabled={loading} data-testid="login-submit">
                {loading ? 'Signing in...' : 'Sign In'}
              </Button>
            </form>
          ) : (
            <form onSubmit={handleMfa} className="space-y-4">
              <div>
                <Label htmlFor="mfa" className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Authenticator Code</Label>
                <Input id="mfa" type="text" value={mfaCode} onChange={(e) => setMfaCode(e.target.value)} placeholder="6-digit code" maxLength={6} className="mt-1.5 text-center tracking-[0.3em] text-lg" required data-testid="mfa-code" />
              </div>
              <Button type="submit" className="w-full bg-[#0F172A] hover:bg-[#1E293B]" disabled={loading} data-testid="mfa-submit">
                {loading ? 'Verifying...' : 'Verify'}
              </Button>
              <Button type="button" variant="ghost" className="w-full" onClick={() => { setMfaMode(false); setError(''); }}>Back</Button>
            </form>
          )}

          <div className="mt-4 pt-4 border-t border-[#E2E8F0]">
            <p className="text-[11px] text-[#64748B] text-center">
              <Lock size={10} className="inline mr-1" />
              All access is logged and audited.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
