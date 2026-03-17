# Roadmap

## Phase 01 — GSD Foundation & Documentation [IN PROGRESS]
- Initialize .planning/ structure with all GSD artifacts
- Create comprehensive README.md
- Create ARCHITECTURE.md
- Create .env.example
- Enable FastAPI auto-docs (OpenAPI/Swagger)
- Create deployment guide

## Phase 02 — Security Hardening [PENDING]
- Add rate limiting (slowapi)
- Add CSRF protection
- Add input sanitization middleware
- Add security headers (CSP, HSTS, X-Frame-Options)
- Secure file uploads (S3 integration)
- Remove dev-mode quick-login from production
- Add field-level PII encryption

## Phase 03 — Testing Infrastructure [PENDING]
- Setup Jest + React Testing Library for frontend
- Add frontend component tests (all pages)
- Expand backend pytest coverage to 90%+
- Setup Playwright for E2E tests
- Add coverage reporting (c8/istanbul + pytest-cov)
- Add security scanning (bandit, eslint-plugin-security)
- Setup load testing with locust

## Phase 04 — Build & Deployment [PENDING]
- Create Dockerfiles (backend, frontend)
- Create docker-compose.yml (full stack + MongoDB)
- Setup GitHub Actions CI/CD pipeline
- Add database migration framework
- Add structured JSON logging
- Add comprehensive health checks

## Phase 05 — Code Quality [PENDING]
- TypeScript migration for frontend (incremental)
- Decompose CaseDetail.js into sub-components
- Configure ESLint + Prettier with auto-fix
- Configure black + flake8 + mypy for Python
- Setup pre-commit hooks (husky + lint-staged)
- Enforce 300-line file size policy

## Phase 06 — Configuration & Feature Flags [PENDING]
- Implement centralized config system with Pydantic Settings
- Add feature flag system
- Create environment-specific configs (dev/staging/prod)
- Document all configuration options
- Add config schema validation

## Phase 07 — Git Workflow & Standards [PENDING]
- Setup conventional commits (commitlint + husky)
- Create PR template
- Create CODEOWNERS
- Setup branch protection rules
- Add changelog generation (standard-version)
- Tag v1.0.0 release

## Phase 08 — Agent & Command Integration [PENDING]
- Integrate GSD agent definitions for project
- Setup project-specific workflows
- Configure GSD hooks for development
- Create project-specific commands

## Phase 09 — Final Verification [PENDING]
- Full GSD framework audit (all categories 10/10)
- Security penetration testing
- Performance benchmarking
- Documentation completeness review
- Release readiness checklist
