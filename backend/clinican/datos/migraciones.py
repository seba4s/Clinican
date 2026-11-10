"""Migraciones numeradas del esquema, controladas con ``PRAGMA user_version``.

Reglas para agregar una migración:

* Se agrega al final de ``MIGRACIONES`` con el número siguiente. Nunca se edita una que ya
  se entregó a la peluquería.
* Solo agrega: tablas, columnas, índices o datos. Para cambiar una tabla se crea la nueva,
  se copian los datos y luego se renombra, dentro de la misma migración.

Cada migración corre en su propia transacción ``BEGIN IMMEDIATE`` junto con el cambio de
``user_version``; si falla, la base queda exactamente como estaba. Correr :func:`migrar` dos
veces no hace nada la segunda vez.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from clinican.datos.conexion import Conexion, transaccion


@dataclass(frozen=True)
class Migracion:
    numero: int
    descripcion: str
    sql: str


class ErrorMigracion(RuntimeError):
    """La base no se puede llevar a la versión de este programa."""


MIGRACIONES: tuple[Migracion, ...] = (
    Migracion(1, "Configuración clave-valor tipada", """
        CREATE TABLE configuracion (
            clave TEXT PRIMARY KEY,
            valor TEXT NOT NULL,
            tipo  TEXT NOT NULL CHECK (tipo IN ('entero', 'decimal', 'texto', 'booleano', 'json'))
        );
    """),
)


def version_actual(con: Conexion) -> int:
    return con.execute("PRAGMA user_version").fetchone()[0]


def version_esperada(migraciones: tuple[Migracion, ...] = MIGRACIONES) -> int:
    return migraciones[-1].numero if migraciones else 0


def _validar(migraciones: tuple[Migracion, ...]) -> None:
    numeros = [m.numero for m in migraciones]
    if numeros != list(range(1, len(numeros) + 1)):
        raise ErrorMigracion(f"Las migraciones deben numerarse 1, 2, 3… sin huecos: {numeros}")


def migrar(con: Conexion, migraciones: tuple[Migracion, ...] = MIGRACIONES) -> list[int]:
    """Aplica las migraciones pendientes y devuelve los números aplicados."""
    _validar(migraciones)
    actual = version_actual(con)
    if actual > version_esperada(migraciones):
        raise ErrorMigracion(
            f"La base de datos es de una versión más nueva del programa ({actual}). "
            "Actualice CLINICAN antes de abrirla.")
    aplicadas = []
    for m in migraciones:
        if m.numero <= actual:
            continue
        with transaccion(con):
            # Se ejecuta sentencia por sentencia porque executescript haría COMMIT por su cuenta.
            for sentencia in _sentencias(m.sql):
                con.execute(sentencia)
            con.execute(f"PRAGMA user_version = {m.numero}")
        aplicadas.append(m.numero)
    return aplicadas


def _sentencias(sql: str) -> list[str]:
    """Parte un guion en sentencias completas (respeta los ``;`` dentro de triggers y textos)."""
    sentencias, actual = [], ""
    for linea in sql.splitlines(keepends=True):
        actual += linea
        if sqlite3.complete_statement(actual):
            if actual.strip():
                sentencias.append(actual.strip())
            actual = ""
    if actual.strip():
        raise ErrorMigracion(f"Sentencia SQL incompleta en la migración: {actual.strip()[:60]}…")
    return sentencias
