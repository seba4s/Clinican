"""Conexión, transacciones BEGIN IMMEDIATE y migraciones numeradas."""

from __future__ import annotations

import sqlite3
import threading

import pytest

from clinican.datos.conexion import ErrorTransaccion, abrir, transaccion
from clinican.datos.migraciones import (
    MIGRACIONES, ErrorMigracion, Migracion, migrar, version_actual, version_esperada,
)


@pytest.fixture
def ruta(tmp_path):
    return tmp_path / "datos" / "clinican.db"


def test_abrir_en_archivo_usa_wal_y_llaves_foraneas(ruta):
    con = abrir(ruta)
    assert ruta.exists()
    assert con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_transaccion_confirma_y_deshace():
    con = abrir(":memory:")
    con.execute("CREATE TABLE t (x INTEGER)")
    with transaccion(con):
        con.execute("INSERT INTO t VALUES (1)")
    with pytest.raises(ValueError):
        with transaccion(con):
            con.execute("INSERT INTO t VALUES (2)")
            raise ValueError("falla a mitad del caso de uso")
    assert [r[0] for r in con.execute("SELECT x FROM t")] == [1]
    assert not con.in_transaction


def test_no_se_anidan_transacciones():
    con = abrir(":memory:")
    with transaccion(con):
        with pytest.raises(ErrorTransaccion):
            with transaccion(con):
                pass


def test_begin_immediate_bloquea_al_segundo_escritor(ruta):
    """El segundo hilo espera a que el primero termine: nunca escriben a la vez."""
    a = abrir(ruta)
    migrar(a)
    orden = []
    dentro = threading.Event()

    def segundo():
        b = abrir(ruta)
        dentro.wait()
        with transaccion(b):
            orden.append("b")

    hilo = threading.Thread(target=segundo)
    hilo.start()
    with transaccion(a):
        dentro.set()
        hilo.join(timeout=0.3)  # b no puede entrar todavía
        orden.append("a")
    hilo.join()
    assert orden == ["a", "b"]


def test_migrar_base_nueva_llega_a_la_ultima_version():
    con = abrir(":memory:")
    assert migrar(con) == [m.numero for m in MIGRACIONES]
    assert version_actual(con) == version_esperada()


def test_migrar_es_idempotente(ruta):
    con = abrir(ruta)
    migrar(con)
    assert migrar(con) == []
    con.close()
    assert migrar(abrir(ruta)) == []


def test_migracion_nueva_conserva_los_datos():
    v1 = (Migracion(1, "t", "CREATE TABLE perros (nombre TEXT);"),)
    v2 = v1 + (Migracion(2, "raza", "ALTER TABLE perros ADD COLUMN raza TEXT;"),)
    con = abrir(":memory:")
    migrar(con, v1)
    con.execute("INSERT INTO perros VALUES ('Lucas')")
    assert migrar(con, v2) == [2]
    assert tuple(con.execute("SELECT nombre, raza FROM perros").fetchone()) == ("Lucas", None)


def test_migracion_que_falla_no_deja_nada_a_medias():
    malas = (Migracion(1, "mala", "CREATE TABLE a (x INTEGER);\nINSERT INTO no_existe VALUES (1);"),)
    con = abrir(":memory:")
    with pytest.raises(sqlite3.OperationalError):
        migrar(con, malas)
    assert version_actual(con) == 0
    assert con.execute("SELECT count(*) FROM sqlite_master WHERE name = 'a'").fetchone()[0] == 0


def test_migraciones_con_huecos_se_rechazan():
    with pytest.raises(ErrorMigracion):
        migrar(abrir(":memory:"), (Migracion(1, "a", "SELECT 1;"), Migracion(3, "c", "SELECT 1;")))


def test_base_de_un_programa_mas_nuevo_se_rechaza():
    con = abrir(":memory:")
    con.execute(f"PRAGMA user_version = {version_esperada() + 1}")
    with pytest.raises(ErrorMigracion, match="más nueva"):
        migrar(con)


def test_migracion_con_trigger_de_varias_sentencias():
    ms = (Migracion(1, "trigger", """
        CREATE TABLE a (x INTEGER);
        CREATE TABLE log (x INTEGER);
        CREATE TRIGGER t AFTER INSERT ON a BEGIN
            INSERT INTO log VALUES (new.x);
        END;
    """),)
    con = abrir(":memory:")
    migrar(con, ms)
    con.execute("INSERT INTO a VALUES (7)")
    assert con.execute("SELECT x FROM log").fetchone()[0] == 7
