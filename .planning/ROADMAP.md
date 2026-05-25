# Roadmap

## Phase 01 — GSD Foundation & Documentation [COMPLETED]
- Initialize .planning/ structure with all GSD artifacts
- Create comprehensive README.md
- Create ARCHITECTURE.md
- Create .env.example
- Enable FastAPI auto-docs (OpenAPI/Swagger)
- Create deployment guide

## Phase 02 — Security Hardening [COMPLETED]
- Add rate limiting (slowapi)
- Add CSRF protection
- Add input sanitization middleware
- Add security headers (CSP, HSTS, X-Frame-Options)
- Secure file uploads (now on GCS — see Phase 09)
- Remove dev-mode quick-login from production (Phase 09)
- Add field-level PII encryption

## Phase 03 — Testing Infrastructure [COMPLETED]
- Setup Jest + React Testing Library for frontend
- Add frontend component tests (all pages)
- Expand backend pytest coverage to 90%+
- Setup Playwright for E2E tests
- Add coverage reporting (c8/istanbul + pytest-cov)
- Add security scanning (bandit, eslint-plugin-security)
- Setup load testing with locust

## Phase 04 — Build & Deployment [COMPLETED]
- Create Dockerfiles (backend, frontend)
- Create docker-compose.yml (full stack + MongoDB)
- Setup GitHub Actions CI/CD pipeline
- Add database migration framework (delivered in Phase 09)
- Add structured JSON logging
- Add comprehensive health checks

## Phase 05 — Code Quality [COMPLETED]
- TypeScript migration for frontend (incremental)
- Decompose CaseDetail.js into sub-components
- Configure ESLint + Prettier with auto-fix
- Configure black + flake8 + mypy for Python
- Setup pre-commit hooks (husky + lint-staged)
- Enforce 300-line file size policy

## Phase 06 — Configuration & Feature Flags [COMPLETED]
- Implement centralized config system with Pydantic Settings
- Add feature flag system
- Create environment-specific configs (dev/staging/prod)
- Document all configuration options
- Add config schema validation

## Phase 07 — Git Workflow & Standards [COMPLETED]
- Setup conventional commits (commitlint + husky)
- Create PR template
- Create CODEOWNERS
- Setup branch protection rules
- Add changelog generation (standard-version)
- Tag v1.0.0 release (executed in Phase 09)

## Phase 08 — Agent & Command Integration [COMPLETED]
- Integrate GSD agent definitions for project
- Setup project-specific workflows
- Configure GSD hooks for development
- Create project-specific commands

## Phase 09 — Final Verification [IN PROGRESS]
- Full GSD framework audit (all categories 10/10)
- Security penetration testing
- Performance benchmarking
- Documentation completeness review
- Release readiness checklist
- **P0 follow-ups landed:**
  - Removed dev-mode quick-login bypass (`/auth/quick-login`, `/auth/users-list`)
  - Established MongoDB migration framework (`backend/migrations/`, `scripts/migrate.py`)
  - Switched document & export storage to GCS via unified `services.storage` facade
  - Prepared real provider integrations (`services/providers/`) for SendGrid, DIDIT, World-Check, ComplyAdvantage — pluggable behind env vars / DB-stored credentials
