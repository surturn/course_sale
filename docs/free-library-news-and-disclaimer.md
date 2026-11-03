# Free library, tech news and the disclaimer gate

These three features sit beside the paid storefront. They bring in visitors who are not ready to buy yet and point them at the paid catalog. None of them touch payments or login code.

## What visitors see

| Page | What it is |
|---|---|
| `/free` | A hand-picked library of free tools, courses, guides and apps for coding, money, habits and learning. One list, filtered by a scrollable row of topic chips and a search box. |
| `/news` | Headlines from trusted tech sites on hardware, software, AI, security and African tech, filtered by topic chips. Every link opens the original story. |

Both pages open with a disclaimer that the visitor must accept, and both end with a block that shows the first three paid resources (with cover art and price) and a "Browse all resources" button.

## The disclaimer gate

Invonics only aggregates links and headlines. It is not the source of that content and is not responsible for it. To make that explicit, `/free` and `/news` are gated on the server.

**Flow**

1. The page asks `GET /api/v1/disclaimer`. If the visitor has not accepted the current version, it shows a modal instead of the content. The modal cannot be dismissed with Esc or by clicking outside, and its Continue button stays disabled until the tick box is checked.
2. Ticking and continuing calls `POST /api/v1/disclaimer/accept` with `{"agreed": true}`. The server stores the acceptance and sets the `aggregator_ok` cookie.
3. Only then does the page request its data. `GET /api/v1/free-resources` and `GET /api/v1/news` return `403` to anyone who has not accepted, so blocking scripts or calling the API directly gets nothing. The link list is not in the JavaScript bundle.
4. If the check fails (offline, server error) the page stays closed and offers "Try again". With scripts blocked, the site shows a notice that JavaScript is required.
5. A "Read the disclaimer" link under each page intro reopens the text as a plain notice.

**What is stored** (table `disclaimer_acceptances`, migration `2720f272fa5d`)

| Column | Meaning |
|---|---|
| `token` | Random value, also held in the visitor's cookie. Unique. |
| `version` | Which wording was accepted (`VERSION` in `backend/app/api/aggregator.py`). |
| `user_id` | The account, if the visitor was logged in. Cleared (set null) if the user is deleted. |
| `ip`, `user_agent` | Network address and browser string at the time. |
| `accepted_at` | When. |

Rows are never edited. An anonymous row proves that someone with that IP and browser ticked the box at that time. It does not identify the person.

**Cookie.** `aggregator_ok` holds the random token. It is `HttpOnly`, `SameSite=Lax`, `Secure` in production, and lasts one year. The server looks the token up on every gated request, so a made-up value gets nothing.

**Accounts.** A logged-in account that accepted once is recognised on any device, even without the cookie.

**Re-asking everyone.** Change the wording, then bump `VERSION` (for example `"v2"`). Old acceptances stop counting and everyone is asked again. Old rows stay as proof of what was accepted earlier.

**Abuse limit.** One IP can create at most 20 acceptances per hour (`ACCEPT_LIMIT`, in-process like the login limiter).

**Privacy.** IP addresses and browser strings are personal data. Mention them in your privacy notice and decide how long to keep the rows. There is no automatic cleanup yet.

## The free library

The list lives in [`backend/app/data/free-resources.json`](../backend/app/data/free-resources.json) and is served by `GET /api/v1/free-resources` (gated). To add a link, add one entry and redeploy:

```json
{ "title": "Khan Academy", "url": "https://www.khanacademy.org", "kind": "course", "niche": "Learn to code", "desc": "Free lessons in maths, science, computing and more." }
```

| Field | Rules |
|---|---|
| `kind` | One of `repo`, `site`, `tool`, `course`. Shown as a badge. |
| `niche` | The topic chip. A new niche name creates a new chip automatically. |
| `desc` | One plain sentence. Say what it is and who it is for. |

Current niches: AI & LLMs, System design & DevOps, Learn to code, Careers, Everyday tools, Design & creative, Money & finance, Habits & wellbeing, Learn anything.

Before adding a link, open it and check it is live and really free, or say in `desc` what is paid. GitHub entries were checked against GitHub when they were added. The non-GitHub sites were not link-checked, so click through them periodically.

Money and health entries link to official or well-known sources. Keep it that way, and keep the disclaimer in front of them.

## Tech news

`GET /api/v1/news?niche=hardware|software|ai|security|africa` (gated) returns a merged list of recent headlines.

- The sources are a fixed list in [`backend/app/api/news.py`](../backend/app/api/news.py) (`FEEDS`): Ars Technica Gadgets, Tom's Hardware, Hacker News, InfoQ, GitHub Blog, Hugging Face Blog, MIT Technology Review AI, BleepingComputer, Krebs on Security and TechCabal. Feed addresses are hardcoded and never taken from the client, so the endpoint cannot be pointed at other servers.
- Feeds are fetched on the server, parsed with `defusedxml` (safe against malicious XML), and cached in memory for 30 minutes. At most 10 items per feed, 100 overall, newest first, nothing older than 30 days. Only `http` and `https` links are kept.
- A feed that fails is skipped. If every feed fails, the last good copy is served, so the page does not go blank.
- The cache is per worker process. Two workers means two caches and slightly different results for a few minutes. That is fine at this scale.

To add or remove a source, edit `FEEDS` (name, feed URL, niche). The server needs outbound HTTPS access to the sites. The Contabo VPS has it. A locked-down or sandboxed host will show an empty news page.

## Paid-catalog block

`StoreCta` (`frontend/src/components/StoreCta.jsx`) reads the public catalog and shows the first three resources with cover art and price. It fails silently, so a catalog error never breaks the free pages.

## API summary

| Method and path | Access | Purpose |
|---|---|---|
| `GET /api/v1/disclaimer` | public | `{"accepted": true/false}` for this browser or account. |
| `POST /api/v1/disclaimer/accept` | public, 20 per IP per hour | Store the acceptance and set the cookie. Body must be `{"agreed": true}`. |
| `GET /api/v1/free-resources` | accepted | The free library list. |
| `GET /api/v1/news` | accepted | Headlines, optional `?niche=`. |

## Tests

`backend/tests/test_aggregator.py` covers the gate: blocked until accepted, the box must be ticked, the stored row, no duplicate rows, forged tokens, a version bump, an account recognised on a new device, and the rate limit. `backend/tests/test_news.py` covers feed parsing (RSS and Atom), unsafe links, old items, an XML entity bomb, merging, filtering, caching and the stale fallback.
