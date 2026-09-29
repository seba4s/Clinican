"""RN-15: textos legales con versiones y consentimientos."""

import json

import pytest

from clinican.dominio.errores import DatoInvalido, PermisoDenegado
from clinican.servicios import legal
from clinican.servicios import propietarios as sp


@pytest.fixture
def dueno(conn, empleada):
    return sp.crear(conn, empleada, "María Pérez", "1098765432", "3012345678", None, "Calle 10")


def test_sin_consentimientos_no_se_puede_agendar(conn, dueno):
    """Criterio de aceptación de la Fase 2."""
    with pytest.raises(DatoInvalido, match="términos y condiciones y autorización"):
        legal.verificar_para_turno(conn, dueno)


def test_falta_solo_uno(conn, empleada, dueno):
    legal.aceptar(conn, empleada, dueno, ["TERMINOS"])
    with pytest.raises(DatoInvalido, match="tratamiento de datos"):
        legal.verificar_para_turno(conn, dueno)
    legal.aceptar(conn, empleada, dueno, ["DATOS"])
    legal.verificar_para_turno(conn, dueno)  # ya no falla


def test_aceptacion_guarda_fecha_version_y_texto(conn, empleada, dueno):
    legal.aceptar(conn, empleada, dueno, ["TERMINOS", "DATOS"])
    estado = legal.estado(conn, dueno)
    assert estado["TERMINOS"]["version"] == 1 and estado["DATOS"]["version"] == 1
    assert estado["TERMINOS"]["aceptado_en"]
    assert estado["TERMINOS"]["registrado_por_nombre"] == "Laura"
    assert "$20.000 por mascota" in estado["TERMINOS"]["texto_mostrado"]
    assert "{" not in estado["DATOS"]["texto_mostrado"]


def test_nueva_version_pide_nueva_aceptacion(conn, admin, empleada, dueno):
    legal.aceptar(conn, empleada, dueno, ["TERMINOS", "DATOS"])
    legal.verificar_para_turno(conn, dueno)
    fila, _ = legal.texto_vigente(conn, "TERMINOS")
    v = legal.nueva_version(conn, admin, "TERMINOS", fila["contenido"] + "\n\n7. Cláusula nueva de prueba.")
    assert v == 2
    with pytest.raises(DatoInvalido, match="términos"):
        legal.verificar_para_turno(conn, dueno)
    assert legal.estado(conn, dueno)["TERMINOS"] is None
    legal.aceptar(conn, empleada, dueno, ["TERMINOS"])
    assert legal.estado(conn, dueno)["TERMINOS"]["version"] == 2
    legal.verificar_para_turno(conn, dueno)
    # El historial conserva la aceptación de la versión 1
    versiones = sorted(c["version"] for c in legal.historial(conn, empleada, dueno) if c["tipo"] == "TERMINOS")
    assert versiones == [1, 2]


def test_solo_admin_edita_textos(conn, empleada):
    fila, _ = legal.texto_vigente(conn, "DATOS")
    with pytest.raises(PermisoDenegado):
        legal.nueva_version(conn, empleada, "DATOS", fila["contenido"] + " cambio")
    with pytest.raises(PermisoDenegado):
        legal.versiones(conn, empleada, "DATOS")


def test_texto_igual_o_vacio(conn, admin):
    fila, _ = legal.texto_vigente(conn, "DATOS")
    with pytest.raises(DatoInvalido):
        legal.nueva_version(conn, admin, "DATOS", fila["contenido"])
    with pytest.raises(DatoInvalido):
        legal.nueva_version(conn, admin, "DATOS", "   ")


def test_responsabilidad_por_mascota(conn, empleada, dueno):
    raza = conn.execute("SELECT id FROM razas WHERE nombre='Husky'").fetchone()[0]
    mid = sp.crear_mascota(conn, empleada, dueno, "Nieve", raza)
    with pytest.raises(DatoInvalido):
        legal.registrar_responsabilidad(conn, empleada, mid, {})
    with pytest.raises(DatoInvalido):
        legal.registrar_responsabilidad(conn, empleada, mid, {"cond_inventada": True})
    legal.registrar_responsabilidad(conn, empleada, mid, {"cond_agresiva": True, "cond_nudos_extremos": True})
    c = [x for x in legal.historial(conn, empleada, dueno) if x["tipo"] == "RESPONSABILIDAD"][0]
    assert c["mascota_nombre"] == "Nieve" and c["aceptado_en"]
    assert json.loads(c["condiciones"]) == {
        "cond_agresiva": True, "cond_nudos_extremos": True, "cond_problemas_piel": False,
        "cond_plagas": False, "cond_edad_avanzada": False,
    }
    # La responsabilidad no reemplaza términos ni datos
    with pytest.raises(DatoInvalido):
        legal.verificar_para_turno(conn, dueno)


def test_aceptar_tipo_invalido(conn, empleada, dueno):
    with pytest.raises(DatoInvalido):
        legal.aceptar(conn, empleada, dueno, ["RESPONSABILIDAD"])
    with pytest.raises(DatoInvalido):
        legal.aceptar(conn, empleada, dueno, [])
