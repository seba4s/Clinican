"""Prueba de arquitectura: las capas no tienen atajos.

Lee el código fuente con ``ast`` (no lo ejecuta) y falla si:

* una capa importa otra que no le corresponde (las dependencias apuntan al dominio);
* se usa ``sqlite3``, se ejecuta SQL o aparece una sentencia SQL fuera de ``datos/``;
* se usa la red fuera de ``adaptadores/`` (la agenda debe funcionar sin conexión).

Los archivos sueltos en ``clinican/`` (``demo.py``) y ``main.py`` son raíces de composición
y pueden conectar todas las capas.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1] / "clinican"

PERMITIDAS: dict[str, set[str]] = {
    "dominio": set(),
    "datos": {"dominio"},
    "servicios": {"datos", "dominio"},
    "adaptadores": {"servicios", "dominio"},
    "ui": {"servicios", "dominio"},
}
CAPAS_CON_SQL = {"datos"}
CAPAS_CON_RED = {"adaptadores"}

MODULOS_SQL = {"sqlite3"}
MODULOS_RED = {"socket", "ssl", "http", "urllib", "requests", "httpx", "smtplib", "ftplib", "asyncio"}
LLAMADAS_SQL = {"execute", "executemany", "executescript", "backup"}
PATRON_SQL = re.compile(
    r"^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|BEGIN|COMMIT|ROLLBACK|PRAGMA|REPLACE|WITH)\s", re.S)


def _docstrings(arbol: ast.AST) -> set[int]:
    ids = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            cuerpo = nodo.body
            if cuerpo and isinstance(cuerpo[0], ast.Expr) and isinstance(cuerpo[0].value, ast.Constant):
                ids.add(id(cuerpo[0].value))
    return ids


def _importaciones(arbol: ast.AST, paquete: str):
    """(línea, módulo absoluto) de cada import, incluidos los relativos y los internos a funciones."""
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                yield nodo.lineno, alias.name
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level:
                base = paquete.split(".")[: len(paquete.split(".")) - nodo.level + 1]
                modulo = ".".join(base + ([nodo.module] if nodo.module else []))
            else:
                modulo = nodo.module or ""
            yield nodo.lineno, modulo
            for alias in nodo.names:  # from clinican import datos
                yield nodo.lineno, f"{modulo}.{alias.name}"


def _capa_de(modulo: str) -> str | None:
    partes = modulo.split(".")
    return partes[1] if len(partes) > 1 and partes[0] == "clinican" and partes[1] in PERMITIDAS else None


def analizar(raiz: Path) -> list[str]:
    """Devuelve una línea por cada atajo encontrado en el paquete ``raiz``."""
    errores: list[str] = []
    for capa in PERMITIDAS:
        for ruta in sorted((raiz / capa).rglob("*.py")):
            relativa = ruta.relative_to(raiz.parent)
            paquete = ".".join(relativa.with_suffix("").parts[:-1])
            arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))

            for linea, modulo in _importaciones(arbol, paquete):
                destino = _capa_de(modulo)
                raiz_modulo = modulo.split(".")[0]
                if destino and destino != capa and destino not in PERMITIDAS[capa]:
                    errores.append(f"{relativa}:{linea} — {capa} importa {destino} ({modulo})")
                if raiz_modulo in MODULOS_SQL and capa not in CAPAS_CON_SQL:
                    errores.append(f"{relativa}:{linea} — {capa} usa {raiz_modulo} (solo datos)")
                if raiz_modulo in MODULOS_RED and capa not in CAPAS_CON_RED:
                    errores.append(f"{relativa}:{linea} — {capa} usa la red con {raiz_modulo} (solo adaptadores)")

            if capa in CAPAS_CON_SQL:
                continue
            docs = _docstrings(arbol)
            for nodo in ast.walk(arbol):
                if (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)
                        and nodo.func.attr in LLAMADAS_SQL):
                    errores.append(f"{relativa}:{nodo.lineno} — {capa} ejecuta SQL (.{nodo.func.attr})")
                elif (isinstance(nodo, ast.Constant) and isinstance(nodo.value, str)
                        and id(nodo) not in docs and PATRON_SQL.match(nodo.value)):
                    errores.append(f"{relativa}:{nodo.lineno} — {capa} contiene SQL: {nodo.value.strip()[:40]!r}")
    return errores


# --- La prueba real -------------------------------------------------------------------------------

def test_las_capas_existen():
    for capa in PERMITIDAS:
        assert (RAIZ / capa / "__init__.py").is_file(), f"Falta la capa {capa}"


def test_no_hay_atajos_entre_capas():
    errores = analizar(RAIZ)
    assert not errores, "Atajos prohibidos:\n" + "\n".join(errores)


# --- El detector detecta: se plantan atajos a propósito en una copia falsa -------------------------

def _paquete_falso(tmp_path: Path, capa: str, codigo: str) -> Path:
    raiz = tmp_path / "clinican"
    for c in PERMITIDAS:
        (raiz / c).mkdir(parents=True, exist_ok=True)
        (raiz / c / "__init__.py").write_text("")
    (raiz / capa / "plantado.py").write_text(codigo, encoding="utf-8")
    return raiz


@pytest.mark.parametrize("capa, codigo, pista", [
    ("dominio", "from clinican.datos import conexion\n", "dominio importa datos"),
    ("dominio", "import clinican.servicios.turnos\n", "dominio importa servicios"),
    ("datos", "from clinican.servicios import x\n", "datos importa servicios"),
    ("servicios", "from clinican.adaptadores import x\n", "servicios importa adaptadores"),
    ("ui", "from clinican.datos import repo\n", "ui importa datos"),
    ("ui", "from clinican import datos\n", "ui importa datos"),
    ("servicios", "from ..datos import repo\n", None),  # relativo permitido: no debe fallar
    ("dominio", "from ..datos import repo\n", "dominio importa datos"),
    ("dominio", "import sqlite3\n", "usa sqlite3"),
    ("servicios", "def f(con):\n    con.execute('x')\n", "ejecuta SQL"),
    ("servicios", "Q = 'SELECT * FROM turnos'\n", "contiene SQL"),
    ("ui", "def f(c):\n    c.executemany('x', [])\n", "ejecuta SQL"),
    ("servicios", "import urllib.request\n", "usa la red"),
    ("dominio", "from http import client\n", "usa la red"),
    ("adaptadores", "import urllib.request\n", None),
    ("servicios", 'def f():\n    """SELECT en un docstring no es SQL."""\n', None),
])
def test_el_detector_encuentra_atajos_plantados(tmp_path, capa, codigo, pista):
    errores = analizar(_paquete_falso(tmp_path, capa, codigo))
    if pista is None:
        assert errores == []
    else:
        assert any(pista in e for e in errores), errores
