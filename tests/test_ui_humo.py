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
    assert set(principal.entradas) == {"Agenda", "Nuevo turno", "Propietarios", "Horarios", "Personal", "Configuración", "Auditoría", "Respaldo", "Cambiar mi PIN"}
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
    assert set(app.vista.entradas) == {"Agenda", "Nuevo turno", "Propietarios", "Horarios", "Respaldo", "Cambiar mi PIN"}
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

    # Sin consentimientos sí se puede agendar: se aceptan al llegar, en la ficha de servicio
    ventana.mostrar("Nuevo turno", propietario_id=pid)
    app.update()
    nuevo = ventana.pantalla_actual
    assert hasattr(nuevo, "zona_horas")
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


def _textos_de_botones(widget) -> list[str]:
    import customtkinter as ctk

    textos = [widget.cget("text")] if isinstance(widget, ctk.CTkButton) else []
    for hijo in widget.winfo_children():
        textos += _textos_de_botones(hijo)
    return textos


def test_pantalla_respaldo(app, conn, monkeypatch, tmp_path, admin, empleada):
    from clinican.servicios import propietarios as sp
    from clinican.ui import dialogos
    from clinican.ui.acceso import PantallaInicioSesion

    mensajes = []
    monkeypatch.setattr(dialogos, "_mostrar", lambda padre, titulo, mensaje, *a, **k: mensajes.append((titulo, mensaje)) or True)
    monkeypatch.setenv("CLINICAN_HOME", str(tmp_path))
    sp.crear(conn, admin, "María Pérez", "1098765432", "3012345678", None, "Calle 10")

    # El personal puede respaldar pero no ve los botones de restaurar
    app._entrar(empleada)
    app.update()
    app.vista.mostrar("Respaldo")
    app.update()
    pantalla = app.vista.pantalla_actual
    pantalla._respaldar_en(pantalla.carpeta)
    app.update()
    assert mensajes[-1][0] == "Respaldo guardado"
    assert len(pantalla.tabla.get_children()) == 1
    assert not any("Restaurar" in t for t in _textos_de_botones(pantalla))

    # La administradora restaura esa copia y vuelve al inicio de sesión
    sp.crear(conn, admin, "Pedro Gómez", "5555555", "3150000000", None, "Cra 2")
    app._entrar(admin)
    app.update()
    app.vista.mostrar("Respaldo")
    app.update()
    pantalla = app.vista.pantalla_actual
    assert "Restaurar la copia elegida" in _textos_de_botones(pantalla)
    pantalla.tabla.selection_set(pantalla.tabla.get_children()[0])
    pantalla._restaurar_elegida()
    app.update()
    assert mensajes[-1][0] == "Respaldo restaurado"
    assert [f[0] for f in conn.execute("SELECT nombre FROM propietarios")] == ["María Pérez"]
    assert isinstance(app.vista, PantallaInicioSesion) and app.sesion is None
    assert app.errores == []


def _boton(widget, texto):
    """Busca un botón por su texto (para pulsar botones cuya acción es una función interna)."""
    import customtkinter as ctk

    if isinstance(widget, ctk.CTkButton) and widget.cget("text") == texto:
        return widget
    for hijo in widget.winfo_children():
        encontrado = _boton(hijo, texto)
        if encontrado is not None:
            return encontrado
    return None


def test_cliente_nuevo_se_agenda_y_se_registra_al_llegar(app, conn, monkeypatch, empleada):
    from datetime import date, timedelta

    from clinican.servicios import legal, turnos
    from clinican.ui import dialogos

    mensajes = []
    monkeypatch.setattr(dialogos, "_mostrar", lambda padre, titulo, mensaje, *a, **k: mensajes.append((titulo, mensaje)) or True)
    hoy = date.today()
    lunes = (hoy + timedelta(days=7 + (7 - hoy.weekday()) % 7)).isoformat()

    app._entrar(empleada)
    app.update()
    ventana = app.vista
    ventana.mostrar("Nuevo turno", fecha=lunes)
    app.update()
    nuevo = ventana.pantalla_actual
    nuevo._form_cliente_nuevo()
    app.update()
    c = nuevo.cliente_nuevo
    c["nombre"].insert(0, "Carolina")
    c["celular"].insert(0, "311 222 3344")
    c["mascota"].insert(0, "Michi")
    c["raza"].especie.codigo = "GATO"
    c["raza"]._al_cambiar_especie()
    c["raza"].raza.set("Gato (sin raza definida)")
    c["raza"].actualizar()
    assert c["raza"].caja_tamano.winfo_manager()  # raza sin tamaño: se pide el tamaño
    c["raza"].tamano.set("Pequeña")
    assert c["raza"].pelaje.get() == "No"  # viene en «No»
    c["tipo"].codigo = "BANO_DESLANADO"
    _boton(nuevo, "Continuar con este cliente").invoke()
    app.update()
    assert nuevo.dueno["provisional"] == 1  # no pidió cédula ni consentimientos
    mid = conn.execute("SELECT id FROM mascotas WHERE nombre = 'Michi'").fetchone()[0]
    assert nuevo._seleccionadas() == [(mid, "BANO_DESLANADO")]  # mascota y servicio ya elegidos
    nuevo._horas_individual()
    app.update()
    assert nuevo.zona_horas.winfo_children()
    nuevo.plan = [(mid, "BANO_DESLANADO", lunes, "09:00")]
    nuevo._dibujar()
    nuevo._agendar()
    app.update()
    tid = conn.execute("SELECT id FROM turnos").fetchone()[0]

    # Al llegar: sin registrar no se puede atender; el registro y los términos van en la ficha
    agenda = ventana.pantalla_actual
    agenda.panel_turno._hacer(turnos.iniciar_atencion)
    assert "sin registrar" in mensajes[-1][1]
    _boton(agenda.panel_turno, "Registrar cliente y términos (ficha)").invoke()
    app.update()
    ficha = ventana.pantalla_actual
    assert ficha.registro["cedula"].get() == "" and ficha.registro["celular1"].get() == "311 222 3344"
    ficha.registro["cedula"].insert(0, "52123456")
    ficha.registro["direccion"].insert(0, "Cra 7 # 8-9")
    for var in ficha.acepta.values():
        var.set(1)
    ficha._guardar()
    app.update()
    assert "Quedaron registrados los datos del cliente" in mensajes[-1][1]
    pid = conn.execute("SELECT propietario_id FROM mascotas WHERE id = ?", (mid,)).fetchone()[0]
    assert conn.execute("SELECT provisional, cedula FROM propietarios WHERE id = ?", (pid,)).fetchone()[:] == (0, "52123456")
    assert legal.estado(conn, pid)["TERMINOS"] and legal.estado(conn, pid)["DATOS"]
    assert not ventana.pantalla_actual.acepta  # ya aceptó: no vuelve a pedirlo
    turnos.iniciar_atencion(conn, empleada, tid)
    assert app.errores == []


def test_ficha_registra_terminos_de_cliente_registrado(app, conn, monkeypatch, admin, empleada):
    from clinican.servicios import legal
    from clinican.servicios import propietarios as sp
    from clinican.ui import dialogos

    monkeypatch.setattr(dialogos, "_mostrar", lambda *a, **k: True)
    pid = sp.crear(conn, admin, "María Pérez", "1098765432", "3012345678", None, "Calle 10")
    mid = sp.crear_mascota(conn, admin, pid, "Toby", conn.execute("SELECT id FROM razas WHERE nombre='Shih Tzu'").fetchone()[0])
    app._entrar(empleada)
    app.update()
    app.vista.ctx.abrir_ficha(pid, mid)
    app.update()
    f = app.vista.pantalla_actual
    assert not f.registro and set(f.acepta) == {"TERMINOS", "DATOS"}
    f.acepta["TERMINOS"].set(1)  # solo acepta los términos
    f._guardar()
    app.update()
    estado = legal.estado(conn, pid)
    assert estado["TERMINOS"] and estado["DATOS"] is None
    assert set(app.vista.pantalla_actual.acepta) == {"DATOS"}
    assert app.errores == []


def test_mascota_con_raza_escrita_y_ficha_con_corbatin(app, conn, monkeypatch, admin, empleada):
    from clinican.servicios import fichas
    from clinican.servicios import propietarios as sp
    from clinican.ui import dialogos

    monkeypatch.setattr(dialogos, "_mostrar", lambda *a, **k: True)
    pid = sp.crear(conn, admin, "María Pérez", "1098765432", "3012345678", None, "Calle 10")
    app._entrar(empleada)
    app.update()
    app.vista.mostrar("Propietarios", propietario_id=pid, pestana="Mascotas")
    app.update()
    detalle = app.vista.pantalla_actual.detalle
    selector = detalle.selector_raza  # formulario de «Nueva mascota» (no tiene mascotas)
    nombre = [w for w in detalle.form_m.winfo_children() if hasattr(w, "insert") and w.winfo_class() == "Frame"][0]
    nombre.insert(0, "Canela")
    selector.raza.set("Beagle")
    selector.actualizar()
    assert "raza nueva" in selector.nota.cget("text")
    selector.tamano.set("Mediana")
    selector.pelaje.set("No")
    _boton(detalle, "Guardar mascota").invoke()
    app.update()
    m = conn.execute("SELECT m.id, r.nombre, m.tamano_manual FROM mascotas m JOIN razas r ON r.id = m.raza_id").fetchone()
    assert (m[1], m[2]) == ("Beagle", "MEDIANA")

    app.vista.ctx.abrir_ficha(pid, m[0])
    app.update()
    f = app.vista.pantalla_actual
    lleva, color = f.accesorios["corbatin"]
    assert color.cget("state") == "disabled"
    lleva.codigo = 1
    f._al_cambiar_accesorio("corbatin")
    assert color.cget("state") == "normal"
    color.set("Azul")
    f.accesorios["monos"][0].codigo = 1
    f._al_cambiar_accesorio("monos")
    f.accesorios["monos"][1].set("Rosado")
    f._guardar()
    app.update()
    s = fichas.obtener(conn, empleada, conn.execute("SELECT id FROM servicios").fetchone()[0])
    assert (s["corbatin"], s["corbatin_color"], s["monos"], s["monos_color"]) == (1, "Azul", 1, "Rosado")
    assert app.errores == []


def test_importar_fichas_antiguas_y_campos_nuevos(app, conn, monkeypatch, tmp_path, empleada):
    from clinican.ui import dialogos
    from tests.test_importar_fichas import ficha

    mensajes = []
    monkeypatch.setattr(dialogos, "_mostrar", lambda padre, titulo, mensaje, *a, **k: mensajes.append((titulo, mensaje)) or True)
    app._entrar(empleada)
    app.update()
    app.vista.mostrar("Propietarios")
    app.update()
    pantalla = app.vista.pantalla_actual
    pantalla.importar_fichas([str(ficha(tmp_path / "lola.xlsx"))])
    app.update()
    assert [t for t, _m in mensajes[-2:]] == ["Revisión de las fichas", "Importación terminada"]
    assert len(pantalla.tabla.get_children()) == 1

    pid = conn.execute("SELECT id FROM propietarios").fetchone()[0]
    mid, sid = conn.execute("SELECT mascota_id, id FROM servicios").fetchone()
    app.vista.ctx.abrir_ficha(pid, mid, sid)
    app.update()
    f = app.vista.pantalla_actual
    assert set(f.adicionales) == {"despunte", "patas_rasuradas", "desparasitacion"}
    assert {"bigotes", "orejas"} <= set(f.opc)
    assert "Hembra" in _textos_de_etiquetas(f)
    assert app.errores == []


def _textos_de_etiquetas(widget) -> str:
    import customtkinter as ctk

    texto = widget.cget("text") if isinstance(widget, ctk.CTkLabel) else ""
    return texto + " ".join(_textos_de_etiquetas(h) for h in widget.winfo_children())
