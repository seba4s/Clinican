"""Estados del turno y sus transiciones permitidas."""

from __future__ import annotations

from enum import Enum


class EstadoTurno(Enum):
    PENDIENTE_ABONO = "pendiente_abono"
    CONFIRMADO = "confirmado"
    EN_ATENCION = "en_atencion"
    ATENDIDO = "atendido"
    ENTREGADO = "entregado"
    LIBERADO = "liberado"
    CANCELADO = "cancelado"
    INASISTENCIA = "inasistencia"


class MotivoLiberacion(Enum):
    ABONO_VENCIDO = "abono_vencido"
    OTRO_PAGO_PRIMERO = "otro_pago_primero"
    OTRO = "otro"


class TransicionInvalida(ValueError):
    """Cambio de estado no permitido."""


E = EstadoTurno

TRANSICIONES: dict[EstadoTurno, frozenset[EstadoTurno]] = {
    E.PENDIENTE_ABONO: frozenset({E.CONFIRMADO, E.LIBERADO, E.CANCELADO}),
    E.CONFIRMADO: frozenset({E.EN_ATENCION, E.CANCELADO, E.INASISTENCIA}),
    E.EN_ATENCION: frozenset({E.ATENDIDO}),
    E.ATENDIDO: frozenset({E.ENTREGADO}),
    E.ENTREGADO: frozenset(),
    E.LIBERADO: frozenset(),
    E.CANCELADO: frozenset(),
    E.INASISTENCIA: frozenset(),
}

ESTADOS_FINALES = frozenset(e for e, salidas in TRANSICIONES.items() if not salidas)

_OCUPAN_CUPO = frozenset(
    {E.PENDIENTE_ABONO, E.CONFIRMADO, E.EN_ATENCION, E.ATENDIDO, E.ENTREGADO}
)


def ocupa_cupo(estado: EstadoTurno) -> bool:
    """Indica si un turno en ``estado`` ocupa su franja (una sola franja de 30 min)."""
    return estado in _OCUPAN_CUPO


def transicionar(
    actual: EstadoTurno,
    nuevo: EstadoTurno,
    motivo: MotivoLiberacion | None = None,
) -> EstadoTurno:
    """Valida el cambio de estado y devuelve el nuevo estado.

    Pasar a LIBERADO exige un ``MotivoLiberacion``; las demás transiciones no
    aceptan motivo.
    """
    if nuevo not in TRANSICIONES[actual]:
        raise TransicionInvalida(f"No se puede pasar de {actual.name} a {nuevo.name}")
    if nuevo is E.LIBERADO:
        if not isinstance(motivo, MotivoLiberacion):
            raise TransicionInvalida("Liberar un turno exige un MotivoLiberacion")
    elif motivo is not None:
        raise TransicionInvalida(f"La transición a {nuevo.name} no lleva motivo")
    return nuevo
