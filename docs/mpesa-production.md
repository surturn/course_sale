# M-Pesa production setup

Everything the code needs to take live STK push payments. The only thing still open is the public callback URL, which needs a domain (or the interim hostname below).

## Settings (docker/.env.prod, never committed)

| Variable | Production value |
|---|---|
| `DARAJA_ENV` | `production` (the API refuses to start if the keys, passkey, shortcode or an https callback URL are missing) |
| `DARAJA_CONSUMER_KEY`, `DARAJA_CONSUMER_SECRET` | From the Daraja portal, Go Live app |
| `DARAJA_SHORTCODE` | BusinessShortCode: the number the passkey was issued for |
| `DARAJA_PASSKEY` | The Lipa na M-Pesa passkey for that shortcode |
| `DARAJA_TRANSACTION_TYPE` | `CustomerPayBillOnline` for a paybill, `CustomerBuyGoodsOnline` for a till |
| `DARAJA_PARTY_B` | Till number for a till. Empty for a paybill (then it equals the shortcode) |
| `DARAJA_CALLBACK_URL` | Public https base, for example `https://store.example.com` |
| `DARAJA_CALLBACK_SECRET` | 24+ random characters. It becomes part of the callback path, so forged callbacks get a 404 |

A till has two numbers: the store number (BusinessShortCode, owns the passkey) and the till (PartyB, receives the money). Mixing them up makes Daraja reject every push.

## Callback URL before the domain exists

Safaricom only accepts an https callback it can reach. Until the real domain is ready, give Caddy a free hostname that points at the VPS:

1. Find the VPS public IP, for example `203.0.113.7`.
2. Set `DOMAIN=203-0-113-7.sslip.io` and `DARAJA_CALLBACK_URL=https://203-0-113-7.sslip.io` in `docker/.env.prod`. Caddy gets a real Let's Encrypt certificate for it.
3. When the real domain is live, change those two values and run `docker compose ... up -d`. Nothing else changes, because the callback path is built from the base URL at request time.

Open ports 80 and 443 on the VPS firewall (Let's Encrypt needs 80).

## If a callback is lost

The API runs a reconciler every 60 seconds. For any order still `processing` after 45 seconds it asks Daraja for the result (STK query) and settles it, so a payment is not stuck when the callback URL is down, wrong or late. Settlement is idempotent: a callback and a reconcile for the same order produce one ledger row and one purchase. A reconciled order has no M-Pesa receipt on file (the STK query does not return one), so check the receipt in the Daraja portal if a customer disputes.

## Go-live checklist

1. Daraja portal: app is on Go Live, STK push enabled for the shortcode.
2. `docker/.env.prod` filled as above; `DARAJA_ENV=production`.
3. `docker compose -f docker/docker-compose.prod.yml --env-file docker/.env.prod up -d --build`
4. `curl https://<your-host>/api/health` returns `{"ok": true}` over a valid certificate.
5. Create a KES 10 test resource, buy it with your own phone, confirm the prompt arrives, pay, and check the order turns `confirmed` and the PDF opens. Then unpublish the test resource.
6. Replay safety (no money): `POST /api/v1/payments/callback/<secret>` twice with the same body in a staging copy. The ledger must show one `confirmed` row.
7. Watch `docker compose logs -f api` for "Callback for unknown CheckoutRequestID" or "amount mismatch" during the first day.

## Guest checkout and money

Guests pay through the same `_start_order` path as account holders: prices come from the server, duplicate prompts are blocked per buyer, callbacks are idempotent. A guest is a passwordless account, so the library, per-buyer watermark and device cap work unchanged. An email or phone that already has an account is refused with "log in", because signing someone into an existing account from typed details would be account takeover. A guest who loses their session gets back in on `/recover` with their email plus the M-Pesa code from the payment SMS (5 misses per email per 15 minutes, then locked).
