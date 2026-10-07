# Plan — payment backend (sandbox-ready)

Source spec: docs/superpowers/specs/2026-09-11-invonics-storefront-design.md

- [x] 1. DB foundation: models (users, resources, orders, purchases, orders_paid), Alembic migration, append-only trigger on orders_paid, dev Postgres on host port 5433.
  - Accept: `alembic upgrade head` works; UPDATE/DELETE on orders_paid raises; second terminal row per order rejected.
- [x] 2. Auth: register + login (argon2id, JWT in HttpOnly cookie), `GET /api/v1/auth/me`.
  - Accept: register/login/me round-trip; wrong password 401; duplicate email 409.
- [x] 3. Checkout: `POST /api/v1/orders` (STK push), `POST /api/v1/payments/callback/{secret}`, `GET /api/v1/orders/{id}`; mock Daraja mode.
  - Accept: success callback creates purchases + confirmed ledger row; duplicate callback is a no-op; failed callback writes failed row; bad secret 404; amount mismatch -> failed.
- [ ] 4. Sandbox E2E: Daraja sandbox client (OAuth, STK push, STK query), ngrok callback, `scripts/e2e_payment.py` demo.
  - Accept: real sandbox STK push reaches phone, callback/query settles order to confirmed.
- [ ] 5. Catalog + admin: public `GET /api/v1/resources`, admin upload PDF (local disk storage), publish/unpublish, `scripts/make_admin.py`.
  - Accept: non-admin 403; only published resources listed; upload stores file + sha256 + page_count.
- [ ] 6. Library + protected delivery: `GET /api/v1/library`, `GET /api/v1/resources/{id}/file` serves a per-buyer watermarked PDF (visible + invisible fingerprint) with Range support; device binding with monthly new-device quota.
  - Accept: non-owner 403; original never served; Range returns 206; device over quota 403.
- [ ] 7. Frontend: catalog, register/login, checkout with STK polling, library, protected viewer, minimal admin page.
  - Accept: `npm run build` passes; full purchase flow works in browser against mock Daraja.
- [ ] 8. Deploy: backend Dockerfile, nginx serving SPA + proxying /api (rate limits, CSP), `docker-compose.prod.yml`, README runbook.
  - Accept: `docker compose -f docker/docker-compose.prod.yml up` serves the app end to end.

Scale target: ~200 users on one VPS. Deliberately skipped until needed: MinIO/CDN (local disk + Range is enough), background queue (watermark generated on first open), OTP re-bind (device quota instead), RLS (ownership checks in queries).
