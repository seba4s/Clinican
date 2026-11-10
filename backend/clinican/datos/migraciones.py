"""Migraciones de esquema numeradas y solo aditivas.

La versión aplicada se guarda en ``PRAGMA user_version``. Cada migración corre
en su propia transacción y fija ``user_version`` dentro de esa misma
transacción, de modo que un fallo a mitad deja la base en la versión anterior.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from clinican.datos.conexion import transaccion


class ErrorMigracion(RuntimeError):
    """Error general de migraciones."""


class BaseMasNueva(ErrorMigracion):
    """La base tiene una versión mayor que la última migración conocida."""


class MigracionesInvalidas(ErrorMigracion):
    """La lista de migraciones no cumple las reglas (numeración o contenido)."""


@dataclass(frozen=True)
class Migracion:
    version: int
    descripcion: str
    sql: str


MIGRACIONES: tuple[Migracion, ...] = (
    Migracion(
        version=1,
        descripcion="Tabla de configuración clave/valor",
        sql="""
        CREATE TABLE configuracion (
            clave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        );
        """,
    ),
)

_DESTRUCTIVO = re.compile(r"\b(DROP|DELETE)\b", re.IGNORECASE)
_COMENTARIOS = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)


def _sentencias(sql: str) -> list[str]:
    """Divide el SQL en sentencias completas (sin comentarios)."""
    limpio = _COMENTARIOS.sub(" ", sql)
    sentencias: list[str] = []
    actual = ""
    for linea in limpio.splitlines(keepends=True):
        actual += linea
        if sqlite3.complete_statement(actual):
            if actual.strip().strip(";").strip():
                sentencias.append(actual.strip())
            actual = ""
    if actual.strip():
        sentencias.append(actual.strip())
    return sentencias


def validar(migraciones) -> None:
    """Verifica numeración 1..n sin huecos y que solo agreguen esquema."""
    versiones = [m.version for m in migraciones]
    if versiones != list(range(1, len(versiones) + 1)):
        raise MigracionesInvalidas(
            f"Las migraciones deben numerarse 1..n sin huecos ni desorden: {versiones}"
        )
    for m in migraciones:
        if _DESTRUCTIVO.search(_COMENTARIOS.sub(" ", m.sql)):
            raise MigracionesInvalidas(
                f"La migración {m.version} contiene DROP o DELETE; solo se permite agregar"
            )


def version_actual(con: sqlite3.Connection) -> int:
    return con.execute("PRAGMA user_version").fetchone()[0]


def migrar(con: sqlite3.Connection, migraciones=MIGRACIONES) -> int:
    """Aplica las migraciones pendientes y devuelve la versión final."""
    migraciones = tuple(migraciones)
    validar(migraciones)
    ultima = len(migraciones)
    actual = version_actual(con)
    if actual > ultima:
        raise BaseMasNueva(
            f"La base está en la versión {actual} y esta aplicación solo conoce hasta la {ultima}"
        )
    for m in migraciones[actual:]:
        with transaccion(con):
            for sentencia in _sentencias(m.sql):
                con.execute(sentencia)
            con.execute(f"PRAGMA user_version={int(m.version)}")
    return version_actual(con)
