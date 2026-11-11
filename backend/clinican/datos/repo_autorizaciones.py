"""Repositorio del historial de autorizaciones de datos (Ley 1581)."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime

from clinican.datos._util import a_texto, de_texto, fecha_a_texto
from clinican.dominio.autorizaciones import AutorizacionDatos

_COLS = "id, propietario_id, otorgada, fecha, medio, registrada_en"


def _autorizacion(f) -> AutorizacionDatos:
    return AutorizacionDatos(f[0], f[1], bool(f[2]), date.fromisoformat(f[3]), f[4], de_texto(f[5]))


def insertar(
    con: sqlite3.Connection,
    propietario_id: int,
    otorgada: bool,
    fecha: date,
    medio: str,
    registrada_en: datetime,
) -> int:
    cur = con.execute(
        "INSERT INTO autorizaciones_datos (propietario_id, otorgada, fecha, medio, registrada_en) "
        "VALUES (?, ?, ?, ?, ?)",
        (propietario_id, int(otorgada), fecha_a_texto(fecha), medio, a_texto(registrada_en)),
    )
    return cur.lastrowid


def historial(con: sqlite3.Connection, propietario_id: int) -> list[AutorizacionDatos]:
    """Registros del propietario, del más antiguo al más reciente."""
    filas = con.execute(
        f"SELECT {_COLS} FROM autorizaciones_datos WHERE propietario_id = ? "
        "ORDER BY registrada_en, id",
        (propietario_id,),
    ).fetchall()
    return [_autorizacion(f) for f in filas]


def ultimo(con: sqlite3.Connection, propietario_id: int) -> AutorizacionDatos | None:
    f = con.execute(
        f"SELECT {_COLS} FROM autorizaciones_datos WHERE propietario_id = ? "
        "ORDER BY registrada_en DESC, id DESC LIMIT 1",
        (propietario_id,),
    ).fetchone()
    return None if f is None else _autorizacion(f)


def mover(con: sqlite3.Connection, origen_id: int, destino_id: int) -> int:
    """Pasa el historial de un propietario a otro (al unir duplicados)."""
    cur = con.execute(
        "UPDATE autorizaciones_datos SET propietario_id = ? WHERE propietario_id = ?",
        (destino_id, origen_id),
    )
    return cur.rowcount
