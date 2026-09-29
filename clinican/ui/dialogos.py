"""Ventanas de aviso, confirmación y PIN, con letra grande."""

from __future__ import annotations

import logging
from typing import Callable

import customtkinter as ctk

from clinican.dominio.errores import ErrorClinican
from clinican.ui import tema

log = logging.getLogger(__name__)


class _Dialogo(ctk.CTkToplevel):
    def __init__(self, padre, titulo: str, mensaje: str, botones: list[tuple[str, str, object]],
                 con_pin: bool = False, detalle: str | None = None):
        super().__init__(padre)
        self.title(titulo)
        self.configure(fg_color=tema.BLANCO)
        self.resizable(False, False)
        self.resultado = None
        tema.poner_icono(self)

        cuerpo = ctk.CTkFrame(self, fg_color=tema.BLANCO)
        cuerpo.pack(padx=32, pady=(28, 16), fill="both", expand=True)
        tema.etiqueta(cuerpo, titulo, tema.TAM_SUBTITULO, negrita=True).pack(anchor="w", pady=(0, 10))
        tema.etiqueta(cuerpo, mensaje, wraplength=620).pack(anchor="w")
        if detalle:
            tema.caja_texto(cuerpo, alto=280, solo_lectura=True, texto=detalle, width=640).pack(fill="both", pady=(14, 0))

        self.pin = None
        if con_pin:
            self.pin = tema.entrada(cuerpo, ancho=220, oculto=True)
            self.pin.pack(anchor="w", pady=(16, 0))
            self.pin.bind("<Return>", lambda _e: self._cerrar(botones[0][2]))

        fila = ctk.CTkFrame(self, fg_color=tema.BLANCO)
        fila.pack(padx=32, pady=(8, 28), anchor="e")
        for texto, estilo, valor in botones:
            tema.boton(fila, texto, lambda v=valor: self._cerrar(v), estilo=estilo, ancho=150).pack(side="left", padx=(12, 0))

        self.protocol("WM_DELETE_WINDOW", lambda: self._cerrar(None))
        self.bind("<Escape>", lambda _e: self._cerrar(None))
        self.transient(padre.winfo_toplevel())
        self.update_idletasks()
        self._centrar(padre)
        self.after(50, self._tomar_foco)

    def _tomar_foco(self):
        try:
            self.grab_set()
        except Exception:  # la ventana aún no es visible
            self.after(50, self._tomar_foco)
            return
        (self.pin or self).focus_force()

    def _centrar(self, padre):
        raiz = padre.winfo_toplevel()
        x = raiz.winfo_rootx() + (raiz.winfo_width() - self.winfo_reqwidth()) // 2
        y = raiz.winfo_rooty() + (raiz.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def _cerrar(self, valor):
        if valor is True and self.pin is not None:
            valor = self.pin.get()
        self.resultado = valor
        self.grab_release()
        self.destroy()


def _mostrar(padre, *args, **kw):
    d = _Dialogo(padre, *args, **kw)
    padre.wait_window(d)
    return d.resultado


def aviso(padre, titulo: str, mensaje: str) -> None:
    _mostrar(padre, titulo, mensaje, [("Entendido", "primario", True)])


def error(padre, mensaje: str, titulo: str = "No se pudo completar") -> None:
    _mostrar(padre, titulo, mensaje, [("Entendido", "peligro", True)])


def confirmar(padre, titulo: str, mensaje: str, si: str = "Sí, continuar", no: str = "No, volver") -> bool:
    return _mostrar(padre, titulo, mensaje, [(si, "primario", True), (no, "secundario", False)]) is True


def reporte(padre, titulo: str, mensaje: str, detalle: str, si: str | None = None, no: str = "Cerrar") -> bool:
    """Muestra un texto largo (por ejemplo, filas rechazadas). Con ``si`` pide confirmación."""
    botones = ([(si, "primario", True)] if si else []) + [(no, "secundario", False)]
    return _mostrar(padre, titulo, mensaje, botones, detalle=detalle or "(sin detalle)") is True


def elegir(padre, titulo: str, mensaje: str, opciones: list[tuple[str, str]], detalle: str | None = None) -> str | None:
    """Varias opciones: [(texto del botón, valor)]. Devuelve el valor, o None si se cierra."""
    botones = [(texto, "primario" if i == 0 else "secundario", valor) for i, (texto, valor) in enumerate(opciones)]
    botones.append(("Cancelar", "secundario", None))
    return _mostrar(padre, titulo, mensaje, botones, detalle=detalle)


def pedir_pin(padre, titulo: str, mensaje: str) -> str | None:
    return _mostrar(padre, titulo, mensaje, [("Confirmar", "primario", True), ("Cancelar", "secundario", None)], con_pin=True)


FALLO = object()


def ejecutar(padre, funcion: Callable, *args, **kwargs):
    """Ejecuta una acción del negocio y muestra el error en pantalla si falla.

    Devuelve el resultado, o ``FALLO`` si hubo error.
    """
    try:
        return funcion(*args, **kwargs)
    except ErrorClinican as e:
        error(padre, str(e))
    except Exception:
        log.exception("Error inesperado")
        error(
            padre,
            "Ocurrió un error inesperado. La información ya guardada está segura.\n"
            "Si se repite, avise a quien administra el sistema (queda anotado en datos\\clinican.log).",
        )
    return FALLO
