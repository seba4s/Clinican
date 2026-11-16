"""Textos que muestra la interfaz: pesos, fechas, cédulas, celulares y tiempo restante."""

from datetime import date, datetime, timedelta, timezone

import pytest

from clinican.dominio.agenda import ZONA
from clinican.dominio.cupos import CategoriaCupo, Servicio, Tamano
from clinican.dominio.errores import DatoInvalido
from interfaz import formato as fmt

HOY = date(2026, 11, 16)


def test_hay_nombre_para_cada_categoria_servicio_y_tamano():
    assert set(fmt.CATEGORIA) == set(CategoriaCupo)
    assert set(fmt.SERVICIO) == set(Servicio)
    assert set(fmt.TAMANO) == set(Tamano)


@pytest.mark.parametrize("valor, texto", [(0, "$0"), (45000, "$45.000"), ("70000", "$70.000")])
def test_pesos(valor, texto):
    assert fmt.pesos(valor) == texto


@pytest.mark.parametrize(
    "texto, valor",
    [("$15.000", 15000), ("15000", 15000), ("15 000", 15000), (" $ 1.250.000 ", 1250000),
     ("", 0), (None, 0), ("  ", 0)],
)
def test_leer_pesos(texto, valor):
    assert fmt.leer_pesos(texto) == valor


@pytest.mark.parametrize("texto", ["15,000", "-500", "veinte mil", "15000.5x", "1e5"])
def test_leer_pesos_rechaza_lo_que_no_son_pesos(texto):
    with pytest.raises(DatoInvalido, match="pesos"):
        fmt.leer_pesos(texto)


def test_pesos_ida_y_vuelta():
    for valor in (0, 500, 20000, 45000, 1250000):
        assert fmt.leer_pesos(fmt.pesos(valor)) == valor


def test_hora_se_muestra_en_hora_de_bogota():
    utc = datetime(2026, 11, 16, 14, 30, tzinfo=timezone.utc)
    assert fmt.hora(utc) == "09:30"
    assert fmt.local(utc).utcoffset() == timedelta(hours=-5)


@pytest.mark.parametrize(
    "dia, texto",
    [(date(2026, 11, 16), "Lunes 16 de noviembre"), (date(2026, 11, 22), "Domingo 22 de noviembre"),
     (date(2027, 1, 6), "Miércoles 6 de enero"), (date(2026, 8, 15), "Sábado 15 de agosto")],
)
def test_dia_largo(dia, texto):
    assert fmt.dia_largo(dia) == texto


@pytest.mark.parametrize(
    "dia, texto",
    [
        (HOY, "Hoy"),
        (HOY + timedelta(days=1), "Mañana"),
        (HOY - timedelta(days=1), "Ayer"),
        (HOY + timedelta(days=2), "18 nov"),
        (date(2026, 10, 28), "28 oct"),
        (date(2025, 12, 31), "31 dic 2025"),
        (date(2027, 1, 1), "1 ene 2027"),
    ],
)
def test_dia_corto_relativo_a_hoy(dia, texto):
    assert fmt.dia_corto(dia, HOY) == texto


def test_dia_corto_sin_hoy_no_dice_hoy_ni_el_anio():
    assert fmt.dia_corto(HOY) == "16 nov"
    assert fmt.dia_corto(date(2020, 3, 1)) == "1 mar"


def test_momento():
    m = datetime(2026, 11, 16, 10, 30, tzinfo=ZONA)
    assert fmt.momento(m, HOY) == "Hoy 10:30"
    assert fmt.momento(m) == "16 nov 10:30"
    assert fmt.momento(m + timedelta(days=1), HOY) == "Mañana 10:30"


def test_momento_cerca_de_medianoche_usa_el_dia_de_bogota():
    utc = datetime(2026, 11, 17, 3, 0, tzinfo=timezone.utc)
    assert fmt.momento(utc, HOY) == "Hoy 22:00"


@pytest.mark.parametrize("texto", ["01/12/2026", " 1/12/2026 ", "29/02/2028"])
def test_leer_fecha(texto):
    fecha = fmt.leer_fecha(texto)
    assert fmt.leer_fecha(fmt.fecha_numerica(fecha)) == fecha


def test_fecha_numerica():
    assert fmt.fecha_numerica(date(2026, 1, 5)) == "05/01/2026"


@pytest.mark.parametrize("texto", ["", "2026-12-01", "31/02/2026", "29/02/2027", "12/31/2026", "hoy"])
def test_leer_fecha_invalida(texto):
    with pytest.raises(DatoInvalido, match="dd/mm/aaaa"):
        fmt.leer_fecha(texto)


@pytest.mark.parametrize(
    "texto, visto",
    [("3005551234", "300 555 1234"), ("300-555-1234", "300 555 1234"), ("300 555 1234", "300 555 1234"),
     ("12345", "12345"), ("", ""), (None, ""), ("573005551234", "573005551234")],
)
def test_celular(texto, visto):
    assert fmt.celular(texto) == visto


@pytest.mark.parametrize(
    "texto, visto",
    [("1085123456", "CC 1.085.123.456"), ("1.085.123.456", "CC 1.085.123.456"), ("1234", "CC 1.234"),
     (None, "sin cédula"), ("", "sin cédula"), ("PE", "PE")],
)
def test_cedula(texto, visto):
    assert fmt.cedula(texto) == visto


@pytest.mark.parametrize(
    "segundos, texto",
    [(-1, "vencido"), (0, "vencido"), (1, "vence en 1 min"), (60, "vence en 1 min"),
     (61, "vence en 2 min"), (1800, "vence en 30 min")],
)
def test_minutos_restantes(segundos, texto):
    ahora = datetime(2026, 11, 16, 9, 0, tzinfo=ZONA)
    assert fmt.minutos_restantes(ahora + timedelta(seconds=segundos), ahora) == texto


@pytest.mark.parametrize(
    "texto, hora",
    [("12 am", "00:00"), ("12:30 a. m.", "00:30"), ("9 am", "09:00"), ("11:30 pm", "23:30"),
     ("0", "00:00"), ("23:30", "23:30"), ("4:30PM", "16:30"), ("4:30 p.m.", "16:30")],
)
def test_leer_hora_con_am_y_pm(texto, hora):
    assert fmt.leer_hora(texto).strftime("%H:%M") == hora


@pytest.mark.parametrize("texto", [None, "25", "9:60", "pm", ":30", "9:3"])
def test_leer_hora_invalida(texto):
    with pytest.raises(DatoInvalido):
        fmt.leer_hora(texto)
