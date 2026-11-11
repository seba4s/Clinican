"""Consultas de solo lectura para la futura interfaz."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from clinican.datos import repo_agenda, repo_consultas
from clinican.dominio.abonos import esta_vencido, vence_en
from clinican.dominio.agenda import Franja, generar_franjas
from clinican.dominio.cupos import CategoriaCupo, cupos_libres
from clinican.dominio.entidades import EstadoNotificacion, Ficha, NotificacionSalida, Turno
from clinican.dominio.turnos import contar_ocupacion
from clinican.servicios import configuracion


@dataclass(frozen=True)
class TurnoEnAgenda:
    turno: Turno
    mascota: str
    propietario: str
    celular: str
    raza: str = ""


@dataclass(frozen=True)
class FranjaDeAgenda:
    franja: Franja
    libres: dict[CategoriaCupo, int]
    turnos: list[TurnoEnAgenda] = field(default_factory=list)


@dataclass(frozen=True)
class PendienteDeAbono:
    turno: Turno
    mascota: str
    propietario: str
    celular: str
    vence_en: datetime
    vencido: bool


@dataclass(frozen=True)
class EstadoBandeja:
    conteo: dict[EstadoNotificacion, int]
    proximas: list[NotificacionSalida]
    fallidas_recientes: list[NotificacionSalida]


def agenda_del_dia(con, dia: date, *, ahora: datetime) -> list[FranjaDeAgenda]:
    """Franjas reservables del día con cupos libres por categoría y sus turnos.

    Incluye todos los turnos del día (también cancelados o liberados) para que
    la pantalla los muestre; los cupos solo cuentan los que ocupan franja.
    """
    cfg = configuracion.cargar(con)
    por_inicio: dict[datetime, list[TurnoEnAgenda]] = {}
    for turno, mascota, propietario, celular, raza in repo_consultas.turnos_detallados_del_dia(con, dia):
        por_inicio.setdefault(turno.inicio, []).append(TurnoEnAgenda(turno, mascota, propietario, celular, raza))
    salida = []
    for franja in generar_franjas(dia, cfg.horario, repo_agenda.bloqueos_del_dia(con, dia)):
        turnos = por_inicio.get(franja.inicio, [])
        ocupacion = contar_ocupacion([t.turno for t in turnos], ahora, cfg.minutos_expiracion)
        libres = {c: cupos_libres(cfg.cupos, ocupacion, c) for c in CategoriaCupo}
        salida.append(FranjaDeAgenda(franja, libres, turnos))
    return salida


def historial_de_mascota(con, mascota_id: int) -> list[tuple[Turno, Ficha | None]]:
    """Turnos de la mascota (del más reciente al más antiguo) con su ficha, si tiene."""
    return repo_consultas.historial_de_mascota(con, mascota_id)


def pendientes_de_abono(con, *, ahora: datetime) -> list[PendienteDeAbono]:
    minutos = configuracion.cargar(con).minutos_expiracion
    return [
        PendienteDeAbono(
            turno, mascota, propietario, celular,
            vence_en=vence_en(turno.creado_en, minutos),
            vencido=esta_vencido(turno.creado_en, ahora, minutos),
        )
        for turno, mascota, propietario, celular in repo_consultas.pendientes_de_abono(con)
    ]


def estado_bandeja(con, limite: int = 20) -> EstadoBandeja:
    crudo = repo_consultas.conteo_bandeja(con)
    return EstadoBandeja(
        conteo={e: crudo.get(e.value, 0) for e in EstadoNotificacion},
        proximas=repo_consultas.notificaciones_por_estado(con, "pendiente", limite),
        fallidas_recientes=repo_consultas.notificaciones_por_estado(
            con, "fallida", limite, recientes_primero=True
        ),
    )
