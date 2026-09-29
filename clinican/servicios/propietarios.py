"""Casos de uso de propietarios y mascotas (ADMIN y PERSONAL)."""

from __future__ import annotations

import sqlite3
from datetime import date

from clinican.datos import repo_auditoria, repo_propietarios as repo, repo_razas
from clinican.datos.conexion import transaccion
from clinican.dominio import mascotas as reglas_mascota
from clinican.dominio.errores import DatoInvalido, NoEncontrado
from clinican.dominio.permisos import Accion
from clinican.dominio.propietarios import validar_propietario
from clinican.servicios.base import Sesion, requerir

_P = Accion.GESTIONAR_PROPIETARIOS

# ------------------------------------------------------------ propietarios


def buscar(conn: sqlite3.Connection, sesion: Sesion, texto: str) -> list[sqlite3.Row]:
    requerir(conn, sesion, _P)
    return repo.buscar(conn, texto)


def obtener(conn: sqlite3.Connection, sesion: Sesion, propietario_id: int) -> sqlite3.Row:
    requerir(conn, sesion, _P)
    fila = repo.propietario(conn, propietario_id)
    if fila is None:
        raise NoEncontrado("No se encontró el propietario.")
    return fila


def _cedula_libre(conn, cedula: str, excepto_id: int | None = None) -> None:
    otro = repo.propietario_por_cedula(conn, cedula)
    if otro is not None and otro["id"] != excepto_id:
        raise DatoInvalido(f"Ya existe un propietario con la cédula {cedula}: {otro['nombre']}.")


def crear(conn, sesion: Sesion, nombre, cedula, celular1, celular2, direccion) -> int:
    requerir(conn, sesion, _P)
    datos = validar_propietario(nombre, cedula, celular1, celular2, direccion)
    with transaccion(conn):
        _cedula_libre(conn, datos["cedula"])
        nuevo = repo.insertar_propietario(conn, datos)
        repo_auditoria.registrar(conn, sesion.personal_id, "CREAR_PROPIETARIO", "propietarios", nuevo,
                                 f"{datos['nombre']} — C.C. {datos['cedula']}")
    return nuevo


def editar(conn, sesion: Sesion, propietario_id: int, nombre, cedula, celular1, celular2, direccion) -> None:
    requerir(conn, sesion, _P)
    datos = validar_propietario(nombre, cedula, celular1, celular2, direccion)
    with transaccion(conn):
        antes = obtener(conn, sesion, propietario_id)
        _cedula_libre(conn, datos["cedula"], excepto_id=propietario_id)
        repo.actualizar_propietario(conn, propietario_id, datos)
        cambios = [f"{c}: {antes[c]} → {datos[c]}" for c in datos if (antes[c] or None) != (datos[c] or None)]
        if cambios:
            repo_auditoria.registrar(conn, sesion.personal_id, "EDITAR_PROPIETARIO", "propietarios",
                                     propietario_id, "; ".join(cambios))


def fijar_requiere_nuevo_abono(conn, sesion: Sesion, propietario_id: int, valor: bool) -> None:
    requerir(conn, sesion, _P)
    with transaccion(conn):
        fila = obtener(conn, sesion, propietario_id)
        if bool(fila["requiere_nuevo_abono"]) == bool(valor):
            return
        repo.fijar_requiere_nuevo_abono(conn, propietario_id, valor)
        repo_auditoria.registrar(conn, sesion.personal_id, "MARCA_NUEVO_ABONO", "propietarios", propietario_id,
                                 f"{fila['nombre']}: requiere nuevo abono = {'sí' if valor else 'no'}")


# ---------------------------------------------------------------- mascotas


def perfil(fila: sqlite3.Row) -> dict:
    """Tamaño y pelaje efectivos de una mascota (fila de ``repo.mascota``)."""
    return {
        "tamano": reglas_mascota.tamano_efectivo(fila["raza_tamano"], fila["tamano_manual"]),
        "pelaje_complicado": reglas_mascota.pelaje_complicado_efectivo(
            fila["raza_pelaje_complicado"], fila["pelaje_complicado_manual"]
        ),
    }


def mascotas(conn, sesion: Sesion, propietario_id: int, incluir_inactivas: bool = True) -> list[sqlite3.Row]:
    requerir(conn, sesion, _P)
    return repo.mascotas_de(conn, propietario_id, incluir_inactivas)


def mascota(conn, sesion: Sesion, mascota_id: int) -> sqlite3.Row:
    requerir(conn, sesion, _P)
    fila = repo.mascota(conn, mascota_id)
    if fila is None:
        raise NoEncontrado("No se encontró la mascota.")
    return fila


def _datos_mascota(conn, nombre, raza_id, tamano_manual, pelaje_manual, edad_anios, edad_meses,
                   fecha_ultima_visita, observaciones) -> dict:
    raza = repo_razas.por_id(conn, raza_id) if raza_id else None
    if raza is None:
        raise DatoInvalido("Elija la raza de la mascota.")
    datos = reglas_mascota.validar_mascota(
        nombre, raza["tamano"], tamano_manual or None, pelaje_manual,
        reglas_mascota.entero_opcional(edad_anios, "La edad en años"),
        reglas_mascota.entero_opcional(edad_meses, "Los meses de edad"),
        fecha_ultima_visita or None,
    )
    datos["raza_id"] = raza["id"]
    datos["observaciones"] = (observaciones or "").strip() or None
    return datos


def crear_mascota(conn, sesion: Sesion, propietario_id: int, nombre, raza_id, tamano_manual=None,
                  pelaje_manual=None, edad_anios=None, edad_meses=None, fecha_ultima_visita=None,
                  observaciones=None) -> int:
    requerir(conn, sesion, _P)
    datos = _datos_mascota(conn, nombre, raza_id, tamano_manual, pelaje_manual, edad_anios, edad_meses,
                           fecha_ultima_visita, observaciones)
    with transaccion(conn):
        dueno = obtener(conn, sesion, propietario_id)
        if repo.mascota_con_nombre(conn, propietario_id, datos["nombre"]):
            raise DatoInvalido(f"{dueno['nombre']} ya tiene una mascota llamada «{datos['nombre']}».")
        nueva = repo.insertar_mascota(conn, propietario_id, datos)
        repo_auditoria.registrar(conn, sesion.personal_id, "CREAR_MASCOTA", "mascotas", nueva,
                                 f"{datos['nombre']} (dueño: {dueno['nombre']})")
    return nueva


def editar_mascota(conn, sesion: Sesion, mascota_id: int, nombre, raza_id, tamano_manual=None,
                   pelaje_manual=None, edad_anios=None, edad_meses=None, fecha_ultima_visita=None,
                   observaciones=None) -> None:
    requerir(conn, sesion, _P)
    datos = _datos_mascota(conn, nombre, raza_id, tamano_manual, pelaje_manual, edad_anios, edad_meses,
                           fecha_ultima_visita, observaciones)
    with transaccion(conn):
        antes = mascota(conn, sesion, mascota_id)
        otra = repo.mascota_con_nombre(conn, antes["propietario_id"], datos["nombre"])
        if otra is not None and otra["id"] != mascota_id:
            raise DatoInvalido(f"El propietario ya tiene otra mascota llamada «{datos['nombre']}».")
        repo.actualizar_mascota(conn, mascota_id, datos)
        cambios = [f"{c}: {antes[c]} → {datos[c]}" for c in datos if antes[c] != datos[c]]
        if cambios:
            repo_auditoria.registrar(conn, sesion.personal_id, "EDITAR_MASCOTA", "mascotas", mascota_id,
                                     "; ".join(cambios))


def fijar_mascota_activa(conn, sesion: Sesion, mascota_id: int, activa: bool) -> None:
    requerir(conn, sesion, _P)
    with transaccion(conn):
        fila = mascota(conn, sesion, mascota_id)
        repo.fijar_mascota_activa(conn, mascota_id, activa)
        repo_auditoria.registrar(conn, sesion.personal_id, "ACTIVAR_MASCOTA" if activa else "DESACTIVAR_MASCOTA",
                                 "mascotas", mascota_id, fila["nombre"])


def corregir_ultima_visita(conn, sesion: Sesion, mascota_id: int, fecha: str | None) -> None:
    """RN-14: la fecha de última visita siempre se puede corregir a mano."""
    requerir(conn, sesion, _P)
    nueva = reglas_mascota.validar_fecha(fecha, "La fecha de última visita") if fecha else None
    if nueva and nueva > date.today().isoformat():
        raise DatoInvalido("La fecha de última visita no puede ser futura.")
    with transaccion(conn):
        fila = mascota(conn, sesion, mascota_id)
        repo.fijar_ultima_visita(conn, mascota_id, nueva)
        repo_auditoria.registrar(conn, sesion.personal_id, "CORREGIR_ULTIMA_VISITA", "mascotas", mascota_id,
                                 f"{fila['nombre']}: {fila['fecha_ultima_visita']} → {nueva}")


def historial(conn, sesion: Sesion, mascota_id: int) -> list[sqlite3.Row]:
    requerir(conn, sesion, _P)
    return repo.historial_servicios(conn, mascota_id)
