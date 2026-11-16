"""Campo de hora: normalizar lo escrito y subir o bajar media hora con las flechas."""

import pytest

pytest.importorskip("PySide6.QtCore", exc_type=ImportError)

from interfaz.puentes.util import HORAS, Util, normalizar_hora, paso_hora  # noqa: E402


def test_lista_de_franjas_de_6_a_2030():
    assert HORAS[0] == "06:00"
    assert HORAS[-1] == "20:30"
    assert len(HORAS) == 30
    assert "16:30" in HORAS


@pytest.mark.parametrize(
    "texto, hora",
    [("9", "09:00"), ("930", "09:30"), ("4:30 pm", "16:30"), ("16.30", "16:30"),
     ("9:15", None), ("", None), ("abc", None), ("25", None)],
)
def test_normalizar_hora(texto, hora):
    assert normalizar_hora(texto) == hora


@pytest.mark.parametrize(
    "texto, sentido, esperada",
    [("09:00", 1, "09:30"), ("09:30", -1, "09:00"), ("9", 1, "09:30"), ("4 pm", -1, "15:30"),
     ("06:00", -1, "06:00"), ("20:30", 1, "20:30"), ("09:00", 0, "09:00"), ("09:00", 4, "11:00")],
)
def test_paso_hora_dentro_de_la_lista(texto, sentido, esperada):
    assert paso_hora(texto, sentido) == esperada


@pytest.mark.parametrize("texto", ["", "hola", "05:00", "21:00", "9:15"])
def test_paso_hora_fuera_de_la_lista_vuelve_a_la_primera(texto):
    assert paso_hora(texto, 1) == "06:00"


def test_paso_hora_con_lista_propia():
    horas = ["09:00", "09:30", "10:00"]
    assert paso_hora("09:30", 1, horas) == "10:00"
    assert paso_hora("10:00", 1, horas) == "10:00"
    assert paso_hora("08:00", -1, horas) == "09:00"


def test_paso_hora_no_modifica_la_lista_recibida():
    horas = ["09:00", "09:30"]
    paso_hora("09:00", 1, horas)
    assert horas == ["09:00", "09:30"]


def test_slots_que_usa_qml():
    util = Util()
    assert util.normalizarHora("930") == "09:30"
    assert util.normalizarHora("nada") == ""
    assert util.pasoHora("09:00", 1, []) == "09:30"
    assert util.pasoHora("09:00", 1, ["09:00", "10:00"]) == "10:00"
    assert util.horas() == HORAS
    assert util.horas() is not HORAS
