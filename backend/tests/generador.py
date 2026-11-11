"""Generador de datos sintéticos (por defecto, cinco años de operación).

Inserta directamente con SQL (rápido) sobre una base ya migrada, respetando
los cupos por franja, los estados y los CHECKs del esquema. Uso:

    python tests/generador.py ruta.db [años]
"""

from __future__ import annotations

import json
import random
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clinican.datos.conexion import abrir  # noqa: E402
from clinican.datos.migraciones import migrar  # noqa: E402
from clinican.dominio.agenda import ZONA  # noqa: E402

CAPACIDAD = {"maquina": 2, "grande": 1, "tijera": 1, "complicado": 1}
PRECIO = {"maquina": 45000, "grande": 70000, "tijera": 50000, "complicado": 50000}
SERVICIO = {"maquina": "corte_maquina", "grande": "bano", "tijera": "corte_tijera", "complicado": "desenredado"}
TAMANO = {"maquina": "mediano", "grande": "grande", "tijera": "pequeno", "complicado": "mediano"}


@dataclass
class Resumen:
    propietarios: int = 0
    mascotas: int = 0
    turnos: int = 0
    fichas: int = 0
    notificaciones: int = 0
    auditoria: int = 0
    desde: date | None = None
    hasta: date | None = None


def _iso(momento: datetime) -> str:
    return momento.astimezone(ZONA).isoformat(timespec="microseconds")


def generar(
    ruta: str | Path,
    anios: int = 5,
    hasta: date = date(2026, 11, 7),
    turnos_por_dia: int = 30,
    propietarios: int = 3000,
    semilla: int = 7,
) -> Resumen:
    azar = random.Random(semilla)
    con = abrir(ruta)
    migrar(con)
    con.close()
    con = sqlite3.connect(str(ruta), isolation_level=None)
    con.execute("PRAGMA foreign_keys=ON")
    resumen = Resumen(desde=hasta - timedelta(days=365 * anios), hasta=hasta)
    con.execute("BEGIN")
    try:
        con.executemany(
            "INSERT INTO propietarios (id, nombre, telefono) VALUES (?, ?, ?)",
            [(i, f"Propietario {i}", f"3{i:09d}") for i in range(1, propietarios + 1)],
        )
        mascotas_por_categoria: dict[str, list[tuple[int, int]]] = {c: [] for c in CAPACIDAD}
        filas_mascotas = []
        mid = 0
        for pid in range(1, propietarios + 1):
            for _ in range(azar.choice((1, 1, 2))):
                mid += 1
                categoria = azar.choices(list(CAPACIDAD), weights=(6, 2, 2, 1))[0]
                filas_mascotas.append(
                    (mid, pid, f"Mascota {mid}", TAMANO[categoria], int(categoria == "complicado"))
                )
                mascotas_por_categoria[categoria].append((mid, pid))
        con.executemany(
            "INSERT INTO mascotas (id, propietario_id, nombre, tamano, complicado) VALUES (?, ?, ?, ?, ?)",
            filas_mascotas,
        )
        resumen.propietarios, resumen.mascotas = propietarios, mid

        turnos, fichas, notifs, auditoria = [], [], [], []
        tid = 0
        dia = resumen.desde
        while dia <= hasta:
            if dia.weekday() != 6:
                ranuras = []
                for i in range(16):
                    inicio = datetime.combine(dia, time(9, 0), tzinfo=ZONA) + timedelta(minutes=30 * i)
                    for categoria, capacidad in CAPACIDAD.items():
                        ranuras.extend([(inicio, categoria)] * capacidad)
                for inicio, categoria in azar.sample(ranuras, min(turnos_por_dia, len(ranuras))):
                    tid += 1
                    mascota_id, propietario_id = azar.choice(mascotas_por_categoria[categoria])
                    creado = inicio - timedelta(days=azar.randint(1, 10), minutes=azar.randint(0, 600))
                    estado = azar.choices(
                        ("entregado", "cancelado", "inasistencia", "liberado"), weights=(88, 5, 3, 4)
                    )[0]
                    pagado = 0 if estado == "liberado" else 20000
                    turnos.append((
                        tid, mascota_id, propietario_id, _iso(inicio), SERVICIO[categoria], categoria,
                        estado, "abono_vencido" if estado == "liberado" else None, 20000, pagado,
                        _iso(creado), None if estado == "liberado" else _iso(creado + timedelta(minutes=10)),
                    ))
                    auditoria.append((_iso(creado), "crear", "turno", tid, json.dumps({"categoria": categoria})))
                    if estado == "entregado":
                        fichas.append((tid, "Servicio completo", "", PRECIO[categoria], "",
                                       _iso(inicio + timedelta(hours=2))))
                    if estado != "liberado":
                        envio = inicio - timedelta(hours=24)
                        notifs.append((tid, "recordatorio", _iso(envio), "enviada", 1, _iso(creado),
                                       _iso(envio), _iso(envio)))
            dia += timedelta(days=1)
        con.executemany(
            "INSERT INTO turnos (id, mascota_id, propietario_id, inicio, servicio, categoria, estado, "
            "motivo_liberacion, abono_requerido, abono_pagado, creado_en, abonado_en) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            turnos,
        )
        con.executemany(
            "INSERT INTO fichas (turno_id, servicios_realizados, detalles_corte, precio_final, "
            "observaciones, creada_en) VALUES (?, ?, ?, ?, ?, ?)",
            fichas,
        )
        con.executemany(
            "INSERT INTO notificaciones_salida (turno_id, tipo, programada_para, estado, intentos, "
            "creada_en, enviada_en, cerrada_en) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            notifs,
        )
        con.executemany(
            "INSERT INTO auditoria (cuando, accion, entidad, entidad_id, detalle) VALUES (?, ?, ?, ?, ?)",
            auditoria,
        )
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    resumen.turnos, resumen.fichas = len(turnos), len(fichas)
    resumen.notificaciones, resumen.auditoria = len(notifs), len(auditoria)
    return resumen


if __name__ == "__main__":
    destino = Path(sys.argv[1])
    print(generar(destino, int(sys.argv[2]) if len(sys.argv) > 2 else 5))
