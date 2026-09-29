"""Franjas de cada fecha (RN-04), franjas sueltas, bloqueos (RN-11) y plantilla semanal."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from clinican.datos import repo_auditoria, repo_config, repo_horarios as repo, repo_turnos
from clinican.datos.conexion import transaccion
from clinican.dominio import cupos as reglas_cupos
from clinican.dominio import franjas as reglas
from clinican.dominio.errores import DatoInvalido, ErrorClinican, NoEncontrado
from clinican.dominio.mascotas import validar_fecha
from clinican.dominio.permisos import Accion
from clinican.servicios.base import Sesion, requerir

DIAS = {1: "Lunes", 2: "Martes", 3: "Miércoles", 4: "Jueves", 5: "Viernes", 6: "Sábado", 7: "Domingo"}
MAX_DIAS_RANGO = 366


class BloqueoConTurnos(ErrorClinican):
    """No se puede bloquear: hay turnos activos. ``turnos`` trae la lista para resolverlos."""

    def __init__(self, mensaje: str, turnos: list[sqlite3.Row]):
        super().__init__(mensaje)
        self.turnos = turnos


# ------------------------------------------------------------------ lectura

def franjas(conn: sqlite3.Connection, fecha: str) -> list[reglas.Franja]:
    """RN-04: franjas disponibles de una fecha."""
    ajustes = repo.ajustes(conn, fecha)
    bloqueos = repo.bloqueos(conn, fecha)
    return reglas.franjas_de_fecha(
        fecha,
        repo.base_del_dia(conn, reglas.dia_semana(fecha)) if reglas.dia_semana(fecha) <= 6 else [],
        [a["hora"] for a in ajustes if a["accion"] == "AGREGAR"],
        [a["hora"] for a in ajustes if a["accion"] == "QUITAR"],
        any(b["hora"] is None for b in bloqueos),
        [b["hora"] for b in bloqueos if b["hora"]],
    )


def cupos_libres(conn: sqlite3.Connection, fecha: str, hora: str, excepto: int | None = None) -> dict[str, int]:
    return reglas_cupos.cupos_libres(repo_turnos.ocupados(conn, fecha, hora, excepto), repo_config.todas(conn))


def libres_por_franja(conn: sqlite3.Connection, fecha: str) -> dict[str, dict[str, int]]:
    return {f.hora: cupos_libres(conn, fecha, f.hora) for f in franjas(conn, fecha)}


def bloqueo_del_dia(conn: sqlite3.Connection, fecha: str) -> sqlite3.Row | None:
    return next((b for b in repo.bloqueos(conn, fecha) if b["hora"] is None), None)


def bloqueos_desde(conn: sqlite3.Connection, desde: str | None = None) -> list[sqlite3.Row]:
    return repo.bloqueos_desde(conn, desde or date.today().isoformat())


def ajustes(conn: sqlite3.Connection, fecha: str) -> list[sqlite3.Row]:
    return repo.ajustes(conn, fecha)


def turnos_activos(conn: sqlite3.Connection, fecha: str, hora: str | None = None) -> list[sqlite3.Row]:
    return repo_turnos.activos_en(conn, fecha, hora)


def _no_pasada(fecha: str) -> None:
    if fecha < date.today().isoformat():
        raise DatoInvalido("No se pueden cambiar los horarios de una fecha que ya pasó.")


# -------------------------------------------------- franjas sueltas (todos)

def agregar_franja_suelta(conn, sesion: Sesion, fecha: str, hora: str) -> None:
    """Agrega una hora extra libre en una fecha (ADMIN y PERSONAL)."""
    requerir(conn, sesion, Accion.AJUSTAR_FRANJAS_SUELTAS)
    fecha = validar_fecha(fecha)
    hora = reglas.validar_hora(hora)
    _no_pasada(fecha)
    with transaccion(conn):
        if bloqueo_del_dia(conn, fecha):
            raise DatoInvalido("Ese día está bloqueado por la administradora.")
        if any(b["hora"] == hora for b in repo.bloqueos(conn, fecha)):
            raise DatoInvalido(f"La franja de las {hora} está bloqueada por la administradora.")
        if any(f.hora == hora for f in franjas(conn, fecha)):
            raise DatoInvalido(f"Ya existe una franja a las {hora} ese día.")
        existente = repo.ajuste(conn, fecha, hora)
        if existente is not None:  # un QUITAR previo: se revierte
            repo.borrar_ajuste(conn, existente["id"])
        else:
            repo.insertar_ajuste(conn, fecha, hora, "AGREGAR", sesion.personal_id)
        repo_auditoria.registrar(conn, sesion.personal_id, "AGREGAR_FRANJA", "franjas_ajuste", None, f"{fecha} {hora}")


def quitar_franja_suelta(conn, sesion: Sesion, fecha: str, hora: str) -> None:
    """Quita una hora extra que se había agregado, si no tiene turnos activos."""
    requerir(conn, sesion, Accion.AJUSTAR_FRANJAS_SUELTAS)
    fecha = validar_fecha(fecha)
    hora = reglas.validar_hora(hora)
    with transaccion(conn):
        ajuste = repo.ajuste(conn, fecha, hora)
        if ajuste is None or ajuste["accion"] != "AGREGAR":
            raise DatoInvalido(
                f"La franja de las {hora} es de la plantilla. Solo la administradora puede desactivarla (bloqueo)."
            )
        if repo_turnos.activos_en(conn, fecha, hora):
            raise DatoInvalido(f"La franja de las {hora} tiene turnos activos; muévalos o cancélelos primero.")
        repo.borrar_ajuste(conn, ajuste["id"])
        repo_auditoria.registrar(conn, sesion.personal_id, "QUITAR_FRANJA", "franjas_ajuste", None, f"{fecha} {hora}")


# ------------------------------------------------------ bloqueos (ADMIN)

def _fechas(desde: str, hasta: str) -> list[str]:
    d1, d2 = date.fromisoformat(desde), date.fromisoformat(hasta)
    if d2 < d1:
        raise DatoInvalido("La fecha final no puede ser anterior a la inicial.")
    if (d2 - d1).days + 1 > MAX_DIAS_RANGO:
        raise DatoInvalido(f"El rango no puede tener más de {MAX_DIAS_RANGO} días.")
    return [(d1 + timedelta(days=i)).isoformat() for i in range((d2 - d1).days + 1)]


def bloquear_dias(conn, sesion: Sesion, desde: str, hasta: str | None = None, motivo: str | None = None) -> int:
    """RN-11: desactiva un día o un rango. Solo si no hay turnos activos en esas fechas.

    Si los hay, lanza ``BloqueoConTurnos`` con la lista para que la administradora decida
    (mover, cancelar o no bloquear). Devuelve cuántos días se bloquearon.
    """
    requerir(conn, sesion, Accion.BLOQUEAR_DIAS)
    desde = validar_fecha(desde, "La fecha inicial")
    hasta = validar_fecha(hasta, "La fecha final") if hasta else desde
    _no_pasada(desde)
    fechas = _fechas(desde, hasta)
    motivo = (motivo or "").strip() or None
    with transaccion(conn):
        afectados = [t for f in fechas for t in repo_turnos.activos_en(conn, f)]
        if afectados:
            raise BloqueoConTurnos(
                f"No se puede bloquear: hay {len(afectados)} turno(s) activo(s) en esas fechas. "
                "Muévalos o cancélelos primero, o no bloquee esos días.", afectados)
        nuevos = 0
        for f in fechas:
            if bloqueo_del_dia(conn, f):
                continue
            # Un bloqueo de día completo reemplaza los bloqueos de franjas sueltas de ese día.
            for b in repo.bloqueos(conn, f):
                repo.borrar_bloqueo(conn, b["id"])
            repo.insertar_bloqueo(conn, f, None, motivo, sesion.personal_id)
            nuevos += 1
        texto = desde if desde == hasta else f"{desde} a {hasta}"
        repo_auditoria.registrar(conn, sesion.personal_id, "BLOQUEAR_DIAS", "bloqueos", None,
                                 f"{texto} ({nuevos} día(s)){' — ' + motivo if motivo else ''}")
    return nuevos


def bloquear_franja(conn, sesion: Sesion, fecha: str, hora: str, motivo: str | None = None) -> None:
    """RN-11: desactiva una franja específica sin turnos activos (solo ADMIN)."""
    requerir(conn, sesion, Accion.BLOQUEAR_FRANJAS)
    fecha = validar_fecha(fecha)
    hora = reglas.validar_hora(hora)
    _no_pasada(fecha)
    with transaccion(conn):
        if not any(f.hora == hora for f in franjas(conn, fecha)):
            raise DatoInvalido(f"No hay una franja disponible a las {hora} ese día.")
        afectados = repo_turnos.activos_en(conn, fecha, hora)
        if afectados:
            raise BloqueoConTurnos(f"La franja de las {hora} tiene {len(afectados)} turno(s) activo(s).", afectados)
        repo.insertar_bloqueo(conn, fecha, hora, (motivo or "").strip() or None, sesion.personal_id)
        repo_auditoria.registrar(conn, sesion.personal_id, "BLOQUEAR_FRANJA", "bloqueos", None, f"{fecha} {hora}")


def desbloquear(conn, sesion: Sesion, bloqueo_id: int) -> None:
    with transaccion(conn):
        b = repo.bloqueo(conn, bloqueo_id)
        if b is None:
            raise NoEncontrado("No se encontró el bloqueo.")
        requerir(conn, sesion, Accion.BLOQUEAR_DIAS if b["hora"] is None else Accion.BLOQUEAR_FRANJAS)
        repo.borrar_bloqueo(conn, bloqueo_id)
        repo_auditoria.registrar(conn, sesion.personal_id, "DESBLOQUEAR", "bloqueos", None,
                                 f"{b['fecha']} {b['hora'] or 'día completo'}")


# ------------------------------------------------- plantilla semanal (ADMIN)

def plantilla(conn) -> list[sqlite3.Row]:
    return repo.plantilla(conn)


def fijar_franja_base(conn, sesion: Sesion, dia_semana: int, hora: str, activa: bool) -> None:
    requerir(conn, sesion, Accion.CAMBIAR_CONFIGURACION)
    hora = reglas.validar_hora(hora)
    if dia_semana not in range(1, 7):
        raise DatoInvalido("El día debe ser de lunes a sábado.")
    with transaccion(conn):
        fila = repo.franja_base(conn, dia_semana, hora)
        if fila is None:
            if not activa:
                raise NoEncontrado("Esa franja no existe en la plantilla.")
            repo.insertar_franja_base(conn, dia_semana, hora, reglas.jornada_de(hora))
        else:
            if not activa:
                futuros = conn.execute(
                    "SELECT COUNT(*) FROM turnos WHERE hora = ? AND fecha >= ? AND CAST(strftime('%w', fecha) AS INTEGER) = ? "
                    "AND estado IN ('PENDIENTE_ABONO','CONFIRMADO','EN_PROCESO','LISTA')",
                    (hora, date.today().isoformat(), dia_semana)).fetchone()[0]
                if futuros:
                    raise DatoInvalido(f"Hay {futuros} turno(s) activo(s) futuros los {DIAS[dia_semana].lower()} "
                                       f"a las {hora}. Muévalos o cancélelos primero.")
            repo.fijar_franja_base_activa(conn, fila["id"], activa)
        repo_auditoria.registrar(conn, sesion.personal_id, "PLANTILLA_FRANJA", "franjas_base", None,
                                 f"{DIAS[dia_semana]} {hora}: {'activa' if activa else 'inactiva'}")


