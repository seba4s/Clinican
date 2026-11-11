"""Cédula del propietario y edad aproximada de la mascota."""

from __future__ import annotations

import re
from datetime import date

from clinican.dominio.errores import DatoInvalido


def normalizar_cedula(texto) -> str:
    """Quita espacios, puntos y guiones. Acepta de 4 a 20 letras o dígitos (en mayúscula)."""
    if isinstance(texto, bool) or texto is None:
        raise DatoInvalido("La cédula es obligatoria")
    if isinstance(texto, int):
        texto = str(texto)
    if not isinstance(texto, str):
        raise DatoInvalido("La cédula debe ser texto")
    limpio = re.sub(r"[\s.\-]", "", texto).upper()
    if not limpio:
        raise DatoInvalido("La cédula es obligatoria")
    if not re.fullmatch(r"[0-9A-Z]{4,20}", limpio):
        raise DatoInvalido(f"Cédula inválida: {texto!r}")
    return limpio


def fecha_nacimiento_aproximada(anios: int, meses: int, hoy: date) -> date:
    """Fecha de nacimiento estimada a partir de la edad en años y meses a ``hoy``."""
    for valor, nombre in ((anios, "años"), (meses, "meses")):
        if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
            raise DatoInvalido(f"La edad en {nombre} debe ser un entero >= 0")
    if meses > 11:
        raise DatoInvalido("La edad en meses debe estar entre 0 y 11")
    total = hoy.year * 12 + (hoy.month - 1) - (anios * 12 + meses)
    anio, mes = divmod(total, 12)
    mes += 1
    # Mismo día del mes, ajustado si ese mes es más corto
    for dia in (hoy.day, 30, 29, 28):
        try:
            return date(anio, mes, min(hoy.day, dia))
        except ValueError:
            continue
    raise AssertionError("inalcanzable")
