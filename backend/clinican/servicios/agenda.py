"""Casos de uso de la agenda: turnos, abonos, inasistencias y bloqueos.

Cada escritura corre dentro de ``transaccion()`` (BEGIN IMMEDIATE), así que la
ocupación de una franja se cuenta y se escribe sin que otra conexión pueda
meterse en medio. El reloj se recibe en ``ahora``: nada aquí lee la hora.

``barrer_vencidos`` debe llamarse al iniciar el programa y periódicamente.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime

from clinican.datos import repo_agenda, repo_clientes
from clinican.datos.conexion import transaccion
from clinican.dominio.abonos import (
    aplicar_saldo,
    esta_vencido,
    resultado_inasistencia,
    validar_pesos,
    vence_en,
)
from clinican.dominio.agenda import ZONA, Bloqueo, Franja, generar_franjas
from clinican.dominio.cupos import (
    CategoriaCupo,
    Servicio,
    cabe_uno_mas,
    categoria_de_cupo,
    cupos_libres,
)
from clinican.dominio.entidades import Turno
from clinican.dominio.errores import (
    AbonoRechazado,
    BloqueoConTurnos,
    DatoInvalido,
    NoEncontrado,
    OperacionNoPermitida,
    SinCupo,
)
from clinican.dominio.estados import EstadoTurno, MotivoLiberacion, transicionar
from clinican.dominio.turnos import contar_ocupacion, esta_activo, validar_franja
from clinican.servicios import configuracion, fichas, notificaciones
from clinican.servicios.auditoria import auditar
from clinican.servicios.configuracion import ConfigClinica

E = EstadoTurno

NOMBRE_CATEGORIA = {
    CategoriaCupo.MAQUINA: "máquina",
    CategoriaCupo.GRANDE: "perro grande",
    CategoriaCupo.TIJERA: "tijera",
    CategoriaCupo.COMPLICADO: "perro complicado",
}

NOMBRE_ESTADO = {
    E.PENDIENTE_ABONO: "pendiente de abono",
    E.CONFIRMADO: "confirmado",
    E.EN_ATENCION: "en atención",
    E.ATENDIDO: "atendido",
    E.ENTREGADO: "entregado",
    E.LIBERADO: "liberado",
    E.CANCELADO: "cancelado",
    E.INASISTENCIA: "marcado como inasistencia",
}


def _hora(momento: datetime) -> str:
    return momento.astimezone(ZONA).strftime("%H:%M del %d/%m/%Y")


def _con_zona(momento: datetime, nombre: str) -> datetime:
    if not isinstance(momento, datetime) or momento.tzinfo is None or momento.utcoffset() is None:
        raise DatoInvalido(f"{nombre} debe ser una fecha y hora con zona horaria")
    return momento


# --------------------------------------------------------------------------- consultas


def obtener_turno(con, turno_id: int) -> Turno:
    turno = repo_agenda.obtener_turno(con, turno_id)
    if turno is None:
        raise NoEncontrado(f"No existe el turno {turno_id}")
    return turno


def turnos_del_dia(con, dia: date) -> list[Turno]:
    return repo_agenda.turnos_del_dia(con, dia)


def bloqueos_del_dia(con, dia: date) -> list[Bloqueo]:
    return repo_agenda.bloqueos_del_dia(con, dia)


def inasistencias_de_propietario(con, propietario_id: int) -> list[Turno]:
    return repo_agenda.turnos_de_propietario(con, propietario_id, E.INASISTENCIA)


def disponibilidad(con, dia: date, *, ahora: datetime) -> list[tuple[Franja, dict[CategoriaCupo, int]]]:
    """Franjas reservables del día con los cupos libres por categoría."""
    cfg = configuracion.cargar(con)
    turnos = repo_agenda.turnos_del_dia(con, dia)
    salida = []
    for franja in generar_franjas(dia, cfg.horario, repo_agenda.bloqueos_del_dia(con, dia)):
        en_franja = [t for t in turnos if t.inicio == franja.inicio]
        ocupacion = contar_ocupacion(en_franja, ahora, cfg.minutos_expiracion)
        salida.append((franja, {c: cupos_libres(cfg.cupos, ocupacion, c) for c in CategoriaCupo}))
    return salida


# --------------------------------------------------------------------------- internas


def _verificar_cupo(
    con,
    inicio: datetime,
    categoria: CategoriaCupo,
    cfg: ConfigClinica,
    ahora: datetime,
    excluir_id: int | None = None,
) -> Franja:
    """Valida la franja y cuenta su ocupación (debe llamarse dentro de la transacción)."""
    _con_zona(inicio, "La hora del turno")
    dia = inicio.astimezone(ZONA).date()
    franja = validar_franja(inicio, cfg.horario, repo_agenda.bloqueos_del_dia(con, dia))
    turnos = repo_agenda.turnos_en_inicio(con, franja.inicio)
    ocupacion = contar_ocupacion(turnos, ahora, cfg.minutos_expiracion, excluir_id)
    if not cabe_uno_mas(cfg.cupos, ocupacion, categoria):
        raise SinCupo(
            f"No hay cupo de {NOMBRE_CATEGORIA[categoria]} a las {_hora(franja.inicio)}: "
            f"{ocupacion[categoria]} de {cfg.cupos.capacidad(categoria)} ocupados"
        )
    return franja


def _devolver_lo_puesto(con, turno: Turno) -> dict:
    """Pendiente que se libera o cancela: el saldo aplicado vuelve al propietario y lo
    abonado parcialmente queda como saldo a favor. Devuelve los campos a actualizar."""
    total = turno.saldo_aplicado + turno.abono_pagado
    if total:
        repo_clientes.sumar_saldo(con, turno.propietario_id, total)
    return {"saldo_aplicado": 0, "saldo_generado": turno.abono_pagado}


def _liberar(con, turno: Turno, motivo: MotivoLiberacion, ahora: datetime) -> None:
    """Libera un pendiente de abono; lo que el cliente ya había puesto vuelve a su saldo."""
    transicionar(turno.estado, E.LIBERADO, motivo)
    campos = {"estado": E.LIBERADO, "motivo_liberacion": motivo, **_devolver_lo_puesto(con, turno)}
    repo_agenda.actualizar_turno(con, turno.id, **campos)
    auditar(con, ahora, "liberar", "turno", turno.id, motivo=motivo.value,
            saldo_devuelto=turno.saldo_aplicado, abono_a_favor=turno.abono_pagado)


def _pendiente_vencido(turno: Turno, cfg: ConfigClinica, ahora: datetime) -> bool:
    return turno.estado is E.PENDIENTE_ABONO and esta_vencido(
        turno.creado_en, ahora, cfg.minutos_expiracion
    )


# --------------------------------------------------------------------------- turnos


def crear_turno(con, mascota_id: int, inicio: datetime, servicio: Servicio, *, ahora: datetime) -> Turno:
    """Reserva un turno en la franja ``inicio``.

    Si el propietario tiene saldo a favor se aplica automáticamente al abono: si
    lo cubre todo, el turno nace CONFIRMADO; si no, PENDIENTE_ABONO por el faltante.
    """
    _con_zona(ahora, "ahora")
    if not isinstance(servicio, Servicio):
        raise DatoInvalido("El servicio debe ser uno de: " + ", ".join(s.value for s in Servicio))
    with transaccion(con):
        cfg = configuracion.cargar(con)
        mascota = repo_clientes.obtener_mascota(con, mascota_id)
        if mascota is None:
            raise NoEncontrado(f"No existe la mascota {mascota_id}")
        if not mascota.activo:
            raise OperacionNoPermitida(f"La mascota {mascota.nombre} está inactiva")
        propietario = repo_clientes.obtener_propietario(con, mascota.propietario_id)
        if not propietario.activo:
            raise OperacionNoPermitida(f"El propietario {propietario.nombre} está inactivo")
        raza = None if mascota.raza_id is None else repo_clientes.obtener_raza(con, mascota.raza_id)
        categoria = categoria_de_cupo(
            None if raza is None else raza.nombre, mascota.tamano, mascota.pelaje,
            servicio, mascota.complicado,
        )
        franja = _verificar_cupo(con, inicio, categoria, cfg, ahora)
        cubierto, _, faltante = aplicar_saldo(propietario.saldo_a_favor, cfg.abono)
        estado = E.CONFIRMADO if faltante == 0 else E.PENDIENTE_ABONO
        if cubierto:
            repo_clientes.sumar_saldo(con, propietario.id, -cubierto)
        turno_id = repo_agenda.insertar_turno(
            con,
            mascota_id=mascota.id,
            propietario_id=propietario.id,
            inicio=franja.inicio,
            servicio=servicio,
            categoria=categoria,
            estado=estado,
            abono_requerido=cfg.abono,
            saldo_aplicado=cubierto,
            creado_en=ahora,
        )
        auditar(
            con, ahora, "crear", "turno", turno_id,
            mascota_id=mascota.id, propietario_id=propietario.id, inicio=franja.inicio.isoformat(),
            servicio=servicio.value, categoria=categoria.value, estado=estado.value,
            abono_requerido=cfg.abono, saldo_aplicado=cubierto,
        )
        if estado is E.CONFIRMADO:
            notificaciones.programar_recordatorio(
                con, turno_id, franja.inicio, cfg.horas_antes_recordatorio, ahora
            )
    return obtener_turno(con, turno_id)


def registrar_abono(con, turno_id: int, monto: int, *, ahora: datetime) -> Turno:
    """Registra un abono (parcial, exacto o de más) de un turno pendiente.

    Los parciales se acumulan y el turno sigue PENDIENTE_ABONO hasta cubrir el
    abono requerido; entonces pasa a CONFIRMADO. Lo pagado de más queda como
    saldo a favor del propietario. Si el abono ya venció (30 min desde la
    creación), el turno se libera (ABONO_VENCIDO) en la misma transacción, lo
    que ya había pagado pasa a saldo a favor y este abono se rechaza.
    """
    _con_zona(ahora, "ahora")
    try:
        validar_pesos(monto, "monto")
    except (TypeError, ValueError) as error:
        raise DatoInvalido(str(error)) from None
    if monto == 0:
        raise DatoInvalido("El abono debe ser mayor que cero")
    vencio_a_las = None
    with transaccion(con):
        cfg = configuracion.cargar(con)
        turno = obtener_turno(con, turno_id)
        if turno.estado is not E.PENDIENTE_ABONO:
            raise AbonoRechazado(
                f"No se puede registrar el abono: el turno está {NOMBRE_ESTADO[turno.estado]}"
            )
        if _pendiente_vencido(turno, cfg, ahora):
            _liberar(con, turno, MotivoLiberacion.ABONO_VENCIDO, ahora)
            vencio_a_las = vence_en(turno.creado_en, cfg.minutos_expiracion)
        else:
            aplicado = min(monto, turno.faltante)
            excedente = monto - aplicado
            campos = {"abono_pagado": turno.abono_pagado + aplicado, "abonado_en": ahora}
            completo = aplicado == turno.faltante
            if completo:
                transicionar(turno.estado, E.CONFIRMADO)
                campos["estado"] = E.CONFIRMADO
            repo_agenda.actualizar_turno(con, turno.id, **campos)
            if excedente:
                repo_clientes.sumar_saldo(con, turno.propietario_id, excedente)
            auditar(con, ahora, "abonar", "turno", turno.id, monto=monto, aplicado=aplicado,
                    excedente_a_favor=excedente, faltante=turno.faltante - aplicado,
                    confirmado=completo)
            if completo:
                notificaciones.programar_recordatorio(
                    con, turno.id, turno.inicio, cfg.horas_antes_recordatorio, ahora
                )
    if vencio_a_las is not None:
        raise AbonoRechazado(
            f"El abono venció a las {_hora(vencio_a_las)}; el turno se liberó. "
            "Si aún hay cupo, cree un turno nuevo."
        )
    return obtener_turno(con, turno_id)


def barrer_vencidos(con, *, ahora: datetime) -> list[int]:
    """Libera (ABONO_VENCIDO) todos los pendientes cuyo abono ya venció."""
    _con_zona(ahora, "ahora")
    liberados = []
    with transaccion(con):
        cfg = configuracion.cargar(con)
        for turno in repo_agenda.turnos_por_estado(con, E.PENDIENTE_ABONO):
            if _pendiente_vencido(turno, cfg, ahora):
                _liberar(con, turno, MotivoLiberacion.ABONO_VENCIDO, ahora)
                liberados.append(turno.id)
    return liberados


def liberar_turno(con, turno_id: int, motivo: MotivoLiberacion, *, ahora: datetime) -> Turno:
    """Libera manualmente un pendiente de abono (p. ej. otro cliente pagó primero)."""
    _con_zona(ahora, "ahora")
    with transaccion(con):
        _liberar(con, obtener_turno(con, turno_id), motivo, ahora)
    return obtener_turno(con, turno_id)


def mover_turno(con, turno_id: int, nuevo_inicio: datetime, *, ahora: datetime) -> Turno:
    """Cambia la franja de un turno pendiente o confirmado, revalidando el cupo."""
    _con_zona(ahora, "ahora")
    vencido = False
    with transaccion(con):
        cfg = configuracion.cargar(con)
        turno = obtener_turno(con, turno_id)
        if _pendiente_vencido(turno, cfg, ahora):
            _liberar(con, turno, MotivoLiberacion.ABONO_VENCIDO, ahora)
            vencido = True
        elif turno.estado not in (E.PENDIENTE_ABONO, E.CONFIRMADO):
            raise OperacionNoPermitida(
                f"No se puede mover un turno {NOMBRE_ESTADO[turno.estado]}"
            )
        else:
            franja = _verificar_cupo(con, nuevo_inicio, turno.categoria, cfg, ahora, turno.id)
            repo_agenda.actualizar_turno(con, turno.id, inicio=franja.inicio)
            auditar(con, ahora, "mover", "turno", turno.id,
                    antes=turno.inicio.isoformat(), despues=franja.inicio.isoformat())
            notificaciones.descartar_pendientes(con, turno.id, "El turno se movió", ahora)
            if turno.estado is E.CONFIRMADO:
                notificaciones.programar_recordatorio(
                    con, turno.id, franja.inicio, cfg.horas_antes_recordatorio, ahora
                )
    if vencido:
        raise OperacionNoPermitida("El abono del turno venció y el turno se liberó")
    return obtener_turno(con, turno_id)


def cancelar_turno(con, turno_id: int, *, ahora: datetime) -> Turno:
    """Cancela un turno pendiente o confirmado.

    Todo lo que el cliente había puesto en el turno (abono pagado y saldo
    aplicado) queda como saldo a favor del propietario, sin importar la
    anticipación con que cancele.
    """
    _con_zona(ahora, "ahora")
    with transaccion(con):
        turno = obtener_turno(con, turno_id)
        transicionar(turno.estado, E.CANCELADO)
        if turno.estado is E.PENDIENTE_ABONO:
            campos = _devolver_lo_puesto(con, turno)
        else:  # CONFIRMADO
            if turno.abono_total:
                repo_clientes.sumar_saldo(con, turno.propietario_id, turno.abono_total)
            campos = {"saldo_generado": turno.abono_total}
        repo_agenda.actualizar_turno(con, turno.id, estado=E.CANCELADO, **campos)
        auditar(con, ahora, "cancelar", "turno", turno.id,
                estado_anterior=turno.estado.value, a_favor=turno.abono_total)
    return obtener_turno(con, turno_id)


def marcar_inasistencia(
    con, turno_id: int, aviso_en: datetime | None = None, *, ahora: datetime
) -> Turno:
    """Marca la inasistencia. Con aviso de 12 h o más, el abono pasa a saldo a favor."""
    _con_zona(ahora, "ahora")
    if aviso_en is not None:
        _con_zona(aviso_en, "La hora del aviso")
        if aviso_en > ahora:
            raise DatoInvalido("La hora del aviso no puede ser posterior a ahora")
    with transaccion(con):
        turno = obtener_turno(con, turno_id)
        transicionar(turno.estado, E.INASISTENCIA)
        saldo = resultado_inasistencia(turno.inicio, aviso_en, turno.abono_total)
        repo_agenda.actualizar_turno(
            con, turno.id, estado=E.INASISTENCIA, aviso_inasistencia_en=aviso_en,
            saldo_generado=saldo,
        )
        if saldo:
            repo_clientes.sumar_saldo(con, turno.propietario_id, saldo)
        auditar(con, ahora, "inasistencia", "turno", turno.id,
                aviso_en=None if aviso_en is None else aviso_en.isoformat(),
                abono=turno.abono_total, saldo_a_favor=saldo)
    return obtener_turno(con, turno_id)


def _cambiar_estado(con, turno_id: int, nuevo: EstadoTurno, ahora: datetime) -> Turno:
    _con_zona(ahora, "ahora")
    with transaccion(con):
        turno = obtener_turno(con, turno_id)
        transicionar(turno.estado, nuevo)
        repo_agenda.actualizar_turno(con, turno.id, estado=nuevo)
        auditar(con, ahora, "cambiar_estado", "turno", turno.id,
                antes=turno.estado.value, despues=nuevo.value)
    return obtener_turno(con, turno_id)


def iniciar_atencion(con, turno_id: int, *, ahora: datetime) -> Turno:
    return _cambiar_estado(con, turno_id, E.EN_ATENCION, ahora)


def marcar_atendido(
    con,
    turno_id: int,
    *,
    ahora: datetime,
    servicios_realizados: str = "",
    detalles_corte: str = "",
    observaciones: str = "",
) -> Turno:
    """Pasa el turno a ATENDIDO y crea su ficha de servicio en la misma transacción."""
    _con_zona(ahora, "ahora")
    with transaccion(con):
        turno = obtener_turno(con, turno_id)
        transicionar(turno.estado, E.ATENDIDO)
        repo_agenda.actualizar_turno(con, turno.id, estado=E.ATENDIDO)
        auditar(con, ahora, "cambiar_estado", "turno", turno.id,
                antes=turno.estado.value, despues=E.ATENDIDO.value)
        fichas.crear_ficha_en_transaccion(
            con, replace(turno, estado=E.ATENDIDO), ahora,
            servicios_realizados, detalles_corte, observaciones,
        )
    return obtener_turno(con, turno_id)


def marcar_entregado(con, turno_id: int, *, ahora: datetime) -> Turno:
    return _cambiar_estado(con, turno_id, E.ENTREGADO, ahora)


# --------------------------------------------------------------------------- bloqueos


def crear_bloqueo(con, bloqueo: Bloqueo, *, ahora: datetime) -> Bloqueo:
    """Bloquea un día completo o un rango de horas.

    Se rechaza si cubre turnos activos (pendientes no vencidos, confirmados o en
    atención): primero hay que moverlos o cancelarlos.
    """
    _con_zona(ahora, "ahora")
    if not isinstance(bloqueo, Bloqueo):
        raise DatoInvalido("Se esperaba un Bloqueo")
    with transaccion(con):
        cfg = configuracion.cargar(con)
        afectados = [
            t for t in repo_agenda.turnos_del_dia(con, bloqueo.fecha)
            if esta_activo(t, ahora, cfg.minutos_expiracion) and bloqueo.cubre(Franja(t.inicio))
        ]
        if afectados:
            horas = ", ".join(sorted({t.inicio.astimezone(ZONA).strftime("%H:%M") for t in afectados}))
            raise BloqueoConTurnos(
                f"No se puede bloquear: hay {len(afectados)} turno(s) activo(s) "
                f"a las {horas}. Muévalos o cancélelos primero."
            )
        bloqueo_id = repo_agenda.insertar_bloqueo(con, bloqueo)
        auditar(
            con, ahora, "crear", "bloqueo", bloqueo_id, fecha=bloqueo.fecha.isoformat(),
            desde=None if bloqueo.desde is None else bloqueo.desde.strftime("%H:%M"),
            hasta=None if bloqueo.hasta is None else bloqueo.hasta.strftime("%H:%M"),
            motivo=bloqueo.motivo,
        )
    return repo_agenda.obtener_bloqueo(con, bloqueo_id)[0]


def quitar_bloqueo(con, bloqueo_id: int, *, ahora: datetime) -> None:
    _con_zona(ahora, "ahora")
    with transaccion(con):
        encontrado = repo_agenda.obtener_bloqueo(con, bloqueo_id)
        if encontrado is None:
            raise NoEncontrado(f"No existe el bloqueo {bloqueo_id}")
        if not encontrado[1]:
            raise OperacionNoPermitida("Ese bloqueo ya fue quitado")
        repo_agenda.desactivar_bloqueo(con, bloqueo_id)
        auditar(con, ahora, "quitar", "bloqueo", bloqueo_id)
