"""Consulta del registro de auditoría (solo la administradora)."""

from __future__ import annotations

import sqlite3

from clinican.datos import repo_auditoria
from clinican.dominio.permisos import Accion
from clinican.servicios.base import Sesion, requerir


def consultar(
    conn: sqlite3.Connection,
    sesion: Sesion,
    personal_id: int | None = None,
    desde: str | None = None,
    hasta: str | None = None,
    texto: str | None = None,
    limite: int = 500,
) -> list[sqlite3.Row]:
    requerir(conn, sesion, Accion.VER_AUDITORIA)
    return repo_auditoria.listar(conn, personal_id, desde, hasta, texto, limite)
