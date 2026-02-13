import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import api from '@/api/client';

export default function WaiversPage() {
  const { getActiveTenantId } = useAuth();
  const tenantId = getActiveTenantId();
  const [waivers, setWaivers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (tenantId) {
      api.get(`/waivers?tenant_id=${tenantId}`).then(r => setWaivers(r.data)).catch(console.error).finally(() => setLoading(false));
    }
  }, [tenantId]);

  const handleApprove = async (id, decision) => {
    try {
      await api.put(`/waivers/${id}/approve`, { decision, notes: '' });
      const updated = await api.get(`/waivers?tenant_id=${tenantId}`);
      setWaivers(updated.data);
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  return (
    <div data-testid="waivers-page">
      <div className="mb-6">
        <h1 className="text-3xl font-semibold tracking-tight font-['IBM_Plex_Sans']">Waivers</h1>
        <p className="text-sm text-[#64748B] mt-1">Policy waiver requests and approvals</p>
      </div>
      <div className="bg-white border border-[#E2E8F0] rounded-md overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-[#F8FAFC]">
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Type</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Requirements</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Justification</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Status</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Expires</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Actions</th>
            </tr>
          </thead>
          <tbody>
            {waivers.map(w => (
              <tr key={w.id} className="border-b hover:bg-[#F8FAFC]">
                <td className="px-4 py-3"><Badge variant="outline" className="text-xs capitalize">{w.waiver_type}</Badge></td>
                <td className="px-4 py-3 text-xs text-[#64748B]">{(w.requirement_keys_json || []).join(', ')}</td>
                <td className="px-4 py-3 text-sm max-w-xs truncate">{w.justification}</td>
                <td className="px-4 py-3"><Badge className={w.status === 'approved' ? 'bg-green-100 text-green-700 border-transparent' : w.status === 'rejected' ? 'bg-red-100 text-red-700 border-transparent' : 'bg-amber-100 text-amber-700 border-transparent'}>{w.status}</Badge></td>
                <td className="px-4 py-3 text-xs font-['JetBrains_Mono'] text-[#64748B]">{w.expires_at?.slice(0,10) || 'N/A'}</td>
                <td className="px-4 py-3">
                  {w.status === 'pending' && (
                    <div className="flex gap-1">
                      <Button size="sm" variant="ghost" className="h-7 text-xs text-green-600" onClick={() => handleApprove(w.id, 'approved')}>Approve</Button>
                      <Button size="sm" variant="ghost" className="h-7 text-xs text-red-600" onClick={() => handleApprove(w.id, 'rejected')}>Reject</Button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {!waivers.length && <tr><td colSpan={6} className="px-4 py-8 text-center text-sm text-[#64748B]">{loading ? 'Loading...' : 'No waivers'}</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
