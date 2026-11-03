# Invonics Technologies Storefront

A web storefront for selling digital resources (study notes, books and interview PDFs) to students. Buyers pay with M-Pesa and read in the browser. Every copy is watermarked with the buyer's identity, so a leaked PDF can be traced back to the account that bought it.

## Status

Working end to end: accounts, catalog, M-Pesa STK checkout, payment ledger, buyer library, per-buyer watermarked PDF reader, admin uploads (PDFs and cover images) and sales list, production Docker setup. Beside the paid store sit a public free library (`/free`), a tech news feed (`/news`) and a disclaimer gate in front of both, described below. Sized for roughly 200 users on one small VPS, now running on a Contabo VPS. The original design spec is at [`docs/superpowers/specs/2026-09-11-invonics-storefront-design.md`](docs/superpowers/specs/2026-09-11-invonics-storefront-design.md); [`tasks/plan.md`](tasks/plan.md) records where the build deliberately simplified it.

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 (JavaScript), Vite, react-pdf |
| Backend | FastAPI, SQLAlchemy 2.0 async, Alembic, pypdf, Pillow (cover images), defusedxml (news feeds) |
| Database | PostgreSQL 16 |
| Payments | M-Pesa Daraja STK push (Lipa na M-Pesa Online) |
| Files | Local disk volume (PDF originals, cover images, per-buyer watermarked copies) |
| Web server | Caddy (automatic HTTPS, static SPA, `/api` reverse proxy, security headers) |
| Deployment | docker compose on a single VPS (Contabo) |

## How protection works

- **Login required** to buy or read anything.
- **Watermark on every page**, generated per buyer on first open: a footer with name, email, order number and date, a faint diagonal email stamp, and an invisible fingerprint (`INVFP:u<user>-r<resource>-<hmac>`) that survives removal of the visible marks. The original upload is never served.
- **Device cap.** Each account can open purchases on at most `REBIND_LIMIT_PER_MONTH` new devices per rolling 30 days. IP addresses are recorded but not enforced, because Safaricom's mobile network changes them constantly.
- **Reader deterrents.** Right-click, drag, print and save/copy shortcuts are blocked. These stop casual copying only; screenshots can't be prevented in a browser, which is why the watermark carries the real protection.
- **Append-only payment ledger.** Every payment state (`pending`, `processing`, `confirmed`, `failed`) is a new row in `orders_paid`; a database trigger rejects updates and deletes. Duplicate or concurrent M-Pesa callbacks settle an order exactly once.

## Free library, tech news and the disclaimer

Public pages that bring in visitors and point them at the paid catalog. Full details are in [`docs/free-library-news-and-disclaimer.md`](docs/free-library-news-and-disclaimer.md).

- **`/free`** is a hand-picked library of free tools, courses and guides (83 links across coding, money, habits and learning), filtered by a scrollable row of topic chips and a search box. The list is [`backend/app/data/free-resources.json`](backend/app/data/free-resources.json). To add a link, add one entry (`title`, `url`, `kind`, `niche`, `desc`) and redeploy.
- **`/news`** merges recent headlines from ten trusted tech sites (hardware, software, AI, security, African tech). The sources are a fixed list in [`backend/app/api/news.py`](backend/app/api/news.py), fetched on the server and cached for 30 minutes. The server needs outbound HTTPS.
- **Disclaimer gate.** Invonics only aggregates these links and is not the source of the content. Visitors must tick a box before they see either page. The server enforces it: `GET /api/v1/free-resources` and `GET /api/v1/news` return 403 until the visitor has accepted, so blocked scripts or direct API calls get nothing. Each acceptance is stored in `disclaimer_acceptances` (random token, version, account if logged in, IP, browser, time) and remembered for a year in an `HttpOnly` cookie. A logged-in account that accepted is recognised on any device. Bump `VERSION` in `backend/app/api/aggregator.py` to ask everyone again.
- Both pages end with a block showing the first three paid resources, so free visitors can see what else is on sale.

IP addresses and browser strings are personal data. Mention them in your privacy notice and decide how long to keep them.

## Cover images

Every resource shows a cover. Admins can upload one per resource in **Manage** (JPEG, PNG or WebP, up to 5 MB, at least 240 x 320 pixels; design it as a 3:4 portrait, for example 1200 x 1600). The server re-encodes every upload to a clean 600 x 800 WebP, centre-cropped, with metadata removed, so SVGs, scripts and hidden data never reach the disk. Covers of hidden (unpublished) resources are not served. A resource without an uploaded cover gets a generated geometric cover in the brand colours, and the generated one also shows if an uploaded image fails to load. Covers are stored in the `storage` volume next to the PDFs.

## Design

The visual rules (flat tone steps, no decorative effects, contrast and tap-target minimums, motion) are in [`docs/ui-conventions.md`](docs/ui-conventions.md). The design guidance used is from third-party agent skills that are not committed to this repository. To use them in a Claude Code session, install them locally (they land in `.agents/` and `.claude/skills/`, both git-ignored; `skills-lock.json` records the sources):

```bash
npx skills add emilkowalski/skill
```

```bash
npx skills add pbakaus/impeccable
```

```bash
npx skills add Leonxlnx/taste-skill
```

Read a skill before you run any script it ships. Impeccable's launcher downloads a binary, and this project has not run it.

## Run it locally

Needs Docker, Python 3.12 and Node 22.

```bash
docker compose -f docker/docker-compose.dev.yml up -d db
```

```bash
cd backend && python -m venv venv && venv/Scripts/pip install -r requirements.txt
```

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env`: keep `DARAJA_ENV=mock` to start, set `DARAJA_CALLBACK_SECRET` to any long random string. Then migrate and start the API (Postgres listens on host port **5433**):

```bash
cd backend && venv/Scripts/alembic upgrade head
```

```bash
cd backend && venv/Scripts/python -m uvicorn app.main:app --port 8000
```

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:3000, create an account, then make it an admin so you can upload PDFs:

```bash
cd backend && venv/Scripts/python -m scripts.make_admin you@example.com
```

## Test

Backend tests use a separate `invonics_test` database and need `COOKIE_SECURE=false` (the test client talks plain HTTP, so secure cookies are never sent back). Create the database once and migrate it:

```bash
docker exec invonics_db_dev psql -U invonics -d invonics_dev -c "CREATE DATABASE invonics_test"
```

```bash
cd backend && DATABASE_URL=postgresql+asyncpg://invonics:invonics_dev_pass@localhost:5433/invonics_test venv/Scripts/alembic upgrade head
```

```bash
cd backend && COOKIE_SECURE=false venv/Scripts/python -m pytest -q
```

On Linux or macOS, replace `venv/Scripts/` with `venv/bin/`. After pulling new work, re-run the `alembic upgrade head` command against both the dev and test databases so new tables exist.

End-to-end payment demo against the running API (upload, publish, signup, STK push, settlement, library, watermark check):

```bash
cd backend && venv/Scripts/python -m scripts.e2e_payment
```

## M-Pesa sandbox test

1. Create an app at developer.safaricom.co.ke with the **M-Pesa Express** (Lipa na M-Pesa Online) product and copy its consumer key and secret.
2. Expose the API so Safaricom can call back: `ngrok http 8000`.
3. In `backend/.env` set `DARAJA_ENV=sandbox`, `DARAJA_CONSUMER_KEY`, `DARAJA_CONSUMER_SECRET`, `DARAJA_SHORTCODE=174379`, the sandbox `DARAJA_PASSKEY` (shown on the Daraja simulator page), and `DARAJA_CALLBACK_URL` to the ngrok `https://` URL. Restart the API.
4. Run the demo with your Safaricom number and approve the prompt on your phone:

```bash
cd backend && venv/Scripts/python -m scripts.e2e_payment --phone 07XXXXXXXX
```

If the callback can't reach you, the order status endpoint falls back to Daraja's STK query after 45 seconds, so the order still settles.

## Deploy (single VPS, running on Contabo)

1. Point your domain's DNS at the server and open ports 80 and 443.
2. `cp docker/.env.prod.example docker/.env.prod` and fill it in: `DOMAIN`, strong `POSTGRES_PASSWORD`, `SECRET_KEY` and `DARAJA_CALLBACK_SECRET`, your Daraja credentials, and `DARAJA_CALLBACK_URL=https://<your domain>`. The API refuses to start with weak secrets unless `DARAJA_ENV=mock`.
3. Start everything. Caddy fetches the HTTPS certificate on first request; the API runs migrations on start, so new database changes apply by themselves. Use `--build` after every pull, because the API image installs its Python packages (Pillow and defusedxml were added with the free library and covers).

```bash
docker compose -f docker/docker-compose.prod.yml --env-file docker/.env.prod up -d --build
```

4. Register your account on the site, then promote it:

```bash
docker compose -f docker/docker-compose.prod.yml --env-file docker/.env.prod exec api python -m scripts.make_admin you@example.com
```

5. Back up nightly. The database and the `storage` volume (uploaded PDFs and cover images) are the only state; watermarked copies regenerate on demand. Back up both:

```bash
docker compose -f docker/docker-compose.prod.yml --env-file docker/.env.prod exec -T db pg_dump -U invonics invonics | gzip > backup-$(date +%F).sql.gz
```

```bash
docker compose -f docker/docker-compose.prod.yml --env-file docker/.env.prod exec -T api tar czf - -C /app/storage . > storage-$(date +%F).tar.gz
```

Copy both files off the server (another machine or object storage). A backup that lives only on the VPS is lost with the VPS.

Rebuilding with `up -d --build` keeps the `pgdata` and `storage` volumes. Never run `docker compose down -v`: the `-v` deletes them.

After a deploy, open `/news` once: it is the first page that fetches other sites, and the VPS needs outbound HTTPS for it.

Go live by switching `DARAJA_ENV=production` with your production shortcode, passkey and keys once Safaricom approves the app.

## Payments dashboard

The admin page lists every order with its account reference (`INV-<order id>`), amount, status, failure reason and M-Pesa receipt, so app payments stay separate from other business activity on the same till or paybill.

## Repository layout

```
backend/    FastAPI app, Alembic migrations, tests, scripts (make_admin, e2e_payment)
            app/api: auth, orders, resources (+ covers), library, news, aggregator (disclaimer gate)
            app/data: free-resources.json (the free library list)
frontend/   React SPA, Caddyfile and Dockerfile for the web container
docker/     dev compose (Postgres + MinIO), production compose, env example
tasks/      build plan and deliberate simplifications
docs/       design spec, free library / news / disclaimer guide, UI conventions
```
