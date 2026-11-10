"""Recordatorios a los dueños por una bandeja de salida (driver D3, ADR-003).

- ``Notificador`` es el **puerto**: lo que la aplicación necesita de un canal. Los
  adaptadores (WhatsApp de Meta, archivo, consola…) viven en ``clinican.adaptadores``
  y esta capa no los importa: se los pasan desde el arranque (``main.py``).
- ``programar_recordatorio`` lo llama el servicio de turnos **dentro de su transacción**
  al confirmar o mover un turno: el recordatorio queda guardado o no queda nada.
- ``despachar`` toma los pendientes y los entrega al canal. No mantiene la base bloqueada
  mientras espera a la red, y si el canal falla reintenta más tarde (al menos una vez).
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol, runtime_checkable

from clinican.datos import repo_config, repo_legal, repo_notificaciones as repo, repo_turnos
from clinican.datos.conexion import transaccion
from clinican.dominio import notificaciones as reglas
from clinican.dominio.turnos import inicio_turno

log = logging.getLogger(__name__)
_FMT = "%Y-%m-%d %H:%M:%S"
DIAS_HISTORIAL = 90


class ErrorEnvio(Exception):
    """El canal no pudo entregar el mensaje ahora (sin conexión, token vencido…). Se reintenta."""


@runtime_checkable
class Notificador(Protocol):
    """Puerto de salida. Un canal nuevo solo tiene que cumplir esto."""

    nombre: str

    def enviar(self, mensaje: reglas.Mensaje) -> None:
        """Entrega el mensaje o lanza ``ErrorEnvio``."""
        ...


@dataclass
class ResumenDespacho:
    enviados: list[int] = field(default_factory=list)
    fallidos: list[tuple[int, str]] = field(default_factory=list)
    descartados: list[tuple[int, str]] = field(default_factory=list)


def programar_recordatorio(conn: sqlite3.Connection, turno_id: int, fecha: str, hora: str,
                           ahora: datetime | None = None) -> None:
    """Deja en la bandeja el recordatorio del turno (llamar dentro de la transacción del turno)."""
    ahora = ahora or datetime.now()
    horas = repo_config.obtener_entero(conn, "recordatorio_horas_antes")
    cuando = reglas.momento_de_envio(inicio_turno(fecha, hora), horas, ahora)
    repo.programar(conn, turno_id, reglas.PLANTILLA_RECORDATORIO, cuando.strftime(_FMT))


def reprogramar(conn: sqlite3.Connection, turno_id: int, ahora: datetime | None = None) -> None:
    """Vuelve a dejar pendiente el recordatorio de un turno (por ejemplo, para reenviarlo)."""
    with transaccion(conn):
        t = repo_turnos.turno(conn, turno_id)
        programar_recordatorio(conn, turno_id, t["fecha"], t["hora"], ahora)


def despachar(conn: sqlite3.Connection, notificador: Notificador, ahora: datetime | None = None,
              limite: int = 50) -> ResumenDespacho:
    """Entrega los recordatorios pendientes con el canal recibido. Devuelve qué pasó con cada uno."""
    ahora = ahora or datetime.now()
    marca = ahora.strftime(_FMT)
    negocio = repo_config.todas(conn).get("negocio_nombre", "CLINICAN")
    resumen = ResumenDespacho()
    for fila in repo.listos_para_enviar(conn, marca, limite):
        inicio = inicio_turno(fila["fecha"], fila["hora"])
        autorizado = "DATOS" in repo_legal.tipos_aceptados_vigentes(conn, fila["propietario_id"])
        motivo = reglas.motivo_para_descartar(fila["turno_estado"], inicio, ahora, autorizado, bool(fila["celular1"]))
        if motivo:
            with transaccion(conn):
                repo.marcar_descartado(conn, fila["id"], motivo, marca)
            resumen.descartados.append((fila["id"], motivo))
            continue
        mensaje = reglas.recordatorio(fila["celular1"], fila["propietario_nombre"], fila["mascota_nombre"],
                                      inicio, negocio, referencia=f"turno-{fila['turno_id']}")
        try:
            notificador.enviar(mensaje)  # fuera de la transacción: la red no bloquea la agenda
        except ErrorEnvio as e:
            siguiente = (ahora + reglas.espera_reintento(fila["intentos"] + 1)).strftime(_FMT)
            with transaccion(conn):
                repo.marcar_fallo(conn, fila["id"], notificador.nombre, str(e), siguiente)
            resumen.fallidos.append((fila["id"], str(e)))
            log.warning("No se pudo enviar el recordatorio %s por %s: %s", fila["id"], notificador.nombre, e)
            continue
        with transaccion(conn):
            repo.marcar_enviado(conn, fila["id"], notificador.nombre, mensaje.destino, mensaje.texto, marca)
        resumen.enviados.append(fila["id"])
    with transaccion(conn):
        repo.purgar_cerrados(conn, (ahora - timedelta(days=DIAS_HISTORIAL)).strftime(_FMT))
    return resumen


def bandeja(conn: sqlite3.Connection, limite: int = 100) -> list[sqlite3.Row]:
    """Mensajes más recientes de la bandeja de salida, con su estado."""
    return repo.recientes(conn, limite)


def conteo(conn: sqlite3.Connection) -> dict[str, int]:
    return {e: 0 for e in reglas.ESTADOS} | repo.conteo_por_estado(conn)
