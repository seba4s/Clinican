"""Fase 2: propietarios, mascotas, razas y búsqueda."""

import pytest

from clinican.dominio.errores import DatoInvalido, PermisoDenegado
from clinican.dominio.mascotas import pelaje_complicado_efectivo, tamano_efectivo
from clinican.servicios import propietarios as sp
from clinican.servicios import razas


def _raza(conn, nombre):
    return conn.execute("SELECT id FROM razas WHERE nombre = ?", (nombre,)).fetchone()[0]


@pytest.fixture
def dueno(conn, empleada):
    return sp.crear(conn, empleada, "María Pérez", "1.098.765.432", "301 234-5678", "", "Calle 10 # 5-20")


# ------------------------------------------------------------ propietarios

def test_crear_propietario_normaliza(conn, empleada, dueno):
    p = sp.obtener(conn, empleada, dueno)
    assert p["cedula"] == "1098765432"
    assert p["celular1"] == "3012345678"
    assert p["celular2"] is None
    assert p["requiere_nuevo_abono"] == 0


def test_cedula_unica(conn, empleada, dueno):
    with pytest.raises(DatoInvalido, match="Ya existe"):
        sp.crear(conn, empleada, "Otra", "1098765432", "3000000000", "", "Cra 1")


@pytest.mark.parametrize(
    "nombre,cedula,cel,direccion",
    [("", "123456", "3001234567", "Calle"), ("Ana", "", "3001234567", "Calle"),
     ("Ana", "123456", "", "Calle"), ("Ana", "123456", "30012", "Calle"),
     ("Ana", "123456", "3001234567", ""), ("Ana", "12#45", "3001234567", "Calle")],
)
def test_propietario_invalido(conn, empleada, nombre, cedula, cel, direccion):
    with pytest.raises(DatoInvalido):
        sp.crear(conn, empleada, nombre, cedula, cel, None, direccion)


def test_editar_propietario_auditado(conn, empleada, dueno):
    sp.editar(conn, empleada, dueno, "María Pérez", "1098765432", "3012345678", "3109998877", "Calle 11")
    p = sp.obtener(conn, empleada, dueno)
    assert p["celular2"] == "3109998877" and p["direccion"] == "Calle 11"
    detalle = conn.execute("SELECT detalle FROM auditoria WHERE accion='EDITAR_PROPIETARIO'").fetchone()[0]
    assert "direccion" in detalle


def test_marca_requiere_nuevo_abono(conn, empleada, dueno):
    sp.fijar_requiere_nuevo_abono(conn, empleada, dueno, True)
    assert sp.obtener(conn, empleada, dueno)["requiere_nuevo_abono"] == 1


def test_busqueda(conn, empleada, dueno):
    sp.crear_mascota(conn, empleada, dueno, "Tóby", _raza(conn, "Shih Tzu"))
    sp.crear(conn, empleada, "Ángela Núñez", "5555555", "3150000000", None, "Cra 2")
    assert [p["nombre"] for p in sp.buscar(conn, empleada, "angela nunez")] == ["Ángela Núñez"]
    assert [p["nombre"] for p in sp.buscar(conn, empleada, "98765")] == ["María Pérez"]
    assert [p["nombre"] for p in sp.buscar(conn, empleada, "301 234")] == ["María Pérez"]
    assert [p["nombre"] for p in sp.buscar(conn, empleada, "toby")] == ["María Pérez"]
    assert len(sp.buscar(conn, empleada, "")) == 2


# ---------------------------------------------------------------- mascotas

def test_mestizo_exige_tamano(conn, empleada, dueno):
    """Criterio de aceptación de la Fase 2."""
    mestizo = _raza(conn, "Perro mestizo (sin raza)")
    with pytest.raises(DatoInvalido, match="tamaño"):
        sp.crear_mascota(conn, empleada, dueno, "Firulais", mestizo, pelaje_manual=0)
    with pytest.raises(DatoInvalido, match="pelaje"):
        sp.crear_mascota(conn, empleada, dueno, "Firulais", mestizo, tamano_manual="MEDIANA")
    mid = sp.crear_mascota(conn, empleada, dueno, "Firulais", mestizo, tamano_manual="MEDIANA", pelaje_manual=0)
    assert sp.perfil(sp.mascota(conn, empleada, mid)) == {"tamano": "MEDIANA", "pelaje_complicado": False}


def test_raza_con_tamano_no_exige(conn, empleada, dueno):
    mid = sp.crear_mascota(conn, empleada, dueno, "Rocky", _raza(conn, "Labrador Retriever"))
    assert sp.perfil(sp.mascota(conn, empleada, mid)) == {"tamano": "GRANDE", "pelaje_complicado": False}


def test_husky_pelaje_complicado_y_marcas_manuales(conn, empleada, dueno):
    husky = sp.crear_mascota(conn, empleada, dueno, "Nieve", _raza(conn, "Husky"))
    assert sp.perfil(sp.mascota(conn, empleada, husky))["pelaje_complicado"] is True
    # Marcas propias prevalecen sobre la raza
    poodle = sp.crear_mascota(conn, empleada, dueno, "Coco", _raza(conn, "Poodle (Caniche) Toy y Miniatura"),
                              tamano_manual="MEDIANA", pelaje_manual=1)
    assert sp.perfil(sp.mascota(conn, empleada, poodle)) == {"tamano": "MEDIANA", "pelaje_complicado": True}


def test_reglas_efectivas():
    assert tamano_efectivo("PEQUENA", None) == "PEQUENA"
    assert tamano_efectivo("PEQUENA", "GRANDE") == "GRANDE"
    with pytest.raises(DatoInvalido):
        tamano_efectivo(None, None)
    assert pelaje_complicado_efectivo(1, None) is True
    assert pelaje_complicado_efectivo(1, 0) is False


def test_mascota_nombre_repetido_y_edad(conn, empleada, dueno):
    shih = _raza(conn, "Shih Tzu")
    sp.crear_mascota(conn, empleada, dueno, "Toby", shih)
    with pytest.raises(DatoInvalido):
        sp.crear_mascota(conn, empleada, dueno, "toby", shih)
    with pytest.raises(DatoInvalido):
        sp.crear_mascota(conn, empleada, dueno, "Luna", shih, edad_anios="3", edad_meses="14")
    with pytest.raises(DatoInvalido):
        sp.crear_mascota(conn, empleada, dueno, "Luna", shih, edad_anios="tres")
    mid = sp.crear_mascota(conn, empleada, dueno, "Luna", shih, edad_anios="3", edad_meses="6",
                           fecha_ultima_visita="15/02/2026")
    m = sp.mascota(conn, empleada, mid)
    assert (m["edad_anios"], m["edad_meses"], m["fecha_ultima_visita"]) == (3, 6, "2026-02-15")


def test_ultima_visita_editable(conn, empleada, dueno):
    """RN-14: se puede corregir a mano."""
    mid = sp.crear_mascota(conn, empleada, dueno, "Toby", _raza(conn, "Shih Tzu"))
    sp.corregir_ultima_visita(conn, empleada, mid, "2026-01-10")
    assert sp.mascota(conn, empleada, mid)["fecha_ultima_visita"] == "2026-01-10"
    sp.corregir_ultima_visita(conn, empleada, mid, "")
    assert sp.mascota(conn, empleada, mid)["fecha_ultima_visita"] is None
    with pytest.raises(DatoInvalido):
        sp.corregir_ultima_visita(conn, empleada, mid, "2026-13-40")
    with pytest.raises(DatoInvalido, match="futura"):
        sp.editar_mascota(conn, empleada, mid, "Toby", _raza(conn, "Shih Tzu"), fecha_ultima_visita="2999-01-01")


def test_desactivar_mascota(conn, empleada, dueno):
    mid = sp.crear_mascota(conn, empleada, dueno, "Toby", _raza(conn, "Shih Tzu"))
    sp.fijar_mascota_activa(conn, empleada, mid, False)
    assert sp.mascotas(conn, empleada, dueno, incluir_inactivas=False) == []
    assert len(sp.mascotas(conn, empleada, dueno)) == 1


# ------------------------------------------------------------------ razas

def test_admin_agrega_raza_complicada(conn, admin, empleada, dueno):
    rid = razas.crear(conn, admin, "Samoyedo", "GRANDE", True)
    mid = sp.crear_mascota(conn, empleada, dueno, "Copo", rid)
    assert sp.perfil(sp.mascota(conn, empleada, mid))["pelaje_complicado"] is True
    with pytest.raises(DatoInvalido):
        razas.crear(conn, admin, "samoyedo", "GRANDE", True)


def test_personal_no_edita_razas(conn, empleada):
    with pytest.raises(PermisoDenegado):
        razas.crear(conn, empleada, "Beagle", "MEDIANA", False)
    with pytest.raises(PermisoDenegado):
        razas.editar(conn, empleada, 1, "X", "PEQUENA", False)


def test_quitar_tamano_a_raza_con_mascotas(conn, admin, empleada, dueno):
    shih = _raza(conn, "Shih Tzu")
    sp.crear_mascota(conn, empleada, dueno, "Toby", shih)
    with pytest.raises(DatoInvalido, match="sin tamaño propio"):
        razas.editar(conn, admin, shih, "Shih Tzu", None, False)
    razas.editar(conn, admin, shih, "Shih Tzu", "MEDIANA", False)


def test_raza_inactiva_no_se_lista(conn, admin):
    shih = _raza(conn, "Shih Tzu")
    razas.editar(conn, admin, shih, "Shih Tzu", "PEQUENA", False, activa=False)
    assert "Shih Tzu" not in [r["nombre"] for r in razas.listar(conn)]
    assert "Shih Tzu" in [r["nombre"] for r in razas.listar(conn, solo_activas=False)]


# ------------------------------------------------- gatos y raza escrita a mano

def test_gato(conn, empleada, dueno):
    gato = _raza(conn, "Gato (sin raza definida)")
    with pytest.raises(DatoInvalido, match="tamaño"):
        sp.crear_mascota(conn, empleada, dueno, "Michi", gato, pelaje_manual=0)
    mid = sp.crear_mascota(conn, empleada, dueno, "Michi", gato, tamano_manual="PEQUENA", pelaje_manual=0)
    m = sp.mascota(conn, empleada, mid)
    assert m["especie"] == "GATO" and sp.perfil(m) == {"tamano": "PEQUENA", "pelaje_complicado": False}


def test_personal_escribe_una_raza_nueva(conn, empleada, dueno):
    mid = sp.crear_mascota(conn, empleada, dueno, "Rocky", raza_texto="  Beagle ", tamano_manual="MEDIANA",
                           pelaje_manual=0)
    m = sp.mascota(conn, empleada, mid)
    assert (m["raza_nombre"], m["raza_tamano"], m["especie"]) == ("Beagle", None, "PERRO")
    assert "Beagle" in [r["nombre"] for r in razas.listar(conn)]
    # Si ya existe (sin importar tildes ni mayúsculas) se usa la misma
    otro = sp.crear_mascota(conn, empleada, dueno, "Canela", raza_texto="beagle", tamano_manual="PEQUENA",
                            pelaje_manual=0)
    assert sp.mascota(conn, empleada, otro)["raza_id"] == m["raza_id"]
    gato = sp.crear_mascota(conn, empleada, dueno, "Garfield", raza_texto="Persa", especie="GATO",
                            tamano_manual="PEQUENA", pelaje_manual=1)
    assert sp.mascota(conn, empleada, gato)["especie"] == "GATO"


def test_raza_escrita_exige_tamano_y_no_queda_suelta(conn, empleada, dueno):
    with pytest.raises(DatoInvalido, match="tamaño"):
        sp.crear_mascota(conn, empleada, dueno, "Rocky", raza_texto="Beagle", pelaje_manual=0)
    assert conn.execute("SELECT COUNT(*) FROM razas WHERE nombre = 'Beagle'").fetchone()[0] == 0
    with pytest.raises(DatoInvalido, match="raza"):
        sp.crear_mascota(conn, empleada, dueno, "Rocky", raza_texto="   ")
