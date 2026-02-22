import { useState } from 'react';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Shield, Building2, Users, Settings, BarChart3, FileText, Bell, LogOut, ChevronLeft, ChevronRight, Activity, Clock, Plug, ArrowRightLeft, Brain, ClipboardList } from 'lucide-react';
import NotificationBell from '@/components/shared/NotificationBell';

const NAV_ITEMS = [
  { label: 'Dashboard', path: '/admin', icon: BarChart3 },
  { label: 'Tenants', path: '/admin/tenants', icon: Building2 },
  { label: 'Users', path: '/admin/users', icon: Users },
  { label: 'Integrations', path: '/admin/integrations', icon: Plug },
  { label: 'AI Prompts', path: '/admin/prompts', icon: Brain },
  { label: 'Customer Form', path: '/admin/customer-form', icon: ClipboardList },
  { label: 'Policy', path: '/admin/policy', icon: FileText },
  { label: 'Jobs', path: '/admin/jobs', icon: Clock },
  { label: 'Settings', path: '/admin/settings', icon: Settings },
];

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="flex h-screen bg-[#F8FAFC]" data-testid="admin-layout">
      {/* Sidebar */}
      <aside className={`${collapsed ? 'w-16' : 'w-56'} bg-[#0F172A] text-white flex flex-col transition-all duration-200`}>
        <div className="h-14 flex items-center px-4 border-b border-white/10">
          <Shield size={20} className="text-white shrink-0" />
          {!collapsed && <span className="ml-2.5 text-sm font-semibold tracking-tight font-['IBM_Plex_Sans']">DDYs Admin</span>}
        </div>
        <nav className="flex-1 py-2">
          {NAV_ITEMS.map(item => {
            const Icon = item.icon;
            const active = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                data-testid={`nav-${item.label.toLowerCase()}`}
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

      {/* Main */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-14 bg-white border-b border-[#E2E8F0] flex items-center justify-between px-6">
          <div className="flex items-center gap-2">
            <Activity size={14} className="text-green-500" />
            <span className="text-xs text-[#64748B] font-['IBM_Plex_Sans']">Platform Admin Console</span>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="outline" size="sm" onClick={() => navigate('/workspace/cases')} className="text-xs" data-testid="switch-to-workspace">
              <ArrowRightLeft size={14} className="mr-1" /> Workspace
            </Button>
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
