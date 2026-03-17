# DDYs - Compliance as a Service

## Vision
DDYs is a multi-tenant KYC/AML compliance platform that automates customer onboarding, risk assessment, and regulatory reporting for financial institutions. "Bloomberg meets modern SaaS" — high density, low noise, functional beauty.

## Problem Statement
Financial institutions face mounting regulatory pressure for KYC/AML compliance. Manual processes are slow, error-prone, and expensive. Existing solutions are either too rigid or too complex for mid-market banks and fintechs.

## Solution
A full-stack compliance platform with:
- **3 User Portals**: Admin Console, Tenant Workspace, Customer Portal
- **AI-Powered Document Intelligence**: Claude Sonnet for document analysis, cross-doc validation, OSINT
- **12-State Case Workflow**: From intake to approval with maker-checker controls
- **Automated Compliance**: Screening, risk scoring, EDR monitoring, waiver management
- **Multi-Tenant Architecture**: Complete tenant isolation with role-based access

## Target Users
- **Platform Admins**: System operators managing tenants and global settings
- **Compliance Officers**: Bank staff managing KYC cases, screening, risk assessment
- **QA Reviewers**: Quality assurance on completed cases
- **End Customers**: Individuals completing onboarding requirements

## Tech Stack
- **Frontend**: React 19, shadcn/ui, Tailwind CSS, React Router 7
- **Backend**: FastAPI, MongoDB (async motor), Python 3.11+
- **Auth**: JWT + TOTP 2FA, 12-role RBAC hierarchy
- **AI/LLM**: Claude Sonnet via Emergent API
- **Build**: CRA + Craco, Yarn 1.22.22

## Success Metrics
- All GSD framework scores at 10/10
- Production-ready deployment with Docker + CI/CD
- 90%+ test coverage (backend + frontend)
- Zero critical security vulnerabilities
- Complete API documentation
- Enterprise-grade monitoring and logging
