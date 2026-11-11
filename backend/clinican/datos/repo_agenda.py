"""Repositorio de turnos y bloqueos."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, time, timedelta
from typing import Any

from clinican.datos._util import a_texto, actualizar, de_texto, fecha_a_texto, hora_a_texto
from clinican.dominio.agenda import Bloqueo
from clinican.dominio.cupos import CategoriaCupo, Servicio
from clinican.dominio.entidades import Turno
from clinican.dominio.estados import EstadoTurno, MotivoLiberacion

# --------------------------------------------------------------------------- turnos

COLUMNAS_TURNO = (
    "id, mascota_id, propietario_id, inicio, servicio, categoria, estado, motivo_liberacion, "
    "abono_requerido, abono_pagado, saldo_aplicado, saldo_generado, creado_en, abonado_en, "
    "aviso_inasistencia_en"
)


def turno_de_fila(f) -> Turno:
    return Turno(
        id=f[0],
        mascota_id=f[1],
        propietario_id=f[2],
        inicio=de_texto(f[3]),
        servicio=Servicio(f[4]),
        categoria=CategoriaCupo(f[5]),
        estado=EstadoTurno(f[6]),
        motivo_liberacion=None if f[7] is None else MotivoLiberacion(f[7]),
        abono_requerido=f[8],
        abono_pagado=f[9],
        saldo_aplicado=f[10],
        saldo_generado=f[11],
        creado_en=de_texto(f[12]),
        abonado_en=de_texto(f[13]),
        aviso_inasistencia_en=de_texto(f[14]),
    )


def _a_columnas(campos: dict[str, Any]) -> dict[str, Any]:
    salida = {}
    for clave, valor in campos.items():
        if isinstance(valor, datetime):
            valor = a_texto(valor)
        elif isinstance(valor, (EstadoTurno, MotivoLiberacion, Servicio, CategoriaCupo)):
            valor = valor.value
        salida[clave] = valor
    return salida


def insertar_turno(
    con: sqlite3.Connection,
    *,
    mascota_id: int,
    propietario_id: int,
    inicio: datetime,
    servicio: Servicio,
    categoria: CategoriaCupo,
    estado: EstadoTurno,
    abono_requerido: int,
    saldo_aplicado: int,
    creado_en: datetime,
) -> int:
    cur = con.execute(
        "INSERT INTO turnos (mascota_id, propietario_id, inicio, servicio, categoria, estado, "
        "abono_requerido, saldo_aplicado, creado_en) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            mascota_id, propietario_id, a_texto(inicio), servicio.value, categoria.value,
            estado.value, abono_requerido, saldo_aplicado, a_texto(creado_en),
        ),
    )
    return cur.lastrowid


def obtener_turno(con: sqlite3.Connection, id_: int) -> Turno | None:
    f = con.execute(f"SELECT {COLUMNAS_TURNO} FROM turnos WHERE id = ?", (id_,)).fetchone()
    return None if f is None else turno_de_fila(f)


def actualizar_turno(con: sqlite3.Connection, id_: int, **campos: Any) -> None:
    actualizar(
        con, "turnos", id_, _a_columnas(campos),
        {
            "inicio", "estado", "motivo_liberacion", "abono_pagado", "saldo_aplicado",
            "saldo_generado", "abonado_en", "aviso_inasistencia_en",
        },
    )


def turnos_en_inicio(con: sqlite3.Connection, inicio: datetime) -> list[Turno]:
    filas = con.execute(
        f"SELECT {COLUMNAS_TURNO} FROM turnos WHERE inicio = ? ORDER BY id", (a_texto(inicio),)
    ).fetchall()
    return [turno_de_fila(f) for f in filas]


def rango_del_dia(dia: date) -> tuple[str, str]:
    """Límites de texto [desde, hasta) del día, para usar el índice turnos(inicio, estado)."""
    return fecha_a_texto(dia), fecha_a_texto(dia + timedelta(days=1))


def turnos_del_dia(con: sqlite3.Connection, dia: date) -> list[Turno]:
    filas = con.execute(
        f"SELECT {COLUMNAS_TURNO} FROM turnos WHERE inicio >= ? AND inicio < ? ORDER BY inicio, id",
        rango_del_dia(dia),
    ).fetchall()
    return [turno_de_fila(f) for f in filas]


def turnos_por_estado(con: sqlite3.Connection, estado: EstadoTurno) -> list[Turno]:
    filas = con.execute(
        f"SELECT {COLUMNAS_TURNO} FROM turnos WHERE estado = ? ORDER BY id", (estado.value,)
    ).fetchall()
    return [turno_de_fila(f) for f in filas]


def turnos_de_propietario(
    con: sqlite3.Connection, propietario_id: int, estado: EstadoTurno | None = None
) -> list[Turno]:
    valor = None if estado is None else estado.value
    filas = con.execute(
        f"SELECT {COLUMNAS_TURNO} FROM turnos WHERE propietario_id = ? AND (? IS NULL OR estado = ?) "
        "ORDER BY inicio, id",
        (propietario_id, valor, valor),
    ).fetchall()
    return [turno_de_fila(f) for f in filas]


def mover_turnos_de_propietario(con: sqlite3.Connection, origen: int, destino: int) -> int:
    cur = con.execute(
        "UPDATE turnos SET propietario_id = ? WHERE propietario_id = ?", (destino, origen)
    )
    return cur.rowcount


# --------------------------------------------------------------------------- bloqueos


def _bloqueo(f) -> Bloqueo:
    return Bloqueo(
        fecha=date.fromisoformat(f[1]),
        desde=None if f[2] is None else time.fromisoformat(f[2]),
        hasta=None if f[3] is None else time.fromisoformat(f[3]),
        motivo=f[4],
        id=f[0],
    )


def insertar_bloqueo(con: sqlite3.Connection, bloqueo: Bloqueo) -> int:
    cur = con.execute(
        "INSERT INTO bloqueos (fecha, hora_inicio, hora_fin, motivo) VALUES (?, ?, ?, ?)",
        (
            fecha_a_texto(bloqueo.fecha), hora_a_texto(bloqueo.desde),
            hora_a_texto(bloqueo.hasta), bloqueo.motivo,
        ),
    )
    return cur.lastrowid


def obtener_bloqueo(con: sqlite3.Connection, id_: int) -> tuple[Bloqueo, bool] | None:
    """Devuelve (bloqueo, activo) o None."""
    f = con.execute(
        "SELECT id, fecha, hora_inicio, hora_fin, motivo, activo FROM bloqueos WHERE id = ?",
        (id_,),
    ).fetchone()
    return None if f is None else (_bloqueo(f), bool(f[5]))


def bloqueos_del_dia(con: sqlite3.Connection, dia: date) -> list[Bloqueo]:
    filas = con.execute(
        "SELECT id, fecha, hora_inicio, hora_fin, motivo FROM bloqueos "
        "WHERE fecha = ? AND activo = 1 ORDER BY hora_inicio, id",
        (fecha_a_texto(dia),),
    ).fetchall()
    return [_bloqueo(f) for f in filas]


def desactivar_bloqueo(con: sqlite3.Connection, id_: int) -> None:
    con.execute("UPDATE bloqueos SET activo = 0 WHERE id = ?", (id_,))
