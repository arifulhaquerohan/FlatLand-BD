import os
import hmac
import hashlib
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, '.env'), override=False)

# Contact details are encrypted at rest. A stable, private key is mandatory:
# silently falling back to a built-in value would make that protection useless.
_secret = (os.getenv('DATA_ENCRYPTION_KEY') or '').strip()
if len(_secret) < 32 or _secret.lower() in {'change-me', 'replace-me'}:
    raise RuntimeError(
        'DATA_ENCRYPTION_KEY must be set to a unique random value of at least 32 characters.'
    )

# Derive the exact 32 bytes required by AES-256 without truncating entropy.
ENCRYPTION_KEY = hashlib.sha256(_secret.encode('utf-8')).digest()

def generate_blind_index(data: str) -> str:
    """Generate a deterministic HMAC-SHA256 blind index for querying encrypted fields."""
    if not data:
        return ""
    # We use the same key for the HMAC, or ideally a separate one. We'll use the same for simplicity.
    return hmac.new(ENCRYPTION_KEY, data.encode('utf-8'), hashlib.sha256).hexdigest()

def encrypt_data(data: str) -> str:
    """Encrypt a string using AES-256 GCM."""
    if not data:
        return ""
    aesgcm = AESGCM(ENCRYPTION_KEY)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, data.encode('utf-8'), None)
    return base64.b64encode(nonce + ct).decode('utf-8')

def decrypt_data(encrypted_data: str) -> str:
    """Decrypt an AES-256 GCM encrypted string."""
    if not encrypted_data:
        return ""
    try:
        raw = base64.b64decode(encrypted_data)
        nonce = raw[:12]
        ct = raw[12:]
        aesgcm = AESGCM(ENCRYPTION_KEY)
        return aesgcm.decrypt(nonce, ct, None).decode('utf-8')
    except Exception as e:
        print(f"Decryption error: {e}")
        return ""
