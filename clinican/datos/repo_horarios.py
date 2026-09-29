"""Tablas ``franjas_base`` (plantilla semanal), ``franjas_ajuste`` y ``bloqueos``."""

from __future__ import annotations

import sqlite3

# ------------------------------------------------------- plantilla semanal


def base_del_dia(conn: sqlite3.Connection, dia_semana: int) -> list[tuple[str, str]]:
    """[(hora, jornada)] activas de ese día de la semana (1 = lunes)."""
    filas = conn.execute("SELECT hora, jornada FROM franjas_base WHERE dia_semana = ? AND activa = 1 ORDER BY hora",
                         (dia_semana,)).fetchall()
    return [(f["hora"], f["jornada"]) for f in filas]


def plantilla(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM franjas_base ORDER BY dia_semana, hora").fetchall()


def franja_base(conn: sqlite3.Connection, dia_semana: int, hora: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM franjas_base WHERE dia_semana = ? AND hora = ?", (dia_semana, hora)).fetchone()


def insertar_franja_base(conn: sqlite3.Connection, dia_semana: int, hora: str, jornada: str) -> int:
    cur = conn.execute("INSERT INTO franjas_base (dia_semana, hora, jornada) VALUES (?, ?, ?)",
                       (dia_semana, hora, jornada))
    return cur.lastrowid


def fijar_franja_base_activa(conn: sqlite3.Connection, franja_id: int, activa: bool) -> None:
    conn.execute("UPDATE franjas_base SET activa = ? WHERE id = ?", (int(bool(activa)), franja_id))


# ------------------------------------------------------ franjas sueltas


def ajustes(conn: sqlite3.Connection, fecha: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM franjas_ajuste WHERE fecha = ? ORDER BY hora", (fecha,)).fetchall()


def ajuste(conn: sqlite3.Connection, fecha: str, hora: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM franjas_ajuste WHERE fecha = ? AND hora = ?", (fecha, hora)).fetchone()


def insertar_ajuste(conn: sqlite3.Connection, fecha: str, hora: str, accion: str, creado_por: int) -> int:
    cur = conn.execute("INSERT INTO franjas_ajuste (fecha, hora, accion, creado_por) VALUES (?, ?, ?, ?)",
                       (fecha, hora, accion, creado_por))
    return cur.lastrowid


def borrar_ajuste(conn: sqlite3.Connection, ajuste_id: int) -> None:
    conn.execute("DELETE FROM franjas_ajuste WHERE id = ?", (ajuste_id,))


# --------------------------------------------------------------- bloqueos

_BLOQUEO = """SELECT b.*, p.nombre AS creado_por_nombre FROM bloqueos b
              LEFT JOIN personal p ON p.id = b.creado_por"""


def bloqueos(conn: sqlite3.Connection, fecha: str) -> list[sqlite3.Row]:
    return conn.execute(f"{_BLOQUEO} WHERE b.fecha = ? ORDER BY b.hora IS NOT NULL, b.hora", (fecha,)).fetchall()


def bloqueos_desde(conn: sqlite3.Connection, desde: str) -> list[sqlite3.Row]:
    return conn.execute(f"{_BLOQUEO} WHERE b.fecha >= ? ORDER BY b.fecha, b.hora IS NOT NULL, b.hora",
                        (desde,)).fetchall()


def bloqueo(conn: sqlite3.Connection, bloqueo_id: int) -> sqlite3.Row | None:
    return conn.execute(f"{_BLOQUEO} WHERE b.id = ?", (bloqueo_id,)).fetchone()


def insertar_bloqueo(conn: sqlite3.Connection, fecha: str, hora: str | None, motivo: str | None, creado_por: int) -> int:
    cur = conn.execute("INSERT INTO bloqueos (fecha, hora, motivo, creado_por) VALUES (?, ?, ?, ?)",
                       (fecha, hora, motivo, creado_por))
    return cur.lastrowid


def borrar_bloqueo(conn: sqlite3.Connection, bloqueo_id: int) -> None:
    conn.execute("DELETE FROM bloqueos WHERE id = ?", (bloqueo_id,))
