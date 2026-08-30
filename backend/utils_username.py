"""Username rules for FlatLand BD.

One username per customer, permanently reserved. Kept in a single module so the
registration form, the live availability check and the admin tools all agree on
what a valid, free username looks like.
"""

import re
import unicodedata

USERNAME_MIN = 3
USERNAME_MAX = 20
USERNAME_RE = re.compile(r'^[a-z0-9_]{%d,%d}$' % (USERNAME_MIN, USERNAME_MAX))

# Names nobody may register: routes, roles and impersonation risks.
RESERVED_USERNAMES = {
    'admin', 'administrator', 'root', 'superuser', 'sysadmin', 'moderator', 'mod',
    'staff', 'team', 'support', 'help', 'helpdesk', 'contact', 'info', 'office',
    'flatland', 'flatlandbd', 'flatland_bd', 'official', 'verified', 'owner',
    'console', 'dashboard', 'panel', 'settings', 'account', 'accounts', 'profile',
    'login', 'logout', 'signin', 'signup', 'register', 'auth', 'password', 'reset',
    'api', 'static', 'assets', 'media', 'uploads', 'images', 'img', 'css', 'js',
    'flat', 'flats', 'interior', 'interiors', 'studio', 'studios', 'listing',
    'listings', 'post', 'search', 'sitemap', 'robots', 'preview', 'system',
    'null', 'none', 'undefined', 'test', 'demo', 'guest', 'anonymous', 'user',
    'me', 'you', 'new', 'edit', 'delete', 'about', 'terms', 'privacy', 'legal',
}


def normalize_username(value):
    """Lowercase, strip accents, keep only a-z 0-9 and underscore."""
    if not value:
        return ''
    text = unicodedata.normalize('NFKD', str(value))
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = text.strip().lower()
    text = re.sub(r'[\s.\-]+', '_', text)
    text = re.sub(r'[^a-z0-9_]', '', text)
    text = re.sub(r'_{2,}', '_', text).strip('_')
    return text[:USERNAME_MAX]


def validate_username(value):
    """Return (ok, cleaned_or_error_message)."""
    cleaned = normalize_username(value)
    if not cleaned:
        return False, 'Please choose a username.'
    if len(cleaned) < USERNAME_MIN:
        return False, 'Username must be at least %d characters.' % USERNAME_MIN
    if len(cleaned) > USERNAME_MAX:
        return False, 'Username must be %d characters or fewer.' % USERNAME_MAX
    if not USERNAME_RE.match(cleaned):
        return False, 'Use only lowercase letters, numbers and underscore.'
    if cleaned[0].isdigit():
        return False, 'Username must start with a letter.'
    if cleaned in RESERVED_USERNAMES:
        return False, 'That username is reserved. Please pick another.'
    return True, cleaned


def is_username_taken(cleaned):
    """True when another account already holds this username."""
    from .models import User
    if not cleaned:
        return False
    return User.query.filter(User.username == cleaned).first() is not None


def suggest_usernames(seed, limit=3):
    """A few free alternatives built from the name the visitor typed."""
    base = normalize_username(seed) or 'member'
    if base[0].isdigit():
        base = 'bd_' + base
    base = base[:USERNAME_MAX - 3]
    out = []
    for suffix in ('', '_bd', '_dhaka'):
        candidate = (base + suffix)[:USERNAME_MAX]
        ok, cleaned = validate_username(candidate)
        if ok and not is_username_taken(cleaned) and cleaned not in out:
            out.append(cleaned)
        if len(out) >= limit:
            return out
    number = 1
    while len(out) < limit and number < 500:
        candidate = ('%s%d' % (base, number))[:USERNAME_MAX]
        ok, cleaned = validate_username(candidate)
        if ok and not is_username_taken(cleaned) and cleaned not in out:
            out.append(cleaned)
        number += 1
    return out


def allocate_username(seed):
    """Always return a free username - used for backfill and admin bootstrap."""
    ok, cleaned = validate_username(seed)
    if ok and not is_username_taken(cleaned):
        return cleaned
    options = suggest_usernames(seed, limit=1)
    return options[0] if options else None
