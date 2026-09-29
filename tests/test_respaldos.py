"""Fase 5: respaldo automático, manual y restauración (sección 10)."""

import sqlite3
from datetime import datetime, timedelta

import pytest

from clinican.datos import migraciones
from clinican.datos.conexion import conectar
from clinican.dominio.errores import DatoInvalido, PermisoDenegado
from clinican.servicios import acceso, configuracion, personal, respaldos
from clinican.servicios import propietarios as sp

AHORA = datetime(2026, 10, 5, 18, 30, 0)


@pytest.fixture
def base(tmp_path):
    """Base de datos en archivo, como en el PC real."""
    c = conectar(tmp_path / "datos" / "clinican.db")
    yield c
    c.close()


@pytest.fixture
def jefe(base):
    return acceso.crear_administradora_inicial(base, "Angela", "Jefe", "1234")


@pytest.fixture
def laura(base, jefe):
    personal.crear(base, jefe, "Laura", "Asistente de peluquería", "5678")
    return acceso.iniciar_sesion(base, "Laura", "5678")


@pytest.fixture
def carpeta(tmp_path):
    return tmp_path / "respaldos"


def _propietarios(conn):
    return [f["nombre"] for f in conn.execute("SELECT nombre FROM propietarios ORDER BY id")]


# ------------------------------------------------------------ automáticos

def test_respaldo_automatico_es_una_copia_completa(base, jefe, carpeta):
    sp.crear(base, jefe, "María Pérez", "1098765432", "3012345678", None, "Calle 10")
    ruta = respaldos.automatico(base, carpeta, AHORA)
    assert ruta.name == "clinican_auto_2026-10-05_183000.db"
    copia = sqlite3.connect(ruta)
    assert copia.execute("SELECT nombre FROM propietarios").fetchone()[0] == "María Pérez"
    assert copia.execute("PRAGMA user_version").fetchone()[0] == migraciones.VERSION_ACTUAL
    copia.close()
    assert not list(carpeta.glob("*.tmp"))


def test_conserva_los_ultimos_n(base, jefe, carpeta):
    configuracion.guardar(base, jefe, {"respaldos_conservar": "3"})
    for i in range(5):
        respaldos.automatico(base, carpeta, AHORA + timedelta(hours=i))
    lista = respaldos.listar(carpeta)
    assert len(lista) == 3
    assert [r.fecha.hour for r in lista] == [22, 21, 20]  # los más recientes


def test_limpieza_no_borra_manuales(base, jefe, carpeta):
    configuracion.guardar(base, jefe, {"respaldos_conservar": "1"})
    respaldos.respaldar_ahora(base, jefe, carpeta, AHORA)
    respaldos.automatico(base, carpeta, AHORA + timedelta(hours=1))
    respaldos.automatico(base, carpeta, AHORA + timedelta(hours=2))
    assert sorted(r.tipo for r in respaldos.listar(carpeta)) == ["auto", "manual"]


def test_respaldo_diario_una_vez_por_dia(base, carpeta):
    assert respaldos.diario(base, carpeta, AHORA) is not None
    assert respaldos.diario(base, carpeta, AHORA + timedelta(hours=3)) is None
    assert respaldos.diario(base, carpeta, AHORA + timedelta(days=1)) is not None
    assert len(respaldos.listar(carpeta)) == 2


def test_dos_respaldos_en_el_mismo_segundo(base, carpeta):
    a = respaldos.automatico(base, carpeta, AHORA)
    b = respaldos.automatico(base, carpeta, AHORA)
    assert a != b and a.exists() and b.exists()


def test_base_en_memoria_no_se_respalda_sola(conn, tmp_path):
    assert respaldos.automatico(conn, tmp_path) is None


# ---------------------------------------------------------------- manuales

def test_personal_puede_respaldar_a_usb(base, laura, tmp_path):
    usb = tmp_path / "USB"
    ruta = respaldos.respaldar_ahora(base, laura, usb, AHORA)
    assert ruta.parent == usb and ruta.name.startswith("clinican_manual_")
    accion = base.execute("SELECT accion FROM auditoria ORDER BY id DESC LIMIT 1").fetchone()[0]
    assert accion == "RESPALDAR"


def test_respaldar_sin_carpeta_o_sin_sesion(base, jefe):
    with pytest.raises(DatoInvalido, match="carpeta"):
        respaldos.respaldar_ahora(base, jefe, "")
    with pytest.raises(PermisoDenegado):
        respaldos.respaldar_ahora(base, None, "x")


# --------------------------------------------------------------- restaurar

def test_restaurar_recupera_los_datos_y_guarda_copia_previa(base, jefe, carpeta):
    sp.crear(base, jefe, "María Pérez", "1098765432", "3012345678", None, "Calle 10")
    respaldo = respaldos.automatico(base, carpeta, AHORA)
    sp.crear(base, jefe, "Pedro Gómez", "5555555", "3150000000", None, "Cra 2")
    assert _propietarios(base) == ["María Pérez", "Pedro Gómez"]

    previa = respaldos.restaurar(base, jefe, respaldo, carpeta, AHORA + timedelta(minutes=5))
    assert _propietarios(base) == ["María Pérez"]
    assert previa.name.startswith("clinican_antes-de-restaurar_")
    # La copia previa tiene el estado anterior: se puede deshacer
    respaldos.restaurar(base, jefe, previa, carpeta, AHORA + timedelta(minutes=6))
    assert _propietarios(base) == ["María Pérez", "Pedro Gómez"]
    assert base.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert "RESTAURAR_RESPALDO" in [f[0] for f in base.execute("SELECT accion FROM auditoria")]


def test_restaurar_desde_otro_equipo_y_la_base_sigue_funcionando(base, jefe, carpeta, tmp_path):
    """Un respaldo hecho en otra base se puede restaurar y usar enseguida."""
    otra = conectar(tmp_path / "otra.db")
    admin_otra = acceso.crear_administradora_inicial(otra, "Angela", "Jefe", "4321")
    sp.crear(otra, admin_otra, "Cliente USB", "7777777", "3170000000", None, "Cra 4")
    usb = respaldos.respaldar_ahora(otra, admin_otra, tmp_path / "USB", AHORA)
    otra.close()

    respaldos.restaurar(base, jefe, usb, carpeta, AHORA)
    assert _propietarios(base) == ["Cliente USB"]
    nueva = acceso.iniciar_sesion(base, "Angela", "4321")  # el PIN es el del respaldo
    sp.crear(base, nueva, "Nuevo", "8888888", "3180000000", None, "Cra 5")


def test_solo_admin_restaura(base, laura, carpeta):
    respaldo = respaldos.automatico(base, carpeta, AHORA)
    with pytest.raises(PermisoDenegado):
        respaldos.restaurar(base, laura, respaldo, carpeta)
    assert [r.tipo for r in respaldos.listar(carpeta)] == ["auto"]  # no se hizo copia previa


def test_restaurar_archivo_invalido_no_toca_nada(base, jefe, carpeta, tmp_path):
    sp.crear(base, jefe, "María Pérez", "1098765432", "3012345678", None, "Calle 10")
    malo = tmp_path / "malo.db"
    malo.write_bytes(b"esto no es una base de datos" * 100)
    with pytest.raises(DatoInvalido):
        respaldos.restaurar(base, jefe, malo, carpeta)
    ajena = tmp_path / "ajena.db"
    c = sqlite3.connect(ajena)
    c.execute("CREATE TABLE cosas (x)")
    c.close()
    with pytest.raises(DatoInvalido, match="no es un respaldo"):
        respaldos.restaurar(base, jefe, ajena, carpeta)
    with pytest.raises(DatoInvalido, match="No se encontró"):
        respaldos.restaurar(base, jefe, tmp_path / "no_existe.db", carpeta)
    assert _propietarios(base) == ["María Pérez"]
    assert respaldos.listar(carpeta) == []


def test_restaurar_respaldo_mas_nuevo_se_rechaza(base, jefe, carpeta):
    respaldo = respaldos.automatico(base, carpeta, AHORA)
    c = sqlite3.connect(respaldo)
    c.execute(f"PRAGMA user_version = {migraciones.VERSION_ACTUAL + 1}")
    c.close()
    with pytest.raises(DatoInvalido, match="más nueva"):
        respaldos.restaurar(base, jefe, respaldo, carpeta)


def test_restaurar_respaldo_antiguo_lo_actualiza(base, jefe, carpeta, tmp_path):
    """Un respaldo de la versión 2 se restaura y recibe la migración 3."""
    viejo = tmp_path / "v2.db"
    c = sqlite3.connect(viejo)
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("BEGIN")
    migraciones._v1(c)
    migraciones._v2(c)
    c.execute("PRAGMA user_version = 2")
    c.commit()
    c.execute("INSERT INTO personal (nombre, cargo, rol, pin_hash, pin_sal) VALUES ('Vieja','Jefe','ADMIN','x','y')")
    c.commit()
    c.close()
    respaldos.restaurar(base, jefe, viejo, carpeta)
    assert migraciones.version(base) == migraciones.VERSION_ACTUAL
    assert base.execute("SELECT valor FROM config WHERE clave = 'abono_minimo'").fetchone()[0] == "20000"


def test_revisar_muestra_resumen(base, jefe, carpeta):
    sp.crear(base, jefe, "María Pérez", "1098765432", "3012345678", None, "Calle 10")
    resumen = respaldos.revisar(respaldos.automatico(base, carpeta, AHORA))
    assert resumen["propietarios"] == 1 and resumen["turnos"] == 0
