"""Reglas de consentimientos (RN-15)."""

from __future__ import annotations

from clinican.dominio.catalogos import CONDICIONES, TIPOS_LEGALES
from clinican.dominio.errores import DatoInvalido

# Aceptaciones que deben existir antes de crear un turno.
REQUERIDOS_PARA_TURNO = ("TERMINOS", "DATOS")


def faltantes_para_turno(textos_aceptados_vigentes: set[str]) -> list[str]:
    """Devuelve los tipos que faltan (con versión vigente) para agendar."""
    return [t for t in REQUERIDOS_PARA_TURNO if t not in textos_aceptados_vigentes]


def mensaje_faltantes(faltan: list[str]) -> str:
    nombres = " y ".join(TIPOS_LEGALES[t].lower() for t in faltan)
    return (
        f"No se puede agendar: el propietario debe aceptar primero {nombres} (versión vigente). "
        "Regístrelo en Propietarios › Consentimientos."
    )


def validar_condiciones(condiciones: dict[str, bool]) -> dict[str, bool]:
    desconocidas = set(condiciones) - set(CONDICIONES)
    if desconocidas:
        raise DatoInvalido(f"Condiciones desconocidas: {', '.join(sorted(desconocidas))}.")
    return {c: bool(condiciones.get(c, False)) for c in CONDICIONES}


def validar_texto_legal(tipo: str, contenido: str) -> str:
    if tipo not in TIPOS_LEGALES:
        raise DatoInvalido("Tipo de texto legal desconocido.")
    contenido = (contenido or "").strip()
    if len(contenido) < 20:
        raise DatoInvalido("El texto legal está vacío o es demasiado corto.")
    return contenido
