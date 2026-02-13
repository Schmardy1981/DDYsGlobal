import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import api from '@/api/client';

export default function EDRPage() {
  const { getActiveTenantId } = useAuth();
  const tenantId = getActiveTenantId();
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (tenantId) {
      api.get(`/edr?tenant_id=${tenantId}`).then(r => setAlerts(r.data)).catch(console.error).finally(() => setLoading(false));
    }
  }, [tenantId]);

  const handleDecide = async (alertId, decision) => {
    try {
      await api.post(`/edr/${alertId}/decide`, { decision });
      api.get(`/edr?tenant_id=${tenantId}`).then(r => setAlerts(r.data));
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  return (
    <div data-testid="edr-page">
      <div className="mb-6">
        <h1 className="text-3xl font-semibold tracking-tight font-['IBM_Plex_Sans']">EDR Alerts</h1>
        <p className="text-sm text-[#64748B] mt-1">Event-Driven Review alerts and decisions</p>
      </div>
      <div className="bg-white border border-[#E2E8F0] rounded-md overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-[#F8FAFC]">
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Trigger</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Detected By</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Review Due</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Completion Due</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Status</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Actions</th>
            </tr>
          </thead>
          <tbody>
            {alerts.map(a => (
              <tr key={a.id} className="border-b hover:bg-[#F8FAFC]">
                <td className="px-4 py-3 text-sm">{a.trigger_event_type?.replace(/_/g, ' ')}</td>
                <td className="px-4 py-3 text-xs text-[#64748B]">{a.detected_by}</td>
                <td className="px-4 py-3 text-xs font-['JetBrains_Mono']">{a.alert_review_due_at?.slice(0,10)}</td>
                <td className="px-4 py-3 text-xs font-['JetBrains_Mono']">{a.completion_due_at?.slice(0,10)}</td>
                <td className="px-4 py-3"><Badge className={a.status === 'open' ? 'bg-amber-100 text-amber-700 border-transparent' : 'bg-green-100 text-green-700 border-transparent'}>{a.status}</Badge></td>
                <td className="px-4 py-3">
                  {a.status === 'open' && (
                    <div className="flex gap-1">
                      <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => handleDecide(a.id, 'edr_full')}>Full EDR</Button>
                      <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => handleDecide(a.id, 'kup')}>KUP</Button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {!alerts.length && <tr><td colSpan={6} className="px-4 py-8 text-center text-sm text-[#64748B]">{loading ? 'Loading...' : 'No EDR alerts'}</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
