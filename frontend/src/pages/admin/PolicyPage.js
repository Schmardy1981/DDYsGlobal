import { useState, useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import api from '@/api/client';

export default function PolicyPage() {
  const [versions, setVersions] = useState([]);
  const [rules, setRules] = useState([]);

  useEffect(() => {
    api.get('/policy/versions').then(r => setVersions(r.data)).catch(() => {});
    api.get('/policy/rules').then(r => setRules(r.data)).catch(() => {});
  }, []);

  return (
    <div data-testid="policy-page">
      <div className="mb-6">
        <h1 className="text-3xl font-semibold tracking-tight font-['IBM_Plex_Sans']">Policy Management</h1>
        <p className="text-sm text-[#64748B] mt-1">KOS v1.11 baseline and tenant policy versions</p>
      </div>

      <div className="mb-6">
        <h2 className="text-lg font-medium font-['IBM_Plex_Sans'] mb-3">Policy Versions</h2>
        <div className="bg-white border border-[#E2E8F0] rounded-md overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b bg-[#F8FAFC]">
                <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Version</th>
                <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">KOS Base</th>
                <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Status</th>
                <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Effective From</th>
              </tr>
            </thead>
            <tbody>
              {versions.map(v => (
                <tr key={v.id} className="border-b hover:bg-[#F8FAFC]">
                  <td className="px-4 py-3 text-sm font-medium">{v.version_name}</td>
                  <td className="px-4 py-3 text-sm font-['JetBrains_Mono']">{v.based_on_kos_version}</td>
                  <td className="px-4 py-3"><Badge className={v.status === 'active' ? 'bg-green-100 text-green-700 border-transparent' : 'bg-gray-100'}>{v.status}</Badge></td>
                  <td className="px-4 py-3 text-xs font-['JetBrains_Mono'] text-[#64748B]">{v.effective_from?.slice(0,10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <h2 className="text-lg font-medium font-['IBM_Plex_Sans'] mb-3">Active Policy Rules</h2>
        <div className="bg-white border border-[#E2E8F0] rounded-md overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b bg-[#F8FAFC]">
                <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Rule Key</th>
                <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Value</th>
                <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Scope</th>
                <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Status</th>
              </tr>
            </thead>
            <tbody>
              {rules.map(r => (
                <tr key={r.id} className="border-b hover:bg-[#F8FAFC]">
                  <td className="px-4 py-3 text-sm font-medium font-['JetBrains_Mono']">{r.rule_key}</td>
                  <td className="px-4 py-3 text-xs font-['JetBrains_Mono'] text-[#64748B]">{JSON.stringify(r.rule_value_json)}</td>
                  <td className="px-4 py-3"><Badge variant="outline" className="text-xs">{r.scope}</Badge></td>
                  <td className="px-4 py-3"><Badge className={r.enabled ? 'bg-green-100 text-green-700 border-transparent' : 'bg-gray-100'}>
                    {r.enabled ? 'Active' : 'Disabled'}
                  </Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
