"""Bandeja de salida de notificaciones (tabla ``notificaciones_salida``)."""

from __future__ import annotations

import sqlite3

_FMT = "%Y-%m-%d %H:%M:%S"


def programar(conn: sqlite3.Connection, turno_id: int, plantilla: str, enviar_desde: str) -> None:
    """Deja un mensaje pendiente para el turno. Si ya había uno sin enviar, actualiza la hora
    (por ejemplo, al mover el turno); si ya se envió o se descartó, lo vuelve a dejar pendiente."""
    conn.execute(
        """INSERT INTO notificaciones_salida (turno_id, plantilla, enviar_desde) VALUES (?, ?, ?)
           ON CONFLICT (turno_id, plantilla) DO UPDATE SET
               enviar_desde = excluded.enviar_desde, estado = 'PENDIENTE', intentos = 0,
               siguiente_intento = NULL, ultimo_error = NULL, cerrado_en = NULL""",
        (turno_id, plantilla, enviar_desde))


def listos_para_enviar(conn: sqlite3.Connection, ahora: str, limite: int = 50) -> list[sqlite3.Row]:
    """Pendientes cuya hora de envío llegó y que no están esperando un reintento.

    Trae lo que el despachador necesita del turno, el propietario y la mascota.
    """
    return conn.execute(
        """SELECT n.*, t.estado AS turno_estado, t.fecha, t.hora, m.propietario_id,
                  p.nombre AS propietario_nombre, p.celular1, m.nombre AS mascota_nombre
           FROM notificaciones_salida n
           JOIN turnos t ON t.id = n.turno_id
           JOIN mascotas m ON m.id = t.mascota_id
           JOIN propietarios p ON p.id = m.propietario_id
           WHERE n.estado = 'PENDIENTE' AND n.enviar_desde <= ?
             AND (n.siguiente_intento IS NULL OR n.siguiente_intento <= ?)
           ORDER BY n.enviar_desde, n.id LIMIT ?""",
        (ahora, ahora, limite)).fetchall()


def marcar_enviado(conn: sqlite3.Connection, salida_id: int, canal: str, destino: str, texto: str, ahora: str) -> None:
    conn.execute("""UPDATE notificaciones_salida SET estado = 'ENVIADO', intentos = intentos + 1, canal = ?,
                    destino = ?, texto = ?, ultimo_error = NULL, cerrado_en = ? WHERE id = ?""",
                 (canal, destino, texto, ahora, salida_id))


def marcar_fallo(conn: sqlite3.Connection, salida_id: int, canal: str, error: str, siguiente: str) -> None:
    conn.execute("""UPDATE notificaciones_salida SET intentos = intentos + 1, canal = ?, ultimo_error = ?,
                    siguiente_intento = ? WHERE id = ?""", (canal, error[:500], siguiente, salida_id))


def marcar_descartado(conn: sqlite3.Connection, salida_id: int, motivo: str, ahora: str) -> None:
    conn.execute("""UPDATE notificaciones_salida SET estado = 'DESCARTADO', ultimo_error = ?, cerrado_en = ?
                    WHERE id = ?""", (motivo, ahora, salida_id))


def de_turno(conn: sqlite3.Connection, turno_id: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM notificaciones_salida WHERE turno_id = ? ORDER BY id", (turno_id,)).fetchall()


def recientes(conn: sqlite3.Connection, limite: int = 100) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT n.*, m.nombre AS mascota_nombre, t.fecha, t.hora FROM notificaciones_salida n
           JOIN turnos t ON t.id = n.turno_id JOIN mascotas m ON m.id = t.mascota_id
           ORDER BY n.id DESC LIMIT ?""", (limite,)).fetchall()


def conteo_por_estado(conn: sqlite3.Connection) -> dict[str, int]:
    return {f[0]: f[1] for f in conn.execute(
        "SELECT estado, COUNT(*) FROM notificaciones_salida GROUP BY estado")}


def purgar_cerrados(conn: sqlite3.Connection, antes_de: str) -> int:
    """Borra los mensajes enviados o descartados antes de esa fecha (la tabla no crece sin límite)."""
    return conn.execute("DELETE FROM notificaciones_salida WHERE estado <> 'PENDIENTE' AND cerrado_en < ?",
                        (antes_de,)).rowcount
