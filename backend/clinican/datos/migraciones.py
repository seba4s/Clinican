"""Migraciones de esquema numeradas y solo aditivas.

La versión aplicada se guarda en ``PRAGMA user_version``. Cada migración corre
en su propia transacción y fija ``user_version`` dentro de esa misma
transacción, de modo que un fallo a mitad deja la base en la versión anterior.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from clinican.datos.conexion import transaccion


class ErrorMigracion(RuntimeError):
    """Error general de migraciones."""


class BaseMasNueva(ErrorMigracion):
    """La base tiene una versión mayor que la última migración conocida."""


class MigracionesInvalidas(ErrorMigracion):
    """La lista de migraciones no cumple las reglas (numeración o contenido)."""


@dataclass(frozen=True)
class Migracion:
    version: int
    descripcion: str
    sql: str


MIGRACIONES: tuple[Migracion, ...] = (
    Migracion(
        version=1,
        descripcion="Tabla de configuración clave/valor",
        sql="""
        CREATE TABLE configuracion (
            clave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        );
        """,
    ),
    Migracion(
        version=2,
        descripcion="Propietarios",
        sql="""
        CREATE TABLE propietarios (
            id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL CHECK (length(trim(nombre)) > 0),
            telefono TEXT NOT NULL DEFAULT '',
            saldo_a_favor INTEGER NOT NULL DEFAULT 0
                CHECK (typeof(saldo_a_favor) = 'integer' AND saldo_a_favor >= 0),
            activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
            fusionado_en INTEGER REFERENCES propietarios(id),
            CHECK (fusionado_en IS NULL OR (fusionado_en <> id AND activo = 0))
        );
        CREATE INDEX ix_propietarios_nombre ON propietarios(nombre);
        CREATE INDEX ix_propietarios_telefono ON propietarios(telefono);
        """,
    ),
    Migracion(
        version=3,
        descripcion="Razas con tamaño y pelaje por defecto",
        sql="""
        CREATE TABLE razas (
            id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK (length(trim(nombre)) > 0),
            tamano TEXT,
            pelaje TEXT NOT NULL DEFAULT '',
            activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
        );
        """,
    ),
    Migracion(
        version=4,
        descripcion="Mascotas",
        sql="""
        CREATE TABLE mascotas (
            id INTEGER PRIMARY KEY,
            propietario_id INTEGER NOT NULL REFERENCES propietarios(id),
            nombre TEXT NOT NULL CHECK (length(trim(nombre)) > 0),
            raza_id INTEGER REFERENCES razas(id),
            tamano TEXT NOT NULL,
            pelaje TEXT NOT NULL DEFAULT '',
            complicado INTEGER NOT NULL DEFAULT 0 CHECK (complicado IN (0, 1)),
            activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
        );
        CREATE INDEX ix_mascotas_propietario ON mascotas(propietario_id);
        """,
    ),
    Migracion(
        version=5,
        descripcion="Turnos (incluye historial de inasistencias por propietario)",
        sql="""
        CREATE TABLE turnos (
            id INTEGER PRIMARY KEY,
            mascota_id INTEGER NOT NULL REFERENCES mascotas(id),
            propietario_id INTEGER NOT NULL REFERENCES propietarios(id),
            inicio TEXT NOT NULL,
            servicio TEXT NOT NULL,
            categoria TEXT NOT NULL
                CHECK (categoria IN ('maquina', 'grande', 'tijera', 'complicado')),
            estado TEXT NOT NULL CHECK (estado IN (
                'pendiente_abono', 'confirmado', 'en_atencion', 'atendido',
                'entregado', 'liberado', 'cancelado', 'inasistencia')),
            motivo_liberacion TEXT
                CHECK (motivo_liberacion IN ('abono_vencido', 'otro_pago_primero', 'otro')),
            abono_requerido INTEGER NOT NULL
                CHECK (typeof(abono_requerido) = 'integer' AND abono_requerido >= 0),
            abono_pagado INTEGER NOT NULL DEFAULT 0
                CHECK (typeof(abono_pagado) = 'integer' AND abono_pagado >= 0),
            saldo_aplicado INTEGER NOT NULL DEFAULT 0
                CHECK (typeof(saldo_aplicado) = 'integer' AND saldo_aplicado >= 0),
            saldo_generado INTEGER NOT NULL DEFAULT 0
                CHECK (typeof(saldo_generado) = 'integer' AND saldo_generado >= 0),
            creado_en TEXT NOT NULL,
            abonado_en TEXT,
            aviso_inasistencia_en TEXT,
            CHECK (abono_pagado + saldo_aplicado <= abono_requerido),
            CHECK ((estado = 'liberado') = (motivo_liberacion IS NOT NULL))
        );
        CREATE INDEX ix_turnos_inicio_estado ON turnos(inicio, estado);
        CREATE INDEX ix_turnos_propietario ON turnos(propietario_id);
        CREATE INDEX ix_turnos_mascota ON turnos(mascota_id);
        """,
    ),
    Migracion(
        version=6,
        descripcion="Bloqueos de agenda",
        sql="""
        CREATE TABLE bloqueos (
            id INTEGER PRIMARY KEY,
            fecha TEXT NOT NULL,
            hora_inicio TEXT,
            hora_fin TEXT,
            motivo TEXT NOT NULL DEFAULT '',
            activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
            CHECK ((hora_inicio IS NULL) = (hora_fin IS NULL)),
            CHECK (hora_inicio IS NULL OR hora_inicio < hora_fin)
        );
        CREATE INDEX ix_bloqueos_fecha ON bloqueos(fecha);
        """,
    ),
    Migracion(
        version=7,
        descripcion="Auditoría de escrituras",
        sql="""
        CREATE TABLE auditoria (
            id INTEGER PRIMARY KEY,
            cuando TEXT NOT NULL,
            accion TEXT NOT NULL,
            entidad TEXT NOT NULL,
            entidad_id INTEGER,
            detalle TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(detalle))
        );
        CREATE INDEX ix_auditoria_entidad ON auditoria(entidad, entidad_id);
        """,
    ),
)

_DESTRUCTIVO = re.compile(r"\b(DROP|DELETE)\b", re.IGNORECASE)
_COMENTARIOS = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)


def _sentencias(sql: str) -> list[str]:
    """Divide el SQL en sentencias completas (sin comentarios)."""
    limpio = _COMENTARIOS.sub(" ", sql)
    sentencias: list[str] = []
    actual = ""
    for linea in limpio.splitlines(keepends=True):
        actual += linea
        if sqlite3.complete_statement(actual):
            if actual.strip().strip(";").strip():
                sentencias.append(actual.strip())
            actual = ""
    if actual.strip():
        sentencias.append(actual.strip())
    return sentencias


def validar(migraciones) -> None:
    """Verifica numeración 1..n sin huecos y que solo agreguen esquema."""
    versiones = [m.version for m in migraciones]
    if versiones != list(range(1, len(versiones) + 1)):
        raise MigracionesInvalidas(
            f"Las migraciones deben numerarse 1..n sin huecos ni desorden: {versiones}"
        )
    for m in migraciones:
        if _DESTRUCTIVO.search(_COMENTARIOS.sub(" ", m.sql)):
            raise MigracionesInvalidas(
                f"La migración {m.version} contiene DROP o DELETE; solo se permite agregar"
            )


def version_actual(con: sqlite3.Connection) -> int:
    return con.execute("PRAGMA user_version").fetchone()[0]


def migrar(con: sqlite3.Connection, migraciones=MIGRACIONES) -> int:
    """Aplica las migraciones pendientes y devuelve la versión final."""
    migraciones = tuple(migraciones)
    validar(migraciones)
    ultima = len(migraciones)
    actual = version_actual(con)
    if actual > ultima:
        raise BaseMasNueva(
            f"La base está en la versión {actual} y esta aplicación solo conoce hasta la {ultima}"
        )
    for m in migraciones[actual:]:
        with transaccion(con):
            for sentencia in _sentencias(m.sql):
                con.execute(sentencia)
            con.execute(f"PRAGMA user_version={int(m.version)}")
    return version_actual(con)
