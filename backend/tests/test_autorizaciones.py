"""Autorización de tratamiento de datos (Ley 1581): registro, historial, auditoría y unión."""

from datetime import date, datetime, timedelta

import pytest

from clinican.dominio.autorizaciones import AutorizacionDatos, validar_fecha, vigente
from clinican.dominio.errores import DatoInvalido, NoEncontrado, OperacionNoPermitida
from clinican.servicios import autorizaciones, clientes
from clinican.servicios.auditoria import historial as auditoria
from clinican.servicios.despachador import Despachador
from conftest import AHORA, a_las

HOY = AHORA.date()


def _registro(id_, otorgada, minuto):
    return AutorizacionDatos(id_, 1, otorgada, HOY, "", AHORA + timedelta(minutes=minuto))


def test_vigente_es_el_ultimo_registro():
    assert vigente([]) is None
    assert vigente([_registro(1, True, 0)]).id == 1
    assert vigente([_registro(2, False, 5), _registro(1, True, 0)]) is None
    assert vigente([_registro(1, False, 0), _registro(2, True, 5)]).id == 2


@pytest.mark.parametrize("fecha", [HOY + timedelta(days=1), datetime(2026, 1, 1), "2026-01-01", None])
def test_fecha_invalida(fecha):
    with pytest.raises(DatoInvalido):
        validar_fecha(fecha, HOY)


def test_sin_autorizacion_por_defecto(con, esc):
    p = esc.propietario()
    assert autorizaciones.autorizacion_vigente(con, p.id) is None
    assert autorizaciones.historial(con, p.id) == []


def test_registrar_y_revocar_deja_historial_y_auditoria(con, esc):
    p = esc.propietario()
    a = autorizaciones.registrar_autorizacion(
        con, p.id, date(2026, 11, 2), ahora=AHORA, medio="  Formato   firmado "
    )
    assert a.otorgada and a.fecha == date(2026, 11, 2) and a.medio == "Formato firmado"
    assert autorizaciones.autorizacion_vigente(con, p.id) == a

    autorizaciones.revocar_autorizacion(con, p.id, HOY, ahora=AHORA + timedelta(minutes=1))
    assert autorizaciones.autorizacion_vigente(con, p.id) is None
    assert [r.otorgada for r in autorizaciones.historial(con, p.id)] == [True, False]

    acciones = [r.accion for r in auditoria(con, "propietario", p.id)]
    assert acciones[-2:] == ["autorizar_datos", "revocar_datos"]


def test_rechaza_fecha_futura_y_propietario_inexistente_o_inactivo(con, esc):
    p = esc.propietario()
    with pytest.raises(DatoInvalido):
        autorizaciones.registrar_autorizacion(con, p.id, HOY + timedelta(days=1), ahora=AHORA)
    with pytest.raises(NoEncontrado):
        autorizaciones.registrar_autorizacion(con, 9999, HOY, ahora=AHORA)
    clientes.desactivar_propietario(con, p.id, ahora=AHORA)
    with pytest.raises(OperacionNoPermitida):
        autorizaciones.registrar_autorizacion(con, p.id, HOY, ahora=AHORA)
    assert autorizaciones.historial(con, p.id) == []


def test_unir_duplicados_traslada_el_historial(con, esc):
    origen = esc.propietario("Ana (duplicada)")
    destino = esc.propietario("Ana")
    autorizaciones.registrar_autorizacion(con, origen.id, HOY, ahora=AHORA)
    clientes.unir_propietarios(con, origen.id, destino.id, ahora=AHORA)
    assert autorizaciones.autorizacion_vigente(con, destino.id) is not None
    assert autorizaciones.historial(con, origen.id) == []


def test_sin_autorizacion_el_recordatorio_se_envia_igual(ruta_db, con, esc):
    """Decisión del negocio: la autorización se registra, pero no bloquea recordatorios."""
    turno = esc.turno(inicio=a_las(10))
    assert autorizaciones.autorizacion_vigente(con, turno.propietario_id) is None

    enviados = []

    class Canal:
        def enviar(self, mensaje):
            enviados.append(mensaje)

    from clinican.servicios import agenda

    agenda.registrar_abono(con, turno.id, 20000, ahora=AHORA)
    Despachador(ruta_db, Canal()).procesar_una_vez(a_las(9))
    assert [m.turno_id for m in enviados] == [turno.id]
