# FlatLand BD 🏠

A full-stack real estate marketplace for Bangladesh — list flats for sale and discover interior design studios, with a complete admin console, Cloudinary-powered image delivery, and security-focused architecture.

## ✨ Features

### For visitors & members
- Browse verified **flat listings** with filters (location, BHK, price range, sort) and search
- Discover **interior design studios** with portfolios and starting prices
- Member accounts with **username / mobile / email login**, encrypted contact data at rest
- Members can **post listings** (pending review) and **delete their own listings**
- Responsive design with lazy-loaded, screen-optimized images

### Admin console
- Dashboard with **live stats and 14-day activity trends**
- Approve / reject / edit / **bulk-delete** flats & studios
- Lead management (new → contacted → closed) with **CSV export**
- **Media library** — see every image, where it's stored, and Cloudinary connection health
- **System health page** — security, storage, performance, and content checks in one place
- AI-assisted listing description generator (drop-in LLM-ready)

### Images & Cloudinary ☁️
- Uploads converted to **WebP**, capped at 1600px
- Auto-resized delivery with **srcset** for every screen
- **Deleting a listing, gallery photo, or cover photo also deletes the file from Cloudinary** — no orphaned files
- Automatic fallback to local storage if Cloudinary is unreachable

### Security & performance
- Encrypted phone/email at rest (blind-indexed lookups)
- CSRF protection, rate limiting, security headers, HTTPS-only cookies
- Redis-backed caching & rate limits (in-memory fallback)
- Gzip/Brotli compression and long-term static caching

## 🛠 Tech Stack

| Layer | Tech |
| --- | --- |
| Backend | Python 3.11 · Flask 3.0 · SQLAlchemy |
| Frontend | Jinja2 templates · custom CSS/JS |
| Database | SQLite (dev) · PostgreSQL / MySQL (prod) |
| Images | Pillow · Cloudinary CDN |
| Auth | Flask-Login · Werkzeug password hashing |
| Extras | Flask-WTF · Flask-Mail · Flask-Limiter · Flask-Compress · Flask-Caching · Redis |
| Server | Gunicorn · cPanel/Passenger ready |

## 🚀 Getting Started

### Prerequisites
- Python 3.11+ (3.11 recommended — pins are tested against it)
- pip & virtualenv

### Install & run

```bash
# 1. Clone & enter the project
cd flatlandbd

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate        # fish: source venv/bin/activate.fish

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
#   → set SECRET_KEY (32+ chars), DATA_ENCRYPTION_KEY,
#     Cloudinary keys, and admin credentials

# 5. Run (dev)
python app.py                    # http://localhost:5001

# 6. Run (production)
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
```

The app auto-creates the SQLite database and the admin account on first boot.

## ☁️ Cloudinary Setup (10 minutes)

1. Create a free account at [cloudinary.com](https://cloudinary.com)
2. Copy **cloud name, API key, API secret** from Settings → API Keys
3. Add them to `.env`:

```ini
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=123456789012345
CLOUDINARY_API_SECRET=your-secret
CLOUDINARY_FOLDER=flatlandbd/uploads
MAX_UPLOAD_MB=24
```

4. Restart the app, then verify from the admin **Media** page (Test connection).

> Without Cloudinary, uploads fall back to local storage — the site still works.

## 📁 Project Structure

```
flatlandbd/
├── app.py                  # entry point (dev)
├── wsgi.py                 # entry point (production)
├── requirements.txt
├── .env.example
├── backend/
│   ├── app.py              # Flask app factory & config
│   ├── models.py           # SQLAlchemy models
│   ├── cloudinary_service.py
│   ├── utils.py
│   └── blueprints/
│       ├── public.py       # visitor + member routes
│       └── admin.py        # admin console
└── frontend/
    ├── templates/          # Jinja2 templates
    └── static/             # CSS, JS, images
```

## 🔐 Environment Variables

See `.env.example` for the full list. Key ones:

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Session signing (32+ chars, required) |
| `DATA_ENCRYPTION_KEY` | Encrypts phone/email at rest |
| `DATABASE_URL` | SQLite default; PostgreSQL/MySQL supported |
| `CLOUDINARY_*` | Cloudinary image hosting |
| `ADMIN_USERNAME/PASSWORD/PHONE` | Auto-creates admin on first boot |
| `REDIS_URL` | Optional: shared cache & rate-limit store |

## 📜 License

MIT — see [LICENSE](LICENSE).

## Google sign-in

1. In [Google Auth Platform](https://console.cloud.google.com/auth/clients), configure branding, audience and an OAuth client of type **Web application**.
2. Add authorized JavaScript origins: `http://localhost:5001`, `http://127.0.0.1:5001`, and your production HTTPS origin. Origins contain no path. Use localhost locally rather than a LAN IP.
3. Put the public client ID in `.env`: `GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com`, then restart Flask. No client secret or redirect URI is needed for this popup ID-token flow.
4. If Google is in Testing mode, add your test Google accounts in Audience before testing.

The official Continue with Google button appears on Sign In and Create Account only when configured. The backend validates Google's signed token, audience, expiry, verified email, and a session nonce; POSTs require Flask CSRF. New members supply a username and mobile number. Matching emails require the existing account password before linking. Duplicate phone numbers never link accounts automatically. Google members receive no user-facing password. A new `google_identity` table is created at startup without changing existing user rows.

Check both account pages on localhost, complete a new registration, sign out and sign in again with Google, and test linking an existing password account. Google sign-in requires network access to Google. If it fails, existing password sign-in remains available.

## Password recovery

Sign In includes **Forgot password?**. Recovery uses the account's email address. Accounts without email should contact support; Google users can continue signing in with Google.

Configure your SMTP provider with `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER` and `MAIL_USE_TLS`. For port 465 use `MAIL_USE_SSL=1` and `MAIL_USE_TLS=0`. Set `PASSWORD_RESET_BASE_URL=http://localhost:5001` locally and your actual `https://` website origin in production, with no path. Restart after changing environment variables. Until SMTP and a trusted origin are configured, the recovery page explains that email recovery is unavailable.

Reset requests return the same confirmation for recognized and unknown emails. Email delivery runs in a background thread; check server logs for delivery errors. Only token hashes are stored. Links expire after 30 minutes, and resetting revokes every outstanding link and existing login for that member. Existing members will need to sign in once after deploying the new session format. Confirm delivery with your mail provider before enabling production recovery; background threads are best-effort if a worker exits.
