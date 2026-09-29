"""Prueba de humo de la interfaz: construye cada pantalla sin mostrarla.

Verifica que no haya errores al dibujar y que el PERSONAL no vea el menú
de administración. Se omite si el equipo no tiene pantalla.
"""

import tkinter as tk
import traceback

import pytest

from clinican.servicios import personal


@pytest.fixture(scope="session")
def _ventana():
    """Una sola ventana raíz para todas las pruebas: crear y destruir varias
    raíces de Tk en el mismo proceso falla de forma intermitente en Windows."""
    from clinican.datos.conexion import conectar
    from clinican.ui.app import AplicacionClinican

    try:
        a = AplicacionClinican(conectar(":memory:"))
    except tk.TclError as e:
        pytest.skip(f"Sin pantalla disponible: {e}")
    a.withdraw()
    yield a
    a.destroy()


@pytest.fixture
def app(_ventana, conn):
    """La ventana compartida, conectada a la base de datos de esta prueba."""
    _ventana.conn = conn
    _ventana.sesion = None
    errores = []
    # Se imprime la traza completa para poder diagnosticar cualquier error de la interfaz.
    _ventana.report_callback_exception = lambda *args: (errores.append(args), traceback.print_exception(*args))
    _ventana.errores = errores
    _ventana.mostrar_acceso()
    _ventana.update()
    yield _ventana


def test_pantallas_fase2(app, conn, monkeypatch, admin):
    from clinican.servicios import legal
    from clinican.servicios import propietarios as sp
    from clinican.ui import dialogos

    mensajes = []
    monkeypatch.setattr(dialogos, "_mostrar", lambda padre, titulo, mensaje, *a, **k: mensajes.append((titulo, mensaje)) or True)

    pid = sp.crear(conn, admin, "María Pérez", "1098765432", "3012345678", None, "Calle 10")
    mestizo = conn.execute("SELECT id FROM razas WHERE tamano IS NULL").fetchone()[0]
    mid = sp.crear_mascota(conn, admin, pid, "Firulais", mestizo, tamano_manual="MEDIANA", pelaje_manual=0)
    legal.aceptar(conn, admin, pid, ["TERMINOS"])
    legal.registrar_responsabilidad(conn, admin, mid, {"cond_agresiva": True})

    app._entrar(admin)
    app.update()
    principal = app.vista
    assert "Propietarios" in principal.entradas and "Configuración" in principal.entradas
    principal.mostrar("Propietarios")
    app.update()
    pantalla = principal.pantalla_actual
    assert len(pantalla.tabla.get_children()) == 1
    pantalla.tabla.selection_set(str(pid))
    app.update()
    for pestana in ("Datos", "Mascotas", "Consentimientos"):
        pantalla.detalle.pestanas.set(pestana)
        app.update()
    pantalla._nuevo()
    app.update()

    principal.mostrar("Configuración")
    app.update()
    config = principal.pantalla_actual
    for pestana in ("Precios y valores", "Razas", "Textos legales"):
        config.pestanas.set(pestana)
        app.update()
    config.widgets["abono_minimo"][1].delete(0, "end")
    config.widgets["abono_minimo"][1].insert(0, "25.000")
    config._guardar_valores()
    assert conn.execute("SELECT valor FROM config WHERE clave='abono_minimo'").fetchone()[0] == "25000"
    assert mensajes[-1][0] == "Configuración guardada"
    assert app.errores == []


def test_ficha_de_servicio(app, conn, monkeypatch, admin, empleada):
    from clinican.servicios import fichas
    from clinican.servicios import propietarios as sp
    from clinican.ui import dialogos
    from clinican.ui.pantalla_ficha import PantallaFicha

    mensajes = []
    monkeypatch.setattr(dialogos, "_mostrar", lambda padre, titulo, mensaje, *a, **k: mensajes.append((titulo, mensaje)) or True)
    pid = sp.crear(conn, admin, "María Pérez", "1098765432", "3012345678", None, "Calle 10")
    raza = conn.execute("SELECT id FROM razas WHERE nombre='Shih Tzu'").fetchone()[0]
    mid = sp.crear_mascota(conn, admin, pid, "Toby", raza)

    app._entrar(empleada)
    app.update()
    ctx = app.vista.ctx
    ctx.abrir_ficha(pid, mid)
    app.update()
    f = app.vista.pantalla_actual
    assert isinstance(f, PantallaFicha)
    # Máquina sin largo: no hay estilo de cola ni forma de cara
    assert f.caja_largo.winfo_manager() and not f.caja_cara.winfo_manager()
    f.largo.codigo = "1CM"
    f._al_cambiar()
    assert f.caja_cara.winfo_manager() and not f.caja_cola.winfo_manager()
    f.opc["cola_leon"].codigo = 1
    f._al_cambiar()
    assert f.caja_cola.winfo_manager()
    f.tipo.codigo = "TIJERA"
    f._al_cambiar()
    assert not f.caja_largo.winfo_manager() and not f.caja_cara.winfo_manager()
    assert f.lbl["minimo"].cget("text") == "$50.000"
    f.medicado.set(1)
    f.precio_final.insert(0, "40.000")
    f._recalcular()
    assert f.lbl["extras"].cget("text") == "$5.000" and f.lbl["total"].cget("text") == "$45.000"
    assert "menor" in f.lbl_aviso.cget("text")
    f._guardar()
    app.update()
    sid = conn.execute("SELECT id FROM servicios").fetchone()[0]
    s = fichas.obtener(conn, empleada, sid)
    assert (s["tipo_servicio"], s["precio_final"], s["extras"], s["cola_estilo"]) == ("TIJERA", 40000, 5000, None)

    f = app.vista.pantalla_actual
    f._cambiar_estado("REVISION_ESTILISTA")
    app.update()
    app.vista.pantalla_actual._cambiar_estado("EN_SESIONES")
    app.update()
    fichas.registrar_sesion(conn, empleada, sid)
    ctx.abrir_ficha(pid, mid, sid)
    app.update()
    f = app.vista.pantalla_actual
    assert len(f.tabla_ses.get_children()) == 1
    assert f.lbl["gran_total"].cget("text") == "$105.000"
    f.al_volver()
    app.update()
    assert app.vista.pantalla_actual.detalle.pestanas.get() == "Mascotas"
    assert app.errores == []


def test_recorrido_admin_y_personal(app, conn):
    from clinican.ui.acceso import PantallaInicioSesion, PantallaPrimerArranque

    assert isinstance(app.vista, PantallaPrimerArranque)
    v = app.vista
    v.nombre.insert(0, "Angela")
    v.pin.insert(0, "1234")
    v.pin2.insert(0, "1234")
    v._crear()
    app.update()
    assert app.sesion.es_admin

    personal.crear(conn, app.sesion, "Laura", "Asistente de peluquería", "5678")
    principal = app.vista
    assert set(principal.entradas) == {"Agenda", "Nuevo turno", "Propietarios", "Horarios", "Personal", "Configuración", "Auditoría", "Cambiar mi PIN"}
    for nombre in principal.entradas:
        principal.mostrar(nombre)
        app.update()
    principal.mostrar("Personal")
    tabla = principal.pantalla_actual.tabla
    assert len(tabla.get_children()) == 2
    tabla.selection_set(tabla.get_children()[1])
    app.update()

    principal._cerrar_sesion()
    app.update()
    assert isinstance(app.vista, PantallaInicioSesion)
    login = app.vista
    login.usuario.set("Laura")
    login.pin.insert(0, "0000")
    login._entrar()
    assert app.sesion is None
    assert "incorrecto" in login.mensaje.cget("text")

    login.pin.insert(0, "5678")
    login._entrar()
    app.update()
    assert not app.sesion.es_admin
    assert set(app.vista.entradas) == {"Agenda", "Nuevo turno", "Propietarios", "Horarios", "Cambiar mi PIN"}
    assert app.errores == []


def test_turnos_desde_la_interfaz(app, conn, monkeypatch, admin, empleada):
    from datetime import date, timedelta

    from clinican.servicios import horarios, legal, turnos
    from clinican.servicios import propietarios as sp
    from clinican.ui import dialogos
    from clinican.ui.panel_turno import PanelTurno

    mensajes = []
    monkeypatch.setattr(dialogos, "_mostrar", lambda padre, titulo, mensaje, *a, **k: mensajes.append((titulo, mensaje)) or True)
    hoy = date.today()
    lunes = (hoy + timedelta(days=7 + (7 - hoy.weekday()) % 7)).isoformat()
    pid = sp.crear(conn, admin, "María Pérez", "1098765432", "3012345678", None, "Calle 10")
    raza = conn.execute("SELECT id FROM razas WHERE nombre='Shih Tzu'").fetchone()[0]
    mid = sp.crear_mascota(conn, admin, pid, "Toby", raza)

    app._entrar(empleada)
    app.update()
    ventana = app.vista
    assert ventana.nombre_actual == "Agenda"

    # Sin consentimientos, «Nuevo turno» no deja seguir
    ventana.mostrar("Nuevo turno", propietario_id=pid)
    app.update()
    nuevo = ventana.pantalla_actual
    assert not nuevo.plan and not hasattr(nuevo, "zona_horas")
    legal.aceptar(conn, empleada, pid, ["TERMINOS", "DATOS"])

    ventana.mostrar("Nuevo turno", propietario_id=pid, fecha=lunes)
    app.update()
    nuevo = ventana.pantalla_actual
    nuevo._horas_individual()
    app.update()
    assert nuevo.zona_horas.winfo_children()  # hay horas para elegir
    nuevo.plan = [(mid, "MAQUINA", lunes, "09:00")]
    nuevo._dibujar()
    nuevo._agendar()
    app.update()
    tid = conn.execute("SELECT id, estado FROM turnos").fetchone()
    assert tid["estado"] == "CONFIRMADO"
    agenda = ventana.pantalla_actual
    assert agenda.fecha.isoformat() == lunes and agenda.seleccionado == tid["id"]
    panel = agenda.panel_turno
    assert isinstance(panel, PanelTurno)
    panel._hacer(turnos.iniciar_atencion)
    app.update()
    panel = agenda.panel_turno
    panel._hacer(turnos.marcar_lista)
    app.update()
    assert turnos.turno(conn, empleada, tid["id"])["estado"] == "LISTA"

    # Horarios: el personal ve solo franjas; la administradora bloquea con turnos → se listan
    ventana.mostrar("Horarios")
    app.update()
    assert not hasattr(ventana.pantalla_actual, "pestanas")
    app._entrar(admin)
    app.update()
    app.vista.mostrar("Horarios")
    app.update()
    pantalla = app.vista.pantalla_actual
    for pestana in ("Franjas de una fecha", "Bloqueos", "Plantilla semanal"):
        pantalla.pestanas.set(pestana)
        app.update()
    pantalla._con_turnos(horarios.bloquear_dias, lunes, lunes, "Prueba")
    app.update()
    assert mensajes[-1][0] == "Hay turnos activos"
    assert app.vista.nombre_actual == "Agenda"
    assert app.errores == []
