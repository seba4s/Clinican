import sqlite3

import pytest

from clinican.datos.conexion import abrir
from clinican.datos.migraciones import MIGRACIONES, migrar, version_actual

TABLAS = {
    "configuracion", "propietarios", "razas", "mascotas", "turnos", "bloqueos", "auditoria",
}


def _nombres(con, tipo):
    return {f[0] for f in con.execute("SELECT name FROM sqlite_master WHERE type = ?", (tipo,))}


def test_tablas_e_indices(con):
    assert version_actual(con) == len(MIGRACIONES) == 7
    assert TABLAS <= _nombres(con, "table")
    assert {"usuarios", "roles", "permisos"}.isdisjoint(_nombres(con, "table"))
    assert {"ix_turnos_inicio_estado", "ix_turnos_propietario"} <= _nombres(con, "index")


def test_subir_desde_version_1_conserva_configuracion(tmp_path):
    c = abrir(tmp_path / "vieja.db")
    try:
        migrar(c, MIGRACIONES[:1])
        c.execute("INSERT INTO configuracion VALUES ('abono', '15000')")
        assert migrar(c) == 7
        assert c.execute("SELECT valor FROM configuracion").fetchall() == [("15000",)]
    finally:
        c.close()


def _propietario(con, saldo=0):
    return con.execute(
        "INSERT INTO propietarios (nombre, saldo_a_favor) VALUES ('Ana', ?)", (saldo,)
    ).lastrowid


def _mascota(con, pid):
    return con.execute(
        "INSERT INTO mascotas (propietario_id, nombre, tamano) VALUES (?, 'Toby', 'mediano')", (pid,)
    ).lastrowid


def _turno(con, **cambios):
    pid = _propietario(con)
    valores = dict(
        mascota_id=_mascota(con, pid), propietario_id=pid, inicio="2026-11-09T09:00",
        servicio="bano", categoria="maquina", estado="pendiente_abono",
        motivo_liberacion=None, abono_requerido=20000, abono_pagado=0, creado_en="x",
    )
    valores.update(cambios)
    columnas = ", ".join(valores)
    marcas = ", ".join("?" for _ in valores)
    con.execute(f"INSERT INTO turnos ({columnas}) VALUES ({marcas})", tuple(valores.values()))


@pytest.mark.parametrize("saldo", [-1, 1.5, "cien"])
def test_saldo_a_favor_entero_no_negativo(con, saldo):
    with pytest.raises(sqlite3.IntegrityError):
        _propietario(con, saldo)


def test_nombre_obligatorio(con):
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO propietarios (nombre) VALUES ('   ')")


def test_claves_foraneas(con):
    with pytest.raises(sqlite3.IntegrityError):
        _mascota(con, 999)


@pytest.mark.parametrize(
    "cambios",
    [
        {"estado": "inventado"},
        {"categoria": "mediana"},
        {"estado": "liberado"},  # sin motivo
        {"motivo_liberacion": "abono_vencido"},  # con motivo sin estar liberado
        {"estado": "liberado", "motivo_liberacion": "porque_si"},
        {"abono_pagado": 30000},  # más que el abono requerido
        {"abono_requerido": 20000.5},
    ],
)
def test_checks_de_turnos(con, cambios):
    with pytest.raises(sqlite3.IntegrityError):
        _turno(con, **cambios)


def test_turno_valido_se_inserta(con):
    _turno(con)
    _turno(con, estado="liberado", motivo_liberacion="abono_vencido")
    assert con.execute("SELECT COUNT(*) FROM turnos").fetchone()[0] == 2


def test_raza_unica_sin_importar_mayusculas(con):
    con.execute("INSERT INTO razas (nombre) VALUES ('Poodle')")
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO razas (nombre) VALUES ('POODLE')")


@pytest.mark.parametrize(
    "inicio, fin", [("10:00", None), (None, "10:00"), ("11:00", "10:00")]
)
def test_checks_de_bloqueos(con, inicio, fin):
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO bloqueos (fecha, hora_inicio, hora_fin) VALUES ('2026-11-09', ?, ?)",
            (inicio, fin),
        )


def test_auditoria_exige_json(con):
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO auditoria (cuando, accion, entidad, detalle) VALUES ('x', 'a', 'b', 'no json')"
        )
