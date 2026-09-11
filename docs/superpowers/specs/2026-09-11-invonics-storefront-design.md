# Invonics Technologies Secure Storefront — Design Spec

Date: 2026-09-11
Status: Approved for implementation planning

## 1. Overview

A secure web storefront for Invonics Technologies selling digital resources: courses, books, and interview PDFs. The primary business objective is preventing unauthorized distribution and sharing of purchased resources.

Stack: React (JavaScript) frontend, FastAPI (Python) backend, PostgreSQL, docker-compose deployment on a single VPS. Payment via M-Pesa Daraja API (C2B).

## 2. Constraints (non-negotiable)

1. **Mandatory authentication.** Users must create an account and log in to purchase or view any resource.
2. **Drift-tolerant IP/device locking.** On first access to a purchased resource, the access token binds to the user's initial IP address and device fingerprint. IP changes trigger one-time OTP re-verification, capped at N re-binds per month. (Revision: strict 403-on-IP-change was rejected — Safaricom CGNAT rotates mobile IPs mid-session and would lock out legitimate buyers.)
3. **Secure content delivery.** Resources (PDFs) stream inline to a custom React viewer. Native downloading, printing, and right-clicking are disabled client-side. Client-side blocks are deterrents only; the real protection is server-side forensic watermarking (see Section 9).
4. **Dynamic watermarking.** Every page is watermarked server-side with the buyer's account details before being served. Technique: hybrid — visible vector text watermark (name, email, order ID, date) plus an invisible forensic fingerprint (buyer ID + token hash) embedded in page content streams. Vector overlay keeps text search/selection working; the invisible fingerprint traces leaked copies back to the source buyer even after visible marks are stripped.
5. **Network resilience.** Backend supports chunked transfer encoding and byte-range requests for lossless streaming over unstable connections. Requires deterministic bytes per recipient — served by per-recipient cached artifacts (see Section 8).
6. **Payment segregation.** M-Pesa transactions route to a dedicated dashboard using the `AccountReference` field (hard cap: 20 characters) to separate app payments from other business activity.
7. **Data integrity (ACID).** Read Committed isolation with row-level locking (`SELECT ... FOR UPDATE`) during callback processing and token redemption. Note: Read Committed does not prevent phantom reads; double-processing is prevented by a unique constraint on `mpesa_receipt` combined with row locks, not by the isolation level.
8. **Immutable ledger.** All transaction states recorded in an append-only `orders_paid` table — INSERT-only, no UPDATE, no DELETE. States: `pending`, `processing`, `confirmed`, `failed` (merged from the original five — `interrupted` folded into `failed` with a `failure_reason` column).
9. **Atomic rollbacks.** Interrupted business logic during streaming or payment processing triggers rollback to the last valid database state. Implemented as a saga: no long-lived DB transaction spans a stream; each state transition is a committed ledger INSERT, and failures write a compensating `failed` row plus partial-artifact cleanup.

## 3. Architecture

```
React SPA ── Nginx (TLS, gzip, static) ── FastAPI (uvicorn) ── PostgreSQL
                                    │              ├── BackgroundTasks ── watermark generation ── MinIO/S3
                                    └── CDN ── signed URLs, Range, chunked
```

- **Single VPS, docker-compose:** services `api`, `db`, `minio`, `frontend-nginx`. No Kubernetes for now — stateless API design kept so the app can move to K8s later if load demands.
- **No Celery/Redis.** Watermark generation runs on FastAPI `BackgroundTasks` (in-process). If retry queues become necessary later, ARQ is the designated bridge.
- **Backend:** FastAPI + SQLAlchemy 2.0 (async), Alembic migrations.
- **Frontend:** React (JavaScript, no TypeScript), Vite build, served by Nginx.

## 4. Database Schema (PostgreSQL, normalized)

### Tables

| Table | Purpose | Key constraints |
|---|---|---|
| `users` | id, email UNIQUE, phone UNIQUE, password_hash (argon2id), is_active, created_at | |
| `resources` | id, title, type ENUM(course, book, pdf), price (decimal), storage_key (original artifact), page_count, sha256, published | |
| `purchases` | id, user_id FK, resource_id FK, price_paid, created_at | UNIQUE(user_id, resource_id) — one license per user per resource |
| `orders_paid` | id, purchase_id FK, mpesa_receipt, phone, amount, account_reference, state ENUM(pending, processing, confirmed, failed), failure_reason, transitioned_at, payload jsonb | **Append-only.** UNIQUE(mpesa_receipt). INSERT-only; no UPDATE/DELETE enforced by app policy + trigger guard |
| `access_tokens` | id, user_id FK, purchase_id FK, token_hash, current_ip inet, device_fingerprint_hash, bind_count, rebinds_used, rebind_limit (default N), expires_at, revoked | token_hash UNIQUE |
| `token_binds` | id, token_id FK, ip inet, fingerprint_hash, bound_at, unbind_reason | Append-only history of every bind |
| `otp_codes` | id, user_id FK, purpose ENUM(rebind), code_hash, expires_at, attempts, consumed_at | Rate-limited issuance |
| `watermarked_assets` | id, resource_id FK, user_id FK, storage_key, state ENUM(generating, ready, failed), failure_reason, generated_at, format_version | **UNIQUE(resource_id, user_id)** — the generation claim lock |
| `audit_log` | id, actor, action, entity, entity_id, details jsonb, created_at | Generic append-only |

### Isolation and locking rules

- All business transactions run at Read Committed.
- Payment callback: idempotency gate `INSERT INTO orders_paid ... ON CONFLICT (mpesa_receipt) DO NOTHING`, then `BEGIN`, `SELECT ... FOR UPDATE` on the purchase row, insert transition row, `COMMIT`.
- Token redemption/re-bind: `SELECT ... FOR UPDATE` on the `access_tokens` row, validate rebind quota, insert `token_binds` row, update token, `COMMIT`.
- Watermark generation claim: `INSERT INTO watermarked_assets (resource_id, user_id, state='generating') ON CONFLICT DO NOTHING` — the unique constraint guarantees exactly one generator per (resource, user), including across multiple uvicorn workers.

## 5. Auth and Token Lifecycle

1. Registration: email or phone + password (argon2id). Email/phone verification before first purchase.
2. Login issues JWT access token (15 min) and refresh token (hashed, stored in DB, revocable).
3. All resource-view and purchase endpoints require a valid access token.
4. First access to a purchased resource: token binds `(current_ip, device_fingerprint)`; `bind_count += 1`; INSERT into `token_binds`.
5. Later access with a different IP: server issues OTP challenge (email/SMS). On success: new `token_binds` row, `rebinds_used += 1`, update `current_ip`. Over `rebind_limit` within the window → 403 with explanation.
6. Revocation: `UPDATE access_tokens SET revoked = true`. Bind history stays immutable.
7. Device fingerprint: client-side hash (user agent, screen, timezone, canvas hash) sent on bind; stored hashed only.

## 6. Payment Flow (M-Pesa C2B)

1. User initiates STK push; `AccountReference = "INV-<purchase_id>"` (≤ 20 chars) routes payment to the app dashboard.
2. Daraja callback (`POST /api/payments/callback`):
   - Validate shortcode and amount.
   - `INSERT ... ON CONFLICT (mpesa_receipt) DO NOTHING` — duplicate callbacks become no-ops (Daraja retries are common).
   - On insert: `BEGIN` → `SELECT purchase FOR UPDATE` → INSERT ledger row `confirmed` → `COMMIT`.
3. Ledger state machine (INSERT-only transitions):

```
pending ──> processing ──> confirmed
      \                    \
       └────────────────────└──> failed (failure_reason: "timeout" | "insufficient_funds" | "user_cancelled" | "stream_interrupted" | ...)
```

4. Callback timeout handling: background reconciliation sweeps `processing` rows older than the M-Pesa transaction TTL, queries Daraja status, writes the terminal ledger row.

## 7. Watermark Pipeline

1. On first access to a purchased resource, API validates JWT, purchase ownership, token IP/fingerprint.
2. Claim: `INSERT watermarked_assets (resource_id, user_id, state='generating') ON CONFLICT DO NOTHING`.
   - Conflict with a `ready` row: serve it.
   - Conflict with a `generating` row: return 202 with retry-after. The unwatermarked original is NEVER served — constraint 4 is absolute.
3. BackgroundTask (runs in-process after response):
   - Fetch original PDF from MinIO/S3.
   - Visible watermark: per-page vector text overlay — buyer name, email, order ID, purchase date (pypdfium2/pikepdf content-stream injection).
   - Forensic fingerprint: invisible marker embedded in page content streams encoding buyer ID + token hash (variant: also in PDF metadata + XMP).
   - Upload per-recipient copy to `watermarked/<resource_id>/<user_id>.pdf`.
   - UPDATE row: `state='ready'`, storage_key, format_version.
4. Generation failure: UPDATE row `state='failed'` + reason; next access retries the claim.
5. Reconciliation: startup sweep and periodic sweep mark `generating` rows older than X minutes as `failed` with reason `"worker_died"` — recovers from in-process BackgroundTask crashes without a queue.

## 8. Streaming and Content Delivery

- Access endpoint issues a signed URL to the per-recipient artifact in object storage (TTL 10–15 min), served through the CDN.
- Signed URLs give Range + chunked transfer for free; bytes are deterministic per recipient because the artifact is generated once.
- IP/device validation happens at URL issuance, not per byte. Signed URL is single-use-token-gated, non-guessable.
- Fallback endpoint: authenticated FastAPI streaming with Range support for cases where signed-URL flow is unavailable (e.g., storage not yet provisioned). Streams the per-recipient watermarked artifact only — never the original.

## 9. React Viewer

- react-pdf (pdf.js) rendering pages to canvas in a custom viewer.
- Disabled client-side: context menu, Ctrl+S/Ctrl+P handlers, drag-out download, native print stylesheet, PDF download toolbar.
- The viewer fetches the signed URL, not the raw resource endpoint.
- Honest security posture documented in code: canvas rendering is screenshot-able; no client-side control can stop photography or memory dumps. Real protection = server-side forensic fingerprint. Visible vector watermark marks every page with buyer identity.

## 10. Atomic Rollback (Saga)

- Worker flow: INSERT `processing` → generate artifact → INSERT `confirmed`.
- Failure at any step: INSERT `failed` + failure_reason, compensating cleanup (delete partial artifact, leave or reset `watermarked_assets` row for retry).
- No database transaction spans a stream. Each transition is its own committed INSERT. The database is always at the last valid committed state.
- M-Pesa callback rollback: if purchase fulfillment fails after a confirmed payment, write a `failed` ledger row with reason and queue (or flag) for refund/manual intervention — money never silently disappears.

## 11. Failure Modes and Error Handling

| Failure | Behavior |
|---|---|
| Duplicate M-Pesa callback | ON CONFLICT no-op |
| IP change beyond rebind limit | 403, audit_log entry, admin notification |
| Worker crash mid-generation | `generating` row swept to `failed` + `worker_died`, retried on next access |
| Storage upload failure | asset row `failed`, retry claim on next access |
| Signed URL expiry mid-read | viewer re-requests access endpoint (new URL) |
| Stream interruption | client resumes via Range; server logs byte progress in audit_log |
| Payment received but resource deleted | ledger `failed` + reason, refund workflow flag |

## 12. Security

- Passwords: argon2id only. Tokens: hashed at rest (SHA-256), never logged.
- Rate limiting on login, OTP, callback, and access endpoints (in-app middleware; Nginx `limit_req` at edge).
- Daraja callback authenticated per Safaricom requirements (IP allowlist + shortcode/amount validation).
- All resource storage private; only signed URLs and authenticated endpoints can read.
- audit_log records: logins, token binds/rebinds, URL issuance, generation jobs, callback outcomes.

## 13. Deployment

- docker-compose on single VPS: `api` (uvicorn, multiple workers), `db` (PostgreSQL), `minio` (object storage), `frontend-nginx`.
- Nginx: TLS termination, static React build serving, `limit_req`, proxy to API.
- Volumes: `pgdata`, `minio-data`.
- Stateless API + workerless design remains K8s-ready; no manifests in this phase.
- Future bridges (explicitly out of scope): ARQ + Redis for retry queues, Kubernetes for horizontal scaling.

## 14. Testing Strategy

- Unit: watermark injection (page count preserved, fingerprint recoverable), ledger state machine (legal + illegal transitions rejected), token bind/rebind logic.
- Integration: callback idempotency (same receipt twice = one ledger row), concurrent redemption (row-lock contention), concurrent generation claims (one winner across workers).
- Contract: Daraja callback payload fixtures, Range request responses (200/206/416).
- E2E (Playwright): purchase → access → viewer renders watermarked pages; IP-change OTP re-bind flow; disabled context menu/print shortcuts.
- Property: byte-range correctness — requesting all ranges of a known artifact reassembles to the exact original file.

## 15. Out of Scope (this phase)

- Kubernetes manifests, ARQ/Celery queue, admin refund UI, course video streaming (PDF-first), multi-tenancy.
