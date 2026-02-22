import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { User, Building2, FileText, HelpCircle, CheckCircle, Circle, Upload, Eye, ExternalLink } from 'lucide-react';
import IntakeForm from '@/pages/customer/IntakeForm';

const ENTITY_REQUIREMENTS = {
  natural_person: [
    { key: 'identity_doc', label: 'Government-issued ID', category: 'identity', hint: 'Passport or national ID card. Must not be expired.' },
    { key: 'proof_of_address', label: 'Proof of Address', category: 'address', hint: 'Utility bill, bank statement, or official letter. Max 3 months old for individuals.' },
    { key: 'sof_sow', label: 'Source of Funds / Wealth', category: 'sof_sow', hint: 'Bank statements, salary slips, investment records, or business financials.' },
    { key: 'sanctions_screening', label: 'Sanctions Screening', category: 'sanctions', hint: 'Automated check. No customer action needed.' },
    { key: 'pep_screening', label: 'PEP Screening', category: 'pep', hint: 'Automated check. No customer action needed.' },
    { key: 'adverse_media', label: 'Adverse Media Check', category: 'adverse_media', hint: 'Automated check. No customer action needed.' },
    { key: 'video_ident', label: 'Video Identification', category: 'video_ident', hint: 'Live video session with compliance agent.' },
  ],
  legal_entity: [
    { key: 'registry_extract', label: 'Registry Extract / Certificate of Incorporation', category: 'existence', hint: 'Official company registry document. Must be current.' },
    { key: 'ownership_chart', label: 'Ownership Structure Chart', category: 'ownership', hint: 'Clear chart showing all shareholders with percentages.' },
    { key: 'articles_of_association', label: 'Articles of Association', category: 'authority', hint: 'Constitutional documents of the company.' },
    { key: 'board_resolution', label: 'Board Resolution / Authority to Act', category: 'authority', hint: 'Board resolution authorizing this business relationship.' },
    { key: 'proof_of_address_entity', label: 'Proof of Business Address', category: 'address', hint: 'Registry extract or utility bill in company name. Valid within 12 months.' },
    { key: 'financial_statements', label: 'Financial Statements / Annual Report', category: 'sof_sow', hint: 'Latest audited financial statements.' },
    { key: 'sanctions_screening_entity', label: 'Entity Sanctions Screening', category: 'sanctions', hint: 'Automated check. No customer action needed.' },
    { key: 'adverse_media_entity', label: 'Entity Adverse Media Check', category: 'adverse_media', hint: 'Automated check. No customer action needed.' },
  ],
  ubo: [
    { key: 'identity_doc', label: 'Government-issued ID', category: 'identity', hint: 'Passport or national ID of UBO.' },
    { key: 'proof_of_address', label: 'Proof of Address', category: 'address', hint: 'Max 3 months old. Utility bill or bank statement.' },
    { key: 'sanctions_screening', label: 'Sanctions Screening', category: 'sanctions', hint: 'Automated.' },
    { key: 'pep_screening', label: 'PEP Screening', category: 'pep', hint: 'Automated.' },
    { key: 'adverse_media', label: 'Adverse Media', category: 'adverse_media', hint: 'Automated.' },
    { key: 'sof_sow', label: 'Source of Funds / Wealth', category: 'sof_sow', hint: "Documentation of UBO's wealth origin." },
    { key: 'video_ident', label: 'Video Identification', category: 'video_ident', hint: 'Required for UBOs.' },
  ],
  director: [
    { key: 'identity_doc', label: 'Government-issued ID', category: 'identity', hint: 'Passport or national ID.' },
    { key: 'proof_of_address', label: 'Proof of Address', category: 'address', hint: 'Max 3 months old.' },
    { key: 'sanctions_screening', label: 'Sanctions Screening', category: 'sanctions', hint: 'Automated.' },
    { key: 'pep_screening', label: 'PEP Screening', category: 'pep', hint: 'Automated.' },
    { key: 'adverse_media', label: 'Adverse Media', category: 'adverse_media', hint: 'Automated.' },
  ]
};

const AI_CHECKS = [
  { name: 'Document Classification', desc: 'AI classifies type and verifies it matches the expected category' },
  { name: 'Date & Recency Check', desc: '3 months for individuals, 12 months for entities' },
  { name: 'Name & Address Match', desc: 'Cross-checks names and addresses across all documents' },
  { name: 'Expiry Detection', desc: 'Checks if IDs and passports have expired' },
  { name: 'Tampering Detection', desc: 'Analyzes for digital manipulation signs' },
  { name: 'PSI Detection', desc: 'Flags Price Sensitive Information and blocks storage' },
  { name: 'Cross-Doc Auto-Fill', desc: 'Tax returns / police reports auto-satisfy proof of address' },
  { name: 'Wrong Type Rejection', desc: 'Rejects if document does not match required category' },
];

export default function CustomerFormPreview() {
  const [entityTab, setEntityTab] = useState('legal_entity');
  const [showPreview, setShowPreview] = useState(false);

  return (
    <div data-testid="customer-form-preview">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight font-['IBM_Plex_Sans']">Customer Form & Documents</h1>
          <p className="text-sm text-[#64748B] mt-1">Preview what customers see and which documents are required per entity type</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => window.open('/intake', '_blank')} data-testid="open-intake-link">
            <ExternalLink size={14} className="mr-1" /> Open Intake Link
          </Button>
          <Button className="bg-[#0F172A] hover:bg-[#1E293B]" onClick={() => setShowPreview(true)} data-testid="preview-form-btn">
            <Eye size={14} className="mr-1" /> Preview Customer Form
          </Button>
        </div>
      </div>

      {/* Full-screen form preview dialog */}
      <Dialog open={showPreview} onOpenChange={setShowPreview}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto p-0">
          <div className="p-6">
            <IntakeForm previewMode={true} />
          </div>
        </DialogContent>
      </Dialog>

      {/* Required Documents by Entity Type */}
      <div className="mb-8">
        <h2 className="text-sm font-semibold text-[#64748B] uppercase tracking-wider mb-3">Required Documents by Role</h2>
        <Tabs value={entityTab} onValueChange={setEntityTab}>
          <TabsList className="mb-3">
            <TabsTrigger value="legal_entity"><Building2 size={14} className="mr-1" /> Company</TabsTrigger>
            <TabsTrigger value="natural_person"><User size={14} className="mr-1" /> Individual</TabsTrigger>
            <TabsTrigger value="ubo"><User size={14} className="mr-1" /> UBO</TabsTrigger>
            <TabsTrigger value="director"><User size={14} className="mr-1" /> Director</TabsTrigger>
          </TabsList>
          {Object.entries(ENTITY_REQUIREMENTS).map(([type, reqs]) => (
            <TabsContent key={type} value={type}>
              <div className="bg-white border border-[#E2E8F0] rounded-md overflow-hidden">
                <table className="w-full"><thead><tr className="border-b bg-[#F8FAFC]">
                  <th className="h-8 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Document</th>
                  <th className="h-8 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Category</th>
                  <th className="h-8 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Type</th>
                  <th className="h-8 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Customer Info</th>
                </tr></thead><tbody>
                  {reqs.map(r => {
                    const isAuto = ['sanctions', 'pep', 'adverse_media', 'video_ident'].includes(r.category);
                    return (
                      <tr key={r.key} className="border-b hover:bg-[#F8FAFC]">
                        <td className="px-3 py-2 text-sm font-medium">{r.label}</td>
                        <td className="px-3 py-2"><Badge variant="outline" className="text-xs">{r.category}</Badge></td>
                        <td className="px-3 py-2">{isAuto ? <Badge className="bg-blue-100 text-blue-700 border-transparent text-xs">Automated</Badge> : <Badge className="bg-amber-100 text-amber-700 border-transparent text-xs">Upload</Badge>}</td>
                        <td className="px-3 py-2"><div className="flex items-start gap-1"><HelpCircle size={12} className="text-[#64748B] shrink-0 mt-0.5" /><span className="text-xs text-[#64748B]">{r.hint}</span></div></td>
                      </tr>
                    );
                  })}
                </tbody></table>
              </div>
            </TabsContent>
          ))}
        </Tabs>
      </div>

      {/* AI Checks */}
      <div>
        <h2 className="text-sm font-semibold text-[#64748B] uppercase tracking-wider mb-3">AI Document Verification</h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {AI_CHECKS.map(c => (
            <Card key={c.name} className="border-[#E2E8F0]"><CardContent className="p-3">
              <div className="flex items-center gap-1.5 mb-1"><CheckCircle size={14} className="text-green-500" /><span className="text-xs font-semibold">{c.name}</span></div>
              <p className="text-[10px] text-[#64748B]">{c.desc}</p>
            </CardContent></Card>
          ))}
        </div>
      </div>
    </div>
  );
}
