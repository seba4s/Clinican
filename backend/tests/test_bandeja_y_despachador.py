import threading
import time as reloj_real
from datetime import timedelta

import pytest

from clinican.datos import repo_notificaciones
from clinican.datos.conexion import abrir
from clinican.dominio.cupos import CategoriaCupo as C
from clinican.dominio.entidades import EstadoNotificacion as EN
from clinican.dominio.notificaciones import espera_tras_fallo
from clinican.servicios import agenda, configuracion
from clinican.servicios.auditoria import historial
from clinican.servicios.despachador import Despachador
from clinican.servicios.notificaciones import ErrorEnvio, notificaciones_de_turno
from escenario import AHORA, LUNES, a_las

MIERCOLES = LUNES + timedelta(days=2)


class Grabador:
    """Notificador falso que guarda lo enviado; puede fallar las primeras N veces."""

    def __init__(self, fallas=0, excepcion=ErrorEnvio("canal caído")):
        self.enviados = []
        self.fallas = fallas
        self.excepcion = excepcion
        self.llamadas = 0
        self._candado = threading.Lock()

    def enviar(self, mensaje):
        with self._candado:
            self.llamadas += 1
            if self.llamadas <= self.fallas:
                raise self.excepcion
            self.enviados.append(mensaje)


def _confirmado(con, esc, inicio, ahora=AHORA, categoria=C.MAQUINA):
    t = esc.turno(categoria, inicio=inicio, ahora=ahora)
    return agenda.registrar_abono(con, t.id, 20000, ahora=ahora)


# --------------------------------------------------------------------------- dominio


def test_reglas_de_dominio():
    assert [espera_tras_fallo(n) for n in (1, 2, 3, 4)] == [
        timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=15), None
    ]


# --------------------------------------------------------------------------- bandeja


def test_confirmar_programa_recordatorio_en_la_misma_transaccion(con, esc):
    t = esc.turno(inicio=a_las(10, dia=MIERCOLES))
    assert notificaciones_de_turno(con, t.id) == []  # pendiente de abono: aún no
    agenda.registrar_abono(con, t.id, 5000, ahora=AHORA)
    assert notificaciones_de_turno(con, t.id) == []  # abono parcial: aún no
    agenda.registrar_abono(con, t.id, 15000, ahora=AHORA)
    primero, final = notificaciones_de_turno(con, t.id)
    assert (primero.estado, primero.tipo, primero.intentos) == (EN.PENDIENTE, "recordatorio", 0)
    assert primero.programada_para == a_las(10, dia=MIERCOLES) - timedelta(hours=24)
    assert (final.estado, final.tipo) == (EN.PENDIENTE, "recordatorio_final")
    assert final.programada_para == a_las(9, dia=MIERCOLES)


def test_turno_cercano_solo_programa_el_de_1_hora(con, esc):
    t = _confirmado(con, esc, a_las(10))
    [n] = notificaciones_de_turno(con, t.id)
    assert (n.tipo, n.programada_para) == ("recordatorio_final", a_las(9))


def test_turno_a_menos_de_1_hora_no_programa(con, esc):
    t = _confirmado(con, esc, a_las(9), ahora=a_las(8, 30))
    assert notificaciones_de_turno(con, t.id) == []


def test_nace_confirmado_por_saldo_y_programa(con, esc):
    p = esc.propietario(saldo=20000)
    t = esc.turno(inicio=a_las(10, dia=MIERCOLES), propietario=p)
    assert len(notificaciones_de_turno(con, t.id)) == 2


def test_horas_antes_configurables(con, esc):
    configuracion.guardar(con, "horas_antes_recordatorio", 3, ahora=AHORA)
    configuracion.guardar(con, "horas_antes_recordatorio_final", 2, ahora=AHORA)
    cfg = configuracion.cargar(con)
    assert (cfg.horas_antes_recordatorio, cfg.horas_antes_recordatorio_final) == (3, 2)
    t = _confirmado(con, esc, a_las(15))
    assert [n.programada_para for n in notificaciones_de_turno(con, t.id)] == [a_las(12), a_las(13)]


def test_mover_descarta_y_reprograma(con, esc):
    t = _confirmado(con, esc, a_las(10, dia=MIERCOLES))
    agenda.mover_turno(con, t.id, a_las(15, dia=MIERCOLES), ahora=AHORA)
    *viejos, primero, final = notificaciones_de_turno(con, t.id)
    assert [(v.estado, v.motivo_descarte) for v in viejos] == [(EN.DESCARTADA, "El turno se movió")] * 2
    assert primero.estado is EN.PENDIENTE and final.estado is EN.PENDIENTE
    assert primero.programada_para == a_las(15, dia=MIERCOLES) - timedelta(hours=24)
    assert final.programada_para == a_las(14, dia=MIERCOLES)


def test_si_falla_la_escritura_no_queda_recordatorio(con, esc, monkeypatch):
    t = esc.turno(inicio=a_las(10, dia=MIERCOLES))

    def explota(*a, **k):
        raise RuntimeError("falla al auditar")

    monkeypatch.setattr("clinican.servicios.notificaciones.auditar", explota)
    with pytest.raises(RuntimeError):
        agenda.registrar_abono(con, t.id, 20000, ahora=AHORA)
    assert agenda.obtener_turno(con, t.id).abono_pagado == 0
    assert notificaciones_de_turno(con, t.id) == []


# --------------------------------------------------------------------------- despachador


def test_envia_solo_las_que_llegaron_a_su_hora(con, esc, ruta_db):
    hoy = _confirmado(con, esc, a_las(10))
    luego = _confirmado(con, esc, a_las(10, dia=MIERCOLES))
    grabador = Grabador()
    d = Despachador(ruta_db, grabador)
    assert d.procesar_una_vez(AHORA).enviadas == 0  # el de las 10 sale a las 9
    resumen = d.procesar_una_vez(a_las(9))
    assert (resumen.enviadas, resumen.descartadas) == (1, 0)
    [m] = grabador.enviados
    assert m.turno_id == hoy.id and m.telefono == "3001234567"
    assert m.texto.startswith("Estimado cliente, le recordamos que hoy, lunes 9 de noviembre (09/11/2026), ")
    assert m.parametros == ("hoy, lunes 9 de noviembre (09/11/2026)", m.mascota, "10:00 am")
    [n] = notificaciones_de_turno(con, hoy.id)
    assert (n.estado, n.intentos, n.enviada_en) == (EN.ENVIADA, 1, a_las(9))
    assert {n.estado for n in notificaciones_de_turno(con, luego.id)} == {EN.PENDIENTE}
    assert historial(con, "notificacion", n.id)[-1].accion == "enviar"


@pytest.mark.parametrize("accion", ["cancelar", "inasistencia"])
def test_descarta_si_el_turno_ya_no_esta_confirmado(con, esc, ruta_db, accion):
    t = _confirmado(con, esc, a_las(10))
    if accion == "cancelar":
        agenda.cancelar_turno(con, t.id, ahora=AHORA)
    else:
        agenda.marcar_inasistencia(con, t.id, ahora=AHORA)
    grabador = Grabador()
    resumen = Despachador(ruta_db, grabador).procesar_una_vez(a_las(9))
    assert resumen.descartadas == 1 and grabador.llamadas == 0
    n = notificaciones_de_turno(con, t.id)[0]
    assert n.estado is EN.DESCARTADA and "no está confirmado" in n.motivo_descarte


def test_descarta_si_el_turno_ya_empezo(con, esc, ruta_db):
    t = _confirmado(con, esc, a_las(10))
    grabador = Grabador()
    Despachador(ruta_db, grabador).procesar_una_vez(a_las(10))
    n = notificaciones_de_turno(con, t.id)[0]
    assert (n.estado, n.motivo_descarte) == (EN.DESCARTADA, "El turno ya empezó")
    assert grabador.llamadas == 0


def test_reintentos_1_5_15_y_luego_fallida(con, esc, ruta_db):
    t = _confirmado(con, esc, a_las(16))
    grabador = Grabador(fallas=99)
    d = Despachador(ruta_db, grabador)
    momento = a_las(15)
    for intento, espera in [(1, 1), (2, 5), (3, 15)]:
        assert d.procesar_una_vez(momento).reintentos == 1
        n = notificaciones_de_turno(con, t.id)[0]
        assert (n.estado, n.intentos, n.ultimo_error) == (EN.PENDIENTE, intento, "canal caído")
        assert n.programada_para == momento + timedelta(minutes=espera)
        # Un segundo antes del reintento no se hace nada
        assert d.procesar_una_vez(n.programada_para - timedelta(seconds=1)).reintentos == 0
        momento = n.programada_para
    assert d.procesar_una_vez(momento).fallidas == 1
    n = notificaciones_de_turno(con, t.id)[0]
    assert (n.estado, n.intentos, n.cerrada_en) == (EN.FALLIDA, 4, momento)
    assert grabador.llamadas == 4
    assert d.procesar_una_vez(momento + timedelta(hours=1)).fallidas == 0


def test_falla_y_luego_envia(con, esc, ruta_db):
    t = _confirmado(con, esc, a_las(16))
    grabador = Grabador(fallas=1, excepcion=ValueError("bug del canal"))
    d = Despachador(ruta_db, grabador)
    d.procesar_una_vez(a_las(15))
    n = notificaciones_de_turno(con, t.id)[0]
    assert "Error inesperado" in n.ultimo_error and n.estado is EN.PENDIENTE
    d.procesar_una_vez(a_las(15, 1))
    n = notificaciones_de_turno(con, t.id)[0]
    assert (n.estado, n.intentos) == (EN.ENVIADA, 2)


def test_purga_cerradas_de_mas_de_90_dias(con, esc, ruta_db):
    viejo = _confirmado(con, esc, a_las(10))
    pendiente = _confirmado(con, esc, a_las(15, dia=MIERCOLES))
    d = Despachador(ruta_db, Grabador())
    d.procesar_una_vez(a_las(9))  # envía la de hoy
    assert d.procesar_una_vez(a_las(9) + timedelta(days=89)).purgadas == 0
    # (las dos pendientes del miércoles se descartan en ese ciclo porque el turno ya pasó)
    resumen = d.procesar_una_vez(a_las(9) + timedelta(days=91))
    assert resumen.purgadas == 1
    assert notificaciones_de_turno(con, viejo.id) == []
    assert len(notificaciones_de_turno(con, pendiente.id)) == 2
    assert d.procesar_una_vez(a_las(9) + timedelta(days=200)).purgadas == 2


def test_dos_despachadores_no_envian_dos_veces(con, esc, ruta_db):
    inicios = [a_las(h, m, dia=MIERCOLES) for h in range(10, 16) for m in (0, 30)]
    for inicio in inicios:
        _confirmado(con, esc, inicio)
    grabador = Grabador()
    barrera = threading.Barrier(2)

    def correr():
        barrera.wait()
        # el martes a las 16:00 ya tocan los 12 recordatorios de 24 h
        Despachador(ruta_db, grabador).procesar_una_vez(a_las(16, dia=LUNES + timedelta(days=1)))

    hilos = [threading.Thread(target=correr) for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(60)
    ids = [m.notificacion_id for m in grabador.enviados]
    assert len(ids) == len(inicios) == len(set(ids))


def test_hilo_con_evento_de_parada(con, esc, ruta_db):
    t = _confirmado(con, esc, a_las(10))
    grabador = Grabador()
    d = Despachador(ruta_db, grabador, reloj=lambda: a_las(9), intervalo_segundos=0.05)
    d.iniciar()
    try:
        limite = reloj_real.monotonic() + 10
        while not grabador.enviados and reloj_real.monotonic() < limite:
            reloj_real.sleep(0.02)
    finally:
        d.detener()
    assert not d.corriendo
    assert [m.turno_id for m in grabador.enviados] == [t.id]


def test_hilo_exige_reloj(ruta_db):
    with pytest.raises(ValueError):
        Despachador(ruta_db, Grabador()).iniciar()


def test_ciclo_con_ahora_sin_zona(ruta_db):
    from datetime import datetime

    with pytest.raises(ValueError):
        Despachador(ruta_db, Grabador()).procesar_una_vez(datetime(2026, 11, 9, 8))


def test_base_compartida_con_otra_conexion(ruta_db, con, esc):
    """El despachador usa su propia conexión: ve lo confirmado por la conexión de la agenda."""
    _confirmado(con, esc, a_las(10))
    otra = abrir(ruta_db)
    try:
        assert len(repo_notificaciones.pendientes_hasta(otra, a_las(9))) == 1
    finally:
        otra.close()


def test_reintentar_fallido_lo_vuelve_a_enviar(con, esc, ruta_db):
    from clinican.dominio.errores import OperacionNoPermitida
    from clinican.servicios.notificaciones import reintentar

    t = _confirmado(con, esc, a_las(16))
    d = Despachador(ruta_db, Grabador(fallas=99))
    momento = a_las(15)
    for _ in range(4):
        d.procesar_una_vez(momento)
        momento = notificaciones_de_turno(con, t.id)[0].programada_para
    n = notificaciones_de_turno(con, t.id)[0]
    assert n.estado is EN.FALLIDA
    luego = a_las(15, 30)
    n = reintentar(con, n.id, ahora=luego)
    assert (n.estado, n.intentos, n.ultimo_error, n.programada_para) == (EN.PENDIENTE, 0, None, luego)
    grabador = Grabador()
    assert Despachador(ruta_db, grabador).procesar_una_vez(luego).enviadas == 1
    with pytest.raises(OperacionNoPermitida):
        reintentar(con, n.id, ahora=luego)  # ya no está fallido


def test_no_reintenta_si_el_turno_ya_no_esta_confirmado(con, esc, ruta_db):
    from clinican.dominio.errores import OperacionNoPermitida
    from clinican.servicios.notificaciones import reintentar

    t = _confirmado(con, esc, a_las(16))
    d = Despachador(ruta_db, Grabador(fallas=99))
    momento = a_las(15)
    for _ in range(4):
        d.procesar_una_vez(momento)
        momento = notificaciones_de_turno(con, t.id)[0].programada_para
    agenda.cancelar_turno(con, t.id, ahora=momento)
    with pytest.raises(OperacionNoPermitida):
        reintentar(con, notificaciones_de_turno(con, t.id)[0].id, ahora=momento)


# --------------------------------------------------------------------------- 24 h y 1 h


def test_envia_los_dos_recordatorios_a_su_hora(con, esc, ruta_db):
    t = _confirmado(con, esc, a_las(10, dia=MIERCOLES))
    grabador = Grabador()
    d = Despachador(ruta_db, grabador)
    assert d.procesar_una_vez(a_las(10, dia=LUNES + timedelta(days=1))).enviadas == 1
    assert d.procesar_una_vez(a_las(9, dia=MIERCOLES)).enviadas == 1
    primero, final = grabador.enviados
    assert primero.parametros[0] == "el día de mañana, miércoles 11 de noviembre (11/11/2026)"
    assert final.parametros[0] == "hoy, miércoles 11 de noviembre (11/11/2026)"
    assert [m.tipo for m in grabador.enviados] == ["recordatorio", "recordatorio_final"]
    assert {n.estado for n in notificaciones_de_turno(con, t.id)} == {EN.ENVIADA}


def test_el_texto_se_calcula_al_enviar_si_salio_tarde(con, esc, ruta_db):
    """El PC estuvo apagado: el de 24 h sale al día siguiente y dice «hoy»."""
    _confirmado(con, esc, a_las(16, dia=MIERCOLES))
    grabador = Grabador()
    Despachador(ruta_db, grabador).procesar_una_vez(a_las(7, dia=MIERCOLES))
    [m] = grabador.enviados
    assert m.tipo == "recordatorio" and m.parametros[0].startswith("hoy, miércoles 11")


def test_si_ya_toca_el_de_1_hora_se_descarta_el_atrasado(con, esc, ruta_db):
    t = _confirmado(con, esc, a_las(10, dia=MIERCOLES))
    grabador = Grabador()
    resumen = Despachador(ruta_db, grabador).procesar_una_vez(a_las(9, 15, dia=MIERCOLES))
    assert (resumen.enviadas, resumen.descartadas) == (1, 1)
    [m] = grabador.enviados
    assert m.tipo == "recordatorio_final"
    primero, final = notificaciones_de_turno(con, t.id)
    assert (primero.estado, primero.motivo_descarte) == (
        EN.DESCARTADA, "Salió tarde y ya es hora del último recordatorio"
    )
    assert final.estado is EN.ENVIADA
