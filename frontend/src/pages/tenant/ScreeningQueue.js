import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import api from '@/api/client';

export default function ScreeningQueue() {
  const { getActiveTenantId } = useAuth();
  const tenantId = getActiveTenantId();
  const [hits, setHits] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (tenantId) {
      api.get(`/screening/hits?tenant_id=${tenantId}`).then(r => setHits(r.data)).catch(console.error).finally(() => setLoading(false));
    }
  }, [tenantId]);

  const handleDispose = async (hitId, disposition) => {
    try {
      await api.put(`/screening/hits/${hitId}`, { disposition, notes: '' });
      setHits(hits.map(h => h.id === hitId ? { ...h, disposition } : h));
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  const severityColor = (s) => {
    if (s === 'high') return 'bg-red-100 text-red-700 border-transparent';
    if (s === 'medium') return 'bg-amber-100 text-amber-700 border-transparent';
    return 'bg-gray-100 text-gray-700 border-transparent';
  };

  return (
    <div data-testid="screening-queue">
      <div className="mb-6">
        <h1 className="text-3xl font-semibold tracking-tight font-['IBM_Plex_Sans']">Screening Hits</h1>
        <p className="text-sm text-[#64748B] mt-1">Review and dispose screening matches</p>
      </div>
      <div className="bg-white border border-[#E2E8F0] rounded-md overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-[#F8FAFC]">
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Matched Name</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">List Source</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Score</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Severity</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Disposition</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Actions</th>
            </tr>
          </thead>
          <tbody>
            {hits.map(h => (
              <tr key={h.id} className="border-b hover:bg-[#F8FAFC]" data-testid={`hit-row-${h.id}`}>
                <td className="px-4 py-3 text-sm font-medium">{h.matched_name}</td>
                <td className="px-4 py-3 text-xs text-[#64748B]">{h.list_source}</td>
                <td className="px-4 py-3 text-sm font-['JetBrains_Mono']">{(h.match_score * 100).toFixed(0)}%</td>
                <td className="px-4 py-3"><Badge className={severityColor(h.hit_severity)}>{h.hit_severity}</Badge></td>
                <td className="px-4 py-3"><Badge variant="outline" className="text-xs capitalize">{h.disposition?.replace(/_/g,' ')}</Badge></td>
                <td className="px-4 py-3">
                  {h.disposition === 'open' && (
                    <div className="flex gap-1">
                      <Button size="sm" variant="ghost" className="h-7 text-xs text-green-600" onClick={() => handleDispose(h.id, 'false_positive')}>False Pos.</Button>
                      <Button size="sm" variant="ghost" className="h-7 text-xs text-red-600" onClick={() => handleDispose(h.id, 'true_match')}>True Match</Button>
                      <Button size="sm" variant="ghost" className="h-7 text-xs text-amber-600" onClick={() => handleDispose(h.id, 'escalated')}>Escalate</Button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {!hits.length && <tr><td colSpan={6} className="px-4 py-8 text-center text-sm text-[#64748B]">{loading ? 'Loading...' : 'No open screening hits'}</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
