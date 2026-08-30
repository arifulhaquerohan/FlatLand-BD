import os
from datetime import datetime, timedelta
from dotenv import load_dotenv


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Load local development values before importing modules that read environment
# variables at import time. cPanel variables remain authoritative because
# override=False does not replace values supplied by Passenger.
load_dotenv(os.path.join(PROJECT_ROOT, '.env'), override=False)

from flask import Flask, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_wtf.csrf import CSRFError

from .models import db, User
from .extensions import csrf, compress, limiter, login_manager, mail, cache
from .utils import optimized_image_srcset, optimized_image_url
from .blueprints.public import public_bp
from .blueprints.admin import admin_bp

FRONTEND_DIR = os.path.join(PROJECT_ROOT, 'frontend')

def resolve_instance_path():
    explicit = os.getenv('INSTANCE_PATH')
    default_path = os.path.join(PROJECT_ROOT, 'instance')
    if explicit:
        candidate = explicit
    elif os.getenv('VERCEL') or os.getenv('AWS_LAMBDA_FUNCTION_NAME') or os.getenv('AWS_EXECUTION_ENV'):
        candidate = '/tmp/instance'
    else:
        candidate = default_path
    try:
        os.makedirs(candidate, exist_ok=True)
        return candidate
    except OSError:
        fallback = '/tmp/instance'
        try:
            os.makedirs(fallback, exist_ok=True)
            return fallback
        except OSError:
            return default_path

app = Flask(
    __name__,
    instance_path=resolve_instance_path(),
    template_folder=os.path.join(FRONTEND_DIR, 'templates'),
    static_folder=os.path.join(FRONTEND_DIR, 'static'),
)

if os.getenv('TRUST_PROXY', '0') == '1':
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

secret_key = (os.getenv('SECRET_KEY') or '').strip()
if len(secret_key) < 32 or secret_key.lower() in {'change-me', 'replace-me'}:
    raise RuntimeError(
        'SECRET_KEY must be set to a unique random value of at least 32 characters.'
    )
    
app.config['SECRET_KEY'] = secret_key
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
app.config['SESSION_COOKIE_SECURE'] = os.getenv('SESSION_COOKIE_SECURE', '0') == '1'
app.config['REMEMBER_COOKIE_HTTPONLY'] = True
app.config['REMEMBER_COOKIE_SAMESITE'] = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
app.config['REMEMBER_COOKIE_SECURE'] = os.getenv('SESSION_COOKIE_SECURE', '0') == '1'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=6)
MAX_UPLOAD_MB = max(4, int(os.getenv('MAX_UPLOAD_MB', '24')))
app.config['MAX_UPLOAD_MB'] = MAX_UPLOAD_MB
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_MB * 1024 * 1024
app.config['WTF_CSRF_TIME_LIMIT'] = int(os.getenv('WTF_CSRF_TIME_LIMIT', '21600'))
app.config['WTF_CSRF_SSL_STRICT'] = True
app.config['COMPRESS_MIN_SIZE'] = int(os.getenv('COMPRESS_MIN_SIZE', '512'))
app.config['COMPRESS_LEVEL'] = int(os.getenv('COMPRESS_LEVEL', '6'))
app.config['COMPRESS_MIMETYPES'] = ['text/html', 'text/css', 'application/javascript', 'application/json', 'application/xml', 'text/xml', 'text/plain', 'image/svg+xml']
app.config['PUBLIC_CACHE_TTL'] = int(os.getenv('PUBLIC_CACHE_TTL', '120'))
app.config['PUBLIC_CACHE_TTL_LONG'] = int(os.getenv('PUBLIC_CACHE_TTL_LONG', '3600'))

database_url = os.getenv('DATABASE_URL', 'sqlite:///flatland.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True, 'pool_recycle': 280}
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000
app.config['LISTINGS_PER_PAGE'] = int(os.getenv('LISTINGS_PER_PAGE', '9'))
app.config['ADMIN_DASHBOARD_RECENT_LIMIT'] = int(os.getenv('ADMIN_DASHBOARD_RECENT_LIMIT', '8'))
app.config['ADMIN_LISTINGS_PER_PAGE'] = int(os.getenv('ADMIN_LISTINGS_PER_PAGE', '20'))
app.config['ALLOWED_IMAGE_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'webp'}
app.config['MAX_GALLERY_IMAGES'] = int(os.getenv('MAX_GALLERY_IMAGES', '10'))
app.config['DEFAULT_META_DESCRIPTION'] = 'FlatlandBD is a trusted platform for buying and selling flats, plus premium interior design services in Bangladesh.'
app.config['DEFAULT_OG_IMAGE'] = os.getenv('DEFAULT_OG_IMAGE', 'https://images.unsplash.com/photo-1505691938895-1758d7feb511?ixlib=rb-4.0.3&auto=format&fit=crop&w=1200&q=80')
app.config['CLOUDINARY_CLOUD_NAME'] = os.getenv('CLOUDINARY_CLOUD_NAME')

# Flask Mail config
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True').lower() in ['true', '1']
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')
app.config['ADMIN_EMAIL'] = os.getenv('ADMIN_EMAIL')
app.config['ADMIN_PATH'] = os.getenv('ADMIN_PATH', 'admin').strip().strip('/') or 'admin'

# Init extensions
db.init_app(app)
compress.init_app(app)
csrf.init_app(app)
limiter.init_app(app)
mail.init_app(app)
login_manager.init_app(app)

cache_config = {'CACHE_TYPE': 'SimpleCache'}
if os.getenv('REDIS_URL'):
    cache_config = {'CACHE_TYPE': 'RedisCache', 'CACHE_REDIS_URL': os.getenv('REDIS_URL')}
app.config.from_mapping(cache_config)
cache.init_app(app)

login_manager.login_view = 'public.login'
login_manager.session_protection = "strong"

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def static_url(filename):
    from flask import url_for
    if not filename: return ''
    file_path = os.path.join(app.static_folder, filename)
    try: version = int(os.path.getmtime(file_path))
    except OSError: version = None
    return url_for('static', filename=filename, v=version) if version else url_for('static', filename=filename)

app.jinja_env.globals['static_url'] = static_url
app.jinja_env.globals['optimized_image_url'] = optimized_image_url
app.jinja_env.globals['optimized_image_srcset'] = optimized_image_srcset

def format_bdt(value):
    """Bangladeshi price formatting: ৳ 1.25 Cr, ৳ 12.5 Lakh, ৳ 8,50,000."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num <= 0:
        return None
    crore = num / 10000000.0
    if crore >= 1:
        text = ('%.2f' % crore).rstrip('0').rstrip('.')
        return '৳ %s Cr' % text
    lakh = num / 100000.0
    if lakh >= 1:
        text = ('%.2f' % lakh).rstrip('0').rstrip('.')
        return '৳ %s Lakh' % text
    whole = int(round(num))
    s = str(whole)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        parts.insert(0, head)
        grouped = ','.join(parts) + ',' + tail
    else:
        grouped = s
    return '৳ %s' % grouped

app.jinja_env.filters['format_bdt'] = format_bdt

@app.context_processor
def override_url_for():
    from flask import url_for as _url_for
    def custom_url_for(endpoint, **values):
        if endpoint and "." not in endpoint and endpoint != "static":
            admin_endpoints = {'admin_dashboard', 'approve_listing', 'delete_listing', 'update_listing_status', 'update_lead_status', 'delete_lead', 'bulk_update_listings', 'bulk_update_leads', 'edit_listing', 'export_data', 'preview', 'media_library', 'media_test', 'system_health'}
            if endpoint in admin_endpoints:
                endpoint = f"admin.{endpoint}"
            else:
                endpoint = f"public.{endpoint}"
        return _url_for(endpoint, **values)
    return dict(url_for=custom_url_for)

@app.context_processor
def inject_meta_defaults():
    return {
        'default_meta_description': app.config['DEFAULT_META_DESCRIPTION'],
        'default_og_image': app.config['DEFAULT_OG_IMAGE'],
        'cloudinary_cloud_name': app.config.get('CLOUDINARY_CLOUD_NAME'),
        'current_year': datetime.utcnow().year,
        'max_upload_mb': app.config['MAX_UPLOAD_MB'],
        'maintenance_notice': os.getenv('MAINTENANCE_NOTICE', '1') == '1',
    }

@app.after_request
def add_security_headers(response):
    csp_parts = [
        "default-src 'self'", "base-uri 'self'", "object-src 'none'", "frame-ancestors 'self'", "form-action 'self'",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "script-src 'self' 'unsafe-inline'",
        "font-src 'self' data: https://fonts.gstatic.com", "img-src 'self' data: blob: https:",
        "frame-src 'self' https://www.google.com https://maps.google.com https://maps.gstatic.com https://www.youtube.com https://www.youtube-nocookie.com",
        "connect-src 'self'",
    ]
    response.headers.setdefault('Content-Security-Policy', '; '.join(csp_parts))
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    response.headers.setdefault('Permissions-Policy', 'geolocation=(), microphone=(), camera=(), payment=()')
    
    current_user_auth = False
    try:
        from flask_login import current_user
        current_user_auth = current_user.is_authenticated
    except Exception:
        pass
    request_secure = request.is_secure if request else False
    if request_secure:
        response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
        
    path = request.path if request else '/'
    endpoint = request.endpoint if request else None

    PUBLIC_CACHE_ENDPOINTS = {'public.index', 'public.flats', 'public.interior', 'public.flat_detail', 'public.interior_detail', 'public.robots', 'public.sitemap'}
    if path.startswith('/static/'): response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    elif path.startswith(f"/{app.config['ADMIN_PATH']}") or current_user_auth: response.headers['Cache-Control'] = 'no-store'
    
    if request.method == 'GET' and not current_user_auth and not response.headers.get('Set-Cookie') and endpoint in PUBLIC_CACHE_ENDPOINTS:
        ttl = app.config['PUBLIC_CACHE_TTL_LONG'] if endpoint in {'public.robots', 'public.sitemap'} else app.config['PUBLIC_CACHE_TTL']
        response.headers.setdefault('Cache-Control', f'public, max-age={ttl}, stale-while-revalidate={ttl // 2}')
        response.headers.setdefault('X-DNS-Prefetch-Control', 'on')
        
    vary = response.headers.get('Vary')
    if vary:
        if 'Accept-Encoding' not in vary: response.headers['Vary'] = f'{vary}, Accept-Encoding'
    else: response.headers['Vary'] = 'Accept-Encoding'
    return response

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    try:
        db.session.rollback()
    except Exception:
        pass
    app.logger.exception('Unhandled server error')
    return render_template('500.html'), 500

@app.errorhandler(413)
def payload_too_large(e):
    from flask import flash, redirect, request as flask_request
    flash(f"Those files are larger than {app.config['MAX_UPLOAD_MB']} MB in total. Please upload fewer or smaller photos.", 'warning')
    return redirect(flask_request.referrer or '/'), 302

@app.errorhandler(CSRFError)
def csrf_error(e):
    # A stale or missing security token (e.g. a form left open too long while
    # picking photos) used to fall through to a raw, unstyled 400 page that
    # looked like the site had crashed. Send people back with a plain-language
    # message and a working page instead.
    from flask import flash, redirect, request as flask_request
    db.session.rollback()
    flash('Your session timed out before this was submitted. Please try again.', 'warning')
    return redirect(flask_request.referrer or '/'), 302

# Register Blueprints
app.register_blueprint(public_bp)
app.register_blueprint(admin_bp, url_prefix=f"/{app.config['ADMIN_PATH']}")

def ensure_schema_upgrades():
    """Add columns introduced after the first release.

    db.create_all() only creates missing tables, never missing columns, so an
    existing database would break when a new column is added. This runs once at
    boot, is safe to repeat, and never takes the site down if it fails.
    """
    from sqlalchemy import inspect, text
    try:
        inspector = inspect(db.engine)
        if 'user' not in inspector.get_table_names():
            return
        columns = {col['name'] for col in inspector.get_columns('user')}

        if 'username' not in columns:
            with db.engine.begin() as conn:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN username VARCHAR(30)'))
            app.logger.info('Added user.username column.')

        # Give every pre-existing account a username so they can still sign in.
        from .utils_username import allocate_username
        pending = User.query.filter(
            (User.username.is_(None)) | (User.username == '')
        ).all()
        for account in pending:
            chosen = allocate_username(account.full_name or ('member%d' % account.id))
            account.username = chosen or ('member%d' % account.id)
        if pending:
            db.session.commit()
            app.logger.info('Backfilled %d username(s).', len(pending))

        try:
            with db.engine.begin() as conn:
                conn.execute(text(
                    'CREATE UNIQUE INDEX IF NOT EXISTS ix_user_username ON "user" (username)'
                ))
        except Exception:
            pass  # MySQL/Postgres may already have it, or not support IF NOT EXISTS
    except Exception as exc:
        db.session.rollback()
        app.logger.warning('Schema upgrade skipped: %s', exc)


with app.app_context():
    db.create_all()
    ensure_schema_upgrades()

    # Create admin if missing
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'Admin')
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
    ADMIN_PHONE = os.getenv('ADMIN_PHONE', '01700000000')
    if not User.query.filter_by(role='admin').first():
        if ADMIN_PASSWORD:
            from .utils_username import allocate_username
            admin = User(full_name=ADMIN_USERNAME, role='admin')
            admin.username = allocate_username(ADMIN_USERNAME) or 'owner_bd'
            admin.phone = ADMIN_PHONE
            if ADMIN_EMAIL:
                admin.email = ADMIN_EMAIL
            admin.set_password(ADMIN_PASSWORD)
            db.session.add(admin)
            db.session.commit()
            print("Admin user created from environment variables.")

# Force HTTPS cookies when behind HTTPS terminators.
if os.getenv('FORCE_HTTPS', '0') == '1':
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['REMEMBER_COOKIE_SECURE'] = True

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    # Debug is opt-in via FLASK_DEBUG=1. Never enable it on a public server:
    # the Werkzeug debugger allows remote code execution.
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug, host='0.0.0.0', port=port)
