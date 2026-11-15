"""Tablero del día sin ventanas: franjas con sus puestos y su agrupación en filas de la hoja.

Lo usan la pantalla de Agenda y sus pruebas; no depende de ningún kit gráfico.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from clinican.dominio.abonos import vence_en
from clinican.dominio.agenda import generar_franjas
from clinican.dominio.cupos import CategoriaCupo
from clinican.dominio.estados import EstadoTurno, ocupa_cupo
from clinican.servicios import agenda, configuracion, consultas
from clinican.servicios.consultas import TurnoEnAgenda

E = EstadoTurno
ORDEN_CATEGORIAS = (CategoriaCupo.MAQUINA, CategoriaCupo.GRANDE, CategoriaCupo.TIJERA, CategoriaCupo.COMPLICADO)


@dataclass
class FilaTablero:
    inicio: datetime
    pasada: bool
    bloqueo: str | None = None
    puestos: dict[CategoriaCupo, list[TurnoEnAgenda | None]] = field(default_factory=dict)


def capacidad(cupos, categoria: CategoriaCupo) -> int:
    return cupos.capacidad(categoria)


def armar_tablero(con, dia: date, ahora: datetime) -> tuple[list[FilaTablero], list[TurnoEnAgenda], int]:
    """Filas del día (también las bloqueadas), turnos fuera de agenda y cupos libres."""
    cfg = configuracion.cargar(con)
    bloqueos = agenda.bloqueos_del_dia(con, dia)
    reservables = {f.franja.inicio: f for f in consultas.agenda_del_dia(con, dia, ahora=ahora)}
    filas: list[FilaTablero] = []
    fuera: list[TurnoEnAgenda] = []
    libres = 0
    for franja in generar_franjas(dia, cfg.horario):
        fila = FilaTablero(franja.inicio, pasada=franja.fin <= ahora)
        datos = reservables.get(franja.inicio)
        if datos is None:
            motivo = next((b.motivo for b in bloqueos if b.cubre(franja)), "")
            fila.bloqueo = motivo or "sin motivo"
            filas.append(fila)
            continue
        for categoria in ORDEN_CATEGORIAS:
            fila.puestos[categoria] = []
        for t in datos.turnos:
            vencido = t.turno.estado is E.PENDIENTE_ABONO and vence_en(t.turno.creado_en, cfg.minutos_expiracion) <= ahora
            if ocupa_cupo(t.turno.estado) and not vencido:
                fila.puestos[t.turno.categoria].append(t)
            else:
                fuera.append(t)
        for categoria in ORDEN_CATEGORIAS:
            cap = capacidad(cfg.cupos, categoria)
            ocupados = fila.puestos[categoria]
            vacios = max(0, cap - len(ocupados))
            if not fila.pasada:
                libres += vacios
            fila.puestos[categoria] = ocupados + [None] * vacios
        filas.append(fila)
    return filas, fuera, libres


@dataclass
class FilaHoja:
    """Una fila dibujada. ``tipo``: turno, libre, pasada o bloqueo."""

    tipo: str
    inicio: datetime
    item: TurnoEnAgenda | None = None
    libres: dict[CategoriaCupo, int] = field(default_factory=dict)
    texto: str = ""
    hasta: datetime | None = None


@dataclass
class GrupoHora:
    """Las filas de una misma franja: la hora se combina en una sola celda."""

    inicio: datetime
    pasada: bool
    filas: list[FilaHoja]


def agrupar(filas_tablero, orden: tuple[CategoriaCupo, ...]) -> list[GrupoHora]:
    """Convierte las filas del tablero (franjas con puestos) en grupos de filas de la hoja.

    Las franjas bloqueadas seguidas con el mismo motivo se juntan en una sola banda.
    """
    grupos: list[GrupoHora] = []
    for f in filas_tablero:
        if f.bloqueo:
            previo = grupos[-1] if grupos else None
            fin = f.inicio + timedelta(minutes=30)
            if previo and previo.filas[0].tipo == "bloqueo" and previo.filas[0].texto == f.bloqueo \
                    and previo.filas[0].hasta == f.inicio:
                previo.filas[0].hasta = fin
                continue
            grupos.append(GrupoHora(f.inicio, f.pasada, [FilaHoja("bloqueo", f.inicio, texto=f.bloqueo, hasta=fin)]))
            continue
        filas = [FilaHoja("turno", f.inicio, item=t) for cat in orden for t in f.puestos.get(cat, []) if t]
        libres = {cat: sum(1 for t in f.puestos.get(cat, []) if t is None) for cat in orden}
        libres = {cat: n for cat, n in libres.items() if n}
        if libres and not f.pasada:
            filas.append(FilaHoja("libre", f.inicio, libres=libres))
        if not filas:
            filas.append(FilaHoja("pasada", f.inicio))
        grupos.append(GrupoHora(f.inicio, f.pasada, filas))
    return grupos
