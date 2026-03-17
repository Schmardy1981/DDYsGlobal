# Requirements

## v1 — MVP Hardening (Current Sprint)

### Architecture & Structure
- REQ-ARCH-01: Complete .planning/ directory with all GSD artifacts
- REQ-ARCH-02: ARCHITECTURE.md documenting system design, data flow, component interaction
- REQ-ARCH-03: Structured artifact templates for all planning documents

### Documentation
- REQ-DOC-01: Comprehensive README.md with setup, usage, architecture overview
- REQ-DOC-02: .env.example with all required environment variables documented
- REQ-DOC-03: OpenAPI/Swagger documentation auto-generated from FastAPI
- REQ-DOC-04: Frontend component documentation
- REQ-DOC-05: Deployment guide

### Security
- REQ-SEC-01: API rate limiting middleware (slowapi)
- REQ-SEC-02: CSRF protection on state-changing endpoints
- REQ-SEC-03: Input sanitization and XSS prevention
- REQ-SEC-04: Field-level encryption for PII data
- REQ-SEC-05: Secure file upload to S3 (not local filesystem)
- REQ-SEC-06: Remove quick-login dev mode code from production paths
- REQ-SEC-07: Content Security Policy headers
- REQ-SEC-08: Helmet-equivalent security headers

### Testing
- REQ-TEST-01: Frontend unit tests with Jest + React Testing Library (90%+ coverage)
- REQ-TEST-02: Backend unit tests with pytest (90%+ coverage)
- REQ-TEST-03: E2E test setup with Playwright
- REQ-TEST-04: Coverage reporting integrated in CI
- REQ-TEST-05: Load testing setup with locust
- REQ-TEST-06: Security scanning (bandit for Python, eslint-plugin-security for JS)

### Build & Deployment
- REQ-BUILD-01: Docker setup (Dockerfile for backend, frontend, docker-compose)
- REQ-BUILD-02: CI/CD pipeline (GitHub Actions: lint, test, build, deploy)
- REQ-BUILD-03: Database migration framework (mongomigrate or custom)
- REQ-BUILD-04: Health check endpoints with dependency status
- REQ-BUILD-05: Structured logging with JSON output
- REQ-BUILD-06: Environment-based configuration management

### Code Quality
- REQ-QUAL-01: TypeScript migration for frontend
- REQ-QUAL-02: CaseDetail.js decomposition into sub-components
- REQ-QUAL-03: ESLint + Prettier configuration with pre-commit hooks
- REQ-QUAL-04: Python linting (black, flake8, mypy) with pre-commit hooks
- REQ-QUAL-05: Maximum file size policy (300 lines per component)

### Configuration
- REQ-CONF-01: Centralized config system with validation
- REQ-CONF-02: Feature flag system for progressive rollout
- REQ-CONF-03: Environment-specific configuration (dev, staging, prod)
- REQ-CONF-04: Config documentation and schema validation

### Git Workflow
- REQ-GIT-01: Branch protection rules for main
- REQ-GIT-02: Conventional commits enforcement
- REQ-GIT-03: PR template with checklist
- REQ-GIT-04: CODEOWNERS file
- REQ-GIT-05: Release tagging and changelog generation

## v2 — Production Readiness (Out of Current Scope)
- Real screening provider integration (DIDIT)
- Real email provider (SendGrid/Resend)
- WebRTC video identification
- SSO/SAML integration
- Data residency controls
- Horizontal scaling for background jobs
