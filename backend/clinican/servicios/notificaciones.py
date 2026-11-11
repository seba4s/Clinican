"""Puerto de notificaciones y bandeja de salida.

La agenda solo escribe en la bandeja (en la misma transacción que confirma o
mueve el turno). Enviar es trabajo del ``Despachador`` usando cualquier
implementación del puerto ``Notificador``; los canales concretos viven fuera
de esta capa y se eligen en la raíz de composición.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from clinican.datos import repo_agenda, repo_notificaciones
from clinican.datos.conexion import transaccion
from clinican.dominio.agenda import ZONA
from clinican.dominio.entidades import EstadoNotificacion, NotificacionSalida
from clinican.dominio.errores import NoEncontrado, OperacionNoPermitida
from clinican.dominio.estados import EstadoTurno
from clinican.dominio.notificaciones import TIPO_RECORDATORIO, hora_recordatorio
from clinican.servicios.auditoria import auditar


class ErrorEnvio(Exception):
    """El canal no pudo entregar el mensaje (se reintentará)."""


@dataclass(frozen=True)
class Mensaje:
    notificacion_id: int
    turno_id: int
    tipo: str
    telefono: str
    propietario: str
    mascota: str
    inicio: datetime
    texto: str


@runtime_checkable
class Notificador(Protocol):
    def enviar(self, mensaje: Mensaje) -> None:
        """Entrega el mensaje o lanza ErrorEnvio."""


def texto_recordatorio(propietario: str, mascota: str, inicio: datetime) -> str:
    """Texto PROVISIONAL del recordatorio (para canales de texto libre)."""
    local = inicio.astimezone(ZONA)
    return (
        f"Hola {propietario}, le recordamos el turno de peluquería de {mascota} "
        f"el {local.strftime('%d/%m/%Y')} a las {local.strftime('%H:%M')}."
    )


def programar_recordatorio(con, turno_id: int, inicio: datetime, horas_antes: int, ahora: datetime) -> int:
    """Inserta el recordatorio del turno. Debe llamarse dentro de la transacción del turno."""
    cuando = hora_recordatorio(inicio, horas_antes, ahora)
    nid = repo_notificaciones.insertar(con, turno_id, TIPO_RECORDATORIO, cuando, ahora)
    auditar(con, ahora, "programar", "notificacion", nid, turno_id=turno_id,
            tipo=TIPO_RECORDATORIO, programada_para=cuando.isoformat())
    return nid


def descartar_pendientes(con, turno_id: int, motivo: str, ahora: datetime) -> list[int]:
    """Descarta las notificaciones pendientes del turno (dentro de la transacción del turno)."""
    descartadas = []
    for n in repo_notificaciones.de_turno(con, turno_id):
        if n.estado is EstadoNotificacion.PENDIENTE:
            repo_notificaciones.actualizar_notificacion(
                con, n.id, estado=EstadoNotificacion.DESCARTADA, motivo_descarte=motivo,
                cerrada_en=ahora,
            )
            auditar(con, ahora, "descartar", "notificacion", n.id, motivo=motivo)
            descartadas.append(n.id)
    return descartadas


def notificaciones_de_turno(con, turno_id: int) -> list[NotificacionSalida]:
    return repo_notificaciones.de_turno(con, turno_id)


def reintentar(con, notificacion_id: int, *, ahora: datetime) -> NotificacionSalida:
    """Vuelve a poner en la bandeja un recordatorio FALLIDO para enviarlo ya.

    Solo si el turno sigue confirmado y no ha empezado. Los intentos vuelven a cero.
    """
    with transaccion(con):
        n = repo_notificaciones.obtener(con, notificacion_id)
        if n is None:
            raise NoEncontrado(f"No existe la notificación {notificacion_id}")
        if n.estado is not EstadoNotificacion.FALLIDA:
            raise OperacionNoPermitida("Solo se puede reintentar un recordatorio fallido")
        turno = repo_agenda.obtener_turno(con, n.turno_id)
        if turno is None or turno.estado is not EstadoTurno.CONFIRMADO or turno.inicio <= ahora:
            raise OperacionNoPermitida("El turno ya no está confirmado o ya empezó: no hace falta recordarlo")
        repo_notificaciones.actualizar_notificacion(
            con, n.id, estado=EstadoNotificacion.PENDIENTE, intentos=0, ultimo_error=None,
            programada_para=ahora, cerrada_en=None,
        )
        auditar(con, ahora, "reintentar", "notificacion", n.id, turno_id=n.turno_id)
    return repo_notificaciones.obtener(con, notificacion_id)
