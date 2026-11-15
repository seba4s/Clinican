"""Piezas comunes: propiedades para QML, la base de pantallas y la base de diálogos."""

from __future__ import annotations

import logging
from typing import Any, Callable

from PySide6.QtCore import Property, QObject, Signal, Slot

from clinican.dominio.errores import ErrorNegocio
from clinican.ui.contexto import Contexto

registro = logging.getLogger("clinican.ui")


class Presentador(QObject):
    """Base con ``poner``: asigna ``self._<nombre>`` y avisa a QML.

    PySide6 solo enlaza una propiedad con una señal declarada en la misma clase, así que
    cada clase que declara propiedades declara también su propia señal ``cambio<Clase>``
    (con nombre único) y ``poner`` emite todas las de la jerarquía.
    """

    def poner(self, **valores: Any) -> None:
        distinto = False
        for nombre, valor in valores.items():
            if getattr(self, "_" + nombre, object()) != valor:
                setattr(self, "_" + nombre, valor)
                distinto = True
        if distinto:
            self.avisar_cambio()

    def avisar_cambio(self) -> None:
        for nombre in _señales(type(self)):
            getattr(self, nombre).emit()


_CACHE_SEÑALES: dict[type, tuple[str, ...]] = {}


def _señales(clase: type) -> tuple[str, ...]:
    if clase not in _CACHE_SEÑALES:
        nombres = []
        for k in clase.__mro__:
            nombres += [n for n, v in vars(k).items() if n.startswith("cambio") and isinstance(v, Signal)]
        _CACHE_SEÑALES[clase] = tuple(dict.fromkeys(nombres))
    return _CACHE_SEÑALES[clase]


def propiedad(tipo, nombre: str, señal: Signal):
    """Propiedad de solo lectura para QML que lee ``self._<nombre>``; ``señal`` es de la misma clase."""

    def leer(self):
        return getattr(self, "_" + nombre)

    return Property(tipo, leer, notify=señal)


class Pantalla(Presentador):
    """Base de cada sección. ``refrescar`` vuelve a leer la base y actualiza lo que QML muestra."""

    titulo = ""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.ctx: Contexto = app.ctx

    def refrescar(self) -> None:  # pragma: no cover - cada pantalla la define
        pass

    def refrescar_periodico(self) -> None:
        """Lo que se redibuja cada 30 s; por defecto, todo."""
        self.refrescar()

    def avisar(self, mensaje: str, error: bool = False) -> None:
        self.app.avisar(mensaje, error)

    def ejecutar(self, accion, exito: str | None = None) -> bool:
        """Corre una operación de servicio; muestra el motivo si una regla la rechaza."""
        try:
            with self.ctx.con() as con:
                accion(con)
        except ErrorNegocio as e:
            self.avisar(str(e), error=True)
            self.refrescar()
            return False
        if exito:
            self.avisar(exito)
        else:
            self.app.ocultar_aviso()
        self.refrescar()
        self.app.actualizar_insignias()
        return True


class Dialogo(Presentador):
    """Diálogo modal corto. QML lo dibuja con ``vista``; Esc lo cierra; nunca hay dos a la vez.

    ``errores`` lleva el mensaje de cada campo (se muestra debajo del campo) y ``error``
    el mensaje general. ``intentar`` corre una acción y guarda el motivo si una regla
    la rechaza. ``cerrar`` avisa a la ventana, que llama a quien lo abrió con ``resultado``.
    """

    cambioDialogo = Signal()
    terminado = Signal()
    vista = ""

    def __init__(self, ctx: Contexto, titulo: str, ancho: int = 640, subtitulo: str = ""):
        super().__init__()
        self.ctx = ctx
        self._titulo = titulo
        self._subtitulo = subtitulo
        self._ancho = ancho
        self._error = ""
        self._errores: dict[str, str] = {}
        self.resultado = None
        self.abierto = True
        self._validadores: dict[str, Callable[[str], str | None]] = {}

    titulo = propiedad(str, "titulo", cambioDialogo)
    subtitulo = propiedad(str, "subtitulo", cambioDialogo)
    ancho = propiedad(int, "ancho", cambioDialogo)
    error_general = propiedad(str, "error", cambioDialogo)
    errores = propiedad("QVariantMap", "errores", cambioDialogo)

    @Property(str, constant=True)
    def archivo(self) -> str:
        return self.vista

    # ------------------------------------------------------------------ errores
    def error(self, mensaje: str | None) -> None:
        self.poner(error=mensaje or "")

    def error_campo(self, campo: str, mensaje: str | None) -> None:
        errores = dict(self._errores)
        if mensaje:
            errores[campo] = mensaje
        else:
            errores.pop(campo, None)
        self.poner(errores=errores)

    @Slot(str, str, result=bool)
    def validar(self, campo: str, texto: str) -> bool:
        """Validación en el momento (al escribir) de los campos que la tienen."""
        regla = self._validadores.get(campo)
        mensaje = regla(texto.strip()) if regla else None
        self.error_campo(campo, mensaje)
        return not mensaje

    def intentar(self, accion: Callable[[], object]) -> bool:
        """Ejecuta ``accion``; si una regla la rechaza, muestra el motivo y devuelve False."""
        try:
            self.resultado = accion()
        except ErrorNegocio as e:
            self.error(str(e))
            return False
        self.error(None)
        return True

    # ------------------------------------------------------------------ cierre
    @Slot()
    def aceptar(self) -> None:  # pragma: no cover - cada diálogo la define
        pass

    @Slot()
    def cancelar(self) -> None:
        self.resultado = None
        self.cerrar()

    def cerrar(self) -> None:
        if self.abierto:
            self.abierto = False
            self.terminado.emit()


class Confirmacion(Dialogo):
    """Pregunta antes de algo que no se deshace. Por defecto el foco queda en «volver»."""

    cambioConfirmacion = Signal()
    vista = "DialogoConfirmar.qml"

    def __init__(self, ctx, titulo: str, explicacion: str, accion: str, peligro: bool = True,
                 no: str = "No, volver"):
        super().__init__(ctx, titulo, ancho=460)
        self._explicacion = explicacion
        self._accion = accion
        self._peligro = peligro
        self._no = no

    explicacion = propiedad(str, "explicacion", cambioConfirmacion)
    accion = propiedad(str, "accion", cambioConfirmacion)
    peligro = propiedad(bool, "peligro", cambioConfirmacion)
    no = propiedad(str, "no", cambioConfirmacion)

    @Slot()
    def aceptar(self) -> None:
        self.resultado = True
        self.cerrar()


class Informacion(Dialogo):
    """Mensaje con un texto largo opcional (por ejemplo, el informe de una importación)."""

    cambioInformacion = Signal()
    vista = "DialogoInformacion.qml"

    def __init__(self, ctx, titulo: str, subtitulo: str = "", detalle: str = "", ancho: int = 560):
        super().__init__(ctx, titulo, ancho=ancho, subtitulo=subtitulo)
        self._detalle = detalle

    detalle = propiedad(str, "detalle", cambioInformacion)

    @Slot()
    def aceptar(self) -> None:
        self.resultado = True
        self.cerrar()
