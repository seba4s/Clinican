"""Rutas correctas con Python y empaquetado (sys.frozen)."""

from pathlib import Path

from clinican import rutas


def test_modo_python(monkeypatch):
    monkeypatch.delenv("CLINICAN_HOME", raising=False)
    raiz = rutas.carpeta_raiz(empaquetado=False)
    assert (raiz / "main.py").exists() or (raiz / "clinican").is_dir()
    assert rutas.ruta_bd().name == "clinican.db"


def test_empaquetado_en_dist(monkeypatch):
    monkeypatch.delenv("CLINICAN_HOME", raising=False)
    raiz = rutas.carpeta_raiz(r"C:\Clinican\dist\CLINICAN\CLINICAN.exe", empaquetado=True)
    assert raiz == Path(r"C:\Clinican")


def test_empaquetado_fuera_de_dist(monkeypatch):
    monkeypatch.delenv("CLINICAN_HOME", raising=False)
    raiz = rutas.carpeta_raiz(r"D:\Programas\CLINICAN\CLINICAN.exe", empaquetado=True)
    assert raiz == Path(r"D:\Programas\CLINICAN")


def test_variable_de_entorno(monkeypatch, tmp_path):
    monkeypatch.setenv("CLINICAN_HOME", str(tmp_path))
    assert rutas.ruta_bd() == tmp_path / "datos" / "clinican.db"
    assert rutas.carpeta_respaldos() == tmp_path / "respaldos"
