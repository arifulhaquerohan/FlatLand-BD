"""Cloudinary integration for FlatLand BD.

One place that knows how images are stored. Everything else (uploads,
admin media page, health checks) asks this module instead of touching the
Cloudinary SDK or environment variables directly.

The module is deliberately defensive:

* it never raises on import when the ``cloudinary`` package is missing,
* it never raises when credentials are absent - callers get a clear status
  dict and can fall back to local storage,
* every network call is wrapped so a Cloudinary outage cannot take the
  website down.
"""

from __future__ import annotations

import os
import re
import time
import threading
from typing import Any, Dict, Optional, Tuple

try:  # pragma: no cover - the SDK is an optional dependency at import time
    import cloudinary
    import cloudinary.api
    import cloudinary.uploader
    import cloudinary.utils
    SDK_AVAILABLE = True
    SDK_ERROR = None
except Exception as exc:  # pragma: no cover
    cloudinary = None
    SDK_AVAILABLE = False
    SDK_ERROR = str(exc)


DEFAULT_FOLDER = 'flatlandbd/uploads'

# https://res.cloudinary.com/<cloud>/image/upload/<transforms>/<public_id>.<ext>
DELIVERY_RE = re.compile(
    r'^(?:https?:)?//res\.cloudinary\.com/([^/]+)/(image|video)/upload/(.+)$',
    re.IGNORECASE,
)

_TRANSFORM_SEGMENT_RE = re.compile(r'^[a-z]{1,3}_[^/]+', re.IGNORECASE)
_VERSION_SEGMENT_RE = re.compile(r'^v\d+$', re.IGNORECASE)

_lock = threading.Lock()
_configured_signature: Optional[Tuple[str, str, str]] = None


# --------------------------------------------------------------------------- #
#  Credentials
# --------------------------------------------------------------------------- #
def _clean(value: Optional[str]) -> str:
    if not value:
        return ''
    return str(value).strip().strip('"').strip("'")


def credentials() -> Dict[str, str]:
    """Read credentials from the environment.

    Supports both styles Cloudinary documents:

    * three separate variables (CLOUDINARY_CLOUD_NAME / _API_KEY / _API_SECRET)
    * a single CLOUDINARY_URL connection string
    """
    cloud_name = _clean(os.environ.get('CLOUDINARY_CLOUD_NAME'))
    api_key = _clean(os.environ.get('CLOUDINARY_API_KEY'))
    api_secret = _clean(os.environ.get('CLOUDINARY_API_SECRET'))
    from_url = False

    url_value = _clean(os.environ.get('CLOUDINARY_URL'))
    if url_value and not (cloud_name and api_key and api_secret):
        parsed = _parse_cloudinary_url(url_value)
        if parsed:
            api_key = api_key or parsed['api_key']
            api_secret = api_secret or parsed['api_secret']
            cloud_name = cloud_name or parsed['cloud_name']
            from_url = True

    return {
        'cloud_name': cloud_name,
        'api_key': api_key,
        'api_secret': api_secret,
        'folder': _clean(os.environ.get('CLOUDINARY_FOLDER')) or DEFAULT_FOLDER,
        'from_url': from_url,
    }


def _parse_cloudinary_url(value: str) -> Optional[Dict[str, str]]:
    """Parse cloudinary://key:secret@cloud_name without urllib surprises."""
    marker = '://'
    if marker not in value:
        return None
    body = value.split(marker, 1)[1]
    if '@' not in body or ':' not in body.split('@', 1)[0]:
        return None
    auth, host = body.split('@', 1)
    api_key, api_secret = auth.split(':', 1)
    cloud_name = host.split('/', 1)[0]
    if not (api_key and api_secret and cloud_name):
        return None
    return {
        'cloud_name': cloud_name,
        'api_key': api_key,
        'api_secret': api_secret,
    }


def configured() -> bool:
    """True when uploads can go to Cloudinary right now."""
    if not SDK_AVAILABLE:
        return False
    creds = credentials()
    return bool(creds['cloud_name'] and creds['api_key'] and creds['api_secret'])


def ensure_configured() -> bool:
    """Configure the SDK once per credential set. Cheap to call repeatedly."""
    global _configured_signature
    if not configured():
        return False
    creds = credentials()
    signature = (creds['cloud_name'], creds['api_key'], creds['api_secret'])
    with _lock:
        if _configured_signature != signature:
            cloudinary.config(
                cloud_name=creds['cloud_name'],
                api_key=creds['api_key'],
                api_secret=creds['api_secret'],
                secure=True,
            )
            _configured_signature = signature
    return True


def folder() -> str:
    return credentials()['folder']


def cloud_name() -> str:
    return credentials()['cloud_name']


def status() -> Dict[str, Any]:
    """Everything the admin UI needs to explain the current setup."""
    creds = credentials()
    return {
        'configured': configured(),
        'cloud_name': creds['cloud_name'],
        'folder': creds['folder'],
        'api_key_set': bool(creds['api_key']),
        'api_secret_set': bool(creds['api_secret']),
        'from_url': creds['from_url'],
        'sdk_available': SDK_AVAILABLE,
        'sdk_error': SDK_ERROR,
    }


# --------------------------------------------------------------------------- #
#  Delivery URLs
# --------------------------------------------------------------------------- #
def is_delivery_url(url: Optional[str]) -> bool:
    return bool(url) and bool(DELIVERY_RE.match(str(url).strip()))


def public_id_from_url(url: Optional[str]) -> Optional[str]:
    """Recover the public id (including folder) from a delivery URL."""
    if not url:
        return None
    match = DELIVERY_RE.match(str(url).strip())
    if not match:
        return None

    remainder = match.group(3)
    remainder = remainder.split('?', 1)[0].split('#', 1)[0]
    segments = [segment for segment in remainder.split('/') if segment]

    # Drop leading transformation segments (w_900, c_fill, f_auto,q_auto ...)
    while segments and _TRANSFORM_SEGMENT_RE.match(segments[0]):
        segments.pop(0)
    # Drop the version segment (v1712345678)
    if segments and _VERSION_SEGMENT_RE.match(segments[0]):
        segments.pop(0)
    if not segments:
        return None

    public_id = '/'.join(segments)
    if '.' in public_id.rsplit('/', 1)[-1]:
        public_id = public_id.rsplit('.', 1)[0]
    return public_id or None


def build_url(url: str, width: int = 900, height: Optional[int] = None,
              crop: str = 'fill', quality: str = 'auto',
              fetch_format: str = 'auto') -> str:
    """Insert resize/format transformations into a delivery URL.

    Falls back to the original URL for anything that is not a Cloudinary
    delivery URL, so templates can call it on every image.
    """
    if not is_delivery_url(url):
        return url
    match = DELIVERY_RE.match(str(url).strip())
    if not match:
        return url

    parts = ['f_' + str(fetch_format), 'q_' + str(quality), 'c_' + str(crop)]
    if width:
        parts.append('w_' + str(int(width)))
    if height:
        parts.append('h_' + str(int(height)))
    if crop in ('fill', 'lfill', 'thumb'):
        parts.append('g_auto')
    transform = ','.join(parts)

    prefix = str(url).strip().split('/upload/', 1)[0]
    remainder = match.group(3)
    # Strip a transformation block that we (or a previous save) already added.
    first = remainder.split('/', 1)[0]
    if _TRANSFORM_SEGMENT_RE.match(first) and ',' in first:
        remainder = remainder.split('/', 1)[1] if '/' in remainder else remainder
    return prefix + '/upload/' + transform + '/' + remainder


def build_srcset(url: str, widths=(420, 640, 900, 1200, 1600)) -> str:
    if not is_delivery_url(url):
        return ''
    entries = []
    for width in widths:
        entries.append(build_url(url, width=width) + ' ' + str(int(width)) + 'w')
    return ', '.join(entries)


# --------------------------------------------------------------------------- #
#  Write operations
# --------------------------------------------------------------------------- #
def upload_stream(stream, original_filename: str = '',
                  subfolder: str = '') -> Dict[str, Any]:
    """Upload a file-like object of image bytes.

    Returns ``{'ok': bool, 'url': str, 'public_id': str, 'error': str}``.
    Never raises.
    """
    if not ensure_configured():
        return {'ok': False, 'url': '', 'public_id': '', 'error': 'Cloudinary is not configured'}

    target_folder = folder()
    if subfolder:
        target_folder = target_folder.rstrip('/') + '/' + subfolder.strip('/')

    name_root = os.path.splitext(os.path.basename(original_filename or 'image'))[0]
    name_root = re.sub(r'[^a-zA-Z0-9_-]+', '-', name_root).strip('-').lower() or 'image'
    public_id = str(int(time.time() * 1000)) + '_' + name_root[:60]

    try:
        result = cloudinary.uploader.upload(
            stream,
            folder=target_folder,
            public_id=public_id,
            resource_type='image',
            format='webp',
            quality='auto:good',
            overwrite=False,
            invalidate=True,
        )
    except Exception as exc:  # pragma: no cover - network dependent
        return {'ok': False, 'url': '', 'public_id': '', 'error': str(exc)}

    secure_url = result.get('secure_url') or result.get('url') or ''
    return {
        'ok': bool(secure_url),
        'url': secure_url,
        'public_id': result.get('public_id', ''),
        'bytes': result.get('bytes', 0),
        'width': result.get('width', 0),
        'height': result.get('height', 0),
        'error': '' if secure_url else 'Cloudinary returned no URL',
    }


def destroy(url_or_public_id: Optional[str]) -> Dict[str, Any]:
    """Delete one asset. Accepts a delivery URL or a raw public id."""
    if not url_or_public_id:
        return {'ok': False, 'error': 'Nothing to delete'}
    if not ensure_configured():
        return {'ok': False, 'error': 'Cloudinary is not configured'}

    public_id = url_or_public_id
    if is_delivery_url(url_or_public_id):
        public_id = public_id_from_url(url_or_public_id) or ''
    if not public_id:
        return {'ok': False, 'error': 'Could not read the public id'}

    try:
        result = cloudinary.uploader.destroy(public_id, invalidate=True)
    except Exception as exc:  # pragma: no cover - network dependent
        return {'ok': False, 'error': str(exc)}

    outcome = str(result.get('result', ''))
    return {
        'ok': outcome in ('ok', 'not found'),
        'result': outcome,
        'public_id': public_id,
        'error': '' if outcome in ('ok', 'not found') else outcome,
    }


# --------------------------------------------------------------------------- #
#  Diagnostics
# --------------------------------------------------------------------------- #
def ping() -> Dict[str, Any]:
    """Check credentials against the Cloudinary API.

    Used by the admin "Test connection" button, so the response is written
    for a human to read.
    """
    info = status()

    if not SDK_AVAILABLE:
        return {
            'ok': False,
            'title': 'Cloudinary library missing',
            'detail': 'Run "Run Pip Install" in cPanel so requirements.txt installs the cloudinary package.',
            'status': info,
        }

    missing = [name for name, present in (
        ('CLOUDINARY_CLOUD_NAME', bool(info['cloud_name'])),
        ('CLOUDINARY_API_KEY', info['api_key_set']),
        ('CLOUDINARY_API_SECRET', info['api_secret_set']),
    ) if not present]
    if missing:
        return {
            'ok': False,
            'title': 'Missing credentials',
            'detail': 'Add these environment variables in cPanel, then restart the app: ' + ', '.join(missing),
            'status': info,
        }

    ensure_configured()
    started = time.time()
    try:
        cloudinary.api.ping()
    except Exception as exc:  # pragma: no cover - network dependent
        message = str(exc)
        hint = 'Double-check the API key and secret were copied without extra spaces.'
        if 'Invalid Signature' in message or '401' in message:
            hint = 'The API secret does not match this cloud name.'
        elif 'Name or service not known' in message or 'timed out' in message.lower():
            hint = 'The server could not reach api.cloudinary.com - ask your host to allow outbound HTTPS.'
        return {
            'ok': False,
            'title': 'Cloudinary rejected the connection',
            'detail': message + ' - ' + hint,
            'status': info,
        }

    elapsed_ms = int((time.time() - started) * 1000)
    usage_line = ''
    try:
        usage = cloudinary.api.usage()
        credits = usage.get('credits') or {}
        used = credits.get('used_percent')
        if used is not None:
            usage_line = ' Plan usage: ' + str(used) + '% of monthly credits.'
        stored = (usage.get('storage') or {}).get('usage')
        if stored:
            usage_line += ' Stored: ' + str(round(float(stored) / (1024 * 1024), 1)) + ' MB.'
    except Exception:  # pragma: no cover - usage is a bonus, not a requirement
        usage_line = ''

    return {
        'ok': True,
        'title': 'Connected to cloud "' + info['cloud_name'] + '"',
        'detail': ('Handshake took ' + str(elapsed_ms) + ' ms. Uploads are saved to folder "'
                   + info['folder'] + '" as WEBP and served from the CDN.' + usage_line),
        'status': info,
    }
