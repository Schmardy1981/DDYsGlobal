import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Brain, Sparkles, Fingerprint, ShieldCheck, Search, Mail, Database, Key, Plug, Check, X, ChevronRight, Zap } from 'lucide-react';
import api from '@/api/client';

const ICON_MAP = {
  brain: Brain,
  sparkles: Sparkles,
  fingerprint: Fingerprint,
  'shield-check': ShieldCheck,
  search: Search,
  mail: Mail,
  database: Database,
  key: Key,
};

const CAT_ORDER = ['AI / LLM', 'Identity Verification', 'Screening', 'Email', 'Storage'];

export default function IntegrationsPage() {
  const [integrations, setIntegrations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editKey, setEditKey] = useState(null);
  const [editValues, setEditValues] = useState({});
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(null);

  useEffect(() => { loadIntegrations(); }, []);

  const loadIntegrations = () => {
    api.get('/integrations').then(r => setIntegrations(r.data)).catch(console.error).finally(() => setLoading(false));
  };

  const handleToggle = async (key, enabled) => {
    try {
      await api.put(`/integrations/${key}`, { enabled });
      loadIntegrations();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed');
    }
  };

  const openEdit = (integ) => {
    const vals = {};
    integ.fields.forEach(f => {
      vals[f.key] = integ.configured_fields?.[f.key] || '';
    });
    setEditValues(vals);
    setEditKey(integ.key);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      // Clean masked values
      const cleanVals = {};
      Object.entries(editValues).forEach(([k, v]) => {
        if (v !== '***configured***') cleanVals[k] = v;
      });
      await api.put(`/integrations/${editKey}`, { values: cleanVals, enabled: true });
      setEditKey(null);
      loadIntegrations();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed');
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async (key) => {
    setTesting(key);
    try {
      const res = await api.post(`/integrations/${key}/test`);
      alert(res.data.message);
      loadIntegrations();
    } catch (err) {
      alert(err.response?.data?.detail || 'Test failed');
    } finally {
      setTesting(null);
    }
  };

  // Group by category
  const grouped = {};
  CAT_ORDER.forEach(cat => { grouped[cat] = []; });
  integrations.forEach(i => {
    if (!grouped[i.category]) grouped[i.category] = [];
    grouped[i.category].push(i);
  });

  const editInteg = integrations.find(i => i.key === editKey);

  if (loading) return <div className="text-sm text-[#64748B]">Loading integrations...</div>;

  return (
    <div data-testid="integrations-page">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight font-['IBM_Plex_Sans']">Integrations</h1>
          <p className="text-sm text-[#64748B] mt-1">Manage API connections and service providers</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge className="bg-green-100 text-green-700 border-transparent">
            {integrations.filter(i => i.connected).length} Connected
          </Badge>
          <Badge variant="outline">{integrations.length} Total</Badge>
        </div>
      </div>

      {/* Edit Dialog */}
      <Dialog open={!!editKey} onOpenChange={(open) => { if (!open) setEditKey(null); }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-['IBM_Plex_Sans'] flex items-center gap-2">
              <Plug size={18} />
              Configure: {editInteg?.name}
            </DialogTitle>
          </DialogHeader>
          {editInteg && (
            <div className="space-y-4 pt-2">
              <p className="text-sm text-[#64748B]">{editInteg.description}</p>
              {editInteg.fields.map(field => (
                <div key={field.key}>
                  <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">{field.label}</Label>
                  <Input
                    className="mt-1.5 font-['JetBrains_Mono'] text-sm"
                    type={field.type === 'password' ? 'password' : 'text'}
                    value={editValues[field.key] || ''}
                    onChange={e => setEditValues({...editValues, [field.key]: e.target.value})}
                    placeholder={field.placeholder}
                    data-testid={`integ-field-${field.key}`}
                  />
                </div>
              ))}
              <div className="flex gap-2">
                <Button className="flex-1 bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleSave} disabled={saving} data-testid="save-integration-btn">
                  {saving ? 'Saving...' : 'Save & Enable'}
                </Button>
                <Button variant="outline" onClick={() => setEditKey(null)}>Cancel</Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Integration Cards by Category */}
      {CAT_ORDER.map(cat => {
        const items = grouped[cat] || [];
        if (!items.length) return null;

        return (
          <div key={cat} className="mb-8">
            <h2 className="text-sm font-semibold text-[#64748B] uppercase tracking-wider mb-3">{cat}</h2>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              {items.map(integ => {
                const Icon = ICON_MAP[integ.icon] || Plug;
                return (
                  <Card key={integ.key} className={`border-[#E2E8F0] transition-all ${integ.connected ? 'border-l-2 border-l-green-500' : ''}`} data-testid={`integration-${integ.key}`}>
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-3">
                          <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${integ.connected ? 'bg-green-50' : 'bg-[#F1F5F9]'}`}>
                            <Icon size={20} className={integ.connected ? 'text-green-600' : 'text-[#64748B]'} />
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium">{integ.name}</span>
                              {integ.connected ? (
                                <Badge className="bg-green-100 text-green-700 border-transparent text-[10px]">Connected</Badge>
                              ) : integ.enabled ? (
                                <Badge className="bg-amber-100 text-amber-700 border-transparent text-[10px]">Enabled (No Key)</Badge>
                              ) : (
                                <Badge className="bg-gray-100 text-gray-500 border-transparent text-[10px]">Disabled</Badge>
                              )}
                            </div>
                            <p className="text-xs text-[#64748B] mt-1">{integ.description}</p>
                            {integ.last_tested && (
                              <p className="text-[10px] text-[#64748B] mt-1 font-['JetBrains_Mono']">
                                Last tested: {new Date(integ.last_tested).toLocaleString()}
                              </p>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <Switch
                            checked={integ.enabled}
                            onCheckedChange={(checked) => handleToggle(integ.key, checked)}
                            data-testid={`toggle-${integ.key}`}
                          />
                        </div>
                      </div>
                      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-[#F1F5F9]">
                        <Button size="sm" variant="outline" className="text-xs h-7" onClick={() => openEdit(integ)} data-testid={`configure-${integ.key}`}>
                          <Key size={12} className="mr-1" /> Configure
                        </Button>
                        {integ.enabled && (
                          <Button size="sm" variant="outline" className="text-xs h-7" onClick={() => handleTest(integ.key)} disabled={testing === integ.key} data-testid={`test-${integ.key}`}>
                            <Zap size={12} className="mr-1" /> {testing === integ.key ? 'Testing...' : 'Test'}
                          </Button>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
