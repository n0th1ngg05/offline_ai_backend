# Auth Backend Build Spec — Architecture & Context Specification

This document contains the complete initial architecture specification needed to build or maintain the standalone authentication backend from scratch.

## 1. What this project actually is

A standalone **auth backend** (FastAPI) that the user's real frontend
(`offline_frontend.zip`, already built, already wired to a fixed API
contract) will be pointed at. This backend owns: Super Admin login with
OTP, JWT issuance, forgot/reset password, and (eventually, not this phase)
Super Admin creating schools/users/admins under schools.

This is NOT the same thing as `offline_ai.zip` (the other reference repo
analyzed earlier in this conversation). That repo is a **separate,
downstream content/lesson-generation microservice** that only ever *reads*
users via read-only mirror models (`app/models/offlineai_core.py` —
`OfflineUser`, `OfflineClass`, etc., all mapped to schema `offlineai`,
`__tablename__` matching the real backend's tables) and verifies JWTs
issued elsewhere (`app/core/security.py`'s `get_current_offline_user`). It
has no register/login/OTP/mail code anywhere. It is useful here ONLY as a
pattern reference (model mixins, config style, security dependency shape) —
see section 3.

## 2. The real requirement, in the user's words

> Super Admin — who manages the entire thing/adding different
> schools/users and managing
>
> 1. Super Admin login using Email and Password
>    1. OTP to Email
>    2. Verify and Login (OTP via GMAIL SMTP)
> 1.1. Forgot Password
>    1. Send OTP to Email Address provided
>    2. if registered in DB, go to reset password page, reset password
>       then back to login page
> 2. Login Successful → Enter Dashboard
> 3. The Super Admin can add different schools/users with roles under
>    school/schools.

Explicit scope for THIS phase (per user, "for now, up till then"): build
only through successful login landing at the dashboard. Super Admin CRUD
for schools/users/admins is understood as the next phase, NOT built yet —
but the data model should accommodate it going forward (Super Admin is "the
ultimate god of this app" — full control).

## 3. Fixed tech stack (user's explicit instruction — do not deviate)

```
Python 3.10 · FastAPI · PostgreSQL 16 (pgvector) · SQLAlchemy 2.0 (asyncpg)
· Redis 7 & ARQ · SSE Pub/Sub
```

- **Python-only.** No Node.js anywhere in this build (this is a reversal of
  the earlier document-ingestion exercise's Node+Python split — that's
  scrapped).
- **SQLAlchemy 2.0 async style** (`Mapped[...]`, `mapped_column`), matching
  `offline_ai`'s `app/models/base.py` / `app/models/user.py` conventions —
  reuse `UUIDMixin`, `TimestampMixin`, `SoftDeleteMixin` patterns from
  there (string-UUID primary keys via `str(uuid.uuid4())`, not native
  Postgres UUID type, for consistency with that reference repo's style —
  though confirm this against the real backend's actual schema once it's
  known, since `offline_ai`'s OWN tables use `String(36)` UUIDs but its
  MIRROR models of the real backend use native `UUID(as_uuid=True)` — the
  real backend apparently uses native Postgres UUIDs. Prefer native
  `UUID(as_uuid=True)` for this new auth backend's own tables to stay
  consistent with what the real backend evidently already does, per
  `app/models/offlineai_core.py`'s `OfflineUser.id = Column(UUID(as_uuid=True), primary_key=True)`.
- **Redis + ARQ**: used for OTP storage (with TTL) and rate-limiting, not
  (yet) for a job queue in this phase — no long-running ingestion/worker
  task exists in this phase of the build. ARQ may be wired for future use
  but nothing in the login/OTP/reset flow strictly requires a job queue;
  OTP email sending can be fire-and-forget via FastAPI `BackgroundTasks` or
  a simple ARQ-enqueued task — lean toward ARQ since the user explicitly
  named it as part of the stack, to keep SMTP calls off the request path.
- **SSE Pub/Sub**: named in the stack but not required by the login/OTP/
  reset flow itself. Likely intended for a future real-time feature
  (e.g. live dashboard updates). Not part of this phase's deliverables —
  don't build it speculatively, just don't contradict it being added later
  (i.e. don't architect anything that would block adding Redis pub/sub +
  SSE endpoints later).
- **Bare metal first, Docker later** — this phase targets local execution
  only (venv + local Postgres + local Redis), matching how the earlier
  document-ingestion exercise was also run locally first. Docker Compose
  comes in a later phase once the bare-metal version works end to end.

## 4. Frontend contract — ALREADY FIXED, do not change

The frontend (`offline_frontend.zip`) is a working React (Vite + MUI +
Redux + react-hook-form + yup) app already wired to call a fixed set of
endpoints and expects specific response shapes. The backend MUST conform to
this contract exactly — the frontend will not be modified to match the
backend; the backend is built to match the frontend.

### Endpoints already called by the frontend (from `src/utils/constants.js`'s `API_URL` and `src/services/api/auth.api.js` / `src/services/actions/auth.action.js`)

```
POST /api/v1/auth/login                    — email+password login, may require OTP
POST /api/v1/auth/register                 — not in scope this phase, but route should exist/not 404 if easy
POST /api/v1/auth/forgot-password          — { email } -> sends OTP if email exists in DB
POST /api/v1/auth/forgot-password/verify   — { email, otp } -> { data: { reset_token } }
POST /api/v1/auth/reset-password           — { reset_token, new_password } -> success message
POST /api/v1/auth/activate                 — account activation, not in scope this phase
POST /api/v1/auth/verify                   — { ...context, otp } -> login OTP verification, issues token
POST /api/v1/auth/resend-otp               — resend login OTP
GET  /api/v1/auth/me                       — current user info from JWT
POST /api/v1/auth/student/request-otp      — student login, NOT in scope this phase
POST /api/v1/auth/student/verify-otp       — NOT in scope this phase
POST /api/v1/auth/student/select           — guardian/child selection, NOT in scope this phase
```

Base URL default (overridable via `VITE_API_BASE_URL` env var in the
frontend): `https://offline-ai-api.teexponent.com` — for local dev, the
frontend's `.env` needs `VITE_API_BASE_URL=http://localhost:8000` (or
whatever port the new backend runs on) pointed at the new local backend.

### Response envelope shape — ALL endpoints must return this shape

Inferred from `auth.action.js`'s handling of every response:

```json
{
  "success": true,
  "message": "human readable message",
  "data": { "...endpoint-specific fields..." },
  "verification_required": false,
  "errors": null
}
```

- `success: boolean` — checked first (`if (response.data.success)`), on
  false the frontend reads `response.data.message` and
  `response.data.errors || response.data` for error display.
- `message: string` — shown via toast.
- On error (`.catch`), frontend reads `error.response.data.errors ||
  error.response.data` — so a 4xx/5xx response body should ALSO follow
  `{success: false, message, errors}` shape, not FastAPI's default
  `{"detail": "..."}` shape. This means: **do not rely on FastAPI's default
  HTTPException body** — wrap errors in a custom exception handler that
  emits this envelope shape, or manually construct every error response
  this way.

### POST /api/v1/auth/login

Request: `{ identifier: string (email), password: string, remember_me?: boolean }`
(frontend sends `identifier`, not `email` — field name is `identifier`
despite being validated as an email via yup).

Two possible success responses:
1. **OTP required** (always true for Super Admin per the spec):
   ```json
   { "success": true, "message": "OTP sent to your email", "verification_required": true }
   ```
   Frontend then shows `OtpVerification`, with `verificationPayload` set to
   the ORIGINAL request data (`{identifier, password}` plus whatever else
   was in the submitted form) — this becomes the `context` passed to
   `UserVerificationAction` on OTP submit. **This means `/auth/verify`
   receives back `{identifier, password, otp}`** (spread of context + otp),
   not just `{email, otp}` — the backend must accept and validate
   accordingly (verify OTP matches what was sent for that email/identifier,
   ignore password on this call OR re-validate it — safer to just trust the
   already-password-validated session tied to the OTP record rather than
   re-checking password here, since password was already checked at the
   `/login` step before OTP was sent).
2. **No OTP needed** (not applicable to Super Admin per this spec, but
   endpoint shape supports it): `token` present directly:
   ```json
   { "success": true, "message": "...", "data": { "access_token": "...", ...user fields } }
   ```

Token is read as `response.data?.data?.access_token || response.data?.token`
— support `data.access_token` as the primary shape.

### POST /api/v1/auth/verify

Request: whatever was in `verificationPayload` (from login) spread with
`{otp}` — practically `{identifier, password, otp, remember_me}`.

Response (success): same `data.access_token` shape as login's non-OTP path,
PLUS user fields the reducer (`auth.reducer.js`'s `getPayloadUser`) reads
directly off `action.payload` (i.e. off `response.data.data`, spread):
```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "access_token": "<jwt>",
    "id": "<uuid>",
    "first_name": "...",
    "last_name": "...",
    "email": "...",
    "user_type": "super_admin",
    "status": "active",
    "is_first_login": false,
    "created_at": "...",
    "profile_picture_url": null,
    "schools": null,
    "school": null,
    "assigned_schools": null,
    "school_assignments": null
  }
}
```
(`role` is also read by the reducer — either top-level `payload.role` or
derived from `user_type`. Include `"role": "super_admin"` at the top level
of `data` too, to be safe, alongside `user_type`.)

### POST /api/v1/auth/resend-otp

Request: `{ email, phone, role, flow }` — whichever of these are non-empty
(frontend filters out empty/undefined fields, see `getResendPayload` in
`OtpVerification.jsx`). For Super Admin login flow, only `email` will be
present (no `phone`, no `role`, no `flow` set in the login context as
built by `AuthPage.jsx`/`UserLoginAction`). Re-sends an OTP to that email,
same as the original login step would have.

### POST /api/v1/auth/forgot-password

Request: `{ email }`. If email exists in DB, send OTP to it. Response
should succeed either way (don't leak whether the email exists) —
**but note**: the user's own spec explicitly says "if registered in DB, go
to reset password page" implying a check does happen — balance this
against not leaking account existence by always returning a generic success
message regardless of whether the email was found, while only actually
sending the OTP email when it IS found. The frontend always advances to the
next step (`VERIFY_CODE`) regardless of response content (it doesn't branch
on anything except HTTP success/failure), so this is safe to do: return
generic success, silently no-op the email send if not found.

Response: `{ success: true, message: "..." }`. (`data` not required here,
frontend just reads `data?.message`.)

### POST /api/v1/auth/forgot-password/verify

Request: `{ email, otp }`.

Response: `{ success: true, message: "...", data: { reset_token: "<token>" } }`
— `getResetToken()` in `ForgotPasswordPage.jsx` checks
`reset_token || resetToken || token`, in that priority order, so use
`reset_token` as the canonical field name. This reset_token should be a
SHORT-LIVED, single-purpose token (NOT a normal login JWT) — e.g. a signed
token with a `purpose: "password_reset"` claim and ~10-15 min expiry,
validated specifically by `/reset-password` and nothing else.

### POST /api/v1/auth/reset-password

Request: `{ reset_token, new_password }`.

Response: `{ success: true, message: "Password reset successfully..." }`.
After this, frontend resets its local flow state and returns to step 1
(frontend-only redirect/state reset — no backend redirect needed, this is
client-side routing).

### GET /api/v1/auth/me

Auth: `Authorization: Bearer <jwt>`. Returns current user's data in the
same `data: {...}` shape as the verify/login success response (minus
`access_token`). Used by `AuthBootstrap.jsx` (not yet read in detail — read
it if continuing this build, to confirm exactly when/how this gets called
on app load).

## 5. Data model

### users table (new, owned by this backend)

Must be compatible with `offline_ai`'s read-only mirror expectations
(`app/models/offlineai_core.py`'s `OfflineUser`) — i.e. whatever schema/
table this backend creates for users, offline_ai's mirror model
(`__tablename__ = "users"`, `__table_args__ = {"schema": "offlineai"}`)
implies the REAL backend's users table lives in a Postgres schema literally
named `offlineai`, table `users`, with at least these columns:
`id (UUID)`, `first_name`, `last_name`, `email`, `user_type (string)`,
`status (string, native Postgres enum uppercase: ACTIVE/INACTIVE/DELETED)`,
`deleted_at (nullable timestamp)`.

**Decision needed / recommended**: create this new auth backend's database
with a Postgres schema named `offlineai` (not `public`) for its `users`
table, so that later, when this backend and `offline_ai` are both pointed
at the same Postgres server/database, `offline_ai`'s existing mirror model
resolves against real data with zero changes on that side. This directly
answers the user's question "what does offline_ai consist of if it doesn't
handle this" — it's a consumer of this new backend's `users` table via
direct DB schema access (read-only), not via an API call between services.

Recommended full schema (extend `offline_ai`'s `OfflineUser` column list
with what THIS backend actually needs to own/write):

```sql
CREATE SCHEMA IF NOT EXISTS offlineai;

CREATE TYPE offlineai.user_status AS ENUM ('ACTIVE', 'INACTIVE', 'DELETED');

CREATE TABLE offlineai.users (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email               VARCHAR(255) UNIQUE NOT NULL,
    hashed_password     TEXT NOT NULL,
    first_name          VARCHAR(100) NOT NULL,
    last_name           VARCHAR(100) NOT NULL,
    phone               VARCHAR(30) UNIQUE,
    user_type           VARCHAR(50) NOT NULL,  -- 'super_admin', 'school_admin', 'content_admin', 'teacher', 'student', 'classroom_operator'
    status              offlineai.user_status NOT NULL DEFAULT 'ACTIVE',
    is_first_login      BOOLEAN NOT NULL DEFAULT true,
    last_login_at       TIMESTAMPTZ,
    profile_picture_url TEXT,
    created_by          UUID REFERENCES offlineai.users(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ,
    deleted_by          UUID
);
```

`user_type` values — CONFIRMED exact strings from `src/utils/roles.js`'s
`USER_ROLES`:
```
super_admin, client_super_admin, content_admin, school_admin,
classroom_operator, teacher, student
```
`SYSTEM_ADMIN_ROLES = {super_admin, client_super_admin, content_admin}` —
these three roles get `can()` → always `true` in the frontend's
`usePermissions` hook (`SYSTEM_ADMIN_ROLES.has(normalizedRole) || ...`),
REGARDLESS of the `permissions` array content. This means: **for this
phase's `super_admin` role, the login/verify response's `permissions` field
can safely be `[]`** — the frontend already grants full access by role
alone for this role. Use literal string `"super_admin"` for the seeded
user's `user_type` (this is the strictest of the three system-admin roles
per the separate `SUPER_ADMIN_ROLES = {super_admin, client_super_admin}`
set used elsewhere — confirms `super_admin` is the correct, topmost role to
seed, not `client_super_admin`).

No `schools` table needed THIS phase (out of scope), but
`app/models/school.py` in `offline_ai` shows the real backend has
`sections`, `school_class_section` tables — schools table itself wasn't
found in `offline_ai`'s models, meaning it likely lives in the real
backend's own schema too, not in `offlineai_core.py`'s mirrors (since
offline_ai apparently doesn't need to read schools directly). Not blocking
for this phase.

### OTP storage — Redis, not Postgres

Store OTPs in Redis with TTL (e.g. 5-10 min), keyed by purpose + identifier,
e.g.:
```
otp:login:{email} -> "123456"        EX 300
otp:forgot_password:{email} -> "123456"   EX 300
```
Separate keyspaces for login-OTP vs forgot-password-OTP so a leaked/guessed
OTP from one flow can't be replayed in the other. Rate-limit OTP
requests/resends per email (e.g. max 1 per 30-60s, matching frontend's own
`RESEND_SECONDS = 25` cooldown UI) using Redis TTL-based locks or counters.

### Reset tokens — short-lived JWT, not stored server-side (or store in Redis for revocability)

Recommend: a short-lived JWT with `{sub: user_id, purpose: "password_reset",
exp: now+15min}`, signed with the same JWT secret (or a separate one for
defense in depth — the user hasn't specified, default to same secret +
distinct `purpose` claim, simpler). `/reset-password` validates this token,
checks `purpose == "password_reset"`, and additionally store a Redis
key `used_reset_token:{jti}` to make the token single-use.

## 6. Security requirements carried over from the earlier (scrapped) document-ingestion build review

These principles still apply even though the Node/Python split is gone:
- Passwords: bcrypt (or Argon2, equally acceptable, pick bcrypt for
  consistency with earlier decisions in this conversation), never plaintext.
- Login timing: run a password-hash comparison even on unknown email, to
  avoid username-enumeration via response timing (same pattern used in the
  earlier Node build's `/auth/login`).
- JWT secret from env var, app fails fast at startup if missing.
- Never leak whether an email exists in the DB via forgot-password response
  content — see section 4's `/auth/forgot-password` notes.
- All error responses must still follow the `{success, message, errors}`
  envelope (section 4) — don't let FastAPI's default validation-error or
  HTTPException shape leak through unmodified.

## 7. Gmail SMTP — how OTP email sending works

User asked "should it happen in executing a google script kind of shit" —
answer: **no**, don't use Google Apps Script. Use Python's stdlib
`smtplib` (or a thin wrapper) to connect directly to Gmail's SMTP server
with an **App Password** (Gmail blocks plain password SMTP auth; requires
2FA enabled on the Gmail account + a 16-character App Password generated
at https://myaccount.google.com/apppasswords). Config:

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587          # STARTTLS
SMTP_USERNAME=<gmail address>
SMTP_PASSWORD=<16-char app password, NOT the real Gmail password>
SMTP_FROM_EMAIL=<same gmail address, or a display name + that address>
```

Send via ARQ-enqueued background task (or FastAPI `BackgroundTasks` as a
simpler fallback) so the HTTP request isn't blocked on SMTP round-trip
latency. OTP generation: random 6-digit numeric code
(`secrets.randbelow(900000) + 100000` or `"".join(secrets.choice(string.digits) for _ in range(6))`),
matching the frontend's `/^\d{6}$/` validation regex exactly.

## 7.5 File structure — explicit, per user instruction

User's instruction, verbatim: "the python backend should have the different
microservices in different files, its not that everything is ingested at
once." This means: strict separation by concern across files/modules —
auth logic, OTP logic, mail logic, user/DB logic, each isolated — NOT a
single monolithic `main.py` or a single `auth.py` containing everything.
This is still ONE FastAPI app/process (not literally separate deployable
microservices in this phase — that would contradict "bare metal first,
single app" implied elsewhere) but internally modularized so each concern
is independently readable, testable, and swappable. Target structure:

```
auth-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    — FastAPI app instantiation, router mounting, lifespan, CORS only. NO business logic here.
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py              — Settings (pydantic-settings), env loading
│   │   ├── database.py            — async SQLAlchemy engine/session
│   │   ├── redis.py               — async Redis client/pool
│   │   ├── security.py            — password hashing (bcrypt), JWT encode/decode helpers ONLY (no endpoint logic)
│   │   └── response.py            — the {success, message, data, errors} envelope + exception handlers
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py                — Base, UUIDMixin, TimestampMixin, SoftDeleteMixin (ported from offline_ai)
│   │   └── user.py                — the offlineai.users ORM model
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── auth.py                — Pydantic request/response models for every auth endpoint
│   ├── services/                  — ONE FILE PER CONCERN, this is the user's explicit requirement
│   │   ├── __init__.py
│   │   ├── otp_service.py         — OTP generation, Redis storage/TTL, verification, rate-limiting. NOTHING about email or HTTP in here.
│   │   ├── mailer_service.py      — Gmail SMTP sending ONLY (aiosmtplib). Takes a rendered subject+body, sends it. Knows nothing about OTPs or users.
│   │   ├── auth_service.py        — login/verify/forgot-password/reset-password BUSINESS LOGIC (orchestrates otp_service + mailer_service + DB), no FastAPI Request/Response objects here, plain Python functions taking a DB session and typed args, returning plain data — this is what makes it testable and what "different microservices in different files" cashes out to: auth_service.py doesn't know about HTTP, routers do.
│   │   └── user_service.py        — user lookup/creation DB queries (get_by_email, create_user, update_password, etc.) — the ONLY place raw user-table queries live; auth_service.py calls into this, never queries User directly itself.
│   └── api/
│       └── v1/
│           ├── __init__.py
│           └── auth.py            — FastAPI router ONLY: request parsing, calls into services/auth_service.py, wraps the result in the envelope via core/response.py. No business logic, no direct DB queries, no direct Redis calls here.
├── sql/
│   └── init.sql
├── requirements.txt
├── .env.example
└── README.md
```

Rule of thumb for every new piece of logic added in this build or later:
- Does it touch HTTP request/response shape? → belongs in `api/v1/*.py`
  (a router file), kept thin.
- Is it a business rule/workflow (e.g. "login requires OTP unless X")? →
  belongs in `services/*_service.py`.
- Is it a raw DB query? → belongs in `services/user_service.py` (or a new
  `*_service.py` per table/entity as more tables are added later, e.g.
  `school_service.py` when schools are built in a future phase).
- Is it OTP-specific (generate/store/verify/expire)? → `otp_service.py`
  only. Never inline Redis OTP calls into `auth_service.py` directly —
  always go through this module's functions.
- Is it email-specific (SMTP connection, sending)? → `mailer_service.py`
  only. It should expose a generic `send_email(to, subject, body)` — OTP
  email TEMPLATES (the actual subject/body text for an OTP email) belong in
  `auth_service.py` (or a future `templates.py` if more email types are
  added later), NOT hardcoded inside `mailer_service.py` itself, since
  `mailer_service.py` should stay a generic "can send any email" utility,
  reusable for non-OTP emails later (e.g. account activation, notifications).

This structure is what any future engineering work should follow when adding
new endpoints or logic — check which of the five bullets above a new piece
of code falls into before deciding which file it goes in.

## 8. Deliverables checklist for this phase

Matches the file structure in section 7.5 exactly — build in this order
(each step depends on the one before it):

- [ ] `app/core/config.py` — Settings (Python 3.10 compatible)
- [ ] `app/core/database.py` — async SQLAlchemy engine/session
- [ ] `app/core/redis.py` — async Redis client/pool
- [ ] `app/models/base.py` + `app/models/user.py` — `offlineai.users` ORM model
- [ ] `sql/init.sql` — schema `offlineai`, `users` table, seed ONE
      super_admin (email/password from user — ASK, don't invent)
- [ ] `app/core/security.py` — bcrypt hashing, JWT encode/decode helpers
      ONLY (no endpoint logic, no DB queries)
- [ ] `app/core/response.py` — `{success, message, data, errors}` envelope
      + exception handlers
- [ ] `app/services/user_service.py` — user DB queries (get_by_email,
      update_password, etc.) — ONLY place raw User queries live
- [ ] `app/services/otp_service.py` — OTP generate/store/verify/rate-limit
      via Redis — ONLY place OTP logic lives
- [ ] `app/services/mailer_service.py` — generic Gmail SMTP `send_email()`
      via aiosmtplib — knows nothing about OTPs or users
- [ ] `app/services/auth_service.py` — orchestrates the above three for
      login/verify/forgot-password/reset-password business logic — no
      FastAPI objects, no direct DB/Redis calls (goes through the other
      three services)
- [ ] `app/schemas/auth.py` — Pydantic request/response models matching
      section 4's contract exactly
- [ ] `app/api/v1/auth.py` — thin FastAPI router: parse request, call
      `auth_service`, wrap in envelope. No business logic here.
- [ ] `app/main.py` — app instantiation, router mounting, lifespan, CORS
- [ ] `requirements.txt` — Python 3.10, FastAPI, SQLAlchemy 2.0, asyncpg,
      redis, arq, aiosmtplib, PyJWT, bcrypt directly (not passlib — passlib
      is unmaintained and has known bcrypt-73-byte-warning issues; use
      `bcrypt` package directly instead), pydantic-settings
- [ ] `.env.example`
- [ ] README with bare-metal run instructions (venv, local Postgres setup,
      local Redis, how to seed the first super admin, how to test each
      endpoint with curl)
- [ ] NO Docker in this phase — bare metal only, per explicit instruction

## 9. Open questions the user has NOT yet answered (ask, don't assume, if resuming)

- Whether `/auth/register`, `/auth/activate`, student-login endpoints need
  to exist as functional stubs (return a clear "not implemented" in the
  success envelope shape) vs. not exist at all (404) — frontend won't call
  them for the Super Admin flow, so this likely doesn't block anything, but
  worth confirming if the frontend's route guards/other pages error out on
  a missing endpoint during dev.
- First super admin's seed email/password — ask the user directly rather
  than inventing one.
- Whether JWT access tokens need a refresh-token pairing (frontend's
  `setRefreshToken` exists in `cookies.js` and is called in
  `SelectStudentChildAction`, suggesting refresh tokens are part of the
  broader design) — not required for Super Admin's login path specifically
  per the response shapes seen so far (only `access_token` is read off
  login/verify responses, no `refresh_token`), so treat as OUT of scope
  this phase unless the user says otherwise.
