"""Errores de reglas de negocio, con mensajes en español para mostrar al usuario."""

from __future__ import annotations


class ErrorNegocio(ValueError):
    """Operación rechazada por una regla de negocio."""


class NoEncontrado(ErrorNegocio, LookupError):
    """El registro pedido no existe."""


class DatoInvalido(ErrorNegocio):
    """Un dato no cumple el formato o las reglas."""


class FranjaNoDisponible(ErrorNegocio):
    """La hora pedida no es una franja reservable (fuera de horario o bloqueada)."""


class SinCupo(ErrorNegocio):
    """La franja ya no tiene cupo para la categoría del turno."""


class AbonoRechazado(ErrorNegocio):
    """No se puede registrar el abono."""


class BloqueoConTurnos(ErrorNegocio):
    """El bloqueo cubriría turnos activos."""


class OperacionNoPermitida(ErrorNegocio):
    """La operación no es válida en el estado actual."""
