import itertools

import pytest

from clinican.dominio.estados import (
    ESTADOS_FINALES,
    EstadoTurno as E,
    MotivoLiberacion as M,
    TransicionInvalida,
    ocupa_cupo,
    transicionar,
)

PERMITIDAS = {
    (E.PENDIENTE_ABONO, E.CONFIRMADO),
    (E.PENDIENTE_ABONO, E.LIBERADO),
    (E.PENDIENTE_ABONO, E.CANCELADO),
    (E.CONFIRMADO, E.EN_ATENCION),
    (E.CONFIRMADO, E.CANCELADO),
    (E.CONFIRMADO, E.INASISTENCIA),
    (E.EN_ATENCION, E.ATENDIDO),
    (E.ATENDIDO, E.ENTREGADO),
}


def test_flujo_completo():
    estado = E.PENDIENTE_ABONO
    for siguiente in (E.CONFIRMADO, E.EN_ATENCION, E.ATENDIDO, E.ENTREGADO):
        estado = transicionar(estado, siguiente)
    assert estado is E.ENTREGADO


@pytest.mark.parametrize("actual, nuevo", sorted(PERMITIDAS, key=lambda p: (p[0].value, p[1].value)))
def test_transiciones_permitidas(actual, nuevo):
    motivo = M.ABONO_VENCIDO if nuevo is E.LIBERADO else None
    assert transicionar(actual, nuevo, motivo) is nuevo


@pytest.mark.parametrize(
    "actual, nuevo",
    [p for p in itertools.product(E, E) if p not in PERMITIDAS],
)
def test_todas_las_demas_son_invalidas(actual, nuevo):
    with pytest.raises(TransicionInvalida):
        transicionar(actual, nuevo, M.OTRO if nuevo is E.LIBERADO else None)


def test_estados_finales_sin_salidas():
    assert ESTADOS_FINALES == {E.ENTREGADO, E.LIBERADO, E.CANCELADO, E.INASISTENCIA}
    for final in ESTADOS_FINALES:
        for destino in E:
            with pytest.raises(TransicionInvalida):
                transicionar(final, destino)


@pytest.mark.parametrize("motivo", list(M))
def test_liberar_con_cada_motivo(motivo):
    assert transicionar(E.PENDIENTE_ABONO, E.LIBERADO, motivo) is E.LIBERADO


def test_liberar_sin_motivo_es_invalido():
    with pytest.raises(TransicionInvalida):
        transicionar(E.PENDIENTE_ABONO, E.LIBERADO)
    with pytest.raises(TransicionInvalida):
        transicionar(E.PENDIENTE_ABONO, E.LIBERADO, "vencido")


def test_motivo_en_otra_transicion_es_invalido():
    with pytest.raises(TransicionInvalida):
        transicionar(E.PENDIENTE_ABONO, E.CANCELADO, M.OTRO)


@pytest.mark.parametrize(
    "estado, ocupa",
    [
        (E.PENDIENTE_ABONO, True),
        (E.CONFIRMADO, True),
        (E.EN_ATENCION, True),
        (E.ATENDIDO, True),
        (E.ENTREGADO, True),
        (E.LIBERADO, False),
        (E.CANCELADO, False),
        (E.INASISTENCIA, False),
    ],
)
def test_ocupa_cupo(estado, ocupa):
    assert ocupa_cupo(estado) is ocupa
