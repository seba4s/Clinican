"""Validación de datos de propietarios."""

from __future__ import annotations

import re

from clinican.dominio.errores import DatoInvalido


def normalizar_cedula(cedula: str) -> str:
    """Quita puntos, espacios y guiones: "1.098.765.432" -> "1098765432".

    Se aceptan letras para documentos de extranjería o pasaporte.
    """
    limpia = re.sub(r"[\s.\-]", "", str(cedula or "")).upper()
    if not limpia:
        raise DatoInvalido("Escriba la cédula del propietario.")
    if not limpia.isalnum() or not (5 <= len(limpia) <= 15):
        raise DatoInvalido("La cédula debe tener entre 5 y 15 caracteres, solo números (o letras si es pasaporte).")
    return limpia


def normalizar_celular(celular: str, obligatorio: bool, etiqueta: str = "El celular") -> str | None:
    """Deja solo los números: "301 441-7194" -> "3014417194"."""
    texto = str(celular or "").strip()
    if texto.startswith("+57"):
        texto = texto[3:]
    digitos = re.sub(r"[\s\-().]", "", texto)
    if not digitos:
        if obligatorio:
            raise DatoInvalido(f"{etiqueta} es obligatorio.")
        return None
    if not digitos.isdigit() or not (7 <= len(digitos) <= 10):
        raise DatoInvalido(f"{etiqueta} debe tener entre 7 y 10 números.")
    return digitos


def formato_celular(digitos: str | None) -> str:
    """"3014417194" -> "301 441 7194"."""
    if not digitos:
        return ""
    if len(digitos) == 10:
        return f"{digitos[:3]} {digitos[3:6]} {digitos[6:]}"
    return digitos


def validar_propietario(nombre: str, cedula: str, celular1: str, celular2: str | None, direccion: str) -> dict:
    nombre = " ".join((nombre or "").split())
    direccion = " ".join((direccion or "").split())
    if not nombre:
        raise DatoInvalido("Escriba el nombre del propietario.")
    if not direccion:
        raise DatoInvalido("Escriba la dirección del propietario.")
    c1 = normalizar_celular(celular1, True, "El celular principal")
    c2 = normalizar_celular(celular2, False, "El segundo celular")
    return {
        "nombre": nombre,
        "cedula": normalizar_cedula(cedula),
        "celular1": c1,
        "celular2": c2 if c2 != c1 else None,
        "direccion": direccion,
    }
