# Project Structure

```
DDYsGlobal/
├── .github/
│   ├── workflows/
│   │   └── ci.yml                    # CI/CD pipeline (lint, test, build, docker, security)
│   └── PULL_REQUEST_TEMPLATE.md      # PR checklist
├── .planning/                         # GSD planning artifacts
│   ├── PROJECT.md                    # Vision, problem, solution
│   ├── REQUIREMENTS.md               # Scoped requirements (v1/v2)
│   ├── ROADMAP.md                    # 9-phase improvement plan
│   ├── STATE.md                      # Living project memory
│   ├── config.json                   # GSD workflow configuration
│   ├── codebase/                     # Codebase analysis
│   │   ├── ARCHITECTURE.md
│   │   ├── STACK.md
│   │   ├── CONVENTIONS.md
│   │   ├── CONCERNS.md
│   │   ├── STRUCTURE.md
│   │   └── TESTING.md
│   ├── phases/                       # Phase execution artifacts
│   ├── research/                     # Domain research
│   ├── quick/                        # Ad-hoc task tracking
│   ├── todos/                        # Idea capture
│   └── debug/                        # Debug sessions
├── backend/
│   ├── server.py                     # FastAPI entry point
│   ├── config.py                     # Pydantic Settings (centralized config)
│   ├── .env.example                  # Environment variable documentation
│   ├── requirements.txt              # Python dependencies (127 packages)
│   ├── middleware/
│   │   ├── auth_middleware.py        # JWT + RBAC (12 roles)
│   │   └── security_middleware.py    # Rate limit, headers, sanitization, logging
│   ├── routes/                       # 22 API route modules
│   │   ├── auth.py                   # Authentication (login, MFA, OTP)
│   │   ├── cases.py                  # Case lifecycle (12 states)
│   │   ├── screening.py              # Screening management
│   │   ├── risk.py                   # Risk assessment
│   │   ├── waivers.py               # Waiver management
│   │   ├── approvals.py             # Maker-checker workflow
│   │   ├── edr.py                   # EDR alerts
│   │   ├── qa.py                    # QA reviews
│   │   ├── documents.py             # Document upload
│   │   ├── video_ident.py           # Video identification
│   │   ├── customer_portal.py       # Customer onboarding
│   │   ├── admin.py                 # Admin management
│   │   ├── tenants.py               # Tenant CRUD
│   │   ├── mi.py                    # Management dashboards
│   │   ├── audit.py                 # Audit logs
│   │   ├── policy.py               # Policy management
│   │   ├── notifications.py        # Notification stubs
│   │   ├── reminders.py            # Reminder sending
│   │   ├── integrations.py         # Email provider stubs
│   │   ├── intake.py               # Public intake
│   │   └── seed.py                 # Demo data
│   └── services/                    # Business logic
│       ├── document_intelligence.py # AI document analysis
│       ├── risk_engine.py           # CRRM risk scoring
│       ├── screening_service.py     # Mock screening
│       ├── periodic_jobs.py         # Background tasks
│       ├── export_service.py        # KYC export
│       └── osint_service.py         # OSINT analysis
├── frontend/
│   ├── package.json                  # Dependencies (56 packages)
│   ├── .prettierrc                   # Prettier config
│   ├── craco.config.js              # Webpack overrides
│   ├── tailwind.config.js           # Theme configuration
│   ├── src/
│   │   ├── App.js                   # Route definitions
│   │   ├── setupTests.js            # Test setup
│   │   ├── api/client.js            # Axios instance
│   │   ├── contexts/AuthContext.js  # Auth state management
│   │   ├── hooks/use-toast.js       # Toast hook
│   │   ├── lib/utils.js            # Tailwind utilities
│   │   ├── layouts/                 # Portal layouts (Admin, Tenant, Customer)
│   │   ├── pages/
│   │   │   ├── admin/              # 9 admin pages
│   │   │   ├── tenant/             # 10 tenant pages
│   │   │   ├── customer/           # 5 customer pages
│   │   │   └── auth/LoginPage.js   # Authentication
│   │   ├── components/
│   │   │   ├── ui/                 # 45 shadcn components
│   │   │   └── shared/             # Shared components
│   │   └── __tests__/              # Frontend test suites
│   │       ├── App.test.js
│   │       ├── api/client.test.js
│   │       ├── components/ui/button.test.js
│   │       ├── contexts/AuthContext.test.js
│   │       └── lib/utils.test.js
├── docker-compose.yml               # Full stack (MongoDB + Backend + Frontend)
├── Dockerfile.backend               # Backend container
├── Dockerfile.frontend              # Frontend multi-stage build
├── nginx.conf                       # Nginx config (security headers, SPA routing, API proxy)
├── .commitlintrc.json              # Conventional commits config
├── CODEOWNERS                       # Code ownership rules
├── design_guidelines.json           # UI design system tokens
├── backend_test.py                  # Backend integration tests
└── test_result.md                   # Test results tracking
```
