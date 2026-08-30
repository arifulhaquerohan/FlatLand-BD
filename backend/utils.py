import os
import time
import re
import json
from io import BytesIO
from urllib.parse import urlparse, parse_qs
from functools import wraps
from flask import request, redirect, url_for, abort, current_app
from flask_login import current_user
from werkzeug.utils import secure_filename
from .models import db, Flat, InteriorService, Lead, FlatImage, InteriorImage, MediaAsset
from . import cloudinary_service

YOUTUBE_ID_RE = re.compile(r'^[a-zA-Z0-9_-]{11}$')
LISTING_STATUSES = {'pending', 'approved', 'rejected'}
LEAD_STATUSES = {'new', 'contacted', 'closed'}
NOCOOKIE_EMBED_BASE = 'https://www.youtube-nocookie.com/embed/'
SHORT_WATCH_BASE = 'https://youtu.be/'
CLOUDINARY_DELIVERY_RE = re.compile(r'^(https?:)?//res\.cloudinary\.com/[^/]+/(image|video)/upload/')

def is_allowed_image(filename):
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in current_app.config['ALLOWED_IMAGE_EXTENSIONS']

def get_image_type(header):
    if header.startswith(b'\xff\xd8\xff'):
        return 'jpeg'
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if header.startswith(b'RIFF') and header[8:12] == b'WEBP':
        return 'webp'
    return None

def is_cloudinary_configured():
    """True when the Cloudinary SDK is installed and credentials are present."""
    return cloudinary_service.configured()

def upload_image_to_cloudinary(img, original_filename):
    """Encode a PIL image as WEBP and push it to Cloudinary.

    Returns the secure delivery URL, or None so the caller can fall back to
    local storage. Never raises.
    """
    buffer = BytesIO()
    try:
        img.save(buffer, 'WEBP', quality=82, method=5)
    except Exception:
        img.save(buffer, 'WEBP', quality=82)
    buffer.seek(0)

    result = cloudinary_service.upload_stream(buffer, original_filename or 'image')
    if result.get('ok'):
        return result.get('url')

    current_app.logger.warning('Cloudinary upload failed: %s', result.get('error'))
    return None

def is_cloudinary_delivery_url(url):
    return bool(url and CLOUDINARY_DELIVERY_RE.match(str(url)))

def cloudinary_image_url(url, width=None, height=None, crop='fill', quality='auto', fetch_format='auto'):
    if not url:
        return ''
    return cloudinary_service.build_url(
        str(url), width=width or 0, height=height, crop=crop,
        quality=quality, fetch_format=fetch_format,
    )

def cloudinary_srcset(url, widths=(420, 640, 900, 1200, 1600), crop='fill', quality='auto', fetch_format='auto'):
    if not url or not is_cloudinary_delivery_url(url):
        return ''

    return ', '.join(
        f"{cloudinary_image_url(url, width=width, crop=crop, quality=quality, fetch_format=fetch_format)} {width}w"
        for width in widths
    )

def optimized_image_url(url, width=900, height=None, crop='fill'):
    return cloudinary_image_url(url, width=width, height=height, crop=crop)

def optimized_image_srcset(url, widths=(420, 640, 900, 1200, 1600), crop='fill'):
    return cloudinary_srcset(url, widths=widths, crop=crop)

def save_uploaded_image(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    if not is_allowed_image(file_storage.filename):
        return None
    if file_storage.mimetype and not file_storage.mimetype.startswith('image/'):
        return None
    
    try:
        from PIL import Image, ImageOps
        img = Image.open(file_storage.stream)
        img = ImageOps.exif_transpose(img)
        
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
            
        max_size = 1600
        if max(img.size) > max_size:
            scale = max_size / float(max(img.size))
            new_size = (int(img.size[0] * scale), int(img.size[1] * scale))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        if is_cloudinary_configured():
            uploaded_url = upload_image_to_cloudinary(img, file_storage.filename)
            if uploaded_url:
                track_media_asset(uploaded_url, 'cloudinary')
                return uploaded_url
            
        upload_dir = os.path.join(current_app.static_folder, 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        
        safe_name = secure_filename(file_storage.filename)
        timestamp = int(time.time() * 1000)
        name_root, _ = os.path.splitext(safe_name)
        filename = f"{timestamp}_{name_root}.webp"
        file_path = os.path.join(upload_dir, filename)
        
        img.save(file_path, 'WEBP', quality=80, optimize=True)
        local_url = url_for('static', filename=f'uploads/{filename}')
        track_media_asset(local_url, 'local', file_path)
        return local_url
        
    except Exception as e:
        print(f"Error optimizing image: {e}")
        try:
            file_storage.stream.seek(0)
            upload_dir = os.path.join(current_app.static_folder, 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            safe_name = secure_filename(file_storage.filename)
            timestamp = int(time.time() * 1000)
            filename = f"{timestamp}_{safe_name}"
            file_storage.save(os.path.join(upload_dir, filename))
            return url_for('static', filename=f'uploads/{filename}')
        except:
            return None

def parse_image_urls(raw_text):
    if not raw_text:
        return []
    parts = re.split(r'[,\n\r]+', raw_text)
    return [part.strip() for part in parts if part.strip()]

def collect_uploaded_images(files):
    urls = []
    invalid = False
    for file_storage in files:
        if not file_storage or not file_storage.filename:
            continue
        uploaded = save_uploaded_image(file_storage)
        if uploaded:
            urls.append(uploaded)
        else:
            invalid = True
    return urls, invalid

def coerce_float(value, fallback=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback

def coerce_int(value, fallback=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback

def summarize_text(text, limit=155):
    if not text:
        return None
    compact = ' '.join(str(text).split())
    if len(compact) <= limit:
        return compact
    return compact[:limit].rstrip()

def extract_youtube_id(url):
    if not url:
        return None
    trimmed = str(url).strip()
    if not trimmed:
        return None
    if YOUTUBE_ID_RE.match(trimmed):
        return trimmed
    try:
        parsed = urlparse(trimmed)
    except ValueError:
        return None
    host = (parsed.netloc or '').lower()
    path = parsed.path or ''
    if host in {'youtu.be', 'www.youtu.be'}:
        candidate = path.lstrip('/').split('/')[0]
        return candidate if YOUTUBE_ID_RE.match(candidate) else None
    if host.endswith('youtube.com') or host.endswith('youtube-nocookie.com'):
        if path == '/watch':
            query = parse_qs(parsed.query or '')
            candidate = query.get('v', [''])[0]
            return candidate if YOUTUBE_ID_RE.match(candidate) else None
        parts = [part for part in path.split('/') if part]
        if len(parts) >= 2 and parts[0] in {'embed', 'shorts', 'v'}:
            candidate = parts[1]
            return candidate if YOUTUBE_ID_RE.match(candidate) else None
    return None

def build_youtube_embed(url):
    video_id = extract_youtube_id(url)
    if not video_id:
        return None
    return NOCOOKIE_EMBED_BASE + video_id + "?rel=0&modestbranding=1&playsinline=1&color=white"

def build_youtube_watch(url):
    video_id = extract_youtube_id(url)
    if not video_id:
        return None
    return SHORT_WATCH_BASE + video_id

_STATS_CACHE = {}
_redis_client = None
_redis_checked = False

def get_redis_client():
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True
    redis_url = os.getenv('REDIS_URL')
    if not redis_url:
        return None
    try:
        from redis import Redis
        client = Redis.from_url(redis_url, decode_responses=True)
        client.ping()
        _redis_client = client
    except Exception:
        _redis_client = None
    return _redis_client

def build_cache_key(key):
    prefix = os.getenv('CACHE_KEY_PREFIX', 'flatlandbd')
    return f'{prefix}:{key}'

def build_status_counts(model):
    from sqlalchemy import func
    rows = db.session.query(model.status, func.count(model.id)).group_by(model.status).all()
    counts = {status: total for status, total in rows}
    counts['total'] = sum(counts.values())
    return counts

def collect_admin_stats():
    flat_counts = build_status_counts(Flat)
    service_counts = build_status_counts(InteriorService)
    lead_counts = build_status_counts(Lead)
    return {
        'total_flats': flat_counts.get('total', 0),
        'pending_flats': flat_counts.get('pending', 0),
        'approved_flats': flat_counts.get('approved', 0),
        'rejected_flats': flat_counts.get('rejected', 0),
        'total_services': service_counts.get('total', 0),
        'pending_services': service_counts.get('pending', 0),
        'approved_services': service_counts.get('approved', 0),
        'rejected_services': service_counts.get('rejected', 0),
        'total_leads': lead_counts.get('total', 0),
        'new_leads': lead_counts.get('new', 0),
    }

def paginate_query(query, page, per_page):
    page = max(page, 1)
    offset = (page - 1) * per_page
    items = query.offset(offset).limit(per_page + 1).all()
    has_next = len(items) > per_page
    return items[:per_page], page > 1, has_next

def get_cached_value(key, ttl_seconds, factory):
    cache_key = build_cache_key(key)
    redis_client = get_redis_client()
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached is not None:
                return json.loads(cached)
        except Exception:
            pass

    now = time.monotonic()
    cached = _STATS_CACHE.get(key)
    if cached and cached['expires_at'] > now:
        return cached['value']
    value = factory()
    _STATS_CACHE[key] = {'value': value, 'expires_at': now + ttl_seconds}
    if redis_client:
        try:
            redis_client.setex(cache_key, ttl_seconds, json.dumps(value))
        except (TypeError, ValueError):
            pass
        except Exception:
            pass
    return value

def safe_next_path():
    path = request.full_path if request.query_string else request.path
    if not path:
        return '/'
    if path.endswith('?'):
        path = path[:-1]
    if '://' in path or path.startswith('//') or '..' in path:
        return '/'
    if not path.startswith('/'):
        return f'/{path}'
    return path

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('public.login', next=safe_next_path()))
        if current_user.role != 'admin':
            abort(404)
        return f(*args, **kwargs)
    return decorated_function

def normalize_preview_path(raw_path):
    if not raw_path:
        return '/'
    path = raw_path.strip()
    if not path:
        return '/'
    if '://' in path or path.startswith('//') or '..' in path:
        return '/'
    if not path.startswith('/'):
        path = f'/{path}'
    if path.startswith('/preview'):
        return '/'
    return path

def get_listing_item(item_type, item_id):
    if item_type == 'flat':
        return Flat.query.get_or_404(item_id)
    if item_type == 'interior':
        return InteriorService.query.get_or_404(item_id)
    abort(404)

def normalize_status(status):
    if not status:
        return None
    status = status.strip().lower()
    if status in LISTING_STATUSES:
        return status
    return None

def normalize_lead_status(status):
    if not status:
        return None
    status = status.strip().lower()
    if status in LEAD_STATUSES:
        return status
    return None

def generate_listing_description(raw_notes):
    """
    Simulates calling an LLM (like OpenAI or Gemini) to generate a professional listing.
    When you have your API key, replace this placeholder logic with the actual API call.
    """
    
    # Example OpenAI Integration:
    # import openai
    # openai.api_key = os.getenv("OPENAI_API_KEY")
    # response = openai.chat.completions.create(
    #     model="gpt-4o-mini",
    #     messages=[
    #         {"role": "system", "content": "You are an expert real estate copywriter. Turn the following raw notes into a beautiful, premium property listing description. Use formatting."},
    #         {"role": "user", "content": raw_notes}
    #     ]
    # )
    # return response.choices[0].message.content
    
    # No artificial delay: this runs synchronously in the request thread and
    # a sleep here would block a worker for every call.
    notes = raw_notes.strip() if raw_notes else "this property"
    
    return f"**Premium Opportunity in a Prime Location**\n\nWelcome to a beautifully designed space that perfectly blends modern elegance with everyday comfort. Based on your notes ({notes}), this property offers an exceptional lifestyle opportunity.\n\n**Key Features:**\n* Expansive, sunlit living areas with premium flooring.\n* Modern kitchen equipped with high-end fixtures.\n* Thoughtfully designed layout maximizing both space and privacy.\n\nThis property is ideal for those seeking a premium living experience with immediate access to top-tier amenities. Contact us today to schedule a private viewing.\n"


# --------------------------------------------------------------------------- #
#  Media bookkeeping
# --------------------------------------------------------------------------- #
def media_provider_for_url(url):
    """Where is this image actually hosted?"""
    if not url:
        return 'none'
    if cloudinary_service.is_delivery_url(url):
        return 'cloudinary'
    if '/static/uploads/' in str(url):
        return 'local'
    return 'external'


def track_media_asset(url, provider=None, storage_key=None):
    """Record an uploaded file so it can be cleaned up later.

    Safe to call repeatedly - the URL column is unique.
    """
    if not url:
        return None
    provider = provider or media_provider_for_url(url)
    if provider == 'cloudinary' and not storage_key:
        storage_key = cloudinary_service.public_id_from_url(url) or ''
    try:
        existing = MediaAsset.query.filter_by(image_url=url).first()
        if existing:
            return existing
        asset = MediaAsset(image_url=url, storage_provider=provider, storage_key=storage_key or '')
        db.session.add(asset)
        db.session.flush()
        return asset
    except Exception as exc:
        current_app.logger.warning('Could not track media asset: %s', exc)
        return None


def delete_media_url(url):
    """Remove one stored image from Cloudinary or local disk.

    External/hotlinked URLs are left alone. Returns True when something was
    actually removed.
    """
    if not url:
        return False
    provider = media_provider_for_url(url)
    removed = False

    if provider == 'cloudinary':
        outcome = cloudinary_service.destroy(url)
        removed = bool(outcome.get('ok'))
        if not removed:
            current_app.logger.warning('Cloudinary delete failed: %s', outcome.get('error'))
    elif provider == 'local':
        try:
            relative = str(url).split('/static/', 1)[1]
            path = os.path.join(current_app.static_folder, relative.replace('/', os.sep))
            root = os.path.realpath(current_app.static_folder)
            target = os.path.realpath(path)
            if target.startswith(root) and os.path.isfile(target):
                os.remove(target)
                removed = True
        except Exception as exc:
            current_app.logger.warning('Local delete failed: %s', exc)

    try:
        MediaAsset.query.filter_by(image_url=url).delete(synchronize_session=False)
    except Exception:
        pass
    return removed


def collect_listing_image_urls(item):
    """Every image URL attached to a flat or interior service."""
    urls = []
    if getattr(item, 'image_url', None):
        urls.append(item.image_url)
    for image in list(getattr(item, 'images', []) or []):
        if image.image_url:
            urls.append(image.image_url)
    seen, unique = set(), []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def delete_listing_media(item):
    """Delete the stored files for a listing before the row disappears."""
    removed = 0
    for url in collect_listing_image_urls(item):
        if delete_media_url(url):
            removed += 1
    return removed


def delete_media_for_urls(urls):
    removed = 0
    for url in urls or []:
        if delete_media_url(url):
            removed += 1
    return removed
