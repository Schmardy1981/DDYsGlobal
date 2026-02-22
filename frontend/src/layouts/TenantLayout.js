import { useState, useEffect } from 'react';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Briefcase, FolderOpen, Search, FileWarning, Shield, BarChart3, Settings, Bell, LogOut, ChevronLeft, ChevronRight, AlertTriangle, Clock, Video, ClipboardCheck, ArrowRightLeft, Inbox } from 'lucide-react';
import NotificationBell from '@/components/shared/NotificationBell';
import api from '@/api/client';

const NAV_ITEMS = [
  { label: 'Intake', path: '/workspace/intake', icon: Inbox },
  { label: 'Cases', path: '/workspace/cases', icon: FolderOpen },
  { label: 'Screening', path: '/workspace/screening', icon: Search },
  { label: 'Video Ident', path: '/workspace/video-ident', icon: Video },
  { label: 'Waivers', path: '/workspace/waivers', icon: FileWarning },
  { label: 'EDR Alerts', path: '/workspace/edr', icon: AlertTriangle },
  { label: 'QA', path: '/workspace/qa', icon: ClipboardCheck },
  { label: 'MI Dashboard', path: '/workspace/mi', icon: BarChart3 },
  { label: 'Settings', path: '/workspace/settings', icon: Settings },
];

export default function TenantLayout() {
  const { user, logout, getActiveTenantId, setActiveTenant } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const [tenants, setTenants] = useState([]);
  const activeTenantId = getActiveTenantId();

  useEffect(() => {
    api.get('/tenants').then(r => {
      setTenants(r.data);
      // Auto-select first tenant if none selected
      if (!activeTenantId && r.data.length > 0) {
        setActiveTenant(r.data[0].id);
      }
    }).catch(() => {});
  }, [activeTenantId, setActiveTenant]);

  const activeTenant = tenants.find(t => t.id === activeTenantId);

  return (
    <div className="flex h-screen bg-[#F8FAFC]" data-testid="tenant-layout">
      <aside className={`${collapsed ? 'w-16' : 'w-56'} bg-[#0F172A] text-white flex flex-col transition-all duration-200`}>
        <div className="h-14 flex items-center px-4 border-b border-white/10">
          <Briefcase size={20} className="text-white shrink-0" />
          {!collapsed && <span className="ml-2.5 text-sm font-semibold tracking-tight font-['IBM_Plex_Sans']">Workspace</span>}
        </div>
        <nav className="flex-1 py-2">
          {NAV_ITEMS.map(item => {
            const Icon = item.icon;
            const active = location.pathname === item.path || (item.path === '/workspace/cases' && location.pathname.startsWith('/workspace/case/'));
            return (
              <Link
                key={item.path}
                to={item.path}
                data-testid={`nav-${item.label.toLowerCase().replace(' ', '-')}`}
                className={`flex items-center h-10 px-4 text-sm transition-colors ${active ? 'bg-white/10 text-white' : 'text-white/60 hover:bg-white/5 hover:text-white'}`}
              >
                <Icon size={16} className="shrink-0" />
                {!collapsed && <span className="ml-3">{item.label}</span>}
              </Link>
            );
          })}
        </nav>
        <button onClick={() => setCollapsed(!collapsed)} className="h-10 flex items-center justify-center text-white/40 hover:text-white border-t border-white/10">
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </aside>

      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-14 bg-white border-b border-[#E2E8F0] flex items-center justify-between px-6">
          <div className="flex items-center gap-4">
            <Select value={activeTenantId || ''} onValueChange={(v) => { setActiveTenant(v); window.location.reload(); }}>
              <SelectTrigger className="w-48 h-8 text-xs" data-testid="tenant-selector">
                <SelectValue placeholder="Select Tenant" />
              </SelectTrigger>
              <SelectContent>
                {tenants.map(t => (
                  <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {activeTenant && <span className="text-xs text-[#64748B]">{activeTenant.default_jurisdiction}</span>}
          </div>
          <div className="flex items-center gap-3">
            {user?.global_role === 'GLOBAL_SUPER_ADMIN' && (
              <Button variant="outline" size="sm" onClick={() => navigate('/admin')} className="text-xs" data-testid="switch-to-admin">
                <ArrowRightLeft size={14} className="mr-1" /> Admin
              </Button>
            )}
            <NotificationBell />
            <div className="text-right">
              <p className="text-sm font-medium leading-none">{user?.name}</p>
              <p className="text-[11px] text-[#64748B]">{user?.global_role?.replace(/_/g, ' ')}</p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => { logout(); navigate('/login'); }} data-testid="logout-btn">
              <LogOut size={16} />
            </Button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
