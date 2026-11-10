"""Prueba de arquitectura (ADR-001, táctica T7): las capas no tienen atajos.

Lee el código fuente (no lo ejecuta) y falla si un módulo importa una capa que el
diseño no le permite, o si la capa de servicios ejecuta SQL por su cuenta.

    dominio  ←  datos  ←  servicios  ←  ui
                             ↑
                        adaptadores          (main.py es la raíz de composición)

Las dependencias apuntan hacia el dominio. La única que salta una capa es ui → dominio
(catálogos y formatos), y está permitida de forma explícita.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1] / "clinican"

# capa -> capas de clinican que puede importar (además de sí misma)
PERMITIDAS = {
    "dominio": set(),
    "datos": {"dominio"},
    "servicios": {"datos", "dominio", "rutas"},
    "adaptadores": {"servicios", "dominio"},
    "ui": {"servicios", "dominio", "rutas"},
}
CAPAS = tuple(PERMITIDAS)
# Llamadas que solo puede hacer la capa de datos.
SQL = {"execute", "executemany", "executescript", "connect", "backup"}


def _modulos(capa: str):
    return sorted((RAIZ / capa).rglob("*.py"))


def _es_type_checking(nodo: ast.If) -> bool:
    prueba = nodo.test
    return (isinstance(prueba, ast.Name) and prueba.id == "TYPE_CHECKING") or (
        isinstance(prueba, ast.Attribute) and prueba.attr == "TYPE_CHECKING")


def _importaciones(ruta: Path):
    """(línea, módulo) de cada import, incluidos los que están dentro de funciones.
    Se ignoran los de ``if TYPE_CHECKING:`` (solo anotaciones, no se ejecutan)."""
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    ignorar = {id(n) for bloque in ast.walk(arbol) if isinstance(bloque, ast.If) and _es_type_checking(bloque)
               for n in ast.walk(bloque)}
    for nodo in ast.walk(arbol):
        if id(nodo) in ignorar:
            continue
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                yield nodo.lineno, alias.name
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
            yield nodo.lineno, nodo.module
            if nodo.module == "clinican":  # from clinican import rutas
                for alias in nodo.names:
                    yield nodo.lineno, f"clinican.{alias.name}"


def _capa_de(modulo: str) -> str | None:
    partes = modulo.split(".")
    return partes[1] if len(partes) > 1 and partes[0] == "clinican" else None


def violaciones_de_capas() -> list[str]:
    errores = []
    for capa in CAPAS:
        for ruta in _modulos(capa):
            for linea, modulo in _importaciones(ruta):
                destino = _capa_de(modulo)
                if destino is None or destino == capa:
                    continue
                if destino not in PERMITIDAS[capa]:
                    errores.append(f"{ruta.relative_to(RAIZ.parent)}:{linea} — {capa} → {destino} ({modulo})")
                if capa == "ui" and modulo == "sqlite3":
                    errores.append(f"{ruta.relative_to(RAIZ.parent)}:{linea} — la interfaz importa sqlite3")
    return errores


def sql_fuera_de_datos() -> list[str]:
    errores = []
    for capa in ("servicios", "ui", "adaptadores", "dominio"):
        for ruta in _modulos(capa):
            for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
                if (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)
                        and nodo.func.attr in SQL):
                    errores.append(f"{ruta.relative_to(RAIZ.parent)}:{nodo.lineno} — .{nodo.func.attr}() fuera de la capa de datos")
    return errores


def test_las_dependencias_apuntan_hacia_el_dominio():
    assert violaciones_de_capas() == []


def test_solo_la_capa_de_datos_ejecuta_sql():
    assert sql_fuera_de_datos() == []


def test_el_dominio_no_depende_de_nada_externo():
    """El dominio es Python puro: ni base de datos, ni interfaz, ni red."""
    prohibidos = {"sqlite3", "tkinter", "customtkinter", "urllib", "openpyxl", "PIL"}
    errores = [f"{r.relative_to(RAIZ.parent)}:{l} importa {m}" for r in _modulos("dominio")
               for l, m in _importaciones(r) if m.split(".")[0] in prohibidos]
    assert errores == []


@pytest.mark.parametrize("capa,codigo,esperado", [
    ("ui", "from clinican.datos import repo_turnos\n", "ui → datos"),
    ("ui", "def f():\n    from clinican.adaptadores import NotificadorArchivo\n", "ui → adaptadores"),
    ("servicios", "import clinican.ui.tema\n", "servicios → ui"),
    ("dominio", "from clinican.datos.conexion import transaccion\n", "dominio → datos"),
    ("adaptadores", "from clinican.datos import repo_config\n", "adaptadores → datos"),
])
def test_la_prueba_detecta_un_atajo(tmp_path, monkeypatch, capa, codigo, esperado):
    """La prueba de verdad atrapa los atajos: se planta uno y debe fallar."""
    raiz = tmp_path / "clinican"
    for c in CAPAS:
        (raiz / c).mkdir(parents=True)
    (raiz / capa / "atajo.py").write_text(codigo, encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "RAIZ", raiz)
    assert any(esperado in e for e in violaciones_de_capas())


def test_la_prueba_detecta_sql_en_servicios(tmp_path, monkeypatch):
    raiz = tmp_path / "clinican"
    for c in CAPAS:
        (raiz / c).mkdir(parents=True)
    (raiz / "servicios" / "atajo.py").write_text("def f(conn):\n    conn.execute('DELETE FROM turnos')\n",
                                                encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "RAIZ", raiz)
    assert sql_fuera_de_datos()


def test_la_demostracion_corre_de_punta_a_punta(capsys):
    """El esqueleto arranca con un comando (python -m clinican.demo) y recorre las capas."""
    from clinican import demo

    assert demo.main() == 0
    salida = capsys.readouterr().out
    assert "Atajos prohibidos encontrados: ninguno" in salida
    assert "OTRO_PAGO_PRIMERO" in salida and "Cupos libres GRANDE a las 10:00: 0" in salida
    assert "último error: no hay conexión a internet" in salida
    assert "Bandeja del turno 2: ENVIADO" in salida and "[sms simulado]" in salida and "Ley 1581" in salida
