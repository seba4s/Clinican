"""Franjas disponibles de una fecha (RN-04) y reparto de grupos (RN-09, [A-3])."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from clinican.dominio.errores import DatoInvalido

MANANA, TARDE = "MANANA", "TARDE"
JORNADAS = {MANANA: "Mañana", TARDE: "Tarde"}
_RE_HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def validar_hora(hora: str) -> str:
    hora = (hora or "").strip()
    if len(hora) == 4 and hora[1] == ":":
        hora = "0" + hora  # 9:00 -> 09:00
    if not _RE_HORA.match(hora):
        raise DatoInvalido(f"«{hora}» no es una hora válida. Use HH:MM, por ejemplo 09:30.")
    return hora


def jornada_de(hora: str) -> str:
    return MANANA if hora < "13:00" else TARDE


def dia_semana(fecha: str) -> int:
    """1 = lunes ... 7 = domingo."""
    return date.fromisoformat(fecha).isoweekday()


@dataclass(frozen=True)
class Franja:
    hora: str
    jornada: str
    extra: bool = False  # agregada a mano para esa fecha


def franjas_de_fecha(
    fecha: str,
    base: list[tuple[str, str]],
    agregar: list[str],
    quitar: list[str],
    bloqueo_dia: bool,
    horas_bloqueadas: list[str],
) -> list[Franja]:
    """RN-04: base del día − QUITAR + AGREGAR − bloqueos. ``base`` = [(hora, jornada)] activas."""
    if bloqueo_dia:
        return []
    resultado = {h: Franja(h, j) for h, j in base if h not in quitar}
    for h in agregar:
        resultado.setdefault(h, Franja(h, jornada_de(h), extra=True))
    for h in horas_bloqueadas:
        resultado.pop(h, None)
    return [resultado[h] for h in sorted(resultado)]


# ------------------------------------------------------------------ grupos

def planificar_grupo(
    categorias: list[str],
    franjas: list[Franja],
    libres: dict[str, dict[str, int]],
    jornada: str,
    inicio: str,
    solo_individuales: set[str],
) -> tuple[list[tuple[int, str]], list[int]]:
    """RN-09 [A-3]: una franja por mascota, consecutivas, desde la hora de inicio de la jornada.

    - ``categorias``: categoría de cupo de cada mascota, en el orden en que se listan.
    - ``libres``: {hora: {categoría: cupos libres}}.
    - Se salta una franja sin cupo para la mascota que sigue, o reservada a turnos individuales.

    Devuelve (asignaciones [(índice de mascota, hora)], índices que no alcanzaron).
    """
    disponibles = [f.hora for f in franjas if f.jornada == jornada and f.hora >= inicio and f.hora not in solo_individuales]
    asignaciones: list[tuple[int, str]] = []
    pendientes = list(range(len(categorias)))
    for hora in disponibles:
        if not pendientes:
            break
        indice = pendientes[0]
        if libres.get(hora, {}).get(categorias[indice], 0) > 0:
            asignaciones.append((indice, hora))
            pendientes.pop(0)
    return asignaciones, pendientes


def repartir_pago(monto: int, cantidad: int, abono_minimo: int) -> list[int]:
    """Pago único de un grupo repartido en abonos por turno (RN-09).

    Cada turno recibe el abono mínimo; si sobra, el excedente va al primero.
    """
    if cantidad < 1:
        raise DatoInvalido("No hay turnos para repartir el pago.")
    if monto < cantidad * abono_minimo:
        from clinican.dominio.formato import pesos

        raise DatoInvalido(
            f"El pago del grupo debe ser de al menos {pesos(cantidad * abono_minimo)} "
            f"({pesos(abono_minimo)} por cada una de las {cantidad} mascotas)."
        )
    montos = [abono_minimo] * cantidad
    montos[0] += monto - cantidad * abono_minimo
    return montos
