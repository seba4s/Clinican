"""PIN de acceso: validación y hash con PBKDF2 y sal propia por persona."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from clinican.dominio.errores import DatoInvalido

ITERACIONES = 200_000
LARGO_MIN_PIN = 4
LARGO_MAX_PIN = 6


def validar_pin(pin: str) -> str:
    pin = (pin or "").strip()
    if not pin.isdigit() or not (LARGO_MIN_PIN <= len(pin) <= LARGO_MAX_PIN):
        raise DatoInvalido(
            f"El PIN debe tener entre {LARGO_MIN_PIN} y {LARGO_MAX_PIN} números, sin letras ni espacios."
        )
    return pin


def generar_hash(pin: str, sal: str | None = None) -> tuple[str, str]:
    """Devuelve ``(hash_hex, sal_hex)``."""
    pin = validar_pin(pin)
    sal = sal or secrets.token_hex(16)
    derivado = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(sal), ITERACIONES)
    return derivado.hex(), sal


def verificar_pin(pin: str, hash_hex: str, sal_hex: str) -> bool:
    try:
        calculado, _ = generar_hash(pin, sal_hex)
    except DatoInvalido:
        return False
    return hmac.compare_digest(calculado, hash_hex)
