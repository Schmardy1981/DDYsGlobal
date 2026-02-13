import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Plus, UserPlus } from 'lucide-react';
import api from '@/api/client';

const ALL_ROLES = [
  'GLOBAL_SUPER_ADMIN', 'DDYS_RCM_MAKER', 'DDYS_RCM_CHECKER',
  'DDYS_QA_FIRST_LINE', 'DDYS_QA_SECOND_LINE', 'DDYS_COMPLIANCE_MANAGER',
  'TENANT_ADMIN', 'TENANT_BUSINESS_USER', 'TENANT_COMPLIANCE_USER', 'TENANT_MLRO',
  'VIDEO_IDENT_AGENT', 'END_CUSTOMER'
];

export default function UsersPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ email: '', name: '', password: '', global_role: '' });

  useEffect(() => { loadUsers(); }, []);

  const loadUsers = () => {
    api.get('/admin/users').then(r => setUsers(r.data)).catch(console.error).finally(() => setLoading(false));
  };

  const handleCreate = async () => {
    try {
      await api.post('/admin/users', form);
      setShowCreate(false);
      setForm({ email: '', name: '', password: '', global_role: '' });
      loadUsers();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed');
    }
  };

  const roleColor = (role) => {
    if (role?.includes('ADMIN')) return 'bg-blue-100 text-blue-700 border-transparent';
    if (role?.includes('MAKER') || role?.includes('CHECKER')) return 'bg-purple-100 text-purple-700 border-transparent';
    if (role?.includes('MLRO')) return 'bg-red-100 text-red-700 border-transparent';
    if (role?.includes('QA')) return 'bg-amber-100 text-amber-700 border-transparent';
    if (role?.includes('COMPLIANCE')) return 'bg-teal-100 text-teal-700 border-transparent';
    return 'bg-gray-100 text-gray-700 border-transparent';
  };

  return (
    <div data-testid="users-page">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight font-['IBM_Plex_Sans']">Users</h1>
          <p className="text-sm text-[#64748B] mt-1">Manage platform users and roles</p>
        </div>
        <Dialog open={showCreate} onOpenChange={setShowCreate}>
          <DialogTrigger asChild>
            <Button className="bg-[#0F172A] hover:bg-[#1E293B]" data-testid="create-user-btn">
              <UserPlus size={16} className="mr-1.5" /> New User
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Create User</DialogTitle></DialogHeader>
            <div className="space-y-4 pt-2">
              <div>
                <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Email</Label>
                <Input className="mt-1.5" value={form.email} onChange={e => setForm({...form, email: e.target.value})} data-testid="user-email-input" />
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Name</Label>
                <Input className="mt-1.5" value={form.name} onChange={e => setForm({...form, name: e.target.value})} data-testid="user-name-input" />
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Password</Label>
                <Input className="mt-1.5" type="password" value={form.password} onChange={e => setForm({...form, password: e.target.value})} data-testid="user-password-input" />
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Role</Label>
                <Select value={form.global_role} onValueChange={v => setForm({...form, global_role: v})}>
                  <SelectTrigger className="mt-1.5" data-testid="user-role-select">
                    <SelectValue placeholder="Select role" />
                  </SelectTrigger>
                  <SelectContent>
                    {ALL_ROLES.map(r => <SelectItem key={r} value={r}>{r.replace(/_/g, ' ')}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <Button className="w-full bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleCreate} data-testid="submit-user-btn">Create User</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="bg-white border border-[#E2E8F0] rounded-md overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-[#F8FAFC]">
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Name</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Email</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Global Role</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">MFA</th>
              <th className="h-10 px-4 text-left text-[11px] uppercase tracking-wider font-semibold text-[#64748B]">Status</th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id} className="border-b hover:bg-[#F8FAFC] transition-colors" data-testid={`user-row-${u.id}`}>
                <td className="px-4 py-3 text-sm font-medium">{u.name}</td>
                <td className="px-4 py-3 text-sm text-[#64748B] font-['JetBrains_Mono'] text-xs">{u.email}</td>
                <td className="px-4 py-3"><Badge className={roleColor(u.global_role)}>{u.global_role?.replace(/_/g, ' ')}</Badge></td>
                <td className="px-4 py-3"><Badge className={u.mfa_enabled ? 'bg-green-100 text-green-700 border-transparent' : 'bg-gray-100 text-gray-500 border-transparent'}>{u.mfa_enabled ? 'Enabled' : 'Off'}</Badge></td>
                <td className="px-4 py-3"><Badge className={u.status === 'active' ? 'bg-green-100 text-green-700 border-transparent' : 'bg-red-100 text-red-700 border-transparent'}>{u.status}</Badge></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
