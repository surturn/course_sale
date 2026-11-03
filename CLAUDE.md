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
- 2026-11-03 (later): PR #1 merged. Branch `feat/guest-checkout-mpesa-prod` (not pushed yet): guest checkout, till-aware Daraja client, order reconciler. Details in `docs/mpesa-production.md`. In short:
  - Guests buy via `POST /api/v1/orders/guest` (name, email, phone). They get a passwordless account (`users.is_guest`, nullable `password_hash`, migration `4d2f7a91c3be`) and a session, so library, watermark and device cap are unchanged. An email or phone with an existing account gets 409 "log in" (never auto-login). Guests set a password after paying (`POST /auth/set-password`) or recover on `/recover` with email plus M-Pesa code (`POST /auth/claim`, 5 misses per email per 15 min). Guests have no Log out button until they set a password.
  - Daraja: `DARAJA_TRANSACTION_TYPE` and `DARAJA_PARTY_B` added. Production here is a TILL (`CustomerBuyGoodsOnline`, store number as shortcode, till as PartyB). `DARAJA_ENV=production` refuses to start without keys, passkey, shortcode and an https callback URL.
  - `reconcile_loop` (started in the app lifespan) settles orders stuck in `processing` through STK query every 60 s, so a missing callback URL does not strand payments. Reconciled orders carry no M-Pesa receipt.
  - Open: callback URL needs a domain. Interim: `<ip-dashes>.sslip.io` as `DOMAIN` and `DARAJA_CALLBACK_URL`. A local `docker/.env.prod` (gitignored) was generated from `.env.production` with DOMAIN and callback URL left as TODO. Prod Daraja OAuth was checked and works; no STK push has been sent. Guest purge for unpaid guest accounts is not built. Guest UI was verified by HTTP only: the browser extension dropped before screenshots at 390x844 and 1440x900 could be taken.
  - Local uncommitted work in the main checkout (resource category migration `c19044b03298`, watermark, spec edits) also parents on `b8791e3cf27f`: rebase its `down_revision` to `4d2f7a91c3be` (or `8b23f849fdc5`) after pulling, or Alembic will have two heads.
- 2026-11-03 (deployed): LIVE at https://getknow.invonicstechnologies.com on the Contabo VPS (167.86.69.120, reach it over Tailscale as the `deploy` user; port 22 is closed publicly). The VPS is shared: one Caddy ("edge", kept in `~/surefire-sites`, one file per domain in `sites/`) owns ports 80 and 443. The storefront runs from `~/course_sale` with `-f docker/docker-compose.prod.yml -f docker/docker-compose.edge.yml`, joins the `edge` network as `getknow-web` and publishes no ports. Compose project name is `course_sale`. See `docs/mpesa-production.md`.
  - A `backup` container writes a DB dump and a storage archive nightly to the `course_sale_backups` volume (14 days). Not yet copied off the server: do that before real customers. Shell scripts are forced to LF by `.gitattributes`.
  - No live STK push has been sent yet. Prod Daraja OAuth works; the callback URL is reachable (wrong secret returns 404).
- Next: register, run `make_admin` on the server, upload a KES 10 test PDF, buy it with a real phone, check the ledger and receipt, unpublish the test. Then copy a backup off the server and decide about memory caps for the storefront containers.

## Verify (see global rule: drive it like a user, mobile 390x844 and desktop 1440x900, screenshots, fix until it works)
- Bring up the dev stack, register, log in, browse, run checkout against a mocked or sandbox Daraja callback, replay the callback (must not credit twice), open the watermarked reader.
- Payments cannot be verified live without real money: say so.

## Caveman mode (always on)
Reply in caveman style: answer first, no filler, all technical facts kept. Follow the `caveman:caveman` skill rules where installed. Stays on until the user says "stop caveman" or "normal mode". Full sentences for security warnings, irreversible actions, questions to the user, and anything written to files, commits, PRs or docs.
