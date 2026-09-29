"""Tablas ``propietarios`` y ``mascotas``."""

from __future__ import annotations

import re
import secrets
import sqlite3

from clinican.dominio.formato import sin_tildes
from clinican.dominio.propietarios import PREFIJO_CEDULA_PROVISIONAL

_AHORA = "datetime('now','localtime')"

_MASCOTA = """
    SELECT m.*, r.nombre AS raza_nombre, r.tamano AS raza_tamano, r.especie,
           r.pelaje_complicado AS raza_pelaje_complicado, p.nombre AS propietario_nombre,
           p.provisional AS propietario_provisional
    FROM mascotas m
    JOIN razas r ON r.id = m.raza_id
    JOIN propietarios p ON p.id = m.propietario_id
"""

# ------------------------------------------------------------ propietarios


def buscar(conn: sqlite3.Connection, texto: str, limite: int = 300) -> list[sqlite3.Row]:
    """Por nombre (sin tildes), cédula, celular o nombre de una mascota. Vacío = todos."""
    texto = (texto or "").strip()
    columnas = """
        SELECT p.*, (SELECT group_concat(m.nombre, ', ') FROM
                       (SELECT nombre FROM mascotas WHERE propietario_id = p.id AND activa = 1 ORDER BY id) m
                    ) AS mascotas
        FROM propietarios p
    """
    if not texto:
        return conn.execute(f"{columnas} ORDER BY sin_tildes(p.nombre) LIMIT ?", (limite,)).fetchall()
    patron = f"%{sin_tildes(texto)}%"
    digitos = re.sub(r"[\s.\-()]", "", texto).upper()
    patron_num = f"%{digitos}%" if digitos else "\x00"
    return conn.execute(
        f"""{columnas}
            WHERE sin_tildes(p.nombre) LIKE ?
               OR p.cedula LIKE ? OR p.celular1 LIKE ? OR IFNULL(p.celular2, '') LIKE ?
               OR EXISTS (SELECT 1 FROM mascotas m WHERE m.propietario_id = p.id AND sin_tildes(m.nombre) LIKE ?)
            ORDER BY sin_tildes(p.nombre) LIMIT ?""",
        (patron, patron_num, patron_num, patron_num, patron, limite),
    ).fetchall()


def propietario(conn: sqlite3.Connection, propietario_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM propietarios WHERE id = ?", (propietario_id,)).fetchone()


def propietario_por_cedula(conn: sqlite3.Connection, cedula: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM propietarios WHERE cedula = ?", (cedula,)).fetchone()


def insertar_propietario(conn: sqlite3.Connection, datos: dict) -> int:
    cur = conn.execute(
        "INSERT INTO propietarios (nombre, cedula, celular1, celular2, direccion) VALUES (?, ?, ?, ?, ?)",
        (datos["nombre"], datos["cedula"], datos["celular1"], datos.get("celular2"), datos["direccion"]),
    )
    return cur.lastrowid


def insertar_provisional(conn: sqlite3.Connection, nombre: str, celular1: str) -> int:
    """Cliente sin registrar: cédula provisional única y dirección vacía hasta completar el registro."""
    temporal = f"{PREFIJO_CEDULA_PROVISIONAL}{secrets.token_hex(8)}"
    cur = conn.execute(
        "INSERT INTO propietarios (nombre, cedula, celular1, direccion, provisional) VALUES (?, ?, ?, '', 1)",
        (nombre, temporal, celular1),
    )
    conn.execute("UPDATE propietarios SET cedula = ? WHERE id = ?",
                 (f"{PREFIJO_CEDULA_PROVISIONAL}{cur.lastrowid}", cur.lastrowid))
    return cur.lastrowid


def completar_registro(conn: sqlite3.Connection, propietario_id: int, datos: dict) -> None:
    actualizar_propietario(conn, propietario_id, datos)
    conn.execute("UPDATE propietarios SET provisional = 0 WHERE id = ?", (propietario_id,))


def borrar_propietario(conn: sqlite3.Connection, propietario_id: int) -> None:
    conn.execute("DELETE FROM propietarios WHERE id = ?", (propietario_id,))


def cambiar_dueno_mascota(conn: sqlite3.Connection, mascota_id: int, propietario_id: int) -> None:
    conn.execute(f"UPDATE mascotas SET propietario_id = ?, actualizado_en = {_AHORA} WHERE id = ?",
                 (propietario_id, mascota_id))


def unir_mascotas(conn: sqlite3.Connection, origen_id: int, destino_id: int) -> None:
    """Pasa turnos, fichas y declaraciones de una mascota a otra y borra la de origen."""
    for tabla in ("turnos", "servicios", "consentimientos"):
        conn.execute(f"UPDATE {tabla} SET mascota_id = ? WHERE mascota_id = ?", (destino_id, origen_id))
    conn.execute("DELETE FROM mascotas WHERE id = ?", (origen_id,))


def actualizar_propietario(conn: sqlite3.Connection, propietario_id: int, datos: dict) -> None:
    conn.execute(
        f"""UPDATE propietarios SET nombre = ?, cedula = ?, celular1 = ?, celular2 = ?, direccion = ?,
               actualizado_en = {_AHORA} WHERE id = ?""",
        (datos["nombre"], datos["cedula"], datos["celular1"], datos.get("celular2"), datos["direccion"],
         propietario_id),
    )


def fijar_requiere_nuevo_abono(conn: sqlite3.Connection, propietario_id: int, valor: bool) -> None:
    conn.execute(f"UPDATE propietarios SET requiere_nuevo_abono = ?, actualizado_en = {_AHORA} WHERE id = ?",
                 (int(bool(valor)), propietario_id))


# ---------------------------------------------------------------- mascotas


def mascotas_de(conn: sqlite3.Connection, propietario_id: int, incluir_inactivas: bool = True) -> list[sqlite3.Row]:
    filtro = "" if incluir_inactivas else "AND m.activa = 1"
    return conn.execute(f"{_MASCOTA} WHERE m.propietario_id = ? {filtro} ORDER BY m.activa DESC, m.id",
                        (propietario_id,)).fetchall()


def mascota(conn: sqlite3.Connection, mascota_id: int) -> sqlite3.Row | None:
    return conn.execute(f"{_MASCOTA} WHERE m.id = ?", (mascota_id,)).fetchone()


def mascota_con_nombre(conn: sqlite3.Connection, propietario_id: int, nombre: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM mascotas WHERE propietario_id = ? AND sin_tildes(nombre) = sin_tildes(?)",
        (propietario_id, " ".join((nombre or "").split())),
    ).fetchone()


_CAMPOS_MASCOTA = ("nombre", "raza_id", "tamano_manual", "pelaje_complicado_manual", "edad_anios", "edad_meses",
                   "fecha_ultima_visita", "observaciones")


def insertar_mascota(conn: sqlite3.Connection, propietario_id: int, datos: dict) -> int:
    cur = conn.execute(
        f"INSERT INTO mascotas (propietario_id, {', '.join(_CAMPOS_MASCOTA)}) "
        f"VALUES (?, {', '.join('?' for _ in _CAMPOS_MASCOTA)})",
        (propietario_id, *(datos.get(c) for c in _CAMPOS_MASCOTA)),
    )
    return cur.lastrowid


def actualizar_mascota(conn: sqlite3.Connection, mascota_id: int, datos: dict) -> None:
    asignaciones = ", ".join(f"{c} = ?" for c in _CAMPOS_MASCOTA)
    conn.execute(f"UPDATE mascotas SET {asignaciones}, actualizado_en = {_AHORA} WHERE id = ?",
                 (*(datos.get(c) for c in _CAMPOS_MASCOTA), mascota_id))


def fijar_mascota_activa(conn: sqlite3.Connection, mascota_id: int, activa: bool) -> None:
    conn.execute(f"UPDATE mascotas SET activa = ?, actualizado_en = {_AHORA} WHERE id = ?",
                 (int(bool(activa)), mascota_id))


def fijar_ultima_visita(conn: sqlite3.Connection, mascota_id: int, fecha: str | None) -> None:
    conn.execute(f"UPDATE mascotas SET fecha_ultima_visita = ?, actualizado_en = {_AHORA} WHERE id = ?",
                 (fecha, mascota_id))


def historial_servicios(conn: sqlite3.Connection, mascota_id: int) -> list[sqlite3.Row]:
    """Fichas de servicio de la mascota, de la más reciente a la más antigua, con el desenredado sumado."""
    return conn.execute(
        """SELECT s.*, (SELECT COALESCE(SUM(d.precio), 0) FROM sesiones_desenredado d WHERE d.servicio_id = s.id)
                  AS desenredado
           FROM servicios s WHERE s.mascota_id = ? ORDER BY s.fecha DESC, s.id DESC""",
        (mascota_id,),
    ).fetchall()
