"""Repositorio del historial de precios (solo se agregan filas)."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime

from clinican.datos._util import a_texto
from clinican.dominio.cupos import CategoriaCupo
from clinican.dominio.precios import PrecioHistorico


def insertar(
    con: sqlite3.Connection,
    categoria: CategoriaCupo,
    valor: int,
    vigente_desde: date,
    registrado_en: datetime,
) -> int:
    cur = con.execute(
        "INSERT INTO precios (categoria, valor, vigente_desde, registrado_en) VALUES (?, ?, ?, ?)",
        (categoria.value, valor, vigente_desde.isoformat(), a_texto(registrado_en)),
    )
    return cur.lastrowid


def valor_en(con: sqlite3.Connection, categoria: CategoriaCupo, vigente_desde: date) -> int | None:
    fila = con.execute(
        "SELECT valor FROM precios WHERE categoria = ? AND vigente_desde = ?",
        (categoria.value, vigente_desde.isoformat()),
    ).fetchone()
    return None if fila is None else fila[0]


def actualizar_valor(
    con: sqlite3.Connection, categoria: CategoriaCupo, vigente_desde: date, valor: int
) -> int:
    cur = con.execute(
        "UPDATE precios SET valor = ? WHERE categoria = ? AND vigente_desde = ?",
        (valor, categoria.value, vigente_desde.isoformat()),
    )
    return cur.rowcount


def historial(con: sqlite3.Connection, categoria: CategoriaCupo | None = None) -> list[PrecioHistorico]:
    valor = None if categoria is None else categoria.value
    filas = con.execute(
        "SELECT vigente_desde, categoria, valor FROM precios "
        "WHERE (? IS NULL OR categoria = ?) ORDER BY categoria, vigente_desde, id",
        (valor, valor),
    ).fetchall()
    return [PrecioHistorico(date.fromisoformat(f[0]), CategoriaCupo(f[1]), f[2]) for f in filas]
