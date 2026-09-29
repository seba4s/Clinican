"""Fase 1: primer arranque, inicio de sesión, gestión de personal y un solo ADMIN."""

import sqlite3

import pytest

from clinican.dominio.errores import CredencialesInvalidas, DatoInvalido, PermisoDenegado
from clinican.dominio.permisos import ADMIN, PERSONAL
from clinican.servicios import acceso, auditoria, personal


def _admins_activos(conn):
    return conn.execute("SELECT COUNT(*) FROM personal WHERE rol='ADMIN' AND activo=1").fetchone()[0]


# ------------------------------------------------------------- primer arranque

def test_primer_arranque_crea_admin(conn):
    assert acceso.necesita_primer_arranque(conn)
    sesion = acceso.crear_administradora_inicial(conn, "  Angela   Benavides ", "Jefe", "1234")
    assert sesion.rol == ADMIN and sesion.nombre == "Angela Benavides"
    assert not acceso.necesita_primer_arranque(conn)
    assert _admins_activos(conn) == 1


def test_primer_arranque_solo_una_vez(conn, admin):
    with pytest.raises(DatoInvalido):
        acceso.crear_administradora_inicial(conn, "Otra", "Jefe", "1111")
    assert _admins_activos(conn) == 1


def test_primer_arranque_valida_pin(conn):
    with pytest.raises(DatoInvalido):
        acceso.crear_administradora_inicial(conn, "Angela", "Jefe", "12")
    assert acceso.necesita_primer_arranque(conn)


# ---------------------------------------------------------- inicio de sesión

def test_inicio_sesion(conn, admin):
    s = acceso.iniciar_sesion(conn, "angela", "1234")  # sin distinguir mayúsculas
    assert s.personal_id == admin.personal_id and s.es_admin


@pytest.mark.parametrize("nombre,pin", [("Angela", "9999"), ("Nadie", "1234"), ("Angela", "")])
def test_inicio_sesion_fallido_se_audita(conn, admin, nombre, pin):
    with pytest.raises(CredencialesInvalidas):
        acceso.iniciar_sesion(conn, nombre, pin)
    ultima = conn.execute("SELECT accion FROM auditoria ORDER BY id DESC LIMIT 1").fetchone()[0]
    assert ultima == "INICIO_SESION_FALLIDO"


def test_persona_inactiva_no_entra(conn, admin, empleada):
    personal.desactivar(conn, admin, empleada.personal_id)
    with pytest.raises(CredencialesInvalidas):
        acceso.iniciar_sesion(conn, "Laura", "5678")
    # y una sesión ya abierta pierde el acceso de inmediato
    with pytest.raises(PermisoDenegado):
        acceso.cambiar_mi_pin(conn, empleada, "5678", "1111")


# ------------------------------------------------------ gestión de personal

def test_jefe_crea_personal(conn, admin):
    nuevo = personal.crear(conn, admin, "Camila", "Médica veterinaria", "4321")
    fila = conn.execute("SELECT * FROM personal WHERE id = ?", (nuevo,)).fetchone()
    assert fila["rol"] == PERSONAL and fila["activo"] == 1
    assert fila["pin_hash"] != "4321"
    nombres = [f["nombre"] for f in personal.listar_activos(conn)]
    assert "Camila" in nombres


def test_nombre_repetido(conn, admin, empleada):
    with pytest.raises(DatoInvalido):
        personal.crear(conn, admin, "LAURA", "Auxiliar", "1111")


def test_editar_personal(conn, admin, empleada):
    personal.editar(conn, admin, empleada.personal_id, "Laura Gómez", "Auxiliar")
    fila = conn.execute("SELECT nombre, cargo FROM personal WHERE id=?", (empleada.personal_id,)).fetchone()
    assert tuple(fila) == ("Laura Gómez", "Auxiliar")


def test_cambiar_pin_de_otro_y_propio(conn, admin, empleada):
    personal.cambiar_pin_de(conn, admin, empleada.personal_id, "2468")
    acceso.iniciar_sesion(conn, "Laura", "2468")
    acceso.cambiar_mi_pin(conn, empleada, "2468", "1357")
    acceso.iniciar_sesion(conn, "Laura", "1357")
    with pytest.raises(CredencialesInvalidas):
        acceso.cambiar_mi_pin(conn, empleada, "0000", "1111")


def test_reactivar(conn, admin, empleada):
    personal.desactivar(conn, admin, empleada.personal_id)
    personal.reactivar(conn, admin, empleada.personal_id)
    acceso.iniciar_sesion(conn, "Laura", "5678")


# --------------------------------------------------------- un solo ADMIN

def test_indice_unico_impide_dos_admins(conn, admin, empleada):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE personal SET rol='ADMIN' WHERE id=?", (empleada.personal_id,))


def test_jefe_no_puede_desactivarse(conn, admin):
    with pytest.raises(DatoInvalido):
        personal.desactivar(conn, admin, admin.personal_id)
    assert _admins_activos(conn) == 1


def test_transferir_administracion(conn, admin, empleada):
    with pytest.raises(CredencialesInvalidas):
        personal.transferir_administracion(conn, admin, empleada.personal_id, "0000")
    personal.transferir_administracion(conn, admin, empleada.personal_id, "1234")
    assert _admins_activos(conn) == 1
    assert admin.rol == PERSONAL
    rol_laura = conn.execute("SELECT rol FROM personal WHERE id=?", (empleada.personal_id,)).fetchone()[0]
    assert rol_laura == ADMIN
    # la antigua jefe ya no puede gestionar personal
    with pytest.raises(PermisoDenegado):
        personal.crear(conn, admin, "Otra", "Auxiliar", "1111")
    # y ahora sí puede ser desactivada por la nueva administradora
    nueva = acceso.iniciar_sesion(conn, "Laura", "5678")
    personal.desactivar(conn, nueva, admin.personal_id)
    assert _admins_activos(conn) == 1


def test_transferir_a_si_misma_o_inactiva(conn, admin, empleada):
    with pytest.raises(DatoInvalido):
        personal.transferir_administracion(conn, admin, admin.personal_id, "1234")
    personal.desactivar(conn, admin, empleada.personal_id)
    with pytest.raises(DatoInvalido):
        personal.transferir_administracion(conn, admin, empleada.personal_id, "1234")
    assert _admins_activos(conn) == 1


# ------------------------------------------------------------- auditoría

def test_acciones_quedan_auditadas(conn, admin, empleada):
    personal.editar(conn, admin, empleada.personal_id, "Laura", "Auxiliar")
    personal.desactivar(conn, admin, empleada.personal_id)
    acciones = [f["accion"] for f in auditoria.consultar(conn, admin)]
    for esperada in ("PRIMER_ARRANQUE", "CREAR_PERSONAL", "INICIO_SESION", "EDITAR_PERSONAL", "DESACTIVAR_PERSONAL"):
        assert esperada in acciones


def test_auditoria_filtra_por_persona(conn, admin, empleada):
    filas = auditoria.consultar(conn, admin, personal_id=empleada.personal_id)
    assert filas and all(f["persona"] == "Laura" for f in filas)
