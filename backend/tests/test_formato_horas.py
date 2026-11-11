"""Lectura de horas escritas a mano (selector de franjas en Ajustes y bloqueos)."""

from datetime import time

import pytest

from clinican.dominio.errores import DatoInvalido
from clinican.ui.formato import leer_hora


@pytest.mark.parametrize(
    "texto, esperada",
    [
        ("9", time(9, 0)),
        ("09:30", time(9, 30)),
        ("9:30", time(9, 30)),
        ("9.30", time(9, 30)),
        ("930", time(9, 30)),
        ("1630", time(16, 30)),
        ("16", time(16, 0)),
        (" 4:30 pm ", time(16, 30)),
        ("4 p. m.", time(16, 0)),
        ("12 pm", time(12, 0)),
        ("9h30", time(9, 30)),
    ],
)
def test_lee_horas_escritas_de_varias_formas(texto, esperada):
    assert leer_hora(texto) == esperada


@pytest.mark.parametrize("texto", ["", "nueve", "9:15", "24:00", "9:75", "123456"])
def test_rechaza_lo_que_no_es_una_franja(texto):
    with pytest.raises(DatoInvalido):
        leer_hora(texto)
