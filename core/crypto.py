import base64
import hashlib
from cryptography.fernet import Fernet

MASTER_SEED = b"job_mailer_master_secret_aes_key_production_2026_salt"

def _get_fernet() -> Fernet:
    """Generate a standard Fernet encryption engine derived via SHA-256."""
    key_32_bytes = hashlib.sha256(MASTER_SEED).digest()
    fernet_key = base64.urlsafe_b64encode(key_32_bytes)
    return Fernet(fernet_key)

def encrypt_secret(plain_text: str) -> str:
    """
    Encrypts sensitive data (SMTP app password, RapidAPI key) at rest.
    Stores only encrypted ciphertext in the database.
    """
    if not plain_text or not str(plain_text).strip():
        return ""
    if str(plain_text).startswith("enc::"):
        return plain_text  # Already encrypted
    fernet = _get_fernet()
    token = fernet.encrypt(plain_text.strip().encode('utf-8'))
    return "enc::" + token.decode('ascii')

def decrypt_secret(cipher_text: str) -> str:
    """
    Decrypts ciphertext in memory only when establishing SMTP connection or calling API.
    """
    if not cipher_text:
        return ""
    if not str(cipher_text).startswith("enc::"):
        return cipher_text.strip()
    try:
        raw_token = cipher_text.replace("enc::", "").encode('ascii')
        fernet = _get_fernet()
        decrypted = fernet.decrypt(raw_token)
        return decrypted.decode('utf-8')
    except Exception:
        return ""
