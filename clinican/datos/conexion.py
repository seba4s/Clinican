"""Conexión a SQLite y transacciones.

- ``PRAGMA foreign_keys = ON`` en cada conexión.
- La conexión trabaja en modo autocommit; las escrituras de los servicios van
  dentro de ``transaccion``, que se puede anidar (usa SAVEPOINT).
- Se registra la función ``sin_tildes`` para buscar sin importar tildes ni mayúsculas.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from itertools import count
from pathlib import Path

from clinican.dominio.formato import sin_tildes

_puntos = count(1)


def preparar(conn: sqlite3.Connection) -> sqlite3.Connection:
    """Ajustes de cada conexión (también se usa al abrir un respaldo)."""
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.create_function("sin_tildes", 1, sin_tildes, deterministic=True)
    return conn


def conectar(ruta: str | Path) -> sqlite3.Connection:
    """Abre (o crea) la base de datos, aplica migraciones y semillas."""
    from clinican.datos import migraciones, semillas

    if str(ruta) != ":memory:":
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(ruta), isolation_level=None)
    try:
        preparar(conn)
        migraciones.migrar(conn)
        semillas.sembrar(conn)
    except Exception:
        conn.close()
        raise
    return conn


@contextmanager
def transaccion(conn: sqlite3.Connection):
    """Todo o nada. Dentro de otra transacción se usa un SAVEPOINT."""
    if conn.in_transaction:
        nombre = f"sp_{next(_puntos)}"
        conn.execute(f"SAVEPOINT {nombre}")
        try:
            yield conn
        except BaseException:
            conn.execute(f"ROLLBACK TO {nombre}")
            conn.execute(f"RELEASE {nombre}")
            raise
        conn.execute(f"RELEASE {nombre}")
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
