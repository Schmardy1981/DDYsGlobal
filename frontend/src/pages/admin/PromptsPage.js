import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Save, RotateCcw, Brain, FileText, Eye, EyeOff } from 'lucide-react';
import api from '@/api/client';

export default function PromptsPage() {
  const [prompts, setPrompts] = useState(null);
  const [defaults, setDefaults] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [tab, setTab] = useState('osint_system');
  const [edited, setEdited] = useState({});
  const [showVars, setShowVars] = useState(false);

  useEffect(() => { loadPrompts(); }, []);

  const loadPrompts = () => {
    api.get('/prompts').then(r => {
      setPrompts({ osint_system: r.data.osint_system, osint_user: r.data.osint_user, docint_system: r.data.docint_system });
      setDefaults(r.data.defaults);
      setEdited({ osint_system: r.data.osint_system, osint_user: r.data.osint_user, docint_system: r.data.docint_system });
    }).catch(console.error).finally(() => setLoading(false));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put('/prompts', edited);
      setPrompts({...edited});
      alert('Prompts saved successfully');
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = (key) => {
    if (defaults) {
      setEdited({...edited, [key]: defaults[key]});
    }
  };

  const hasChanges = (key) => prompts && edited[key] !== prompts[key];

  if (loading) return <div className="text-sm text-[#64748B]">Loading prompts...</div>;

  const PROMPT_TABS = [
    { key: 'osint_system', label: 'OSINT System Prompt', icon: Brain, desc: 'System instructions for the OSINT/Risk analysis AI. Defines the output format and analysis scope.' },
    { key: 'osint_user', label: 'OSINT User Prompt', icon: Brain, desc: 'Template for each analysis request. Variables: {name}, {party_type}, {nationality}, {role_in_case}, {addresses}, {identifiers}' },
    { key: 'docint_system', label: 'Document Intelligence', icon: FileText, desc: 'System instructions for document classification, OCR extraction, and compliance checking.' },
  ];

  return (
    <div data-testid="prompts-page">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight font-['IBM_Plex_Sans']">AI Prompts</h1>
          <p className="text-sm text-[#64748B] mt-1">Configure LLM system prompts for OSINT and Document Intelligence</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setShowVars(!showVars)} data-testid="toggle-vars">
            {showVars ? <EyeOff size={14} className="mr-1" /> : <Eye size={14} className="mr-1" />}
            {showVars ? 'Hide' : 'Show'} Variables
          </Button>
          <Button className="bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleSave} disabled={saving} data-testid="save-prompts-btn">
            <Save size={14} className="mr-1" /> {saving ? 'Saving...' : 'Save All'}
          </Button>
        </div>
      </div>

      {showVars && (
        <Card className="border-[#E2E8F0] mb-4 border-l-2 border-l-blue-500">
          <CardContent className="p-4">
            <p className="text-xs font-semibold text-[#64748B] uppercase tracking-wider mb-2">Available Template Variables (User Prompt)</p>
            <div className="flex flex-wrap gap-2">
              {['{name}', '{party_type}', '{nationality}', '{role_in_case}', '{addresses}', '{identifiers}'].map(v => (
                <Badge key={v} variant="outline" className="font-['JetBrains_Mono'] text-xs">{v}</Badge>
              ))}
            </div>
            <p className="text-xs text-[#64748B] mt-2">These get replaced with actual party data when the analysis runs.</p>
          </CardContent>
        </Card>
      )}

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="mb-4">
          {PROMPT_TABS.map(t => (
            <TabsTrigger key={t.key} value={t.key} data-testid={`tab-${t.key}`} className="relative">
              {t.label}
              {hasChanges(t.key) && <span className="absolute -top-1 -right-1 w-2 h-2 bg-amber-500 rounded-full" />}
            </TabsTrigger>
          ))}
        </TabsList>

        {PROMPT_TABS.map(t => {
          const Icon = t.icon;
          return (
            <TabsContent key={t.key} value={t.key}>
              <Card className="border-[#E2E8F0]">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base font-['IBM_Plex_Sans'] flex items-center gap-2">
                      <Icon size={16} /> {t.label}
                    </CardTitle>
                    <div className="flex items-center gap-2">
                      {hasChanges(t.key) && <Badge className="bg-amber-100 text-amber-700 border-transparent text-xs">Unsaved</Badge>}
                      <Button variant="ghost" size="sm" onClick={() => handleReset(t.key)} data-testid={`reset-${t.key}`}>
                        <RotateCcw size={14} className="mr-1" /> Reset to Default
                      </Button>
                    </div>
                  </div>
                  <p className="text-xs text-[#64748B]">{t.desc}</p>
                </CardHeader>
                <CardContent>
                  <Textarea
                    className="font-['JetBrains_Mono'] text-sm min-h-[400px] leading-relaxed"
                    value={edited[t.key] || ''}
                    onChange={e => setEdited({...edited, [t.key]: e.target.value})}
                    data-testid={`prompt-${t.key}`}
                  />
                  <div className="flex justify-between items-center mt-3">
                    <p className="text-xs text-[#64748B]">{(edited[t.key] || '').length} characters</p>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          );
        })}
      </Tabs>
    </div>
  );
}
