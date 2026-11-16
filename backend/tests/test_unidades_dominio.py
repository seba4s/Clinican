"""Casos límite de las reglas del dominio: cédulas, edades, franjas, bloqueos, precios y reintentos."""

from datetime import date, datetime, time, timedelta

import pytest

from clinican.dominio.agenda import ZONA, Bloqueo, Franja
from clinican.dominio.cupos import CategoriaCupo
from clinican.dominio.documentos import fecha_nacimiento_aproximada, normalizar_cedula
from clinican.dominio.errores import DatoInvalido
from clinican.dominio.notificaciones import espera_tras_fallo
from clinican.dominio.precios import PrecioHistorico, formatear_pesos, precio_vigente

LUNES = date(2026, 11, 9)


@pytest.mark.parametrize(
    "texto, esperada",
    [
        ("1.085.123.456", "1085123456"),
        (" 1085 123-456 ", "1085123456"),
        ("pe1234", "PE1234"),
        (1085123456, "1085123456"),
        ("1234", "1234"),
        ("1" * 20, "1" * 20),
    ],
)
def test_normaliza_cedulas_validas(texto, esperada):
    assert normalizar_cedula(texto) == esperada


@pytest.mark.parametrize("texto", [None, True, False, "", "  ", " .-. "])
def test_cedula_obligatoria(texto):
    with pytest.raises(DatoInvalido, match="obligatoria"):
        normalizar_cedula(texto)


@pytest.mark.parametrize("texto", [12.5, ["123"], b"12345"])
def test_cedula_que_no_es_texto(texto):
    with pytest.raises(DatoInvalido, match="texto"):
        normalizar_cedula(texto)


@pytest.mark.parametrize("texto", ["123", "1" * 21, "12_345", "1234#", "ñandú12"])
def test_cedula_con_formato_invalido(texto):
    with pytest.raises(DatoInvalido, match="inválida"):
        normalizar_cedula(texto)


@pytest.mark.parametrize(
    "anios, meses, hoy, esperada",
    [
        (0, 0, date(2026, 11, 16), date(2026, 11, 16)),
        (2, 0, date(2026, 11, 16), date(2024, 11, 16)),
        (0, 11, date(2026, 11, 16), date(2025, 12, 16)),
        (1, 3, date(2026, 2, 10), date(2024, 11, 10)),
        (0, 1, date(2026, 3, 31), date(2026, 2, 28)),
        (2, 1, date(2026, 3, 31), date(2024, 2, 29)),
        (0, 5, date(2026, 10, 31), date(2026, 5, 31)),
        (0, 4, date(2026, 10, 31), date(2026, 6, 30)),
    ],
)
def test_fecha_de_nacimiento_aproximada(anios, meses, hoy, esperada):
    assert fecha_nacimiento_aproximada(anios, meses, hoy) == esperada


@pytest.mark.parametrize(
    "anios, meses, mensaje",
    [
        (-1, 0, "años"),
        (0, -1, "meses"),
        (True, 0, "años"),
        (0, False, "meses"),
        (1.5, 0, "años"),
        ("2", 0, "años"),
        (0, 12, "entre 0 y 11"),
    ],
)
def test_edad_invalida(anios, meses, mensaje):
    with pytest.raises(DatoInvalido, match=mensaje):
        fecha_nacimiento_aproximada(anios, meses, LUNES)


def test_franja_sin_zona_horaria():
    with pytest.raises(ValueError, match="zona horaria"):
        Franja(datetime(2026, 11, 9, 9, 0))


@pytest.mark.parametrize("minuto, segundo, micro", [(15, 0, 0), (0, 1, 0), (30, 0, 1)])
def test_franja_solo_en_punto_o_y_media(minuto, segundo, micro):
    with pytest.raises(ValueError, match="en punto o y media"):
        Franja(datetime(2026, 11, 9, 9, minuto, segundo, micro, tzinfo=ZONA))


def test_franja_dura_media_hora():
    franja = Franja(datetime(2026, 11, 9, 16, 30, tzinfo=ZONA))
    assert franja.fin - franja.inicio == timedelta(minutes=30)


def test_bloqueo_por_horas_debe_tener_desde_antes_de_hasta():
    with pytest.raises(ValueError):
        Bloqueo(LUNES, desde=time(11), hasta=time(10))
    with pytest.raises(ValueError):
        Bloqueo(LUNES, desde=time(10), hasta=time(10))


def test_bloqueo_no_cubre_otro_dia():
    bloqueo = Bloqueo(LUNES)
    assert bloqueo.dia_completo
    assert bloqueo.cubre(Franja(datetime(2026, 11, 9, 9, tzinfo=ZONA)))
    assert not bloqueo.cubre(Franja(datetime(2026, 11, 10, 9, tzinfo=ZONA)))


def test_bloqueo_por_horas_cubre_solo_su_rango():
    bloqueo = Bloqueo(LUNES, desde=time(10), hasta=time(11))
    assert not bloqueo.dia_completo
    cubiertas = [
        h for h in (9, 9.5, 10, 10.5, 11, 11.5)
        if bloqueo.cubre(Franja(datetime(2026, 11, 9, int(h), 30 if h % 1 else 0, tzinfo=ZONA)))
    ]
    assert cubiertas == [10, 10.5]


def test_bloqueo_compara_la_hora_local_de_bogota():
    utc = datetime(2026, 11, 9, 15, 0, tzinfo=ZONA).astimezone(tz=None)
    bloqueo = Bloqueo(LUNES, desde=time(15), hasta=time(16))
    assert bloqueo.cubre(Franja(utc))


def test_precio_historico_rechaza_fecha_que_no_es_fecha():
    with pytest.raises(TypeError, match="fecha"):
        PrecioHistorico("2026-01-01", CategoriaCupo.MAQUINA, 45000)


@pytest.mark.parametrize("valor", [-1, 1.5, True, "45000"])
def test_precio_historico_rechaza_valor_invalido(valor):
    with pytest.raises((TypeError, ValueError)):
        PrecioHistorico(date(2026, 1, 1), CategoriaCupo.MAQUINA, valor)


def test_precio_vigente_toma_el_ultimo_antes_de_la_fecha():
    historial = [
        PrecioHistorico(date(2000, 1, 1), CategoriaCupo.MAQUINA, 45000),
        PrecioHistorico(date(2026, 12, 1), CategoriaCupo.MAQUINA, 48000),
        PrecioHistorico(date(2000, 1, 1), CategoriaCupo.GRANDE, 70000),
    ]
    assert precio_vigente(historial, date(2026, 11, 30), CategoriaCupo.MAQUINA) == 45000
    assert precio_vigente(historial, date(2026, 12, 1), CategoriaCupo.MAQUINA) == 48000
    assert precio_vigente(historial, date(2026, 12, 1), CategoriaCupo.GRANDE) == 70000


@pytest.mark.parametrize(
    "valor, texto", [(0, "$0"), (500, "$500"), (45000, "$45.000"), (1250000, "$1.250.000")]
)
def test_formatear_pesos(valor, texto):
    assert formatear_pesos(valor) == texto


@pytest.mark.parametrize("intentos", [0, -3])
def test_espera_tras_fallo_exige_al_menos_un_intento(intentos):
    with pytest.raises(ValueError):
        espera_tras_fallo(intentos)


def test_esperas_de_reintento_son_1_5_y_15_minutos():
    assert [espera_tras_fallo(n) for n in (1, 2, 3, 4)] == [
        timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=15), None,
    ]
