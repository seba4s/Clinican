import dataclasses

import pytest

from clinican.dominio.cupos import (
    CategoriaCupo,
    CuposPorFranja,
    Servicio,
    Tamano,
    cabe_uno_mas,
    categoria_de_cupo,
    cupos_libres,
)

C = CategoriaCupo


@pytest.mark.parametrize(
    "tamano, servicio, complicado, esperada",
    [
        (Tamano.GRANDE, Servicio.CORTE_TIJERA, True, C.COMPLICADO),
        (Tamano.PEQUENO, Servicio.BANO, True, C.COMPLICADO),
        (Tamano.GRANDE, Servicio.CORTE_TIJERA, False, C.GRANDE),
        (Tamano.GRANDE, Servicio.CORTE_MAQUINA, False, C.GRANDE),
        (Tamano.MEDIANO, Servicio.CORTE_TIJERA, False, C.TIJERA),
        (Tamano.MINI, Servicio.CORTE_TIJERA, False, C.TIJERA),
        (Tamano.MEDIANO, Servicio.CORTE_MAQUINA, False, C.MAQUINA),
        (Tamano.PEQUENO, Servicio.BANO, False, C.MAQUINA),
        (Tamano.MINI, Servicio.DESENREDADO, False, C.MAQUINA),
    ],
)
def test_prioridad_de_categoria(tamano, servicio, complicado, esperada):
    assert categoria_de_cupo("Poodle", tamano, "rizado", servicio, complicado) is esperada


def test_raza_y_pelaje_no_cambian_la_categoria():
    a = categoria_de_cupo(None, Tamano.MEDIANO, None, Servicio.BANO, False)
    b = categoria_de_cupo("Chow chow", Tamano.MEDIANO, "doble capa", Servicio.BANO, False)
    assert a is b is C.MAQUINA


def test_tipos_invalidos():
    with pytest.raises(TypeError):
        categoria_de_cupo("x", "grande", "x", Servicio.BANO, False)
    with pytest.raises(TypeError):
        categoria_de_cupo("x", Tamano.GRANDE, "x", "bano", False)


def test_servicios_minimos_presentes():
    assert {"CORTE_MAQUINA", "CORTE_TIJERA", "BANO", "DESENREDADO"} <= set(Servicio.__members__)


def test_cupos_por_defecto():
    c = CuposPorFranja()
    assert [c.capacidad(x) for x in (C.MAQUINA, C.GRANDE, C.TIJERA, C.COMPLICADO)] == [2, 1, 1, 1]


def test_cupos_inmutables_y_configurables():
    c = CuposPorFranja(maquina=3, complicado=0)
    assert c.capacidad(C.MAQUINA) == 3 and c.capacidad(C.COMPLICADO) == 0
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.maquina = 5


@pytest.mark.parametrize("valor", [-1, 1.5, True, "2"])
def test_cupos_invalidos(valor):
    with pytest.raises(ValueError):
        CuposPorFranja(maquina=valor)


def test_libres_y_cabe():
    c = CuposPorFranja()
    vacia = {}
    assert cupos_libres(c, vacia, C.MAQUINA) == 2
    assert cabe_uno_mas(c, vacia, C.MAQUINA)
    una = {C.MAQUINA: 1}
    assert cupos_libres(c, una, C.MAQUINA) == 1 and cabe_uno_mas(c, una, C.MAQUINA)
    llena = {C.MAQUINA: 2, C.GRANDE: 1}
    assert cupos_libres(c, llena, C.MAQUINA) == 0 and not cabe_uno_mas(c, llena, C.MAQUINA)
    assert not cabe_uno_mas(c, llena, C.GRANDE)
    # Las categorías son independientes
    assert cabe_uno_mas(c, llena, C.TIJERA) and cabe_uno_mas(c, llena, C.COMPLICADO)


def test_sobreocupacion_no_da_negativos():
    assert cupos_libres(CuposPorFranja(), {C.TIJERA: 3}, C.TIJERA) == 0


def test_ocupacion_negativa_rechazada():
    with pytest.raises(ValueError):
        cupos_libres(CuposPorFranja(), {C.TIJERA: -1}, C.TIJERA)
