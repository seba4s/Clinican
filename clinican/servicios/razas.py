"""Catálogo de razas. Leer: todos. Crear o editar: solo la administradora."""

from __future__ import annotations

import sqlite3

from clinican.datos import repo_auditoria, repo_razas
from clinican.datos.conexion import transaccion
from clinican.dominio.catalogos import TAMANOS, nombre_tamano
from clinican.dominio.errores import DatoInvalido, NoEncontrado
from clinican.dominio.permisos import Accion
from clinican.servicios.base import Sesion, requerir


def listar(conn: sqlite3.Connection, solo_activas: bool = True) -> list[sqlite3.Row]:
    return repo_razas.listar(conn, solo_activas)


def _validar(nombre: str, tamano: str | None) -> tuple[str, str | None]:
    nombre = " ".join((nombre or "").split())
    if not nombre:
        raise DatoInvalido("Escriba el nombre de la raza.")
    if tamano is not None and tamano not in TAMANOS:
        raise DatoInvalido("El tamaño de la raza debe ser pequeña, mediana, grande o «se elige por mascota».")
    return nombre, tamano


def crear(conn, sesion: Sesion, nombre: str, tamano: str | None, pelaje_complicado: bool) -> int:
    requerir(conn, sesion, Accion.CAMBIAR_CONFIGURACION)
    nombre, tamano = _validar(nombre, tamano)
    with transaccion(conn):
        if repo_razas.por_nombre(conn, nombre):
            raise DatoInvalido(f"Ya existe la raza «{nombre}».")
        nueva = repo_razas.insertar(conn, nombre, tamano, pelaje_complicado)
        repo_auditoria.registrar(conn, sesion.personal_id, "CREAR_RAZA", "razas", nueva,
                                 f"{nombre} — {nombre_tamano(tamano)} — pelaje complicado: {'sí' if pelaje_complicado else 'no'}")
    return nueva


def editar(conn, sesion: Sesion, raza_id: int, nombre: str, tamano: str | None,
           pelaje_complicado: bool, activa: bool = True) -> None:
    requerir(conn, sesion, Accion.CAMBIAR_CONFIGURACION)
    nombre, tamano = _validar(nombre, tamano)
    with transaccion(conn):
        antes = repo_razas.por_id(conn, raza_id)
        if antes is None:
            raise NoEncontrado("No se encontró la raza.")
        otra = repo_razas.por_nombre(conn, nombre)
        if otra is not None and otra["id"] != raza_id:
            raise DatoInvalido(f"Ya existe la raza «{nombre}».")
        if tamano is None and antes["tamano"] is not None:
            afectadas = repo_razas.mascotas_sin_tamano_si_quita(conn, raza_id)
            if afectadas:
                raise DatoInvalido(
                    f"Hay {afectadas} mascota(s) de esta raza sin tamaño propio. "
                    "Primero asígneles un tamaño en su ficha, o deje un tamaño para la raza."
                )
        repo_razas.actualizar(conn, raza_id, nombre, tamano, pelaje_complicado, activa)
        repo_auditoria.registrar(
            conn, sesion.personal_id, "EDITAR_RAZA", "razas", raza_id,
            f"{antes['nombre']} ({nombre_tamano(antes['tamano'])}, complicado={antes['pelaje_complicado']}, "
            f"activa={antes['activa']}) → {nombre} ({nombre_tamano(tamano)}, complicado={int(pelaje_complicado)}, "
            f"activa={int(activa)})",
        )
