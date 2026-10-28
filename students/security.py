"""Aadhaar number protection.

* The full number is stored only encrypted (Fernet / AES-128-CBC + HMAC).
* A keyed hash allows duplicate detection without decrypting anything.
* Only the last four digits are ever displayed.
"""
import base64
import hashlib
import hmac
import re

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ValidationError

# Verhoeff tables (the check-digit scheme used by Aadhaar).
_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6], [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4], [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2], [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def verhoeff_valid(number: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(number)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def normalise_aadhaar(value: str) -> str:
    return re.sub(r"[\s-]", "", value or "")


def validate_aadhaar(value: str) -> str:
    number = normalise_aadhaar(value)
    if not re.fullmatch(r"[2-9]\d{11}", number):
        raise ValidationError("Enter a valid 12-digit Aadhaar number (it cannot start with 0 or 1).")
    if getattr(settings, "AADHAAR_VERIFY_CHECKSUM", True) and not verhoeff_valid(number):
        raise ValidationError("This Aadhaar number is not valid (check digit does not match). Please re-check it.")
    return number


def _key_material() -> bytes:
    secret = getattr(settings, "AADHAAR_ENCRYPTION_KEY", "") or settings.SECRET_KEY
    return hashlib.sha256(("aadhaar-key:" + secret).encode()).digest()


def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(_key_material()))


def encrypt_aadhaar(number: str) -> str:
    return _fernet().encrypt(number.encode()).decode()


def decrypt_aadhaar(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return ""


def hash_aadhaar(number: str) -> str:
    return hmac.new(_key_material(), number.encode(), hashlib.sha256).hexdigest()


def mask_aadhaar(last4: str) -> str:
    return f"XXXX XXXX {last4}" if last4 else "-"
