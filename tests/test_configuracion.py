"""Configuración editable y formato."""

import pytest

from clinican.datos import semillas
from clinican.dominio import config_claves
from clinican.dominio.errores import DatoInvalido
from clinican.dominio.formato import pesos, rellenar_texto
from clinican.servicios import configuracion


def test_toda_clave_sembrada_tiene_descripcion():
    assert set(semillas.CONFIG_INICIAL) == set(config_claves.POR_CLAVE)


def test_admin_cambia_precio_y_queda_auditado(conn, admin):
    cambiadas = configuracion.guardar(conn, admin, {"precio_min_PEQUENA": "$48.000", "cupo_MAQUINA": "2"})
    assert cambiadas == ["precio_min_PEQUENA"]
    assert configuracion.valores(conn)["precio_min_PEQUENA"] == "48000"
    detalle = conn.execute(
        "SELECT detalle FROM auditoria WHERE accion='CAMBIAR_CONFIGURACION'"
    ).fetchone()[0]
    assert detalle == "precio_min_PEQUENA: 45000 → 48000"


@pytest.mark.parametrize(
    "clave,valor",
    [
        ("abono_minimo", "veinte mil"),
        ("abono_minimo", "20000.5"),
        ("cupo_TIJERA", "0"),
        ("inicio_grupo_manana", "9am"),
        ("franjas_solo_individuales", "08:30, 25:00"),
        ("cupos_independientes", "tal vez"),
        ("negocio_nombre", "   "),
        ("clave_inventada", "1"),
    ],
)
def test_valores_invalidos(conn, admin, clave, valor):
    with pytest.raises(DatoInvalido):
        configuracion.guardar(conn, admin, {clave: valor})


def test_cambio_invalido_no_guarda_nada(conn, admin):
    with pytest.raises(DatoInvalido):
        configuracion.guardar(conn, admin, {"abono_minimo": "25000", "cupo_GRANDE": "x"})
    assert configuracion.valores(conn)["abono_minimo"] == "20000"


def test_pesos():
    assert pesos(45000) == "$45.000"
    assert pesos("1200000") == "$1.200.000"
    assert pesos(None) == "—"


def test_texto_legal_usa_config(conn):
    terminos = conn.execute("SELECT contenido FROM textos_legales WHERE tipo='TERMINOS'").fetchone()[0]
    texto = rellenar_texto(terminos, configuracion.valores(conn))
    assert "$20.000 por mascota" in texto
    assert "301 441 7194" in texto
    assert "12 horas" in texto
    assert "30 minutos" in texto
    assert "{" not in texto
