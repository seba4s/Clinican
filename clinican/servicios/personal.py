"""Gestión del personal (solo la administradora, salvo la lista de personal activo)."""

from __future__ import annotations

import sqlite3

from clinican.datos import repo_auditoria, repo_personal
from clinican.datos.conexion import transaccion
from clinican.dominio import seguridad
from clinican.dominio.errores import CredencialesInvalidas, DatoInvalido, NoEncontrado
from clinican.dominio.permisos import ADMIN, PERSONAL, Accion
from clinican.servicios.base import Sesion, requerir

CARGOS_SUGERIDOS = ["Jefe", "Asistente de peluquería", "Médica veterinaria", "Auxiliar"]
LARGO_MAX_NOMBRE = 60


def validar_datos_persona(nombre: str, cargo: str) -> tuple[str, str]:
    nombre = " ".join((nombre or "").split())
    cargo = " ".join((cargo or "").split())
    if not nombre:
        raise DatoInvalido("Escriba el nombre de la persona.")
    if len(nombre) > LARGO_MAX_NOMBRE:
        raise DatoInvalido(f"El nombre no puede tener más de {LARGO_MAX_NOMBRE} letras.")
    if not cargo:
        raise DatoInvalido("Escriba o elija el cargo de la persona.")
    return nombre, cargo


def _obtener(conn: sqlite3.Connection, personal_id: int) -> sqlite3.Row:
    fila = repo_personal.por_id(conn, personal_id)
    if fila is None:
        raise NoEncontrado("No se encontró a esa persona.")
    return fila


def _nombre_libre(conn: sqlite3.Connection, nombre: str, excepto_id: int | None = None) -> None:
    otra = repo_personal.por_nombre(conn, nombre)
    if otra is not None and otra["id"] != excepto_id:
        raise DatoInvalido(f"Ya existe una persona llamada «{otra['nombre']}». Use otro nombre.")


def listar_activos(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Lista para «¿Quién agenda?» y para el inicio de sesión. Disponible para todos."""
    return repo_personal.listar(conn, solo_activos=True)


def listar_todos(conn: sqlite3.Connection, sesion: Sesion) -> list[sqlite3.Row]:
    requerir(conn, sesion, Accion.GESTIONAR_PERSONAL)
    return repo_personal.listar(conn)


def crear(conn: sqlite3.Connection, sesion: Sesion, nombre: str, cargo: str, pin: str) -> int:
    requerir(conn, sesion, Accion.GESTIONAR_PERSONAL)
    nombre, cargo = validar_datos_persona(nombre, cargo)
    hash_pin, sal = seguridad.generar_hash(pin)
    with transaccion(conn):
        _nombre_libre(conn, nombre)
        nuevo_id = repo_personal.insertar(conn, nombre, cargo, PERSONAL, hash_pin, sal)
        repo_auditoria.registrar(conn, sesion.personal_id, "CREAR_PERSONAL", "personal", nuevo_id, f"{nombre} ({cargo})")
    return nuevo_id


def editar(conn: sqlite3.Connection, sesion: Sesion, personal_id: int, nombre: str, cargo: str) -> None:
    requerir(conn, sesion, Accion.GESTIONAR_PERSONAL)
    nombre, cargo = validar_datos_persona(nombre, cargo)
    with transaccion(conn):
        antes = _obtener(conn, personal_id)
        _nombre_libre(conn, nombre, excepto_id=personal_id)
        repo_personal.actualizar_datos(conn, personal_id, nombre, cargo)
        repo_auditoria.registrar(
            conn, sesion.personal_id, "EDITAR_PERSONAL", "personal", personal_id,
            f"{antes['nombre']} ({antes['cargo']}) → {nombre} ({cargo})",
        )
    if personal_id == sesion.personal_id:
        sesion.nombre, sesion.cargo = nombre, cargo


def desactivar(conn: sqlite3.Connection, sesion: Sesion, personal_id: int) -> None:
    requerir(conn, sesion, Accion.GESTIONAR_PERSONAL)
    with transaccion(conn):
        fila = _obtener(conn, personal_id)
        if fila["rol"] == ADMIN:
            raise DatoInvalido(
                "No se puede desactivar a la administradora. "
                "Primero transfiera el rol de administrador a otra persona."
            )
        repo_personal.cambiar_activo(conn, personal_id, False)
        repo_auditoria.registrar(conn, sesion.personal_id, "DESACTIVAR_PERSONAL", "personal", personal_id, fila["nombre"])


def reactivar(conn: sqlite3.Connection, sesion: Sesion, personal_id: int) -> None:
    requerir(conn, sesion, Accion.GESTIONAR_PERSONAL)
    with transaccion(conn):
        fila = _obtener(conn, personal_id)
        if fila["rol"] == ADMIN and repo_personal.contar_admins_activos(conn) > 0:
            # No debería ocurrir; se protege el «un solo ADMIN activo».
            repo_personal.cambiar_rol(conn, personal_id, PERSONAL)
        repo_personal.cambiar_activo(conn, personal_id, True)
        repo_auditoria.registrar(conn, sesion.personal_id, "REACTIVAR_PERSONAL", "personal", personal_id, fila["nombre"])


def cambiar_pin_de(conn: sqlite3.Connection, sesion: Sesion, personal_id: int, pin_nuevo: str) -> None:
    requerir(conn, sesion, Accion.GESTIONAR_PERSONAL)
    hash_pin, sal = seguridad.generar_hash(pin_nuevo)
    with transaccion(conn):
        fila = _obtener(conn, personal_id)
        repo_personal.actualizar_pin(conn, personal_id, hash_pin, sal)
        repo_auditoria.registrar(conn, sesion.personal_id, "CAMBIAR_PIN_DE_OTRO", "personal", personal_id, fila["nombre"])


def transferir_administracion(
    conn: sqlite3.Connection, sesion: Sesion, nuevo_admin_id: int, mi_pin: str
) -> None:
    """La jefe entrega el rol ADMIN a otra persona activa y queda como PERSONAL."""
    requerir(conn, sesion, Accion.GESTIONAR_PERSONAL)
    yo = _obtener(conn, sesion.personal_id)
    if not seguridad.verificar_pin(mi_pin, yo["pin_hash"], yo["pin_sal"]):
        raise CredencialesInvalidas("Su PIN no es correcto. La administración no se transfirió.")
    with transaccion(conn):
        destino = _obtener(conn, nuevo_admin_id)
        if destino["id"] == sesion.personal_id:
            raise DatoInvalido("Elija a otra persona para entregarle la administración.")
        if not destino["activo"]:
            raise DatoInvalido("Solo se puede entregar la administración a una persona activa.")
        # Primero se quita el rol propio para respetar el índice de un solo ADMIN.
        repo_personal.cambiar_rol(conn, sesion.personal_id, PERSONAL)
        repo_personal.cambiar_rol(conn, destino["id"], ADMIN)
        repo_auditoria.registrar(
            conn, sesion.personal_id, "TRANSFERIR_ADMINISTRACION", "personal", destino["id"],
            f"{yo['nombre']} → {destino['nombre']}",
        )
    sesion.rol = PERSONAL
