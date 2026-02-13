import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Save, Key, Mail, Search, Video } from 'lucide-react';
import api from '@/api/client';

export default function SettingsPage() {
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({});

  useEffect(() => {
    api.get('/admin/settings').then(r => { setSettings(r.data); setForm(r.data); }).catch(console.error).finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put('/admin/settings', form);
      alert('Settings saved');
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="text-sm text-[#64748B]">Loading...</div>;

  return (
    <div data-testid="settings-page">
      <div className="mb-6">
        <h1 className="text-3xl font-semibold tracking-tight font-['IBM_Plex_Sans']">System Settings</h1>
        <p className="text-sm text-[#64748B] mt-1">Configure integrations and system parameters</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border-[#E2E8F0]">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-['IBM_Plex_Sans'] flex items-center gap-2"><Key size={16} /> LLM Configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Provider</Label>
              <Select value={form.llm_provider || 'anthropic'} onValueChange={v => setForm({...form, llm_provider: v})}>
                <SelectTrigger className="mt-1.5" data-testid="llm-provider-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="anthropic">Anthropic (Claude)</SelectItem>
                  <SelectItem value="openai">OpenAI</SelectItem>
                  <SelectItem value="gemini">Google (Gemini)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Model</Label>
              <Input className="mt-1.5" value={form.llm_model || ''} onChange={e => setForm({...form, llm_model: e.target.value})} placeholder="e.g. claude-sonnet-4-5-20250929" data-testid="llm-model-input" />
            </div>
            <div>
              <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Custom API Key (leave empty for Emergent key)</Label>
              <Input className="mt-1.5" type="password" value={form.custom_llm_key || ''} onChange={e => setForm({...form, custom_llm_key: e.target.value})} placeholder="sk-..." data-testid="llm-key-input" />
              <p className="text-xs text-[#64748B] mt-1">Currently using: {settings.llm_api_key_set ? 'Emergent Universal Key' : 'Not configured'}</p>
            </div>
          </CardContent>
        </Card>

        <Card className="border-[#E2E8F0]">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-['IBM_Plex_Sans'] flex items-center gap-2"><Mail size={16} /> Email Configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Provider</Label>
              <Select value={form.email_provider || 'mock'} onValueChange={v => setForm({...form, email_provider: v})}>
                <SelectTrigger className="mt-1.5" data-testid="email-provider-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="mock">Mock (Demo)</SelectItem>
                  <SelectItem value="sendgrid">SendGrid</SelectItem>
                  <SelectItem value="resend">Resend</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">API Key</Label>
              <Input className="mt-1.5" type="password" value={form.email_api_key || ''} onChange={e => setForm({...form, email_api_key: e.target.value})} placeholder="Enter API key" data-testid="email-key-input" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-[#E2E8F0]">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-['IBM_Plex_Sans'] flex items-center gap-2"><Search size={16} /> Screening Provider</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Provider</Label>
              <Select value={form.screening_provider || 'mock'} onValueChange={v => setForm({...form, screening_provider: v})}>
                <SelectTrigger className="mt-1.5" data-testid="screening-provider-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="mock">Mock (Demo)</SelectItem>
                  <SelectItem value="didit">DIDIT</SelectItem>
                  <SelectItem value="refinitiv">Refinitiv / World-Check</SelectItem>
                  <SelectItem value="complyadvantage">ComplyAdvantage</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">API Key</Label>
              <Input className="mt-1.5" type="password" value={form.screening_api_key || ''} onChange={e => setForm({...form, screening_api_key: e.target.value})} placeholder="Enter API key" data-testid="screening-key-input" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-[#E2E8F0]">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-['IBM_Plex_Sans'] flex items-center gap-2"><Video size={16} /> Video Ident</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Provider</Label>
              <Select value={form.video_ident_provider || 'mock'} onValueChange={v => setForm({...form, video_ident_provider: v})}>
                <SelectTrigger className="mt-1.5">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="mock">Mock (Demo)</SelectItem>
                  <SelectItem value="internal_webrtc">Internal WebRTC</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <p className="text-xs text-[#64748B]">Video ident with deepfake/liveness detection will be available in Phase 2.</p>
          </CardContent>
        </Card>
      </div>

      <div className="mt-6">
        <Button className="bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleSave} disabled={saving} data-testid="save-settings-btn">
          <Save size={16} className="mr-1.5" /> {saving ? 'Saving...' : 'Save Settings'}
        </Button>
      </div>
    </div>
  );
}
