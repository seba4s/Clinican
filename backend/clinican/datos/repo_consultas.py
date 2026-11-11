"""Consultas de solo lectura para pantallas (con joins para evitar N+1)."""

from __future__ import annotations

import sqlite3
from datetime import date

from clinican.datos.repo_agenda import COLUMNAS_TURNO, rango_del_dia, turno_de_fila
from clinican.datos.repo_fichas import _FICHA, _ficha
from clinican.datos.repo_notificaciones import _COLS as COLUMNAS_NOTIF
from clinican.datos.repo_notificaciones import _notificacion
from clinican.dominio.entidades import Ficha, NotificacionSalida, Turno

_N = len(COLUMNAS_TURNO.split(","))


def _prefijo(columnas: str, alias: str) -> str:
    return ", ".join(f"{alias}.{c.strip()}" for c in columnas.split(","))


_T = _prefijo(COLUMNAS_TURNO, "t")


def turnos_detallados_del_dia(
    con: sqlite3.Connection, dia: date
) -> list[tuple[Turno, str, str, str]]:
    """(turno, mascota, propietario, celular) del día, ordenados por hora."""
    filas = con.execute(
        f"SELECT {_T}, m.nombre, p.nombre, p.telefono FROM turnos t "
        "JOIN mascotas m ON m.id = t.mascota_id JOIN propietarios p ON p.id = t.propietario_id "
        "WHERE t.inicio >= ? AND t.inicio < ? ORDER BY t.inicio, t.id",
        rango_del_dia(dia),
    ).fetchall()
    return [(turno_de_fila(f[:_N]), f[_N], f[_N + 1], f[_N + 2]) for f in filas]


def historial_de_mascota(con: sqlite3.Connection, mascota_id: int) -> list[tuple[Turno, Ficha | None]]:
    filas = con.execute(
        f"SELECT {_T}, {_prefijo(_FICHA, 'f')} FROM turnos t "
        "LEFT JOIN fichas f ON f.turno_id = t.id WHERE t.mascota_id = ? ORDER BY t.inicio DESC, t.id DESC",
        (mascota_id,),
    ).fetchall()
    return [
        (turno_de_fila(f[:_N]), None if f[_N] is None else _ficha(f[_N:])) for f in filas
    ]


def pendientes_de_abono(con: sqlite3.Connection) -> list[tuple[Turno, str, str, str]]:
    filas = con.execute(
        f"SELECT {_T}, m.nombre, p.nombre, p.telefono FROM turnos t "
        "JOIN mascotas m ON m.id = t.mascota_id JOIN propietarios p ON p.id = t.propietario_id "
        "WHERE t.estado = 'pendiente_abono' ORDER BY t.creado_en, t.id"
    ).fetchall()
    return [(turno_de_fila(f[:_N]), f[_N], f[_N + 1], f[_N + 2]) for f in filas]


def conteo_bandeja(con: sqlite3.Connection) -> dict[str, int]:
    return dict(
        con.execute("SELECT estado, COUNT(*) FROM notificaciones_salida GROUP BY estado").fetchall()
    )


def notificaciones_por_estado(
    con: sqlite3.Connection, estado: str, limite: int = 20, recientes_primero: bool = False
) -> list[NotificacionSalida]:
    orden = "DESC" if recientes_primero else "ASC"
    filas = con.execute(
        f"SELECT {COLUMNAS_NOTIF} FROM notificaciones_salida WHERE estado = ? "
        f"ORDER BY programada_para {orden}, id {orden} LIMIT ?",
        (estado, limite),
    ).fetchall()
    return [_notificacion(f) for f in filas]
