import ast
from pathlib import Path

DOMINIO = Path(__file__).resolve().parent.parent / "clinican" / "dominio"


def test_dominio_no_lee_el_reloj():
    """El reloj se inyecta: el dominio no llama now/today/utcnow/time()."""
    prohibidas = {"now", "today", "utcnow", "time", "monotonic", "perf_counter"}
    hallazgos = []
    for archivo in DOMINIO.rglob("*.py"):
        for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
            if (
                isinstance(nodo, ast.Call)
                and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr in prohibidas
            ):
                hallazgos.append(f"{archivo.name}:{nodo.lineno} .{nodo.func.attr}()")
    assert not hallazgos, hallazgos


def test_no_hay_pin_ni_login():
    """Un solo perfil sin PIN: el programa abre directo."""
    assert not (DOMINIO / "seguridad.py").exists()
    for archivo in DOMINIO.rglob("*.py"):
        texto = archivo.read_text(encoding="utf-8")
        assert "pbkdf2" not in texto and "hash_pin" not in texto, archivo.name
