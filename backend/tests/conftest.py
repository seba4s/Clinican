from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from clinican.datos import repo_clientes
from clinican.datos.conexion import abrir
from clinican.datos.migraciones import migrar
from clinican.dominio.agenda import ZONA
from clinican.dominio.cupos import CategoriaCupo, Servicio, Tamano
from clinican.servicios import agenda, clientes

LUNES = date(2026, 11, 9)
DOMINGO = date(2026, 11, 15)


def a_las(hora: int, minuto: int = 0, dia: date = LUNES) -> datetime:
    return datetime(dia.year, dia.month, dia.day, hora, minuto, tzinfo=ZONA)


AHORA = a_las(8)  # lunes 8:00, antes de abrir

# categoría -> (tamaño, complicado, servicio) que la produce
PERFIL = {
    CategoriaCupo.MAQUINA: (Tamano.MEDIANO, False, Servicio.CORTE_MAQUINA),
    CategoriaCupo.GRANDE: (Tamano.GRANDE, False, Servicio.BANO),
    CategoriaCupo.TIJERA: (Tamano.PEQUENO, False, Servicio.CORTE_TIJERA),
    CategoriaCupo.COMPLICADO: (Tamano.MEDIANO, True, Servicio.BANO),
}


class Escenario:
    def __init__(self, con):
        self.con = con
        self._n = 0

    def propietario(self, nombre: str | None = None, saldo: int = 0):
        self._n += 1
        p = clientes.crear_propietario(self.con, nombre or f"Cliente {self._n}", "3001234567", ahora=AHORA)
        if saldo:
            repo_clientes.sumar_saldo(self.con, p.id, saldo)
        return clientes.obtener_propietario(self.con, p.id)

    def mascota(self, categoria=CategoriaCupo.MAQUINA, propietario=None):
        propietario = propietario or self.propietario()
        tamano, complicado, _ = PERFIL[categoria]
        self._n += 1
        return clientes.crear_mascota(
            self.con, propietario.id, f"Perro {self._n}", ahora=AHORA,
            tamano=tamano, complicado=complicado,
        )

    def turno(self, categoria=CategoriaCupo.MAQUINA, inicio=None, ahora=AHORA, propietario=None):
        mascota = self.mascota(categoria, propietario)
        return agenda.crear_turno(
            self.con, mascota.id, inicio or a_las(9), PERFIL[categoria][2], ahora=ahora
        )


@pytest.fixture
def ruta_db(tmp_path):
    ruta = tmp_path / "clinica.db"
    c = abrir(ruta)
    migrar(c)
    c.close()
    return ruta


@pytest.fixture
def con(ruta_db):
    c = abrir(ruta_db)
    yield c
    c.close()


@pytest.fixture
def esc(con):
    return Escenario(con)


__all__ = ["AHORA", "DOMINGO", "LUNES", "PERFIL", "a_las", "timedelta"]
