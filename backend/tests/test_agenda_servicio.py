from datetime import datetime, time

import pytest

from clinican.datos import repo_clientes
from clinican.datos.conexion import abrir
from clinican.dominio.agenda import Bloqueo
from clinican.dominio.cupos import CategoriaCupo as C
from clinican.dominio.cupos import CuposPorFranja, Servicio
from clinican.dominio.errores import (
    AbonoRechazado,
    BloqueoConTurnos,
    DatoInvalido,
    FranjaNoDisponible,
    NoEncontrado,
    OperacionNoPermitida,
    SinCupo,
)
from clinican.dominio.estados import EstadoTurno as E
from clinican.dominio.estados import MotivoLiberacion as M
from clinican.dominio.estados import TransicionInvalida
from clinican.servicios import agenda, clientes, configuracion
from clinican.servicios.auditoria import historial
from conftest import AHORA, DOMINGO, LUNES, a_las, timedelta

MIN30 = timedelta(minutes=30)


def _saldo(con, propietario_id):
    return clientes.obtener_propietario(con, propietario_id).saldo_a_favor


# --------------------------------------------------------------------------- crear


def test_crear_turno_pendiente(con, esc):
    t = esc.turno(C.MAQUINA)
    assert t.estado is E.PENDIENTE_ABONO
    assert t.categoria is C.MAQUINA
    assert (t.abono_requerido, t.abono_pagado, t.saldo_aplicado, t.faltante) == (20000, 0, 0, 20000)
    assert t.inicio == a_las(9) and t.creado_en == AHORA
    registro = historial(con, "turno", t.id)[0]
    assert registro.accion == "crear" and registro.detalle["categoria"] == "maquina"


@pytest.mark.parametrize(
    "inicio, error",
    [
        (a_las(9, 15), FranjaNoDisponible),
        (a_las(8, 30), FranjaNoDisponible),
        (a_las(17, 0), FranjaNoDisponible),
        (a_las(10, dia=DOMINGO), FranjaNoDisponible),
        (datetime(2026, 11, 9, 9, 0), DatoInvalido),
    ],
)
def test_franja_no_valida(con, esc, inicio, error):
    m = esc.mascota()
    with pytest.raises(error):
        agenda.crear_turno(con, m.id, inicio, Servicio.CORTE_MAQUINA, ahora=AHORA)
    assert historial(con, "turno") == []


def test_ultima_franja_1630(esc):
    assert esc.turno(inicio=a_las(16, 30)).inicio == a_las(16, 30)


def test_franja_bloqueada(con, esc):
    agenda.crear_bloqueo(con, Bloqueo(LUNES, time(9), time(10), "Fumigación"), ahora=AHORA)
    with pytest.raises(FranjaNoDisponible, match="Fumigación"):
        esc.turno(inicio=a_las(9, 30))
    assert esc.turno(inicio=a_las(10)).estado is E.PENDIENTE_ABONO


def test_cupos_por_categoria(con, esc):
    esc.turno(C.MAQUINA)
    esc.turno(C.MAQUINA)
    with pytest.raises(SinCupo, match="máquina.*2 de 2"):
        esc.turno(C.MAQUINA)
    for cat in (C.GRANDE, C.TIJERA, C.COMPLICADO):
        esc.turno(cat)
        with pytest.raises(SinCupo):
            esc.turno(cat)
    # Otra franja está libre
    assert esc.turno(C.MAQUINA, inicio=a_las(9, 30)).estado is E.PENDIENTE_ABONO


def test_pendiente_vencido_no_ocupa_cupo(con, esc):
    esc.turno(C.GRANDE, ahora=AHORA)
    with pytest.raises(SinCupo):
        esc.turno(C.GRANDE, ahora=AHORA + MIN30 - timedelta(seconds=1))
    assert esc.turno(C.GRANDE, ahora=AHORA + MIN30).estado is E.PENDIENTE_ABONO


def test_confirmado_y_atendidos_ocupan_cupo(con, esc):
    t = esc.turno(C.GRANDE)
    agenda.registrar_abono(con, t.id, 20000, ahora=AHORA)
    agenda.iniciar_atencion(con, t.id, ahora=a_las(9))
    agenda.marcar_atendido(con, t.id, ahora=a_las(9, 30))
    agenda.marcar_entregado(con, t.id, ahora=a_las(10))
    with pytest.raises(SinCupo):
        esc.turno(C.GRANDE, ahora=a_las(12))


def test_cupos_configurables(con, esc):
    configuracion.guardar(con, "cupos", CuposPorFranja(maquina=1), ahora=AHORA)
    esc.turno(C.MAQUINA)
    with pytest.raises(SinCupo):
        esc.turno(C.MAQUINA)


def test_abono_configurable(con, esc):
    configuracion.guardar(con, "abono", 15000, ahora=AHORA)
    assert esc.turno().abono_requerido == 15000


# --------------------------------------------------------------------------- saldo a favor


def test_saldo_cubre_todo_el_abono(con, esc):
    p = esc.propietario(saldo=25000)
    t = esc.turno(propietario=p)
    assert t.estado is E.CONFIRMADO
    assert (t.saldo_aplicado, t.faltante) == (20000, 0)
    assert _saldo(con, p.id) == 5000


def test_saldo_parcial(con, esc):
    p = esc.propietario(saldo=5000)
    t = esc.turno(propietario=p)
    assert t.estado is E.PENDIENTE_ABONO
    assert (t.saldo_aplicado, t.faltante) == (5000, 15000)
    assert _saldo(con, p.id) == 0
    t = agenda.registrar_abono(con, t.id, 15000, ahora=AHORA + timedelta(minutes=10))
    assert t.estado is E.CONFIRMADO and t.abono_pagado == 15000


def test_liberar_devuelve_saldo_aplicado(con, esc):
    p = esc.propietario(saldo=5000)
    t = esc.turno(propietario=p)
    assert agenda.barrer_vencidos(con, ahora=AHORA + MIN30) == [t.id]
    t = agenda.obtener_turno(con, t.id)
    assert (t.estado, t.motivo_liberacion, t.saldo_aplicado) == (E.LIBERADO, M.ABONO_VENCIDO, 0)
    assert _saldo(con, p.id) == 5000


# --------------------------------------------------------------------------- abonos


def test_registrar_abono_confirma(con, esc):
    t = esc.turno()
    t = agenda.registrar_abono(con, t.id, 20000, ahora=AHORA + timedelta(minutes=29))
    assert t.estado is E.CONFIRMADO
    assert t.abono_pagado == 20000 and t.abonado_en == AHORA + timedelta(minutes=29)
    assert historial(con, "turno", t.id)[-1].accion == "abonar"


@pytest.mark.parametrize("monto", [10000, 25000])
def test_abono_con_monto_distinto(con, esc, monto):
    t = esc.turno()
    with pytest.raises(AbonoRechazado, match=r"\$20\.000"):
        agenda.registrar_abono(con, t.id, monto, ahora=AHORA)
    assert agenda.obtener_turno(con, t.id).estado is E.PENDIENTE_ABONO


@pytest.mark.parametrize("monto", [20000.0, -1, "20000"])
def test_abono_solo_pesos_enteros(con, esc, monto):
    t = esc.turno()
    with pytest.raises(DatoInvalido):
        agenda.registrar_abono(con, t.id, monto, ahora=AHORA)


def test_abono_vencido_libera_y_rechaza(con, esc, ruta_db):
    t = esc.turno()
    with pytest.raises(AbonoRechazado, match="venció"):
        agenda.registrar_abono(con, t.id, 20000, ahora=AHORA + MIN30)
    otra = abrir(ruta_db)  # la liberación quedó confirmada en disco
    try:
        guardado = agenda.obtener_turno(otra, t.id)
    finally:
        otra.close()
    assert (guardado.estado, guardado.motivo_liberacion) == (E.LIBERADO, M.ABONO_VENCIDO)
    assert guardado.abono_pagado == 0
    assert [r.accion for r in historial(con, "turno", t.id)] == ["crear", "liberar"]


def test_abono_a_turno_liberado_o_cancelado(con, esc):
    t1, t2 = esc.turno(), esc.turno()
    agenda.liberar_turno(con, t1.id, M.OTRO_PAGO_PRIMERO, ahora=AHORA)
    agenda.cancelar_turno(con, t2.id, ahora=AHORA)
    with pytest.raises(AbonoRechazado, match="liberado"):
        agenda.registrar_abono(con, t1.id, 20000, ahora=AHORA)
    with pytest.raises(AbonoRechazado, match="cancelado"):
        agenda.registrar_abono(con, t2.id, 20000, ahora=AHORA)


def test_abono_doble(con, esc):
    t = esc.turno()
    agenda.registrar_abono(con, t.id, 20000, ahora=AHORA)
    with pytest.raises(AbonoRechazado, match="confirmado"):
        agenda.registrar_abono(con, t.id, 20000, ahora=AHORA)


def test_turno_inexistente(con):
    with pytest.raises(NoEncontrado):
        agenda.registrar_abono(con, 999, 20000, ahora=AHORA)


def test_barrer_vencidos_solo_libera_vencidos(con, esc):
    viejo = esc.turno(ahora=AHORA)
    nuevo = esc.turno(ahora=AHORA + timedelta(minutes=10))
    confirmado = esc.turno(C.GRANDE, ahora=AHORA)
    agenda.registrar_abono(con, confirmado.id, 20000, ahora=AHORA)
    assert agenda.barrer_vencidos(con, ahora=AHORA + timedelta(minutes=35)) == [viejo.id]
    assert agenda.obtener_turno(con, nuevo.id).estado is E.PENDIENTE_ABONO
    assert agenda.obtener_turno(con, confirmado.id).estado is E.CONFIRMADO
    assert agenda.barrer_vencidos(con, ahora=AHORA + timedelta(minutes=35)) == []


def test_minutos_de_expiracion_configurables(con, esc):
    configuracion.guardar(con, "minutos_expiracion", 60, ahora=AHORA)
    t = esc.turno()
    assert agenda.barrer_vencidos(con, ahora=AHORA + timedelta(minutes=59)) == []
    assert agenda.barrer_vencidos(con, ahora=AHORA + timedelta(minutes=60)) == [t.id]


# --------------------------------------------------------------------------- mover / cancelar


def test_mover_turno(con, esc):
    t = esc.turno(inicio=a_las(9))
    t = agenda.mover_turno(con, t.id, a_las(11), ahora=AHORA)
    assert t.inicio == a_las(11)
    assert historial(con, "turno", t.id)[-1].accion == "mover"


def test_mover_revalida_cupo_excluyendo_el_propio(con, esc):
    a = esc.turno(inicio=a_las(9))
    esc.turno(inicio=a_las(9))
    esc.turno(inicio=a_las(10))
    esc.turno(inicio=a_las(10))
    with pytest.raises(SinCupo):
        agenda.mover_turno(con, a.id, a_las(10), ahora=AHORA)
    # Moverlo a su misma franja llena no cuenta dos veces
    assert agenda.mover_turno(con, a.id, a_las(9), ahora=AHORA).inicio == a_las(9)
    with pytest.raises(FranjaNoDisponible):
        agenda.mover_turno(con, a.id, a_las(10, dia=DOMINGO), ahora=AHORA)


def test_mover_estados_no_permitidos(con, esc):
    t = esc.turno()
    agenda.registrar_abono(con, t.id, 20000, ahora=AHORA)
    agenda.iniciar_atencion(con, t.id, ahora=a_las(9))
    with pytest.raises(OperacionNoPermitida):
        agenda.mover_turno(con, t.id, a_las(11), ahora=a_las(9))
    vencido = esc.turno(inicio=a_las(12))
    with pytest.raises(OperacionNoPermitida, match="venció"):
        agenda.mover_turno(con, vencido.id, a_las(13), ahora=AHORA + MIN30)
    assert agenda.obtener_turno(con, vencido.id).estado is E.LIBERADO


def test_cancelar_libera_cupo(con, esc):
    t = esc.turno(C.TIJERA)
    agenda.cancelar_turno(con, t.id, ahora=AHORA)
    assert agenda.obtener_turno(con, t.id).estado is E.CANCELADO
    assert esc.turno(C.TIJERA).estado is E.PENDIENTE_ABONO


def test_cancelar_pendiente_devuelve_saldo(con, esc):
    p = esc.propietario(saldo=5000)
    t = esc.turno(propietario=p)
    agenda.cancelar_turno(con, t.id, ahora=AHORA)
    assert _saldo(con, p.id) == 5000


def test_cancelar_estado_final(con, esc):
    t = esc.turno()
    agenda.cancelar_turno(con, t.id, ahora=AHORA)
    with pytest.raises(TransicionInvalida):
        agenda.cancelar_turno(con, t.id, ahora=AHORA)


# --------------------------------------------------------------------------- inasistencias


def test_inasistencia_con_aviso_genera_saldo_que_se_aplica_al_siguiente(con, esc):
    p = esc.propietario()
    t = esc.turno(propietario=p, inicio=a_las(10))
    agenda.registrar_abono(con, t.id, 20000, ahora=AHORA)
    aviso = a_las(10) - timedelta(hours=12)
    t = agenda.marcar_inasistencia(con, t.id, aviso_en=aviso, ahora=a_las(10, 30))
    assert (t.estado, t.saldo_generado, t.aviso_inasistencia_en) == (E.INASISTENCIA, 20000, aviso)
    assert _saldo(con, p.id) == 20000
    siguiente = esc.turno(propietario=p, inicio=a_las(11), ahora=a_las(10, 30))
    assert siguiente.estado is E.CONFIRMADO and siguiente.saldo_aplicado == 20000
    assert _saldo(con, p.id) == 0
    assert [x.id for x in agenda.inasistencias_de_propietario(con, p.id)] == [t.id]


@pytest.mark.parametrize("horas", [None, 11])
def test_inasistencia_sin_aviso_a_tiempo_pierde_abono(con, esc, horas):
    p = esc.propietario()
    t = esc.turno(propietario=p, inicio=a_las(10))
    agenda.registrar_abono(con, t.id, 20000, ahora=AHORA)
    aviso = None if horas is None else a_las(10) - timedelta(hours=horas)
    t = agenda.marcar_inasistencia(con, t.id, aviso_en=aviso, ahora=a_las(10, 30))
    assert t.saldo_generado == 0 and _saldo(con, p.id) == 0


def test_inasistencia_cuenta_saldo_aplicado_como_abono(con, esc):
    p = esc.propietario(saldo=20000)
    t = esc.turno(propietario=p, inicio=a_las(15))
    assert t.estado is E.CONFIRMADO
    aviso = a_las(15) - timedelta(hours=13)
    agenda.marcar_inasistencia(con, t.id, aviso_en=aviso, ahora=a_las(15, 30))
    assert _saldo(con, p.id) == 20000


def test_inasistencia_validaciones(con, esc):
    t = esc.turno()
    with pytest.raises(TransicionInvalida):
        agenda.marcar_inasistencia(con, t.id, ahora=a_las(10))
    agenda.registrar_abono(con, t.id, 20000, ahora=AHORA)
    with pytest.raises(DatoInvalido):
        agenda.marcar_inasistencia(con, t.id, aviso_en=a_las(11), ahora=a_las(10))


# --------------------------------------------------------------------------- atención


def test_flujo_de_atencion_audita_cada_paso(con, esc):
    t = esc.turno()
    agenda.registrar_abono(con, t.id, 20000, ahora=AHORA)
    with pytest.raises(TransicionInvalida):
        agenda.marcar_entregado(con, t.id, ahora=a_las(9))
    agenda.iniciar_atencion(con, t.id, ahora=a_las(9))
    agenda.marcar_atendido(con, t.id, ahora=a_las(10))
    t = agenda.marcar_entregado(con, t.id, ahora=a_las(11))
    assert t.estado is E.ENTREGADO
    assert [r.accion for r in historial(con, "turno", t.id)] == [
        "crear", "abonar", "cambiar_estado", "cambiar_estado", "cambiar_estado",
    ]


# --------------------------------------------------------------------------- bloqueos


def test_bloqueo_con_turnos_activos_rechazado(con, esc):
    esc.turno(inicio=a_las(14))
    with pytest.raises(BloqueoConTurnos, match="14:00"):
        agenda.crear_bloqueo(con, Bloqueo(LUNES, motivo="Festivo"), ahora=AHORA)
    with pytest.raises(BloqueoConTurnos):
        agenda.crear_bloqueo(con, Bloqueo(LUNES, time(13, 45), time(14, 15)), ahora=AHORA)
    assert agenda.bloqueos_del_dia(con, LUNES) == []
    # Un rango que no toca el turno sí se puede
    b = agenda.crear_bloqueo(con, Bloqueo(LUNES, time(9), time(12)), ahora=AHORA)
    assert b.id is not None and agenda.bloqueos_del_dia(con, LUNES) == [b]


def test_bloqueo_ignora_turnos_inactivos(con, esc):
    cancelado = esc.turno(inicio=a_las(14))
    agenda.cancelar_turno(con, cancelado.id, ahora=AHORA)
    esc.turno(inicio=a_las(15))  # pendiente que vencerá
    b = agenda.crear_bloqueo(con, Bloqueo(LUNES), ahora=AHORA + MIN30)
    assert agenda.bloqueos_del_dia(con, LUNES) == [b]


def test_quitar_bloqueo(con, esc):
    b = agenda.crear_bloqueo(con, Bloqueo(LUNES, motivo="Capacitación"), ahora=AHORA)
    with pytest.raises(FranjaNoDisponible):
        esc.turno()
    agenda.quitar_bloqueo(con, b.id, ahora=AHORA)
    assert esc.turno().estado is E.PENDIENTE_ABONO
    with pytest.raises(OperacionNoPermitida):
        agenda.quitar_bloqueo(con, b.id, ahora=AHORA)
    with pytest.raises(NoEncontrado):
        agenda.quitar_bloqueo(con, 999, ahora=AHORA)
    assert [r.accion for r in historial(con, "bloqueo", b.id)] == ["crear", "quitar"]


# --------------------------------------------------------------------------- consultas y auditoría


def test_disponibilidad(con, esc):
    esc.turno(C.MAQUINA, inicio=a_las(9))
    agenda.crear_bloqueo(con, Bloqueo(LUNES, time(12), time(13)), ahora=AHORA)
    dispo = agenda.disponibilidad(con, LUNES, ahora=AHORA)
    assert len(dispo) == 14
    franja, libres = dispo[0]
    assert franja.inicio == a_las(9)
    assert libres == {C.MAQUINA: 1, C.GRANDE: 1, C.TIJERA: 1, C.COMPLICADO: 1}
    assert agenda.disponibilidad(con, DOMINGO, ahora=AHORA) == []


def test_escritura_fallida_no_deja_auditoria(con, esc):
    esc.turno(C.GRANDE)
    antes = len(historial(con))
    with pytest.raises(SinCupo):
        esc.turno(C.GRANDE, propietario=repo_clientes.obtener_propietario(con, 1))
    # El escenario crea una mascota (auditada) antes de intentar el turno
    nuevas = historial(con)[antes:]
    assert [r.entidad for r in nuevas] == ["mascota"]
