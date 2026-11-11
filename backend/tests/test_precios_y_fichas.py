from datetime import date, datetime

import pytest

from clinican.dominio.cupos import CategoriaCupo as C
from clinican.dominio.errores import DatoInvalido, NoEncontrado, OperacionNoPermitida
from clinican.dominio.estados import EstadoTurno as E
from clinican.dominio.precios import FECHA_PRECIOS_INICIALES, PRECIOS_INICIALES
from clinican.servicios import agenda, fichas, precios
from clinican.servicios.auditoria import historial
from conftest import AHORA, LUNES, a_las, timedelta


# --------------------------------------------------------------------------- precios


def test_precios_iniciales_sembrados(con):
    assert precios.precios_vigentes(con, LUNES) == dict(PRECIOS_INICIALES)
    assert precios.precios_vigentes(con, FECHA_PRECIOS_INICIALES) == dict(PRECIOS_INICIALES)
    assert len(precios.historial_precios(con)) == 4


def test_antes_de_la_siembra_no_hay_precio(con):
    with pytest.raises(NoEncontrado, match="MAQUINA"):
        precios.precio_en_fecha(con, C.MAQUINA, date(1999, 12, 31))


def test_cambiar_precio_agrega_historial(con):
    precios.cambiar_precio(con, C.MAQUINA, 48000, date(2026, 12, 1), ahora=AHORA)
    assert precios.precio_en_fecha(con, C.MAQUINA, date(2026, 11, 30)) == 45000
    assert precios.precio_en_fecha(con, C.MAQUINA, date(2026, 12, 1)) == 48000
    assert precios.precio_en_fecha(con, C.GRANDE, date(2026, 12, 1)) == 70000
    assert [p.valor for p in precios.historial_precios(con, C.MAQUINA)] == [45000, 48000]
    registro = historial(con, "precio")[-1]
    assert registro.detalle["valor_texto"] == "$48.000"


@pytest.mark.parametrize(
    "valor, fecha",
    [
        (48000.0, date(2026, 12, 1)),
        (-1, date(2026, 12, 1)),
        (48000, datetime(2026, 12, 1, 9)),
        (48000, "2026-12-01"),
        (48000, FECHA_PRECIOS_INICIALES),  # ya hay precio en esa fecha
    ],
)
def test_cambiar_precio_validaciones(con, valor, fecha):
    with pytest.raises(DatoInvalido):
        precios.cambiar_precio(con, C.MAQUINA, valor, fecha, ahora=AHORA)
    assert len(precios.historial_precios(con, C.MAQUINA)) == 1


# --------------------------------------------------------------------------- fichas


def _atendido(con, esc, categoria=C.MAQUINA, inicio=None, **ficha):
    t = esc.turno(categoria, inicio=inicio or a_las(9))
    agenda.registrar_abono(con, t.id, 20000, ahora=AHORA)
    agenda.iniciar_atencion(con, t.id, ahora=a_las(9))
    return agenda.marcar_atendido(con, t.id, ahora=a_las(10), **ficha)


def test_marcar_atendido_crea_ficha_con_precio_vigente(con, esc):
    t = _atendido(con, esc, C.GRANDE, servicios_realizados="Baño y corte",
                  detalles_corte="Rapado #4", observaciones="Nervioso")
    ficha = fichas.ficha_de_turno(con, t.id)
    assert ficha.precio_final == 70000
    assert (ficha.servicios_realizados, ficha.detalles_corte, ficha.observaciones) == (
        "Baño y corte", "Rapado #4", "Nervioso"
    )
    assert ficha.creada_en == a_las(10)
    assert historial(con, "ficha", ficha.id)[0].detalle["precio_final"] == 70000


def test_precio_final_se_toma_en_la_fecha_del_turno_y_queda_guardado(con, esc):
    precios.cambiar_precio(con, C.MAQUINA, 50000, LUNES + timedelta(days=1), ahora=AHORA)
    t = _atendido(con, esc, inicio=a_las(9))  # turno del lunes: precio anterior
    ficha = fichas.ficha_de_turno(con, t.id)
    assert ficha.precio_final == 45000
    precios.cambiar_precio(con, C.MAQUINA, 99000, LUNES - timedelta(days=1), ahora=AHORA)
    assert fichas.obtener_ficha(con, ficha.id).precio_final == 45000  # no se recalcula


def test_ficha_falla_si_no_hay_precio_y_el_turno_no_cambia(con, esc, monkeypatch):
    t = esc.turno()
    agenda.registrar_abono(con, t.id, 20000, ahora=AHORA)
    agenda.iniciar_atencion(con, t.id, ahora=a_las(9))

    def sin_precio(*a, **k):
        raise NoEncontrado("No hay precio")

    monkeypatch.setattr(fichas, "precio_en_fecha", sin_precio)
    with pytest.raises(NoEncontrado):
        agenda.marcar_atendido(con, t.id, ahora=a_las(10))
    assert agenda.obtener_turno(con, t.id).estado is E.EN_ATENCION
    assert fichas.ficha_de_turno(con, t.id) is None


def test_crear_ficha_manual_y_reglas(con, esc):
    t = esc.turno()
    with pytest.raises(OperacionNoPermitida, match="atendidos"):
        fichas.crear_ficha(con, t.id, ahora=AHORA)
    t = _atendido(con, esc, inicio=a_las(10))
    with pytest.raises(OperacionNoPermitida, match="ya tiene ficha"):
        fichas.crear_ficha(con, t.id, ahora=AHORA)
    with pytest.raises(NoEncontrado):
        fichas.crear_ficha(con, 999, ahora=AHORA)


def test_editar_ficha_no_toca_precio(con, esc):
    t = _atendido(con, esc)
    ficha = fichas.ficha_de_turno(con, t.id)
    editada = fichas.editar_ficha(con, ficha.id, observaciones="Volver en 6 semanas", ahora=a_las(11))
    assert editada.observaciones == "Volver en 6 semanas"
    assert editada.precio_final == ficha.precio_final
    assert historial(con, "ficha", ficha.id)[-1].accion == "editar"


def test_sesiones_de_desenredado(con, esc):
    t1 = _atendido(con, esc, inicio=a_las(9))
    f1 = fichas.ficha_de_turno(con, t1.id)
    s1 = fichas.registrar_sesion_desenredado(con, f1.id, avance="Lomo", porcentaje=30, ahora=a_las(11))
    s2 = fichas.registrar_sesion_desenredado(con, f1.id, avance="Patas", porcentaje=60, ahora=a_las(11))
    assert (s1.numero_sesion, s2.numero_sesion) == (1, 2)
    assert s1.fecha == LUNES and s1.mascota_id == t1.mascota_id
    assert [s.avance for s in fichas.sesiones_de_mascota(con, t1.mascota_id)] == ["Lomo", "Patas"]
    for malo in (101, -1, 50.5, True):
        with pytest.raises(DatoInvalido):
            fichas.registrar_sesion_desenredado(con, f1.id, porcentaje=malo, ahora=a_las(11))
    sin_porcentaje = fichas.registrar_sesion_desenredado(con, f1.id, avance="Revisión", ahora=a_las(11))
    assert sin_porcentaje.porcentaje is None and sin_porcentaje.numero_sesion == 3
