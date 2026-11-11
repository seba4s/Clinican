"""Prueba de humo de la interfaz: abre cada pantalla y recorre los diálogos principales.

La ventana queda oculta (withdraw). Se omite si no hay pantalla disponible.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

ctk = pytest.importorskip("customtkinter")

from clinican.datos.conexion import abrir  # noqa: E402
from clinican.dominio.cupos import CategoriaCupo as C  # noqa: E402
from clinican.dominio.estados import EstadoTurno as E  # noqa: E402
from clinican.servicios import agenda, clientes, fichas  # noqa: E402
from conftest import AHORA, a_las  # noqa: E402

AHORA_UI = a_las(9, 40)


@pytest.fixture
def app(ruta_db, con, esc):
    from clinican.ui.app import App
    from clinican.ui.contexto import Contexto

    # Datos: un pendiente, un confirmado, uno en atención y un grande atendido.
    pendiente = esc.turno(inicio=a_las(11), ahora=a_las(9, 30))
    confirmado = agenda.registrar_abono(con, esc.turno(inicio=a_las(10)).id, 20000, ahora=AHORA)
    en_atencion = agenda.registrar_abono(con, esc.turno(inicio=a_las(9)).id, 20000, ahora=AHORA)
    agenda.iniciar_atencion(con, en_atencion.id, ahora=AHORA)
    grande = agenda.registrar_abono(con, esc.turno(C.GRANDE, inicio=a_las(9)).id, 20000, ahora=AHORA)
    agenda.iniciar_atencion(con, grande.id, ahora=AHORA)
    agenda.marcar_atendido(con, grande.id, ahora=AHORA)

    ctx = Contexto(abrir=lambda: abrir(ruta_db), ruta_db=ruta_db, reloj=lambda: AHORA_UI)
    try:
        ventana = App(ctx)
    except Exception as e:  # sin pantalla (servidor sin escritorio)
        pytest.skip(f"No hay pantalla para Tk: {e}")
    ventana.withdraw()
    ventana.ids = {"pendiente": pendiente.id, "confirmado": confirmado.id,
                   "en_atencion": en_atencion.id, "grande": grande.id}
    yield ventana
    ventana.destroy()


def test_todas_las_pantallas_abren(app):
    for nombre in app.SECCIONES:
        pantalla = app.ir(nombre)
        app.update_idletasks()
        assert pantalla.winfo_manager() == "pack"
    ajustes = app.pantallas["Ajustes"]
    from clinican.ui.pantalla_ajustes import SECCIONES

    for seccion in SECCIONES:
        ajustes.ir(seccion)
        app.update_idletasks()


def test_agenda_muestra_turnos_y_acciones_por_estado(app):
    ag = app.ir("Agenda")
    assert set(app.ids.values()) <= set(ag._turnos)
    esperadas = {
        "pendiente": "Registrar abono",
        "confirmado": "Iniciar atención",
        "en_atencion": "Marcar atendido y llenar ficha",
        "grande": "Entregar",
    }
    for clave, primera in esperadas.items():
        ag.seleccionar(app.ids[clave])
        turno = ag._turnos[app.ids[clave]].turno
        assert ag._acciones(turno, None)[0][0] == primera
    # Días anterior y siguiente no fallan (domingo cerrado incluido)
    for _ in range(7):
        ag.dia_siguiente()


def test_tablero_cuenta_libres_y_bloquea_pasadas(app, con):
    from clinican.ui.pantalla_agenda import armar_tablero

    filas, fuera, libres = armar_tablero(con, a_las(9).date(), AHORA_UI)
    assert len(filas) == 16
    assert filas[0].pasada and not filas[-1].pasada
    assert not fuera
    # 16 franjas x 5 puestos, menos las pasadas (9:00) y los turnos de las franjas futuras
    assert libres == 15 * 5 - 2


def test_nuevo_turno_desde_el_dialogo(app, con, esc):
    from clinican.ui.dialogos_turno import DialogoNuevoTurno

    p = esc.propietario(saldo=5000)
    m = esc.mascota(propietario=p)
    ag = app.ir("Agenda")
    d = DialogoNuevoTurno(ag, app.ctx, dia=a_las(9).date(), mascota_id=m.id)
    assert d.propietario.id == p.id and d._mascota().id == m.id
    d.selector.elegir(a_las(14))
    d.campo_abono.poner("$15.000")
    d._agendar()
    turno = d.resultado
    assert turno.inicio == a_las(14)
    assert turno.estado is E.CONFIRMADO  # 5.000 de saldo + 15.000 de abono
    assert not d.winfo_exists()


def test_abono_parcial_y_ficha(app, con):
    from clinican.ui.dialogo_ficha import DialogoFicha
    from clinican.ui.dialogos_turno import DialogoAbono

    ag = app.ir("Agenda")
    t = agenda.obtener_turno(con, app.ids["pendiente"])
    d = DialogoAbono(ag, app.ctx, t)
    d.campo.poner("10000")
    d._registrar()
    assert d.resultado.abono_pagado == 10000 and d.resultado.estado is E.PENDIENTE_ABONO

    f = DialogoFicha(ag, app.ctx, app.ids["en_atencion"])
    f.precio.poner("$50.000")
    f.porcentaje.poner("40")
    f.avance.poner("Lomo listo")
    f._guardar()
    assert agenda.obtener_turno(con, app.ids["en_atencion"]).estado is E.ATENDIDO
    ficha = fichas.ficha_de_turno(con, app.ids["en_atencion"])
    assert ficha.precio_final == 50000
    assert len(fichas.sesiones_de_mascota(con, agenda.obtener_turno(con, app.ids["en_atencion"]).mascota_id)) == 1


def test_mover_y_bloquear(app, con):
    from clinican.ui.dialogos_turno import DialogoBloqueo, DialogoMover

    ag = app.ir("Agenda")
    t = agenda.obtener_turno(con, app.ids["confirmado"])
    d = DialogoMover(ag, app.ctx, t)
    d.selector.elegir(a_las(15))
    d._mover()
    assert agenda.obtener_turno(con, t.id).inicio == a_las(15)

    b = DialogoBloqueo(ag, app.ctx, a_las(9).date())
    b.desde.set("12:00")
    b.hasta.set("13:00")
    b._bloquear()
    assert len(agenda.bloqueos_del_dia(con, a_las(9).date())) == 1
    from clinican.ui.pantalla_agenda import armar_tablero

    filas, _fuera, _libres = armar_tablero(con, a_las(9).date(), AHORA_UI)
    assert [f.bloqueo for f in filas if f.bloqueo] == ["Almuerzo", "Almuerzo"]


def test_cliente_nuevo_y_mascota(app, con):
    from clinican.ui.pantalla_clientes import DialogoCliente, DialogoMascota

    cl = app.ir("Clientes")
    d = DialogoCliente(cl, app.ctx, None, "3001234567")
    assert d.celular.valor() == "3001234567"
    d.nombre.poner("Ana Quintero")
    d.cedula.poner("1020")
    d._guardar()
    p = d.resultado
    assert p.telefono == "3001234567"

    corto = DialogoCliente(cl, app.ctx, None, "")
    corto.nombre.poner("X")
    corto.cedula.poner("1")
    corto.celular.poner("300")
    corto._guardar()
    assert corto.resultado is None and corto.winfo_exists()
    corto.destroy()

    m = DialogoMascota(cl, app.ctx, p.id)
    m.nombre.poner("Chispa")
    m.complicado.set(True)
    m._guardar()
    assert m.resultado.complicado
    cl.elegir(p.id)
    app.update_idletasks()


def test_formatos():
    from clinican.ui import formato as fmt

    assert fmt.pesos(45000) == "$45.000"
    assert fmt.leer_pesos("$15.000") == 15000 and fmt.leer_pesos("") == 0
    assert fmt.celular("3005551234") == "300 555 1234"
    assert fmt.dia_largo(a_las(9).date()) == "Lunes 9 de noviembre"
    assert fmt.dia_corto(a_las(9).date() + timedelta(days=1), a_las(9).date()) == "Mañana"
    assert fmt.minutos_restantes(a_las(10), a_las(9, 48)) == "vence en 12 min"
