"""RN-01: permisos por rol (tabla de la sección 4).

Se prueba la tabla completa y, para cada acción ya implementada, que la capa
de servicios rechace al PERSONAL aunque la pantalla no muestre el botón.
Las fases siguientes agregan aquí las acciones de turnos, bloqueos, etc.
"""

import pytest

from clinican.dominio.errores import PermisoDenegado
from clinican.dominio.permisos import ADMIN, PERSONAL, Accion, puede
from clinican.servicios import auditoria, configuracion, personal
from clinican.servicios.base import requerir

# Tabla de la sección 4: acción -> (ADMIN, PERSONAL)
TABLA_SECCION_4 = {
    Accion.AGENDAR_TURNOS: (True, True),
    Accion.REGISTRAR_ABONOS: (True, True),
    Accion.GESTIONAR_PROPIETARIOS: (True, True),
    Accion.GESTIONAR_FICHAS: (True, True),
    Accion.AJUSTAR_FRANJAS_SUELTAS: (True, True),
    Accion.BLOQUEAR_DIAS: (True, False),
    Accion.BLOQUEAR_FRANJAS: (True, False),
    Accion.GESTIONAR_PERSONAL: (True, False),
    Accion.CAMBIAR_CONFIGURACION: (True, False),
    Accion.EDITAR_TEXTOS_LEGALES: (True, False),
    Accion.RESPALDAR: (True, True),
    Accion.RESTAURAR: (True, False),
    Accion.VER_AUDITORIA: (True, False),
    Accion.CAMBIAR_PIN_PROPIO: (True, True),
}


def test_tabla_cubre_todas_las_acciones():
    assert set(TABLA_SECCION_4) == set(Accion)


@pytest.mark.parametrize("accion,esperado", TABLA_SECCION_4.items(), ids=lambda x: getattr(x, "name", ""))
def test_tabla_de_permisos(accion, esperado):
    assert puede(ADMIN, accion) is esperado[0]
    assert puede(PERSONAL, accion) is esperado[1]


@pytest.mark.parametrize("accion,esperado", TABLA_SECCION_4.items(), ids=lambda x: getattr(x, "name", ""))
def test_requerir_en_servicios(conn, admin, empleada, accion, esperado):
    requerir(conn, admin, accion)
    if esperado[1]:
        requerir(conn, empleada, accion)
    else:
        with pytest.raises(PermisoDenegado):
            requerir(conn, empleada, accion)


def test_rol_desconocido_no_puede_nada():
    assert not any(puede("INVITADO", a) for a in Accion)


def test_requerir_sin_sesion(conn):
    with pytest.raises(PermisoDenegado):
        requerir(conn, None, Accion.AGENDAR_TURNOS)


def test_sesion_manipulada_no_sirve(conn, admin, empleada):
    """Aunque alguien cambie el rol en memoria, el servicio relee la base de datos."""
    empleada.rol = ADMIN
    with pytest.raises(PermisoDenegado):
        personal.crear(conn, empleada, "Intrusa", "Auxiliar", "1111")
    assert empleada.rol == PERSONAL


# --- Acciones de ADMIN ya implementadas: el PERSONAL es rechazado en el servicio

def test_personal_no_gestiona_personal(conn, admin, empleada):
    with pytest.raises(PermisoDenegado):
        personal.crear(conn, empleada, "Otra", "Auxiliar", "1111")
    with pytest.raises(PermisoDenegado):
        personal.editar(conn, empleada, admin.personal_id, "X", "Y")
    with pytest.raises(PermisoDenegado):
        personal.desactivar(conn, empleada, admin.personal_id)
    with pytest.raises(PermisoDenegado):
        personal.reactivar(conn, empleada, admin.personal_id)
    with pytest.raises(PermisoDenegado):
        personal.cambiar_pin_de(conn, empleada, admin.personal_id, "0000")
    with pytest.raises(PermisoDenegado):
        personal.transferir_administracion(conn, empleada, empleada.personal_id, "5678")
    with pytest.raises(PermisoDenegado):
        personal.listar_todos(conn, empleada)


def test_personal_no_ve_auditoria(conn, empleada):
    with pytest.raises(PermisoDenegado):
        auditoria.consultar(conn, empleada)


def test_personal_no_cambia_configuracion(conn, empleada):
    with pytest.raises(PermisoDenegado):
        configuracion.guardar(conn, empleada, {"abono_minimo": "1000"})
    assert configuracion.valores(conn)["abono_minimo"] == "20000"
