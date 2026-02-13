import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Video, Plus, Play, CheckCircle, XCircle, RefreshCw, User, Shield } from 'lucide-react';
import api from '@/api/client';

export default function VideoIdentPage() {
  const { getActiveTenantId } = useAuth();
  const tenantId = getActiveTenantId();
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [showComplete, setShowComplete] = useState(null);
  const [completeForm, setCompleteForm] = useState({ outcome: 'pass', notes: '', identity_confirmed: true, document_match: true });
  const [cases, setCases] = useState([]);
  const [parties, setParties] = useState([]);
  const [createForm, setCreateForm] = useState({ case_id: '', party_id: '', scheduled_at: '' });

  useEffect(() => { loadData(); }, [tenantId]);

  const loadData = () => {
    if (!tenantId) return;
    api.get(`/video-ident/sessions?tenant_id=${tenantId}`).then(r => setSessions(r.data)).catch(console.error).finally(() => setLoading(false));
    api.get(`/cases?tenant_id=${tenantId}`).then(r => setCases(r.data)).catch(() => {});
  };

  const loadParties = async (caseId) => {
    try {
      const res = await api.get(`/cases/${caseId}`);
      const np = (res.data.parties || []).filter(p => p.party_type === 'natural_person');
      setParties(np);
    } catch { setParties([]); }
  };

  const handleCreate = async () => {
    try {
      await api.post('/video-ident/sessions', createForm);
      setShowCreate(false);
      setCreateForm({ case_id: '', party_id: '', scheduled_at: '' });
      loadData();
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  const handleJoin = async (sessionId) => {
    try {
      await api.post(`/video-ident/sessions/${sessionId}/join`, { role: 'agent' });
      loadData();
    } catch (err) { alert(err.response?.data?.detail || 'Failed to join'); }
  };

  const handleComplete = async () => {
    if (!showComplete) return;
    try {
      await api.post(`/video-ident/sessions/${showComplete}/complete`, completeForm);
      setShowComplete(null);
      setCompleteForm({ outcome: 'pass', notes: '', identity_confirmed: true, document_match: true });
      loadData();
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  const outcomeIcon = (o) => {
    if (o === 'pass') return <CheckCircle size={14} className="text-green-500" />;
    if (o === 'fail') return <XCircle size={14} className="text-red-500" />;
    return <RefreshCw size={14} className="text-amber-500" />;
  };

  return (
    <div data-testid="video-ident-page">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight font-['IBM_Plex_Sans']">Video Identification</h1>
          <p className="text-sm text-[#64748B] mt-1">Schedule, conduct, and review video ident sessions</p>
        </div>
        <Dialog open={showCreate} onOpenChange={setShowCreate}>
          <DialogTrigger asChild>
            <Button className="bg-[#0F172A] hover:bg-[#1E293B]" data-testid="schedule-video-btn">
              <Plus size={14} className="mr-1" /> Schedule Session
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Schedule Video Ident</DialogTitle></DialogHeader>
            <div className="space-y-4 pt-2">
              <div>
                <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Case</Label>
                <Select value={createForm.case_id} onValueChange={v => { setCreateForm({...createForm, case_id: v, party_id: ''}); loadParties(v); }}>
                  <SelectTrigger className="mt-1.5"><SelectValue placeholder="Select case" /></SelectTrigger>
                  <SelectContent>
                    {cases.map(c => <SelectItem key={c.id} value={c.id}>{c.case_ref}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Party (Natural Person)</Label>
                <Select value={createForm.party_id} onValueChange={v => setCreateForm({...createForm, party_id: v})}>
                  <SelectTrigger className="mt-1.5"><SelectValue placeholder="Select party" /></SelectTrigger>
                  <SelectContent>
                    {parties.map(p => <SelectItem key={p.id} value={p.id}>{p.first_name} {p.last_name} ({p.role_in_case})</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Scheduled Date/Time</Label>
                <Input className="mt-1.5" type="datetime-local" value={createForm.scheduled_at} onChange={e => setCreateForm({...createForm, scheduled_at: e.target.value})} />
              </div>
              <Button className="w-full bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleCreate} data-testid="submit-video-session-btn">Schedule</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Completion dialog */}
      <Dialog open={!!showComplete} onOpenChange={(o) => !o && setShowComplete(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Complete Video Ident</DialogTitle></DialogHeader>
          <div className="space-y-4 pt-2">
            <div>
              <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Outcome</Label>
              <Select value={completeForm.outcome} onValueChange={v => setCompleteForm({...completeForm, outcome: v})}>
                <SelectTrigger className="mt-1.5"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="pass">Pass</SelectItem>
                  <SelectItem value="fail">Fail</SelectItem>
                  <SelectItem value="retry">Retry Required</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex gap-4">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={completeForm.identity_confirmed} onChange={e => setCompleteForm({...completeForm, identity_confirmed: e.target.checked})} />
                Identity Confirmed
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={completeForm.document_match} onChange={e => setCompleteForm({...completeForm, document_match: e.target.checked})} />
                Document Match
              </label>
            </div>
            <div>
              <Label className="text-xs uppercase tracking-wider font-semibold text-[#64748B]">Agent Notes</Label>
              <Textarea className="mt-1.5" value={completeForm.notes} onChange={e => setCompleteForm({...completeForm, notes: e.target.value})} rows={3} />
            </div>
            <Button className="w-full bg-[#0F172A] hover:bg-[#1E293B]" onClick={handleComplete} data-testid="complete-video-btn">Complete Session</Button>
          </div>
        </DialogContent>
      </Dialog>

      <div className="space-y-3">
        {sessions.map(s => (
          <Card key={s.id} className="border-[#E2E8F0]" data-testid={`video-session-${s.id}`}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-md bg-[#F1F5F9] flex items-center justify-center">
                    <Video size={18} className="text-[#64748B]" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{s.party_name || 'Unknown Party'}</span>
                      <Badge className={
                        s.status === 'completed' ? (s.outcome === 'pass' ? 'bg-green-100 text-green-700' : s.outcome === 'fail' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700') + ' border-transparent' :
                        s.status === 'in_progress' ? 'bg-blue-100 text-blue-700 border-transparent' :
                        'bg-gray-100 text-gray-700 border-transparent'
                      }>{s.status}</Badge>
                      {s.outcome && (
                        <span className="flex items-center gap-1 text-xs">
                          {outcomeIcon(s.outcome)} {s.outcome}
                        </span>
                      )}
                    </div>
                    <div className="flex gap-4 mt-1 text-xs text-[#64748B]">
                      <span>Scheduled: {s.scheduled_at ? new Date(s.scheduled_at).toLocaleString() : 'TBD'}</span>
                      {s.room_id && <span className="font-['JetBrains_Mono']">Room: {s.room_id}</span>}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {s.liveness_score != null && (
                    <div className="text-right mr-4">
                      <div className="flex items-center gap-2 text-xs">
                        <User size={12} /> Liveness: <span className={`font-['JetBrains_Mono'] font-medium ${s.liveness_pass ? 'text-green-600' : 'text-red-600'}`}>{s.liveness_score}</span>
                      </div>
                      <div className="flex items-center gap-2 text-xs">
                        <Shield size={12} /> Deepfake: <span className={`font-['JetBrains_Mono'] font-medium ${s.deepfake_pass ? 'text-green-600' : 'text-red-600'}`}>{s.deepfake_score}</span>
                      </div>
                    </div>
                  )}
                  {s.status === 'scheduled' && (
                    <Button size="sm" variant="outline" onClick={() => handleJoin(s.id)} data-testid={`join-video-${s.id}`}>
                      <Play size={14} className="mr-1" /> Join as Agent
                    </Button>
                  )}
                  {s.status === 'in_progress' && (
                    <Button size="sm" className="bg-[#0F172A] hover:bg-[#1E293B]" onClick={() => setShowComplete(s.id)} data-testid={`complete-video-${s.id}`}>
                      <CheckCircle size={14} className="mr-1" /> Complete
                    </Button>
                  )}
                </div>
              </div>
              {s.notes && <p className="mt-2 text-xs text-[#64748B] bg-[#F8FAFC] p-2 rounded">{s.notes}</p>}
            </CardContent>
          </Card>
        ))}
        {!sessions.length && <div className="text-center py-8 text-sm text-[#64748B]">{loading ? 'Loading...' : 'No video ident sessions. Schedule one above.'}</div>}
      </div>
    </div>
  );
}
