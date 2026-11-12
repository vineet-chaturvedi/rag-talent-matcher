# 13 · Step 9 Explained: Authentication and Roles

This document explains Step 9: **why** the system needs logins and roles, **what** users experience, **how** every part works (passwords, tokens, cookies, roles), **every file**, and the **alternatives** up to enterprise single sign-on.

**Read first:** 12 (Step 8). **Read with:** 05 (endpoints and settings), 08 (troubleshooting 401/403/429).

---

## 1. Where Step 9 sits

| Step | Gave us | Step 9 adds |
|---|---|---|
| 3 | The `users` table (email, hashed password, role, active) and "who did it" columns: `resumes.uploaded_by_id`, `projects.created_by_id`, `match_runs.created_by_id` | They're finally filled in |
| 4–8 | ~30 endpoints: uploads, re-processing, profiles, search, projects, matching | Every one now needs a logged-in user; destructive or admin actions need the admin role |
| 11–13 (next) | The Next.js portal | Will log in once and send the cookie automatically |

## 2. Why we need Step 9

Until now anyone who could reach port 8010 could read every resume, delete files, re-run the AI on everything, or see matching results. Resumes are **personal data** (DPDP Act in India, GDPR in the EU): the law expects access to be limited to people who need it, and to be traceable.

Step 9 answers three questions on every request:

| Question | Name | How |
|---|---|---|
| **Who** are you? | Authentication | Email + password once → a signed token on every request |
| **What** may you do? | Authorization | Your role: `admin` or `resource_manager` |
| **Who did** this? | Audit | `uploaded_by_id`, `created_by_id` saved with resumes, projects and match runs |

> **Step 9 puts a login in front of the whole API, gives each person a role that decides what they may do, and records who uploaded, created and ran what.**

There is **no AI in this step**, on purpose. But it protects the AI parts: only admins can trigger expensive AI work (`reextract` = ~12 minutes of LLM time), and only signed-in users can see AI-generated profiles and judgements.

## 3. Who can do what

| Action | admin | resource_manager | not logged in |
|---|---|---|---|
| Health check, log in | ✅ | ✅ | ✅ |
| See employees, resumes, profiles, chunks, queue stats | ✅ | ✅ | ❌ 401 |
| Search, projects, roles, requirements, candidates, match runs | ✅ | ✅ | ❌ 401 |
| Import employees, upload resumes, retry/delete resumes, re-extract, re-embed | ✅ | ❌ 403 | ❌ 401 |
| Manage users | ✅ | ❌ 403 | ❌ 401 |
| Dev tools (`/api/dev/*`) | ✅ (development only) | ❌ 403 | ❌ 401 |

**401 Unauthorized** = "I don't know who you are" (no or bad token). **403 Forbidden** = "I know who you are, but you may not do this."

## 4. The flows

### 4.1 First-time setup (developer)
```
pip install -r requirements.txt                    pwdlib[argon2] + PyJWT
python -m scripts.create_user --secret             → JWT_SECRET=... → paste into .env
python -m scripts.create_user --role admin --email admin@company.local --name "Portal Admin"
                                                   password asked twice, hashed with Argon2id, saved
start the server → log in → admin creates other users with POST /api/users
```

### 4.2 Logging in (end user → system)
```
Browser / script                       Server
POST /api/auth/login {email, password}
                                        login_guard: 5 failures in 15 min for this email? → 429
                                        find user (case-insensitive email)
                                        verify_password (Argon2id, ~0.1 s; runs even for unknown emails)
                                        wrong or inactive → 401 "Wrong email or password." (same message always)
                                        create JWT {sub: user id, role, iat, exp: +8 h}, signed with JWT_SECRET
← 200 {access_token, expires_at, user}   + Set-Cookie: rtm_access=<token>; HttpOnly; SameSite=Lax
```

### 4.3 Every later request
```
GET /api/projects   (Authorization: Bearer <token>   or   Cookie: rtm_access=<token>)
  main.py: router included with dependencies=[Depends(get_current_user)]
  get_current_user:  token from header or cookie → verify signature + expiry → load user from DB → active?
     no token / bad / expired → 401 · user disabled → 401
  admin-only endpoint? require_admin → role check → 403 if not admin
  endpoint runs (and can record user.id as uploaded_by / created_by)
```

### 4.4 What the end user experiences
- **Resource manager:** logs in once in the morning; the session lasts a working day (8 hours). Sees employees, profiles, runs matches. Upload buttons and admin pages are not available (the API refuses with 403; the Step 12 UI will hide them).
- **Admin:** also imports HR data, uploads resumes, re-processes, and manages users: creates accounts, resets passwords, changes roles, deactivates people who leave (deactivation works **immediately**, even for someone already logged in).
- **Wrong password 5 times:** "Too many failed logins. Try again in 15 minutes."
- **Forgotten password:** an admin sets a new one (`PATCH /api/users/{id}`); the person changes it with `POST /api/auth/change-password`.

## 5. The ideas behind it

### 5.1 Password hashing with Argon2id
We store a **hash**, a one-way fingerprint, never the password. At login the typed password is hashed and compared.
```
$argon2id$v=19$m=65536,t=3,p=4$<random salt>$<hash>
```
- **Slow on purpose** (~50–100 ms and 64 MB of memory per guess; 91 ms measured in testing): fine for one login, ruinous for an attacker trying billions of guesses on GPUs.
- **Salted:** a random salt per password, so identical passwords give different hashes and precomputed tables don't work.
- **Self-describing:** the parameters are in the string, so they can be raised later.
- Argon2id won the Password Hashing Competition and is OWASP's first recommendation; FastAPI's documentation uses `pwdlib` with Argon2. Alternatives: bcrypt (fine, but limited to 72 bytes), scrypt, PBKDF2 (needed for FIPS compliance). Never: plain SHA-256 or MD5 (far too fast).

**Password policy:** at least 12 characters, no other complexity rules. Current NIST guidance (SP 800-63B) says length beats forced symbols, and forced rotation makes passwords worse.

### 5.2 Timing and enumeration
Two quiet defences in `_authenticate`:
- the message is **identical** for "no such user" and "wrong password";
- for an unknown email, a **dummy hash** is still verified, so the response takes the same time.
Otherwise an attacker could discover which emails have accounts.

### 5.3 JSON Web Tokens (JWT)
```
eyJhbGciOiJIUzI1NiIs...  .  eyJzdWIiOiIzIiwicm9sZSI6ImFkbWluIi...  .  Xb3k...
header {"alg":"HS256"}       payload {"sub":"3","role":"admin","exp":...}   signature = HMAC-SHA256(header.payload, JWT_SECRET)
```
- The payload is only **encoded**, not encrypted: anyone can read it, so nothing secret goes in it.
- The **signature** proves the server made it: change `"role"` to `"admin"` and the signature no longer matches (tested: "Invalid token.").
- `algorithms=["HS256"]` is fixed when decoding: the token never chooses its own algorithm (the famous `"alg": "none"` attack).
- **Stateless:** no session table; any server with the secret can check a token.
- **Trade-off:** a token can't be "taken back" before it expires. We soften that by **loading the user from the database on every request**: a deactivated user is locked out immediately, and the role used is the current one from the database, not the one in the token.

### 5.4 Cookie or header?
| | `Authorization: Bearer` header | HttpOnly cookie |
|---|---|---|
| Used by | scripts, Swagger, other services | the browser (Next.js portal) |
| Stealable by injected JavaScript (XSS)? | yes, if stored in localStorage | **no**: `HttpOnly` hides it from JavaScript |
| Sent automatically | no | yes, which is why `SameSite=Lax` matters (not sent on cross-site POSTs → basic CSRF protection) |
| Our setting | supported | `HttpOnly; SameSite=Lax; Secure` in production |

The server accepts both. `localhost:3000` and `localhost:8010` count as the **same site** (ports don't matter for SameSite), so the cookie works for local development.

### 5.5 Brute-force protection
`login_guard.py` counts failed logins per email: 5 within 15 minutes → **429 Too Many Requests** with a `Retry-After` header. Kept in memory (resets on restart; one server). Enterprise: counters in Redis, per-IP limits at the API gateway, CAPTCHA, alerts.

### 5.6 FastAPI dependencies as security guards
```python
app.include_router(projects.router, dependencies=[Depends(get_current_user)])   # whole router
@router.post("/import", dependencies=[Depends(require_admin)])                  # one endpoint
async def upload_resume(..., user: User = Depends(require_admin)):               # and use the user
```
FastAPI runs dependencies **before** the endpoint; if one raises, the endpoint never runs. Security is declared next to each endpoint and shows up in `/docs` (padlocks, "Authorize" button), instead of being a check someone might forget inside the code.

### 5.7 The secret
`JWT_SECRET` must be long, random and private: anyone who knows it can make valid tokens for any user. In development, if it's missing, a random one is created at startup (with a warning; everyone is logged out on restart). In production the server **refuses to start** without it. Enterprise: keep it in a secret manager (Azure Key Vault, AWS Secrets Manager, HashiCorp Vault) and rotate it.

## 6. The files

```
login request ──▶ api/auth.py ──▶ auth/login_guard.py (too many tries?)
                               ──▶ auth/passwords.py   (verify Argon2id hash)
                               ──▶ auth/tokens.py      (create signed JWT) ──▶ token + cookie
any request   ──▶ main.py (router dependencies) ──▶ auth/dependencies.py: get_current_user / require_admin
                                                    ──▶ auth/tokens.py (verify) ──▶ users table
admin         ──▶ api/users.py (create / change / deactivate users)
developer     ──▶ scripts/create_user.py (first admin, secret)  ·  scripts/api_login.py (scripts log in)
```

| File | New / changed | What it does | Input → output |
|---|---|---|---|
| `app/auth/passwords.py` | new | Argon2id hashing, verification (with dummy hash), password policy | password → hash; password + hash → true/false |
| `app/auth/tokens.py` | new | Create and verify JWTs | user id + role → signed token; token → claims or `TokenError` |
| `app/auth/login_guard.py` | new | Counts failed logins, locks for 15 min after 5 | email → seconds locked |
| `app/auth/dependencies.py` | new | `get_current_user`, `require_roles`, `require_admin` | request → `User` or 401/403 |
| `app/api/auth.py` | new | `/login`, `/token` (Swagger), `/logout`, `/me`, `/change-password` | credentials → token + cookie |
| `app/api/users.py` | new | Admin user management; never deletes; protects the last admin | admin request → users |
| `app/schemas/auth.py` | new | `LoginRequest`, `TokenResponse`, `UserOut`, `UserCreate`, `UserUpdate`, `PasswordChange` | JSON ↔ Python |
| `app/services/users.py` | new | `count_users()` for the startup hint | — → number |
| `scripts/create_user.py` | new | First admin (password asked twice), `--secret` prints a JWT secret | CLI → user row |
| `scripts/api_login.py` | new | Scripts log in using `RTM_EMAIL` / `RTM_PASSWORD` or a prompt | client → client with token |
| `app/main.py` | changed | Public vs signed-in routers, admin-only dev tools, startup warnings, version 0.8.0 | — |
| `app/config.py` | changed | `JWT_SECRET`, `ACCESS_TOKEN_MINUTES`, `AUTH_COOKIE_NAME`, `jwt_secret_value` | `.env` → settings |
| `app/api/resumes.py`, `employees.py` | changed | Admin-only uploads, imports, retry, delete, re-extract, re-embed; uploader recorded | — |
| `app/api/projects.py`, `matching.py`, `matching/runner.py` | changed | Record who created the project / ran the match | — |
| `app/services/resumes.py` | changed | `add_resume(..., uploaded_by_id=)` | — |
| 5 scripts | changed | `login(client)` after opening the HTTP client | — |
| `requirements.txt`, `.env.example` | changed | `pwdlib[argon2]`, `PyJWT`; auth settings block | — |

No database change: the `users` table and the "by" columns were designed in Step 3.

## 7. Python you'll meet
| Code | Meaning |
|---|---|
| `Depends(get_current_user)` | Run this function first and pass its result in (or stop with its error) |
| `def require_roles(*roles): async def checker(...)...; return checker` | A **function that builds a dependency** (a closure remembers `roles`) |
| `Annotated` / `Depends` in `include_router(..., dependencies=[...])` | Apply a guard to every endpoint of a router |
| `HTTPException(status.HTTP_401_UNAUTHORIZED, ..., headers={"WWW-Authenticate": "Bearer"})` | The standard way to say "log in first" |
| `response.set_cookie(..., httponly=True, samesite="lax", secure=...)` | Send a cookie with its security flags |
| `if wait := login_guard.seconds_locked(email):` | Walrus: assign and test |
| `getpass.getpass()` | Read a password in the terminal without showing it |
| `secrets.token_urlsafe(48)` | Cryptographically secure random text (never `random` for secrets) |
| `field_validator("email")` | Clean a field (lowercase) when the model is created |
| `global _DEV_SECRET` | Change a module-level variable from inside a function |

## 8. Alternatives, industry standard and enterprise grade
| Need | Ours (learning) | Common production | Enterprise / world-class |
|---|---|---|---|
| Identity | Our own users table | Auth library (FastAPI Users, Authlib) | **Single sign-on** with the company identity provider: **Microsoft Entra ID** (Azure AD), Okta, Google Workspace, Keycloak (self-hosted), via **OpenID Connect** / SAML |
| Passwords | Argon2id, 12+ chars | Same + breached-password check (Have I Been Pwned k-anonymity API) | No passwords in our app at all (the IdP handles them), **MFA** / passkeys (WebAuthn) |
| Sessions | One 8-hour JWT | Short access token (15 min) + **refresh token** (rotated) | IdP sessions, token exchange, central logout, device policies |
| Roles | 2 fixed roles | Role-based access control (RBAC) with more roles | **Attribute/relationship-based** access (ABAC/ReBAC, e.g. OpenFGA, Cerbos): "managers see only their department's employees" |
| Brute force | In-memory counter | Redis counters, rate limits | API gateway / WAF (Cloudflare, Azure Front Door), anomaly detection |
| Secrets | `.env` | Environment variables in the deployment | Key Vault / Secrets Manager / Vault with rotation |
| Audit | "by" columns | Audit log table of every sensitive action | Immutable audit trail shipped to a SIEM (Splunk, Sentinel) |

**Why we built it ourselves anyway:** to understand exactly what an identity provider does for you. In a company deployment (Step 15) the login would move to the company's SSO (Entra ID / Okta) through OpenID Connect; `get_current_user` would then verify the **IdP's** token instead of ours, and the rest of the code (roles, `require_admin`, audit columns) stays the same.

## 9. Limitations
- **No refresh tokens:** after 8 hours you log in again; a stolen token works until it expires (unless the user is deactivated).
- **Logout only removes the cookie:** a copied token stays valid until expiry (no deny-list).
- **Lockout is in memory:** resets on restart; one server only. Locking by email lets someone lock a known user out on purpose (a known trade-off; per-IP limits help).
- **Two coarse roles:** every resource manager sees every employee. Department-level access is an ABAC/ReBAC upgrade.
- **No MFA, no password reset by email.**

## 10. Try it
```powershell
python -m scripts.create_user --secret      # add the line to .env, restart the server
python -m scripts.create_user --role admin --email admin@company.local --name "Portal Admin"
# /docs → "Authorize" → username = email, password → try any endpoint (padlock icons)
$env:RTM_EMAIL = "admin@company.local"; $env:RTM_PASSWORD = "<your password>"
python -m scripts.evaluate_matching --judge-top-n 0      # scripts now log in first
```
Experiments: call `GET /api/projects` without Authorize (401); create a resource manager and try `POST /api/resumes/reextract` (403); type a wrong password 6 times (429).

## 11. Glossary
| Term | Meaning |
|---|---|
| **Authentication** | Proving who you are |
| **Authorization** | Deciding what you may do |
| **Hash / salt** | One-way fingerprint of a password / random value mixed in per password |
| **Argon2id** | Modern slow, memory-hard password hash |
| **JWT** | Signed token carrying claims (user id, role, expiry) |
| **HMAC / HS256** | Signature made with a shared secret key and SHA-256 |
| **HttpOnly / SameSite / Secure** | Cookie flags: hidden from JavaScript / not sent cross-site / HTTPS only |
| **XSS / CSRF** | Injected JavaScript / a foreign site making your browser send requests |
| **RBAC** | Role-based access control |
| **SSO / IdP / OIDC** | Single sign-on / identity provider / OpenID Connect, the standard SSO protocol |
| **401 / 403 / 429** | Not logged in / not allowed / too many requests |
