import threading
import time as reloj_real
from pathlib import Path

import main
from clinican.datos.conexion import abrir
from clinican.datos.migraciones import MIGRACIONES
from clinican.servicios import respaldos
from escenario import AHORA


def test_main_arranca_y_cierra_con_respaldo(tmp_path, monkeypatch):
    ruta = tmp_path / "datos" / "clinican.db"
    monkeypatch.setenv("CLINICAN_BD", str(ruta))
    parar = threading.Event()
    resultado = {}
    hilo = threading.Thread(
        target=lambda: resultado.setdefault(
            "codigo",
            main.main(parar=parar, reloj=lambda: AHORA, intervalo_despacho=0.05,
                      intervalo_respaldo=0.05, intervalo_barrido=0),
        )
    )
    hilo.start()
    limite = reloj_real.monotonic() + 15
    while not respaldos.listar_respaldos(ruta.parent / "respaldos") and reloj_real.monotonic() < limite:
        reloj_real.sleep(0.05)
    parar.set()
    hilo.join(30)
    assert resultado["codigo"] == 0
    con = abrir(ruta)
    try:
        assert con.execute("PRAGMA user_version").fetchone()[0] == len(MIGRACIONES)
    finally:
        con.close()
    nombres = [p.name for p in respaldos.listar_respaldos(ruta.parent / "respaldos")]
    assert len(nombres) == 2


def test_ruta_por_defecto(monkeypatch):
    monkeypatch.delenv("CLINICAN_BD", raising=False)
    assert main.ruta_base() == Path.home() / "Clinican" / "clinican.db"
    monkeypatch.setenv("CLINICAN_BD", "  ")
    assert main.ruta_base() == Path.home() / "Clinican" / "clinican.db"
