"""Tablas ``turnos`` y ``abonos``."""

from __future__ import annotations

import sqlite3

from clinican.dominio.cupos import OCUPAN_CUPO
from clinican.dominio.turnos import ACTIVOS

_AHORA = "datetime('now','localtime')"
_EN = lambda estados: "(" + ", ".join(f"'{e}'" for e in estados) + ")"  # noqa: E731

# Un turno con los datos de la mascota, el propietario, la ficha y lo abonado.
# «abonado» suma los abonos vigentes y los ya aplicados al cobro.
_TURNO = """
    SELECT t.*, m.nombre AS mascota_nombre, m.propietario_id, r.nombre AS raza_nombre,
           p.nombre AS propietario_nombre, p.cedula, p.celular1, p.celular2, p.requiere_nuevo_abono,
           a.nombre AS agendado_por_nombre, s.tipo_servicio, s.estado AS servicio_estado,
           (SELECT COALESCE(SUM(ab.monto), 0) FROM abonos ab
             WHERE ab.turno_id = t.id AND ab.estado IN ('VIGENTE', 'APLICADO')) AS abonado
    FROM turnos t
    JOIN mascotas m ON m.id = t.mascota_id
    JOIN razas r ON r.id = m.raza_id
    JOIN propietarios p ON p.id = m.propietario_id
    JOIN personal a ON a.id = t.agendado_por
    LEFT JOIN servicios s ON s.id = t.servicio_id
"""

_COLUMNAS = {
    "fecha", "hora", "mascota_id", "servicio_id", "grupo_id", "categoria_cupo", "estado", "pendiente_hasta",
    "motivo_liberacion", "avisado_en", "motivo_no_atendido", "llamada_en", "agendado_por", "origen", "creado_en",
}


def _validar(campos: dict) -> None:
    desconocidas = set(campos) - _COLUMNAS
    if desconocidas:
        raise ValueError(f"Columnas desconocidas en turnos: {sorted(desconocidas)}")


# ------------------------------------------------------------------ lectura

def turno(conn: sqlite3.Connection, turno_id: int) -> sqlite3.Row | None:
    return conn.execute(f"{_TURNO} WHERE t.id = ?", (turno_id,)).fetchone()


def del_dia(conn: sqlite3.Connection, fecha: str) -> list[sqlite3.Row]:
    return conn.execute(f"{_TURNO} WHERE t.fecha = ? ORDER BY t.hora, t.id", (fecha,)).fetchall()


def de_grupo(conn: sqlite3.Connection, grupo_id: int) -> list[sqlite3.Row]:
    """Turnos del grupo en el orden en que se agendaron."""
    return conn.execute(f"{_TURNO} WHERE t.grupo_id = ? ORDER BY t.id", (grupo_id,)).fetchall()


def activos_en(conn: sqlite3.Connection, fecha: str, hora: str | None = None) -> list[sqlite3.Row]:
    """Turnos activos (pendientes, confirmados, en proceso o listos) de una fecha u hora."""
    sql = f"{_TURNO} WHERE t.fecha = ? AND t.estado IN {_EN(ACTIVOS)}"
    parametros: list = [fecha]
    if hora is not None:
        sql += " AND t.hora = ?"
        parametros.append(hora)
    return conn.execute(sql + " ORDER BY t.hora, t.id", parametros).fetchall()


def activo_de_mascota(conn: sqlite3.Connection, mascota_id: int, fecha: str,
                      excepto: int | None = None) -> sqlite3.Row | None:
    return conn.execute(
        f"SELECT * FROM turnos WHERE mascota_id = ? AND fecha = ? AND estado IN {_EN(ACTIVOS)} AND id <> ? LIMIT 1",
        (mascota_id, fecha, excepto or 0),
    ).fetchone()


def ocupados(conn: sqlite3.Connection, fecha: str, hora: str, excepto: int | None = None) -> dict[str, int]:
    """RN-03: turnos que ocupan cupo en la franja, por categoría."""
    filas = conn.execute(
        f"""SELECT categoria_cupo, COUNT(*) AS n FROM turnos
            WHERE fecha = ? AND hora = ? AND estado IN {_EN(OCUPAN_CUPO)} AND id <> ?
            GROUP BY categoria_cupo""",
        (fecha, hora, excepto or 0),
    ).fetchall()
    return {f["categoria_cupo"]: f["n"] for f in filas}


def pendientes_todos(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(f"{_TURNO} WHERE t.estado = 'PENDIENTE_ABONO' ORDER BY t.id").fetchall()


def pendientes_en(conn: sqlite3.Connection, fecha: str, hora: str, categoria: str,
                  excepto: int | None = None) -> list[sqlite3.Row]:
    return conn.execute(
        f"""{_TURNO} WHERE t.fecha = ? AND t.hora = ? AND t.categoria_cupo = ?
            AND t.estado = 'PENDIENTE_ABONO' AND t.id <> ? ORDER BY t.id""",
        (fecha, hora, categoria, excepto or 0),
    ).fetchall()


# ---------------------------------------------------------------- escritura

def insertar(conn: sqlite3.Connection, datos: dict) -> int:
    _validar(datos)
    columnas = [c for c, v in datos.items() if v is not None]
    cur = conn.execute(
        f"INSERT INTO turnos ({', '.join(columnas)}) VALUES ({', '.join('?' for _ in columnas)})",
        [datos[c] for c in columnas],
    )
    return cur.lastrowid


def actualizar(conn: sqlite3.Connection, turno_id: int, campos: dict) -> None:
    if not campos:
        return
    _validar(campos)
    asignaciones = ", ".join(f"{c} = ?" for c in campos)
    conn.execute(f"UPDATE turnos SET {asignaciones}, actualizado_en = {_AHORA} WHERE id = ?",
                 (*campos.values(), turno_id))


# ------------------------------------------------------------------- abonos

_ABONO = """SELECT ab.*, p.nombre AS registrado_por_nombre, d.nombre AS devuelto_por_nombre
            FROM abonos ab
            JOIN personal p ON p.id = ab.registrado_por
            LEFT JOIN personal d ON d.id = ab.devuelto_por"""


def abonos(conn: sqlite3.Connection, turno_id: int) -> list[sqlite3.Row]:
    return conn.execute(f"{_ABONO} WHERE ab.turno_id = ? ORDER BY ab.id", (turno_id,)).fetchall()


def abono(conn: sqlite3.Connection, abono_id: int) -> sqlite3.Row | None:
    return conn.execute(f"{_ABONO} WHERE ab.id = ?", (abono_id,)).fetchone()


def insertar_abono(conn: sqlite3.Connection, turno_id: int, monto: int, medio: str, referencia: str | None,
                   registrado_por: int, recibido_en: str) -> int:
    cur = conn.execute(
        "INSERT INTO abonos (turno_id, monto, medio, referencia, registrado_por, recibido_en) VALUES (?, ?, ?, ?, ?, ?)",
        (turno_id, monto, medio, referencia, registrado_por, recibido_en),
    )
    return cur.lastrowid


def actualizar_abono(conn: sqlite3.Connection, abono_id: int, campos: dict) -> None:
    permitidas = {"monto", "medio", "referencia", "estado", "turno_id", "devuelto_por", "devuelto_en"}
    if set(campos) - permitidas:
        raise ValueError(f"Columnas desconocidas en abonos: {sorted(set(campos) - permitidas)}")
    asignaciones = ", ".join(f"{c} = ?" for c in campos)
    conn.execute(f"UPDATE abonos SET {asignaciones} WHERE id = ?", (*campos.values(), abono_id))


def fijar_estado_abonos(conn: sqlite3.Connection, turno_id: int, desde: str, hacia: str) -> None:
    conn.execute("UPDATE abonos SET estado = ? WHERE turno_id = ? AND estado = ?", (hacia, turno_id, desde))


def devolver_abonos(conn: sqlite3.Connection, turno_id: int, personal_id: int, cuando: str) -> int:
    """Marca como devueltos los abonos vigentes del turno. Devuelve el total devuelto."""
    total = conn.execute("SELECT COALESCE(SUM(monto), 0) FROM abonos WHERE turno_id = ? AND estado = 'VIGENTE'",
                         (turno_id,)).fetchone()[0]
    conn.execute(
        "UPDATE abonos SET estado = 'DEVUELTO', devuelto_por = ?, devuelto_en = ? WHERE turno_id = ? AND estado = 'VIGENTE'",
        (personal_id, cuando, turno_id),
    )
    return total


def abonos_a_favor(conn: sqlite3.Connection, propietario_id: int) -> list[sqlite3.Row]:
    """Abonos vigentes de turnos que ya no se atenderán (cancelados, avisó a tiempo o no atendidos):
    quedan a favor del propietario para otro turno (RN-10, [A-8])."""
    return conn.execute(
        f"""SELECT ab.*, t.fecha AS turno_fecha, t.hora AS turno_hora, t.estado AS turno_estado,
                   m.nombre AS mascota_nombre
            FROM abonos ab
            JOIN turnos t ON t.id = ab.turno_id
            JOIN mascotas m ON m.id = t.mascota_id
            WHERE m.propietario_id = ? AND ab.estado = 'VIGENTE'
              AND t.estado IN ('LIBERADO', 'NO_ASISTIO_AVISO', 'NO_ATENDIDO')
            ORDER BY ab.id""",
        (propietario_id,),
    ).fetchall()


def mover_abono(conn: sqlite3.Connection, abono_id: int, turno_id: int) -> None:
    conn.execute("UPDATE abonos SET turno_id = ? WHERE id = ?", (turno_id, abono_id))
