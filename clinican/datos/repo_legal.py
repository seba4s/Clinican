"""Tablas ``textos_legales`` y ``consentimientos`` (RN-15)."""

from __future__ import annotations

import sqlite3


def vigente(conn: sqlite3.Connection, tipo: str) -> sqlite3.Row:
    return conn.execute(
        "SELECT * FROM textos_legales WHERE tipo = ? AND vigente = 1 ORDER BY version DESC LIMIT 1", (tipo,)
    ).fetchone()


def versiones(conn: sqlite3.Connection, tipo: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM textos_legales WHERE tipo = ? ORDER BY version DESC", (tipo,)).fetchall()


def insertar_version(conn: sqlite3.Connection, tipo: str, contenido: str) -> tuple[int, int]:
    """Crea la versión siguiente como vigente y deja las demás como anteriores. Devuelve (id, versión)."""
    version = conn.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM textos_legales WHERE tipo = ?",
                           (tipo,)).fetchone()[0]
    conn.execute("UPDATE textos_legales SET vigente = 0 WHERE tipo = ?", (tipo,))
    cur = conn.execute("INSERT INTO textos_legales (tipo, version, contenido, vigente) VALUES (?, ?, ?, 1)",
                       (tipo, version, contenido))
    return cur.lastrowid, version


def insertar_consentimiento(conn: sqlite3.Connection, propietario_id: int, mascota_id: int | None, tipo: str,
                            texto_id: int, texto_mostrado: str, condiciones: str | None, registrado_por: int,
                            origen: str = "LOCAL") -> int:
    cur = conn.execute(
        """INSERT INTO consentimientos (propietario_id, mascota_id, tipo, texto_id, texto_mostrado, condiciones,
                                        registrado_por, origen)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (propietario_id, mascota_id, tipo, texto_id, texto_mostrado, condiciones, registrado_por, origen),
    )
    return cur.lastrowid


def consentimientos_de(conn: sqlite3.Connection, propietario_id: int) -> list[sqlite3.Row]:
    """Del más reciente al más antiguo, con la versión del texto y si esa versión sigue vigente."""
    return conn.execute(
        """SELECT c.*, t.version, t.vigente AS texto_vigente, p.nombre AS registrado_por_nombre,
                  m.nombre AS mascota_nombre
           FROM consentimientos c
           JOIN textos_legales t ON t.id = c.texto_id
           JOIN personal p ON p.id = c.registrado_por
           LEFT JOIN mascotas m ON m.id = c.mascota_id
           WHERE c.propietario_id = ?
           ORDER BY c.aceptado_en DESC, c.id DESC""",
        (propietario_id,),
    ).fetchall()


def tipos_aceptados_vigentes(conn: sqlite3.Connection, propietario_id: int) -> set[str]:
    filas = conn.execute(
        """SELECT DISTINCT c.tipo FROM consentimientos c JOIN textos_legales t ON t.id = c.texto_id
           WHERE c.propietario_id = ? AND c.mascota_id IS NULL AND t.vigente = 1""",
        (propietario_id,),
    ).fetchall()
    return {f["tipo"] for f in filas}
