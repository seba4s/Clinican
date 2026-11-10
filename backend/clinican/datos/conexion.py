"""Apertura de conexiones SQLite y manejo explícito de transacciones.

Las conexiones se abren en modo autocommit (``isolation_level=None``) para que
las transacciones sean siempre explícitas mediante :func:`transaccion`.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class TransaccionAnidada(RuntimeError):
    """Se intentó abrir una transacción con otra ya en curso."""


def abrir(ruta: str | Path, busy_timeout_ms: int = 5000) -> sqlite3.Connection:
    """Abre la base en ``ruta`` con WAL, claves foráneas y tiempo de espera."""
    con = sqlite3.connect(str(ruta), isolation_level=None)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        con.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
    except Exception:
        con.close()
        raise
    return con


@contextmanager
def transaccion(con: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Ejecuta el bloque dentro de ``BEGIN IMMEDIATE``.

    Hace COMMIT si el bloque termina bien y ROLLBACK si lanza una excepción.
    No se permiten transacciones anidadas.
    """
    if con.in_transaction:
        raise TransaccionAnidada("Ya hay una transacción en curso en esta conexión")
    con.execute("BEGIN IMMEDIATE")
    try:
        yield con
    except BaseException:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    else:
        con.execute("COMMIT")
