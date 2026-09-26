# Gabstep — Visa Application Platform

International student admissions and visa support: applicants apply to partner
institutions and track their file, and partner agents recruit students, earn
commission and draw it down.

The product is two deployables that talk over a JSON API.

```
VISA APPLICATION/
├── backend/        Django 5 + Django REST Framework API
├── frontend/       React 19 + Vite single-page app
└── docs/           Reference material
```

---

## Running it locally

You need **Python 3.11+** and **Node 20+**. Two terminals.

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate          # macOS or Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # the defaults work for local development

python manage.py migrate
python manage.py seed_catalog   # countries, partner schools, courses, FAQs
python manage.py ensure_admin --email you@example.com
python manage.py runserver      # http://127.0.0.1:8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

The Vite dev server proxies `/api` and `/media` to Django on port 8000, so the
browser sees a single origin and nothing depends on CORS while developing.

### Accounts

There is no demo seeder. `seed_demo` created an applicant, an agent and a set of
invented applications with passwords written into the source, which is a set of
live credentials on any deployment that ever ran it. It has been deleted.

Every account is made the way a real one is:

| Role | How it is created |
| --- | --- |
| Admissions desk | `manage.py ensure_admin --email you@example.com` |
| Applicant | signs themselves up through the application wizard |
| Agent | signs themselves up at `/agent/register` |
| Sales Manager | **Partners & sales → Sales managers** in the admin, which is also the only thing that generates the `GSA-` code |

`ensure_admin` is the non-interactive equivalent of `createsuperuser`: it takes
`--email`, `--password` and `--name`, or reads `DJANGO_ADMIN_EMAIL`,
`DJANGO_ADMIN_PASSWORD` and `DJANGO_ADMIN_NAME`. **There is no default
password.** Supply one, or the command generates a 20-character one and prints it
once — it is not stored in readable form and cannot be recovered, so run the
command again to set a new one.

A student an agent registers gets an account with **no usable password**. They
are never emailed and never sign in: the agent collected their documents and pays
their fee, so every letter and status update goes to the agent.

---

## How the product works

**Applicants** fill in a five-step wizard: personal details, academic
background, institution and courses, documents, payment. An account is created
for them at the moment they pay, and the generated password is shown once. From
then on the portal carries their stage track, documents, contact details and
correction requests.

**Partner agents** register their agency and file the same application on behalf
of students. Each student also gets their own portal login, handed back to the
agent once. Agents browse every course on the platform from **Courses**, and the
overview carries a live currency converter, since they earn in Naira and quote
tuition in the destination's currency.

An agent earns **₦30,000 the moment a student's application fee is paid** and
**₦30,000 again once the admissions desk verifies the visa**. Nothing is credited
on an unpaid file, so the balance only ever reflects money the business has
actually received — a student registered without settling the fee shows as *Fee
outstanding* on the Students table with a **Pay fee** button, and the commission
lands the instant it clears. A fee-free partner institution charges nothing, so
it earns no registration commission; the visa half is unaffected.

Agents withdraw the balance to a registered bank account and can borrow
interest-free capital for recruitment advertising. While a loan is outstanding,
a tenth of every withdrawal repays it. Agent withdrawals start at ₦100,000;
Sales Manager withdrawals also start at **₦100,000**, and are paid in full since
there is no loan to settle against them.

**Sales Managers** are created by the admissions desk, never self-registered.
Saving one generates an **agent code** of the form `GSA-XXXXXX`; agents enter
that code on the sign-up form, and from then on the Sales Manager sees those
agents, every student they register, and their own earnings. A Sales Manager
earns **₦2,000 each time one of their agents registers a student**, credited the
moment the registration is filed. They oversee rather than operate: their portal
is read-only, with no approvals and no payout requests.

The code that identifies an agent's own account is `AGT-00001`; the code that
joins an agent to a Sales Manager is `GSA-XXXXXX`. Two different things, two
different prefixes.

| Who | Earns | When |
| --- | --- | --- |
| Agent | ₦30,000 | The student's application fee is paid |
| Agent | ₦30,000 | The desk verifies that student's visa |
| Sales Manager | ₦2,000 | Their agent registers a student |

Withdrawals start at **₦100,000**. The floor is `MIN_WITHDRAWAL_NGN` in
`backend/apps/applications/constants.py`, and the wallet endpoint publishes it as
`minimum_withdrawal` so the portal enforces exactly what the API enforces rather
than keeping its own copy of the number.

Two rules run through the whole product:

- **The application fee is charged once per institution, never per course.** An
  applicant may choose up to two courses at their chosen school for one fee, and
  a fee-free partner institution waives it entirely.
- **The fee is always ₦200,000, shown in the applicant's own currency.** The
  country of origin decides the display currency, and the Naira figure is kept
  alongside the converted one so any drift in the rate stays visible.

The catalogue ships with **France and Spain**: seven partner schools and 142
courses. Everything else is added by staff from the admin.

> The exchange rates in `backend/apps/catalog/data/catalog.json` are indicative
> reference values used to price the application fee. Wire
> `OriginCountry.ngn_per_unit` to a live source before taking real money.
>
> The converter is separate and genuinely live: `apps/catalog/fx.py` fetches
> from a public provider, caches for five minutes, and falls back to the stored
> table if the provider cannot be reached — labelling the figures as indicative
> when it does, rather than passing stale numbers off as live.

---

## The admissions desk (Django admin)

`/admin/` is where staff work the pipeline. Selecting rows on a changelist and
choosing an action from the dropdown handles a batch at once; everything that
changes what the applicant can see also writes them a notification.

**Applications** — the main screen.

| Action                        | What it does                                                                  |
| ----------------------------- | ----------------------------------------------------------------------------- |
| Verify documents              | Marks every document verified and moves the file to institution review         |
| Grant admission               | Advances the stage track. Pays nothing — the fee already did                   |
| Confirm visa verified         | Closes the track and pays the agent their second ₦30,000                       |
| Decline application           | Stops the track and tells the applicant                                        |

Opening one application gives the stage track inline, so a stage can be set to
*In progress* by hand when a file does not follow the usual path — the ring on
the applicant's dashboard follows whatever the stages say.

**Issuing a letter.** Add a Letter on the application (or from *Letters* for a
batch), attach the PDF and leave *Published* ticked. It appears on the
applicant's Letters page immediately and they are notified. Untick it to stage a
letter for checking first; nothing is shown until it is published.

**Documents** — approve or reject what applicants upload. A rejection tells them
to send a clearer copy, which they do from Details in their portal.

**Corrections** — approving one writes the change straight to the file where it
is a plain value, such as a legal name, and keeps the applicant's account name
in step. A correction to an institution or a course is marked verified and left
for a person, because it changes a relation and triggers a re-review.

**Partners & sales → Ad funding requests** — approve and disburse in one step; the agent's
loan balance goes up and repayment is then taken at 10% of each withdrawal.

**Partners & sales → Agent payouts / Sales manager payouts** — mark a payout as
sent once it has actually left the account, or as failed, which returns the
money to the balance it came from.

The index is ordered by the work rather than alphabetically: Applications, then
Partners & sales, Payments, Add course, and Accounts last. Screens that
only ever duplicated something shown inline — wallets, commissions, bonuses,
notifications, saved wizard drafts — were removed, as was Django's unused Groups
page.

**Partners & sales → Sales managers** — create a Sales Manager account. Fill in their
name, email and password on one screen; saving creates the sign-in and generates
the `GSA-` agent code to hand them. The change page lists the agents who used
that code and every bonus earned.

**Payments** — *Confirm payment received* settles a transfer that arrived off
platform, and credits the agent's registration commission exactly as paying
through checkout does.

**Add course** — the whole catalogue on one screen. Paste a school's course
list, straight from a spreadsheet, a PDF table or one course per line. The
parser works out which column is the course, the duration, the accreditation,
the tuition and the intake, and reads a country, school or city named on its own
line. What it made of the paste comes back as a table where every row can be
corrected and any row can be left out; set the application fee, press save, and
the country, the school and every course are written in one pass. Nothing
reaches the database until that table has been confirmed.

Courses, schools and countries keep their own screens for the edits that come
after — fixing a tuition figure, reordering, hiding a school — but they are not
listed on the index. Add course links to them at the foot of the page, along
with the FAQ and the exchange rates. A saved change reaches the public site and
the agent course browser within seconds.

Every portal refetches on a timer and whenever its tab is brought back to the
front, so an approval, a stage change or a new course appears without anyone
reloading: the applicant portal every 15 seconds, the agent and Sales Manager
portals every 20. It is polling rather than a socket, because the data changes a
few times a day and a websocket stack would be a lot of moving parts for a delay
nobody would notice.

> Approvals belong to the desk, not to the agent. The partner portal submits
> requests and reports their state; it has no self-approval controls.

---

## Email

SMTP is configured in `backend/.env`. Nothing is hardcoded: the password is read
from the environment only, so a missing value fails loudly rather than falling
back to a credential in source.

```
EMAIL_HOST=mail.gabstep.com      EMAIL_PORT=465      EMAIL_USE_SSL=True
EMAIL_HOST_USER=support@gabstep.com
DEFAULT_FROM_EMAIL=Gabstep <support@gabstep.com>
FRONTEND_URL=http://localhost:5173
```

**Set `FRONTEND_URL` to the live site before sending to real recipients.** Every
button in an email is built from it. Django now refuses to start with
`DJANGO_DEBUG=False` and a localhost value, because the mail would still send and
the recipient would get a button that only works on the machine that sent it
(`apps/accounts/checks.py`).

Ten messages are sent, all from `apps/accounts/emails.py`:

| Message | Fires when | Goes to |
| --- | --- | --- |
| Your Gabstep account | An applicant signs themselves up | The applicant |
| Your partner account | An agent registers | The agent |
| Your sales manager account | The desk creates one, with the `GSA-` code | The Sales Manager |
| Application update | Any notification is written on a file | The applicant, or the agent if they filed it |
| Ad funding approved | The desk approves and disburses | The agent |
| Ad funding declined | The desk declines | The agent |
| Payout sent | A withdrawal is marked paid | The agent |
| Payout failed | A withdrawal fails and the balance returns | The agent |
| Payout sent | A Sales Manager withdrawal is marked paid | The Sales Manager |
| Payout failed | A Sales Manager withdrawal fails | The Sales Manager |

The application update is driven by a `post_save` signal on `Notification`, so
every stage change, document decision, correction and letter mails out without
each of those having to remember to send one. Notifications written during
submission set `send_email=False`: a sign-up writes half a dozen of them within a
few seconds, and mailing each one would mean six messages for one action.

A student registered by an agent is never emailed at all, and no password is
issued for their account. The agent collected the documents and pays the fee, so
every update on that file goes to the agent instead.

Sending happens on a daemon thread so the HTTP response is not held up by SMTP,
and a failure is logged rather than raised: an applicant's account is still
created if the mail server is briefly unreachable.

---

## Backend

Django project in `backend/`, split into five apps under `backend/apps/`:

| App            | What it owns                                                      |
| -------------- | ----------------------------------------------------------------- |
| `accounts`     | One user model for applicants, agents and staff, keyed on email    |
| `catalog`      | Origin and destination countries, institutions, programmes, FAQs   |
| `applications` | The application, its stages, documents, letters, corrections       |
| `partners`     | Agents and Sales Managers: wallets, commissions, loans, payouts    |
| `payments`     | The application fee: quote, checkout, receipt                      |

Authentication is JWT (`djangorestframework-simplejwt`). The access token lasts
an hour and refreshes silently; the frontend retries a 401 once with a refreshed
token before giving up.

Browsable API documentation is served at `/api/docs/` while `DJANGO_DEBUG` is on.

### Key endpoints

```
POST   /api/auth/login/                         Sign in, returns tokens and the user
POST   /api/auth/register/applicant/            Create an applicant account
POST   /api/auth/register/agent/                Create an agency, profile and wallet
GET    /api/catalog/institutions/?country=Spain Partner institutions and courses
GET    /api/catalog/fee-quote/?origin=Ghana     The fee in the applicant's currency
GET    /api/catalog/programs/?search=MBA        Every course, searchable and filterable
GET    /api/catalog/exchange-rates/?base=NGN    Live rates for the converter
POST   /api/applications/                       Submit the whole wizard in one call
GET    /api/applications/mine/                  The signed-in applicant's file
POST   /api/payments/checkout/                  Settle the fee
GET    /api/partners/overview/                  Everything the agent overview needs
GET    /api/supervisors/overview/               Everything the Sales Manager overview needs
GET    /api/supervisors/agents/                 The agents who used this manager's code
GET    /api/supervisors/students/               Students filed by any of those agents
POST   /api/partners/students/                  File an application for a student
POST   /api/partners/withdrawals/               Request a payout (the desk approves it)
```

### Payments

**A payment is only settled by something that can prove money moved.** The
checkout endpoint used to call `mark_paid` itself, which meant anyone who could
reach it had the fee marked paid and, on an agent-filed application, the
₦30,000 registration commission credited, with no money arriving anywhere.

`POST /api/payments/checkout/` now records a **pending** payment and nothing
else. Settlement has exactly two doors:

| Door | What proves it | Credits the agent |
| --- | --- | --- |
| `POST /api/payments/webhook/paystack/` | HMAC-SHA512 signature over the raw body, checked in constant time, plus the amount matching the quote | yes |
| **Payments → Confirm payment received** in the admin | a human seeing the transfer land | yes |

A fee-free institution is still waived on the spot, because there is nothing to
collect and a waiver earns no commission either way.

With `PAYSTACK_SECRET_KEY` set, checkout returns an `authorization_url` and the
applicant is handed to the provider — card details are entered on the provider's
page and never reach this project. With no key, the platform runs in **transfer
mode**: the fee is recorded as outstanding, the account from
`PAYOUT_BANK_NAME` / `PAYOUT_BANK_ACCOUNT` / `PAYOUT_BANK_BENEFICIARY` is shown,
and the desk confirms receipt. Both are real ways to take money; neither is a
simulation.

The webhook replays safely: a second delivery for a payment already settled is
ignored, so a retrying provider cannot pay the commission twice.

### Setting up Paystack

Set two variables and point one webhook. Nothing else.

| Variable | Value |
| --- | --- |
| `PAYSTACK_SECRET_KEY` | your `sk_live_…` (or `sk_test_…`) key |
| `PAYSTACK_PUBLIC_KEY` | your `pk_live_…` key |

The same variable holds a test or a live key; Paystack decides which environment
that is from the key itself, so there is no mode flag here to fall out of step
with it.

Then, in the Paystack dashboard under **Settings → API Keys & Webhooks**, set the
webhook URL to:

```
https://YOUR-DOMAIN/api/payments/webhook/paystack/
```

That endpoint is unauthenticated by necessity — Paystack holds no account here —
so the signature is the authentication. It checks, in order: the optional IP
allowlist, an HMAC-SHA512 signature over the **raw** request body compared in
constant time, that the event is `charge.success`, that the transaction status is
`success`, that the currency is NGN, and that the amount collected covers the
quote. Anything that fails is logged and ignored, and the endpoint always answers
`200` so a sender is never told whether it guessed right.

**The webhook is not the only path.** It can be late, retried, or lost behind a
deploy, and the applicant is standing there now. So when they come back from
Paystack they land on `/payment/<reference>`, which calls
`GET /api/payments/status/<reference>/`; that verifies the transaction
server-to-server against Paystack and settles it if the money is in. Both routes
call the same `settle()` in `apps/payments/settlement.py`, which takes the row
lock and re-reads the status inside it, so whichever arrives first does the work
and the other is a no-op. A commission cannot be paid twice.

A retried payment gets a fresh gateway reference (`GBS-…-A2`), because Paystack
refuses a reference it has already seen. Without that, an applicant who abandoned
their first attempt could never pay at all.

#### The fee the applicant pays

Paystack's own charge is computed in Naira from their published pricing — 1.5%
plus ₦100, the flat part waived under ₦2,500, capped at ₦2,000 — added to the
application fee, and only then converted for display. On a ₦200,000 fee that is
₦2,000, so the card is debited **₦202,000**.

This matters because the old code added a flat `3.50` in the applicant's own
currency to the total on screen and then asked the gateway for the application fee
alone. Nobody was ever charged that 3.50, so every receipt was wrong by it and
nothing would have reconciled against a settlement report. All four numbers are
env-overridable if you have a negotiated rate.

#### Deploying on Render

- Set every variable from `.env.example` in the Render service's environment. It
  reads them directly; there is no `.env` file on the server.
- `RENDER_EXTERNAL_HOSTNAME` is set by Render and added to `ALLOWED_HOSTS`
  automatically, so a first deploy answers instead of returning `DisallowedHost`.
- Leave `PAYSTACK_WEBHOOK_IPS` **empty**. Render terminates TLS in front of the
  app and does not pass Paystack's original address through, so an allowlist
  there would reject every genuine webhook.
- `SECURE_PROXY_SSL_HEADER` is already set for `X-Forwarded-Proto`, which is what
  Render sends.
- Serve the built frontend from the same hostname, with the API under `/api`. The
  refresh-token cookie is same-origin: split them and everyone is logged out on
  every reload.

### Sessions

The access token lives in **memory** in the browser and the refresh token in an
**httpOnly cookie** scoped to `/api/auth/`. Neither is in `localStorage`, which
any script on the page can read: one injected script used to be enough to walk
off with a refresh token good for a week from anywhere.

The consequence to plan for: **the API and the site must be same-origin**, or the
browser will not send the cookie. The Vite dev server proxies `/api` and
`/media`, and a deployment should put both behind one hostname.

### Rate limits

Nothing was limited before, which made the sign-in endpoint a free password
oracle and `email-available/` a free way to list every account. The scopes are in
`REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]` and each is overridable from the
environment: `login` 8/min, `register` 5/hour, `email_check` 20/hour, `money`
12/hour, plus `anon` and `user` as the floor.

### Uploads

An upload is checked three ways before it is accepted: the extension, the
declared content type, and the first bytes of the file. Only PDF, JPG, PNG, WEBP
and HEIC pass. Before this only the size was checked, so `.html` and `.svg` were
accepted and then served back from the portal's own origin, where they run as the
portal's own page.

Everything under `MEDIA_URL` is also served with `Content-Disposition:
attachment` and `X-Content-Type-Options: nosniff` by
`config.middleware.UploadedFileHeadersMiddleware`. **On a deployment where the
web server serves media directly, set those two headers there as well** — Django
never sees those requests.

### Configuration

Everything environment-specific reads from `backend/.env`; see `.env.example`.

`DATABASE_URL` switches the project onto PostgreSQL with no other change, and the
query string is honoured, so `?sslmode=require` on a managed database is kept
rather than silently dropped. Connections are reused for ten minutes, because a
pooler in front of a managed database charges for them.

Two things have no default and will stop the project rather than fall back:

* `DJANGO_SECRET_KEY` — with `DJANGO_DEBUG` off, a missing key raises rather than
  using a value that is printed in this repository. In debug it is generated per
  start, so it can never quietly become something depended on. Make it at least
  50 characters: a short key is also the JWT signing key, and under 32 bytes is
  too short for HS256.
* `FRONTEND_URL` — with `DJANGO_DEBUG` off, a localhost value raises, because the
  mail would still send and every button in it would be dead for the recipient.

`DJANGO_DEBUG` defaults to **off**, so a deployment that forgets it gets the safe
behaviour: HSTS, secure cookies and the SSL redirect are all on.
`apps/accounts/checks.py` holds these checks; `manage.py check --deploy` runs
them.

---

## Frontend

React 19 with Vite, React Router and Axios. Charts are Chart.js through
`react-chartjs-2`.

```
frontend/src/
├── api/           Axios client with token refresh, and the endpoint map
├── components/    Shell, charts, and the shared UI pieces (modal, dropzone…)
├── context/       Auth session and toasts
├── features/      landing · auth · wizard · applicant portal · agent portal
├── hooks/         Catalogue data
├── lib/           Formatting helpers and the SVG icon set
└── styles/        Design tokens and the stylesheets
```

The portals and the wizard are lazily loaded, and Chart.js sits in its own
bundle, so the landing page does not download either.

### Design

`src/styles/tokens.css` holds the design system as CSS custom properties: a
deep-green brand ramp, warm-neutral surfaces, a type and spacing scale, and an
ordinal chart ramp validated for contrast in both light and dark. Components
reference the tokens rather than hex values, and a dark appearance is available
by setting `data-theme="dark"` on `<html>`.

Every icon is a drawn SVG from `src/lib/icons.jsx` on one grid at one stroke
weight — no emoji, and no characters pressed into service as icons. Each chart
ships with a table of the same numbers beneath it, so nothing is reachable by
hover alone.

---

## Production build

```bash
cd frontend && npm run build          # static files in frontend/dist
cd backend  && python manage.py collectstatic --no-input
```

Serve `frontend/dist` from any static host with a catch-all rewrite to
`index.html` (the app routes on the client), and run the API with
`gunicorn config.wsgi` behind your web server.

**Serve both from one hostname**, with the API under `/api` and the built app
everywhere else. The refresh-token cookie is same-origin, so splitting them
across two domains logs everyone out on every reload.

Before going live:

- [ ] `DJANGO_SECRET_KEY` set, 50+ characters, not shared with anything else
- [ ] `DJANGO_DEBUG` unset or `False`
- [ ] `DJANGO_ALLOWED_HOSTS` lists your domains
- [ ] `FRONTEND_URL` is the public https address
- [ ] `DATABASE_URL` points at the production database with `sslmode=require`
- [ ] `EMAIL_HOST_PASSWORD` set, and rotated if it was ever in a file
- [ ] `PAYSTACK_SECRET_KEY`, or the three `PAYOUT_BANK_*` values for transfer mode
- [ ] the provider's webhook points at `/api/payments/webhook/paystack/`
- [ ] the web server sets `Content-Disposition: attachment` and
      `X-Content-Type-Options: nosniff` on everything under `/media/`
- [ ] `manage.py check --deploy` is clean
- [ ] an admin exists: `manage.py ensure_admin --email you@example.com`
