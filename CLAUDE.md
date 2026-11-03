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
- 2026-11-03: added public `/free` Free library page (search plus niche filter). Links live in `frontend/src/data/free-resources.json`; add a link by adding one entry. Frontend only, no payment or auth changes.
- 2026-11-03 (later): added money/wellbeing/everyday-learning entries to the free library, a `/news` tech feed (backend `GET /api/v1/news`: fixed RSS list in `backend/app/api/news.py`, 30 min cache, stale-on-failure), and a paid-catalog block (`StoreCta`) under both free pages. Feed URLs are hardcoded, never from the client. Live feed fetch is untested from the sandbox (outbound blocked); unit tests use fake feeds.
- 2026-11-03 (gate): `/free` and `/news` are server-gated. `GET /api/v1/free-resources` and `/api/v1/news` return 403 until the visitor ticks the disclaimer (`POST /api/v1/disclaimer/accept`, 1-year HttpOnly cookie `aggregator_ok`, bump `VERSION` in `backend/app/api/aggregator.py` to re-ask). Link data lives in `backend/app/data/free-resources.json`. UI skills from `emilkowalski/skill` installed under `.agents/skills`.
- 2026-11-03 (acceptance + design): disclaimer acceptance is stored in `disclaimer_acceptances` (token, version, user_id if logged in, IP, user agent, time; migration `2720f272fa5d`); cookie holds the random token, 20 accepts/IP/hour. A logged-in account that accepted is recognised on any device. UI restyled in the "Design pass" block at the end of `frontend/src/styles.css` (apple-design skill: hairlines, grouped lists, translucent header and sheet). Backend tests need `COOKIE_SECURE=false` and the dev Postgres.
- 2026-11-03 (design v2): applied `impeccable` (read-only: its launcher downloads a remote binary, so it was NOT run) and `design-taste-frontend` rules to the new pages. House rules now: tone steps instead of lines, no glass or gradients (except the brand highlighter on h1), shadow only on the disclaimer dialog, round buttons/chips/search, secondary text >= 4.5:1, tap targets >= 44px, headlines <= 2 lines on the free and news pages. Reader and admin pages were not restyled or re-checked.
- 2026-11-03 (chips): topic filters on /free and /news are one scrollable `ChipRow` (swipe on touch, arrow buttons for mouse); the per-topic headings in the free list were removed. A grid parent needs `minmax(0, 1fr)` or the row grows to content width and the page scrolls sideways.
- Next: not recorded. Check `tasks/`.

## Verify (see global rule: drive it like a user, mobile 390x844 and desktop 1440x900, screenshots, fix until it works)
- Bring up the dev stack, register, log in, browse, run checkout against a mocked or sandbox Daraja callback, replay the callback (must not credit twice), open the watermarked reader.
- Payments cannot be verified live without real money: say so.

## Caveman mode (always on)
Reply in caveman style: answer first, no filler, all technical facts kept. Follow the `caveman:caveman` skill rules where installed. Stays on until the user says "stop caveman" or "normal mode". Full sentences for security warnings, irreversible actions, questions to the user, and anything written to files, commits, PRs or docs.
