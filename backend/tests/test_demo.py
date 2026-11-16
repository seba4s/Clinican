import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


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
