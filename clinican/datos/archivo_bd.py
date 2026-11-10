"""Operaciones sobre el archivo completo de la base de datos (respaldos).

Aquí vive todo el SQL que toca archivos ``.db`` enteros: copiar con la API de
respaldo de SQLite, revisar la integridad y leer el resumen de un respaldo. La
capa de servicios decide cuándo y con qué permisos; esta capa solo sabe hacerlo.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from clinican.datos import migraciones, semillas
from clinican.datos.conexion import preparar


def _solo_lectura(ruta: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{Path(ruta).resolve().as_uri()}?mode=ro", uri=True)


def es_memoria(conn: sqlite3.Connection) -> bool:
    """True si la base es temporal (en memoria) y no tiene archivo que respaldar."""
    principal = next((f for f in conn.execute("PRAGMA database_list") if f[1] == "main"), None)
    return principal is None or not principal[2]


def copiar(conn: sqlite3.Connection, destino: Path) -> None:
    """Copia la base abierta, completa, al archivo ``destino``."""
    copia = sqlite3.connect(destino)
    try:
        conn.backup(copia)
    finally:
        copia.close()


def revision_integridad(ruta: Path) -> str:
    """Resultado de ``PRAGMA quick_check`` («ok» si está sana).

    Lanza ``sqlite3.DatabaseError`` si el archivo no es una base de datos.
    """
    c = _solo_lectura(ruta)
    try:
        return c.execute("PRAGMA quick_check").fetchone()[0]
    finally:
        c.close()


def resumen(ruta: Path, tablas_contadas: tuple[str, ...]) -> dict:
    """Tablas, versión del esquema, personal activo y conteo de registros de un respaldo."""
    c = _solo_lectura(ruta)
    try:
        tablas = {f[0] for f in c.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        datos = {"tablas": tablas, "version": c.execute("PRAGMA user_version").fetchone()[0]}
        if "personal" in tablas:
            datos["personal_activo"] = c.execute("SELECT COUNT(*) FROM personal WHERE activo = 1").fetchone()[0]
        for t in tablas_contadas:
            if t in tablas:
                datos[t] = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        return datos
    finally:
        c.close()


def cargar_desde(conn: sqlite3.Connection, origen: Path) -> None:
    """Reemplaza el contenido de la base abierta por el del archivo ``origen`` y lo pone al día."""
    fuente = _solo_lectura(origen)
    try:
        fuente.backup(conn)
    finally:
        fuente.close()
    preparar(conn)
    migraciones.migrar(conn)  # un respaldo antiguo se pone al día
    semillas.sembrar(conn)
