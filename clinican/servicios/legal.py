"""Textos legales con versiones y consentimientos (RN-15)."""

from __future__ import annotations

import json
import sqlite3

from clinican.datos import repo_auditoria, repo_config, repo_legal, repo_propietarios
from clinican.datos.conexion import transaccion
from clinican.dominio import legal as reglas
from clinican.dominio.catalogos import CONDICIONES, TIPOS_LEGALES
from clinican.dominio.errores import DatoInvalido, NoEncontrado
from clinican.dominio.formato import rellenar_texto
from clinican.dominio.permisos import Accion
from clinican.servicios.base import Sesion, requerir


def texto_vigente(conn: sqlite3.Connection, tipo: str) -> tuple[sqlite3.Row, str]:
    """Devuelve la fila vigente y el texto listo para mostrar (con valores de config)."""
    fila = repo_legal.vigente(conn, tipo)
    return fila, rellenar_texto(fila["contenido"], repo_config.todas(conn))


def versiones(conn, sesion: Sesion, tipo: str) -> list[sqlite3.Row]:
    requerir(conn, sesion, Accion.EDITAR_TEXTOS_LEGALES)
    return repo_legal.versiones(conn, tipo)


def nueva_version(conn, sesion: Sesion, tipo: str, contenido: str) -> int:
    """Crea una versión nueva. Las aceptaciones anteriores dejan de ser vigentes."""
    requerir(conn, sesion, Accion.EDITAR_TEXTOS_LEGALES)
    contenido = reglas.validar_texto_legal(tipo, contenido)
    with transaccion(conn):
        actual = repo_legal.vigente(conn, tipo)
        if actual["contenido"].strip() == contenido:
            raise DatoInvalido("El texto no cambió; no se creó una versión nueva.")
        _, version = repo_legal.insertar_version(conn, tipo, contenido)
        repo_auditoria.registrar(conn, sesion.personal_id, "NUEVA_VERSION_TEXTO_LEGAL", "textos_legales", None,
                                 f"{TIPOS_LEGALES[tipo]}: versión {actual['version']} → {version}")
    return version


# ------------------------------------------------------------ aceptaciones


def aceptar(conn, sesion: Sesion, propietario_id: int, tipos: list[str], origen: str = "LOCAL") -> None:
    """Registra la aceptación de términos y/o datos, con la versión vigente y la fecha."""
    requerir(conn, sesion, Accion.GESTIONAR_PROPIETARIOS)
    if not tipos:
        raise DatoInvalido("Marque al menos una casilla de aceptación.")
    for t in tipos:
        if t not in reglas.REQUERIDOS_PARA_TURNO:
            raise DatoInvalido("Aquí solo se aceptan los términos y la autorización de datos.")
    with transaccion(conn):
        dueno = repo_propietarios.propietario(conn, propietario_id)
        if dueno is None:
            raise NoEncontrado("No se encontró el propietario.")
        if dueno["provisional"]:
            raise DatoInvalido("Primero complete los datos del cliente (cédula y dirección) en la pestaña «Datos».")
        for t in tipos:
            fila, texto = texto_vigente(conn, t)
            repo_legal.insertar_consentimiento(conn, propietario_id, None, t, fila["id"], texto, None,
                                               sesion.personal_id, origen)
            repo_auditoria.registrar(conn, sesion.personal_id, "ACEPTAR_" + t, "propietarios", propietario_id,
                                     f"{dueno['nombre']} aceptó {TIPOS_LEGALES[t].lower()} v{fila['version']}")


def registrar_responsabilidad(conn, sesion: Sesion, mascota_id: int, condiciones: dict[str, bool],
                              origen: str = "LOCAL") -> int:
    """Declaración de responsabilidad por mascota difícil (con sus condiciones)."""
    requerir(conn, sesion, Accion.GESTIONAR_PROPIETARIOS)
    marcadas = reglas.validar_condiciones(condiciones)
    if not any(marcadas.values()):
        raise DatoInvalido("Marque al menos una condición de la mascota.")
    with transaccion(conn):
        mascota = repo_propietarios.mascota(conn, mascota_id)
        if mascota is None:
            raise NoEncontrado("No se encontró la mascota.")
        fila, texto = texto_vigente(conn, "RESPONSABILIDAD")
        nuevo = repo_legal.insertar_consentimiento(
            conn, mascota["propietario_id"], mascota_id, "RESPONSABILIDAD", fila["id"], texto,
            json.dumps(marcadas, ensure_ascii=False), sesion.personal_id, origen,
        )
        lista = ", ".join(CONDICIONES[c].lower() for c, v in marcadas.items() if v)
        repo_auditoria.registrar(conn, sesion.personal_id, "ACEPTAR_RESPONSABILIDAD", "mascotas", mascota_id,
                                 f"{mascota['nombre']}: {lista}")
    return nuevo


def historial(conn, sesion: Sesion, propietario_id: int) -> list[sqlite3.Row]:
    requerir(conn, sesion, Accion.GESTIONAR_PROPIETARIOS)
    return repo_legal.consentimientos_de(conn, propietario_id)


def estado(conn, propietario_id: int) -> dict[str, sqlite3.Row | None]:
    """Para cada tipo requerido: la aceptación más reciente de la versión vigente, o None."""
    resultado: dict[str, sqlite3.Row | None] = {t: None for t in reglas.REQUERIDOS_PARA_TURNO}
    for c in repo_legal.consentimientos_de(conn, propietario_id):
        if c["tipo"] in resultado and c["texto_vigente"] and resultado[c["tipo"]] is None and c["mascota_id"] is None:
            resultado[c["tipo"]] = c
    return resultado


def verificar_para_turno(conn, propietario_id: int) -> None:
    """RN-05 y RN-15: sin términos y datos aceptados (versión vigente) no hay turno."""
    faltan = reglas.faltantes_para_turno(repo_legal.tipos_aceptados_vigentes(conn, propietario_id))
    if faltan:
        raise DatoInvalido(reglas.mensaje_faltantes(faltan))
