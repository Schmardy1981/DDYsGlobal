import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { FolderOpen, Clock, AlertTriangle, Shield, FileWarning, Search } from 'lucide-react';
import api from '@/api/client';

const COLORS = ['#0F172A', '#2563EB', '#D97706', '#DC2626', '#16A34A', '#8B5CF6', '#EC4899'];

export default function MIDashboard() {
  const { getActiveTenantId } = useAuth();
  const tenantId = getActiveTenantId();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (tenantId) {
      api.get(`/mi/dashboard?tenant_id=${tenantId}`).then(r => setData(r.data)).catch(console.error).finally(() => setLoading(false));
    }
  }, [tenantId]);

  if (loading) return <div className="text-sm text-[#64748B]">Loading MI data...</div>;
  if (!data) return <div className="text-sm text-[#64748B]">No data available</div>;

  const pipelineData = Object.entries(data.pipeline || {}).map(([name, value]) => ({ name: name.replace(/_/g, ' '), value }));
  const riskData = Object.entries(data.risk_distribution || {}).filter(([,v]) => v > 0).map(([name, value]) => ({ name, value }));
  const riskColors = { low: '#16A34A', medium: '#D97706', high: '#DC2626', unrated: '#64748B' };

  return (
    <div data-testid="mi-dashboard">
      <div className="mb-6">
        <h1 className="text-3xl font-semibold tracking-tight font-['IBM_Plex_Sans']">Management Information</h1>
        <p className="text-sm text-[#64748B] mt-1">Compliance operations analytics and metrics</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        <MiniCard icon={FolderOpen} label="Total Cases" value={data.total_cases} />
        <MiniCard icon={Clock} label="Overdue NRD" value={data.nrd?.overdue || 0} alert={data.nrd?.overdue > 0} />
        <MiniCard icon={Clock} label="NRD 30d" value={data.nrd?.due_30d || 0} />
        <MiniCard icon={AlertTriangle} label="EDR Open" value={data.edr?.open || 0} alert={data.edr?.open > 0} />
        <MiniCard icon={FileWarning} label="Waivers Pending" value={data.waivers?.pending || 0} />
        <MiniCard icon={Search} label="Hits Open" value={data.screening?.hits_open || 0} alert={data.screening?.hits_open > 0} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <Card className="border-[#E2E8F0]">
          <CardHeader className="pb-2"><CardTitle className="text-sm font-['IBM_Plex_Sans']">Pipeline by Stage</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={pipelineData} layout="vertical">
                <XAxis type="number" />
                <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="value" fill="#0F172A" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="border-[#E2E8F0]">
          <CardHeader className="pb-2"><CardTitle className="text-sm font-['IBM_Plex_Sans']">Risk Distribution</CardTitle></CardHeader>
          <CardContent>
            <div className="flex items-center">
              <ResponsiveContainer width="50%" height={200}>
                <PieChart>
                  <Pie data={riskData} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                    {riskData.map((entry) => <Cell key={entry.name} fill={riskColors[entry.name] || '#64748B'} />)}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-2">
                {riskData.map(d => (
                  <div key={d.name} className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: riskColors[d.name] || '#64748B' }} />
                    <span className="text-sm capitalize">{d.name}: <span className="font-['JetBrains_Mono'] font-medium">{d.value}</span></span>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="border-[#E2E8F0]">
          <CardHeader className="pb-2"><CardTitle className="text-sm font-['IBM_Plex_Sans']">NRD Overview</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            <MetricRow label="Overdue" value={data.nrd?.overdue || 0} alert />
            <MetricRow label="Due in 30 days" value={data.nrd?.due_30d || 0} />
            <MetricRow label="Due in 60 days" value={data.nrd?.due_60d || 0} />
            <MetricRow label="Due in 90 days" value={data.nrd?.due_90d || 0} />
          </CardContent>
        </Card>

        <Card className="border-[#E2E8F0]">
          <CardHeader className="pb-2"><CardTitle className="text-sm font-['IBM_Plex_Sans']">EDR Alerts</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            <MetricRow label="Total" value={data.edr?.total || 0} />
            <MetricRow label="Open" value={data.edr?.open || 0} />
            <MetricRow label="SLA Breached" value={data.edr?.sla_breached || 0} alert />
          </CardContent>
        </Card>

        <Card className="border-[#E2E8F0]">
          <CardHeader className="pb-2"><CardTitle className="text-sm font-['IBM_Plex_Sans']">Screening</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            <MetricRow label="Open Hits" value={data.screening?.hits_open || 0} />
            <MetricRow label="Total Hits" value={data.screening?.hits_total || 0} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function MiniCard({ icon: Icon, label, value, alert }) {
  return (
    <Card className={`border-[#E2E8F0] ${alert ? 'border-l-2 border-l-red-500' : ''}`}>
      <CardContent className="p-3">
        <div className="flex items-center gap-2">
          <Icon size={14} className={alert ? 'text-red-500' : 'text-[#64748B]'} />
          <div>
            <p className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">{label}</p>
            <p className={`text-lg font-semibold font-['JetBrains_Mono'] ${alert ? 'text-red-600' : ''}`}>{value}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function MetricRow({ label, value, alert }) {
  return (
    <div className="flex justify-between items-center py-1">
      <span className="text-xs text-[#64748B]">{label}</span>
      <span className={`text-sm font-['JetBrains_Mono'] font-medium ${alert && value > 0 ? 'text-red-600' : ''}`}>{value}</span>
    </div>
  );
}
