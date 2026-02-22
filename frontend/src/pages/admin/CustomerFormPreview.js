import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { User, Building2, FileText, HelpCircle, CheckCircle, Circle, Upload } from 'lucide-react';

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
    { key: 'sof_sow', label: 'Source of Funds / Wealth', category: 'sof_sow', hint: 'Documentation of UBO\'s wealth origin.' },
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

const QUESTIONNAIRE_STEPS = [
  { step: 1, title: 'Entity Type Selection', desc: 'Customer selects: Company, Individual, Trust, or Foundation', fields: ['Entity type'] },
  { step: 2, title: 'Basic Information', desc: 'Company name/person name, jurisdiction, address', fields: ['Name', 'Jurisdiction', 'Address (Street, City, Country)'] },
  { step: 3, title: 'UBO Declaration', desc: 'Add all Ultimate Beneficial Owners with ownership %', fields: ['First Name', 'Last Name', 'DOB', 'Nationality', 'Ownership %'] },
  { step: 4, title: 'Review & Submit', desc: 'Customer reviews all data and confirms accuracy', fields: ['Summary review', 'Accuracy confirmation'] },
];

const AI_CHECKS = [
  { name: 'Document Classification', desc: 'AI classifies the uploaded document type and verifies it matches the expected category' },
  { name: 'Date Extraction & Recency', desc: 'Extracts issue date and checks recency (3 months for individuals, 12 months for entities)' },
  { name: 'Name & Address Matching', desc: 'Compares names and addresses across documents and questionnaire answers' },
  { name: 'Expiry Detection', desc: 'Checks if document has expired (IDs, passports)' },
  { name: 'Tampering Detection', desc: 'Analyzes for signs of digital manipulation or inconsistent fonts' },
  { name: 'PSI Detection', desc: 'Flags potential Price Sensitive Information and blocks storage' },
  { name: 'Cross-Document Fill', desc: 'Tax returns and police reports auto-satisfy proof of address requirements' },
  { name: 'Wrong Type Detection', desc: 'Rejects if uploaded document doesn\'t match the required category' },
];

export default function CustomerFormPreview() {
  const [entityTab, setEntityTab] = useState('legal_entity');

  return (
    <div data-testid="customer-form-preview">
      <div className="mb-6">
        <h1 className="text-3xl font-semibold tracking-tight font-['IBM_Plex_Sans']">Customer Form & Documents</h1>
        <p className="text-sm text-[#64748B] mt-1">Preview what customers see and which documents are required per entity type</p>
      </div>

      {/* Questionnaire Flow */}
      <div className="mb-8">
        <h2 className="text-sm font-semibold text-[#64748B] uppercase tracking-wider mb-3">Questionnaire Steps</h2>
        <div className="flex gap-3">
          {QUESTIONNAIRE_STEPS.map((s, i) => (
            <Card key={s.step} className="border-[#E2E8F0] flex-1">
              <CardContent className="p-3">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-6 h-6 rounded-full bg-[#0F172A] text-white flex items-center justify-center text-xs font-bold">{s.step}</div>
                  <span className="text-sm font-medium">{s.title}</span>
                </div>
                <p className="text-xs text-[#64748B] mb-2">{s.desc}</p>
                <div className="space-y-1">{s.fields.map(f => <div key={f} className="text-[10px] text-[#64748B] flex items-center gap-1"><Circle size={6} /> {f}</div>)}</div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

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
                <table className="w-full">
                  <thead><tr className="border-b bg-[#F8FAFC]">
                    <th className="h-8 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Document / Check</th>
                    <th className="h-8 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Category</th>
                    <th className="h-8 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Type</th>
                    <th className="h-8 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-[#64748B]">Customer Info</th>
                  </tr></thead>
                  <tbody>
                    {reqs.map(r => {
                      const isAuto = ['sanctions', 'pep', 'adverse_media', 'video_ident'].includes(r.category);
                      return (
                        <tr key={r.key} className="border-b hover:bg-[#F8FAFC]">
                          <td className="px-3 py-2 text-sm font-medium">{r.label}</td>
                          <td className="px-3 py-2"><Badge variant="outline" className="text-xs">{r.category}</Badge></td>
                          <td className="px-3 py-2">{isAuto ? <Badge className="bg-blue-100 text-blue-700 border-transparent text-xs">Automated</Badge> : <Badge className="bg-amber-100 text-amber-700 border-transparent text-xs">Upload</Badge>}</td>
                          <td className="px-3 py-2">
                            <div className="flex items-start gap-1"><HelpCircle size={12} className="text-[#64748B] shrink-0 mt-0.5" /><span className="text-xs text-[#64748B]">{r.hint}</span></div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </TabsContent>
          ))}
        </Tabs>
      </div>

      {/* AI Document Checks */}
      <div>
        <h2 className="text-sm font-semibold text-[#64748B] uppercase tracking-wider mb-3">AI Document Verification Checks</h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {AI_CHECKS.map(check => (
            <Card key={check.name} className="border-[#E2E8F0]">
              <CardContent className="p-3">
                <div className="flex items-center gap-1.5 mb-1"><CheckCircle size={14} className="text-green-500" /><span className="text-xs font-semibold">{check.name}</span></div>
                <p className="text-[10px] text-[#64748B]">{check.desc}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
