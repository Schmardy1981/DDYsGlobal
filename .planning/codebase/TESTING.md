# Testing Strategy

## Backend Testing
- **Framework**: pytest + pytest-asyncio
- **Coverage tool**: pytest-cov
- **Target**: 90%+ line coverage
- **Test types**:
  - Unit tests: Individual service functions
  - Integration tests: API endpoint testing with real MongoDB
  - Security tests: Auth, RBAC, input validation

## Frontend Testing
- **Framework**: Jest + React Testing Library
- **Coverage tool**: built-in Jest coverage
- **Target**: 90%+ line coverage
- **Test types**:
  - Unit tests: Component rendering, hooks, utilities
  - Integration tests: Page-level with mocked API
  - Accessibility tests: jest-axe

## E2E Testing
- **Framework**: Playwright
- **Scope**: Critical user journeys (login, case creation, approval flow)

## Security Testing
- **Python**: bandit (static analysis)
- **JavaScript**: eslint-plugin-security
- **Dependencies**: npm audit, pip-audit

## Performance Testing
- **Framework**: locust
- **Scope**: API endpoints under load

## CI Integration
- All tests run on every PR via GitHub Actions
- Coverage reports uploaded to Codecov
- Security scans run as separate job
