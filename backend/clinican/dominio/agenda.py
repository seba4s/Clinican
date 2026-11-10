"""Franjas de 30 minutos, horario semanal de recepción y bloqueos.

La peluquería atiende hasta las 18:30, pero solo RECIBE perros de lunes a
sábado de 9:00 a 16:30: las franjas empiezan a las 9:00, 9:30, ... y la última
empieza a las 16:30 (16 franjas por día). El domingo está cerrado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from typing import Iterable, Mapping

DURACION_FRANJA = timedelta(minutes=30)


def _zona_bogota() -> tzinfo:
    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            return ZoneInfo("America/Bogota")
        except ZoneInfoNotFoundError:
            pass
    except ImportError:  # pragma: no cover
        pass
    # Windows sin el paquete tzdata: Colombia no tiene horario de verano.
    return timezone(timedelta(hours=-5), "COT")


ZONA = _zona_bogota()


@dataclass(frozen=True, order=True)
class Franja:
    """Franja de 30 minutos que empieza en ``inicio`` (con zona horaria)."""

    inicio: datetime

    def __post_init__(self) -> None:
        if self.inicio.tzinfo is None or self.inicio.utcoffset() is None:
            raise ValueError("El inicio de la franja debe tener zona horaria")
        if self.inicio.minute not in (0, 30) or self.inicio.second or self.inicio.microsecond:
            raise ValueError("Las franjas empiezan en punto o y media")

    @property
    def fin(self) -> datetime:
        return self.inicio + DURACION_FRANJA


@dataclass(frozen=True)
class Jornada:
    """Recepción de un día: primera franja en ``apertura``, última en ``ultima_franja``."""

    apertura: time
    ultima_franja: time

    def __post_init__(self) -> None:
        for hora in (self.apertura, self.ultima_franja):
            if hora.minute not in (0, 30) or hora.second or hora.microsecond:
                raise ValueError("Las franjas empiezan en punto o y media")
        if self.apertura > self.ultima_franja:
            raise ValueError("La apertura no puede ser posterior a la última franja")


_JORNADA_NORMAL = Jornada(time(9, 0), time(16, 30))  # 16 franjas


def _horario_por_defecto() -> dict[int, Jornada | None]:
    # 0 = lunes ... 6 = domingo
    return {**{d: _JORNADA_NORMAL for d in range(6)}, 6: None}


@dataclass(frozen=True)
class HorarioSemanal:
    """Jornada de recepción por día de la semana (0 = lunes); None = cerrado."""

    dias: Mapping[int, Jornada | None] = field(default_factory=_horario_por_defecto)

    def jornada(self, fecha: date) -> Jornada | None:
        return self.dias.get(fecha.weekday())


@dataclass(frozen=True)
class Bloqueo:
    """Bloqueo de agenda: día completo (sin horas) o rango [desde, hasta)."""

    fecha: date
    desde: time | None = None
    hasta: time | None = None
    motivo: str = ""

    def __post_init__(self) -> None:
        if (self.desde is None) != (self.hasta is None):
            raise ValueError("Un bloqueo por horas necesita desde y hasta")
        if self.desde is not None and self.desde >= self.hasta:
            raise ValueError("En un bloqueo, desde debe ser anterior a hasta")

    @property
    def dia_completo(self) -> bool:
        return self.desde is None

    def cubre(self, franja: Franja) -> bool:
        local = franja.inicio.astimezone(ZONA)
        if local.date() != self.fecha:
            return False
        if self.dia_completo:
            return True
        ini = datetime.combine(self.fecha, self.desde, tzinfo=ZONA)
        fin = datetime.combine(self.fecha, self.hasta, tzinfo=ZONA)
        return franja.inicio < fin and franja.fin > ini


def generar_franjas(
    fecha: date,
    horario: HorarioSemanal | None = None,
    bloqueos: Iterable[Bloqueo] = (),
) -> list[Franja]:
    """Franjas reservables de ``fecha`` que no caen en ningún bloqueo."""
    horario = horario or HorarioSemanal()
    jornada = horario.jornada(fecha)
    if jornada is None:
        return []
    bloqueos = [b for b in bloqueos if b.fecha == fecha]
    actual = datetime.combine(fecha, jornada.apertura, tzinfo=ZONA)
    ultima = datetime.combine(fecha, jornada.ultima_franja, tzinfo=ZONA)
    franjas: list[Franja] = []
    while actual <= ultima:
        franja = Franja(actual)
        if not any(b.cubre(franja) for b in bloqueos):
            franjas.append(franja)
        actual += DURACION_FRANJA
    return franjas
