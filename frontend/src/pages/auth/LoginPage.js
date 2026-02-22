import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Shield, Lock, Eye, EyeOff, AlertCircle, X, ArrowRight } from 'lucide-react';
import api from '@/api/client';

const ROLE_COLORS = {
  GLOBAL_SUPER_ADMIN: 'bg-blue-100 text-blue-700',
  DDYS_RCM_MAKER: 'bg-purple-100 text-purple-700',
  DDYS_RCM_CHECKER: 'bg-purple-100 text-purple-700',
  DDYS_QA_FIRST_LINE: 'bg-amber-100 text-amber-700',
  DDYS_QA_SECOND_LINE: 'bg-amber-100 text-amber-700',
  DDYS_COMPLIANCE_MANAGER: 'bg-teal-100 text-teal-700',
  TENANT_ADMIN: 'bg-blue-100 text-blue-700',
  TENANT_BUSINESS_USER: 'bg-green-100 text-green-700',
  TENANT_COMPLIANCE_USER: 'bg-teal-100 text-teal-700',
  TENANT_MLRO: 'bg-red-100 text-red-700',
};

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
  const [users, setUsers] = useState([]);
  const [quickLoading, setQuickLoading] = useState(null);

  useEffect(() => {
    // Load available users for quick access
    api.get('/auth/users-list').then(r => setUsers(r.data)).catch(() => {});
  }, []);

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

  const handleQuickLogin = async (userEmail) => {
    setQuickLoading(userEmail);
    setError('');
    try {
      const res = await api.post('/auth/quick-login', { email: userEmail });
      completeLogin(res.data.token, res.data.user);
      redirectUser(res.data.user);
    } catch (err) {
      setError(err.response?.data?.detail || 'Quick login failed');
    } finally {
      setQuickLoading(null);
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
    else if (role === 'GLOBAL_SUPER_ADMIN') navigate('/admin');
    else navigate('/workspace/cases');
  };

  // Group users by category
  const ddysUsers = users.filter(u => u.global_role?.startsWith('DDYS_') || u.global_role === 'GLOBAL_SUPER_ADMIN');
  const tenantUsers = users.filter(u => u.global_role?.startsWith('TENANT_'));

  return (
    <div className="min-h-screen flex" data-testid="login-page">
      {/* Error Popup */}
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

      {/* Left: Quick Session Switcher */}
      <div className="hidden lg:flex lg:w-1/2 bg-[#0F172A] flex-col p-8 overflow-y-auto">
        <div className="flex items-center gap-2 mb-8">
          <Shield size={24} className="text-white" />
          <span className="text-lg font-semibold text-white font-['IBM_Plex_Sans']">DDYs</span>
          <span className="text-sm text-white/40">Quick Access</span>
        </div>

        {/* DDYs Staff */}
        <div className="mb-6">
          <p className="text-[11px] uppercase tracking-wider font-semibold text-white/40 mb-3">DDYs Platform Staff</p>
          <div className="space-y-1.5">
            {ddysUsers.map(u => (
              <button
                key={u.id}
                onClick={() => handleQuickLogin(u.email)}
                disabled={quickLoading === u.email}
                className="w-full flex items-center justify-between p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors text-left group"
                data-testid={`quick-login-${u.email}`}
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-white text-xs font-semibold">
                    {u.name?.charAt(0) || '?'}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-white">{u.name}</p>
                    <p className="text-xs text-white/40 font-['JetBrains_Mono']">{u.email}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge className={`${ROLE_COLORS[u.global_role] || 'bg-gray-100 text-gray-700'} border-transparent text-[10px]`}>
                    {u.global_role?.replace(/^(DDYS_|GLOBAL_)/, '').replace(/_/g, ' ')}
                  </Badge>
                  {quickLoading === u.email ? (
                    <span className="text-xs text-white/40">Loading...</span>
                  ) : (
                    <ArrowRight size={14} className="text-white/20 group-hover:text-white/60 transition-colors" />
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Tenant Users */}
        <div className="mb-6">
          <p className="text-[11px] uppercase tracking-wider font-semibold text-white/40 mb-3">Demo Bank Staff</p>
          <div className="space-y-1.5">
            {tenantUsers.map(u => (
              <button
                key={u.id}
                onClick={() => handleQuickLogin(u.email)}
                disabled={quickLoading === u.email}
                className="w-full flex items-center justify-between p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors text-left group"
                data-testid={`quick-login-${u.email}`}
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-white text-xs font-semibold">
                    {u.name?.charAt(0) || '?'}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-white">{u.name}</p>
                    <p className="text-xs text-white/40 font-['JetBrains_Mono']">{u.email}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge className={`${ROLE_COLORS[u.global_role] || 'bg-gray-100 text-gray-700'} border-transparent text-[10px]`}>
                    {u.global_role?.replace(/^TENANT_/, '').replace(/_/g, ' ')}
                  </Badge>
                  {quickLoading === u.email ? (
                    <span className="text-xs text-white/40">Loading...</span>
                  ) : (
                    <ArrowRight size={14} className="text-white/20 group-hover:text-white/60 transition-colors" />
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="mt-auto pt-4 border-t border-white/10">
          <p className="text-xs text-white/30">Click any account to login instantly. No password required in dev mode.</p>
        </div>
      </div>

      {/* Right: Traditional Login Form */}
      <div className="flex-1 flex items-center justify-center p-8 bg-[#F8FAFC]">
        <Card className="w-full max-w-md shadow-sm border-[#E2E8F0]">
          <CardHeader className="pb-4">
            <div className="flex items-center gap-2 lg:hidden mb-4">
              <Shield size={24} className="text-[#0F172A]" />
              <span className="text-lg font-semibold font-['IBM_Plex_Sans']">DDYs</span>
            </div>
            <CardTitle className="text-xl font-['IBM_Plex_Sans']">
              {mfaMode ? 'Two-Factor Authentication' : 'Sign In'}
            </CardTitle>
            <p className="text-sm text-[#64748B]">
              {mfaMode ? 'Enter your authenticator code' : 'Or use the quick-access panel on the left'}
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

            {/* Mobile quick access */}
            <div className="lg:hidden mt-6 pt-4 border-t border-[#E2E8F0]">
              <p className="text-[11px] font-semibold text-[#64748B] uppercase tracking-wider mb-2">Quick Access</p>
              <div className="space-y-1">
                {users.slice(0, 5).map(u => (
                  <button key={u.id} onClick={() => handleQuickLogin(u.email)} className="w-full flex items-center justify-between p-2 rounded hover:bg-[#F1F5F9] text-xs text-left" data-testid={`quick-mobile-${u.email}`}>
                    <span className="font-['JetBrains_Mono'] text-[#0F172A]">{u.email}</span>
                    <Badge className={`${ROLE_COLORS[u.global_role] || 'bg-gray-100'} border-transparent text-[9px]`}>
                      {u.global_role?.replace(/^(DDYS_|GLOBAL_|TENANT_)/, '').replace(/_/g, ' ')}
                    </Badge>
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-4 pt-4 border-t border-[#E2E8F0]">
              <p className="text-[11px] text-[#64748B] text-center">
                <Lock size={10} className="inline mr-1" />
                All access is logged and audited.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
