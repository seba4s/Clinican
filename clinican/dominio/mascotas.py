"""Reglas de mascotas: tamaño y pelaje efectivos, validación de datos."""

from __future__ import annotations

from datetime import date

from clinican.dominio.catalogos import SEXOS, TAMANOS
from clinican.dominio.errores import DatoInvalido

EDAD_MAX_ANIOS = 30


def tamano_efectivo(tamano_raza: str | None, tamano_manual: str | None) -> str:
    """El tamaño propio de la mascota prevalece sobre el de la raza (5.1)."""
    tamano = tamano_manual or tamano_raza
    if tamano not in TAMANOS:
        raise DatoInvalido(
            "Esta raza no tiene un tamaño definido (por ejemplo, perro mestizo). "
            "Elija el tamaño de la mascota: pequeña, mediana o grande."
        )
    return tamano


def pelaje_complicado_efectivo(pelaje_raza: int | bool, pelaje_manual: int | bool | None) -> bool:
    """La marca propia de la mascota prevalece sobre la de la raza (5.1)."""
    if pelaje_manual is None:
        return bool(pelaje_raza)
    return bool(pelaje_manual)


def validar_mascota(
    nombre: str,
    tamano_raza: str | None,
    tamano_manual: str | None,
    pelaje_manual: int | None,
    edad_anios: int | None,
    edad_meses: int | None,
    fecha_ultima_visita: str | None,
    sexo: str | None = None,
) -> dict:
    """Valida y normaliza. Devuelve los campos listos para guardar."""
    nombre = " ".join((nombre or "").split())
    if not nombre:
        raise DatoInvalido("Escriba el nombre de la mascota.")
    if tamano_manual is not None and tamano_manual not in TAMANOS:
        raise DatoInvalido("El tamaño debe ser pequeña, mediana o grande.")
    tamano_efectivo(tamano_raza, tamano_manual)
    if tamano_raza is None and pelaje_manual is None:
        raise DatoInvalido("Para esta raza indique si la mascota tiene pelaje complicado (sí o no).")
    if pelaje_manual not in (None, 0, 1):
        raise DatoInvalido("Pelaje complicado debe ser sí o no.")
    if edad_anios is not None and not (0 <= edad_anios <= EDAD_MAX_ANIOS):
        raise DatoInvalido(f"La edad en años debe estar entre 0 y {EDAD_MAX_ANIOS}.")
    if edad_meses is not None and not (0 <= edad_meses <= 11):
        raise DatoInvalido("Los meses de edad deben estar entre 0 y 11.")
    if sexo is not None and sexo not in SEXOS:
        raise DatoInvalido("El sexo debe ser hembra o macho.")
    fecha = validar_fecha(fecha_ultima_visita, "La fecha de última visita") if fecha_ultima_visita else None
    if fecha and fecha > date.today().isoformat():
        raise DatoInvalido("La fecha de última visita no puede ser futura.")
    return {
        "nombre": nombre,
        "tamano_manual": tamano_manual,
        "pelaje_complicado_manual": pelaje_manual,
        "edad_anios": edad_anios,
        "edad_meses": edad_meses or 0,
        "fecha_ultima_visita": fecha,
        "sexo": sexo,
    }


def validar_fecha(texto: str, etiqueta: str = "La fecha") -> str:
    """Acepta AAAA-MM-DD o DD/MM/AAAA. Devuelve AAAA-MM-DD."""
    texto = (texto or "").strip()
    try:
        if "/" in texto:
            d, m, a = texto.split("/")
            return date(int(a), int(m), int(d)).isoformat()
        return date.fromisoformat(texto).isoformat()
    except ValueError:
        raise DatoInvalido(f"{etiqueta} no es válida. Use el formato AAAA-MM-DD, por ejemplo 2026-03-26.") from None


def entero_opcional(texto, etiqueta: str) -> int | None:
    if texto is None or str(texto).strip() == "":
        return None
    try:
        valor = float(str(texto).strip().replace(",", "."))
    except ValueError:
        raise DatoInvalido(f"{etiqueta} debe ser un número.") from None
    if valor != int(valor):
        raise DatoInvalido(f"{etiqueta} debe ser un número entero.")
    return int(valor)
