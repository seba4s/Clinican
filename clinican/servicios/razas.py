"""Catálogo de razas. Leer: todos. Crear o editar: solo la administradora,
salvo la raza escrita a mano al registrar una mascota (todo el personal)."""

from __future__ import annotations

import sqlite3

from clinican.datos import repo_auditoria, repo_razas
from clinican.datos.conexion import transaccion
from clinican.dominio.catalogos import ESPECIES, TAMANOS, nombre_tamano
from clinican.dominio.errores import DatoInvalido, NoEncontrado
from clinican.dominio.permisos import Accion
from clinican.servicios.base import Sesion, requerir


def listar(conn: sqlite3.Connection, solo_activas: bool = True) -> list[sqlite3.Row]:
    return repo_razas.listar(conn, solo_activas)


LARGO_MAX_NOMBRE = 60


def _validar(nombre: str, tamano: str | None, especie: str | None = "PERRO") -> tuple[str, str | None]:
    nombre = " ".join((nombre or "").split())
    if not nombre:
        raise DatoInvalido("Escriba el nombre de la raza.")
    if len(nombre) > LARGO_MAX_NOMBRE:
        raise DatoInvalido(f"El nombre de la raza no puede tener más de {LARGO_MAX_NOMBRE} letras.")
    if tamano is not None and tamano not in TAMANOS:
        raise DatoInvalido("El tamaño de la raza debe ser pequeña, mediana, grande o «se elige por mascota».")
    if especie is not None and especie not in ESPECIES:
        raise DatoInvalido("La especie debe ser perro o gato.")
    return nombre, tamano


def _detalle(nombre, tamano, pelaje, especie) -> str:
    return (f"{nombre} — {ESPECIES.get(especie, especie)} — {nombre_tamano(tamano)} — "
            f"pelaje complicado: {'sí' if pelaje else 'no'}")


def crear(conn, sesion: Sesion, nombre: str, tamano: str | None, pelaje_complicado: bool,
          especie: str = "PERRO") -> int:
    requerir(conn, sesion, Accion.CAMBIAR_CONFIGURACION)
    nombre, tamano = _validar(nombre, tamano, especie)
    with transaccion(conn):
        if repo_razas.por_nombre(conn, nombre):
            raise DatoInvalido(f"Ya existe la raza «{nombre}».")
        nueva = repo_razas.insertar(conn, nombre, tamano, pelaje_complicado, especie)
        repo_auditoria.registrar(conn, sesion.personal_id, "CREAR_RAZA", "razas", nueva,
                                 _detalle(nombre, tamano, pelaje_complicado, especie))
    return nueva


def obtener_o_crear_escrita(conn, sesion: Sesion, nombre: str, especie: str) -> sqlite3.Row:
    """Raza escrita a mano al registrar una mascota (ADMIN y PERSONAL).

    Si ya existe (sin importar tildes ni mayúsculas) se usa esa. Si no, se crea sin
    tamaño, así que cada mascota de esa raza lleva su propio tamaño y pelaje, como el
    mestizo. La administradora puede completarla después en Configuración › Razas.
    Debe llamarse dentro de una transacción.
    """
    nombre, _ = _validar(nombre, None, especie)
    existente = repo_razas.por_nombre(conn, nombre)
    if existente is not None:
        return existente
    nueva = repo_razas.insertar(conn, nombre, None, False, especie)
    repo_auditoria.registrar(conn, sesion.personal_id, "CREAR_RAZA", "razas", nueva,
                             _detalle(nombre, None, False, especie) + " — escrita al registrar una mascota")
    return repo_razas.por_id(conn, nueva)


def editar(conn, sesion: Sesion, raza_id: int, nombre: str, tamano: str | None,
           pelaje_complicado: bool, activa: bool = True, especie: str | None = None) -> None:
    requerir(conn, sesion, Accion.CAMBIAR_CONFIGURACION)
    nombre, tamano = _validar(nombre, tamano, especie)
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
        repo_razas.actualizar(conn, raza_id, nombre, tamano, pelaje_complicado, activa, especie)
        repo_auditoria.registrar(
            conn, sesion.personal_id, "EDITAR_RAZA", "razas", raza_id,
            f"{antes['nombre']} ({nombre_tamano(antes['tamano'])}, complicado={antes['pelaje_complicado']}, "
            f"activa={antes['activa']}) → {nombre} ({nombre_tamano(tamano)}, complicado={int(pelaje_complicado)}, "
            f"activa={int(activa)})",
        )
