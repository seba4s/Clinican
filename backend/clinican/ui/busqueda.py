"""Búsqueda de clientes por nombre, cédula, celular o nombre de mascota.

Ignora mayúsculas y tildes ("jose" encuentra "José") y acepta varias palabras
en cualquier orden ("lopez sebastian" encuentra "Sebastián López").
"""

from __future__ import annotations

import re
import unicodedata

from clinican.dominio.entidades import Propietario
from clinican.servicios import clientes


def _plano(texto: str | None) -> str:
    descompuesto = unicodedata.normalize("NFD", texto or "")
    sin_tildes = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return sin_tildes.casefold()


def buscar_clientes(con, texto: str, limite: int = 50) -> list[Propietario]:
    texto = (texto or "").strip()
    digitos = re.sub(r"[\s.\-]", "", texto)
    if digitos and digitos.isdigit():
        encontrados = clientes.buscar_propietarios(con, digitos)
        return sorted(encontrados, key=lambda p: _plano(p.nombre))[:limite]

    propietarios = clientes.buscar_propietarios(con)
    palabras = _plano(texto).split()
    if palabras:
        mascotas: dict[int, list[str]] = {}
        for m in clientes.buscar_mascotas(con):
            mascotas.setdefault(m.propietario_id, []).append(_plano(m.nombre))
        filtrados = []
        for p in propietarios:
            pajar = " ".join(
                [_plano(p.nombre), _plano(p.cedula), _plano(p.telefono), *mascotas.get(p.id, [])]
            )
            if all(w in pajar for w in palabras):
                filtrados.append(p)
        propietarios = filtrados
    return sorted(propietarios, key=lambda p: _plano(p.nombre))[:limite]
