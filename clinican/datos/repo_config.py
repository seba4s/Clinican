"""Tabla ``config`` (clave → valor en texto)."""

from __future__ import annotations

import sqlite3

from clinican.dominio.errores import DatoInvalido


def todas(conn: sqlite3.Connection) -> dict[str, str]:
    return {f["clave"]: f["valor"] for f in conn.execute("SELECT clave, valor FROM config")}


def obtener(conn: sqlite3.Connection, clave: str) -> str | None:
    fila = conn.execute("SELECT valor FROM config WHERE clave = ?", (clave,)).fetchone()
    return None if fila is None else fila["valor"]


def obtener_entero(conn: sqlite3.Connection, clave: str) -> int:
    valor = obtener(conn, clave)
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise DatoInvalido(f"Falta o es inválido el valor de configuración «{clave}».") from None


def guardar(conn: sqlite3.Connection, clave: str, valor: str) -> None:
    conn.execute(
        "INSERT INTO config (clave, valor) VALUES (?, ?) ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
        (clave, valor),
    )
