# UAT Report — DDYs Global KYC/AML Platform

**Date:** 2026-05-25
**Method:** Static code review + flow tracing (no runtime — server not running)
**Scope:** All 3 portals (Customer, Tenant Workspace, Admin), full backend RBAC, case state machine
**Code base:** `/Users/christianschmitt/Desktop/DDYsGlobal/DDYsGlobal-repo`
**Volume reviewed:** 6.321 LoC Backend + 4.808 LoC Frontend, 22 Route-Module, 7 Services

---

## Executive Summary

The platform is **not production-ready**. While the architecture (FastAPI + React, RBAC matrix, multi-tenancy, audit logging, periodic jobs, AI document intelligence) is in place, **critical security and integrity gaps** prevent it from going live as a KYC/AML system handling regulated PII.

**Top-level verdict: FAIL.** Acceptable for an internal demo. Not acceptable for prospective customers, regulators, or real onboarding.

### Verdict matrix

| Portal | Flows tested | PASS | PARTIAL | FAIL |
|---|---|---:|---:|---:|
| Customer | 8 | 0 | 7 | 1 |
| Tenant Workspace | 16 | 1 | 11 | 4 |
| Admin | 11 | 3 | 7 | 1 |
| **Total** | **35** | **4** | **25** | **6** |

### The five things that block release

1. **Tenant isolation is broken in ~18 of 22 route modules.** `get_current_user` is wired everywhere; `require_tenant_access` / `require_permission` is wired in only **2** files (`tenants.py`, `cases.py`). Any authenticated user — including an END_CUSTOMER — can read or mutate cross-tenant data simply by sending the right ID in a query string or form field. ([Details](#3-rbac--tenant-isolation-systemwide).)
2. **Case state machine has a documented vs. implemented mismatch and the `rejected` state is unreachable.** README documents `INTAKE → NEW → DATA_GATHERING → SCREENING → RISK_ASSESSMENT → MAKER_REVIEW → CHECKER_REVIEW → APPROVED/REJECTED/ESCALATED → EDR_REVIEW → CLOSED`. Implementation uses 13 different states. `valid_transitions` (cases.py:247-259) has **no path to `rejected`**. The only way to reject a case is the unprotected quick-status endpoint, which bypasses gating. ([Details](#5-state-machine--integrity).)
3. **`PUT /api/cases/:id/status` (cases.py:190-227) accepts ANY authenticated user** and sets ANY status with NO gating checks. A BANK_USER (whose `can_approve_cases=False`) can flip a case to `completed` in one request. Same for END_CUSTOMER.
4. **PII document leak.** `GET /api/documents` (documents.py:120-133) with no filter returns ALL documents across ALL tenants. `GET /api/documents/{doc_id}` has no ownership check. KYC passports/proof-of-address are world-readable to any logged-in user.
5. **OTP-Tokens have no expiry enforcement** (auth.py:231-236, customer_portal.py:298-303). Invite tokens never expire (reminders.py:222-234). The invite flow hard-codes `123456` regardless of provider (customer_portal.py:272). Effectively no second factor on the customer side.

---

## 1. Architecture & Mapping

### 1.1 Backend route topology

22 router modules registered in `server.py`. All depend on `get_current_user` for authentication, but only `cases.py` and `tenants.py` ever call `require_tenant_access`, and **no route module** uses `require_permission` from `auth_middleware.py`. The `ROLE_PERMISSIONS` matrix exists but is dead code.

| Module | Endpoints | RBAC guard present? | Tenant isolation? |
|---|---:|---|---|
| auth | 7 (login, MFA, OTP, register, me) | n/a | n/a |
| cases | 8 | ✅ partial (`require_tenant_access` on create) | ✅ partial (filter on list) |
| tenants | 9 | ✅ ADMIN check on create/update | ✅ on get/users |
| documents | 5 | ❌ none | ❌ none |
| screening | 6 | ❌ none | ❌ none |
| risk | 3 | ❌ none | ❌ none |
| waivers | 3 | ❌ none (only "cannot approve own") | ❌ none |
| approvals | 3 | ❌ none | ❌ none |
| audit | 2 | ❌ none — anyone can read all logs | ❌ none |
| mi | 2 | ❌ none | ❌ none |
| policy | 5 | ❌ none | ❌ none |
| admin | 5 | ✅ inline ADMIN check | n/a |
| customer_portal | 9 | ❌ none beyond auth | ❌ none |
| notifications | 4 | ❌ ad-hoc user_id filter | n/a |
| edr | 4 | ❌ none | ❌ none |
| qa | 7 | ❌ none | ❌ none |
| video_ident | 6 | ❌ none | ❌ none |
| reminders | n/a | ❌ none | ❌ none |
| integrations | 3 | ❌ none | ❌ none |
| intake | 5 | ❌ none on assign/reject (should be staff-only) | n/a |

### 1.2 Frontend page topology

| Path | Page | Layout | Protected? |
|---|---|---|---|
| `/login` | LoginPage | – | no |
| `/intake` | IntakeForm | – | no (public) |
| `/admin` + 8 sub | AdminLayout | yes | yes |
| `/workspace` + 9 sub | TenantLayout | yes | yes |
| `/portal` + 3 sub | CustomerLayout | partial | dashboard/questionnaire protected; landing+invite public |
| `*` | redirect → /login | – | – |

Frontend does NOT validate role-to-portal mapping. AdminLayout/TenantLayout do not check that `user.global_role` actually matches the portal. A CASE_MANAGER can technically navigate to `/admin/tenants` URL — the backend will 403, but the layout still renders.

### 1.3 Case state machine

Code (cases.py:9-14) defines **13 statuses**, README documents a completely different set:

| Source | States |
|---|---|
| README.md:97-101 | INTAKE → NEW → DATA_GATHERING → SCREENING → RISK_ASSESSMENT → MAKER_REVIEW → CHECKER_REVIEW → APPROVED/REJECTED/ESCALATED → EDR_REVIEW → CLOSED |
| cases.py:9-14 | draft, customer_in_progress, customer_submitted, automated_checks, maker_review, checker_review, business_approval, compliance_approval, mlro_approval, completed, restricted, rejected, offboarded |

Transition graph from `valid_transitions` (cases.py:247-259):

```
draft → customer_in_progress
customer_in_progress → customer_submitted
customer_submitted → automated_checks
automated_checks → maker_review
maker_review → checker_review | customer_in_progress
checker_review → maker_review | business_approval | compliance_approval | completed
business_approval → compliance_approval | mlro_approval | completed
compliance_approval → mlro_approval | completed
mlro_approval → completed
completed → restricted | offboarded
restricted → maker_review | offboarded
```

**Unreachable states via state machine:** `rejected`. (Only via `PUT /api/cases/:id/status`, which has no gating.)
**Dead-end states:** `offboarded` (correct), `rejected` (no exit defined either way).
**Missing transitions:** No path from `customer_in_progress → draft` (cancel/restart). No path from `customer_submitted → maker_review` (skipping `automated_checks` — fine for now but undocumented).

---

## 2. Customer Portal — Detailed Findings

All 8 flows tested by the sub-agent and corroborated against my own reads.

### Flow 1 — Public Intake Form (`/intake`) → **PARTIAL**

✅ Three-step wizard with client validation, anonymous POST to `/api/intake/submit`.
❌ **Field-name drift backend↔frontend (HIGH).** `IntakeForm.js:102-106` posts `bank_street`, `bank_city`, `mobile_full`, `phone_full`, `phone_code`, `mobile_code`, `confirm_email`, `street_number`, `postal_code`. Backend `intake.py:22-40` reads NONE of these — they are silently dropped.
❌ **No rate limit, no captcha, no IP throttle** on a public endpoint that creates DB rows.
❌ **Returned "reference" is the first 8 chars of the internal UUID** (intake.py:52) — meaningless to the customer, no lookup endpoint to use it.
❌ **No email format / duplicate check.**

### Flow 2 — Invite Link (`/portal/invite/:token`) → **PARTIAL**

✅ Token-based landing, email-match check (customer_portal.py:268-269), JWT issued with case_id + tenant_id.
🔴 **CRITICAL — Invite token never expires.** `reminders.py:222-234` writes invite document without `expires_at`; nothing on the verify path checks it.
🔴 **CRITICAL — Invite is replayable.** `/verify` (customer_portal.py:286-313) doesn't check `invite.status`; an already-accepted invite still works.
🔴 **CRITICAL — Hard-coded `"123456"` OTP for invites** in all environments (customer_portal.py:272). The mock-only branching that auth.py has is missing here.
❌ **`GET /customer/invite/:token` leaks the full invite document** (customer_user_id, case_id, tenant_id) — useful for token enumeration attacks.

### Flow 3 — OTP Login → **PARTIAL**

🔴 **CRITICAL — OTP expiry never enforced** (auth.py:231-236 / customer_portal.py:298-303). The 10-minute `expires_at` written at insert is dead metadata.
🔴 **CRITICAL — Auto-provisioning of END_CUSTOMER user on `/auth/customer/otp-request`** (auth.py:164-178). Anyone can register an END_CUSTOMER user for any email.
🔴 **CRITICAL — Tenant binding is client-supplied.** `/customer/otp-verify` takes `tenant_id` from request body and stamps it into the JWT's `tenant_roles` with no verification (auth.py:245).
❌ **AuthContext doesn't model the customer/OTP flow** — customer pages bypass it, write to localStorage directly, reload the page. Fragile.
❌ **api/client.js 401 redirect sends a customer to `/login`** (staff login), not `/portal`.

### Flow 4 — Customer Dashboard → **PARTIAL**

🔴 **CRITICAL — `GET /customer/case` reads any case by tenant_id+case_ref** (customer_portal.py:13-43) with no ownership/JWT check. Case refs are short and guessable (`DDY-YYYYMMDD-XXXXXX`).
🔴 **CRITICAL — `GET /customer/case-by-id/:case_id`** (customer_portal.py:346-376) has no ownership check at all.
❌ **`POST /customer/submit`** accepts any case_id and flips status (customer_portal.py:202-220) — cross-tenant case-tampering possible.
❌ Dashboard does not poll, has no notifications, won't show staff updates until manual reload.

### Flow 5 — Questionnaire → **PARTIAL**

🔴 **CRITICAL — localStorage key mismatch.** Invite flow writes `ddys_customer_case_id` (CustomerInvitePage.js:46-49), questionnaire reads `ddys_customer_case_ref` (Questionnaire.js:33-41). Result: invited customer who clicks "Start Questionnaire" hits an empty 404. Dashboard CTA broken on the invite flow.
❌ **No ownership/tenant check on `/questionnaire/start`, `/:id` PUT, `/complete`** — any END_CUSTOMER JWT mutates any other tenant's questionnaire.
❌ **`complete` can duplicate UBO parties** if called twice (customer_portal.py:166-189 — no idempotency).
❌ **Address shape mismatch.** Frontend posts `address_street`, `address_city`, `address_country`. Backend stores `answers.address` as `addresses_json` directly (customer_portal.py:154). Result: `addresses_json={}`.

### Flow 6 — Document Upload → **PARTIAL**

🔴 **CRITICAL — No file-size limit.** `documents.py:29` does `await file.read()` unbounded. DoS surface.
❌ **No MIME allowlist server-side.** `accept` attribute on `<input>` is cosmetic.
❌ **`tenant_id` and `requirement_item_id` are trusted from form input**, never validated against JWT/ownership (documents.py:15-83).
❌ **MIME mismatch / disguised executables** not detected.
❌ Document Intelligence errors are silently swallowed (documents.py:92-94).

### Flow 7 — Video-Ident (customer side) → **FAIL**

❌ **No customer-facing video-ident UI.** No `/video-room/:roomId` route in App.js. The `customer_token` generated at video_ident.py:34 is never delivered to the customer (no email path, no notification, no UI surfaces it).
❌ Customer dashboard only shows static "You will be contacted" text (CustomerDashboard.js:306-328).

### Flow 8 — Status visibility → **PARTIAL**

❌ No polling, no SSE, no WebSocket. Customer cannot see staff actions in real time.
❌ Dashboard doesn't fetch `/customer/notifications` even though the endpoint exists.
❌ One-way submit lock: once `customer_submitted`, customer can't re-upload even if staff rejects a doc.

---

## 3. Tenant Workspace — Detailed Findings

### Flow 1 — Manual Intake (`/workspace/intake`) → **PARTIAL**

✅ Page exists, calls `POST /api/cases` and `POST /api/cases/:id/parties`. `_generate_requirements` works correctly per party type (cases.py:421-473).
❌ Only `POST /api/cases` calls `require_tenant_access`. The party-creation endpoint (cases.py:324-375) and the requirement-generation cascade don't recheck tenant.
❌ A staff user CAN create a case in tenant A while having tenant_roles only for tenant B — the body-passed `tenant_id` is trusted on `POST /api/cases/:case_id/parties`.

### Flow 2 — Cases Pipeline (`/workspace/cases`) → **PASS**

✅ Backend correctly scopes non-ADMIN to user.tenant_roles (cases.py:50-54). Filters work for status/risk/case_type.
⚠️ Minor: `cases.py:52` checks `global_role not in ["ADMIN"]` then uses `tenant_roles` from the JWT. CASE_MANAGER is treated the same as BANK_USER here. If a tenant ID is explicitly passed AND the user has no role for it, the query goes through anyway — the explicit `tenant_id` query parameter is NOT validated against `tenant_roles`. So a CASE_MANAGER assigned only to tenant A can list cases of tenant B by passing `?tenant_id=B`. **HIGH.**

### Flow 3 — Case Detail (`/workspace/case/:caseId`) → **PARTIAL**

✅ Frontend (916 LoC, the biggest page in the app) loads all related entities via the enriched `GET /api/cases/:id` (cases.py:124-151).
❌ **No tenant check on `GET /api/cases/:id`.** Any authenticated user can read any case by ID. (CRITICAL.)
❌ `cases.py:154-186` `PUT /api/cases/:id` — same. Any authenticated user can mutate any case.

### Flow 4 — Document review → **PARTIAL**

✅ Document Intelligence path (`services/document_intelligence.py`) is wired; auto-classification updates requirement status.
❌ Same RBAC holes as documents.py covered above.
❌ Approve/Reject of a document is just `PUT /api/cases/:case_id/requirements/:req_id` (cases.py:486-518) with arbitrary status — no validation of allowed transitions on requirements.
❌ No segregation between document uploader and document approver.

### Flow 5 — Screening Queue (`/workspace/screening`) → **PARTIAL**

✅ `POST /api/screening/run` exists (screening.py:13-97), iterates parties, persists hits, updates requirement statuses to `auto_passed` / `needs_review`.
❌ **Bug — wrong requirement_category match** at screening.py:70: query uses `requirement_category: run_type`, but the actual categories are `sanctions`, `pep`, `adverse_media`, `video_ident`, `identity`, `address`, ... — so for `run_type="sanctions"` it works, but if anyone calls with a different `run_type` the requirement update is silently skipped.
❌ No RBAC — BANK_USER (who has `can_run_screening=False`) can hit this endpoint.
❌ `GET /api/screening/hits` (screening.py:100-118) takes optional `tenant_id`. If omitted, returns hits across all tenants for any authenticated user. CRITICAL.

### Flow 6 — Risk Assessment → **PARTIAL**

✅ `POST /api/risk/assess` calls `services/risk_engine.py:compute_risk` — CRRM-like scoring.
✅ `POST /api/risk/challenge` correctly blocks downgrade-to-low when per-se PEP/high-risk-country flags are set (risk.py:71-75).
✅ Challenge creates MLRO approval task — good segregation primitive.
❌ No RBAC — BANK_USER can trigger risk assessment.
❌ `GET /api/risk/:case_id` — no tenant check.

### Flow 7 — Waivers (`/workspace/waivers`) → **PARTIAL**

✅ Approval chain derived from risk rating (waivers.py:32-37).
✅ "Cannot approve own waiver" check present (waivers.py:121-122) — good 4-eyes principle.
✅ 90-day cap on temporary waivers (waivers.py:28).
❌ No role check on `/waivers` POST — END_CUSTOMER can create a waiver.
❌ No verification that the approver matches the chain — waivers.py:124-141 lets any non-requester approve, regardless of `approval_chain_json`.
❌ Single-step approval — the documented chain (`case_manager → business_unit_head → mlro` for high risk) is never enforced; one approve call flips status from `pending` to `approved` directly.

### Flow 8 — EDR (`/workspace/edr`) → **PARTIAL**

✅ EDR alert creation with 28-day review deadline + 90-day completion deadline (edr.py:50-51) — matches typical regulator expectation.
✅ `POST /edr/:id/decide` creates either Full-EDR case or KUP case; KUP correctly does NOT reset NRD (edr.py:160).
❌ No role check.
❌ `POST /edr` accepts any case_id — END_CUSTOMER can create EDR alerts on any case.

### Flow 9 — QA (`/workspace/qa`) → **PARTIAL**

Spot-check: routes/qa.py:14-310 has 7 endpoints (reviews, sample, governance-pack, settings). No role guards present in route signatures from what I inspected. Marking PARTIAL pending deeper review.

### Flow 10 — Video-Ident (`/workspace/video-ident`) → **PARTIAL**

✅ Session creation generates customer + agent tokens (video_ident.py:34-35), room ID, internal WebRTC URL.
✅ Liveness/deepfake fields modeled.
❌ No frontend route `/video-room/:roomId` — the URL is generated but unusable.
❌ No RBAC — only VIDEO_AGENT should perform sessions (`can_video_ident=True`), but any authenticated user can.
❌ Session completion (`POST /video-ident/sessions/:id/complete`) accepts arbitrary liveness/deepfake scores from body — should be set by the WebRTC provider, not the client.

### Flow 11 — State Machine Transitions → **FAIL**

🔴 **CRITICAL — `rejected` state unreachable via state machine** (cases.py:247-259). Yet it's in CASE_STATUSES and used in MI dashboard reports.
🔴 **CRITICAL — `quick_status_change` (`PUT /api/cases/:id/status`)** at cases.py:190-227 has NO role check, NO gating, NO 4-eyes. A BANK_USER, VIDEO_AGENT, or END_CUSTOMER can set ANY case to ANY status in one HTTP call. This invalidates the entire maker/checker/MLRO workflow.
❌ **Maker = Checker is not enforced.** cases.py:273-275 has a comment `# Maker cannot be checker (but in this case we're transitioning TO checker, so the checker will validate)` — but the `pass` statement means the rule is NOT enforced. Same user can pull both reviews.
❌ **High-risk MLRO gating** (cases.py:277-286) only checks for an approval_task with `decision="approved"`. The approval_tasks have no role check (approvals.py:57-101) — any user (incl. the maker) can mark an MLRO task approved.
✅ Gating: all requirements must be `approved/waived/auto_passed` to enter `checker_review` (cases.py:266-271) — actually works.
✅ NRD computation for completed onboarding/EDR based on risk (cases.py:295-301) — correct.

### Flow 12 — Approvals → **FAIL**

🔴 **CRITICAL — `PUT /api/approvals/:task_id`** (approvals.py:57-101) has no role check, no 4-eyes, no assignment validation. Anyone authenticated can complete any approval task with any decision.
❌ `POST /api/approvals` takes `task_type` and `assigned_to` from the body — no validation that the assignee has the right role.

### Flow 13 — Audit Log → **FAIL**

🔴 **CRITICAL — `GET /api/audit`** (audit.py:13-28) returns ALL audit logs across ALL tenants to any authenticated user. PII + compliance-grade data leak. A BANK_USER of demobank can read DDYs' internal admin actions. A VIDEO_AGENT can read MLRO decisions on any case.
❌ Audit log is mutable from the API layer — no integrity hash, no append-only enforcement at storage level.
❌ Missing actor_user_id in some entries from `quick_status_change` and `decide_approval` — actually present, but no IP scrubbing logic for the `restricted` PII case.

### Flow 14 — MI Dashboard (`/workspace/mi`) → **PARTIAL**

mi.py has 2 endpoints (dashboard, global). Visible to all authenticated users, but the README's `can_view_mi` is set to `True` for BANK_USER + CASE_MANAGER + ADMIN. VIDEO_AGENT should not see MI — currently can.

### Flow 15 — Tenant Settings (`/workspace/settings`) → **PARTIAL**

Page exists (173 LoC). What it actually modifies is unclear without a server run; likely tenant.branding_json + regulations. Need to confirm what BANK_USER can edit. Route `PUT /api/tenants/:id` (tenants.py:138-168) explicitly requires ADMIN — so this page is broken for non-ADMINs. Frontend should hide it for non-ADMIN, doesn't.

### Flow 16 — RBAC Spot Checks → **FAIL**

| Endpoint | Required role | Actual guard |
|---|---|---|
| `POST /api/screening/run` | CASE_MANAGER+ (`can_run_screening`) | none — any auth user |
| `POST /api/risk/assess` | CASE_MANAGER+ | none |
| `POST /api/waivers` | CASE_MANAGER+ (`can_manage_waivers`) | none |
| `PUT /api/cases/:id/status` | CASE_MANAGER+ (`can_approve_cases`) | none |
| `PUT /api/approvals/:id` | depends on task_type | none |
| `GET /api/audit` | CASE_MANAGER+/ADMIN | none |
| `POST /api/video-ident/sessions` | VIDEO_AGENT/ADMIN | none |
| `POST /api/edr` | CASE_MANAGER+ | none |
| `GET /api/documents` | (tenant-scoped) | none + cross-tenant leak |
| `POST /api/intake/:id/assign` | ADMIN/CASE_MANAGER (staff) | none — anyone authenticated |

The `ROLE_PERMISSIONS` dict in `auth_middleware.py` and `require_permission()` function are **dead code**.

---

## 4. Admin Portal — Detailed Findings

### Flow 1 — Admin Login → **PASS**

✅ Standard JWT + TOTP MFA path through `LoginPage` → `/auth/login` → `/auth/mfa/verify` (auth.py:71-119). `AuthContext.getPortal()` correctly returns `admin` for `global_role=ADMIN`.
⚠️ Frontend does NOT auto-redirect post-login based on portal — only the App layer's `ProtectedRoute` blocks; routing must be triggered by login flow. Acceptable.

### Flow 2 — Admin Dashboard (`/admin`) → **PARTIAL**

Page is 83 LoC, calls a couple of `/api/admin/*` endpoints and MI. Not all endpoints were inspected; flagging as PARTIAL.

### Flow 3 — Tenants Management → **PASS**

✅ `GET /api/tenants` is ADMIN/CASE_MANAGER scoped (tenants.py:34-38).
✅ `POST /api/tenants` ADMIN-only with explicit check (tenants.py:46-47).
✅ `PUT /api/tenants/:id` ADMIN-only (tenants.py:142-143).
✅ Default policy bootstrap (policy version + 11 default rules) on tenant creation (tenants.py:64-104) — good.
⚠️ `DELETE /api/tenants/:id` not visible; soft-delete via `status=inactive` only? Need to confirm.

### Flow 4 — Users Management → **PASS**

✅ `GET /api/admin/users`, `POST`, `PUT` all check `global_role == ADMIN` (admin.py:18, 40, 105).
✅ Password hashed with bcrypt (admin.py:51, 120). Password_hash + mfa_secret stripped from responses.
❌ **Default password `Welcome123!`** (admin.py:50) — must be force-rotated. No mechanism to force first-login password change.
❌ No password complexity check.
❌ No protection against ADMIN demoting/deleting their own account (lockout risk).

### Flow 5 — Integrations → **PARTIAL**

integrations.py has 3 endpoints. PUT stores API keys in `system_settings`. Need confirmation they're either encrypted at rest or at least masked on read.

### Flow 6 — Prompts → **PARTIAL**

✅ Server-level `GET/PUT /api/prompts` (server.py:288-337). ADMIN-only check on PUT.
❌ GET has no role check — any authenticated user can read system prompts (low sensitivity but unnecessary leak).
❌ Audit log truncates `v[:50]` (server.py:332) — actual prompts not stored in audit, only previews.

### Flow 7 — Customer Form Preview → **PARTIAL**

Frontend-only page (140 LoC). Unclear if backend supports tenant-specific form schema. Currently a static preview.

### Flow 8 — Policy → **PARTIAL**

policy.py has 5 endpoints (versions, rules, rules/:id, versions POST). No role checks visible in router signatures. ADMIN check needs to be enforced — this is regulator-facing data.

### Flow 9 — Periodic Jobs → **PASS**

✅ `POST /api/jobs/run-now` (server.py:146-156): ADMIN check.
✅ `PUT /api/jobs/intervals` (server.py:194-214): ADMIN check, minimum 24h enforced.
✅ `GET /api/jobs/status` and `/intervals`: read-only, allowed for any auth user — acceptable.

### Flow 10 — Settings → **PASS**

✅ `GET/PUT /api/admin/settings` ADMIN-only (admin.py:147, 183).
✅ API keys are masked on read with `***configured***` (admin.py:166-172) — good.

### Flow 11 — Seed → **FAIL**

🔴 **CRITICAL — `POST /api/seed`** (server.py:217-225) is **public, unauthenticated**. Idempotent (checks for existing Demo Bank tenant), but if the demo data was wiped, anyone can re-seed and create the default ADMIN account `admin@ddys.com / Admin123!`. In production, this is an instant root takeover.

Mitigation: gated by rate limiter (5/min) — not sufficient.

### Cross-cutting admin findings

| Concern | Verdict | Evidence |
|---|---|---|
| Password hash returned | ✅ filtered everywhere checked | admin.py:26, 110, 139; auth.py:91, 117 |
| MFA secret returned | ✅ filtered | same |
| JWT secret | ✅ env-only, not returned | auth.py:15 |
| API keys masked | ✅ on read | admin.py:166-172 |
| Public seed endpoint | ❌ unauthenticated | server.py:217-225 |
| Prompts read public | ❌ | server.py:288-303 |

---

## 5. State Machine — Integrity Findings

### Critical issues

1. **Documentation drift** — README v "actual states" diverge entirely. Any auditor will flag this.
2. **`rejected` unreachable.** No transition target. Only reachable via the unprotected `quick_status_change`.
3. **`quick_status_change` is a backdoor.** No role check, no gating, no 4-eyes — invalidates the entire workflow.
4. **Maker = Checker not enforced** — the comment at cases.py:273-275 says it should be, the code says it isn't.
5. **MLRO approval can be self-approved** — approval_tasks has no role-check, so the same user can play maker, checker, and MLRO.
6. **`completed → restricted/offboarded`** — only path. Cannot go back to active investigation from `restricted` other than to `maker_review` — but a `restricted` case re-entering `maker_review` triggers no fresh customer engagement, which is operationally unusual.
7. **No `customer_in_progress → cancelled`** — once a customer starts, the case can never be cancelled by them or by staff without going through the full motion.

---

## 6. Edge Cases & Operational Concerns

### What's broken when…

| Scenario | Behavior | Verdict |
|---|---|---|
| Customer uploads 5 GB file | Worker OOMs | FAIL — no size limit |
| Customer uploads .exe renamed to .pdf | Stored, served via inline `Content-Disposition` | FAIL |
| Customer abandons case for 6 months | Case sits in `customer_in_progress` forever | FAIL — periodic jobs review deadlines for EDR/RR but not abandoned drafts |
| Two customers submit intake with same email | Two intake_requests rows created | FAIL — no dedup |
| Customer clicks invite link 6 months later | Works (no expiry) | FAIL |
| Invite link is leaked / forwarded | Works (no PoP, no IP binding) | FAIL |
| Customer submits questionnaire twice | Duplicate UBO parties | FAIL |
| Staff approves their own waiver | Blocked | PASS |
| Maker also acts as Checker | Allowed | FAIL |
| Same user approves their own MLRO challenge | Allowed | FAIL |
| BANK_USER tries to flip case to "completed" | Allowed via `PUT /:id/status` | FAIL |
| Periodic job fails | Logged, retried next cycle | PASS |
| MongoDB connection drops mid-request | 500 — no graceful degradation | PARTIAL |
| Rate limit triggered | 429 with `Retry-After` | PASS |
| GCS signed URL fails | Falls back to proxy | PASS |
| AI document analysis fails | Logged, swallowed, doc remains `uploaded` | PARTIAL — no retry queue, no flag to staff |

### Missing operational features

- **No password reset flow.** No `/auth/forgot-password`.
- **No customer "cancel my application" flow.**
- **No bulk operations** in cases pipeline (assign maker to many, screen many).
- **No SLA breach alerts** beyond the 28d/90d EDR clocks.
- **No GDPR delete / export request handling.**
- **No case-locking** — two case managers can edit the same case simultaneously without optimistic concurrency control.
- **No webhook out** for tenant integration (e.g., notifying the bank when a case completes).

---

## 7. Top 25 Bugs (consolidated, sorted by severity)

| # | Sev | Bug | Location |
|---|---|---|---|
| 1 | **CRITICAL** | `GET /api/audit` returns all audit logs across all tenants to any authenticated user | `backend/routes/audit.py:13-28` |
| 2 | **CRITICAL** | `GET /api/documents` returns all documents across all tenants if filters omitted | `backend/routes/documents.py:120-133` |
| 3 | **CRITICAL** | `GET /api/documents/:doc_id` no ownership check | `backend/routes/documents.py:136-151` |
| 4 | **CRITICAL** | `POST /api/documents/upload` trusts tenant_id/case_id/requirement_id from form data | `backend/routes/documents.py:15-83` |
| 5 | **CRITICAL** | `GET /api/customer/case` and `case-by-id/:id` no ownership check — cross-tenant case read | `backend/routes/customer_portal.py:13-43, 346-376` |
| 6 | **CRITICAL** | `PUT /api/cases/:id/status` no role check, no gating — any user flips any case status | `backend/routes/cases.py:190-227` |
| 7 | **CRITICAL** | `PUT /api/approvals/:task_id` no role check, no 4-eyes | `backend/routes/approvals.py:57-101` |
| 8 | **CRITICAL** | `rejected` state unreachable via state machine | `backend/routes/cases.py:247-259` |
| 9 | **CRITICAL** | OTP `expires_at` never enforced | `backend/routes/auth.py:231-236`, `customer_portal.py:298-303` |
| 10 | **CRITICAL** | Invite tokens never expire and are replayable | `backend/routes/reminders.py:222-234`, `customer_portal.py:286-313` |
| 11 | **CRITICAL** | Hard-coded `"123456"` OTP in invite verify path, all envs | `backend/routes/customer_portal.py:272` |
| 12 | **CRITICAL** | `POST /api/seed` public, can re-create default ADMIN account | `backend/server.py:217-225` |
| 13 | **CRITICAL** | No file-size limit on `/api/documents/upload` — DoS surface | `backend/routes/documents.py:29` |
| 14 | **CRITICAL** | Questionnaire start broken for invited customers (localStorage key mismatch) | `frontend/src/pages/customer/Questionnaire.js:33-41` vs `CustomerInvitePage.js:46-49` |
| 15 | **CRITICAL** | `/auth/customer/otp-request` auto-provisions END_CUSTOMER for arbitrary email | `backend/routes/auth.py:164-178` |
| 16 | **HIGH** | Maker = Checker not enforced; comment says blocked, code doesn't | `backend/routes/cases.py:273-275` |
| 17 | **HIGH** | Self-MLRO-approval possible via approval_tasks | `backend/routes/approvals.py:57-101` |
| 18 | **HIGH** | OTP tenant binding from client body, no validation | `backend/routes/auth.py:245` |
| 19 | **HIGH** | No MIME allowlist / executable detection on uploads | `backend/routes/documents.py:38` |
| 20 | **HIGH** | Intake form drops ~9 fields (bank_street, mobile, postal_code, etc.) silently | `frontend/src/pages/customer/IntakeForm.js:102-106` vs `backend/routes/intake.py:22-40` |
| 21 | **HIGH** | No customer video-ident UI; `/video-room/:roomId` not registered | `backend/routes/video_ident.py:34-52`, `frontend/src/App.js:85-94` |
| 22 | **HIGH** | Tenant `?tenant_id=B` query param honored even when user has no role for B | `backend/routes/cases.py:50-54` |
| 23 | **HIGH** | README state machine documentation does not match implementation | `README.md:97-101` vs `backend/routes/cases.py:9-14` |
| 24 | **HIGH** | Waiver approval chain modeled but not enforced — single approve flips status | `backend/routes/waivers.py:109-141` |
| 25 | **HIGH** | `quick_status_change` allows any user to set `completed/rejected/restricted` without 4-eyes | `backend/routes/cases.py:190-227` |

---

## 8. Recommendations (in priority order)

### P0 — Must fix before any external traffic

1. **Wire `require_permission()` and `require_tenant_access()` on every non-auth route.** Build a route-by-route RBAC matrix and ship a CI test that fails when a route lacks an explicit guard.
2. **Delete `quick_status_change`** or hide it behind `require_permission("can_approve_cases")` AND apply the full gating.
3. **Add `expires_at` checks on every OTP verify** (auth + invite). Single-use enforcement on invites.
4. **Add `expires_at` to invite tokens.** Default 14 days.
5. **Replace hard-coded `"123456"` in `customer_portal.py:272`** with the same provider-aware logic as `auth.py:189-191`.
6. **Gate `POST /api/seed`** behind an env flag (`ALLOW_SEED=true`) AND an admin token. Or remove from production builds.
7. **Document upload: size limit (e.g. 25 MB), MIME allowlist, content sniffing, derive tenant_id from JWT.**
8. **Audit log endpoint: ADMIN-only OR scoped to user's tenant_roles.**
9. **Fix Questionnaire localStorage key mismatch** (CustomerInvitePage writes `ddys_customer_case_id`; Questionnaire must read it).
10. **State machine: add transition path to `rejected`** from at least `maker_review`, `checker_review`, `business_approval`, and require 4-eyes for it.

### P1 — Should fix before pilot

11. **Enforce Maker ≠ Checker** in `transition_case` (real check, not a `pass`).
12. **Enforce approval-chain semantics on waivers** (multi-step approve, role-aware assignee).
13. **Enforce role on `approval_tasks` PUT** — decided_by must have the role the task requires.
14. **Tenant-scope filtering on every list endpoint.** Whitelist allowed query params; reject body-supplied tenant_id from non-ADMIN.
15. **Force password change on first login** for users created with the default `Welcome123!`.
16. **Implement customer-side video-ident UI** or remove the requirement from `_generate_requirements`.
17. **Fix intake field drift** — pick one canonical schema (frontend or backend) and align.
18. **Update README's documented state lifecycle** to match the implementation.
19. **Notifications: polling or SSE** in customer dashboard.
20. **Idempotency** on `complete_questionnaire`.

### P2 — Quality / DX

21. **Replace inline `if user.get("global_role") != "ADMIN"` patterns** with `Depends(require_permission(...))` to centralize.
22. **CI lint: every router function must declare a dependency on `get_current_user` AND a permission/role check.**
23. **PII redaction** on audit logs (mask emails, document filenames where sensitive).
24. **GDPR**: data subject access + erasure endpoints.
25. **Optimistic concurrency control** on cases (version field + If-Match header).
26. **Webhook outbox** for tenant integrations.
27. **Single-source RBAC frontend guards** (don't render admin links for non-admin).
28. **End-to-end tests** for the maker/checker/MLRO golden path AND the BANK_USER-attempts-to-approve negative path.

---

## 9. Test Coverage Snapshot

The repo's existing `backend_test.py` (14.221 bytes, ~300 LoC) covers auth + CRUD happy paths. **It does not cover RBAC negative paths, tenant isolation, state machine gating, or PII leakage** — the exact areas where the platform fails. Coverage of the failure modes above: **near zero.**

---

## 10. Addendum — Additional findings from deep dives

After completing the consolidated report above, the per-portal deep-dive agents surfaced material that wasn't visible in the first pass. Treat these as additions to the Top 25 (severity-tagged).

### Newly confirmed CRITICAL

26. **API keys stored plaintext in MongoDB.** `PUT /api/integrations/{key}` (integrations.py:186) and `PUT /api/admin/settings` (admin.py:188-199) persist raw API keys (Anthropic, Refinitiv/screening, SendGrid, Supabase, etc.) without encryption layer. A DB dump = full third-party-credentials compromise. — *integrations.py:186, admin.py:188-199*

27. **`POST /api/auth/mfa/setup` allows MFA-secret takeover.** Any active session can call it and OVERWRITE the user's existing TOTP secret with no re-auth (auth.py:122-137). A stolen / hijacked session can permanently lock the legitimate user out of their own MFA. — *auth.py:122-137*

28. **`POST /api/admin/seed`** is a second, equally unauthenticated seed endpoint that duplicates `/api/seed`. Closing only `/api/seed` is insufficient. — *admin.py:219-231*

29. **Risk engine is decorative.** `risk.py:13` receives `inputs:{}` from CaseDetail.js:99-104. With empty inputs, the risk engine defaults to category score 2 everywhere → outputs **"medium" for every case** regardless of actual party nationality, PEP flags, or screening hits. The CRRM score is fake. — *risk.py:13-43, risk_engine.py:14-19, CaseDetail.js:99-104*

30. **`PUT /api/screening/hits/:id` and `PUT /api/approvals/:id` have ZERO role guards.** A BANK_USER can mark every sanctions hit "false positive" and approve every pending task. The Approval workflow → State Machine completion chain collapses. — *screening.py:121-184, approvals.py:57-101*

### Newly confirmed HIGH

31. **Document viewer is broken in browsers.** `CaseDetail.js:154-158` calls `window.open(url + '?token=' + jwt)`. `view_document_file` (server.py:341-386) reads JWT from the Authorization header via `get_current_user` — query-string tokens are not supported. Document viewing fails with 401. — *CaseDetail.js:154-158, server.py:341-348*

32. **MFA opt-in for ADMIN.** Seed users (seed.py:89) have `mfa_enabled:false`; backend login skips MFA when disabled. ADMIN can log in with password alone — non-compliant for staff of a regulated KYC provider. — *seed.py:89, auth.py:83-93*

33. **Public unauthenticated `POST /api/intake/submit`** has no rate limit / captcha / email confirmation. Open spam surface that creates DB rows + downstream cases. — *intake.py:13-52*

34. **`GET /api/intake` (list) and `POST /api/intake/:id/assign`** lack tenant scoping and role checks. A BANK_USER of tenant A can read intake records destined for tenant B AND hijack them into their own tenant by calling `/assign`. — *intake.py:55-73, 88-193*

35. **`GET /api/integrations` no role check.** CASE_MANAGER / BANK_USER / VIDEO_AGENT can enumerate which integrations are configured (Anthropic, Refinitiv, Supabase, email provider, etc.). — *integrations.py:122-149*

36. **`GET /api/policy/versions` and `GET /api/policy/rules` no role check.** Regulator-facing policy data exposed to any logged-in user. — *policy.py:13-40*

37. **`GET /api/mi/dashboard`** honors `tenant_id` if passed but returns aggregated platform-wide data if omitted. BANK_USER can drop the param to see global pipeline volumes. — *mi.py:12-115*

38. **`/api/video-ident/join/{token}`** is unauthenticated AND tokens never expire. Leaked URL grants party PII forever. — *video_ident.py:261-274*

39. **Video-ident liveness/deepfake scores are `random.uniform(...)`.** No biometric evaluation occurs; the system claims liveness-pass via a coin flip. — *video_ident.py:167-169*

40. **`POST /api/auth/customer/otp-request` rate-limited at 10/min but auto-provisions users for arbitrary emails.** Combined with no OTP expiry enforcement, an attacker can resurrect old END_CUSTOMER accounts. — *auth.py:155-220*

41. **No tenant deactivation endpoint.** `tenants.py` has no DELETE route; `deleted:true` flag is queried but never written. UAT requirement "deactivate tenants" cannot be fulfilled. — *tenants.py (no DELETE)*

42. **Policy authoring UI absent.** `PolicyPage.js` is read-only; no UI to create/transition policy versions or rules. Backend POST/PUT exist but unreachable. Regulator updates require code deploy. — *PolicyPage.js, policy.py:122-145*

43. **Default user password `Welcome123!`** identical for every new account created via admin (admin.py:50). No force-rotate-on-first-login. — *admin.py:50*

44. **AdminLayout has no client-side role guard.** A CASE_MANAGER or BANK_USER who manually navigates to `/admin/users` loads the page; API calls then 403 but the admin nav shell renders → information disclosure about the admin surface. — *AdminLayout.js:20-83, App.js:43-48*

45. **`handleOsint` in CaseDetail.js calls non-existent `POST /osint/analyze`** (real route is `POST /screening/osint`). Dead button silently 404s; user sees a success toast. — *CaseDetail.js:106-112*

46. **`update_edr_alert`, `update_qa_review`, and `decide_edr` (full/kup case creation) skip audit logging.** Compliance-relevant mutations are untraceable. — *edr.py:77-99, qa.py:75-97, edr.py:117-177*

47. **Trust/foundation requirements gap.** `_generate_requirements` for `party_type=="trust"` only generates 4 requirements (no PEP, no adverse-media, no financial statements, no ownership chart). — *cases.py:449-455*

48. **`UsersPage.js` is read-only.** Backend supports user updates / tenant-role assignment / MFA reset / password reset — none is exposed in the UI. — *UsersPage.js, admin.py:101-140*

49. **`PORTAL_ACCESS` is dead code.** Defined in auth_middleware.py:34-38 but never imported / enforced anywhere. False sense of security in code review. — *auth_middleware.py:34-38*

50. **No `JWT_SECRET` startup validation.** `os.environ.get('JWT_SECRET')` returns None if unset; `jwt.encode(..., None, ...)` crashes — service degrades silently. — *auth.py:15, auth_middleware.py:10*

### Implication on the Top 25

Items 26-30 are CRITICAL and join items 1-15 in the "must fix before any external traffic" list. The total count of CRITICAL bugs is now **17**, HIGH **27**, MEDIUM/LOW dozens more. The verdict does not change — it solidifies.

---

## 11. Summary Verdict

**The DDYs Global KYC/AML Platform is FAIL for production release as of 2026-05-25.**

- **17 CRITICAL** issues across the three portals.
- **27 HIGH** issues, mostly RBAC/RBAC-shaped.
- The functional surface (UI flows, AI integration, MI dashboard, periodic jobs, audit infrastructure) is impressive in breadth.
- The compliance-grade execution layer (RBAC, tenant isolation, segregation-of-duties, audit immutability, OTP/token hygiene) is largely **absent in code despite being modeled in `auth_middleware.py`** — `require_permission`, `require_roles`, and `PORTAL_ACCESS` are dead code.
- Three documented compliance primitives are theatre: (a) the **risk engine** always returns "medium" because the frontend passes empty inputs; (b) the **video-ident liveness/deepfake check** is `random.uniform()`; (c) the **waiver approval chain** is modeled but never enforced.
- The case state machine has a **dead `rejected` state**, an **unreachable maker/checker SoD check**, and an **unprotected `quick_status_change` backdoor** that lets any authenticated user (including END_CUSTOMER) flip any case to any state.

A real-world KYC/AML provider must close at least items 1-15 and 26-30 of the consolidated bug list before serving any regulated traffic. After that, items 16-25 and 31-40 are required before pilot.

The good news: every gap above is fixable with the existing primitives. What's missing is the discipline of wiring them on every route and the negative-path test coverage that proves they stay wired. Recommended approach: a CI gate that fails any route handler that doesn't depend on a permission check.

---

*UAT performed via static code analysis on 2026-05-25. Confirm findings with runtime tests once a server is available. Recommended next step: spin up `docker-compose up`, seed demo data, and replay the top 50 bugs as automated negative-path tests.*
