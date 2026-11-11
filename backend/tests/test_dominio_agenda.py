from datetime import date, datetime, time, timedelta

import pytest

from clinican.dominio.agenda import (
    ZONA,
    Bloqueo,
    Franja,
    HorarioSemanal,
    Jornada,
    generar_franjas,
)

LUNES = date(2026, 11, 9)
SABADO = date(2026, 11, 14)
DOMINGO = date(2026, 11, 15)


def _horas(franjas):
    return [f.inicio.strftime("%H:%M") for f in franjas]


def test_zona_es_bogota_menos_cinco():
    assert datetime(2026, 7, 1, 12, tzinfo=ZONA).utcoffset() == timedelta(hours=-5)
    assert datetime(2026, 1, 1, 12, tzinfo=ZONA).utcoffset() == timedelta(hours=-5)


def test_lunes_a_sabado_de_9_a_1630():
    for dia in range(6):
        franjas = generar_franjas(LUNES + timedelta(days=dia))
        assert len(franjas) == 16
        assert _horas(franjas)[0] == "09:00"
        assert _horas(franjas)[-1] == "16:30"
        assert "17:00" not in _horas(franjas)


def test_domingo_cerrado():
    assert generar_franjas(DOMINGO) == []


def test_franjas_con_zona_y_consecutivas():
    franjas = generar_franjas(LUNES)
    assert all(f.inicio.tzinfo is ZONA for f in franjas)
    for a, b in zip(franjas, franjas[1:]):
        assert a.fin == b.inicio
        assert b.inicio - a.inicio == timedelta(minutes=30)


def test_bloqueo_dia_completo():
    assert generar_franjas(SABADO, bloqueos=[Bloqueo(SABADO, motivo="Festivo")]) == []
    # No afecta otros días
    assert len(generar_franjas(LUNES, bloqueos=[Bloqueo(SABADO)])) == 16


def test_bloqueo_por_rango_de_horas():
    bloqueo = Bloqueo(LUNES, time(12, 0), time(13, 0))
    horas = _horas(generar_franjas(LUNES, bloqueos=[bloqueo]))
    assert "12:00" not in horas and "12:30" not in horas
    assert "11:30" in horas and "13:00" in horas
    assert len(horas) == 14


def test_bloqueo_que_corta_una_franja_la_bloquea_entera():
    horas = _horas(generar_franjas(LUNES, bloqueos=[Bloqueo(LUNES, time(10, 15), time(10, 45))]))
    assert "10:00" not in horas and "10:30" not in horas
    assert "09:30" in horas and "11:00" in horas


def test_horario_personalizado():
    horario = HorarioSemanal({0: Jornada(time(8, 0), time(9, 0))})
    assert _horas(generar_franjas(LUNES, horario)) == ["08:00", "08:30", "09:00"]
    una_sola = HorarioSemanal({0: Jornada(time(10, 0), time(10, 0))})
    assert _horas(generar_franjas(LUNES, una_sola)) == ["10:00"]
    assert generar_franjas(SABADO, horario) == []


def test_jornada_invalida():
    with pytest.raises(ValueError):
        Jornada(time(16, 0), time(9, 0))
    with pytest.raises(ValueError):
        Jornada(time(9, 0), time(16, 15))


@pytest.mark.parametrize(
    "desde, hasta",
    [(time(10), None), (None, time(10)), (time(11), time(10)), (time(10), time(10))],
)
def test_bloqueo_invalido(desde, hasta):
    with pytest.raises(ValueError):
        Bloqueo(LUNES, desde, hasta)


def test_franja_exige_zona_y_media_hora():
    with pytest.raises(ValueError):
        Franja(datetime(2026, 11, 9, 9, 0))
    with pytest.raises(ValueError):
        Franja(datetime(2026, 11, 9, 9, 15, tzinfo=ZONA))
    f = Franja(datetime(2026, 11, 9, 9, 30, tzinfo=ZONA))
    assert f.fin == datetime(2026, 11, 9, 10, 0, tzinfo=ZONA)
