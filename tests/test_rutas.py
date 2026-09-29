"""Rutas correctas con Python y empaquetado (sys.frozen)."""

import sys
from pathlib import Path

import pytest

from clinican import rutas

solo_windows = pytest.mark.skipif(sys.platform != "win32", reason="rutas de Windows (C:\\...)")


def test_modo_python(monkeypatch):
    monkeypatch.delenv("CLINICAN_HOME", raising=False)
    raiz = rutas.carpeta_raiz(empaquetado=False)
    assert (raiz / "main.py").exists() or (raiz / "clinican").is_dir()
    assert rutas.ruta_bd().name == "clinican.db"


@solo_windows
def test_empaquetado_en_dist(monkeypatch):
    monkeypatch.delenv("CLINICAN_HOME", raising=False)
    raiz = rutas.carpeta_raiz(r"C:\Clinican\dist\CLINICAN\CLINICAN.exe", empaquetado=True)
    assert raiz == Path(r"C:\Clinican")


@solo_windows
def test_empaquetado_fuera_de_dist(monkeypatch):
    monkeypatch.delenv("CLINICAN_HOME", raising=False)
    raiz = rutas.carpeta_raiz(r"D:\Programas\CLINICAN\CLINICAN.exe", empaquetado=True)
    assert raiz == Path(r"D:\Programas\CLINICAN")


def test_variable_de_entorno(monkeypatch, tmp_path):
    monkeypatch.setenv("CLINICAN_HOME", str(tmp_path))
    assert rutas.ruta_bd() == tmp_path / "datos" / "clinican.db"
    assert rutas.carpeta_respaldos() == tmp_path / "respaldos"


def test_empaquetado_en_dist_cualquier_sistema(monkeypatch, tmp_path):
    """La misma regla con rutas del sistema donde corren las pruebas."""
    monkeypatch.delenv("CLINICAN_HOME", raising=False)
    exe = tmp_path / "Clinican" / "dist" / "CLINICAN" / "CLINICAN.exe"
    assert rutas.carpeta_raiz(str(exe), empaquetado=True) == (tmp_path / "Clinican").resolve()
    suelto = tmp_path / "Programas" / "CLINICAN" / "CLINICAN.exe"
    assert rutas.carpeta_raiz(str(suelto), empaquetado=True) == (tmp_path / "Programas" / "CLINICAN").resolve()
