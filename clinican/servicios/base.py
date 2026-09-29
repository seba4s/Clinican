"""Sesión de la persona que usa el programa y validación de permisos (RN-01)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from clinican.datos import repo_personal
from clinican.dominio.errores import PermisoDenegado
from clinican.dominio.permisos import ADMIN, Accion, puede


@dataclass
class Sesion:
    personal_id: int
    nombre: str
    cargo: str
    rol: str

    @property
    def es_admin(self) -> bool:
        return self.rol == ADMIN

    def puede(self, accion: Accion) -> bool:
        """Solo para mostrar u ocultar botones. La validación real es ``requerir``."""
        return puede(self.rol, accion)


def requerir(conn: sqlite3.Connection, sesion: Sesion | None, accion: Accion) -> None:
    """Verifica el permiso contra la base de datos (no contra lo que diga la pantalla).

    Relee el rol y el estado de la persona, de modo que si la jefe transfirió
    la administración o desactivó a alguien, el cambio aplica de inmediato.
    """
    if sesion is None:
        raise PermisoDenegado("Debe iniciar sesión.")
    fila = repo_personal.por_id(conn, sesion.personal_id)
    if fila is None or not fila["activo"]:
        raise PermisoDenegado("Su usuario no está activo. Hable con la administradora.")
    sesion.rol = fila["rol"]
    if not puede(fila["rol"], accion):
        raise PermisoDenegado(
            f"No tiene permiso para esta acción: {accion.value}. Solo la administradora puede hacerlo."
        )
