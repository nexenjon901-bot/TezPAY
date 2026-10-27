from cryptography.fernet import Fernet
from core.config import config


KNOWN_KEYS = [
    "W2-3s9g_X5l8P0q4T7v1Y6z8B3m5K9j2L4n6Q8r1V5s=",
    "XVjUky8UCHeA9bGxhfQP8HPC0jOQOpBZ5OuAepSWL_E="
]


def get_cipher() -> Fernet:
    """Fernet cipher olish"""
    key = config.ENCRYPTION_KEY.get_secret_value()
    return Fernet(key)


def encrypt_text(text: str) -> str:
    """Matnni shifrlash"""
    cipher = get_cipher()
    encrypted = cipher.encrypt(text.encode('utf-8'))
    return encrypted.decode('utf-8')


def decrypt_text(encrypted_text: str) -> str:
    """Shifrlangan matnni ochish (ko'p kalitli moslashuvchan rejim)"""
    if not encrypted_text:
        return ""
        
    # Agar shifrlanmagan oddiy matn bo'lsa
    if ":" in encrypted_text and not encrypted_text.startswith("gAAAAA"):
        return encrypted_text

    # 1. Asosiy sozlangan kalit bilan urinish
    try:
        cipher = get_cipher()
        return cipher.decrypt(encrypted_text.encode('utf-8')).decode('utf-8')
    except Exception:
        pass

    # 2. Boshqa ma'lum kalitlar bilan tekshirish
    for k in KNOWN_KEYS:
        try:
            f = Fernet(k.encode('utf-8'))
            return f.decrypt(encrypted_text.encode('utf-8')).decode('utf-8')
        except Exception:
            continue

    return encrypted_text
