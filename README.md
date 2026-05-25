# DDYs - Compliance as a Service

Multi-tenant KYC/AML compliance platform for financial institutions. AI-powered document intelligence, automated risk assessment, and regulatory reporting.

## Architecture

```
Frontend (React 19 + shadcn/ui)  →  Backend (FastAPI)  →  MongoDB
     ↓                                    ↓
3 Portals:                          Services:
 • Admin Console                     • Document Intelligence (Claude AI)
 • Tenant Workspace                  • Risk Engine (CRRM-like scoring)
 • Customer Portal                   • Screening (sanctions/PEP/AML)
                                     • Background Jobs (periodic compliance checks)
```

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+ / Yarn 1.22+
- MongoDB 6+
- Claude API key (via Emergent)

### Setup

```bash
# Clone
git clone https://github.com/Schmardy1981/DDYsGlobal.git
cd DDYsGlobal

# Backend
cp backend/.env.example backend/.env  # Edit with your values
cd backend
pip install -r requirements.txt
python server.py

# Frontend (new terminal)
cd frontend
yarn install
yarn start

# Seed demo data
curl -X POST http://localhost:8000/api/seed
```

### Default Accounts (after seeding)
| Role | Email | Password |
|------|-------|----------|
| Admin (Plattform) | admin@ddys.com | Admin123! |
| Case Manager (DDYs) | sarah@ddys.com | Case123! |
| Case Manager (DDYs) | michael@ddys.com | Case123! |
| Video Agent | video@ddys.com | Video123! |
| Bank User (Demo Bank) | bankadmin@demobank.com | Bank123! |
| Bank User (Demo Bank) | compliance@demobank.com | Bank123! |

## Project Structure

```
├── backend/
│   ├── server.py              # FastAPI entry point
│   ├── middleware/
│   │   └── auth_middleware.py  # JWT + RBAC (4 roles)
│   ├── routes/                 # 22 API route modules
│   ├── services/               # Business logic layer
│   │   ├── document_intelligence.py  # AI document analysis
│   │   ├── risk_engine.py            # CRRM risk scoring
│   │   ├── screening_service.py      # Sanctions/PEP screening
│   │   ├── periodic_jobs.py          # Background compliance jobs
│   │   ├── export_service.py         # KYC file export
│   │   └── osint_service.py          # OSINT via Claude
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/admin/        # Platform admin pages
│   │   ├── pages/tenant/       # Compliance workspace pages
│   │   ├── pages/customer/     # End-customer portal pages
│   │   ├── components/ui/      # shadcn/ui components
│   │   ├── contexts/           # Auth context
│   │   └── api/                # Axios HTTP client
│   └── package.json
├── .planning/                  # GSD project planning artifacts
├── docker-compose.yml          # Full stack deployment
├── Dockerfile.backend          # Backend container
├── Dockerfile.frontend         # Frontend container
└── .github/workflows/          # CI/CD pipeline
```

## API Documentation

FastAPI auto-generates interactive API docs:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Case Lifecycle

```
INTAKE → NEW → DATA_GATHERING → SCREENING → RISK_ASSESSMENT →
MAKER_REVIEW → CHECKER_REVIEW → APPROVED / REJECTED / ESCALATED →
EDR_REVIEW → CLOSED
```

## Zugangssystem (4 Rollen)

| Rolle | Beschreibung | Portal |
|-------|-------------|--------|
| **ADMIN** | DDYs Plattform-Administratoren — voller Zugriff | Admin + Workspace |
| **CASE_MANAGER** | DDYs-Mitarbeiter die Bankkunden betreuen (Cases, QA, Screening, Approval) | Workspace |
| **VIDEO_AGENT** | Mitarbeiter für Video-Identifikation | Workspace (nur Video-Ident) |
| **BANK_USER** | Bankkunden — sehen nur eigene Kundendaten (Tenant-isoliert) | Workspace (eigener Bereich) |

Zusätzlich: `END_CUSTOMER` für das OTP-basierte Endkunden-Portal (kein Staff-Login).

## Tech Stack

- **Frontend**: React 19, shadcn/ui, Tailwind CSS, React Router 7
- **Backend**: FastAPI, MongoDB (async motor), Pydantic
- **Auth**: JWT + TOTP 2FA, 4-role RBAC (ADMIN, CASE_MANAGER, VIDEO_AGENT, BANK_USER) plus END_CUSTOMER portal access
- **AI**: Claude Sonnet (document intelligence, OSINT)
- **Build**: CRA + Craco, Docker, GitHub Actions

## Development

```bash
# Run tests
cd backend && python -m pytest backend_test.py -v
cd frontend && yarn test

# Lint
cd backend && black . && flake8 . && mypy .
cd frontend && npx eslint src/

# Docker (full stack)
docker-compose up --build
```

## License

Proprietary - DDYs Global
