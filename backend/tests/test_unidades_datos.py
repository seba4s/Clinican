"""Conversión de valores a texto de SQLite, lista blanca de columnas y verificación de copias."""

from datetime import date, datetime, time, timedelta, timezone

import pytest

from clinican.datos import respaldos as datos_respaldos
from clinican.datos._util import a_texto, actualizar, de_texto, fecha_a_texto, hora_a_texto
from clinican.dominio.agenda import ZONA


def test_a_texto_de_none_es_none():
    assert a_texto(None) is None
    assert de_texto(None) is None
    assert hora_a_texto(None) is None


def test_a_texto_exige_zona_horaria():
    with pytest.raises(ValueError, match="zona horaria"):
        a_texto(datetime(2026, 11, 9, 9, 0))


def test_a_texto_guarda_en_hora_de_bogota():
    utc = datetime(2026, 11, 9, 14, 0, tzinfo=timezone.utc)
    texto = a_texto(utc)
    assert texto == "2026-11-09T09:00:00.000000-05:00"
    assert de_texto(texto) == utc


def test_textos_de_fechas_se_ordenan_como_las_fechas():
    base = datetime(2026, 11, 9, 9, 0, tzinfo=ZONA)
    momentos = [base + timedelta(minutes=m) for m in (90, 0, 30, 600, 1)]
    assert sorted(a_texto(m) for m in momentos) == [a_texto(m) for m in sorted(momentos)]


def test_fecha_y_hora_a_texto():
    assert fecha_a_texto(date(2026, 1, 5)) == "2026-01-05"
    assert hora_a_texto(time(9, 0)) == "09:00"
    assert hora_a_texto(time(16, 30)) == "16:30"


@pytest.fixture
def tabla(con):
    con.execute("CREATE TABLE prueba (id INTEGER PRIMARY KEY, a TEXT, b INTEGER)")
    con.execute("INSERT INTO prueba (id, a, b) VALUES (1, 'x', 1)")
    return con


def test_actualizar_cambia_solo_las_columnas_dadas(tabla):
    actualizar(tabla, "prueba", 1, {"b": 7}, permitidos=("a", "b"))
    assert tabla.execute("SELECT a, b FROM prueba WHERE id = 1").fetchone() == ("x", 7)


def test_actualizar_sin_campos_no_hace_nada(tabla):
    actualizar(tabla, "prueba", 1, {}, permitidos=("a",))
    assert tabla.execute("SELECT a, b FROM prueba WHERE id = 1").fetchone() == ("x", 1)


def test_actualizar_rechaza_columnas_fuera_de_la_lista(tabla):
    with pytest.raises(ValueError, match="no permitidas"):
        actualizar(tabla, "prueba", 1, {"a": "y", "id": 9}, permitidos=("a",))
    assert tabla.execute("SELECT id, a FROM prueba").fetchall() == [(1, "x")]


def test_verificar_archivo_que_no_existe(tmp_path):
    with pytest.raises(datos_respaldos.RespaldoInvalido, match="No existe"):
        datos_respaldos.verificar(tmp_path / "nada.db")


def test_verificar_archivo_que_no_es_base(tmp_path):
    falso = tmp_path / "falso.db"
    falso.write_bytes(b"esto no es sqlite" * 100)
    with pytest.raises(datos_respaldos.RespaldoInvalido, match="no es una base"):
        datos_respaldos.verificar(falso)


def test_verificar_base_sana(ruta_db):
    datos_respaldos.verificar(ruta_db)
