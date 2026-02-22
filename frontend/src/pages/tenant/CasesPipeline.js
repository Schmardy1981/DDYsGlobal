import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Plus, FolderOpen, Filter, ArrowUpDown } from 'lucide-react';
import api from '@/api/client';

const STATUS_COLORS = {
  draft: 'bg-gray-100 text-gray-700', customer_in_progress: 'bg-blue-100 text-blue-700',
  customer_submitted: 'bg-indigo-100 text-indigo-700', automated_checks: 'bg-purple-100 text-purple-700',
  maker_review: 'bg-amber-100 text-amber-700', checker_review: 'bg-orange-100 text-orange-700',
  business_approval: 'bg-cyan-100 text-cyan-700', compliance_approval: 'bg-teal-100 text-teal-700',
  mlro_approval: 'bg-pink-100 text-pink-700', completed: 'bg-green-100 text-green-700',
  restricted: 'bg-red-100 text-red-700', rejected: 'bg-red-100 text-red-700', offboarded: 'bg-gray-100 text-gray-700'
};

const ALL_STATUSES = ['draft','customer_in_progress','customer_submitted','automated_checks','maker_review','checker_review','business_approval','compliance_approval','mlro_approval','completed','restricted','rejected','offboarded'];

const RISK_COLORS = { low: 'bg-green-100 text-green-700', medium: 'bg-amber-100 text-amber-700', high: 'bg-red-100 text-red-700' };

export default function CasesPipeline() {
  const { getActiveTenantId } = useAuth();
  const navigate = useNavigate();
  const tenantId = getActiveTenantId();
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [riskFilter, setRiskFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [newCase, setNewCase] = useState({ case_type: 'onboarding', jurisdiction: 'EU', product_scope: '' });

  useEffect(() => {
    let url = '/cases';
    const params = [];
    if (tenantId) params.push(`tenant_id=${tenantId}`);
    if (statusFilter !== 'all') params.push(`status=${statusFilter}`);
    if (riskFilter !== 'all') params.push(`risk_rating=${riskFilter}`);
    if (typeFilter !== 'all') params.push(`case_type=${typeFilter}`);
    if (params.length) url += '?' + params.join('&');
    api.get(url).then(r => setCases(r.data)).catch(console.error).finally(() => setLoading(false));
  }, [tenantId, statusFilter, riskFilter, typeFilter]);

  const handleStatusChange = async (caseId, newStatus, e) => {
    e.stopPropagation();
    try {
      await api.put(`/cases/${caseId}/status`, { status: newStatus });
      // Reload
      let url = '/cases';
      const params = [];
      if (tenantId) params.push(`tenant_id=${tenantId}`);
      if (statusFilter !== 'all') params.push(`status=${statusFilter}`);
      if (riskFilter !== 'all') params.push(`risk_rating=${riskFilter}`);
      if (typeFilter !== 'all') params.push(`case_type=${typeFilter}`);
      if (params.length) url += '?' + params.join('&');
      api.get(url).then(r => setCases(r.data));
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  const handleCreate = async () => {
    try {
      const tid = tenantId || (await api.get('/tenants').then(r => r.data[0]?.id));
      if (!tid) { alert('No tenant available'); return; }
      const res = await api.post('/cases', { tenant_id: tid, ...newCase });
      setShowCreate(false);
      navigate(`/workspace/case/${res.data.id}`);
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  const filtered = cases.filter(c => {
    if (!search) return true;
    const s = search.toLowerCase();
    return c.case_ref?.toLowerCase().includes(s) || c.jurisdiction?.toLowerCase().includes(s);
  });

  return (
    <div data-testid="cases-pipeline">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight font-['IBM_Plex_Sans']">Cases Pipeline</h1>
          <p className="text-sm text-[#64748B] mt-1">{filtered.length} case{filtered.length !== 1 ? 's' : ''}</p>
        </div>
        <Dialog open={showCreate} onOpenChange={setShowCreate}>
          <DialogTrigger asChild>
            <Button className="bg-[#0F172A] hover:bg-[#1E293B]" data-testid="create-case-btn"><Plus size={16} className="mr-1.5" /> New Case</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Create New Case</DialogTitle></DialogHeader>
            <div className="space-y-4 pt-2">
              <div>
                <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Case Type</Label>
                <Select value={newCase.case_type} onValueChange={v => setNewCase({...newCase, case_type: v})}>
                  <SelectTrigger className="mt-1.5"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="onboarding">Onboarding</SelectItem>
                    <SelectItem value="rr">Regular Review</SelectItem>
                    <SelectItem value="edr_full">Full EDR</SelectItem>
                    <SelectItem value="kup">KYC Update (KUP)</SelectItem>
                    <SelectItem value="npe">New Product Extension</SelectItem>
                    <SelectItem value="exit">Client Exit</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Jurisdiction</Label>
                <Input className="mt-1.5" value={newCase.jurisdiction} onChange={e => setNewCase({...newCase, jurisdiction: e.target.value})} />
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Product Scope</Label>
                <Input className="mt-1.5" value={newCase.product_scope} onChange={e => setNewCase({...newCase, product_scope: e.target.value})} placeholder="e.g. Corporate Banking" />
              </div>
              <Button className="w-full bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleCreate} data-testid="submit-case-btn">Create Case</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <Input placeholder="Search cases..." value={search} onChange={e => setSearch(e.target.value)} className="w-64" data-testid="case-search" />
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-44"><SelectValue placeholder="Status" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            {Object.keys(STATUS_COLORS).map(s => <SelectItem key={s} value={s}>{s.replace(/_/g, ' ')}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={riskFilter} onValueChange={setRiskFilter}>
          <SelectTrigger className="w-36"><SelectValue placeholder="Risk" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Risk</SelectItem>
            <SelectItem value="low">Low</SelectItem>
            <SelectItem value="medium">Medium</SelectItem>
            <SelectItem value="high">High</SelectItem>
          </SelectContent>
        </Select>
        <Select value={typeFilter} onValueChange={setTypeFilter}>
          <SelectTrigger className="w-44"><SelectValue placeholder="Type" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            <SelectItem value="onboarding">Onboarding</SelectItem>
            <SelectItem value="rr">Regular Review</SelectItem>
            <SelectItem value="edr_full">Full EDR</SelectItem>
            <SelectItem value="kup">KUP</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="bg-white border border-[#E2E8F0] rounded-md overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-[#F8FAFC]">
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Case Ref</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Type</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Status</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Risk</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">DD Level</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Jurisdiction</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">NRD</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Created</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(c => (
              <tr key={c.id} className="border-b hover:bg-[#F8FAFC] transition-colors cursor-pointer" onClick={() => navigate(`/workspace/case/${c.id}`)} data-testid={`case-row-${c.id}`}>
                <td className="px-4 py-3 text-sm font-medium font-['JetBrains_Mono']">{c.case_ref}</td>
                <td className="px-4 py-3"><Badge variant="outline" className="text-xs capitalize">{c.case_type?.replace(/_/g, ' ')}</Badge></td>
                <td className="px-4 py-3"><Badge className={`${STATUS_COLORS[c.status] || ''} border-transparent text-xs`}>{c.status?.replace(/_/g, ' ')}</Badge></td>
                <td className="px-4 py-3">{c.risk_rating ? <Badge className={`${RISK_COLORS[c.risk_rating] || ''} border-transparent text-xs capitalize`}>{c.risk_rating}</Badge> : <span className="text-xs text-[#64748B]">-</span>}</td>
                <td className="px-4 py-3 text-xs uppercase font-['JetBrains_Mono'] text-[#64748B]">{c.due_diligence_level || '-'}</td>
                <td className="px-4 py-3 text-xs font-['JetBrains_Mono']">{c.jurisdiction}</td>
                <td className="px-4 py-3 text-xs font-['JetBrains_Mono'] text-[#64748B]">{c.nrd_date?.slice(0,10) || '-'}</td>
                <td className="px-4 py-3 text-xs font-['JetBrains_Mono'] text-[#64748B]">{c.created_at?.slice(0,10)}</td>
              </tr>
            ))}
            {!filtered.length && <tr><td colSpan={8} className="px-4 py-8 text-center text-sm text-[#64748B]">{loading ? 'Loading...' : 'No cases found'}</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
