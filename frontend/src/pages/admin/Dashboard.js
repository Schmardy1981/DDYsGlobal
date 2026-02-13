import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Building2, Users, FolderOpen, AlertTriangle, Shield, Activity } from 'lucide-react';
import api from '@/api/client';

export default function AdminDashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/mi/global').then(r => setStats(r.data)).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex items-center justify-center h-64 text-[#64748B] text-sm">Loading dashboard...</div>;

  return (
    <div data-testid="admin-dashboard">
      <div className="mb-6">
        <h1 className="text-3xl font-semibold tracking-tight font-['IBM_Plex_Sans']">Platform Overview</h1>
        <p className="text-sm text-[#64748B] mt-1">Global compliance operations dashboard</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard icon={Building2} label="Total Tenants" value={stats?.total_tenants || 0} />
        <MetricCard icon={FolderOpen} label="Total Cases" value={stats?.total_cases || 0} />
        <MetricCard icon={Activity} label="System Status" value={stats?.system_health?.status || 'N/A'} isText />
        <MetricCard icon={Shield} label="Uptime" value={stats?.system_health?.uptime || 'N/A'} isText />
      </div>

      <div className="mb-6">
        <h2 className="text-lg font-medium font-['IBM_Plex_Sans'] mb-3">Tenant Overview</h2>
        <div className="bg-white border border-[#E2E8F0] rounded-md overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b bg-[#F8FAFC]">
                <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Tenant</th>
                <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Total Cases</th>
                <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Active Cases</th>
                <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Status</th>
              </tr>
            </thead>
            <tbody>
              {(stats?.tenant_stats || []).map(t => (
                <tr key={t.tenant_id} className="border-b hover:bg-[#F8FAFC] transition-colors" data-testid={`tenant-row-${t.tenant_id}`}>
                  <td className="px-4 py-3 text-sm font-medium">{t.tenant_name}</td>
                  <td className="px-4 py-3 text-sm font-['JetBrains_Mono']">{t.total_cases}</td>
                  <td className="px-4 py-3 text-sm font-['JetBrains_Mono']">{t.active_cases}</td>
                  <td className="px-4 py-3">
                    <Badge className={t.status === 'active' ? 'bg-green-100 text-green-700 border-transparent' : 'bg-gray-100 text-gray-700 border-transparent'}>
                      {t.status}
                    </Badge>
                  </td>
                </tr>
              ))}
              {(!stats?.tenant_stats?.length) && (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-sm text-[#64748B]">No tenants yet. Create one to get started.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ icon: Icon, label, value, isText }) {
  return (
    <Card className="border-[#E2E8F0] shadow-sm">
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">{label}</p>
            <p className={`mt-1 ${isText ? 'text-lg font-medium capitalize' : 'text-2xl font-semibold font-["JetBrains_Mono"]'}`}>{value}</p>
          </div>
          <div className="w-10 h-10 rounded-md bg-[#F1F5F9] flex items-center justify-center">
            <Icon size={18} className="text-[#64748B]" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
