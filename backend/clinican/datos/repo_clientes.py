"""Repositorio de propietarios, razas y mascotas."""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from clinican.datos._util import actualizar
from clinican.dominio.cupos import Tamano
from clinican.dominio.entidades import Mascota, Propietario, Raza

# --------------------------------------------------------------------------- propietarios

_PROP = "id, nombre, telefono, saldo_a_favor, activo, fusionado_en, cedula, direccion, celular2"


def _propietario(f) -> Propietario:
    return Propietario(f[0], f[1], f[2], f[3], bool(f[4]), f[5], f[6], f[7], f[8])


def insertar_propietario(
    con: sqlite3.Connection,
    nombre: str,
    telefono: str,
    cedula: str | None = None,
    direccion: str = "",
    celular2: str | None = None,
) -> int:
    cur = con.execute(
        "INSERT INTO propietarios (nombre, telefono, cedula, direccion, celular2) VALUES (?, ?, ?, ?, ?)",
        (nombre, telefono, cedula, direccion, celular2),
    )
    return cur.lastrowid


def obtener_propietario_por_cedula(con: sqlite3.Connection, cedula: str) -> Propietario | None:
    f = con.execute(f"SELECT {_PROP} FROM propietarios WHERE cedula = ?", (cedula,)).fetchone()
    return None if f is None else _propietario(f)


def obtener_propietario(con: sqlite3.Connection, id_: int) -> Propietario | None:
    f = con.execute(f"SELECT {_PROP} FROM propietarios WHERE id = ?", (id_,)).fetchone()
    return None if f is None else _propietario(f)


def actualizar_propietario(con: sqlite3.Connection, id_: int, **campos: Any) -> None:
    if "activo" in campos:
        campos["activo"] = int(campos["activo"])
    actualizar(
        con, "propietarios", id_, campos,
        {"nombre", "telefono", "saldo_a_favor", "activo", "fusionado_en", "cedula", "direccion",
         "celular2"},
    )


def sumar_saldo(con: sqlite3.Connection, id_: int, delta: int) -> None:
    con.execute(
        "UPDATE propietarios SET saldo_a_favor = saldo_a_favor + ? WHERE id = ?", (delta, id_)
    )


def buscar_propietarios(
    con: sqlite3.Connection, texto: str = "", incluir_inactivos: bool = False
) -> list[Propietario]:
    filas = con.execute(
        f"SELECT {_PROP} FROM propietarios "
        "WHERE (instr(lower(nombre), lower(?)) > 0 OR instr(telefono, ?) > 0 "
        "OR instr(coalesce(cedula, ''), upper(?)) > 0) "
        "AND (? OR activo = 1) ORDER BY nombre, id",
        (texto, texto, texto, int(incluir_inactivos)),
    ).fetchall()
    return [_propietario(f) for f in filas]


# --------------------------------------------------------------------------- razas

_RAZA = "id, nombre, tamano, pelaje, activo"


def _raza(f) -> Raza:
    return Raza(f[0], f[1], None if f[2] is None else Tamano(f[2]), f[3], bool(f[4]))


def insertar_raza(con: sqlite3.Connection, nombre: str, tamano: Tamano | None, pelaje: str) -> int:
    cur = con.execute(
        "INSERT INTO razas (nombre, tamano, pelaje) VALUES (?, ?, ?)",
        (nombre, None if tamano is None else tamano.value, pelaje),
    )
    return cur.lastrowid


def obtener_raza(con: sqlite3.Connection, id_: int) -> Raza | None:
    f = con.execute(f"SELECT {_RAZA} FROM razas WHERE id = ?", (id_,)).fetchone()
    return None if f is None else _raza(f)


def obtener_raza_por_nombre(con: sqlite3.Connection, nombre: str) -> Raza | None:
    f = con.execute(f"SELECT {_RAZA} FROM razas WHERE nombre = ?", (nombre,)).fetchone()
    return None if f is None else _raza(f)


def actualizar_raza(con: sqlite3.Connection, id_: int, **campos: Any) -> None:
    if isinstance(campos.get("tamano"), Tamano):
        campos["tamano"] = campos["tamano"].value
    if "activo" in campos:
        campos["activo"] = int(campos["activo"])
    actualizar(con, "razas", id_, campos, {"nombre", "tamano", "pelaje", "activo"})


def buscar_razas(
    con: sqlite3.Connection, texto: str = "", incluir_inactivas: bool = False
) -> list[Raza]:
    filas = con.execute(
        f"SELECT {_RAZA} FROM razas WHERE instr(lower(nombre), lower(?)) > 0 "
        "AND (? OR activo = 1) ORDER BY nombre",
        (texto, int(incluir_inactivas)),
    ).fetchall()
    return [_raza(f) for f in filas]


# --------------------------------------------------------------------------- mascotas

_MASC = (
    "id, propietario_id, nombre, raza_id, tamano, pelaje, complicado, activo, fecha_nacimiento, "
    "ultima_visita, observaciones"
)


def _fecha(texto: str | None) -> date | None:
    return None if texto is None else date.fromisoformat(texto)


def _mascota(f) -> Mascota:
    return Mascota(
        f[0], f[1], f[2], f[3], Tamano(f[4]), f[5], bool(f[6]), bool(f[7]),
        _fecha(f[8]), _fecha(f[9]), f[10],
    )


def insertar_mascota(
    con: sqlite3.Connection,
    propietario_id: int,
    nombre: str,
    raza_id: int | None,
    tamano: Tamano,
    pelaje: str,
    complicado: bool,
    fecha_nacimiento: date | None = None,
    ultima_visita: date | None = None,
    observaciones: str = "",
) -> int:
    cur = con.execute(
        "INSERT INTO mascotas (propietario_id, nombre, raza_id, tamano, pelaje, complicado, "
        "fecha_nacimiento, ultima_visita, observaciones) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            propietario_id, nombre, raza_id, tamano.value, pelaje, int(complicado),
            None if fecha_nacimiento is None else fecha_nacimiento.isoformat(),
            None if ultima_visita is None else ultima_visita.isoformat(),
            observaciones,
        ),
    )
    return cur.lastrowid


def obtener_mascota(con: sqlite3.Connection, id_: int) -> Mascota | None:
    f = con.execute(f"SELECT {_MASC} FROM mascotas WHERE id = ?", (id_,)).fetchone()
    return None if f is None else _mascota(f)


def actualizar_mascota(con: sqlite3.Connection, id_: int, **campos: Any) -> None:
    if isinstance(campos.get("tamano"), Tamano):
        campos["tamano"] = campos["tamano"].value
    for booleano in ("complicado", "activo"):
        if booleano in campos:
            campos[booleano] = int(campos[booleano])
    for fecha in ("fecha_nacimiento", "ultima_visita"):
        if isinstance(campos.get(fecha), date):
            campos[fecha] = campos[fecha].isoformat()
    actualizar(
        con, "mascotas", id_, campos,
        {"nombre", "raza_id", "tamano", "pelaje", "complicado", "activo", "fecha_nacimiento",
         "ultima_visita", "observaciones"},
    )


def buscar_mascotas(
    con: sqlite3.Connection,
    texto: str = "",
    propietario_id: int | None = None,
    incluir_inactivas: bool = False,
) -> list[Mascota]:
    filas = con.execute(
        f"SELECT {_MASC} FROM mascotas WHERE instr(lower(nombre), lower(?)) > 0 "
        "AND (? IS NULL OR propietario_id = ?) AND (? OR activo = 1) ORDER BY nombre, id",
        (texto, propietario_id, propietario_id, int(incluir_inactivas)),
    ).fetchall()
    return [_mascota(f) for f in filas]


def mover_mascotas(con: sqlite3.Connection, origen: int, destino: int) -> int:
    cur = con.execute(
        "UPDATE mascotas SET propietario_id = ? WHERE propietario_id = ?", (destino, origen)
    )
    return cur.rowcount
