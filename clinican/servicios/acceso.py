"""Primer arranque, inicio de sesión y cambio del propio PIN."""

from __future__ import annotations

import sqlite3

from clinican.datos import repo_auditoria, repo_personal
from clinican.datos.conexion import transaccion
from clinican.dominio import seguridad
from clinican.dominio.errores import CredencialesInvalidas, DatoInvalido
from clinican.dominio.permisos import ADMIN, Accion
from clinican.servicios.base import Sesion, requerir
from clinican.servicios.personal import validar_datos_persona


def necesita_primer_arranque(conn: sqlite3.Connection) -> bool:
    return repo_personal.contar(conn) == 0


def crear_administradora_inicial(conn: sqlite3.Connection, nombre: str, cargo: str, pin: str) -> Sesion:
    """Asistente del primer arranque: crea a la jefe como ADMIN."""
    nombre, cargo = validar_datos_persona(nombre, cargo)
    hash_pin, sal = seguridad.generar_hash(pin)
    with transaccion(conn):
        if repo_personal.contar(conn) > 0:
            raise DatoInvalido("El sistema ya tiene personal registrado; el asistente inicial no aplica.")
        nuevo_id = repo_personal.insertar(conn, nombre, cargo, ADMIN, hash_pin, sal)
        repo_auditoria.registrar(conn, nuevo_id, "PRIMER_ARRANQUE", "personal", nuevo_id, f"Administradora: {nombre}")
    return Sesion(nuevo_id, nombre, cargo, ADMIN)


def iniciar_sesion(conn: sqlite3.Connection, nombre: str, pin: str) -> Sesion:
    fila = repo_personal.por_nombre(conn, nombre or "")
    valido = (
        fila is not None
        and fila["activo"]
        and seguridad.verificar_pin(pin, fila["pin_hash"], fila["pin_sal"])
    )
    with transaccion(conn):
        if not valido:
            repo_auditoria.registrar(
                conn, fila["id"] if fila else None, "INICIO_SESION_FALLIDO", "personal",
                fila["id"] if fila else None, f"Usuario escrito: {nombre!r}",
            )
        else:
            repo_auditoria.registrar(conn, fila["id"], "INICIO_SESION", "personal", fila["id"])
    if not valido:
        raise CredencialesInvalidas("Usuario o PIN incorrecto. Revise e intente de nuevo.")
    return Sesion(fila["id"], fila["nombre"], fila["cargo"], fila["rol"])


def cerrar_sesion(conn: sqlite3.Connection, sesion: Sesion) -> None:
    with transaccion(conn):
        repo_auditoria.registrar(conn, sesion.personal_id, "CIERRE_SESION", "personal", sesion.personal_id)


def cambiar_mi_pin(conn: sqlite3.Connection, sesion: Sesion, pin_actual: str, pin_nuevo: str) -> None:
    requerir(conn, sesion, Accion.CAMBIAR_PIN_PROPIO)
    fila = repo_personal.por_id(conn, sesion.personal_id)
    if not seguridad.verificar_pin(pin_actual, fila["pin_hash"], fila["pin_sal"]):
        raise CredencialesInvalidas("El PIN actual no es correcto.")
    hash_pin, sal = seguridad.generar_hash(pin_nuevo)
    with transaccion(conn):
        repo_personal.actualizar_pin(conn, sesion.personal_id, hash_pin, sal)
        repo_auditoria.registrar(conn, sesion.personal_id, "CAMBIAR_PIN_PROPIO", "personal", sesion.personal_id)
