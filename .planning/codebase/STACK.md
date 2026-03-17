# Tech Stack

## Backend
| Technology | Version | Purpose |
|-----------|---------|---------|
| Python | 3.11+ | Runtime |
| FastAPI | 0.110.1 | Web framework |
| Uvicorn | 0.25.0 | ASGI server |
| Motor | 3.3.1 | Async MongoDB driver |
| PyMongo | 4.5.0 | MongoDB ODM |
| Pydantic | 2.12.5 | Data validation |
| PyJWT | 2.11.0 | JWT tokens |
| bcrypt | 4.1.3 | Password hashing |
| pyotp | 2.9.0 | TOTP 2FA |
| boto3 | 1.42.42 | AWS S3 (file storage) |
| stripe | 14.3.0 | Payments |
| emergentintegrations | 0.1.0 | LLM integration |
| pytest | 9.0.2 | Testing |
| black | 26.1.0 | Code formatting |
| flake8 | 7.3.0 | Linting |
| mypy | 1.19.1 | Type checking |

## Frontend
| Technology | Version | Purpose |
|-----------|---------|---------|
| React | 19.0.0 | UI framework |
| React Router | 7.5.1 | Routing |
| shadcn/ui | latest | Component library (Radix-based) |
| Tailwind CSS | 3.4.17 | Styling |
| Axios | 1.8.4 | HTTP client |
| React Hook Form | 7.56.2 | Form management |
| Zod | 3.24.4 | Schema validation |
| Recharts | 3.6.0 | Data visualization |
| Lucide React | 0.507.0 | Icons |
| Sonner | 2.0.3 | Toast notifications |
| CRA + Craco | 7.1.0 | Build tooling |
| Yarn | 1.22.22 | Package manager |

## Infrastructure
| Technology | Purpose |
|-----------|---------|
| MongoDB | Primary database |
| Local filesystem | File storage (to be migrated to S3) |
| Claude Sonnet | LLM for document intelligence + OSINT |
