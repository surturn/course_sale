# course_sale (Invonics Technologies Storefront)

Storefront that sells digital resources (notes, books, interview PDFs) to students. Pay with M-Pesa, read in the browser, every copy watermarked with the buyer's identity.

## Stack
- Frontend: React 18 (JavaScript), Vite, react-pdf.
- Backend: FastAPI, SQLAlchemy 2.0 async, Alembic, pypdf.
- DB: PostgreSQL 16. Payments: M-Pesa Daraja STK push. Files on a local disk volume.
- Web: Caddy (HTTPS, static SPA, `/api` proxy).

## Layout
`backend/`, `frontend/`, `docker/`, `docs/`, `design/`, `tasks/` (task breakdown), `content/`.

## Commands
- Dev DB: `docker compose -f docker/docker-compose.dev.yml up -d db`
- Prod: `docker compose -f docker/docker-compose.prod.yml --env-file docker/.env.prod up -d --build`
- Make admin: `... exec api python -m scripts.make_admin <email>`
- Backend tests: pytest in `backend/` (isolated test DB; see README).

## Rules (payments, treat as money paths)
- Callbacks are idempotent: a replayed M-Pesa callback must not credit twice.
- Amounts come from the server, never the client.
- Block duplicate STK prompts. The Daraja contract is tested.
- Watermarks are per buyer and generated on first open. Device cap is `REBIND_LIMIT_PER_MONTH`. IPs are recorded, not enforced.
- Run the `security-check` skill before any change to payments or auth.

## Deploy
README says docker compose on a single VPS (Caddy). Railway takes precedence for now (services plus PostgreSQL, from GitHub). Sydney plans to move major projects to a Contabo VPS later, so the Docker and Caddy setup is the future path, keep it working.

## Session state (update at the end of each session)
- 2026-10-09: working end to end (accounts, catalog, checkout, ledger, library, watermarked reader, admin uploads). Last commit: duplicate STK prompt block.
- Next: not recorded. Check `tasks/`.

## Verify (see global rule: drive it like a user, mobile 390x844 and desktop 1440x900, screenshots, fix until it works)
- Bring up the dev stack, register, log in, browse, run checkout against a mocked or sandbox Daraja callback, replay the callback (must not credit twice), open the watermarked reader.
- Payments cannot be verified live without real money: say so.
