"""Tabla ``razas``."""

from __future__ import annotations

import sqlite3


def listar(conn: sqlite3.Connection, solo_activas: bool = True) -> list[sqlite3.Row]:
    filtro = "WHERE activa = 1" if solo_activas else ""
    return conn.execute(f"SELECT * FROM razas {filtro} ORDER BY sin_tildes(nombre)").fetchall()


def por_id(conn: sqlite3.Connection, raza_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM razas WHERE id = ?", (raza_id,)).fetchone()


def por_nombre(conn: sqlite3.Connection, nombre: str) -> sqlite3.Row | None:
    """Sin distinguir mayúsculas, tildes ni espacios de más ("shih tzu" = "Shih Tzu")."""
    limpio = " ".join(str(nombre or "").split())
    if not limpio:
        return None
    return conn.execute("SELECT * FROM razas WHERE sin_tildes(nombre) = sin_tildes(?)", (limpio,)).fetchone()


def insertar(conn: sqlite3.Connection, nombre: str, tamano: str | None, pelaje_complicado: bool) -> int:
    cur = conn.execute("INSERT INTO razas (nombre, tamano, pelaje_complicado) VALUES (?, ?, ?)",
                       (nombre, tamano, int(bool(pelaje_complicado))))
    return cur.lastrowid


def actualizar(conn: sqlite3.Connection, raza_id: int, nombre: str, tamano: str | None,
               pelaje_complicado: bool, activa: bool) -> None:
    conn.execute("UPDATE razas SET nombre = ?, tamano = ?, pelaje_complicado = ?, activa = ? WHERE id = ?",
                 (nombre, tamano, int(bool(pelaje_complicado)), int(bool(activa)), raza_id))


def mascotas_sin_tamano_si_quita(conn: sqlite3.Connection, raza_id: int) -> int:
    """Mascotas de la raza que quedarían sin tamaño si la raza deja de tenerlo."""
    return conn.execute("SELECT COUNT(*) FROM mascotas WHERE raza_id = ? AND tamano_manual IS NULL",
                        (raza_id,)).fetchone()[0]
