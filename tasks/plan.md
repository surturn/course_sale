# Plan — payment backend (sandbox-ready)

Source spec: docs/superpowers/specs/2026-09-11-invonics-storefront-design.md

- [x] 1. DB foundation: models (users, resources, orders, purchases, orders_paid), Alembic migration, append-only trigger on orders_paid, dev Postgres on host port 5433.
  - Accept: `alembic upgrade head` works; UPDATE/DELETE on orders_paid raises; second terminal row per order rejected.
- [x] 2. Auth: register + login (argon2id, JWT in HttpOnly cookie), `GET /api/v1/auth/me`.
  - Accept: register/login/me round-trip; wrong password 401; duplicate email 409.
- [ ] 3. Checkout: `POST /api/v1/orders` (STK push), `POST /api/v1/payments/callback/{secret}`, `GET /api/v1/orders/{id}`; mock Daraja mode.
  - Accept: success callback creates purchases + confirmed ledger row; duplicate callback is a no-op; failed callback writes failed row; bad secret 404; amount mismatch -> failed.
- [ ] 4. Sandbox E2E: Daraja sandbox client (OAuth, STK push, STK query), ngrok callback, `scripts/e2e_payment.py` demo.
  - Accept: real sandbox STK push reaches phone, callback/query settles order to confirmed.
