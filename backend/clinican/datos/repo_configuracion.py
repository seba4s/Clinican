"""Repositorio de la tabla configuracion (clave -> texto)."""

from __future__ import annotations

import sqlite3


def leer(con: sqlite3.Connection, clave: str) -> str | None:
    fila = con.execute("SELECT valor FROM configuracion WHERE clave = ?", (clave,)).fetchone()
    return None if fila is None else fila[0]


def guardar(con: sqlite3.Connection, clave: str, valor: str) -> None:
    con.execute(
        "INSERT INTO configuracion (clave, valor) VALUES (?, ?) "
        "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
        (clave, valor),
    )


def todas(con: sqlite3.Connection) -> dict[str, str]:
    return dict(con.execute("SELECT clave, valor FROM configuracion").fetchall())
