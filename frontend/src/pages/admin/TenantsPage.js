import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Plus, Building2 } from 'lucide-react';
import api from '@/api/client';

export default function TenantsPage() {
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: '', legal_name: '', default_jurisdiction: 'EU' });

  useEffect(() => { loadTenants(); }, []);

  const loadTenants = () => {
    api.get('/tenants').then(r => setTenants(r.data)).catch(console.error).finally(() => setLoading(false));
  };

  const handleCreate = async () => {
    try {
      await api.post('/tenants', form);
      setShowCreate(false);
      setForm({ name: '', legal_name: '', default_jurisdiction: 'EU' });
      loadTenants();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to create tenant');
    }
  };

  return (
    <div data-testid="tenants-page">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight font-['IBM_Plex_Sans']">Tenants</h1>
          <p className="text-sm text-[#64748B] mt-1">Manage financial institution tenants</p>
        </div>
        <Dialog open={showCreate} onOpenChange={setShowCreate}>
          <DialogTrigger asChild>
            <Button className="bg-[#0F172A] hover:bg-[#1E293B]" data-testid="create-tenant-btn">
              <Plus size={16} className="mr-1.5" /> New Tenant
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Create Tenant</DialogTitle></DialogHeader>
            <div className="space-y-4 pt-2">
              <div>
                <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Name</Label>
                <Input className="mt-1.5" value={form.name} onChange={e => setForm({...form, name: e.target.value})} placeholder="e.g. Acme Bank" data-testid="tenant-name-input" />
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Legal Name</Label>
                <Input className="mt-1.5" value={form.legal_name} onChange={e => setForm({...form, legal_name: e.target.value})} placeholder="e.g. Acme Bank AG" data-testid="tenant-legal-name-input" />
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Default Jurisdiction</Label>
                <Input className="mt-1.5" value={form.default_jurisdiction} onChange={e => setForm({...form, default_jurisdiction: e.target.value})} placeholder="EU" data-testid="tenant-jurisdiction-input" />
              </div>
              <Button className="w-full bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleCreate} data-testid="submit-tenant-btn">Create Tenant</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="bg-white border border-[#E2E8F0] rounded-md overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-[#F8FAFC]">
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Name</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Legal Name</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Jurisdiction</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Status</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Created</th>
            </tr>
          </thead>
          <tbody>
            {tenants.map(t => (
              <tr key={t.id} className="border-b hover:bg-[#F8FAFC] transition-colors cursor-pointer" data-testid={`tenant-row-${t.id}`}>
                <td className="px-4 py-3 text-sm font-medium flex items-center gap-2">
                  <Building2 size={14} className="text-[#64748B]" />{t.name}
                </td>
                <td className="px-4 py-3 text-sm text-[#64748B]">{t.legal_name}</td>
                <td className="px-4 py-3 text-sm"><Badge variant="outline" className="font-['JetBrains_Mono'] text-xs">{t.default_jurisdiction}</Badge></td>
                <td className="px-4 py-3"><Badge className={t.status === 'active' ? 'bg-green-100 text-green-700 border-transparent' : 'bg-gray-100'}>{t.status}</Badge></td>
                <td className="px-4 py-3 text-xs text-[#64748B] font-['JetBrains_Mono']">{t.created_at?.slice(0,10)}</td>
              </tr>
            ))}
            {!tenants.length && <tr><td colSpan={5} className="px-4 py-8 text-center text-sm text-[#64748B]">{loading ? 'Loading...' : 'No tenants found'}</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
