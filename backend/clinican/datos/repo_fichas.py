"""Repositorio de fichas de servicio y sesiones de desenredado."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from typing import Any

from clinican.datos._util import a_texto, actualizar, de_texto
from clinican.dominio.entidades import Ficha, SesionDesenredado

_FICHA = "id, turno_id, servicios_realizados, detalles_corte, precio_final, observaciones, creada_en"


def _ficha(f) -> Ficha:
    return Ficha(f[0], f[1], f[2], f[3], f[4], f[5], de_texto(f[6]))


def insertar_ficha(
    con: sqlite3.Connection,
    *,
    turno_id: int,
    servicios_realizados: str,
    detalles_corte: str,
    precio_final: int,
    observaciones: str,
    creada_en: datetime,
) -> int:
    cur = con.execute(
        "INSERT INTO fichas (turno_id, servicios_realizados, detalles_corte, precio_final, "
        "observaciones, creada_en) VALUES (?, ?, ?, ?, ?, ?)",
        (turno_id, servicios_realizados, detalles_corte, precio_final, observaciones,
         a_texto(creada_en)),
    )
    return cur.lastrowid


def obtener_ficha(con: sqlite3.Connection, id_: int) -> Ficha | None:
    f = con.execute(f"SELECT {_FICHA} FROM fichas WHERE id = ?", (id_,)).fetchone()
    return None if f is None else _ficha(f)


def ficha_de_turno(con: sqlite3.Connection, turno_id: int) -> Ficha | None:
    f = con.execute(f"SELECT {_FICHA} FROM fichas WHERE turno_id = ?", (turno_id,)).fetchone()
    return None if f is None else _ficha(f)


def actualizar_ficha(con: sqlite3.Connection, id_: int, **campos: Any) -> None:
    actualizar(
        con, "fichas", id_, campos,
        {"servicios_realizados", "detalles_corte", "observaciones", "precio_final"},
    )


_SESION = "id, mascota_id, ficha_id, numero_sesion, avance, porcentaje, fecha"


def _sesion(f) -> SesionDesenredado:
    return SesionDesenredado(f[0], f[1], f[2], f[3], f[4], f[5], date.fromisoformat(f[6]))


def siguiente_numero_sesion(con: sqlite3.Connection, mascota_id: int) -> int:
    return con.execute(
        "SELECT COALESCE(MAX(numero_sesion), 0) + 1 FROM sesiones_desenredado WHERE mascota_id = ?",
        (mascota_id,),
    ).fetchone()[0]


def insertar_sesion(
    con: sqlite3.Connection,
    *,
    mascota_id: int,
    ficha_id: int,
    numero_sesion: int,
    avance: str,
    porcentaje: int | None,
    fecha: date,
) -> int:
    cur = con.execute(
        "INSERT INTO sesiones_desenredado (mascota_id, ficha_id, numero_sesion, avance, "
        "porcentaje, fecha) VALUES (?, ?, ?, ?, ?, ?)",
        (mascota_id, ficha_id, numero_sesion, avance, porcentaje, fecha.isoformat()),
    )
    return cur.lastrowid


def obtener_sesion(con: sqlite3.Connection, id_: int) -> SesionDesenredado | None:
    f = con.execute(f"SELECT {_SESION} FROM sesiones_desenredado WHERE id = ?", (id_,)).fetchone()
    return None if f is None else _sesion(f)


def sesiones_de_mascota(con: sqlite3.Connection, mascota_id: int) -> list[SesionDesenredado]:
    filas = con.execute(
        f"SELECT {_SESION} FROM sesiones_desenredado WHERE mascota_id = ? ORDER BY numero_sesion",
        (mascota_id,),
    ).fetchall()
    return [_sesion(f) for f in filas]
