import os
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_compress import Compress
from flask_login import LoginManager
from flask_mail import Mail
from flask_caching import Cache

csrf = CSRFProtect()
compress = Compress()
login_manager = LoginManager()
mail = Mail()
cache = Cache()

rate_limit_storage_uri = os.getenv('RATELIMIT_STORAGE_URI') or os.getenv('REDIS_URL') or 'memory://'
# Per-IP defaults. Bangladeshi carriers CGNAT heavily: hundreds of visitors
# can share one public IP, so the old 500/hour throttled whole carrier pools.
# Sensitive routes (login, register, contact, AI) keep their own tight
# decorators — these defaults only govern ordinary page browsing.
_default_limits = [s.strip() for s in os.getenv(
    "RATELIMIT_DEFAULTS", "2500 per hour;12000 per day").split(";") if s.strip()]

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=_default_limits,
    storage_uri=rate_limit_storage_uri,
)
