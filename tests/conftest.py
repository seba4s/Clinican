import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clinican.datos.conexion import conectar  # noqa: E402
from clinican.servicios import acceso, personal  # noqa: E402


@pytest.fixture
def conn():
    c = conectar(":memory:")
    yield c
    c.close()


@pytest.fixture
def admin(conn):
    return acceso.crear_administradora_inicial(conn, "Angela", "Jefe", "1234")


@pytest.fixture
def empleada(conn, admin):
    nuevo_id = personal.crear(conn, admin, "Laura", "Asistente de peluquería", "5678")
    return acceso.iniciar_sesion(conn, "Laura", "5678")
