# Plan — payment backend (sandbox-ready)

Source spec: docs/superpowers/specs/2026-09-11-invonics-storefront-design.md

- [x] 1. DB foundation: models (users, resources, orders, purchases, orders_paid), Alembic migration, append-only trigger on orders_paid, dev Postgres on host port 5433.
  - Accept: `alembic upgrade head` works; UPDATE/DELETE on orders_paid raises; second terminal row per order rejected.
- [x] 2. Auth: register + login (argon2id, JWT in HttpOnly cookie), `GET /api/v1/auth/me`.
  - Accept: register/login/me round-trip; wrong password 401; duplicate email 409.
- [x] 3. Checkout: `POST /api/v1/orders` (STK push), `POST /api/v1/payments/callback/{secret}`, `GET /api/v1/orders/{id}`; mock Daraja mode.
  - Accept: success callback creates purchases + confirmed ledger row; duplicate callback is a no-op; failed callback writes failed row; bad secret 404; amount mismatch -> failed.
- [ ] 4. Sandbox E2E: Daraja sandbox client (OAuth, STK push, STK query), ngrok callback, `scripts/e2e_payment.py` demo. (Code + mock run done; real sandbox run blocked on Daraja consumer key/secret.)
  - Accept: real sandbox STK push reaches phone, callback/query settles order to confirmed.
- [x] 5. Catalog + admin: public `GET /api/v1/resources`, admin upload PDF (local disk storage), publish/unpublish, `scripts/make_admin.py`.
  - Accept: non-admin 403; only published resources listed; upload stores file + sha256 + page_count.
- [x] 6. Library + protected delivery: `GET /api/v1/library`, `GET /api/v1/resources/{id}/file` serves a per-buyer watermarked PDF (visible + invisible fingerprint) with Range support; device binding with monthly new-device quota.
  - Accept: non-owner 403; original never served; Range returns 206; device over quota 403.
- [x] 7. Frontend: catalog, register/login, checkout with STK polling, library, protected viewer, minimal admin page.
  - Accept: `npm run build` passes; full purchase flow works in browser against mock Daraja.
- [x] 8. Deploy: backend Dockerfile, nginx serving SPA + proxying /api (rate limits, CSP), `docker-compose.prod.yml`, README runbook.
  - Accept: `docker compose -f docker/docker-compose.prod.yml up` serves the app end to end.
- [x] 9. Free library: public `/free` page (search plus topic chips) and `GET /api/v1/free-resources`, data in `backend/app/data/free-resources.json`.
  - Accept: 83 links across 9 topics; adding a JSON entry shows it after redeploy.
- [x] 10. Tech news: `GET /api/v1/news` merges 10 fixed RSS/Atom feeds, 30 min cache, stale copy if all feeds fail; `/news` page with topic chips.
  - Accept: unit tests with fake feeds pass (RSS, Atom, unsafe links, old items, XML entity bomb, caching, fallback). Live fetch needs outbound HTTPS, check `/news` after each deploy.
- [x] 11. Disclaimer gate: `/free` and `/news` data refused (403) until the visitor ticks the box; acceptance stored in `disclaimer_acceptances` (migration `2720f272fa5d`), 1-year HttpOnly cookie, accounts recognised across devices, `VERSION` to re-ask, 20 accepts per IP per hour.
  - Accept: tests cover blocked, unticked, stored row, forged token, version bump, new device, rate limit.
- [x] 12. Covers: generated geometric cover per title, and admin-uploaded covers (`POST/DELETE /api/v1/admin/resources/{id}/cover`, migration `8b23f849fdc5`), re-encoded to 600x800 WebP.
  - Accept: bad types, oversize, tiny images rejected; admin only; hidden resources not served; remove falls back to generated.
- [x] 13. Design pass: flat tone-stepped UI, scrollable chip rows, 44px tap targets, contrast at least 4.5:1 (see `docs/ui-conventions.md`).
  - Accept: checked in light and dark at 390x844 and 1440x900. The reader and admin pages were not redesigned.
- [ ] 14. Follow-ups: retention policy for disclaimer rows (IP and browser strings); link-check the non-GitHub free-library sites; redesign and re-check the reader and admin pages; Kenyan business news feeds if working feed addresses are found.

Scale target: ~200 users on one VPS. Deliberately skipped until needed: MinIO/CDN (local disk + Range is enough), background queue (watermark generated on first open), OTP re-bind (device quota instead), RLS (ownership checks in queries), refresh tokens (single 12h session cookie), Nginx (Caddy for automatic HTTPS; login/signup throttling in-app), a shared cache for news (per-worker in-memory cache is enough), a job queue for feed refresh (refreshed on request).
