"""Fichas de servicio y sesiones de desenredado.

La ficha se crea automáticamente al marcar el turno ATENDIDO (ver
``agenda.marcar_atendido``) o con ``crear_ficha``. Su precio final se toma del
historial de precios vigente en la fecha del turno y queda guardado.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from clinican.datos import repo_agenda, repo_fichas
from clinican.datos.conexion import transaccion
from clinican.dominio.agenda import ZONA
from clinican.dominio.entidades import Ficha, SesionDesenredado, Turno
from clinican.dominio.errores import DatoInvalido, NoEncontrado, OperacionNoPermitida
from clinican.dominio.estados import EstadoTurno
from clinican.servicios.auditoria import auditar
from clinican.servicios.precios import precio_en_fecha

ESTADOS_CON_FICHA = frozenset({EstadoTurno.ATENDIDO, EstadoTurno.ENTREGADO})


class _SinCambio:
    def __repr__(self) -> str:
        return "SIN_CAMBIO"


SIN_CAMBIO: Any = _SinCambio()


def _texto(valor: Any, campo: str) -> str:
    if not isinstance(valor, str):
        raise DatoInvalido(f"El campo {campo} debe ser texto")
    return valor.strip()


def crear_ficha_en_transaccion(
    con,
    turno: Turno,
    ahora: datetime,
    servicios_realizados: str = "",
    detalles_corte: str = "",
    observaciones: str = "",
) -> int:
    """Crea la ficha del turno; debe llamarse dentro de una transacción abierta."""
    if turno.estado not in ESTADOS_CON_FICHA:
        raise OperacionNoPermitida("Solo se crea ficha para turnos atendidos o entregados")
    if repo_fichas.ficha_de_turno(con, turno.id) is not None:
        raise OperacionNoPermitida("El turno ya tiene ficha")
    campos = {
        "servicios_realizados": _texto(servicios_realizados, "servicios realizados"),
        "detalles_corte": _texto(detalles_corte, "detalles del corte"),
        "observaciones": _texto(observaciones, "observaciones"),
    }
    precio = precio_en_fecha(con, turno.categoria, turno.inicio.astimezone(ZONA).date())
    ficha_id = repo_fichas.insertar_ficha(
        con, turno_id=turno.id, precio_final=precio, creada_en=ahora, **campos
    )
    auditar(con, ahora, "crear", "ficha", ficha_id, turno_id=turno.id, precio_final=precio, **campos)
    return ficha_id


def obtener_ficha(con, ficha_id: int) -> Ficha:
    ficha = repo_fichas.obtener_ficha(con, ficha_id)
    if ficha is None:
        raise NoEncontrado(f"No existe la ficha {ficha_id}")
    return ficha


def ficha_de_turno(con, turno_id: int) -> Ficha | None:
    return repo_fichas.ficha_de_turno(con, turno_id)


def crear_ficha(
    con,
    turno_id: int,
    *,
    ahora: datetime,
    servicios_realizados: str = "",
    detalles_corte: str = "",
    observaciones: str = "",
) -> Ficha:
    with transaccion(con):
        turno = repo_agenda.obtener_turno(con, turno_id)
        if turno is None:
            raise NoEncontrado(f"No existe el turno {turno_id}")
        ficha_id = crear_ficha_en_transaccion(
            con, turno, ahora, servicios_realizados, detalles_corte, observaciones
        )
    return obtener_ficha(con, ficha_id)


def editar_ficha(
    con,
    ficha_id: int,
    *,
    ahora: datetime,
    servicios_realizados: Any = SIN_CAMBIO,
    detalles_corte: Any = SIN_CAMBIO,
    observaciones: Any = SIN_CAMBIO,
    precio_final: Any = SIN_CAMBIO,
) -> Ficha:
    """Edita la ficha. El precio final se puede corregir (entero de pesos > 0);
    la auditoría guarda el valor anterior y el nuevo."""
    cambios = {
        k: _texto(v, k)
        for k, v in {
            "servicios_realizados": servicios_realizados,
            "detalles_corte": detalles_corte,
            "observaciones": observaciones,
        }.items()
        if v is not SIN_CAMBIO
    }
    if precio_final is not SIN_CAMBIO:
        if isinstance(precio_final, bool) or not isinstance(precio_final, int) or precio_final <= 0:
            raise DatoInvalido("El precio final debe ser un entero de pesos mayor que cero")
        cambios["precio_final"] = precio_final
    with transaccion(con):
        anterior = obtener_ficha(con, ficha_id)
        repo_fichas.actualizar_ficha(con, ficha_id, **cambios)
        detalle = dict(cambios)
        if "precio_final" in cambios:
            detalle["precio_anterior"] = anterior.precio_final
        auditar(con, ahora, "editar", "ficha", ficha_id, **detalle)
    return obtener_ficha(con, ficha_id)


def registrar_sesion_desenredado(
    con, ficha_id: int, *, ahora: datetime, avance: str = "", porcentaje: int | None = None
) -> SesionDesenredado:
    """Agrega la siguiente sesión de desenredado de la mascota (fecha = día del turno)."""
    avance = _texto(avance, "avance")
    if porcentaje is not None and (
        isinstance(porcentaje, bool) or not isinstance(porcentaje, int) or not 0 <= porcentaje <= 100
    ):
        raise DatoInvalido("El porcentaje de avance debe ser un entero entre 0 y 100")
    with transaccion(con):
        ficha = obtener_ficha(con, ficha_id)
        turno = repo_agenda.obtener_turno(con, ficha.turno_id)
        numero = repo_fichas.siguiente_numero_sesion(con, turno.mascota_id)
        sesion_id = repo_fichas.insertar_sesion(
            con, mascota_id=turno.mascota_id, ficha_id=ficha.id, numero_sesion=numero,
            avance=avance, porcentaje=porcentaje, fecha=turno.inicio.astimezone(ZONA).date(),
        )
        auditar(con, ahora, "crear", "sesion_desenredado", sesion_id, ficha_id=ficha.id,
                mascota_id=turno.mascota_id, numero_sesion=numero, avance=avance,
                porcentaje=porcentaje)
    return repo_fichas.obtener_sesion(con, sesion_id)


def sesiones_de_mascota(con, mascota_id: int) -> list[SesionDesenredado]:
    return repo_fichas.sesiones_de_mascota(con, mascota_id)
