from datetime import date

import pytest

from clinican.dominio.cupos import CategoriaCupo, Servicio
from clinican.dominio.precios import (
    PRECIOS_INICIALES,
    PrecioDuplicado,
    PrecioHistorico,
    SinPrecioVigente,
    formatear_pesos,
    precio_vigente,
)

HISTORIAL = [
    PrecioHistorico(date(2026, 1, 1), CategoriaCupo.MAQUINA, 40000),
    PrecioHistorico(date(2026, 6, 1), CategoriaCupo.MAQUINA, 45000),
    PrecioHistorico(date(2026, 3, 1), CategoriaCupo.TIJERA, 50000),
    PrecioHistorico(date(2026, 3, 1), Servicio.BANO, 30000),
]


def test_precios_iniciales_confirmados():
    assert dict(PRECIOS_INICIALES) == {
        CategoriaCupo.MAQUINA: 45000,
        CategoriaCupo.GRANDE: 70000,
        CategoriaCupo.TIJERA: 50000,
        CategoriaCupo.COMPLICADO: 50000,
    }
    assert set(PRECIOS_INICIALES) == set(CategoriaCupo)
    assert all(type(v) is int for v in PRECIOS_INICIALES.values())


def test_precios_iniciales_inmutables():
    with pytest.raises(TypeError):
        PRECIOS_INICIALES[CategoriaCupo.MAQUINA] = 1


@pytest.mark.parametrize(
    "valor, texto",
    [
        (45000, "$45.000"),
        (70000, "$70.000"),
        (0, "$0"),
        (999, "$999"),
        (1000, "$1.000"),
        (1250000, "$1.250.000"),
        (-5000, "-$5.000"),
    ],
)
def test_formatear_pesos(valor, texto):
    assert formatear_pesos(valor) == texto


@pytest.mark.parametrize("valor", [45000.0, True, "45000"])
def test_formatear_pesos_solo_enteros(valor):
    with pytest.raises(TypeError):
        formatear_pesos(valor)


@pytest.mark.parametrize(
    "fecha, valor",
    [
        (date(2026, 1, 1), 40000),
        (date(2026, 5, 31), 40000),
        (date(2026, 6, 1), 45000),
        (date(2027, 1, 1), 45000),
    ],
)
def test_precio_vigente_por_fecha(fecha, valor):
    assert precio_vigente(HISTORIAL, fecha, CategoriaCupo.MAQUINA) == valor


def test_precio_por_servicio():
    assert precio_vigente(HISTORIAL, date(2026, 4, 1), Servicio.BANO) == 30000


def test_sin_precio_vigente():
    with pytest.raises(SinPrecioVigente, match="TIJERA"):
        precio_vigente(HISTORIAL, date(2026, 2, 28), CategoriaCupo.TIJERA)
    with pytest.raises(SinPrecioVigente, match="GRANDE"):
        precio_vigente(HISTORIAL, date(2026, 12, 1), CategoriaCupo.GRANDE)
    with pytest.raises(SinPrecioVigente):
        precio_vigente([], date(2026, 12, 1), CategoriaCupo.GRANDE)


def test_precio_duplicado_en_misma_fecha():
    historial = HISTORIAL + [PrecioHistorico(date(2026, 6, 1), CategoriaCupo.MAQUINA, 47000)]
    with pytest.raises(PrecioDuplicado):
        precio_vigente(historial, date(2026, 7, 1), CategoriaCupo.MAQUINA)


@pytest.mark.parametrize("valor", [45000.0, -1, True])
def test_precio_solo_pesos_enteros(valor):
    with pytest.raises((TypeError, ValueError)):
        PrecioHistorico(date(2026, 1, 1), CategoriaCupo.MAQUINA, valor)
