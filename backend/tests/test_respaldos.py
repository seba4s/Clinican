import sqlite3
import time as reloj_real
from datetime import timedelta

import pytest

from clinican.datos.conexion import abrir
from clinican.datos.migraciones import MIGRACIONES, BaseMasNueva, migrar
from clinican.dominio.errores import DatoInvalido, NoEncontrado
from clinican.servicios import clientes, configuracion, respaldos
from clinican.servicios.auditoria import historial
from conftest import AHORA


def _carpeta(ruta_db):
    return ruta_db.parent / "respaldos"


def test_crear_respaldo_verificado(con, esc, ruta_db):
    esc.propietario("Ana")
    copia = respaldos.crear_respaldo(ruta_db, ahora=AHORA)
    assert copia.parent == _carpeta(ruta_db)
    assert copia.name == "clinican_20261109_080000.db"
    otra = sqlite3.connect(copia)
    try:
        assert otra.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert otra.execute("SELECT nombre FROM propietarios").fetchall() == [("Ana",)]
    finally:
        otra.close()
    assert historial(con, "respaldo")[-1].detalle["archivo"] == copia.name


def test_dos_respaldos_en_el_mismo_segundo(ruta_db):
    a = respaldos.crear_respaldo(ruta_db, ahora=AHORA)
    b = respaldos.crear_respaldo(ruta_db, ahora=AHORA)
    assert a != b and a.exists() and b.exists()


def test_carpeta_configurable_absoluta(con, ruta_db, tmp_path):
    destino = tmp_path / "otra_carpeta"
    configuracion.guardar(con, "carpeta_respaldos", str(destino), ahora=AHORA)
    assert respaldos.crear_respaldo(ruta_db, ahora=AHORA).parent == destino


def test_conserva_las_ultimas_n(con, ruta_db):
    assert configuracion.cargar(con).respaldos_a_conservar == 30
    configuracion.guardar(con, "respaldos_a_conservar", 3, ahora=AHORA)
    for i in range(5):
        respaldos.crear_respaldo(ruta_db, ahora=AHORA + timedelta(days=i))
    nombres = [p.name for p in respaldos.listar_respaldos(_carpeta(ruta_db))]
    assert nombres == [
        "clinican_20261111_080000.db", "clinican_20261112_080000.db", "clinican_20261113_080000.db"
    ]


def test_respaldo_diario_solo_si_falta(ruta_db):
    assert not respaldos.hay_respaldo_del_dia(ruta_db, AHORA)
    assert respaldos.respaldo_diario_si_falta(ruta_db, ahora=AHORA) is not None
    assert respaldos.respaldo_diario_si_falta(ruta_db, ahora=AHORA + timedelta(hours=10)) is None
    assert respaldos.respaldo_diario_si_falta(ruta_db, ahora=AHORA + timedelta(days=1)) is not None
    assert len(respaldos.listar_respaldos(_carpeta(ruta_db))) == 2


def test_restaurar_respalda_antes_y_restaura(con, esc, ruta_db):
    esc.propietario("Ana")
    copia = respaldos.crear_respaldo(ruta_db, ahora=AHORA)
    esc.propietario("Beto")  # cambio posterior a la copia
    previo = respaldos.restaurar(ruta_db, copia, ahora=AHORA + timedelta(minutes=5))
    nueva = abrir(ruta_db)
    try:
        assert [p.nombre for p in clientes.buscar_propietarios(nueva)] == ["Ana"]
        assert historial(nueva, "respaldo")[-1].accion == "restaurar"
    finally:
        nueva.close()
    # El respaldo previo guarda el estado de antes de restaurar (con Beto)
    viejo = sqlite3.connect(previo)
    try:
        assert {f[0] for f in viejo.execute("SELECT nombre FROM propietarios")} == {"Ana", "Beto"}
    finally:
        viejo.close()


def test_restaurar_copia_invalida_no_toca_nada(esc, ruta_db, tmp_path):
    esc.propietario("Ana")
    basura = tmp_path / "clinican_20260101_000000.db"
    basura.write_bytes(b"esto no es una base de datos" * 100)
    with pytest.raises(DatoInvalido):
        respaldos.restaurar(ruta_db, basura, ahora=AHORA)
    with pytest.raises(NoEncontrado):
        respaldos.restaurar(ruta_db, tmp_path / "no_existe.db", ahora=AHORA)
    con = abrir(ruta_db)
    try:
        assert len(clientes.buscar_propietarios(con)) == 1
    finally:
        con.close()
    assert respaldos.listar_respaldos(_carpeta(ruta_db)) == []


def test_restaurar_copia_vieja_la_migra(ruta_db, tmp_path):
    vieja = tmp_path / "vieja.db"
    c = abrir(vieja)
    migrar(c, MIGRACIONES[:1])
    c.execute("INSERT INTO configuracion VALUES ('abono', '15000')")
    c.close()
    respaldos.restaurar(ruta_db, vieja, ahora=AHORA)
    con = abrir(ruta_db)
    try:
        assert con.execute("PRAGMA user_version").fetchone()[0] == len(MIGRACIONES)
        assert configuracion.cargar(con).abono == 15000
    finally:
        con.close()


def test_restaurar_copia_mas_nueva_rechazada(ruta_db, tmp_path):
    nueva = tmp_path / "nueva.db"
    c = sqlite3.connect(nueva)
    c.execute(f"PRAGMA user_version={len(MIGRACIONES) + 1}")
    c.close()
    with pytest.raises(BaseMasNueva):
        respaldos.restaurar(ruta_db, nueva, ahora=AHORA)


def test_hilo_de_respaldo_diario(ruta_db):
    hilo = respaldos.RespaldoDiario(ruta_db, reloj=lambda: AHORA, intervalo_segundos=0.05)
    hilo.iniciar()
    try:
        limite = reloj_real.monotonic() + 10
        while not respaldos.listar_respaldos(_carpeta(ruta_db)) and reloj_real.monotonic() < limite:
            reloj_real.sleep(0.02)
        reloj_real.sleep(0.2)  # varios ciclos más: no debe duplicar la copia del día
    finally:
        hilo.detener()
    assert not hilo.corriendo
    assert len(respaldos.listar_respaldos(_carpeta(ruta_db))) == 1
