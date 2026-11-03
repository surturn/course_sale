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

## Callback URL and the shared front door

Safaricom only accepts a public https callback it can reach. Production is `https://getknow.invonicstechnologies.com`, so `DOMAIN` and `DARAJA_CALLBACK_URL` in `docker/.env.prod` are both that name. The callback path is built from the base URL at request time, so moving to another domain later means changing those two values only.

The Contabo VPS (167.86.69.120) is shared with other projects, so ports 80 and 443 belong to one shared Caddy ("edge") that holds a certificate per domain and forwards each to its project over a Docker network called `edge`. The storefront does not publish ports. It joins `edge` as `getknow-web` and the shared Caddy forwards the domain to it.

Deploy on the server (the `deploy` user, over Tailscale; port 22 is closed on the public network):

1. Put the code in `~/course_sale` and the settings in `~/course_sale/docker/.env.prod` (`chmod 600`).
2. Start the stack with the edge override:

```bash
cd ~/course_sale
docker compose -f docker/docker-compose.prod.yml -f docker/docker-compose.edge.yml --env-file docker/.env.prod up -d --build
```

3. One-time, tell the shared Caddy about the domain, check the config, then reload (graceful; other projects keep serving):

```bash
cp ~/course_sale/docker/edge/getknow.caddy.example ~/lucklotter/deploy/edge/sites/getknow.caddy
docker exec edge-caddy-1 caddy validate --config /etc/caddy/Caddyfile
docker exec edge-caddy-1 caddy reload --config /etc/caddy/Caddyfile
```

To undo: delete `getknow.caddy` and reload. The domain's A record must already point at the server or the certificate cannot be issued. The inner Caddy trusts the front door's address (`trusted_proxies`), so the API sees real client IPs and the login and signup throttles stay per visitor.

On a server that is only for this project, skip `docker-compose.edge.yml`: `docker-compose.prod.yml` then serves HTTPS itself on 80 and 443.

## If a callback is lost

The API runs a reconciler every 60 seconds. For any order still `processing` after 45 seconds it asks Daraja for the result (STK query) and settles it, so a payment is not stuck when the callback URL is down, wrong or late. Settlement is idempotent: a callback and a reconcile for the same order produce one ledger row and one purchase. A reconciled order has no M-Pesa receipt on file (the STK query does not return one), so check the receipt in the Daraja portal if a customer disputes.

## Go-live checklist

1. Daraja portal: app is on Go Live, STK push enabled for the shortcode.
2. `docker/.env.prod` filled as above; `DARAJA_ENV=production`.
3. Start the stack (see the section above, edge override on the shared VPS).
4. `curl https://getknow.invonicstechnologies.com/api/health` returns `{"ok": true}` over a valid certificate.
5. Create a KES 10 test resource, buy it with your own phone, confirm the prompt arrives, pay, and check the order turns `confirmed` and the PDF opens. Then unpublish the test resource.
6. Replay safety (no money): `POST /api/v1/payments/callback/<secret>` twice with the same body in a staging copy. The ledger must show one `confirmed` row.
7. Watch `docker compose logs -f api` for "Callback for unknown CheckoutRequestID" or "amount mismatch" during the first day.

## Guest checkout and money

Guests pay through the same `_start_order` path as account holders: prices come from the server, duplicate prompts are blocked per buyer, callbacks are idempotent. A guest is a passwordless account, so the library, per-buyer watermark and device cap work unchanged. An email or phone that already has an account is refused with "log in", because signing someone into an existing account from typed details would be account takeover. A guest who loses their session gets back in on `/recover` with their email plus the M-Pesa code from the payment SMS (5 misses per email per 15 minutes, then locked).

## Backups

The `backup` container dumps the database and archives the storage volume every night and keeps 14 days (`BACKUP_KEEP_DAYS`). Restore steps and how to copy backups off the server are in the README, step 5. Payments live in the `orders_paid` ledger, so the dump is also your payment record: copy it off the server before real customers arrive.
