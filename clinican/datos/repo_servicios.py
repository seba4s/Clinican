"""Tablas ``servicios`` (ficha de servicio) y ``sesiones_desenredado``."""

from __future__ import annotations

import sqlite3

_COLUMNAS = {
    "mascota_id", "fecha", "tipo_servicio", "largo_maquina", "bano_medicado", "bano_antipulgas",
    "cantidad_banos_extra", "copete", "barbas", "cola_leon", "cola_estilo", "forma_cara", "cond_agresiva",
    "cond_nudos_extremos", "cond_problemas_piel", "cond_plagas", "cond_edad_avanzada", "estado", "precio_minimo",
    "precio_final", "extras", "total", "observaciones", "corbatin", "corbatin_color", "monos", "monos_color",
}


def _validar_columnas(campos: dict) -> None:
    desconocidas = set(campos) - _COLUMNAS
    if desconocidas:
        raise ValueError(f"Columnas desconocidas en servicios: {sorted(desconocidas)}")


def obtener(conn: sqlite3.Connection, servicio_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT s.*, m.nombre AS mascota_nombre, m.tamano_manual, m.propietario_id, r.tamano AS raza_tamano,
                  r.nombre AS raza_nombre, p.nombre AS creado_por_nombre
           FROM servicios s
           JOIN mascotas m ON m.id = s.mascota_id
           JOIN razas r ON r.id = m.raza_id
           LEFT JOIN personal p ON p.id = s.creado_por
           WHERE s.id = ?""",
        (servicio_id,),
    ).fetchone()


def insertar(conn: sqlite3.Connection, mascota_id: int, fecha: str, columnas: dict, precio_minimo: int,
             precio_final: int | None, extras: int, total: int | None, creado_por: int) -> int:
    campos = {**columnas, "mascota_id": mascota_id, "fecha": fecha, "precio_minimo": precio_minimo,
              "precio_final": precio_final, "extras": extras, "total": total}
    _validar_columnas(campos)
    nombres = list(campos)
    cur = conn.execute(
        f"INSERT INTO servicios ({', '.join(nombres)}, creado_por) VALUES ({', '.join('?' for _ in nombres)}, ?)",
        (*campos.values(), creado_por),
    )
    return cur.lastrowid


def actualizar(conn: sqlite3.Connection, servicio_id: int, campos: dict) -> None:
    if not campos:
        return
    _validar_columnas(campos)
    asignaciones = ", ".join(f"{c} = ?" for c in campos)
    conn.execute(f"UPDATE servicios SET {asignaciones} WHERE id = ?", (*campos.values(), servicio_id))


def en_sesiones_de_mascota(conn: sqlite3.Connection, mascota_id: int, excepto_id: int | None = None) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM servicios WHERE mascota_id = ? AND estado = 'EN_SESIONES' AND id <> ? LIMIT 1",
        (mascota_id, excepto_id or 0),
    ).fetchone()


# -------------------------------------------------------------- desenredado

def total_desenredado(conn: sqlite3.Connection, servicio_id: int | None) -> int:
    if not servicio_id:
        return 0
    return conn.execute("SELECT COALESCE(SUM(precio), 0) FROM sesiones_desenredado WHERE servicio_id = ?",
                        (servicio_id,)).fetchone()[0]


def sesiones(conn: sqlite3.Connection, servicio_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT d.*, p.nombre AS realizada_por_nombre FROM sesiones_desenredado d
           LEFT JOIN personal p ON p.id = d.realizada_por
           WHERE d.servicio_id = ? ORDER BY d.fecha, d.id""",
        (servicio_id,),
    ).fetchall()


def sesion(conn: sqlite3.Connection, sesion_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM sesiones_desenredado WHERE id = ?", (sesion_id,)).fetchone()


def insertar_sesion(conn: sqlite3.Connection, servicio_id: int, fecha: str, precio: int, notas: str | None,
                    realizada_por: int | None) -> int:
    cur = conn.execute(
        "INSERT INTO sesiones_desenredado (servicio_id, fecha, precio, notas, realizada_por) VALUES (?, ?, ?, ?, ?)",
        (servicio_id, fecha, precio, notas, realizada_por),
    )
    return cur.lastrowid


def borrar_sesion(conn: sqlite3.Connection, sesion_id: int) -> None:
    conn.execute("DELETE FROM sesiones_desenredado WHERE id = ?", (sesion_id,))
