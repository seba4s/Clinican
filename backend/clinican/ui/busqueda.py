"""Búsqueda de clientes por nombre, cédula, celular o nombre de mascota."""

from __future__ import annotations

import re

from clinican.dominio.entidades import Propietario
from clinican.servicios import clientes


def buscar_clientes(con, texto: str, limite: int = 50) -> list[Propietario]:
    texto = (texto or "").strip()
    digitos = re.sub(r"[\s.\-]", "", texto)
    clave = digitos if digitos.isdigit() else texto
    vistos: dict[int, Propietario] = {}
    for p in clientes.buscar_propietarios(con, clave):
        vistos.setdefault(p.id, p)
    if texto and not digitos.isdigit():
        for m in clientes.buscar_mascotas(con, texto):
            if m.propietario_id not in vistos:
                try:
                    p = clientes.obtener_propietario(con, m.propietario_id)
                except Exception:
                    continue
                if p.activo:
                    vistos[p.id] = p
    return sorted(vistos.values(), key=lambda p: p.nombre.lower())[:limite]
