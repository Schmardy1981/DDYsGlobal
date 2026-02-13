import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Settings } from 'lucide-react';

export default function TenantSettings() {
  const { getActiveTenantId } = useAuth();
  const tenantId = getActiveTenantId();

  return (
    <div data-testid="tenant-settings">
      <div className="mb-6">
        <h1 className="text-3xl font-semibold tracking-tight font-['IBM_Plex_Sans']">Tenant Settings</h1>
        <p className="text-sm text-[#64748B] mt-1">Configure tenant-specific settings</p>
      </div>
      <Card className="border-[#E2E8F0]">
        <CardHeader><CardTitle className="text-base font-['IBM_Plex_Sans'] flex items-center gap-2"><Settings size={16} /> Configuration</CardTitle></CardHeader>
        <CardContent>
          <p className="text-sm text-[#64748B]">Tenant ID: <span className="font-['JetBrains_Mono']">{tenantId || 'None selected'}</span></p>
          <p className="text-sm text-[#64748B] mt-2">Branding, policy rules, connectors, and user management will be configurable here. Select a tenant from the top bar to manage settings.</p>
        </CardContent>
      </Card>
    </div>
  );
}
