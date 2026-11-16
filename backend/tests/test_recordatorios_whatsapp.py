"""Recordatorios 24 h y 1 h antes, con fecha y hora en palabras y números."""

from datetime import date, datetime, time, timedelta

import pytest

from clinican.dominio.agenda import ZONA
from clinican.dominio.fechas_texto import dia_en_texto, hora_en_texto
from clinican.dominio.notificaciones import (
    TIPO_RECORDATORIO,
    TIPO_RECORDATORIO_FINAL,
    planificar_recordatorios,
    texto_recordatorio,
)

ANTICIPACIONES = ((TIPO_RECORDATORIO, 24), (TIPO_RECORDATORIO_FINAL, 1))


def _m(d, h, mi=0):
    return datetime(d.year, d.month, d.day, h, mi, tzinfo=ZONA)


@pytest.mark.parametrize(
    "hoy, dia, esperado",
    [
        (date(2026, 10, 7), date(2026, 10, 8), "el día de mañana, jueves 8 de octubre (08/10/2026)"),
        (date(2026, 10, 8), date(2026, 10, 8), "hoy, jueves 8 de octubre (08/10/2026)"),
        (date(2026, 10, 31), date(2026, 11, 1), "el día de mañana, domingo 1 de noviembre (01/11/2026)"),
        (date(2026, 12, 31), date(2027, 1, 1), "el día de mañana, viernes 1 de enero (01/01/2027)"),
        (date(2026, 11, 9), date(2026, 11, 12), "el jueves 12 de noviembre (12/11/2026)"),
    ],
)
def test_dia_en_texto(hoy, dia, esperado):
    assert dia_en_texto(dia, hoy) == esperado


def test_todos_los_dias_y_meses_en_espanol():
    lunes = date(2026, 11, 9)
    dias = [dia_en_texto(lunes + timedelta(days=i), date(2026, 1, 1)).split()[1] for i in range(7)]
    assert dias == ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = [dia_en_texto(date(2026, m, 1), date(2025, 1, 1)).split()[4] for m in range(1, 13)]
    assert meses == ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                     "septiembre", "octubre", "noviembre", "diciembre"]


@pytest.mark.parametrize(
    "hora, esperado",
    [
        (time(9, 0), "9:00 am"),
        (time(11, 30), "11:30 am"),
        (time(12, 0), "12:00 pm"),
        (time(16, 30), "4:30 pm"),
        (time(0, 15), "12:15 am"),
    ],
)
def test_hora_en_texto(hora, esperado):
    assert hora_en_texto(hora) == esperado


def test_texto_del_recordatorio_como_el_ejemplo():
    inicio = _m(date(2026, 10, 8), 9)
    assert texto_recordatorio("Roma", inicio, inicio - timedelta(hours=24)) == (
        "Estimado cliente, le recordamos que el día de mañana, jueves 8 de octubre (08/10/2026), "
        "tiene un turno de peluquería para Roma, a las 9:00 am. En caso de no poder asistir, "
        "avisar con anterioridad para evitar pérdida del saldo abonado. Muchas gracias."
    )
    assert texto_recordatorio("Roma", inicio, inicio - timedelta(hours=1)).startswith(
        "Estimado cliente, le recordamos que hoy, jueves 8 de octubre (08/10/2026), tiene"
    )


def test_texto_usa_la_hora_de_colombia():
    from datetime import timezone

    inicio = datetime(2026, 10, 8, 14, 0, tzinfo=timezone.utc)
    assert "a las 9:00 am" in texto_recordatorio("Roma", inicio, inicio - timedelta(hours=1))


def test_con_mas_de_24_horas_programa_los_dos():
    inicio = _m(date(2026, 11, 11), 10)
    ahora = _m(date(2026, 11, 9), 8)
    assert planificar_recordatorios(inicio, ANTICIPACIONES, ahora) == [
        (TIPO_RECORDATORIO, inicio - timedelta(hours=24)),
        (TIPO_RECORDATORIO_FINAL, inicio - timedelta(hours=1)),
    ]


def test_con_menos_de_24_horas_solo_el_de_1_hora():
    inicio = _m(date(2026, 11, 9), 15)
    assert planificar_recordatorios(inicio, ANTICIPACIONES, _m(date(2026, 11, 9), 8)) == [
        (TIPO_RECORDATORIO_FINAL, inicio - timedelta(hours=1)),
    ]


def test_con_menos_de_1_hora_ninguno():
    inicio = _m(date(2026, 11, 9), 9)
    assert planificar_recordatorios(inicio, ANTICIPACIONES, _m(date(2026, 11, 9), 8, 30)) == []


def test_justo_en_el_limite_si_se_programa():
    inicio = _m(date(2026, 11, 10), 9)
    ahora = inicio - timedelta(hours=24)
    assert planificar_recordatorios(inicio, ANTICIPACIONES, ahora)[0] == (TIPO_RECORDATORIO, ahora)


def test_cero_horas_apaga_ese_recordatorio_y_no_se_duplican():
    inicio = _m(date(2026, 11, 11), 10)
    ahora = _m(date(2026, 11, 9), 8)
    assert planificar_recordatorios(inicio, ((TIPO_RECORDATORIO, 24), (TIPO_RECORDATORIO_FINAL, 0)), ahora) == [
        (TIPO_RECORDATORIO, inicio - timedelta(hours=24))
    ]
    assert planificar_recordatorios(inicio, ((TIPO_RECORDATORIO, 3), (TIPO_RECORDATORIO_FINAL, 3)), ahora) == [
        (TIPO_RECORDATORIO, inicio - timedelta(hours=3))
    ]


def test_horas_invalidas():
    inicio = _m(date(2026, 11, 11), 10)
    for malo in (-1, 1.5, True):
        with pytest.raises(ValueError):
            planificar_recordatorios(inicio, ((TIPO_RECORDATORIO, malo),), inicio)
