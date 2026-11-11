from datetime import time

import pytest

from clinican.datos import repo_configuracion
from clinican.datos.conexion import abrir
from clinican.dominio.agenda import HorarioSemanal, Jornada
from clinican.dominio.cupos import CuposPorFranja
from clinican.dominio.errores import DatoInvalido
from clinican.servicios import configuracion
from clinican.servicios.auditoria import historial
from conftest import AHORA


def test_valores_por_defecto(con):
    cfg = configuracion.cargar(con)
    assert cfg.cupos == CuposPorFranja(maquina=2, grande=1, tijera=1, complicado=1)
    assert cfg.abono == 20000
    assert cfg.minutos_expiracion == 30
    assert cfg.canal_notificaciones == "archivo"
    assert cfg.carpeta_respaldos == "respaldos"
    for dia in range(6):
        assert cfg.horario.dias[dia] == Jornada(time(9, 0), time(16, 30))
    assert cfg.horario.dias[6] is None
    assert repo_configuracion.todas(con) == {}


@pytest.mark.parametrize(
    "clave, valor",
    [
        ("cupos", CuposPorFranja(maquina=3, grande=2, tijera=1, complicado=0)),
        ("abono", 25000),
        ("abono", 0),
        ("minutos_expiracion", 45),
        ("horario", HorarioSemanal({0: Jornada(time(8, 0), time(12, 0)), 5: None})),
        ("canal_notificaciones", "archivo"),
        ("carpeta_respaldos", r"D:\respaldos"),
    ],
)
def test_guardar_y_leer(con, ruta_db, clave, valor):
    configuracion.guardar(con, clave, valor, ahora=AHORA)
    otra = abrir(ruta_db)
    try:
        leido = configuracion.leer(otra, clave)
    finally:
        otra.close()
    if clave == "horario":
        assert dict(leido.dias) == {
            **{d: None for d in range(7)}, 0: Jornada(time(8, 0), time(12, 0))
        }
    else:
        assert leido == valor


@pytest.mark.parametrize(
    "clave, valor",
    [
        ("abono", 20000.0),
        ("abono", "20000"),
        ("abono", -1),
        ("abono", True),
        ("minutos_expiracion", 0),
        ("minutos_expiracion", 30.5),
        ("cupos", {"maquina": 2}),
        ("horario", {0: ("09:00", "16:30")}),
        ("horario", HorarioSemanal({7: None})),
        ("canal_notificaciones", ""),
        ("carpeta_respaldos", None),
        ("inexistente", 1),
    ],
)
def test_validacion_de_tipo_al_guardar(con, clave, valor):
    with pytest.raises(DatoInvalido):
        configuracion.guardar(con, clave, valor, ahora=AHORA)
    assert repo_configuracion.todas(con) == {}
    assert historial(con, "configuracion") == []


def test_guardar_audita_en_la_misma_transaccion(con):
    configuracion.guardar(con, "abono", 25000, ahora=AHORA)
    configuracion.guardar(con, "abono", 30000, ahora=AHORA)
    registros = historial(con, "configuracion")
    assert [(r.accion, r.detalle["clave"], r.detalle["despues"]) for r in registros] == [
        ("guardar", "abono", "25000"),
        ("guardar", "abono", "30000"),
    ]
    assert registros[1].detalle["antes"] == "25000"
    assert registros[0].cuando == AHORA


def test_valor_danado_da_error_claro(con):
    repo_configuracion.guardar(con, "abono", "veinte mil")
    with pytest.raises(DatoInvalido, match="abono"):
        configuracion.leer(con, "abono")
