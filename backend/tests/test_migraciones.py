import pytest

from clinican.datos.conexion import abrir
from clinican.datos.migraciones import (
    MIGRACIONES,
    BaseMasNueva,
    Migracion,
    MigracionesInvalidas,
    migrar,
    version_actual,
)


@pytest.fixture
def con(tmp_path):
    c = abrir(tmp_path / "clinica.db")
    yield c
    c.close()


def _tablas(con):
    return {
        fila[0]
        for fila in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }


V2 = Migracion(2, "pacientes", "CREATE TABLE pacientes (id INTEGER PRIMARY KEY, nombre TEXT);")
V3 = Migracion(3, "columna extra", "ALTER TABLE pacientes ADD COLUMN telefono TEXT;")


def test_migracion_inicial_crea_configuracion(con):
    assert migrar(con) == len(MIGRACIONES) == 1
    assert "configuracion" in _tablas(con)
    con.execute("INSERT INTO configuracion (clave, valor) VALUES ('a', 'b')")


def test_idempotente(con):
    assert migrar(con) == 1
    con.execute("INSERT INTO configuracion VALUES ('clave', 'valor')")
    assert migrar(con) == 1
    assert migrar(con) == 1
    assert con.execute("SELECT valor FROM configuracion").fetchall() == [("valor",)]


def test_subir_version_conserva_datos(con):
    migrar(con, MIGRACIONES)
    con.execute("INSERT INTO configuracion VALUES ('clinica', 'Central')")
    assert migrar(con, (*MIGRACIONES, V2)) == 2
    con.execute("INSERT INTO pacientes (nombre) VALUES ('Ana')")
    assert migrar(con, (*MIGRACIONES, V2, V3)) == 3
    assert con.execute("SELECT valor FROM configuracion").fetchall() == [("Central",)]
    assert con.execute("SELECT nombre, telefono FROM pacientes").fetchall() == [("Ana", None)]


def test_fallo_a_mitad_deja_version_anterior_sin_tablas_parciales(con):
    migrar(con)
    rota = Migracion(
        2,
        "rota a mitad",
        """
        CREATE TABLE parcial (id INTEGER PRIMARY KEY);
        CREATE TABLE otra_parcial (id INTEGER PRIMARY KEY);
        ESTO NO ES SQL;
        """,
    )
    with pytest.raises(Exception):
        migrar(con, (*MIGRACIONES, rota))
    assert version_actual(con) == 1
    assert not con.in_transaction
    assert {"parcial", "otra_parcial"}.isdisjoint(_tablas(con))
    # Corregida la migración, se aplica normalmente
    assert migrar(con, (*MIGRACIONES, V2)) == 2


def test_fallo_en_varias_pendientes_conserva_las_ya_aplicadas(con):
    rota = Migracion(3, "rota", "CREATE TABLE x (id INTEGER); INSERT INTO no_existe VALUES (1);")
    with pytest.raises(Exception):
        migrar(con, (*MIGRACIONES, V2, rota))
    assert version_actual(con) == 2
    assert "pacientes" in _tablas(con)
    assert "x" not in _tablas(con)


def test_base_mas_nueva_rechazada(con):
    migrar(con, (*MIGRACIONES, V2))
    with pytest.raises(BaseMasNueva):
        migrar(con, MIGRACIONES)
    assert version_actual(con) == 2


@pytest.mark.parametrize(
    "versiones",
    [(1, 3), (2,), (1, 2, 2), (2, 1), (0, 1)],
)
def test_huecos_o_desorden_rechazados(con, versiones):
    migs = tuple(Migracion(v, f"m{v}", f"CREATE TABLE t{i} (a);") for i, v in enumerate(versiones))
    with pytest.raises(MigracionesInvalidas):
        migrar(con, migs)
    assert version_actual(con) == 0
    assert _tablas(con) == set()


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE configuracion;",
        "drop index i;",
        "DELETE FROM configuracion;",
        "CREATE TABLE a (x); delete from a;",
    ],
)
def test_drop_y_delete_rechazados(con, sql):
    migrar(con)
    with pytest.raises(MigracionesInvalidas):
        migrar(con, (*MIGRACIONES, Migracion(2, "destructiva", sql)))
    assert version_actual(con) == 1
    assert "configuracion" in _tablas(con)
