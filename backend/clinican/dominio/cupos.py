"""Categorías de cupo y capacidad por franja de 30 minutos."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class Tamano(Enum):
    MINI = "mini"
    PEQUENO = "pequeno"
    MEDIANO = "mediano"
    GRANDE = "grande"


class Servicio(Enum):
    """Servicios de peluquería.

    Lista PROVISIONAL: se ajustará cuando se defina el catálogo definitivo.
    """

    CORTE_MAQUINA = "corte_maquina"
    CORTE_TIJERA = "corte_tijera"
    BANO = "bano"
    DESENREDADO = "desenredado"


class CategoriaCupo(Enum):
    MAQUINA = "maquina"
    GRANDE = "grande"
    TIJERA = "tijera"
    COMPLICADO = "complicado"


def categoria_de_cupo(
    raza: str | None,
    tamano: Tamano,
    pelaje: str | None,
    servicio: Servicio,
    complicado: bool,
) -> CategoriaCupo:
    """Clasifica el turno en una categoría de cupo.

    Prioridad: COMPLICADO (mascota marcada como complicada) > GRANDE (tamaño
    grande) > TIJERA (corte a tijera) > MAQUINA. ``raza`` y ``pelaje`` se reciben
    para registro, pero hoy no cambian la categoría.
    """
    if not isinstance(tamano, Tamano):
        raise TypeError(f"tamano debe ser Tamano, no {type(tamano).__name__}")
    if not isinstance(servicio, Servicio):
        raise TypeError(f"servicio debe ser Servicio, no {type(servicio).__name__}")
    if complicado:
        return CategoriaCupo.COMPLICADO
    if tamano is Tamano.GRANDE:
        return CategoriaCupo.GRANDE
    if servicio is Servicio.CORTE_TIJERA:
        return CategoriaCupo.TIJERA
    return CategoriaCupo.MAQUINA


@dataclass(frozen=True)
class CuposPorFranja:
    """Capacidad máxima de turnos por categoría en una misma franja."""

    maquina: int = 2
    grande: int = 1
    tijera: int = 1
    complicado: int = 1

    def __post_init__(self) -> None:
        for categoria in CategoriaCupo:
            valor = getattr(self, categoria.value)
            if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
                raise ValueError(f"El cupo de {categoria.value} debe ser un entero >= 0")

    def capacidad(self, categoria: CategoriaCupo) -> int:
        return getattr(self, categoria.value)


def cupos_libres(
    cupos: CuposPorFranja,
    ocupacion: Mapping[CategoriaCupo, int],
    categoria: CategoriaCupo,
) -> int:
    """Cupos libres de ``categoria`` en la franja dada su ocupación actual."""
    ocupados = ocupacion.get(categoria, 0)
    if ocupados < 0:
        raise ValueError("La ocupación no puede ser negativa")
    return max(cupos.capacidad(categoria) - ocupados, 0)


def cabe_uno_mas(
    cupos: CuposPorFranja,
    ocupacion: Mapping[CategoriaCupo, int],
    categoria: CategoriaCupo,
) -> bool:
    return cupos_libres(cupos, ocupacion, categoria) > 0
