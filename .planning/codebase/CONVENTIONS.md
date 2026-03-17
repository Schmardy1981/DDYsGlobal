# Code Conventions

## Python (Backend)
- **Formatting**: black (line length 120)
- **Linting**: flake8 (max line 120)
- **Type checking**: mypy (ignore-missing-imports)
- **Security**: bandit
- **Naming**: snake_case for functions/variables, CamelCase for classes
- **Async**: All route handlers and DB operations use async/await
- **Imports**: stdlib → third-party → local (isort enforced)
- **Error handling**: HTTPException with specific status codes
- **Validation**: Pydantic models for request/response schemas

## JavaScript/React (Frontend)
- **Formatting**: Prettier
- **Linting**: ESLint (react, jsx-a11y, import, react-hooks plugins)
- **Components**: Functional components with hooks only
- **State**: useState/useEffect for local, Context API for global
- **Styling**: Tailwind CSS utility classes, cn() helper for conditionals
- **UI Library**: shadcn/ui components exclusively
- **Icons**: Lucide React only (stroke-width 1.5, size 16)
- **Notifications**: Sonner toasts only
- **Naming**: CamelCase for components, camelCase for functions/hooks

## Git
- **Commits**: Conventional Commits (feat/fix/docs/refactor/test/ci/security)
- **Branches**: main (protected), feature/*, bugfix/*, hotfix/*
- **PRs**: Template required, at least 1 review
- **Tags**: Semantic versioning (v1.0.0)

## File Organization
- **Max file size**: 300 lines per component/module
- **One component per file** in frontend
- **Route modules**: One per domain entity in backend
- **Services**: Business logic separated from routes
