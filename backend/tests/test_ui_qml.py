"""Prueba de humo de la interfaz QML: abre cada pantalla y recorre los diálogos principales.

La ventana se dibuja fuera de pantalla (``QT_QPA_PLATFORM=offscreen``). Además de las
acciones, cada prueba verifica que QML no haya dejado avisos (errores de enlace, tipos).
"""

from __future__ import annotations

import os
from datetime import timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtQuick", exc_type=ImportError)

from PySide6.QtCore import QCoreApplication, QObject  # noqa: E402

from clinican.datos.conexion import abrir  # noqa: E402
from clinican.dominio.cupos import CategoriaCupo as C  # noqa: E402
from clinican.dominio.estados import EstadoTurno as E  # noqa: E402
from clinican.servicios import agenda, fichas  # noqa: E402
from conftest import AHORA, a_las  # noqa: E402

AHORA_UI = a_las(9, 40)


def procesar() -> None:
    for _ in range(3):
        QCoreApplication.processEvents()


@pytest.fixture
def ventana(ruta_db, con, esc):
    from clinican.ui.contexto import Contexto
    from clinican.ui.puentes.app import Ventana

    # Datos: un pendiente, un confirmado, uno en atención y un grande atendido.
    pendiente = esc.turno(inicio=a_las(11), ahora=a_las(9, 30))
    confirmado = agenda.registrar_abono(con, esc.turno(inicio=a_las(10)).id, 20000, ahora=AHORA)
    en_atencion = agenda.registrar_abono(con, esc.turno(inicio=a_las(9)).id, 20000, ahora=AHORA)
    agenda.iniciar_atencion(con, en_atencion.id, ahora=AHORA)
    grande = agenda.registrar_abono(con, esc.turno(C.GRANDE, inicio=a_las(9)).id, 20000, ahora=AHORA)
    agenda.iniciar_atencion(con, grande.id, ahora=AHORA)
    agenda.marcar_atendido(con, grande.id, ahora=AHORA)

    ctx = Contexto(abrir=lambda: abrir(ruta_db), ruta_db=ruta_db, reloj=lambda: AHORA_UI)
    v = Ventana(ctx)
    v.ids = {"pendiente": pendiente.id, "confirmado": confirmado.id,
             "en_atencion": en_atencion.id, "grande": grande.id}
    procesar()
    yield v
    procesar()
    avisos = list(v.avisos_qml)
    v.cerrar()
    assert not avisos, "\n".join(avisos)


def items(v, nombre: str) -> list:
    """Elementos visuales con ese objectName (los de un Repeater no son hijos QObject)."""
    encontrados, pendientes = [], [v.raiz.contentItem()]
    while pendientes:
        item = pendientes.pop()
        if item.objectName() == nombre:
            encontrados.append(item)
        pendientes.extend(item.childItems())
    return encontrados


def item(v, nombre: str):
    lista = items(v, nombre)
    return lista[0] if lista else None


def dialogo_qml(v) -> QObject | None:
    """El objeto QML del diálogo abierto (o None)."""
    procesar()
    cargador = v.raiz.findChild(QObject, "dialogo")
    return cargador.property("item")


def test_todas_las_pantallas_abren(ventana):
    app = ventana.app
    for nombre in app.SECCIONES:
        pantalla = app.ir(nombre)
        procesar()
        assert app.actual == nombre and pantalla is app.pantallas[nombre]
        pagina = item(ventana, "pagina" + nombre)
        assert pagina.property("item") is not None  # la página cargó
        assert pagina.property("activa")


def test_agenda_muestra_turnos_y_acciones_por_estado(ventana):
    ag = ventana.app.ir("Agenda")
    assert set(ventana.ids.values()) <= set(ag._turnos)
    esperadas = {
        "pendiente": "Registrar abono",
        "confirmado": "Iniciar atención",
        "en_atencion": "Marcar atendido y llenar ficha",
        "grande": "Entregar",
    }
    for clave, primera in esperadas.items():
        ag.seleccionar(ventana.ids[clave])
        procesar()
        turno = ag._turnos[ventana.ids[clave]].turno
        assert ag._acciones(turno, None)[0][0] == primera
        assert ag.panel["acciones"][0]["texto"] == primera
        boton = item(ventana, "accion0")
        assert boton is not None and boton.property("text") == primera
    # Días anterior y siguiente no fallan (domingo cerrado incluido)
    for _ in range(7):
        ag.dia_siguiente()
        procesar()


def test_tablero_cuenta_libres_y_bloquea_pasadas(ventana, con):
    from clinican.ui.tablero import armar_tablero

    filas, fuera, libres = armar_tablero(con, a_las(9).date(), AHORA_UI)
    assert len(filas) == 16
    assert filas[0].pasada and not filas[-1].pasada
    assert not fuera
    # 16 franjas x 5 puestos, menos las pasadas (9:00) y los turnos de las franjas futuras
    assert libres == 15 * 5 - 2


def test_nuevo_turno_desde_el_dialogo(ventana, con, esc):
    p = esc.propietario(saldo=5000)
    m = esc.mascota(propietario=p)
    ag = ventana.app.ir("Agenda")
    ag.nuevo_turno(mascota_id=m.id)
    d = ventana.app._dialogo
    assert dialogo_qml(ventana) is not None
    assert d.propietario.id == p.id and d._mascota().id == m.id
    d.selector.elegir(a_las(14))
    assert d.textoBoton == "Agendar a las 14:00"
    d.agendar("$15.000")
    turno = d.resultado
    assert turno.inicio == a_las(14)
    assert turno.estado is E.CONFIRMADO  # 5.000 de saldo + 15.000 de abono
    assert ventana.app._dialogo is None and dialogo_qml(ventana) is None
    assert ag.seleccion == turno.id and "confirmado" in ventana.app._aviso


def test_nuevo_turno_busca_cliente_y_valida(ventana, esc):
    p = esc.propietario("Ana Quintero")
    esc.mascota(propietario=p)
    ventana.app.nuevo_turno()
    d = ventana.app._dialogo
    d.buscar("Quint")
    assert d.resultados and d.resultados[0]["id"] == p.id
    d.elegir_cliente(p.id)
    assert d.cliente["nombre"] == "Ana Quintero" and d.mascotaId
    d.agendar("")
    assert d.error_general == "Elige la hora." and d.abierto
    d.buscar("zzzz")
    assert d.sinResultados
    d.cancelar()
    assert ventana.app._dialogo is None


def test_abono_parcial_y_ficha(ventana, con):
    from clinican.ui.puentes.dialogo_ficha import DialogoFicha
    from clinican.ui.puentes.dialogos_turno import DialogoAbono

    ag = ventana.app.ir("Agenda")
    t = agenda.obtener_turno(con, ventana.ids["pendiente"])
    ag.registrar_abono(t)
    d = ventana.app._dialogo
    assert isinstance(d, DialogoAbono) and dialogo_qml(ventana) is not None
    d.registrar("0")
    assert d.errores["valor"] and d.abierto
    d.registrar("10000")
    assert d.resultado.abono_pagado == 10000 and d.resultado.estado is E.PENDIENTE_ABONO
    assert "Falta $10.000" in ventana.app._aviso

    ag.ficha(agenda.obtener_turno(con, ventana.ids["en_atencion"]))
    f = ventana.app._dialogo
    assert isinstance(f, DialogoFicha) and dialogo_qml(ventana) is not None
    f.cuenta("$50.000")
    assert f.cobrar.endswith("Cobrar al entregar $30.000")  # el abono se resta del precio final
    f.guardar(["Baño"], "", "", "40", "Lomo listo", "$50.000")
    assert agenda.obtener_turno(con, ventana.ids["en_atencion"]).estado is E.ATENDIDO
    ficha = fichas.ficha_de_turno(con, ventana.ids["en_atencion"])
    assert ficha.precio_final == 50000 and ficha.servicios_realizados == "Baño"
    assert len(fichas.sesiones_de_mascota(con, agenda.obtener_turno(con, ventana.ids["en_atencion"]).mascota_id)) == 1


def test_mover_cancelar_y_bloquear(ventana, con):
    from clinican.ui.tablero import armar_tablero

    ag = ventana.app.ir("Agenda")
    t = agenda.obtener_turno(con, ventana.ids["confirmado"])
    ag.mover(t)
    d = ventana.app._dialogo
    assert dialogo_qml(ventana) is not None
    d.selector.elegir(a_las(15))
    d.aceptar()
    assert agenda.obtener_turno(con, t.id).inicio == a_las(15)

    ag.cancelar(agenda.obtener_turno(con, t.id))
    confirmacion = ventana.app._dialogo
    assert dialogo_qml(ventana) is not None
    confirmacion.cancelar()
    assert agenda.obtener_turno(con, t.id).estado is E.CONFIRMADO  # «No, volver» no cancela

    ag.bloquear()
    b = ventana.app._dialogo
    assert dialogo_qml(ventana) is not None
    b.bloquear("09/11/2026", False, "12:00", "13:00", "Almuerzo")
    assert len(agenda.bloqueos_del_dia(con, a_las(9).date())) == 1
    filas, _fuera, _libres = armar_tablero(con, a_las(9).date(), AHORA_UI)
    assert [f.bloqueo for f in filas if f.bloqueo] == ["Almuerzo", "Almuerzo"]

    ag.bloquear()
    malo = ventana.app._dialogo
    malo.bloquear("9-11-26", False, "12:00", "13:00", "")
    assert malo.errores["fecha"] and malo.abierto
    malo.bloquear("10/11/2026", False, "13:00", "12:00", "")
    assert "posterior" in malo.error_general
    malo.cancelar()


def test_formatos():
    from clinican.ui import formato as fmt

    assert fmt.pesos(45000) == "$45.000"
    assert fmt.leer_pesos("$15.000") == 15000 and fmt.leer_pesos("") == 0
    assert fmt.celular("3005551234") == "300 555 1234"
    assert fmt.dia_largo(a_las(9).date()) == "Lunes 9 de noviembre"
    assert fmt.dia_corto(a_las(9).date() + timedelta(days=1), a_las(9).date()) == "Mañana"
    assert fmt.minutos_restantes(a_las(10), a_las(9, 48)) == "vence en 12 min"


def test_hoja_tipo_excel_agrupa_por_hora_y_agenda_desde_libre(ventana, con):
    from clinican.dominio.agenda import Bloqueo
    from clinican.ui.tablero import ORDEN_CATEGORIAS, agrupar, armar_tablero

    agenda.crear_bloqueo(con, Bloqueo(a_las(9).date(), a_las(12).timetz(), a_las(13).timetz(), "Almuerzo"),
                         ahora=AHORA)
    filas, _fuera, _libres = armar_tablero(con, a_las(9).date(), AHORA_UI)
    grupos = agrupar(filas, ORDEN_CATEGORIAS)
    bandas = [g for g in grupos if g.filas[0].tipo == "bloqueo"]
    assert len(bandas) == 1 and bandas[0].filas[0].hasta == a_las(13)  # 12:00 y 12:30 en una sola banda
    nueve = grupos[0]
    assert [f.tipo for f in nueve.filas] == ["turno", "turno"]  # 9:00 ya pasó: sin fila «Libre»
    diez = next(g for g in grupos if g.inicio == a_las(10))
    assert [f.tipo for f in diez.filas] == ["turno", "libre"]
    assert diez.filas[-1].libres[C.MAQUINA] == 1

    ag = ventana.app.ir("Agenda")
    ag.refrescar()
    procesar()
    hoja = ag.grupos
    assert [g["hora"] for g in hoja][:2] == ["09:00", "09:30"]
    assert any(g["bloqueo"] and g["filas"][0]["texto"].startswith("Bloqueado de 12:00 a 13:00") for g in hoja)
    assert len(items(ventana, "libre")) > 0  # los cupos libres se dibujan
    # Tocar un cupo libre abre el nuevo turno en esa hora y categoría
    diez_qml = next(g for g in hoja if g["hora"] == "10:00")
    clave = diez_qml["filas"][-1]["libres"][0]["clave"]
    ag.elegir_libre(clave)
    d = ventana.app._dialogo
    assert d.selector.elegida == a_las(10) and d.categoria_sugerida is C.MAQUINA
    d.cancelar()
    # Elegir un turno marca la fila sin volver a armar la hoja
    antes = ag.grupos
    ag.seleccionar(ventana.ids["confirmado"])
    assert ag.seleccion == ventana.ids["confirmado"] and ag.seleccionado == ventana.ids["confirmado"]
    assert ag.grupos is antes


def test_atajos_y_un_dialogo_a_la_vez(ventana):
    app = ventana.app
    app.nuevoTurno()
    primero = app._dialogo
    assert primero is not None and app.actual == "Agenda"
    app.nuevoTurno()
    app.buscarCliente()
    assert app._dialogo is primero and app.actual == "Agenda"  # nunca hay dos a la vez
    primero.cancelar()
    app.buscarCliente()
    assert app.actual == "Clientes"


def test_cliente_nuevo_y_mascota(ventana, con):
    from clinican.ui.puentes.clientes import DialogoCliente, DialogoMascota

    cl = ventana.app.ir("Clientes")
    cl.nuevo_cliente("3001234567")
    d = ventana.app._dialogo
    assert isinstance(d, DialogoCliente) and dialogo_qml(ventana) is not None
    assert d.inicial["celular"] == "3001234567" and d.inicial["nombre"] == ""
    d.guardar("Ana Quintero", "1020", "3001234567", "", False, d.inicial["fecha"], "")
    p = d.resultado
    assert p.telefono == "3001234567"
    # Al crear el cliente se abre de una vez el diálogo de su mascota.
    m = ventana.app._dialogo
    assert isinstance(m, DialogoMascota) and m.propietario_id == p.id and dialogo_qml(ventana) is not None
    m.guardar("", "Sin raza", False, "", "")
    assert m.errores["nombre"] and m.abierto
    m.guardar("Chispa", "Raza que no existe", False, "", "")
    assert "Elige una raza de la lista" in m.error_general
    m.elegir_tamano("Grande")
    m.guardar("Chispa", "Sin raza", True, "3", "Muerde")
    assert m.resultado.complicado and m.resultado.tamano.name == "GRANDE" and m.resultado.fecha_nacimiento
    assert cl.seleccion == p.id and cl.detalle["mascotas"][0]["nombre"] == "Chispa"
    assert cl.detalle["mascotas"][0]["cupo"] == "CUPO COMPLICADO"

    cl.nuevo_cliente("")
    corto = ventana.app._dialogo
    corto.guardar("X", "1", "300", "", False, corto.inicial["fecha"], "")
    assert corto.resultado is None and corto.abierto and corto.errores["celular"]
    corto.cancelar()


def test_cliente_autoriza_y_revoca_datos(ventana, con):
    from clinican.servicios import autorizaciones
    from clinican.ui import formato as fmt

    cl = ventana.app.ir("Clientes")
    cl.nuevo_cliente("3009998877")
    d = ventana.app._dialogo
    d.guardar("Luis Pantoja", "5050", "3009998877", "", True, "05/11/2026", "Formato firmado")
    p = d.resultado
    ventana.app._dialogo.cancelar()  # el diálogo de la mascota
    vigente = autorizaciones.autorizacion_vigente(con, p.id)
    assert vigente is not None and vigente.medio == "Formato firmado"
    assert fmt.fecha_numerica(vigente.fecha) == "05/11/2026"
    assert cl.detalle["metricas"][3]["valor"] == "Autorizó"

    cl.editar()
    futura = ventana.app._dialogo
    assert futura.inicial["autorizo"]
    futura.guardar("Luis Pantoja", "5050", "3009998877", "", True, "01/01/2099", "Formato firmado")
    assert futura.resultado is None and futura.abierto and "posterior a hoy" in futura.errores["fecha"]
    futura.cancelar()

    cl.editar()
    e = ventana.app._dialogo
    e.guardar("Luis Pantoja", "5050", "3009998877", "", False, e.inicial["fecha"], "")
    assert autorizaciones.autorizacion_vigente(con, p.id) is None
    assert len(autorizaciones.historial(con, p.id)) == 2
    assert cl.detalle["metricas"][3]["valor"] == "Sin autorización"


def test_clientes_busca_une_e_historial(ventana, con, esc):
    from clinican.servicios import clientes

    cl = ventana.app.ir("Clientes")
    uno = esc.propietario("Rosa Benavides")
    otro = esc.propietario("Rosa B.")  # mismo celular de prueba: posible duplicado
    esc.mascota(propietario=otro)
    cl.buscar("Rosa")
    assert {f["id"] for f in cl.lista} == {uno.id, otro.id}
    assert all(f["linea2"].startswith("Posible duplicado") for f in cl.lista)
    cl.elegir(uno.id)
    cl.unir()
    u = ventana.app._dialogo
    assert dialogo_qml(ventana) is not None
    u.aceptar()
    assert u.error_general == "Elige el cliente duplicado."
    u.buscar("Rosa B")
    u.elegir(otro.id)
    assert any(r["elegido"] for r in u.resultados)
    u.aceptar()
    assert not clientes.obtener_propietario(con, otro.id).activo
    assert len(cl.detalle["mascotas"]) == 1 and "Clientes unidos" in ventana.app._aviso

    # Historial con ficha: el precio abre la ficha para corregirla.
    t = agenda.obtener_turno(con, ventana.ids["grande"])
    cl.elegir(t.propietario_id)
    fila = next(f for f in cl.detalle["historial"] if f["turnoId"] == t.id)
    assert fila["precio"] == "$70.000"
    cl.ver_ficha(t.id)
    assert dialogo_qml(ventana) is not None and ventana.app._dialogo.textoGuardar == "Guardar cambios"
    ventana.app._dialogo.cancelar()

    cl.elegir(uno.id)
    cl.nuevo_turno_cliente()  # una sola mascota: abre el turno con ella
    assert ventana.app._dialogo is not None and ventana.app.actual == "Agenda"
    ventana.app._dialogo.cancelar()


def test_importar_excel_muestra_el_informe(ventana, tmp_path):
    from types import SimpleNamespace

    from clinican.ui.puentes.base import Informacion

    llamadas = []

    def importar(con, ruta, ahora):
        llamadas.append(ruta)
        return SimpleNamespace(aceptadas=[1, 2], rechazadas=[SimpleNamespace(fila=4, motivo="sin cédula")])

    ventana.app.ctx.importar_excel = importar
    cl = ventana.app.ir("Clientes")
    archivo = tmp_path / "mascotas.xlsx"
    cl.importar(archivo.as_uri())
    assert llamadas == [archivo]
    d = ventana.app._dialogo
    assert isinstance(d, Informacion) and dialogo_qml(ventana) is not None
    assert d.subtitulo == "2 filas aceptadas, 1 rechazadas." and d.detalle == "Fila 4: sin cédula"
    d.aceptar()
    ventana.app.ctx.importar_excel = None
    cl.importar(archivo.as_uri())
    assert ventana.app.avisoError and "no está disponible" in ventana.app.aviso
