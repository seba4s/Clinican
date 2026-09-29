"""Agendar a un cliente nuevo sin registrarlo; el registro se completa al momento del servicio."""

from datetime import date, datetime, timedelta

import pytest

from clinican.dominio.errores import DatoInvalido
from clinican.dominio.propietarios import SIN_REGISTRAR, cedula_visible
from clinican.servicios import legal
from clinican.servicios import propietarios as sp
from clinican.servicios import turnos as st
from clinican.servicios.turnos import Abono

_hoy = date.today()
LUNES = (_hoy + timedelta(days=7 + (7 - _hoy.weekday()) % 7)).isoformat()
AHORA = datetime.fromisoformat(f"{LUNES} 07:00:00")


def _raza(conn, nombre):
    return conn.execute("SELECT id FROM razas WHERE nombre = ?", (nombre,)).fetchone()[0]


@pytest.fixture
def nuevo(conn, empleada):
    """Cliente nuevo con su mascota, sin cédula ni consentimientos."""
    return sp.crear_provisional(conn, empleada, "Carolina", "311 222 3344", "Lola", _raza(conn, "Shih Tzu"))


def _agendar(conn, s, mid, hora="09:00", pagar=True):
    abono = Abono(20000, "NEQUI") if pagar else None
    return st.crear_turno(conn, s, mid, "MAQUINA", LUNES, hora, s.personal_id, abono, ahora=AHORA).turnos[0]


def test_crear_cliente_sin_registrar(conn, empleada, nuevo):
    pid, mid = nuevo
    p = sp.obtener(conn, empleada, pid)
    assert p["provisional"] == 1 and p["celular1"] == "3112223344" and p["direccion"] == ""
    assert cedula_visible(p) == SIN_REGISTRAR
    assert sp.mascota(conn, empleada, mid)["nombre"] == "Lola"
    # Se encuentra por nombre, celular o mascota para el siguiente turno
    assert [f["id"] for f in sp.buscar(conn, empleada, "311 222")] == [pid]
    assert [f["id"] for f in sp.buscar(conn, empleada, "lola")] == [pid]


def test_datos_minimos_obligatorios(conn, empleada):
    shih = _raza(conn, "Shih Tzu")
    with pytest.raises(DatoInvalido, match="nombre del cliente"):
        sp.crear_provisional(conn, empleada, "", "3112223344", "Lola", shih)
    with pytest.raises(DatoInvalido, match="celular"):
        sp.crear_provisional(conn, empleada, "Carolina", "", "Lola", shih)
    with pytest.raises(DatoInvalido, match="tamaño"):  # sin tamaño no se sabe el cupo
        sp.crear_provisional(conn, empleada, "Carolina", "3112223344", "Lola",
                             _raza(conn, "Perro mestizo (sin raza)"), pelaje_manual=0)
    assert conn.execute("SELECT COUNT(*) FROM propietarios").fetchone()[0] == 0  # todo o nada


def test_se_agenda_sin_cedula_ni_consentimientos(conn, empleada, nuevo):
    _, mid = nuevo
    t = _agendar(conn, empleada, mid)
    fila = st.turno(conn, empleada, t)
    assert fila["estado"] == "CONFIRMADO" and fila["propietario_provisional"] == 1


def test_no_se_atiende_hasta_registrar_y_aceptar(conn, empleada, nuevo):
    pid, mid = nuevo
    t = _agendar(conn, empleada, mid)
    with pytest.raises(DatoInvalido, match="sin registrar"):
        st.iniciar_atencion(conn, empleada, t)
    with pytest.raises(DatoInvalido, match="Primero complete"):
        legal.aceptar(conn, empleada, pid, ["TERMINOS", "DATOS"])

    final = sp.completar_registro(conn, empleada, pid, "Carolina Ruiz", "52.123.456", "3112223344", None, "Cra 7 # 8-9")
    assert final == pid
    p = sp.obtener(conn, empleada, pid)
    assert (p["provisional"], p["cedula"], p["nombre"]) == (0, "52123456", "Carolina Ruiz")
    with pytest.raises(DatoInvalido, match="términos"):
        st.iniciar_atencion(conn, empleada, t)
    legal.aceptar(conn, empleada, pid, ["TERMINOS", "DATOS"])
    st.iniciar_atencion(conn, empleada, t)
    assert st.turno(conn, empleada, t)["estado"] == "EN_PROCESO"


def test_completar_con_cedula_existente_une_al_cliente(conn, empleada, nuevo):
    """Si el «cliente nuevo» ya estaba registrado, sus mascotas y turnos pasan a ese propietario."""
    pid, mid = nuevo
    viejo = sp.crear(conn, empleada, "Carolina Ruiz", "52123456", "3112223344", None, "Cra 7")
    lola_vieja = sp.crear_mascota(conn, empleada, viejo, "Lola", _raza(conn, "Shih Tzu"))
    otra = sp.crear_mascota(conn, empleada, pid, "Max", _raza(conn, "Schnauzer"))
    t = _agendar(conn, empleada, mid)

    final = sp.completar_registro(conn, empleada, pid, "Carolina", "52123456", "3112223344", None, "Cra 7")
    assert final == viejo
    assert conn.execute("SELECT COUNT(*) FROM propietarios WHERE id = ?", (pid,)).fetchone()[0] == 0
    assert sorted(m["nombre"] for m in sp.mascotas(conn, empleada, viejo)) == ["Lola", "Max"]
    assert st.turno(conn, empleada, t)["mascota_id"] == lola_vieja  # la misma Lola, sin duplicarla
    assert sp.mascota(conn, empleada, otra)["propietario_id"] == viejo
    assert "COMPLETAR_REGISTRO" in [f[0] for f in conn.execute("SELECT accion FROM auditoria")]


def test_editar_datos_de_un_cliente_sin_registrar_lo_registra(conn, empleada, nuevo):
    pid, _ = nuevo
    assert sp.editar(conn, empleada, pid, "Carolina", "52123456", "3112223344", "", "Cra 7") == pid
    assert sp.obtener(conn, empleada, pid)["provisional"] == 0


def test_completar_un_registrado_se_rechaza(conn, empleada):
    pid = sp.crear(conn, empleada, "María", "1098765432", "3012345678", None, "Calle 10")
    with pytest.raises(DatoInvalido, match="ya está registrado"):
        sp.completar_registro(conn, empleada, pid, "María", "1098765432", "3012345678", None, "Calle 10")


def test_cliente_registrado_sigue_necesitando_consentimientos_para_agendar(conn, empleada):
    pid = sp.crear(conn, empleada, "María", "1098765432", "3012345678", None, "Calle 10")
    mid = sp.crear_mascota(conn, empleada, pid, "Toby", _raza(conn, "Shih Tzu"))
    with pytest.raises(DatoInvalido, match="términos"):
        _agendar(conn, empleada, mid)
