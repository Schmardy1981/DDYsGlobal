import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Settings, Globe, FileText, Plus, Trash2, Shield, Scale } from 'lucide-react';
import api from '@/api/client';

const FRAMEWORKS = ['MiCAR', 'SEC', 'FMA (Liechtenstein)', 'FINMA (Switzerland)', 'BaFin (Germany)', 'FCA (UK)', 'MAS (Singapore)', 'VARA (Dubai)', 'CSSF (Luxembourg)', 'Other'];
const JURISDICTIONS = ['EU', 'US', 'CH', 'LI', 'DE', 'UK', 'SG', 'AE', 'LU', 'Other'];

export default function TenantSettings() {
  const { getActiveTenantId } = useAuth();
  const tenantId = getActiveTenantId();
  const [tenant, setTenant] = useState(null);
  const [regulations, setRegulations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('general');
  const [showAddReg, setShowAddReg] = useState(false);
  const [regForm, setRegForm] = useState({ framework: '', jurisdiction: '', description: '', required_documents: '' });

  useEffect(() => { if (tenantId) loadData(); }, [tenantId]);

  const loadData = () => {
    Promise.all([
      api.get(`/tenants/${tenantId}`),
      api.get(`/tenants/${tenantId}/regulations`)
    ]).then(([tRes, rRes]) => {
      setTenant(tRes.data);
      setRegulations(rRes.data);
    }).catch(console.error).finally(() => setLoading(false));
  };

  const handleAddRegulation = async () => {
    try {
      const docs = regForm.required_documents.split('\n').filter(Boolean).map(d => d.trim());
      await api.post(`/tenants/${tenantId}/regulations`, {
        ...regForm,
        required_documents: docs,
        rules_json: {}
      });
      setShowAddReg(false);
      setRegForm({ framework: '', jurisdiction: '', description: '', required_documents: '' });
      loadData();
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  const handleDeleteReg = async (regId) => {
    if (!window.confirm('Delete this regulation?')) return;
    try {
      await api.delete(`/tenants/${tenantId}/regulations/${regId}`);
      loadData();
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  if (!tenantId) return <div className="text-sm text-[#64748B]">Select a tenant from the top bar.</div>;
  if (loading) return <div className="text-sm text-[#64748B]">Loading...</div>;

  return (
    <div data-testid="tenant-settings">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight font-['IBM_Plex_Sans']">Tenant Settings</h1>
          <p className="text-sm text-[#64748B] mt-1">{tenant?.name} ({tenant?.legal_name})</p>
        </div>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="mb-4">
          <TabsTrigger value="general"><Settings size={14} className="mr-1" /> General</TabsTrigger>
          <TabsTrigger value="regulations"><Scale size={14} className="mr-1" /> Regulatory Frameworks</TabsTrigger>
        </TabsList>

        <TabsContent value="general">
          <Card className="border-[#E2E8F0]">
            <CardContent className="p-5 space-y-3">
              <div className="grid grid-cols-2 gap-4">
                <div><Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Name</Label><p className="text-sm font-medium mt-1">{tenant?.name}</p></div>
                <div><Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Legal Name</Label><p className="text-sm font-medium mt-1">{tenant?.legal_name}</p></div>
                <div><Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Default Jurisdiction</Label><p className="text-sm font-medium mt-1">{tenant?.default_jurisdiction}</p></div>
                <div><Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Status</Label><Badge className="mt-1 bg-green-100 text-green-700 border-transparent">{tenant?.status}</Badge></div>
                <div><Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Tenant ID</Label><p className="text-xs font-['JetBrains_Mono'] text-[#64748B] mt-1">{tenantId}</p></div>
                <div><Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Created</Label><p className="text-xs font-['JetBrains_Mono'] text-[#64748B] mt-1">{tenant?.created_at?.slice(0,10)}</p></div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="regulations">
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm text-[#64748B]">Define which regulatory frameworks this bank operates under. Each framework can require specific documents.</p>
            <Dialog open={showAddReg} onOpenChange={setShowAddReg}>
              <DialogTrigger asChild>
                <Button size="sm" className="bg-[#0F172A] hover:bg-[#1E293B]" data-testid="add-regulation-btn"><Plus size={14} className="mr-1" /> Add Framework</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader><DialogTitle>Add Regulatory Framework</DialogTitle></DialogHeader>
                <div className="space-y-4 pt-2">
                  <div>
                    <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Framework</Label>
                    <Select value={regForm.framework} onValueChange={v => setRegForm({...regForm, framework: v})}>
                      <SelectTrigger className="mt-1.5"><SelectValue placeholder="Select framework" /></SelectTrigger>
                      <SelectContent>{FRAMEWORKS.map(f => <SelectItem key={f} value={f}>{f}</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Jurisdiction</Label>
                    <Select value={regForm.jurisdiction} onValueChange={v => setRegForm({...regForm, jurisdiction: v})}>
                      <SelectTrigger className="mt-1.5"><SelectValue placeholder="Select jurisdiction" /></SelectTrigger>
                      <SelectContent>{JURISDICTIONS.map(j => <SelectItem key={j} value={j}>{j}</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Description</Label>
                    <Textarea className="mt-1.5" value={regForm.description} onChange={e => setRegForm({...regForm, description: e.target.value})} placeholder="e.g. Markets in Crypto-Assets Regulation for EU operations" rows={2} />
                  </div>
                  <div>
                    <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Required Documents (one per line)</Label>
                    <Textarea className="mt-1.5 font-['JetBrains_Mono'] text-sm" value={regForm.required_documents} onChange={e => setRegForm({...regForm, required_documents: e.target.value})} placeholder={"Proof of Identity\nProof of Address\nSource of Funds\nCorporate Registry Extract"} rows={6} />
                  </div>
                  <Button className="w-full bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleAddRegulation} data-testid="submit-regulation-btn">Add Framework</Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>

          {regulations.length === 0 && (
            <Card className="border-[#E2E8F0] border-dashed"><CardContent className="p-8 text-center text-sm text-[#64748B]">No regulatory frameworks configured. Add one to define compliance requirements.</CardContent></Card>
          )}

          <div className="space-y-3">
            {regulations.map(reg => (
              <Card key={reg.id} className="border-[#E2E8F0] border-l-4 border-l-blue-500" data-testid={`regulation-${reg.id}`}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <Scale size={16} className="text-blue-600" />
                        <span className="text-sm font-semibold">{reg.framework}</span>
                        <Badge variant="outline" className="text-xs">{reg.jurisdiction}</Badge>
                        <Badge className={reg.active ? 'bg-green-100 text-green-700 border-transparent text-[10px]' : 'bg-gray-100 text-gray-500 border-transparent text-[10px]'}>{reg.active ? 'Active' : 'Inactive'}</Badge>
                      </div>
                      {reg.description && <p className="text-xs text-[#64748B] mb-2">{reg.description}</p>}
                      {reg.required_documents?.length > 0 && (
                        <div>
                          <p className="text-[10px] text-[#64748B] uppercase tracking-wider mb-1">Required Documents:</p>
                          <div className="flex flex-wrap gap-1">
                            {reg.required_documents.map((doc, i) => (
                              <Badge key={i} variant="outline" className="text-xs font-normal">{doc}</Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                    <Button size="sm" variant="ghost" className="text-red-400 hover:text-red-600 h-7" onClick={() => handleDeleteReg(reg.id)} data-testid={`delete-reg-${reg.id}`}>
                      <Trash2 size={14} />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
