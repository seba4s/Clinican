from datetime import datetime, timedelta

import pytest

from clinican.dominio.abonos import aplicar_saldo, esta_vencido, resultado_inasistencia
from clinican.dominio.agenda import ZONA

CREADO = datetime(2026, 11, 10, 10, 0, tzinfo=ZONA)
TURNO = datetime(2026, 11, 12, 10, 0, tzinfo=ZONA)


def test_vencimiento_por_defecto_30_minutos():
    assert not esta_vencido(CREADO, CREADO)
    assert not esta_vencido(CREADO, CREADO + timedelta(minutes=29, seconds=59))
    assert esta_vencido(CREADO, CREADO + timedelta(minutes=30))
    assert esta_vencido(CREADO, CREADO + timedelta(hours=2))


def test_vencimiento_configurable():
    assert not esta_vencido(CREADO, CREADO + timedelta(minutes=30), minutos=45)
    assert esta_vencido(CREADO, CREADO + timedelta(minutes=45), minutos=45)
    with pytest.raises(ValueError):
        esta_vencido(CREADO, CREADO, minutos=0)


def test_vencimiento_exige_zona_horaria():
    with pytest.raises(ValueError):
        esta_vencido(datetime(2026, 11, 10, 10, 0), CREADO)


@pytest.mark.parametrize(
    "anticipacion, saldo",
    [
        (timedelta(hours=12), 20000),
        (timedelta(hours=30), 20000),
        (timedelta(hours=11, minutes=59), 0),
        (timedelta(hours=1), 0),
        (timedelta(hours=-1), 0),  # avisó después de la hora del turno
    ],
)
def test_inasistencia_segun_aviso(anticipacion, saldo):
    assert resultado_inasistencia(TURNO, TURNO - anticipacion, 20000) == saldo


def test_inasistencia_sin_aviso_pierde_abono():
    assert resultado_inasistencia(TURNO, None, 20000) == 0


@pytest.mark.parametrize("abono", [20000.0, -1, True, "20000"])
def test_dinero_solo_enteros(abono):
    with pytest.raises((TypeError, ValueError)):
        resultado_inasistencia(TURNO, None, abono)


@pytest.mark.parametrize(
    "saldo, requerido, esperado",
    [
        (20000, 20000, (20000, 0, 0)),
        (30000, 20000, (20000, 10000, 0)),
        (5000, 20000, (5000, 0, 15000)),
        (0, 20000, (0, 0, 20000)),
        (10000, 0, (0, 10000, 0)),
    ],
)
def test_aplicar_saldo(saldo, requerido, esperado):
    resultado = aplicar_saldo(saldo, requerido)
    assert resultado == esperado
    assert all(type(x) is int for x in resultado)


@pytest.mark.parametrize("saldo, requerido", [(1.5, 10), (10, 2.0), (-1, 10), (10, -1)])
def test_aplicar_saldo_valida_pesos(saldo, requerido):
    with pytest.raises((TypeError, ValueError)):
        aplicar_saldo(saldo, requerido)
