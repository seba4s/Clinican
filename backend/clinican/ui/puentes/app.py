"""Ventana principal: barra lateral con cuatro secciones, aviso, diálogos y refresco periódico."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import Property, QCoreApplication, QEvent, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from clinican.dominio.entidades import EstadoNotificacion
from clinican.servicios import consultas
from clinican.ui.contexto import Contexto
from clinican.ui.puentes.base import Dialogo, Presentador, propiedad
from clinican.ui.puentes.tema import Tema
from clinican.ui.puentes.util import Util

registro = logging.getLogger("clinican.ui")

RAIZ_UI = Path(__file__).resolve().parent.parent
QML = RAIZ_UI / "qml"
LOGO = RAIZ_UI / "recursos" / "logo_perro.png"
REFRESCO_MS = 30_000


class App(Presentador):
    """Estado de la ventana: sección actual, aviso, insignia y el diálogo abierto (uno a la vez)."""

    SECCIONES = ("Agenda", "Clientes", "Recordatorios", "Ajustes")

    cambioApp = Signal()
    enfocarBusqueda = Signal()

    def __init__(self, ctx: Contexto):
        super().__init__()
        self.ctx = ctx
        self._seccion = ""
        self._aviso = ""
        self._aviso_error = False
        self._aviso_visible = False
        self._insignia = "Recordatorios"
        self._dialogo: Dialogo | None = None
        self._al_cerrar = None
        self._cerrados: list[Dialogo] = []  # QML puede seguir animando el cierre

        from clinican.ui.puentes.agenda import PantallaAgenda
        from clinican.ui.puentes.ajustes import PantallaAjustes
        from clinican.ui.puentes.clientes import PantallaClientes
        from clinican.ui.puentes.recordatorios import PantallaRecordatorios

        self.pantallas = {
            "Agenda": PantallaAgenda(self),
            "Clientes": PantallaClientes(self),
            "Recordatorios": PantallaRecordatorios(self),
            "Ajustes": PantallaAjustes(self),
        }
        self.reloj = QTimer(self)
        self.reloj.setInterval(REFRESCO_MS)
        self.reloj.timeout.connect(self._refresco_periodico)
        self.ir("Agenda")
        self.actualizar_insignias()
        self.reloj.start()

    seccion = propiedad(str, "seccion", cambioApp)
    aviso = propiedad(str, "aviso", cambioApp)
    avisoError = propiedad(bool, "aviso_error", cambioApp)
    avisoVisible = propiedad(bool, "aviso_visible", cambioApp)
    insignia = propiedad(str, "insignia", cambioApp)
    dialogo = propiedad(QObject, "dialogo", cambioApp)

    @Property("QVariantList", constant=True)
    def secciones(self) -> list[str]:
        return list(self.SECCIONES)

    @Property(QObject, constant=True)
    def agenda(self):
        return self.pantallas["Agenda"]

    @Property(QObject, constant=True)
    def clientes(self):
        return self.pantallas["Clientes"]

    @Property(QObject, constant=True)
    def recordatorios(self):
        return self.pantallas["Recordatorios"]

    @Property(QObject, constant=True)
    def ajustes(self):
        return self.pantallas["Ajustes"]

    @property
    def actual(self) -> str:
        return self._seccion

    # ------------------------------------------------------------------ aviso
    def avisar(self, mensaje: str, error: bool = False) -> None:
        self.poner(aviso=mensaje, aviso_error=error, aviso_visible=True)

    @Slot()
    def ocultar_aviso(self) -> None:
        self.poner(aviso_visible=False)

    def actualizar_insignias(self) -> None:
        """Muestra en la barra cuántos recordatorios fallaron."""
        try:
            with self.ctx.con() as con:
                fallidas = consultas.estado_bandeja(con, limite=1).conteo.get(EstadoNotificacion.FALLIDA, 0)
        except Exception:  # la insignia nunca debe tumbar la ventana
            registro.exception("No se pudo leer la bandeja")
            return
        texto = "Recordatorios" + (f"   ·  {fallidas} fallido{'s' if fallidas != 1 else ''}" if fallidas else "")
        self.poner(insignia=texto)

    # ------------------------------------------------------------------ navegación
    @Slot(str)
    def ir(self, nombre: str):
        """Muestra una sección. Se actualiza antes de pasar al frente, para que nunca se vea a medio armar."""
        pantalla = self.pantallas[nombre]
        pantalla.refrescar()
        self.poner(seccion=nombre, aviso_visible=False)
        return pantalla

    @Slot()
    def nuevoTurno(self) -> None:
        self.nuevo_turno()

    def nuevo_turno(self, **datos) -> None:
        if self.hay_dialogo():
            return
        self.ir("Agenda").nuevo_turno(**datos)

    @Slot()
    def buscarCliente(self) -> None:
        if self.hay_dialogo():
            return
        self.ir("Clientes")
        self.enfocarBusqueda.emit()

    # ------------------------------------------------------------------ diálogos
    def hay_dialogo(self) -> bool:
        return self._dialogo is not None

    def abrir(self, dialogo: Dialogo, al_cerrar=None) -> bool:
        """Muestra ``dialogo``; al cerrarse llama ``al_cerrar(resultado)``. Nunca hay dos a la vez."""
        if self._dialogo is not None:
            return False
        dialogo.terminado.connect(self._al_terminar)
        self._al_cerrar = al_cerrar
        self.poner(dialogo=dialogo)
        return True

    def _al_terminar(self) -> None:
        d, accion = self._dialogo, self._al_cerrar
        self._al_cerrar = None
        if d is not None:
            self._cerrados = (self._cerrados + [d])[-3:]
        self.poner(dialogo=None)
        if accion is not None:
            accion(d.resultado if d is not None else None)

    def _refresco_periodico(self) -> None:
        try:
            if self._seccion and not self.hay_dialogo():
                self.pantallas[self._seccion].refrescar_periodico()
                self.actualizar_insignias()
        except Exception:
            registro.exception("Falló el refresco periódico")


class Ventana:
    """Arma el motor de QML con el tema, las ayudas y la aplicación, y carga ``Main.qml``."""

    def __init__(self, ctx: Contexto):
        QQuickStyle.setStyle("Basic")
        self.qapp = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
        self.qapp.setApplicationName("Clinican")
        self.qapp.setWindowIcon(QIcon(str(LOGO)))
        self.avisos_qml: list[str] = []
        self.tema = Tema(self.qapp)
        self.util = Util()
        self.app = App(ctx)
        self.motor = QQmlApplicationEngine()
        self.motor.warnings.connect(lambda lista: self.avisos_qml.extend(w.toString() for w in lista))
        contexto = self.motor.rootContext()
        contexto.setContextProperty("tema", self.tema)
        contexto.setContextProperty("util", self.util)
        self.motor.rootContext().setContextProperty("app", self.app)
        self.motor.rootContext().setContextProperty("logo", QUrl.fromLocalFile(str(LOGO)))
        self.motor.load(QUrl.fromLocalFile(str(QML / "Main.qml")))
        if not self.motor.rootObjects():
            raise RuntimeError("No se pudo cargar la interfaz: " + "; ".join(self.avisos_qml))
        self.raiz = self.motor.rootObjects()[0]

    def cerrar(self) -> None:
        """Destruye la ventana antes que el tema y la aplicación (evita avisos de QML al salir)."""
        self.app.reloj.stop()
        self.raiz.deleteLater()
        self.motor.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QCoreApplication.processEvents()


def ejecutar(ctx: Contexto) -> None:
    ventana = Ventana(ctx)
    try:
        ventana.qapp.exec()
    finally:
        ventana.cerrar()
