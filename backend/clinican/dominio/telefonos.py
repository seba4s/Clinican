"""Celulares de propietarios: exactamente 10 dígitos (sin indicativo de país)."""

from __future__ import annotations

import re

from clinican.dominio.errores import DatoInvalido


def normalizar_celular(texto: str) -> str:
    """Quita espacios y guiones y exige exactamente 10 dígitos. Devuelve solo los dígitos."""
    if not isinstance(texto, str):
        raise DatoInvalido("El celular debe ser texto")
    limpio = re.sub(r"[\s\-]", "", texto)
    if not re.fullmatch(r"\d{10}", limpio):
        raise DatoInvalido(
            f"El celular debe tener exactamente 10 dígitos (se recibió {texto!r})"
        )
    return limpio
