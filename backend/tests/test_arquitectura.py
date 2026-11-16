"""Prueba de arquitectura: verifica capas, aislamiento de SQL y de red con ``ast``.

Reglas:
- Capas permitidas: dominio -> ninguna; datos -> dominio; servicios -> dominio, datos;
  adaptadores -> dominio, servicios; ui (``frontend/interfaz``) -> dominio, servicios.
  ``clinican/__init__.py``, ``clinican/demo.py`` y ``frontend/main.py`` son raíz de composición.
- Fuera de ``datos/``: prohibido ``sqlite3``, llamadas ``.execute``/``.executemany``/
  ``.executescript``/``.backup`` y textos SQL (se ignoran los docstrings).
- Fuera de ``adaptadores/``: prohibidos los módulos de red.
"""

from __future__ import annotations

import ast
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path

PAQUETE = "clinican"
PAQUETE_UI = "interfaz"
RAIZ_REPO = Path(__file__).resolve().parents[2]
FUENTES = {"backend": PAQUETE, "frontend": PAQUETE_UI}

CAPAS_PERMITIDAS: dict[str, set[str]] = {
    "dominio": set(),
    "datos": {"dominio"},
    "servicios": {"dominio", "datos"},
    "adaptadores": {"dominio", "servicios"},
    "ui": {"dominio", "servicios"},
}
RAIZ = "raiz"
MODULOS_RAIZ = {f"{PAQUETE}", f"{PAQUETE}.demo", "main"}

MODULOS_RED = {
    "urllib", "http", "socket", "ssl", "smtplib", "ftplib",
    "socketserver", "xmlrpc", "requests", "httpx", "aiohttp",
}
METODOS_SQL = {"execute", "executemany", "executescript", "backup"}

_PATRONES_SQL = [
    re.compile(r"\bSELECT\b[\s\S]*?\bFROM\b", re.IGNORECASE),
    re.compile(r"\bINSERT\s+(OR\s+\w+\s+)?INTO\b", re.IGNORECASE),
    re.compile(r"\bUPDATE\s+\w+\s+SET\b", re.IGNORECASE),
    re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE),
    re.compile(
        r"\b(CREATE|DROP|ALTER)\s+((UNIQUE|TEMP|TEMPORARY)\s+)?(TABLE|INDEX)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bPRAGMA\s+\w+", re.IGNORECASE),
    re.compile(r"^\s*BEGIN\b", re.IGNORECASE),
    re.compile(r"^\s*(COMMIT|ROLLBACK)\b", re.IGNORECASE),
]


@dataclass(frozen=True)
class Violacion:
    archivo: str
    linea: int
    regla: str
    detalle: str

    def __str__(self) -> str:
        return f"{self.archivo}:{self.linea} [{self.regla}] {self.detalle}"


def _modulo_de(ruta: Path, raiz: Path) -> tuple[str, bool]:
    """Devuelve (nombre de módulo, es_paquete) para un archivo .py."""
    partes = list(ruta.relative_to(raiz).with_suffix("").parts)
    es_paquete = partes[-1] == "__init__"
    if es_paquete:
        partes = partes[:-1]
    return ".".join(partes), es_paquete


def _capa_de(modulo: str) -> str | None:
    """Capa a la que pertenece un módulo propio; RAIZ o None si no clasifica."""
    if modulo in MODULOS_RAIZ:
        return RAIZ
    partes = modulo.split(".")
    if partes[0] == PAQUETE_UI:
        return "ui"
    if partes[0] != PAQUETE:
        return None
    if len(partes) >= 2 and partes[1] in CAPAS_PERMITIDAS and partes[1] != "ui":
        return partes[1]
    return None


def _resolver_relativo(nivel: int, modulo: str | None, paquete_actual: str) -> str:
    base = paquete_actual.split(".") if paquete_actual else []
    if nivel > 1:
        base = base[: len(base) - (nivel - 1)]
    if modulo:
        base = base + modulo.split(".")
    return ".".join(base)


def _docstrings(arbol: ast.AST) -> set[int]:
    ids: set[int] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            cuerpo = nodo.body
            if (
                cuerpo
                and isinstance(cuerpo[0], ast.Expr)
                and isinstance(cuerpo[0].value, ast.Constant)
                and isinstance(cuerpo[0].value.value, str)
            ):
                ids.add(id(cuerpo[0].value))
    return ids


def _texto(nodo: ast.AST | None) -> str | None:
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
        return nodo.value
    return None


def _importaciones(arbol: ast.AST, paquete_actual: str) -> list[tuple[str, int]]:
    """Lista (módulo importado, línea), resolviendo relativos y textos dinámicos."""
    encontrados: list[tuple[str, int]] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                encontrados.append((alias.name, nodo.lineno))
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level:
                base = _resolver_relativo(nodo.level, nodo.module, paquete_actual)
            else:
                base = nodo.module or ""
            encontrados.append((base, nodo.lineno))
            for alias in nodo.names:
                if alias.name != "*" and base:
                    encontrados.append((f"{base}.{alias.name}", nodo.lineno))
        elif isinstance(nodo, ast.Call):
            func = nodo.func
            nombre = (
                func.attr if isinstance(func, ast.Attribute)
                else func.id if isinstance(func, ast.Name) else None
            )
            if nombre in {"import_module", "__import__"} and nodo.args:
                destino = _texto(nodo.args[0])
                if destino is None:
                    continue
                if destino.startswith("."):
                    paquete = _texto(nodo.args[1]) if len(nodo.args) > 1 else None
                    for kw in nodo.keywords:
                        if kw.arg == "package":
                            paquete = _texto(kw.value)
                    nivel = len(destino) - len(destino.lstrip("."))
                    destino = _resolver_relativo(
                        nivel, destino.lstrip(".") or None, paquete or paquete_actual
                    )
                encontrados.append((destino, nodo.lineno))
    return encontrados


def _es_sql(texto: str) -> bool:
    return any(p.search(texto) for p in _PATRONES_SQL)


def archivos_a_revisar(raiz: Path) -> list[tuple[Path, Path]]:
    """Pares (archivo, carpeta desde la que se importa su paquete)."""
    archivos: list[tuple[Path, Path]] = []
    for carpeta, paquete in FUENTES.items():
        base = raiz / carpeta
        archivos.extend((ruta, base) for ruta in sorted((base / paquete).rglob("*.py")))
    main = raiz / "frontend" / "main.py"
    if main.exists():
        archivos.append((main, main.parent))
    return archivos


def analizar_archivo(ruta: Path, raiz: Path, base: Path) -> list[Violacion]:
    rel = ruta.relative_to(raiz).as_posix()
    modulo, es_paquete = _modulo_de(ruta, base)
    paquete_actual = modulo if es_paquete else modulo.rpartition(".")[0]
    capa = _capa_de(modulo)
    arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=rel)
    violaciones: list[Violacion] = []

    if capa is None:
        violaciones.append(Violacion(rel, 1, "sin-capa", f"{modulo} no pertenece a ninguna capa"))

    for destino, linea in _importaciones(arbol, paquete_actual):
        raiz_mod = destino.split(".")[0]
        if raiz_mod in (PAQUETE, PAQUETE_UI) and destino != PAQUETE and capa not in (None, RAIZ):
            capa_destino = _capa_de(destino)
            if capa_destino in (RAIZ, None):
                violaciones.append(
                    Violacion(rel, linea, "capas", f"{capa} no puede importar {destino}")
                )
            elif capa_destino != capa and capa_destino not in CAPAS_PERMITIDAS[capa]:
                violaciones.append(
                    Violacion(rel, linea, "capas", f"{capa} no puede importar {capa_destino} ({destino})")
                )
        if raiz_mod == "sqlite3" and capa != "datos":
            violaciones.append(Violacion(rel, linea, "sqlite3", f"importa {destino} fuera de datos/"))
        if raiz_mod in MODULOS_RED and capa != "adaptadores":
            violaciones.append(Violacion(rel, linea, "red", f"importa {destino} fuera de adaptadores/"))

    if capa != "datos":
        docstrings = _docstrings(arbol)
        for nodo in ast.walk(arbol):
            if (
                isinstance(nodo, ast.Call)
                and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr in METODOS_SQL
            ):
                violaciones.append(
                    Violacion(rel, nodo.lineno, "sql-llamada", f".{nodo.func.attr}() fuera de datos/")
                )
            elif (
                isinstance(nodo, ast.Constant)
                and isinstance(nodo.value, str)
                and id(nodo) not in docstrings
                and _es_sql(nodo.value)
            ):
                violaciones.append(
                    Violacion(rel, nodo.lineno, "sql-texto", f"texto SQL fuera de datos/: {nodo.value[:40]!r}")
                )
    return violaciones


def analizar(raiz: Path) -> list[Violacion]:
    violaciones: list[Violacion] = []
    for archivo, base in archivos_a_revisar(raiz):
        violaciones.extend(analizar_archivo(archivo, raiz, base))
    return violaciones


def test_paquete_real_respeta_la_arquitectura():
    violaciones = analizar(RAIZ_REPO)
    assert not violaciones, "Violaciones de arquitectura:\n" + "\n".join(map(str, violaciones))


ATAJOS: list[tuple[str, str, str]] = [
    ("backend/clinican/dominio/a1.py", "from clinican.datos import repo", "capas"),
    ("backend/clinican/dominio/a2.py", "from ..servicios import algo", "capas"),
    ("backend/clinican/dominio/a3.py", "import interfaz", "capas"),
    ("backend/clinican/dominio/a4.py", "import importlib\nimportlib.import_module('clinican.adaptadores')", "capas"),
    ("backend/clinican/dominio/a5.py", "__import__('clinican.servicios')", "capas"),
    ("backend/clinican/dominio/a6.py", "from importlib import import_module\nimport_module('.datos', 'clinican')", "capas"),
    ("backend/clinican/datos/a7.py", "import clinican.servicios.casos", "capas"),
    ("backend/clinican/servicios/a8.py", "from interfaz import pantalla", "capas"),
    ("backend/clinican/adaptadores/a9.py", "from clinican.datos import repo", "capas"),
    ("frontend/interfaz/a10.py", "from clinican.datos.conexion import abrir", "capas"),
    ("frontend/interfaz/a11.py", "from clinican import adaptadores", "capas"),
    ("backend/clinican/servicios/a12.py", "from clinican import demo", "capas"),
    ("backend/clinican/servicios/b1.py", "import sqlite3", "sqlite3"),
    ("backend/clinican/servicios/b2.py", "from sqlite3 import connect", "sqlite3"),
    ("backend/clinican/servicios/b3.py", "import importlib\nimportlib.import_module('sqlite3')", "sqlite3"),
    ("frontend/interfaz/b4.py", "__import__('sqlite3')", "sqlite3"),
    ("frontend/main.py", "import sqlite3", "sqlite3"),
    ("frontend/interfaz/c1.py", "def f(con):\n    con.execute('x')", "sql-llamada"),
    ("frontend/interfaz/c2.py", "def f(cur):\n    cur.executemany('x', [])", "sql-llamada"),
    ("frontend/interfaz/c3.py", "def f(con):\n    con.executescript('x')", "sql-llamada"),
    ("backend/clinican/servicios/c4.py", "def f(con, otra):\n    con.backup(otra)", "sql-llamada"),
    ("backend/clinican/servicios/d1.py", "Q = 'SELECT nombre FROM pacientes'", "sql-texto"),
    ("backend/clinican/servicios/d2.py", "Q = 'insert into pacientes values (1)'", "sql-texto"),
    ("backend/clinican/servicios/d3.py", "Q = 'UPDATE pacientes SET nombre = 1'", "sql-texto"),
    ("backend/clinican/servicios/d4.py", "Q = 'DELETE FROM pacientes'", "sql-texto"),
    ("backend/clinican/servicios/d5.py", "Q = 'CREATE TABLE t (a)'", "sql-texto"),
    ("backend/clinican/servicios/d6.py", "Q = 'DROP INDEX i'", "sql-texto"),
    ("backend/clinican/servicios/d7.py", "Q = 'ALTER TABLE t ADD b'", "sql-texto"),
    ("backend/clinican/servicios/d8.py", "Q = 'PRAGMA foreign_keys'", "sql-texto"),
    ("backend/clinican/servicios/d9.py", "Q = 'BEGIN IMMEDIATE'", "sql-texto"),
    ("backend/clinican/servicios/d10.py", "Q = 'COMMIT'", "sql-texto"),
    ("backend/clinican/servicios/d11.py", "Q = 'ROLLBACK'", "sql-texto"),
    ("backend/clinican/servicios/d12.py", "def f(t):\n    return f'SELECT * FROM {t}'", "sql-texto"),
    ("backend/clinican/dominio/d13.py", "def f():\n    x = 1\n    'DELETE FROM t'", "sql-texto"),
    *[
        (f"backend/clinican/servicios/e_{m}.py", f"import {m}", "red")
        for m in sorted(MODULOS_RED)
    ],
    ("frontend/interfaz/e_urllib_req.py", "from urllib.request import urlopen", "red"),
    ("frontend/interfaz/e_http_client.py", "import http.client", "red"),
    ("frontend/interfaz/e_xmlrpc.py", "from xmlrpc import client", "red"),
    ("backend/clinican/dominio/e_dinamico.py", "import importlib\nimportlib.import_module('socket')", "red"),
    ("backend/clinican/datos/e_datos.py", "import requests", "red"),
]

LIMPIOS: list[tuple[str, str]] = [
    ("backend/clinican/__init__.py", '"""Paquete."""'),
    ("backend/clinican/demo.py", "from clinican import datos, servicios, adaptadores"),
    ("backend/clinican/dominio/__init__.py", '"""SELECT * FROM docstring no cuenta."""'),
    ("backend/clinican/datos/__init__.py", ""),
    ("backend/clinican/servicios/__init__.py", ""),
    ("backend/clinican/adaptadores/__init__.py", ""),
    ("frontend/interfaz/__init__.py", ""),
    (
        "backend/clinican/datos/ok.py",
        "import sqlite3\nfrom clinican.dominio import x\n"
        "def f(con):\n    con.execute('SELECT 1 FROM t')",
    ),
    ("backend/clinican/adaptadores/ok.py", "import urllib.request\nfrom clinican.servicios import s"),
    (
        "backend/clinican/servicios/ok.py",
        '"""Docstring con DELETE FROM t."""\nfrom clinican.datos import repo\n'
        "from . import otro\nfrom ..dominio import modelo\n"
        "def f():\n    \"\"\"UPDATE x SET y.\"\"\"\n    return 'Seleccione un paciente de la lista'",
    ),
    ("frontend/interfaz/ok.py", "from clinican.servicios import s\nfrom clinican.dominio import d\nfrom . import otro"),
]


def _plantar(raiz: Path, archivos) -> None:
    for rel, codigo in archivos:
        ruta = raiz / rel
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(textwrap.dedent(codigo) + "\n", encoding="utf-8")


def test_detecta_todos_los_atajos(tmp_path):
    _plantar(tmp_path, LIMPIOS)
    _plantar(tmp_path, [(rel, codigo) for rel, codigo, _ in ATAJOS])

    violaciones = analizar(tmp_path)
    por_archivo: dict[str, set[str]] = {}
    for v in violaciones:
        por_archivo.setdefault(v.archivo, set()).add(v.regla)

    no_detectados = [
        f"{rel} (esperaba {regla})"
        for rel, _, regla in ATAJOS
        if regla not in por_archivo.get(rel, set())
    ]
    assert not no_detectados, "Atajos no detectados:\n" + "\n".join(no_detectados)

    falsos_positivos = [str(v) for v in violaciones if v.archivo in {r for r, _ in LIMPIOS}]
    assert not falsos_positivos, "Falsos positivos:\n" + "\n".join(falsos_positivos)


def test_modulo_sin_capa_se_detecta(tmp_path):
    _plantar(tmp_path, [("backend/clinican/__init__.py", ""), ("backend/clinican/suelto.py", "x = 1")])
    reglas = {v.regla for v in analizar(tmp_path)}
    assert "sin-capa" in reglas
