import pytest

from clinican.datos import repo_clientes
from clinican.dominio.cupos import CategoriaCupo, Servicio, Tamano
from clinican.dominio.errores import DatoInvalido, NoEncontrado, OperacionNoPermitida
from clinican.servicios import agenda, clientes
from clinican.servicios.auditoria import historial
from conftest import AHORA, a_las, timedelta


# --------------------------------------------------------------------------- propietarios


def test_crear_editar_buscar_desactivar_propietario(con):
    p = clientes.crear_propietario(con, "  Ana Gómez ", "3001234567", ahora=AHORA)
    assert (p.nombre, p.telefono, p.saldo_a_favor, p.activo) == ("Ana Gómez", "3001234567", 0, True)

    p = clientes.editar_propietario(con, p.id, nombre="Ana María Gómez", ahora=AHORA)
    assert p.nombre == "Ana María Gómez" and p.telefono == "3001234567"

    clientes.crear_propietario(con, "Beto", "3109999999", ahora=AHORA)
    assert [x.nombre for x in clientes.buscar_propietarios(con, "maría")] == ["Ana María Gómez"]
    assert [x.nombre for x in clientes.buscar_propietarios(con, "310")] == ["Beto"]
    assert len(clientes.buscar_propietarios(con)) == 2

    clientes.desactivar_propietario(con, p.id, ahora=AHORA)
    assert [x.nombre for x in clientes.buscar_propietarios(con)] == ["Beto"]
    assert len(clientes.buscar_propietarios(con, incluir_inactivos=True)) == 2

    acciones = [r.accion for r in historial(con, "propietario", p.id)]
    assert acciones == ["crear", "editar", "desactivar"]


@pytest.mark.parametrize("nombre", ["", "   ", None])
def test_nombre_de_propietario_obligatorio(con, nombre):
    with pytest.raises(DatoInvalido):
        clientes.crear_propietario(con, nombre, "3001234567", ahora=AHORA)
    assert historial(con) == []


@pytest.mark.parametrize(
    "entrada, guardado",
    [("3001234567", "3001234567"), ("300 123 4567", "3001234567"), ("300-123-45-67", "3001234567")],
)
def test_celular_se_guarda_con_10_digitos(con, entrada, guardado):
    p = clientes.crear_propietario(con, "Ana", entrada, ahora=AHORA)
    assert p.telefono == guardado
    p = clientes.editar_propietario(con, p.id, telefono="310 999 9999", ahora=AHORA)
    assert p.telefono == "3109999999"


@pytest.mark.parametrize(
    "telefono", ["", "300123456", "30012345678", "+57 3001234567", "300.123.4567", "300abc4567", None]
)
def test_celular_invalido(con, telefono):
    with pytest.raises(DatoInvalido, match="10 dígitos|texto"):
        clientes.crear_propietario(con, "Ana", telefono, ahora=AHORA)
    p = clientes.crear_propietario(con, "Ana", "3001234567", ahora=AHORA)
    with pytest.raises(DatoInvalido):
        clientes.editar_propietario(con, p.id, telefono=telefono, ahora=AHORA)
    assert clientes.obtener_propietario(con, p.id).telefono == "3001234567"


def test_buscar_por_celular(con):
    a = clientes.crear_propietario(con, "Ana", "3001234567", ahora=AHORA)
    clientes.crear_propietario(con, "Beto", "3001234568", ahora=AHORA)
    assert [p.id for p in clientes.buscar_por_celular(con, "300 123 4567")] == [a.id]
    assert len(clientes.buscar_propietarios(con, "300 123")) == 2


def test_propietario_inexistente(con):
    with pytest.raises(NoEncontrado):
        clientes.editar_propietario(con, 99, nombre="X", ahora=AHORA)


# --------------------------------------------------------------------------- razas


def test_razas(con):
    poodle = clientes.crear_raza(con, "Poodle", Tamano.PEQUENO, "rizado", ahora=AHORA)
    assert (poodle.tamano, poodle.pelaje) == (Tamano.PEQUENO, "rizado")
    with pytest.raises(DatoInvalido, match="Ya existe"):
        clientes.crear_raza(con, "POODLE", ahora=AHORA)
    labrador = clientes.crear_raza(con, "Labrador", Tamano.GRANDE, ahora=AHORA)
    with pytest.raises(DatoInvalido):
        clientes.editar_raza(con, labrador.id, nombre="poodle", ahora=AHORA)
    labrador = clientes.editar_raza(con, labrador.id, pelaje="corto", ahora=AHORA)
    assert labrador.pelaje == "corto" and labrador.tamano is Tamano.GRANDE
    clientes.desactivar_raza(con, poodle.id, ahora=AHORA)
    assert [r.nombre for r in clientes.buscar_razas(con)] == ["Labrador"]
    with pytest.raises(DatoInvalido):
        clientes.crear_raza(con, "Pug", "pequeño", ahora=AHORA)


# --------------------------------------------------------------------------- mascotas


def test_mascota_toma_tamano_y_pelaje_de_la_raza(con, esc):
    dueno = esc.propietario()
    raza = clientes.crear_raza(con, "Golden", Tamano.GRANDE, "largo", ahora=AHORA)
    m = clientes.crear_mascota(con, dueno.id, "Max", raza_id=raza.id, ahora=AHORA)
    assert (m.tamano, m.pelaje, m.complicado) == (Tamano.GRANDE, "largo", False)
    otra = clientes.crear_mascota(
        con, dueno.id, "Luna", raza_id=raza.id, tamano=Tamano.MEDIANO, pelaje="corto",
        complicado=True, ahora=AHORA,
    )
    assert (otra.tamano, otra.pelaje, otra.complicado) == (Tamano.MEDIANO, "corto", True)


def test_mascota_sin_tamano_posible(con, esc):
    dueno = esc.propietario()
    mestizo = clientes.crear_raza(con, "Mestizo", ahora=AHORA)
    with pytest.raises(DatoInvalido, match="tamaño"):
        clientes.crear_mascota(con, dueno.id, "Toby", raza_id=mestizo.id, ahora=AHORA)
    with pytest.raises(DatoInvalido, match="tamaño"):
        clientes.crear_mascota(con, dueno.id, "Toby", ahora=AHORA)


def test_mascota_de_propietario_inactivo(con, esc):
    dueno = esc.propietario()
    clientes.desactivar_propietario(con, dueno.id, ahora=AHORA)
    with pytest.raises(OperacionNoPermitida):
        clientes.crear_mascota(con, dueno.id, "Toby", tamano=Tamano.MINI, ahora=AHORA)


def test_editar_buscar_desactivar_mascota(con, esc):
    dueno = esc.propietario()
    m = clientes.crear_mascota(con, dueno.id, "Toby", tamano=Tamano.MINI, ahora=AHORA)
    clientes.crear_mascota(con, esc.propietario().id, "Tobías", tamano=Tamano.MINI, ahora=AHORA)
    m = clientes.editar_mascota(con, m.id, complicado=True, tamano=Tamano.MEDIANO, ahora=AHORA)
    assert m.complicado and m.tamano is Tamano.MEDIANO
    assert len(clientes.buscar_mascotas(con, "tob")) == 2
    assert [x.nombre for x in clientes.buscar_mascotas(con, propietario_id=dueno.id)] == ["Toby"]
    clientes.desactivar_mascota(con, m.id, ahora=AHORA)
    assert [x.nombre for x in clientes.buscar_mascotas(con, "tob")] == ["Tobías"]
    with pytest.raises(DatoInvalido):
        clientes.editar_mascota(con, m.id, tamano=None, ahora=AHORA)
    with pytest.raises(NoEncontrado):
        clientes.editar_mascota(con, m.id, raza_id=999, ahora=AHORA)


# --------------------------------------------------------------------------- unir propietarios


def test_unir_propietarios(con, esc):
    origen = esc.propietario("Ana (duplicada)", saldo=5000)
    destino = esc.propietario("Ana", saldo=1000)
    turno = esc.turno(propietario=origen)  # usa los 5000 de saldo de origen
    esc.mascota(propietario=origen)
    # Una inasistencia avisada a tiempo en el historial del origen
    t2 = esc.turno(inicio=a_las(10), propietario=origen)
    agenda.registrar_abono(con, t2.id, t2.faltante, ahora=AHORA)
    agenda.marcar_inasistencia(con, t2.id, aviso_en=a_las(10) - timedelta(hours=13),
                               ahora=a_las(11))
    saldo_origen = clientes.obtener_propietario(con, origen.id).saldo_a_favor
    assert saldo_origen == 20000

    resultado = clientes.unir_propietarios(con, origen.id, destino.id, ahora=a_las(12))

    assert resultado.saldo_a_favor == 1000 + saldo_origen
    viejo = clientes.obtener_propietario(con, origen.id)
    assert (viejo.activo, viejo.fusionado_en, viejo.saldo_a_favor) == (False, destino.id, 0)
    assert clientes.buscar_mascotas(con, propietario_id=origen.id, incluir_inactivas=True) == []
    assert len(clientes.buscar_mascotas(con, propietario_id=destino.id)) == 3
    assert agenda.obtener_turno(con, turno.id).propietario_id == destino.id
    assert [t.id for t in agenda.inasistencias_de_propietario(con, destino.id)] == [t2.id]
    registro = historial(con, "propietario", destino.id)[-1]
    assert registro.accion == "unir"
    assert registro.detalle["origen_id"] == origen.id
    assert registro.detalle["mascotas_movidas"] == 3
    assert registro.detalle["saldo_trasladado"] == saldo_origen


def test_unir_rechazos_no_cambian_nada(con, esc):
    a = esc.propietario(saldo=3000)
    b = esc.propietario()
    esc.mascota(propietario=a)
    with pytest.raises(OperacionNoPermitida):
        clientes.unir_propietarios(con, a.id, a.id, ahora=AHORA)
    clientes.desactivar_propietario(con, b.id, ahora=AHORA)
    with pytest.raises(OperacionNoPermitida):
        clientes.unir_propietarios(con, a.id, b.id, ahora=AHORA)
    with pytest.raises(NoEncontrado):
        clientes.unir_propietarios(con, a.id, 999, ahora=AHORA)
    assert repo_clientes.obtener_propietario(con, a.id).saldo_a_favor == 3000
    assert len(clientes.buscar_mascotas(con, propietario_id=a.id)) == 1
    assert [r.accion for r in historial(con, "propietario")].count("unir") == 0


def test_no_se_puede_unir_un_propietario_ya_fusionado(con, esc):
    a, b, c = esc.propietario(), esc.propietario(), esc.propietario()
    clientes.unir_propietarios(con, a.id, b.id, ahora=AHORA)
    with pytest.raises(OperacionNoPermitida):
        clientes.unir_propietarios(con, a.id, c.id, ahora=AHORA)


def test_turno_de_mascota_inactiva_rechazado(con, esc):
    m = esc.mascota(CategoriaCupo.MAQUINA)
    clientes.desactivar_mascota(con, m.id, ahora=AHORA)
    with pytest.raises(OperacionNoPermitida):
        agenda.crear_turno(con, m.id, a_las(9), Servicio.CORTE_MAQUINA, ahora=AHORA)
    assert agenda.turnos_del_dia(con, a_las(9).date()) == []
