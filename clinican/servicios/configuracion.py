"""Lectura y cambio de la configuración (cambiar: solo la administradora)."""

from __future__ import annotations

import sqlite3

from clinican.datos import repo_auditoria, repo_config
from clinican.datos.conexion import transaccion
from clinican.dominio import config_claves
from clinican.dominio.permisos import Accion
from clinican.servicios.base import Sesion, requerir


def valores(conn: sqlite3.Connection) -> dict[str, str]:
    """Todos pueden leer la configuración (precios, datos de pago, etc.)."""
    return repo_config.todas(conn)


def guardar(conn: sqlite3.Connection, sesion: Sesion, cambios: dict[str, str]) -> list[str]:
    """Valida y guarda los cambios. Devuelve las claves que cambiaron."""
    requerir(conn, sesion, Accion.CAMBIAR_CONFIGURACION)
    normalizados = {clave: config_claves.normalizar(clave, valor) for clave, valor in cambios.items()}
    cambiadas: list[str] = []
    with transaccion(conn):
        actuales = repo_config.todas(conn)
        for clave, valor in normalizados.items():
            anterior = actuales.get(clave)
            if anterior == valor:
                continue
            repo_config.guardar(conn, clave, valor)
            repo_auditoria.registrar(
                conn, sesion.personal_id, "CAMBIAR_CONFIGURACION", "config", None,
                f"{clave}: {anterior} → {valor}",
            )
            cambiadas.append(clave)
    return cambiadas
