import os
import subprocess
import sys
import threading
import time as reloj_real
from pathlib import Path

import main
from clinican.datos.conexion import abrir
from clinican.datos.migraciones import MIGRACIONES
from clinican.servicios import respaldos
from conftest import AHORA

BACKEND = Path(__file__).resolve().parents[1]


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
        reloj_real.sleep(0.05)  # el respaldo diario corre al arrancar
    parar.set()
    hilo.join(30)
    assert resultado["codigo"] == 0
    con = abrir(ruta)
    try:
        assert con.execute("PRAGMA user_version").fetchone()[0] == len(MIGRACIONES)
    finally:
        con.close()
    nombres = [p.name for p in respaldos.listar_respaldos(ruta.parent / "respaldos")]
    assert len(nombres) == 2  # diario + al cerrar


def test_ruta_por_defecto(monkeypatch):
    monkeypatch.delenv("CLINICAN_BD", raising=False)
    assert main.ruta_base() == Path.home() / "Clinican" / "clinican.db"
    monkeypatch.setenv("CLINICAN_BD", "  ")
    assert main.ruta_base() == Path.home() / "Clinican" / "clinican.db"


def test_demo_corre_sin_error():
    entorno = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proceso = subprocess.run(
        [sys.executable, "-m", "clinican.demo"], cwd=BACKEND, env=entorno,
        capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert proceso.returncode == 0, proceso.stderr
    salida = proceso.stdout
    for titulo in ("1) Capas", "2) Último cupo", "3) Agendar sin red", "4) Cambio de canal"):
        assert titulo in salida
    assert "VIOLACIÓN" not in salida
    assert salida.count("obtuvo el turno") == 1 and "No hay cupo" in salida
    assert "con reintento" in salida and "1 con reintento" in salida
    assert "[recordatorio]" in salida and "recordatorios.txt ->" in salida
    assert "Demo terminada." in salida
