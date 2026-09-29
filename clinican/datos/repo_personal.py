"""Tabla ``personal``."""

from __future__ import annotations

import sqlite3


def por_id(conn: sqlite3.Connection, personal_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM personal WHERE id = ?", (personal_id,)).fetchone()


def por_nombre(conn: sqlite3.Connection, nombre: str) -> sqlite3.Row | None:
    """Sin distinguir mayúsculas, tildes ni espacios de más."""
    limpio = " ".join((nombre or "").split())
    return conn.execute("SELECT * FROM personal WHERE sin_tildes(nombre) = sin_tildes(?)", (limpio,)).fetchone()


def contar(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM personal").fetchone()[0]


def contar_admins_activos(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM personal WHERE rol = 'ADMIN' AND activo = 1").fetchone()[0]


def listar(conn: sqlite3.Connection, solo_activos: bool = False) -> list[sqlite3.Row]:
    filtro = "WHERE activo = 1" if solo_activos else ""
    return conn.execute(
        f"SELECT * FROM personal {filtro} ORDER BY activo DESC, rol = 'ADMIN' DESC, sin_tildes(nombre)"
    ).fetchall()


def insertar(conn: sqlite3.Connection, nombre: str, cargo: str, rol: str, pin_hash: str, pin_sal: str) -> int:
    cur = conn.execute(
        "INSERT INTO personal (nombre, cargo, rol, pin_hash, pin_sal) VALUES (?, ?, ?, ?, ?)",
        (nombre, cargo, rol, pin_hash, pin_sal),
    )
    return cur.lastrowid


def actualizar_datos(conn: sqlite3.Connection, personal_id: int, nombre: str, cargo: str) -> None:
    conn.execute("UPDATE personal SET nombre = ?, cargo = ? WHERE id = ?", (nombre, cargo, personal_id))


def actualizar_pin(conn: sqlite3.Connection, personal_id: int, pin_hash: str, pin_sal: str) -> None:
    conn.execute("UPDATE personal SET pin_hash = ?, pin_sal = ? WHERE id = ?", (pin_hash, pin_sal, personal_id))


def cambiar_activo(conn: sqlite3.Connection, personal_id: int, activo: bool) -> None:
    conn.execute("UPDATE personal SET activo = ? WHERE id = ?", (int(bool(activo)), personal_id))


def cambiar_rol(conn: sqlite3.Connection, personal_id: int, rol: str) -> None:
    conn.execute("UPDATE personal SET rol = ? WHERE id = ?", (rol, personal_id))
