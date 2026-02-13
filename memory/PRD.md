# DDYs - Compliance as a Service Platform

## Original Problem Statement
Build a production-ready, multi-tenant "Compliance as a Service" platform for KYC/AML onboarding and ongoing reviews for financial institutions. Enforce KOS v1.11 as baseline operating model.

## Architecture
- **Frontend**: React 19 + shadcn/ui + Tailwind CSS + React Router
- **Backend**: FastAPI + MongoDB (motor async driver)
- **Auth**: JWT with 2FA (TOTP via pyotp)
- **LLM**: Claude Sonnet via Emergent LLM Key (for Document Intelligence + OSINT)
- **Design**: Light theme, IBM Plex Sans + Inter fonts, Bloomberg-meets-SaaS aesthetic

## User Personas
1. **DDYs Platform Admin** - Manages tenants, global policy, users, system settings
2. **DDYs Operations (Maker/Checker)** - Executes KYC onboarding/reviews
3. **DDYs Compliance QA** - Monitors quality, runs governance
4. **Tenant Admin** - Configures bank-specific settings
5. **Tenant Business User** - Initiates cases, business approvals
6. **Tenant MLRO** - High-risk approvals, waivers, escalations
7. **End Customer** - Completes questionnaire, uploads documents

## Core Requirements
- Multi-tenant isolation via tenant_id on all records
- 12 RBAC roles with segregation of duties (maker ≠ checker)
- Case workflow: 12 states with gating rules
- KOS v1.11 policy enforcement (review cycles, EDR timelines, waiver limits)
- Document Intelligence Service (LLM-powered classification + deterministic checks)
- Risk assessment (CRRM-like scoring with per-se flags)
- Screening (sanctions, PEP, adverse media) with mock adapter
- Immutable audit logs on every action

## What's Been Implemented (Phase 1 - Feb 2026)
### Backend (15 route modules + 5 services)
- Auth with JWT + TOTP 2FA + customer OTP flow
- Tenant CRUD with auto-policy provisioning
- Case management with full 12-state workflow engine + gating rules
- Party management with auto-requirement generation
- Document upload with Document Intelligence Service (Claude LLM)
- Screening with mock adapter (sanctions, PEP, adverse media)
- Risk assessment with CRRM-like scoring + challenge workflow
- Waivers with 90-day enforcement + approval routing
- EDR alerts with 28-day/90-day SLA + Full EDR vs KUP decision
- Approvals system (maker-checker, business, compliance, MLRO)
- MI dashboards (pipeline, NRD, EDR, waivers, screening)
- Policy management with versioning
- KYC File Export (ZIP with full evidence bundle)
- OSINT/Risk analysis via Claude LLM
- Notifications system
- Immutable audit logs
- Admin settings (LLM provider/key, email, screening)
- Seed data (Demo Bank + 11 demo users + demo case)

### Frontend (3 portals)
- **Admin Console**: Dashboard, Tenants, Users, Policy, Settings
- **Tenant Workspace**: Cases Pipeline (filterable), Case Detail (8 tabs), Screening Queue, Waivers, EDR Alerts, MI Dashboard, Settings
- **Customer Portal**: Bank selection + OTP, Dashboard checklist, Questionnaire wizard, Document upload

## What's Been Implemented (Phase 2 - Feb 2026)
### Periodic Background Jobs
- Regular Review (RR) auto-generation when NRD approaches (High: 12mo, Medium: 24mo, Low: 60mo, triggers 60 days early)
- EDR deadline monitoring (28-day review SLA, 90-day completion SLA, auto-restrict on breach, MLRO escalation)
- Waiver expiry monitoring (alerts at 30/14/7/1 days, auto-expire, auto-restrict, revert waived requirements)
- Document expiry monitoring (flag expired docs, create EDR alerts)
- Ongoing screening refresh (weekly re-screening of active clients)
- Manual trigger via admin "Run All Jobs Now" button
- Runs every hour automatically

### Video Identification
- Create/schedule video ident sessions per party
- Agent join and complete workflow
- Mock liveness/deepfake scoring with policy thresholds (liveness >= 0.70, deepfake <= 0.30)
- Auto-escalation to MLRO on suspected deepfake
- Session tracking (scheduled, in_progress, completed)

### QA Module
- Risk-weighted + random sampling (default 5% of completed cases monthly)
- First line and second line QA reviews
- Manual review creation with findings, severity, remediation tracking
- Governance Council pack (monthly metrics, trends, findings summary, remediation tracker)
- Open/close review lifecycle

### New Frontend Pages
- Admin: Periodic Jobs page (5 job cards with status, Run All Now button)
- Workspace: QA page (Reviews tab + Governance Pack tab)
- Workspace: Video Ident page (schedule, join, complete sessions)

## Prioritized Backlog
### P0 (Next Phase)
- Video Ident with WebRTC (agent + customer)
- Deepfake/Liveness mock adapter
- Regular Review (RR) auto-generation from NRD
- EDR automation jobs

### P1
- QA Module (sampling, first/second line reviews, governance council)
- Email integration (SendGrid/Resend with API key in admin panel)
- Full maker-checker narrative editor (rich text)
- Tenant branding (white-label customer portal)

### P2
- Real screening provider integration (DIDIT adapter)
- Bulk import/export for legacy KYC files
- SSO/SAML integration
- Data residency controls per tenant
- In-app help page ("How to operate DDYs")

## Demo Credentials
| Email | Password | Role |
|-------|----------|------|
| admin@ddys.com | Admin123! | GLOBAL_SUPER_ADMIN |
| maker@ddys.com | Maker123! | DDYS_RCM_MAKER |
| checker@ddys.com | Checker123! | DDYS_RCM_CHECKER |
| mlro@demobank.com | MLRO123! | TENANT_MLRO |
| customer@example.com | Cust123! | END_CUSTOMER |

## Environment Variables
- `MONGO_URL` - MongoDB connection
- `DB_NAME` - Database name
- `JWT_SECRET` - JWT signing secret
- `EMERGENT_LLM_KEY` - Claude API key via Emergent
- `MFA_ISSUER` - 2FA issuer name
- `CORS_ORIGINS` - Allowed origins
