# Invonics Technologies Storefront

A secure web storefront for selling digital resources — courses, books, and interview PDFs. The primary business objective is preventing unauthorized distribution and sharing of purchased resources.

## Status

Design phase. The approved architecture spec lives at [`docs/superpowers/specs/2026-09-11-invonics-storefront-design.md`](docs/superpowers/specs/2026-09-11-invonics-storefront-design.md). Implementation has not started.

## Stack

| Layer | Technology |
|---|---|
| Frontend | React (JavaScript), Vite, react-pdf viewer |
| Backend | FastAPI (Python), SQLAlchemy 2.0 async, Alembic |
| Database | PostgreSQL (normalized schema) |
| Payments | M-Pesa Daraja API (C2B) |
| Storage | MinIO / S3 (originals and per-recipient watermarked copies) |
| Deployment | docker-compose on a single VPS |

## What makes this different

The storefront is built around one requirement: a purchased PDF must not be redistributable.

- **Mandatory authentication.** No purchase or view without an account.
- **Drift-tolerant device binding.** Access tokens bind to the buyer's IP and device fingerprint. IP changes trigger one-time OTP re-verification rather than a hard lockout, because CGNAT on mobile networks rotates IPs mid-session.
- **Server-side watermarking.** Every page carries a visible vector watermark (buyer name, email, order ID, date) plus an invisible forensic fingerprint. Visible marks deter casual sharing; the fingerprint traces a leaked copy back to the buyer it was issued to.
- **Per-recipient cached artifacts.** Watermarked PDFs are generated once per (resource, buyer) and served through signed CDN URLs, which keeps byte-range and chunked streaming byte-deterministic.
- **Immutable payment ledger.** Every transaction state transition is an append-only insert in `orders_paid`. M-Pesa callbacks are idempotent on a unique receipt number, so Daraja's retries cannot double-process a payment.

Client-side controls — disabled right-click, print, and download — are deterrents, not protection. Screenshots and cameras defeat them. The load-bearing defenses are server-side.

## Architecture

```
React SPA ── Nginx (TLS, gzip, static) ── FastAPI (uvicorn) ── PostgreSQL
                                    │              ├── BackgroundTasks ── watermark generation ── MinIO/S3
                                    └── CDN ── signed URLs, Range, chunked
```

## Repository layout

```
docs/superpowers/specs/   Approved architecture specs
```

Application source (`api/`, `web/`, `docker-compose.yml`) will be scaffolded from the implementation plan.

## Getting started

Not yet runnable — scaffolding comes after the implementation plan. See the spec for the full architecture, schema, and flows.
