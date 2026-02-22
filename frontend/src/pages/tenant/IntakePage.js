import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { UserPlus, Building2, User, MapPin, Mail, Phone, Globe, ArrowRight, XCircle, CheckCircle, Clock, Link2, Copy } from 'lucide-react';
import api from '@/api/client';

const STATUS_COLORS = {
  new: 'bg-blue-100 text-blue-700', reviewed: 'bg-amber-100 text-amber-700',
  assigned: 'bg-green-100 text-green-700', rejected: 'bg-red-100 text-red-700'
};

export default function IntakePage() {
  const navigate = useNavigate();
  const [intakes, setIntakes] = useState([]);
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [assignDialog, setAssignDialog] = useState(null);
  const [selectedTenant, setSelectedTenant] = useState('');
  const [showLink, setShowLink] = useState(false);

  const intakeUrl = `${window.location.origin}/intake`;

  useEffect(() => {
    Promise.all([
      api.get('/intake' + (statusFilter !== 'all' ? `?status=${statusFilter}` : '')),
      api.get('/tenants')
    ]).then(([iRes, tRes]) => {
      setIntakes(iRes.data);
      setTenants(tRes.data);
    }).catch(console.error).finally(() => setLoading(false));
  }, [statusFilter]);

  const handleAssign = async () => {
    if (!assignDialog || !selectedTenant) return;
    try {
      const res = await api.post(`/intake/${assignDialog.id}/assign`, { tenant_id: selectedTenant });
      alert(res.data.message);
      setAssignDialog(null);
      setSelectedTenant('');
      // Reload
      api.get('/intake').then(r => setIntakes(r.data));
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  const handleReject = async (id) => {
    if (!window.confirm('Reject this intake request?')) return;
    try {
      await api.put(`/intake/${id}/reject`, { reason: 'Not eligible' });
      api.get('/intake').then(r => setIntakes(r.data));
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  const copyLink = () => {
    navigator.clipboard.writeText(intakeUrl);
    alert('Link copied!');
  };

  const newCount = intakes.filter(i => i.status === 'new').length;
  const assignedCount = intakes.filter(i => i.status === 'assigned').length;

  return (
    <div data-testid="intake-page">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight font-['IBM_Plex_Sans']">Incoming Clients</h1>
          <p className="text-sm text-[#64748B] mt-1">
            {newCount > 0 ? <><span className="text-blue-600 font-semibold">{newCount} new</span> request{newCount > 1 ? 's' : ''} pending</> : 'Review and assign incoming KYC requests to banks'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setShowLink(true)} data-testid="share-link-btn">
            <Link2 size={14} className="mr-1" /> Share Intake Link
          </Button>
        </div>
      </div>

      {/* Share Link Dialog */}
      <Dialog open={showLink} onOpenChange={setShowLink}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>Client Intake Link</DialogTitle></DialogHeader>
          <div className="space-y-4 pt-2">
            <p className="text-sm text-[#64748B]">Share this link with incoming clients. They fill out their details and specify which bank they need KYC for.</p>
            <div className="flex items-center gap-2">
              <Input value={intakeUrl} readOnly className="font-['JetBrains_Mono'] text-sm flex-1" data-testid="intake-link" />
              <Button variant="outline" onClick={copyLink} data-testid="copy-link-btn"><Copy size={14} /></Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Assign Dialog */}
      <Dialog open={!!assignDialog} onOpenChange={(o) => { if (!o) setAssignDialog(null); }}>
        <DialogContent>
          <DialogHeader><DialogTitle>Assign to Bank</DialogTitle></DialogHeader>
          {assignDialog && (
            <div className="space-y-4 pt-2">
              <div className="p-3 bg-[#F8FAFC] rounded-md space-y-1">
                <p className="text-sm font-semibold">{assignDialog.company_name || `${assignDialog.first_name} ${assignDialog.last_name}`}</p>
                <p className="text-xs text-[#64748B]">Requested bank: <span className="font-medium text-[#0F172A]">{assignDialog.bank_name}</span></p>
                {assignDialog.bank_address && <p className="text-xs text-[#64748B]">{assignDialog.bank_address}, {assignDialog.bank_country}</p>}
              </div>
              <div>
                <p className="text-xs uppercase tracking-wider font-semibold text-[#64748B] mb-1.5">Assign to Tenant</p>
                <Select value={selectedTenant} onValueChange={setSelectedTenant}>
                  <SelectTrigger data-testid="assign-tenant-select"><SelectValue placeholder="Select bank / tenant" /></SelectTrigger>
                  <SelectContent>
                    {tenants.map(t => <SelectItem key={t.id} value={t.id}>{t.name} ({t.default_jurisdiction})</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <Button className="w-full bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleAssign} disabled={!selectedTenant} data-testid="confirm-assign-btn">
                <CheckCircle size={14} className="mr-1" /> Assign & Create Case
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <Tabs value={statusFilter} onValueChange={setStatusFilter} className="w-auto">
          <TabsList>
            <TabsTrigger value="all">All ({intakes.length})</TabsTrigger>
            <TabsTrigger value="new" className="relative">
              New
              {newCount > 0 && <span className="ml-1.5 bg-blue-600 text-white text-[9px] font-bold px-1.5 py-0.5 rounded-full">{newCount}</span>}
            </TabsTrigger>
            <TabsTrigger value="assigned">Assigned ({assignedCount})</TabsTrigger>
            <TabsTrigger value="rejected">Rejected</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Intake List */}
      <div className="space-y-3">
        {intakes.map(i => {
          const isCompany = i.client_type === 'legal_entity';
          const clientName = isCompany ? i.company_name : `${i.first_name} ${i.last_name}`.trim();
          return (
            <Card key={i.id} className={`border-[#E2E8F0] ${i.status === 'new' ? 'border-l-4 border-l-blue-500' : ''}`} data-testid={`intake-${i.id}`}>
              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${isCompany ? 'bg-blue-50' : 'bg-purple-50'}`}>
                      {isCompany ? <Building2 size={20} className="text-blue-600" /> : <User size={20} className="text-purple-600" />}
                    </div>
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-semibold">{clientName || 'Unknown'}</span>
                        <Badge className={`${STATUS_COLORS[i.status]} border-transparent text-[10px]`}>{i.status}</Badge>
                        <Badge variant="outline" className="text-[10px]">{i.client_type?.replace(/_/g, ' ')}</Badge>
                      </div>
                      <div className="grid grid-cols-2 lg:grid-cols-4 gap-x-6 gap-y-1 text-xs text-[#64748B]">
                        {i.email && <span className="flex items-center gap-1"><Mail size={10} /> {i.email}</span>}
                        {i.phone && <span className="flex items-center gap-1"><Phone size={10} /> {i.phone}</span>}
                        {(i.city || i.country) && <span className="flex items-center gap-1"><MapPin size={10} /> {[i.city, i.country].filter(Boolean).join(', ')}</span>}
                        {i.nationality && <span className="flex items-center gap-1"><Globe size={10} /> {i.nationality}</span>}
                      </div>
                      {/* Bank info */}
                      <div className="mt-2 p-2 bg-[#F8FAFC] rounded-md">
                        <span className="text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Requested for Bank:</span>
                        <div className="flex items-center gap-2 mt-0.5">
                          <Building2 size={12} className="text-[#64748B]" />
                          <span className="text-sm font-medium">{i.bank_name || 'Not specified'}</span>
                          {i.bank_country && <Badge variant="outline" className="text-[10px]">{i.bank_country}</Badge>}
                        </div>
                        {i.bank_address && <p className="text-[11px] text-[#64748B] mt-0.5">{i.bank_address}</p>}
                        {i.product_requested && <p className="text-[11px] text-[#64748B]">Product: {i.product_requested}</p>}
                      </div>
                      {i.assigned_tenant_name && (
                        <div className="mt-2 flex items-center gap-1 text-xs text-green-600">
                          <CheckCircle size={12} /> Assigned to: <span className="font-semibold">{i.assigned_tenant_name}</span>
                        </div>
                      )}
                      <p className="text-[10px] text-[#64748B] mt-1 font-['JetBrains_Mono']">Submitted: {new Date(i.created_at).toLocaleString()}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    {i.status === 'new' && (
                      <>
                        <Button size="sm" className="bg-[#0F172A] hover:bg-[#1E293B] h-8 text-xs" onClick={() => setAssignDialog(i)} data-testid={`assign-${i.id}`}>
                          <ArrowRight size={12} className="mr-1" /> Assign
                        </Button>
                        <Button size="sm" variant="ghost" className="h-8 text-xs text-red-500" onClick={() => handleReject(i.id)} data-testid={`reject-${i.id}`}>
                          <XCircle size={12} />
                        </Button>
                      </>
                    )}
                    {i.status === 'assigned' && i.assigned_case_id && (
                      <Button size="sm" variant="outline" className="h-8 text-xs" onClick={() => navigate(`/workspace/case/${i.assigned_case_id}`)} data-testid={`goto-case-${i.id}`}>
                        Open Case <ArrowRight size={12} className="ml-1" />
                      </Button>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
        {!intakes.length && <div className="text-center py-12 text-sm text-[#64748B]">{loading ? 'Loading...' : 'No intake requests yet. Share the intake link with incoming clients.'}</div>}
      </div>
    </div>
  );
}
