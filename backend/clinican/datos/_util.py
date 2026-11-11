"""Conversión entre valores del dominio y texto almacenado en SQLite."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, time
from typing import Any, Iterable, Mapping

from clinican.dominio.agenda import ZONA


def a_texto(momento: datetime | None) -> str | None:
    """Fecha y hora con zona -> ISO en hora de Bogotá (ordenable como texto)."""
    if momento is None:
        return None
    if momento.tzinfo is None or momento.utcoffset() is None:
        raise ValueError("Las fechas y horas deben tener zona horaria")
    return momento.astimezone(ZONA).isoformat(timespec="microseconds")


def de_texto(texto: str | None) -> datetime | None:
    return None if texto is None else datetime.fromisoformat(texto)


def fecha_a_texto(dia: date) -> str:
    return dia.isoformat()


def hora_a_texto(hora: time | None) -> str | None:
    return None if hora is None else hora.strftime("%H:%M")


def actualizar(
    con: sqlite3.Connection,
    tabla: str,
    id_: int,
    campos: Mapping[str, Any],
    permitidos: Iterable[str],
) -> None:
    """Actualiza columnas de una lista blanca (los nombres nunca vienen del usuario)."""
    permitidos = set(permitidos)
    desconocidos = set(campos) - permitidos
    if desconocidos:
        raise ValueError(f"Columnas no permitidas en {tabla}: {sorted(desconocidos)}")
    if not campos:
        return
    asignaciones = ", ".join(f"{c} = ?" for c in campos)
    con.execute(f"UPDATE {tabla} SET {asignaciones} WHERE id = ?", (*campos.values(), id_))
