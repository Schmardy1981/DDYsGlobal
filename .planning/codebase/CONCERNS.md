# Known Concerns & Technical Debt

## P0 — Critical (Pre-Production)
1. **Mock integrations**: Screening, email, and video ident are all mocked. Must implement real providers before production.
2. **Local file storage**: Documents stored on local filesystem. Must migrate to S3 for durability.
3. **No database migrations**: Schema changes are unversioned. Need migration framework.
4. **Quick-login code**: Dev-mode authentication bypass exists in codebase.

## P1 — High Priority
5. **CaseDetail.js (916 lines)**: Monolithic component needs decomposition into sub-components.
6. **No TypeScript**: Frontend has no type safety. Incremental migration needed.
7. **No frontend tests**: Zero test coverage on React components.
8. **Error messages may leak internals**: Stack traces and system paths in error responses.

## P2 — Medium Priority
9. **No global state management**: Complex pages use local state only — may cause prop drilling.
10. **Background job resilience**: Single asyncio task, no retry/dead-letter mechanism.
11. **No WebSocket**: Real-time updates use polling or manual refresh.
12. **Inline imports in server.py**: Multiple `from fastapi import HTTPException` inside functions.

## Resolved
- [2026-03-17] Rate limiting added via RateLimitMiddleware
- [2026-03-17] Security headers added via SecurityHeadersMiddleware
- [2026-03-17] Input sanitization added via InputSanitizationMiddleware
- [2026-03-17] Structured logging added via RequestLoggingMiddleware
- [2026-03-17] Docker setup created (Dockerfile.backend, Dockerfile.frontend, docker-compose.yml)
- [2026-03-17] CI/CD pipeline created (GitHub Actions)
- [2026-03-17] Centralized config with Pydantic Settings (config.py)
- [2026-03-17] Feature flag system implemented
- [2026-03-17] API documentation enabled (Swagger/ReDoc)
