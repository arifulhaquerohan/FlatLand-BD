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
