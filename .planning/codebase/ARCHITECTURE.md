# Architecture

## System Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    DDYs Compliance Platform                    │
├──────────────┬──────────────┬──────────────────────────────────┤
│ Admin Portal │ Tenant Portal│ Customer Portal                  │
│ (React SPA)  │ (React SPA)  │ (React SPA)                      │
├──────────────┴──────────────┴──────────────────────────────────┤
│                    Axios HTTP Client + JWT                      │
├──────────────────────────────────────────────────────────────────┤
│                    FastAPI Backend (async)                       │
├──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬────────┤
│ Auth │Cases │Screen│ Risk │Waiver│Approv│ EDR  │  QA  │  MI    │
│Routes│Routes│Routes│Routes│Routes│Routes│Routes│Routes│Routes  │
├──────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┴────────┤
│                    Middleware Layer                              │
│              JWT Auth │ RBAC │ Tenant Isolation                  │
├──────────────────────────────────────────────────────────────────┤
│                    Service Layer                                 │
│  DocIntelligence │ RiskEngine │ Screening │ Export │ OSINT       │
├──────────────────────────────────────────────────────────────────┤
│                    Data Layer                                    │
│              MongoDB (async motor) │ File Storage                │
├──────────────────────────────────────────────────────────────────┤
│                    Background Jobs                               │
│  NRD/RR Check │ EDR Deadlines │ Waiver Expiry │ Screening Refresh│
└──────────────────────────────────────────────────────────────────┘
```

## Backend Architecture

### Entry Point
- `server.py`: FastAPI app setup, CORS, startup events, direct endpoints (health, seed, prompts, jobs, OSINT, export)

### Route Layer (22 modules)
Each route module creates an `APIRouter` with prefixed paths:
| Module | Prefix | Responsibility |
|--------|--------|---------------|
| auth | /api/auth | Login, MFA, OTP, quick-login |
| cases | /api/cases | Case CRUD, 12-state workflow, parties, requirements |
| screening | /api/screening | Mock screening, hit management |
| risk | /api/risk | CRRM-like scoring, challenge workflow |
| waivers | /api/waivers | Waiver creation/approval, 90-day enforcement |
| approvals | /api/approvals | Maker-checker workflow |
| edr | /api/edr | EDR alerts, 28d/90d SLAs |
| qa | /api/qa | QA reviews, governance council |
| documents | /api/documents | Upload, AI analysis triggering |
| video_ident | /api/video-ident | Session management, liveness scoring |
| customer_portal | /api/customer | End-customer onboarding workflow |
| admin | /api/admin | User management, settings |
| tenants | /api/tenants | Tenant CRUD, policy provisioning |
| mi | /api/mi | Management dashboards |
| audit | /api/audit | Immutable audit log retrieval |
| policy | /api/policy | KOS policy CRUD, versioning |
| notifications | /api/notifications | Notification stubs |
| reminders | /api/reminders | Invitation sending (mocked) |
| integrations | /api/integrations | Email provider stubs |
| intake | /api/intake | Public intake submission |
| seed | /api/seed | Demo data generation |

### Service Layer (6 modules)
| Service | Purpose |
|---------|---------|
| document_intelligence | LLM-powered OCR, cross-doc validation, auto-fill |
| risk_engine | CRRM-like risk scoring, per-se flags, DD levels |
| screening_service | Mock sanctions/PEP/adverse media screening |
| export_service | KYC ZIP file export with evidence bundle |
| osint_service | Claude-powered OSINT analysis |
| periodic_jobs | Hourly background tasks (RR, EDR, expiry, refresh) |

### Middleware
- `auth_middleware.py`: JWT validation, 12-role hierarchy, tenant access control

### Data Model (MongoDB Collections)
| Collection | Purpose |
|-----------|---------|
| users | User accounts with roles |
| tenants | Tenant organizations |
| cases | KYC cases with 12-state lifecycle |
| documents | Uploaded documents with AI analysis |
| screening_results | Screening hits and decisions |
| risk_assessments | Risk scores and challenges |
| waivers | Active waivers with expiry |
| approval_tasks | Maker-checker tasks |
| edr_alerts | Enhanced due review alerts |
| qa_reviews | QA review records |
| audit_logs | Immutable audit trail |
| system_settings | Global configuration |
| kyc_exports | Export records |

## Frontend Architecture

### Routing (React Router 7)
```
/login                    → LoginPage
/admin/*                  → AdminLayout
  /admin/dashboard        → Dashboard
  /admin/tenants          → TenantsPage
  /admin/users            → UsersPage
  /admin/policy           → PolicyPage
  /admin/settings         → SettingsPage
  /admin/jobs             → PeriodicJobsPage
  /admin/prompts          → PromptsPage
  /admin/integrations     → IntegrationsPage
/tenant/*                 → TenantLayout
  /tenant/cases           → CasesPipeline
  /tenant/cases/:id       → CaseDetail (8 tabs)
  /tenant/screening       → ScreeningQueue
  /tenant/waivers         → WaiversPage
  /tenant/mi              → MIDashboard
  /tenant/edr             → EDRPage
  /tenant/qa              → QAPage
  /tenant/video-ident     → VideoIdentPage
  /tenant/intake          → IntakePage
/customer/*               → CustomerLayout
  /customer/landing       → CustomerLanding
  /customer/dashboard     → CustomerDashboard
  /customer/questionnaire → Questionnaire
  /customer/intake        → IntakeForm
```

### State Management
- **AuthContext**: Global auth state (user, token, roles)
- **Component-level state**: useState/useEffect per page
- **No global state library** (no Redux/Zustand)

### UI Framework
- shadcn/ui (45 Radix-based components)
- Tailwind CSS with design_guidelines.json tokens
- Lucide icons, Sonner toasts, Recharts for data viz

## Case Lifecycle (12 States)
```
INTAKE → NEW → DATA_GATHERING → SCREENING → RISK_ASSESSMENT →
MAKER_REVIEW → CHECKER_REVIEW → APPROVED / REJECTED / ESCALATED →
EDR_REVIEW → CLOSED
```
