import sqlite3

import pytest

from clinican.datos.conexion import TransaccionAnidada, abrir, transaccion


@pytest.fixture
def ruta(tmp_path):
    return tmp_path / "clinica.db"


@pytest.fixture
def con(ruta):
    c = abrir(ruta)
    c.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    yield c
    c.close()


def test_modo_wal(con):
    assert con.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"


def test_claves_foraneas_activas(con):
    assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    con.execute("CREATE TABLE hija (id INTEGER PRIMARY KEY, t_id INTEGER REFERENCES t(id))")
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO hija (t_id) VALUES (999)")


def test_busy_timeout(ruta):
    c = abrir(ruta, busy_timeout_ms=1234)
    try:
        assert c.execute("PRAGMA busy_timeout").fetchone()[0] == 1234
    finally:
        c.close()


def test_modo_autocommit(con):
    assert con.isolation_level is None
    assert not con.in_transaction


def test_commit(con, ruta):
    with transaccion(con):
        con.execute("INSERT INTO t (v) VALUES ('a')")
    assert not con.in_transaction
    otra = abrir(ruta)
    try:
        assert otra.execute("SELECT v FROM t").fetchall() == [("a",)]
    finally:
        otra.close()


def test_rollback_ante_excepcion(con):
    with pytest.raises(ValueError):
        with transaccion(con):
            con.execute("INSERT INTO t (v) VALUES ('a')")
            raise ValueError("fallo")
    assert not con.in_transaction
    assert con.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0


def test_transaccion_anidada_rechazada(con):
    with transaccion(con):
        con.execute("INSERT INTO t (v) VALUES ('a')")
        with pytest.raises(TransaccionAnidada):
            with transaccion(con):
                pass
    # La transacción externa sigue y confirma normalmente
    assert con.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1


def test_begin_immediate_bloquea_otra_escritura(con, ruta):
    otra = abrir(ruta, busy_timeout_ms=50)
    try:
        with transaccion(con):
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                with transaccion(otra):
                    pass
            assert not otra.in_transaction
        # Liberado el bloqueo, la segunda conexión puede escribir
        with transaccion(otra):
            otra.execute("INSERT INTO t (v) VALUES ('b')")
    finally:
        otra.close()
