"""Autorización de tratamiento de datos personales (Ley 1581 de 2012).

Cada propietario tiene un historial de registros: otorgar o revocar, con la
fecha en que el titular lo hizo. Nada se borra; vale el último registro.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from clinican.dominio.errores import DatoInvalido

LEY = "Ley 1581 de 2012"


@dataclass(frozen=True)
class AutorizacionDatos:
    id: int
    propietario_id: int
    otorgada: bool
    fecha: date
    medio: str
    registrada_en: datetime


def validar_fecha(fecha: date, hoy: date) -> date:
    """La fecha en que el titular autorizó o revocó: una fecha real, nunca futura."""
    if isinstance(fecha, datetime) or not isinstance(fecha, date):
        raise DatoInvalido("La fecha de la autorización debe ser una fecha (día, mes y año)")
    if fecha > hoy:
        raise DatoInvalido("La fecha de la autorización no puede ser posterior a hoy")
    return fecha


def vigente(registros: Iterable[AutorizacionDatos]) -> AutorizacionDatos | None:
    """El último registro si es una autorización otorgada; None si no hay o fue revocada."""
    ultimo = max(registros, key=lambda r: (r.registrada_en, r.id), default=None)
    if ultimo is None or not ultimo.otorgada:
        return None
    return ultimo
