import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import api from '@/api/client';

const AuthContext = createContext(null);

const ADMIN_ONLY_ROLES = ['ADMIN'];
const WORKSPACE_ROLES = ['CASE_MANAGER', 'VIDEO_AGENT', 'BANK_USER'];

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const savedToken = localStorage.getItem('ddys_token');
    const savedUser = localStorage.getItem('ddys_user');
    if (savedToken && savedUser) {
      setToken(savedToken);
      try { setUser(JSON.parse(savedUser)); } catch { /* ignore */ }
    }
    setLoading(false);
  }, []);

  const login = useCallback(async (email, password) => {
    const res = await api.post('/auth/login', { email, password });
    return res.data;
  }, []);

  const verifyMfa = useCallback(async (mfaToken, code) => {
    const res = await api.post('/auth/mfa/verify', { mfa_token: mfaToken, code });
    const { token: t, user: u } = res.data;
    localStorage.setItem('ddys_token', t);
    localStorage.setItem('ddys_user', JSON.stringify(u));
    setToken(t);
    setUser(u);
    return u;
  }, []);

  const completeLogin = useCallback((t, u) => {
    localStorage.setItem('ddys_token', t);
    localStorage.setItem('ddys_user', JSON.stringify(u));
    setToken(t);
    setUser(u);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('ddys_token');
    localStorage.removeItem('ddys_user');
    setToken(null);
    setUser(null);
  }, []);

  const getPortal = useCallback(() => {
    if (!user) return null;
    const role = user.global_role;
    if (role === 'END_CUSTOMER') return 'portal';
    if (ADMIN_ONLY_ROLES.includes(role)) return 'admin';
    return 'workspace';
  }, [user]);

  const hasRole = useCallback((roles) => {
    if (!user) return false;
    const allRoles = new Set();
    if (user.global_role) allRoles.add(user.global_role);
    (user.tenant_roles || []).forEach(tr => allRoles.add(tr.role));
    return roles.some(r => allRoles.has(r));
  }, [user]);

  const getActiveTenantId = useCallback(() => {
    if (!user) return null;
    const saved = localStorage.getItem('ddys_active_tenant');
    if (saved) return saved;
    const trs = user.tenant_roles || [];
    return trs.length > 0 ? trs[0].tenant_id : null;
  }, [user]);

  const setActiveTenant = useCallback((tenantId) => {
    localStorage.setItem('ddys_active_tenant', tenantId);
  }, []);

  return (
    <AuthContext.Provider value={{
      user, token, loading, login, verifyMfa, completeLogin, logout,
      getPortal, hasRole, getActiveTenantId, setActiveTenant, isAuthenticated: !!token
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
