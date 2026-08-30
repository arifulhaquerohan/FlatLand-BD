# FlatLand BD

Flats and interior studios for Bangladesh. Every listing is checked by a human before it
goes live, and every enquiry lands in one inbox inside the operations console.

---

## What this is built with, and why

| Layer | Choice | Reason |
| --- | --- | --- |
| Server | Flask (Python 3.11) | Runs on shared cPanel hosting with Passenger. No Node process needed in production. |
| Templates | Jinja | Server rendered HTML, so pages are fast and indexable on cheap hosting. |
| Styling | Hand written CSS, three files | **No build step.** Edit the file, refresh the browser. Nothing to compile before deploy. |
| Scripting | Vanilla JS, two files | No framework, no npm install, no lock file to rot. Everything degrades gracefully if JS fails. |
| Images | Cloudinary, optional | Automatic WebP conversion, resizing and CDN delivery. Falls back to local disk if keys are absent. |
| Database | SQLite by default, MySQL or Postgres via one variable | Works instantly, upgrades without code changes. |

Tailwind and its build pipeline were removed. There is no `npm run build`; the CSS you
see in `frontend/static/css` is the CSS the browser gets.

---

## Project layout

```
wsgi.py                    Passenger entry point (exposes `application`)
requirements.txt           Python dependencies
.env.example               Every setting, documented. Copy to .env
CLOUDINARY.md              Ten minute image CDN setup guide
CPANEL_SETUP.md            Step by step hosting guide

backend/
  app.py                   App factory, config, security headers, caching
  models.py                User, Flat, InteriorService, images, Lead, MediaAsset
  forms.py                 WTForms with CSRF
  extensions.py            db, login manager, limiter, cache, mail, compress
  utils.py                 Uploads, image URLs, YouTube embeds, media cleanup
  utils_security.py        Encryption and hashing for phone and email
  cloudinary_service.py    Single source of truth for image storage
  blueprints/
    public.py              Website: browse, detail, auth, dashboard, post listing
    admin.py               Console: moderation, leads, media, health, export

frontend/
  templates/               20 Jinja templates, public site plus console
  static/css/core.css      Tokens, layout, buttons, forms, shared components
  static/css/site.css      Public site only
  static/css/console.css   Admin console only
  static/js/app.js         Public site interactions and animation
  static/js/console.js     Console: command palette, bulk actions, charts
  static/img/              Logo mark and icon
  static/uploads/          Local image fallback when Cloudinary is off
```

---

## Running it locally

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # then edit the marked values
python -m backend.app
```

Open `http://127.0.0.1:5001`. The admin console lives at the path you set in
`ADMIN_PATH`, for example `http://127.0.0.1:5001/console-x7`.

An admin account is created on first boot from `ADMIN_USERNAME`, `ADMIN_EMAIL` and
`ADMIN_PASSWORD`. Change the password after the first login.

---

## Settings you must set

These four are the difference between a demo and a real deployment:

| Variable | Why it matters |
| --- | --- |
| `SECRET_KEY` | Signs sessions. Random, 32 bytes or more. |
| `DATA_ENCRYPTION_KEY` | Encrypts stored phone numbers and emails. **If you lose it, that data is unreadable.** |
| `ADMIN_PATH` | Moves the console off `/admin` so bots cannot find the login. |
| `ADMIN_PASSWORD` | The first admin login. |

Generate the two keys:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Everything else is documented inline in `.env.example`.

---

## The public site

- **Home** — hero with live counts, handpicked flats, studios, how it works, enquiry form.
- **Buy flats** — search, BHK, price range and four sort orders, with a result summary and
  an empty state that explains what to widen.
- **Interior studios** — packages with prices stated up front.
- **Detail pages** — gallery with lightbox and keyboard navigation, YouTube embeds through
  the cookie free domain, WhatsApp and call buttons, related listings.
- **Accounts** — register, sign in, personal dashboard, post a listing through a three step
  wizard with drag and drop uploads and live previews.
- **Extras** — scroll progress, reveal on scroll, animated counters, sitemap, robots,
  custom 404 and 500 pages.

All motion respects `prefers-reduced-motion`. Content is visible with animation disabled,
and the site still works with JavaScript switched off.

---

## The operations console

Reachable at `/<ADMIN_PATH>`, admin accounts only, dark by design so it never gets
confused with the public site.

- **Overview** — counts, a fourteen day submissions and enquiries chart, approval rings,
  newest listings and enquiries, quick actions.
- **Flats, Studios, Leads** — one table per tab with search, status filter, instant client
  side filtering, select all, bulk approve, reject or delete behind a confirm dialog, and
  per row status changes.
- **Media and CDN** — every image the site serves, where it is stored, how much is on the
  CDN, and a one click connection test.
- **Health and config** — live checks on database, security keys, storage, mail, cache and
  rate limiting, with the installed package versions.
- **Live preview** — the public site inside desktop, tablet and phone frames.
- **Export data** — flats and leads as CSV.
- **Command palette** — `Cmd K` or `Ctrl K`, jump anywhere. `/` focuses the search box.

---

## Images

Uploads are converted to WebP and capped at 1600px, so a six megabyte phone photo becomes
a few hundred kilobytes. With Cloudinary keys present, files go to the CDN and visitors get
a size matched to their screen. Without keys, files go to `frontend/static/uploads` and the
site works exactly the same, just heavier.

Deleting a listing or removing a gallery photo also deletes the stored file, so nothing is
left orphaned. Setup takes about ten minutes: see `CLOUDINARY.md`.

---

## Security posture

CSRF on every form, rate limits on login, registration, enquiries and admin actions,
hashed passwords, encrypted contact details, a strict Content Security Policy, HTTPS
redirect and secure cookies behind `FORCE_HTTPS`, and an admin console on a secret path.
Uploads are validated by extension, decoded by Pillow before being stored, and capped by
`MAX_UPLOAD_MB` with a friendly page instead of a raw error when the cap is hit.

---

## Deploying

See `CPANEL_SETUP.md`. Short version: upload, create a Python 3.11 app pointing at
`wsgi.py` with entry point `application`, run pip install against `requirements.txt`,
create `.env`, restart.
