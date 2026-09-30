"""Esquema, migraciones y semillas."""

import sqlite3

import pytest

from clinican.datos import migraciones, semillas
from clinican.datos.conexion import conectar


def test_version_y_llaves_foraneas(conn):
    assert migraciones.version(conn) == migraciones.VERSION_ACTUAL
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_semillas_cargadas(conn):
    assert conn.execute("SELECT COUNT(*) FROM razas").fetchone()[0] == 14  # 13 de perro + gato
    # 12 franjas por día, lunes a sábado
    assert conn.execute("SELECT COUNT(*) FROM franjas_base").fetchone()[0] == 72
    assert conn.execute("SELECT COUNT(*) FROM franjas_base WHERE dia_semana = 6").fetchone()[0] == 12
    tipos = {f[0] for f in conn.execute("SELECT tipo FROM textos_legales WHERE version = 1 AND vigente = 1")}
    assert tipos == {"TERMINOS", "DATOS", "RESPONSABILIDAD"}
    config = dict(conn.execute("SELECT clave, valor FROM config").fetchall())
    for clave, valor in semillas.CONFIG_INICIAL.items():
        assert config[clave] == valor


def test_husky_y_mestizo(conn):
    husky = conn.execute("SELECT * FROM razas WHERE nombre = 'Husky'").fetchone()
    assert husky["tamano"] == "GRANDE" and husky["pelaje_complicado"] == 1
    mestizo = conn.execute("SELECT * FROM razas WHERE nombre LIKE 'Perro mestizo%'").fetchone()
    assert mestizo["tamano"] is None and mestizo["especie"] == "PERRO"
    gato = conn.execute("SELECT * FROM razas WHERE especie = 'GATO'").fetchone()
    assert gato["nombre"] == "Gato (sin raza definida)" and gato["tamano"] is None


def test_migrar_dos_veces_no_duplica(tmp_path):
    ruta = tmp_path / "prueba.db"
    c1 = conectar(ruta)
    c1.execute("UPDATE config SET valor = '99999' WHERE clave = 'abono_minimo'")
    c1.commit()
    c1.close()
    c2 = conectar(ruta)
    assert c2.execute("SELECT COUNT(*) FROM razas").fetchone()[0] == 14
    # Volver a abrir no pisa lo que editó la administradora
    assert c2.execute("SELECT valor FROM config WHERE clave = 'abono_minimo'").fetchone()[0] == "99999"
    c2.close()


def test_llave_foranea_activa(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO mascotas (propietario_id, nombre, raza_id) VALUES (999, 'Toby', 1)"
        )


def test_base_mas_nueva_se_rechaza(tmp_path):
    ruta = tmp_path / "nueva.db"
    c = sqlite3.connect(ruta)
    c.execute(f"PRAGMA user_version = {migraciones.VERSION_ACTUAL + 1}")
    c.close()
    with pytest.raises(RuntimeError):
        conectar(ruta)


def test_base_de_fase_1_se_actualiza(tmp_path):
    """Una base creada con la versión 1 recibe la migración 2 sin perder datos."""
    ruta = tmp_path / "v1.db"
    c = sqlite3.connect(ruta)
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("BEGIN")
    migraciones._v1(c)
    c.execute("PRAGMA user_version = 1")
    c.commit()
    c.execute("INSERT INTO personal (nombre, cargo, rol, pin_hash, pin_sal) VALUES ('Angela','Jefe','ADMIN','x','y')")
    c.commit()
    c.close()
    c2 = conectar(ruta)
    assert migraciones.version(c2) == migraciones.VERSION_ACTUAL
    columnas = [f["name"] for f in c2.execute("PRAGMA table_info(consentimientos)")]
    assert "texto_mostrado" in columnas
    assert c2.execute("SELECT nombre FROM personal").fetchone()[0] == "Angela"
    c2.close()


def test_migracion_3_conserva_abonos(tmp_path):
    """Los abonos existentes sobreviven a la reconstrucción de la tabla (estados nuevos)."""
    ruta = tmp_path / "v2.db"
    c = sqlite3.connect(ruta)
    c.execute("PRAGMA foreign_keys = ON")
    c.create_function("sin_tildes", 1, lambda x: x, deterministic=True)
    c.execute("BEGIN")
    migraciones._v1(c)
    migraciones._v2(c)
    c.execute("PRAGMA user_version = 2")
    c.commit()
    c.execute("INSERT INTO personal (id, nombre, cargo, rol, pin_hash, pin_sal) VALUES (1,'A','Jefe','ADMIN','x','y')")
    c.execute("INSERT INTO propietarios (id, nombre, cedula, celular1, direccion) VALUES (1,'M','123456','3001234567','C')")
    c.execute("INSERT INTO mascotas (id, propietario_id, nombre, raza_id) VALUES (1,1,'Toby',1)")
    c.execute("INSERT INTO turnos (id, fecha, hora, mascota_id, categoria_cupo, agendado_por) "
              "VALUES (1,'2026-10-05','09:00',1,'MAQUINA',1)")
    c.execute("INSERT INTO abonos (turno_id, monto, medio, registrado_por, estado) VALUES (1, 20000, 'NEQUI', 1, 'PERDIDO')")
    c.commit()
    c.close()
    c2 = conectar(ruta)
    assert migraciones.version(c2) == migraciones.VERSION_ACTUAL
    fila = c2.execute("SELECT monto, estado FROM abonos").fetchone()
    assert tuple(fila) == (20000, "PERDIDO")
    c2.execute("UPDATE abonos SET estado = 'DEVUELTO'")  # el estado nuevo ya es válido
    assert c2.execute("SELECT valor FROM config WHERE clave='horas_minimas_devolucion'").fetchone()[0] == "12"
    c2.close()


def test_migracion_5_cambia_el_borrador_de_terminos(tmp_path):
    """Una base con el borrador inicial recibe los términos reales como versión nueva."""
    ruta = tmp_path / "v4.db"
    c = sqlite3.connect(ruta)
    c.execute("PRAGMA foreign_keys = ON")
    c.create_function("sin_tildes", 1, lambda x: x, deterministic=True)
    c.execute("BEGIN")
    for n in (1, 2, 3, 4):
        migraciones.MIGRACIONES[n](c)
    c.execute("PRAGMA user_version = 4")
    c.execute("INSERT INTO textos_legales (tipo, version, contenido) VALUES ('TERMINOS', 1, ?)",
              (semillas.TERMINOS_BORRADOR,))
    c.commit()
    c.close()
    c2 = conectar(ruta)
    filas = c2.execute("SELECT version, vigente, contenido FROM textos_legales WHERE tipo='TERMINOS' ORDER BY version").fetchall()
    assert [(f["version"], f["vigente"]) for f in filas] == [(1, 0), (2, 1)]
    assert filas[1]["contenido"] == semillas.TERMINOS_CLINICAN
    c2.close()


def test_migracion_5_respeta_terminos_editados(tmp_path):
    ruta = tmp_path / "v4b.db"
    c = sqlite3.connect(ruta)
    c.execute("PRAGMA foreign_keys = ON")
    c.create_function("sin_tildes", 1, lambda x: x, deterministic=True)
    c.execute("BEGIN")
    for n in (1, 2, 3, 4):
        migraciones.MIGRACIONES[n](c)
    c.execute("PRAGMA user_version = 4")
    c.execute("INSERT INTO textos_legales (tipo, version, contenido) VALUES ('TERMINOS', 3, 'Texto propio de la jefe')")
    c.commit()
    c.close()
    c2 = conectar(ruta)
    assert c2.execute("SELECT version, contenido FROM textos_legales WHERE tipo='TERMINOS' AND vigente=1").fetchone()[:] == (
        3, "Texto propio de la jefe")
    c2.close()


def test_base_nueva_usa_los_terminos_reales(conn):
    contenido = conn.execute("SELECT contenido FROM textos_legales WHERE tipo='TERMINOS' AND vigente=1").fetchone()[0]
    assert contenido.startswith("AUTORIZACIÓN PARA REALIZAR PROCEDIMIENTOS DE ESTÉTICA")
    assert "No se aceptan reclamos después de las 24 horas" in contenido
