"""Precios en pesos enteros: valores iniciales, historial con vigencia y formato.

``PRECIOS_INICIALES`` no tiene fecha de vigencia: se usa al sembrar la base.
Desde ahí, el precio de cada fecha sale del historial.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from types import MappingProxyType
from typing import Hashable, Iterable, Mapping

from clinican.dominio.abonos import validar_pesos
from clinican.dominio.cupos import CategoriaCupo

# Fecha con la que se siembran los precios iniciales: "desde siempre", para que
# cualquier turno (incluso de fechas pasadas) tenga un precio vigente.
FECHA_PRECIOS_INICIALES = date(2000, 1, 1)

PRECIOS_INICIALES: Mapping[CategoriaCupo, int] = MappingProxyType(
    {
        CategoriaCupo.MAQUINA: 45000,
        CategoriaCupo.GRANDE: 70000,
        CategoriaCupo.TIJERA: 50000,
        CategoriaCupo.COMPLICADO: 50000,
    }
)


def formatear_pesos(valor: int) -> str:
    """Formatea pesos enteros con punto de miles: 45000 -> "$45.000"."""
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise TypeError(f"valor debe ser un entero de pesos, no {type(valor).__name__}")
    signo = "-" if valor < 0 else ""
    return f"{signo}${abs(valor):,}".replace(",", ".")


class SinPrecioVigente(LookupError):
    """No hay precio registrado para esa clave en esa fecha."""


class PrecioDuplicado(ValueError):
    """Dos precios para la misma clave con la misma fecha de vigencia."""


@dataclass(frozen=True)
class PrecioHistorico:
    """Precio de ``clave`` (un Servicio o una CategoriaCupo) desde ``vigente_desde``."""

    vigente_desde: date
    clave: Hashable
    valor: int

    def __post_init__(self) -> None:
        validar_pesos(self.valor, "valor")
        if not isinstance(self.vigente_desde, date):
            raise TypeError("vigente_desde debe ser una fecha")


def _nombre(clave: Hashable) -> str:
    return clave.name if isinstance(clave, Enum) else str(clave)


def precio_vigente(historial: Iterable[PrecioHistorico], fecha: date, clave: Hashable) -> int:
    """Último precio de ``clave`` con ``vigente_desde <= fecha``."""
    candidatos = [p for p in historial if p.clave == clave and p.vigente_desde <= fecha]
    if not candidatos:
        raise SinPrecioVigente(
            f"No hay precio para {_nombre(clave)} vigente al {fecha.isoformat()}"
        )
    ultimo = max(candidatos, key=lambda p: p.vigente_desde)
    empatados = [p for p in candidatos if p.vigente_desde == ultimo.vigente_desde]
    if len(empatados) > 1:
        raise PrecioDuplicado(
            f"Hay {len(empatados)} precios para {_nombre(clave)} desde "
            f"{ultimo.vigente_desde.isoformat()}"
        )
    return ultimo.valor
