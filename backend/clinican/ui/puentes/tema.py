"""Colores y letra para QML, tomados de ``tema.py``, según el modo claro u oscuro.

Sigue el modo de Windows hasta que se usa el botón de la barra lateral; desde entonces se
recuerda la elección (preferencia de la ventana, guardada con ``QSettings``).
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, QSettings, Qt, Signal, Slot
from PySide6.QtGui import QFontDatabase, QGuiApplication

from clinican.dominio.estados import EstadoTurno
from clinican.ui import tema

COLORES = (
    "FONDO", "SUPERFICIE", "SUPERFICIE_SUAVE", "TINTA", "TINTA_SUAVE", "BORDE_CAMPO", "BORDE", "ACCION",
    "ACCION_HOVER", "PELIGRO", "ENLACE", "SELECCION_FONDO", "SELECCION_TEXTO", "HOVER_NEUTRO", "VELO",
    "VERDE", "VERDE_LINEA", "TINTA_SOBRE_VERDE", "FONDO_HORA", "FONDO_SELECCION", "LINEA", "AVISO_OK",
    "AVISO_ERROR", "VIDRIO", "VIDRIO_FUERTE", "VIDRIO_BRILLO", "VIDRIO_BORDE", "SOMBRA", "MANCHA_1",
    "MANCHA_2", "MANCHA_3",
)


def _camello(nombre: str) -> str:
    primera, *resto = nombre.lower().split("_")
    return primera + "".join(p.capitalize() for p in resto)


def familia() -> str:
    """Segoe UI Variable si existe (Windows 11), si no Segoe UI o la del sistema."""
    disponibles = set(QFontDatabase.families())
    for nombre in ("Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI"):
        if nombre in disponibles:
            return nombre
    return QGuiApplication.font().family()


class Tema(QObject):
    """``tema`` en QML: ``tema.color.tinta``, ``tema.estado("CONFIRMADO")``, ``tema.oscuro``."""

    cambioTema = Signal()

    def __init__(self, app: QGuiApplication | None = None):
        super().__init__()
        self._familia = familia()
        self._ajustes = QSettings("Clinican", "Clinican")
        guardado = self._ajustes.value("tema/oscuro")
        self._forzado: bool | None = None if guardado is None else str(guardado).lower() in ("true", "1")
        self._hints = (app or QGuiApplication.instance()).styleHints()
        self._hints.colorSchemeChanged.connect(lambda _esquema: self.cambioTema.emit())

    def _es_oscuro(self) -> bool:
        if self._forzado is not None:
            return self._forzado
        return self._hints.colorScheme() == Qt.ColorScheme.Dark

    def forzar(self, oscuro: bool | None) -> None:
        """Solo para capturas y pruebas: fija el modo sin depender de Windows."""
        self._forzado = oscuro
        self.cambioTema.emit()

    @Slot()
    def alternar(self) -> None:
        """Botón de la barra lateral: cambia entre modo claro y oscuro y recuerda la elección."""
        self._forzado = not self._es_oscuro()
        self._ajustes.setValue("tema/oscuro", self._forzado)
        self._ajustes.sync()
        self.cambioTema.emit()

    def _par(self, par) -> str:
        return par[1] if self._es_oscuro() else par[0]

    @Property(bool, notify=cambioTema)
    def oscuro(self) -> bool:
        return self._es_oscuro()

    @Property("QVariantMap", notify=cambioTema)
    def color(self) -> dict:
        return {_camello(n): self._par(getattr(tema, n)) for n in COLORES}

    @Property("QVariantMap", notify=cambioTema)
    def estados(self) -> dict:
        datos = {}
        for estado in EstadoTurno:
            fondo, letra, borde, nombre, icono = tema.estilo_estado(estado)
            datos[estado.name] = {"fondo": self._par(fondo), "letra": self._par(letra), "borde": self._par(borde),
                                  "nombre": nombre, "icono": icono}
        return datos

    @Property(str, constant=True)
    def familia(self) -> str:
        return self._familia

    @Property("QVariantMap", constant=True)
    def medida(self) -> dict:
        return {"altoControl": tema.ALTO_CONTROL, "radio": tema.RADIO, "radioTarjeta": tema.RADIO_TARJETA,
                "sep": tema.SEP, "titulo": tema.TITULO, "subtitulo": tema.SUBTITULO, "cuerpo": tema.CUERPO,
                "etiqueta": tema.ETIQUETA}

    @Slot(str, result="QVariantMap")
    def estado(self, nombre: str) -> dict:
        return self.estados.get(nombre, {})
