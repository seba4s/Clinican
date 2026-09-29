"""Rutas del programa, correctas tanto con Python como empaquetado con PyInstaller.

- Los recursos (logo, icono) viajan dentro del paquete.
- La base de datos y los respaldos viven en la carpeta raíz del proyecto
  (C:\\Clinican\\datos y C:\\Clinican\\respaldos), fuera de ``dist``, para que
  no se pierdan al recompilar.
- La variable de entorno ``CLINICAN_HOME`` permite cambiar la carpeta raíz.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _raiz_codigo() -> Path:
    """Carpeta donde está main.py (modo Python)."""
    return Path(__file__).resolve().parent.parent


def es_empaquetado() -> bool:
    return bool(getattr(sys, "frozen", False))


def carpeta_raiz(ejecutable: str | None = None, empaquetado: bool | None = None) -> Path:
    """Carpeta raíz de datos del sistema (normalmente C:\\Clinican)."""
    personalizada = os.environ.get("CLINICAN_HOME")
    if personalizada:
        return Path(personalizada)

    if empaquetado is None:
        empaquetado = es_empaquetado()
    if not empaquetado:
        return _raiz_codigo()

    carpeta_exe = Path(ejecutable or sys.executable).resolve().parent
    # Compilado en C:\Clinican\dist\CLINICAN\CLINICAN.exe -> raíz C:\Clinican
    if carpeta_exe.parent.name.lower() == "dist":
        return carpeta_exe.parent.parent
    return carpeta_exe


def carpeta_assets() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "assets"
    return _raiz_codigo() / "assets"


def carpeta_datos() -> Path:
    return carpeta_raiz() / "datos"


def carpeta_respaldos() -> Path:
    return carpeta_raiz() / "respaldos"


def ruta_bd() -> Path:
    return carpeta_datos() / "clinican.db"


def asset(nombre: str) -> Path:
    return carpeta_assets() / nombre
