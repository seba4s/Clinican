"""Configuración tipada guardada como clave -> texto.

Si una clave no tiene fila se usa su valor por defecto. Al guardar se valida
el tipo y se audita en la misma transacción.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, Callable

from clinican.datos import repo_configuracion
from clinican.datos.conexion import transaccion
from clinican.dominio.abonos import validar_pesos
from clinican.dominio.agenda import HorarioSemanal, Jornada
from clinican.dominio.cupos import CategoriaCupo, CuposPorFranja
from clinican.dominio.errores import DatoInvalido
from clinican.dominio.notificaciones import HORAS_ANTES_RECORDATORIO
from clinican.servicios.auditoria import auditar


# --------------------------------------------------------------------------- conversores


def _cupos_a_texto(c: CuposPorFranja) -> str:
    return json.dumps({cat.value: c.capacidad(cat) for cat in CategoriaCupo}, sort_keys=True)


def _cupos_de_texto(texto: str) -> CuposPorFranja:
    return CuposPorFranja(**json.loads(texto))


def _horario_a_texto(h: HorarioSemanal) -> str:
    dias = {}
    for dia in range(7):
        j = h.dias.get(dia)
        dias[str(dia)] = None if j is None else [
            j.apertura.strftime("%H:%M"), j.ultima_franja.strftime("%H:%M")
        ]
    return json.dumps(dias, sort_keys=True)


def _horario_de_texto(texto: str) -> HorarioSemanal:
    dias = {}
    for dia, valor in json.loads(texto).items():
        dias[int(dia)] = None if valor is None else Jornada(
            time.fromisoformat(valor[0]), time.fromisoformat(valor[1])
        )
    return HorarioSemanal(dias)


def _validar_entero_positivo(valor: Any) -> None:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
        raise TypeError("debe ser un entero mayor que cero")


def _validar_entero_no_negativo(valor: Any) -> None:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        raise TypeError("debe ser un entero mayor o igual a cero")


def _validar_pesos(valor: Any) -> None:
    try:
        validar_pesos(valor)
    except (TypeError, ValueError):
        raise TypeError("debe ser un entero de pesos mayor o igual a cero") from None


def _validar_texto(valor: Any) -> None:
    if not isinstance(valor, str) or not valor.strip():
        raise TypeError("debe ser un texto no vacío")


def _validar_horario(valor: Any) -> None:
    if not isinstance(valor, HorarioSemanal):
        raise TypeError("debe ser un HorarioSemanal")
    for dia, jornada in valor.dias.items():
        if dia not in range(7) or not (jornada is None or isinstance(jornada, Jornada)):
            raise TypeError("cada día (0 = lunes ... 6 = domingo) debe tener una Jornada o None")


def _validar_tipo(tipo: type) -> Callable[[Any], None]:
    def validar(valor: Any) -> None:
        if not isinstance(valor, tipo):
            raise TypeError(f"debe ser {tipo.__name__}")
    return validar


@dataclass(frozen=True)
class Clave:
    nombre: str
    por_defecto: Any
    validar: Callable[[Any], None]
    a_texto: Callable[[Any], str]
    de_texto: Callable[[str], Any]


CLAVES: dict[str, Clave] = {
    c.nombre: c
    for c in (
        Clave("cupos", CuposPorFranja(), _validar_tipo(CuposPorFranja), _cupos_a_texto, _cupos_de_texto),
        Clave("abono", 20000, _validar_pesos, str, int),
        Clave("minutos_expiracion", 30, _validar_entero_positivo, str, int),
        Clave("horario", HorarioSemanal(), _validar_horario, _horario_a_texto, _horario_de_texto),
        Clave("canal_notificaciones", "archivo", _validar_texto, str, str),
        Clave("carpeta_respaldos", "respaldos", _validar_texto, str, str),
        # 24 h antes por defecto (confirmado), configurable.
        Clave("horas_antes_recordatorio", HORAS_ANTES_RECORDATORIO, _validar_entero_no_negativo, str, int),
    )
}


@dataclass(frozen=True)
class ConfigClinica:
    cupos: CuposPorFranja
    abono: int
    minutos_expiracion: int
    horario: HorarioSemanal
    canal_notificaciones: str
    carpeta_respaldos: str
    horas_antes_recordatorio: int


def _clave(nombre: str) -> Clave:
    try:
        return CLAVES[nombre]
    except KeyError:
        raise DatoInvalido(f"No existe la configuración '{nombre}'") from None


def leer(con, nombre: str) -> Any:
    clave = _clave(nombre)
    texto = repo_configuracion.leer(con, nombre)
    if texto is None:
        return clave.por_defecto
    try:
        return clave.de_texto(texto)
    except (ValueError, TypeError, KeyError, IndexError) as error:
        raise DatoInvalido(f"La configuración '{nombre}' guardada está dañada: {error}") from None


def cargar(con) -> ConfigClinica:
    return ConfigClinica(**{nombre: leer(con, nombre) for nombre in CLAVES})


def guardar(con, nombre: str, valor: Any, *, ahora: datetime) -> None:
    clave = _clave(nombre)
    try:
        clave.validar(valor)
    except (TypeError, ValueError) as error:
        raise DatoInvalido(f"La configuración '{nombre}' {error}") from None
    texto = clave.a_texto(valor)
    with transaccion(con):
        anterior = repo_configuracion.leer(con, nombre)
        repo_configuracion.guardar(con, nombre, texto)
        auditar(con, ahora, "guardar", "configuracion", None, clave=nombre, antes=anterior, despues=texto)
