"""Copias de la base con la API de backup de SQLite, verificadas con quick_check."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from clinican.datos.conexion import abrir


class RespaldoInvalido(RuntimeError):
    """La copia no pasó PRAGMA quick_check o no es una base de Clinican."""


def verificar(ruta: str | Path) -> None:
    """Lanza RespaldoInvalido si la base en ``ruta`` no pasa quick_check."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise RespaldoInvalido(f"No existe el archivo {ruta}")
    try:
        con = sqlite3.connect(f"file:{ruta.as_posix()}?mode=ro", uri=True)
        try:
            resultado = [f[0] for f in con.execute("PRAGMA quick_check").fetchall()]
        finally:
            con.close()
    except sqlite3.DatabaseError as error:
        raise RespaldoInvalido(f"{ruta.name} no es una base válida: {error}") from None
    if resultado != ["ok"]:
        raise RespaldoInvalido(f"{ruta.name} falló la verificación: {'; '.join(resultado[:5])}")


def version(ruta: str | Path) -> int:
    con = sqlite3.connect(f"file:{Path(ruta).as_posix()}?mode=ro", uri=True)
    try:
        return con.execute("PRAGMA user_version").fetchone()[0]
    finally:
        con.close()


def copiar(ruta_origen: str | Path, ruta_destino: str | Path) -> None:
    """Copia en caliente la base ``ruta_origen`` (puede estar en uso) a ``ruta_destino``."""
    destino = Path(ruta_destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    origen = abrir(ruta_origen)
    try:
        copia = sqlite3.connect(str(destino))
        try:
            origen.backup(copia)
            # La copia queda autocontenida (sin archivos -wal aparte)
            copia.execute("PRAGMA journal_mode=DELETE")
        finally:
            copia.close()
    finally:
        origen.close()


def restaurar_sobre(ruta_copia: str | Path, ruta_db: str | Path) -> None:
    """Reemplaza el contenido de ``ruta_db`` por el de ``ruta_copia`` (página a página)."""
    origen = sqlite3.connect(f"file:{Path(ruta_copia).as_posix()}?mode=ro", uri=True)
    try:
        destino = abrir(ruta_db)
        try:
            origen.backup(destino)
        finally:
            destino.close()
    finally:
        origen.close()
