"""Conexión a SQLite y transacciones.

Cada hilo abre su propia conexión con :func:`abrir`. Las conexiones trabajan en modo
autocommit (``isolation_level=None``) y toda escritura de un caso de uso se agrupa con
:func:`transaccion`, que abre ``BEGIN IMMEDIATE``: el bloqueo de escritura se toma al
empezar, de modo que dos hilos no pueden leer la misma ocupación y escribir los dos.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

# Cuánto espera una conexión a que otra suelte el bloqueo de escritura antes de fallar.
ESPERA_BLOQUEO_SEGUNDOS = 10.0

Conexion = sqlite3.Connection


class ErrorTransaccion(RuntimeError):
    """Se intentó abrir una transacción dentro de otra."""


def abrir(ruta: str | Path) -> Conexion:
    """Abre la base de datos (``":memory:"`` para pruebas) con las opciones del programa."""
    en_memoria = str(ruta) == ":memory:"
    if not en_memoria:
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(ruta), timeout=ESPERA_BLOQUEO_SEGUNDOS, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute(f"PRAGMA busy_timeout = {int(ESPERA_BLOQUEO_SEGUNDOS * 1000)}")
    if not en_memoria:
        # WAL deja leer mientras otro hilo escribe (el despachador lee mientras la recepción agenda).
        con.execute("PRAGMA journal_mode = WAL")
        con.execute("PRAGMA synchronous = NORMAL")
    return con


@contextmanager
def transaccion(con: Conexion) -> Iterator[Conexion]:
    """``BEGIN IMMEDIATE`` … ``COMMIT``; si algo falla, ``ROLLBACK`` y se relanza el error."""
    if con.in_transaction:
        raise ErrorTransaccion("Ya hay una transacción abierta en esta conexión.")
    con.execute("BEGIN IMMEDIATE")
    try:
        yield con
    except BaseException:
        con.execute("ROLLBACK")
        raise
    else:
        con.execute("COMMIT")
