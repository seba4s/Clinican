"""Casos de uso de la autorización de datos personales (Ley 1581 de 2012).

El personal registra que el dueño autorizó (o revocó) el tratamiento de sus
datos y en qué fecha. El historial no se borra: cada cambio es un registro
nuevo y queda en la auditoría. Por decisión del negocio, la autorización solo
se registra y se consulta: no bloquea turnos ni recordatorios.
"""

from __future__ import annotations

from datetime import date, datetime

from clinican.datos import repo_autorizaciones, repo_clientes
from clinican.datos.conexion import transaccion
from clinican.dominio.agenda import ZONA
from clinican.dominio.autorizaciones import AutorizacionDatos, validar_fecha, vigente
from clinican.dominio.errores import DatoInvalido, NoEncontrado, OperacionNoPermitida
from clinican.servicios.auditoria import auditar


def _propietario(con, propietario_id: int):
    propietario = repo_clientes.obtener_propietario(con, propietario_id)
    if propietario is None:
        raise NoEncontrado(f"No existe el propietario {propietario_id}")
    return propietario


def _medio(valor) -> str:
    if valor is None:
        return ""
    if not isinstance(valor, str):
        raise DatoInvalido("El medio de la autorización debe ser un texto")
    return " ".join(valor.split())


def _registrar(con, propietario_id: int, otorgada: bool, fecha: date, medio, ahora: datetime):
    if ahora.tzinfo is None or ahora.utcoffset() is None:
        raise ValueError("ahora debe tener zona horaria")
    fecha = validar_fecha(fecha, ahora.astimezone(ZONA).date())
    medio = _medio(medio)
    with transaccion(con):
        propietario = _propietario(con, propietario_id)
        if not propietario.activo:
            raise OperacionNoPermitida(f"El propietario {propietario.nombre} está inactivo")
        rid = repo_autorizaciones.insertar(con, propietario.id, otorgada, fecha, medio, ahora)
        auditar(
            con, ahora, "autorizar_datos" if otorgada else "revocar_datos", "propietario",
            propietario.id, fecha=fecha.isoformat(), medio=medio, registro_id=rid,
        )


def registrar_autorizacion(
    con, propietario_id: int, fecha: date, *, ahora: datetime, medio: str = ""
) -> AutorizacionDatos:
    """El dueño autorizó el tratamiento de sus datos en ``fecha`` (por ejemplo, formato firmado)."""
    _registrar(con, propietario_id, True, fecha, medio, ahora)
    return autorizacion_vigente(con, propietario_id)


def revocar_autorizacion(
    con, propietario_id: int, fecha: date, *, ahora: datetime, medio: str = ""
) -> None:
    """El dueño retiró la autorización en ``fecha``."""
    _registrar(con, propietario_id, False, fecha, medio, ahora)


def autorizacion_vigente(con, propietario_id: int) -> AutorizacionDatos | None:
    """La autorización vigente del propietario, o None si nunca autorizó o la revocó."""
    _propietario(con, propietario_id)
    ultimo = repo_autorizaciones.ultimo(con, propietario_id)
    return vigente([] if ultimo is None else [ultimo])


def historial(con, propietario_id: int) -> list[AutorizacionDatos]:
    _propietario(con, propietario_id)
    return repo_autorizaciones.historial(con, propietario_id)
