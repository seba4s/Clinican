"""Repositorio de la bandeja de salida (notificaciones_salida)."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from clinican.datos._util import a_texto, actualizar, de_texto
from clinican.dominio.entidades import EstadoNotificacion, NotificacionSalida

_COLS = (
    "id, turno_id, tipo, programada_para, estado, intentos, ultimo_error, motivo_descarte, "
    "creada_en, enviada_en, cerrada_en"
)


def _notificacion(f) -> NotificacionSalida:
    return NotificacionSalida(
        id=f[0],
        turno_id=f[1],
        tipo=f[2],
        programada_para=de_texto(f[3]),
        estado=EstadoNotificacion(f[4]),
        intentos=f[5],
        ultimo_error=f[6],
        motivo_descarte=f[7],
        creada_en=de_texto(f[8]),
        enviada_en=de_texto(f[9]),
        cerrada_en=de_texto(f[10]),
    )


def insertar(
    con: sqlite3.Connection, turno_id: int, tipo: str, programada_para: datetime, creada_en: datetime
) -> int:
    cur = con.execute(
        "INSERT INTO notificaciones_salida (turno_id, tipo, programada_para, creada_en) "
        "VALUES (?, ?, ?, ?)",
        (turno_id, tipo, a_texto(programada_para), a_texto(creada_en)),
    )
    return cur.lastrowid


def obtener(con: sqlite3.Connection, id_: int) -> NotificacionSalida | None:
    f = con.execute(f"SELECT {_COLS} FROM notificaciones_salida WHERE id = ?", (id_,)).fetchone()
    return None if f is None else _notificacion(f)


def de_turno(con: sqlite3.Connection, turno_id: int) -> list[NotificacionSalida]:
    filas = con.execute(
        f"SELECT {_COLS} FROM notificaciones_salida WHERE turno_id = ? ORDER BY id", (turno_id,)
    ).fetchall()
    return [_notificacion(f) for f in filas]


def pendientes_hasta(con: sqlite3.Connection, ahora: datetime, limite: int = 100) -> list[NotificacionSalida]:
    filas = con.execute(
        f"SELECT {_COLS} FROM notificaciones_salida "
        "WHERE estado = 'pendiente' AND programada_para <= ? ORDER BY programada_para, id LIMIT ?",
        (a_texto(ahora), limite),
    ).fetchall()
    return [_notificacion(f) for f in filas]


def actualizar_notificacion(con: sqlite3.Connection, id_: int, **campos: Any) -> None:
    valores = {}
    for clave, valor in campos.items():
        if isinstance(valor, datetime):
            valor = a_texto(valor)
        elif isinstance(valor, EstadoNotificacion):
            valor = valor.value
        valores[clave] = valor
    actualizar(
        con, "notificaciones_salida", id_, valores,
        {"programada_para", "estado", "intentos", "ultimo_error", "motivo_descarte",
         "enviada_en", "cerrada_en"},
    )


def purgar_cerradas(con: sqlite3.Connection, antes_de: datetime) -> int:
    """Borra enviadas, descartadas y fallidas cerradas antes de ``antes_de``."""
    cur = con.execute(
        "DELETE FROM notificaciones_salida WHERE estado <> 'pendiente' AND cerrada_en < ?",
        (a_texto(antes_de),),
    )
    return cur.rowcount
