"""Tabla ``auditoria``: acciones sensibles (RN-01)."""

from __future__ import annotations

import sqlite3

from clinican.dominio.formato import sin_tildes


def registrar(conn: sqlite3.Connection, personal_id: int | None, accion: str, entidad: str,
              entidad_id: int | None = None, detalle: str | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO auditoria (personal_id, accion, entidad, entidad_id, detalle) VALUES (?, ?, ?, ?, ?)",
        (personal_id, accion, entidad, entidad_id, detalle),
    )
    return cur.lastrowid


def listar(conn: sqlite3.Connection, personal_id: int | None = None, desde: str | None = None,
           hasta: str | None = None, texto: str | None = None, limite: int = 500) -> list[sqlite3.Row]:
    """Del más reciente al más antiguo. ``desde``/``hasta`` son fechas AAAA-MM-DD inclusivas."""
    condiciones, parametros = [], []
    if personal_id is not None:
        condiciones.append("a.personal_id = ?")
        parametros.append(personal_id)
    if desde:
        condiciones.append("substr(a.ts, 1, 10) >= ?")
        parametros.append(desde)
    if hasta:
        condiciones.append("substr(a.ts, 1, 10) <= ?")
        parametros.append(hasta)
    if texto:
        condiciones.append("(sin_tildes(a.detalle) LIKE ? OR sin_tildes(a.accion) LIKE ? OR sin_tildes(p.nombre) LIKE ?)")
        patron = f"%{sin_tildes(texto.strip())}%"
        parametros += [patron, patron, patron]
    donde = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    return conn.execute(
        f"""SELECT a.*, COALESCE(p.nombre, 'Sistema') AS persona
            FROM auditoria a LEFT JOIN personal p ON p.id = a.personal_id
            {donde} ORDER BY a.id DESC LIMIT ?""",
        (*parametros, limite),
    ).fetchall()
