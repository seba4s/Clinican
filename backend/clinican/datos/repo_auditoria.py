"""Repositorio de la tabla auditoria."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from clinican.datos._util import a_texto, de_texto
from clinican.dominio.entidades import RegistroAuditoria


def registrar(
    con: sqlite3.Connection,
    cuando: datetime,
    accion: str,
    entidad: str,
    entidad_id: int | None,
    detalle: dict[str, Any],
) -> int:
    texto = json.dumps(detalle, ensure_ascii=False, sort_keys=True, default=str)
    cur = con.execute(
        "INSERT INTO auditoria (cuando, accion, entidad, entidad_id, detalle) "
        "VALUES (?, ?, ?, ?, ?)",
        (a_texto(cuando), accion, entidad, entidad_id, texto),
    )
    return cur.lastrowid


def listar(
    con: sqlite3.Connection,
    entidad: str | None = None,
    entidad_id: int | None = None,
) -> list[RegistroAuditoria]:
    filas = con.execute(
        "SELECT id, cuando, accion, entidad, entidad_id, detalle FROM auditoria "
        "WHERE (? IS NULL OR entidad = ?) AND (? IS NULL OR entidad_id = ?) ORDER BY id",
        (entidad, entidad, entidad_id, entidad_id),
    ).fetchall()
    return [
        RegistroAuditoria(f[0], de_texto(f[1]), f[2], f[3], f[4], json.loads(f[5])) for f in filas
    ]
