import { Outlet } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Shield, LogOut } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function CustomerLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-[#F8FAFC]" data-testid="customer-layout">
      <header className="h-14 bg-white border-b border-[#E2E8F0] flex items-center justify-between px-6">
        <div className="flex items-center gap-2">
          <Shield size={18} className="text-[#0F172A]" />
          <span className="text-sm font-semibold font-['IBM_Plex_Sans'] text-[#0F172A]">Client Portal</span>
        </div>
        {user && (
          <div className="flex items-center gap-3">
            <span className="text-sm text-[#64748B]">{user.email}</span>
            <Button variant="ghost" size="sm" onClick={logout} data-testid="customer-logout-btn">
              <LogOut size={16} />
            </Button>
          </div>
        )}
      </header>
      <main className="max-w-4xl mx-auto py-8 px-4">
        <Outlet />
      </main>
    </div>
  );
}
