# course_sale (Invonics Technologies Storefront)

Storefront that sells digital resources (notes, books, interview PDFs) to students. Pay with M-Pesa, read in the browser, every copy watermarked with the buyer's identity.

## Stack
- Frontend: React 18 (JavaScript), Vite, react-pdf.
- Backend: FastAPI, SQLAlchemy 2.0 async, Alembic, pypdf, Pillow (covers), defusedxml (news feeds).
- DB: PostgreSQL 16. Payments: M-Pesa Daraja STK push. Files on a local disk volume.
- Web: Caddy (HTTPS, static SPA, `/api` proxy).

## Layout
`backend/`, `frontend/`, `docker/`, `docs/` (spec, free library guide, UI conventions), `design/`, `tasks/` (task breakdown), `content/`. `.agents/` and `.claude/skills/` hold third-party design skills installed with `npx skills add` (see README). They are git-ignored, and `skills-lock.json` records their sources.

## Commands
- Dev DB: `docker compose -f docker/docker-compose.dev.yml up -d db`
- Prod: `docker compose -f docker/docker-compose.prod.yml --env-file docker/.env.prod up -d --build`
- Make admin: `... exec api python -m scripts.make_admin <email>`
- Backend tests: `COOKIE_SECURE=false pytest` in `backend/` (isolated test DB; see README). Run `alembic upgrade head` on the dev and test databases after pulling new migrations.

## Rules (payments, treat as money paths)
- Callbacks are idempotent: a replayed M-Pesa callback must not credit twice.
- Amounts come from the server, never the client.
- Block duplicate STK prompts. The Daraja contract is tested.
- Watermarks are per buyer and generated on first open. Device cap is `REBIND_LIMIT_PER_MONTH`. IPs are recorded, not enforced.
- Run the `security-check` skill before any change to payments or auth.
- The free library and news data must stay behind the disclaimer gate (`require_disclaimer`). Feed URLs are hardcoded, never user input.
- Do not run scripts that ship inside third-party skills (for example Impeccable's launcher, which downloads a binary) without reading them and the user agreeing.

## Deploy
Production runs on a Contabo VPS (moved off Railway on 2026-11-03) with `docker/docker-compose.prod.yml`: Postgres, API and Caddy (HTTPS, SPA, `/api` proxy). The API runs `alembic upgrade head` on every start. State lives in the `pgdata` and `storage` named volumes (PDFs, covers); they survive `up -d --build`, never use `down -v`. Back up both nightly and copy them off the server (README, Deploy step 5).

## Session state (update at the end of each session)
- 2026-10-09: working end to end (accounts, catalog, checkout, ledger, library, watermarked reader, admin uploads). Last commit: duplicate STK prompt block.
- 2026-11-03: added the free library, tech news, disclaimer gate, covers and a design pass. Nothing in payments or auth changed. Details are in `docs/free-library-news-and-disclaimer.md` and `docs/ui-conventions.md`. In short:
  - `/free` and `/news` pages. Free links live in `backend/app/data/free-resources.json` (add an entry to add a link). News comes from a fixed list of RSS feeds in `backend/app/api/news.py`, cached 30 minutes, last good copy served if all feeds fail. Feed URLs are never taken from the client.
  - Both are gated: `GET /api/v1/free-resources` and `/api/v1/news` return 403 until the visitor ticks the disclaimer (`POST /api/v1/disclaimer/accept`). Acceptances are stored in `disclaimer_acceptances` (migration `2720f272fa5d`); the `aggregator_ok` cookie holds a random token for one year; accounts are recognised across devices; bump `VERSION` in `backend/app/api/aggregator.py` to ask everyone again; 300 accepts per IP per hour.
  - Covers: admins upload one per resource on `/admin` (`POST/DELETE /api/v1/admin/resources/{id}/cover`, migration `8b23f849fdc5`). Pillow re-encodes to 600x800 WebP at `storage/covers/<id>.webp`. Without an upload, `Cover.jsx` draws a generated geometric cover.
  - UI: flat, tone-stepped, no glass or gradients (except the brand highlighter on headings), shadow only on the disclaimer dialog, contrast at least 4.5:1, tap targets at least 44px. Topic filters are the scrollable `ChipRow`. The reader and admin pages were not redesigned.
- Open follow-ups: retention policy for disclaimer rows (they hold IP and browser strings); link-check the non-GitHub free-library sites; check `/news` on the Contabo VPS (live feeds have never been fetched from the dev sandbox); redesign the reader and admin pages. See `tasks/plan.md` item 14.
- Next: not recorded. Check `tasks/`.

## Verify (see global rule: drive it like a user, mobile 390x844 and desktop 1440x900, screenshots, fix until it works)
- Bring up the dev stack, register, log in, browse, run checkout against a mocked or sandbox Daraja callback, replay the callback (must not credit twice), open the watermarked reader.
- Payments cannot be verified live without real money: say so.

## Caveman mode (always on)
Reply in caveman style: answer first, no filler, all technical facts kept. Follow the `caveman:caveman` skill rules where installed. Stays on until the user says "stop caveman" or "normal mode". Full sentences for security warnings, irreversible actions, questions to the user, and anything written to files, commits, PRs or docs.
