"""Registro de auditoría: qué se hizo y cuándo (no hay "quién": un solo perfil).

``auditar`` debe llamarse dentro de la misma transacción que la escritura.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from clinican.datos import repo_auditoria
from clinican.dominio.entidades import RegistroAuditoria


def auditar(
    con, ahora: datetime, accion: str, entidad: str, entidad_id: int | None, **detalle: Any
) -> None:
    repo_auditoria.registrar(con, ahora, accion, entidad, entidad_id, detalle)


def historial(con, entidad: str | None = None, entidad_id: int | None = None) -> list[RegistroAuditoria]:
    return repo_auditoria.listar(con, entidad, entidad_id)
