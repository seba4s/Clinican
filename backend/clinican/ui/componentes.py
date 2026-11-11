"""Piezas reutilizables: botones, chips de estado, campos con error y diálogos."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from clinican.dominio.errores import ErrorNegocio
from clinican.dominio.estados import EstadoTurno
from clinican.ui import tema


def boton(padre, texto: str, comando: Callable | None = None, tipo: str = "secundario",
          ancho: int | None = None, alto: int = tema.ALTO_CONTROL) -> ctk.CTkButton:
    """tipo: principal (fucsia, uno por pantalla), secundario, peligro o enlace."""
    comun = dict(text=texto, command=comando, height=alto, corner_radius=tema.RADIO,
                 font=tema.fuente(tema.CUERPO, True))
    if ancho:
        comun["width"] = ancho
    if tipo == "principal":
        return ctk.CTkButton(padre, fg_color=tema.ACCION, hover_color=tema.ACCION_HOVER,
                             text_color="#FFFFFF", **comun)
    if tipo == "peligro":
        return ctk.CTkButton(padre, fg_color="transparent", hover_color=tema.HOVER_NEUTRO,
                             text_color=tema.PELIGRO, anchor="w", **comun)
    if tipo == "enlace":
        return ctk.CTkButton(padre, fg_color="transparent", hover_color=tema.HOVER_NEUTRO,
                             text_color=tema.ENLACE, anchor="w", **comun)
    return ctk.CTkButton(padre, fg_color=tema.SUPERFICIE, hover_color=tema.HOVER_NEUTRO,
                         text_color=tema.TINTA, border_width=1, border_color=tema.BORDE_CAMPO, **comun)


def etiqueta(padre, texto: str = "", tamano: int = tema.CUERPO, negrita: bool = False,
             suave: bool = False, color=None, **extra) -> ctk.CTkLabel:
    return ctk.CTkLabel(padre, text=texto, font=tema.fuente(tamano, negrita),
                        text_color=color or (tema.TINTA_SUAVE if suave else tema.TINTA),
                        anchor="w", justify="left", **extra)


def tarjeta(padre, **extra) -> ctk.CTkFrame:
    return ctk.CTkFrame(padre, fg_color=tema.SUPERFICIE, corner_radius=tema.RADIO_TARJETA, **extra)


def chip_estado(padre, estado: EstadoTurno, texto: str | None = None) -> ctk.CTkLabel:
    fondo, letra, _borde, nombre, icono = tema.estilo_estado(estado)
    return ctk.CTkLabel(padre, text=f"{icono}  {texto or nombre}", fg_color=fondo, text_color=letra,
                        corner_radius=14, height=28, font=tema.fuente(tema.ETIQUETA + 1, True))


def chip(padre, texto: str, fondo, letra) -> ctk.CTkLabel:
    return ctk.CTkLabel(padre, text=texto, fg_color=fondo, text_color=letra, corner_radius=12,
                        height=24, font=tema.fuente(tema.ETIQUETA, True))


class Campo(ctk.CTkFrame):
    """Etiqueta, entrada y mensaje de error debajo (validación en el momento)."""

    def __init__(self, padre, titulo: str, valor: str = "", ancho: int = 260,
                 placeholder: str = "", validar: Callable[[str], str | None] | None = None):
        super().__init__(padre, fg_color="transparent")
        self._validar = validar
        etiqueta(self, titulo, tema.ETIQUETA + 1, True).pack(anchor="w")
        self.entrada = ctk.CTkEntry(self, width=ancho, height=tema.ALTO_CONTROL, corner_radius=tema.RADIO,
                                    border_width=1, border_color=tema.BORDE_CAMPO, fg_color=tema.SUPERFICIE,
                                    text_color=tema.TINTA, placeholder_text=placeholder,
                                    font=tema.fuente(tema.CUERPO))
        self.entrada.pack(anchor="w", pady=(4, 0))
        if valor:
            self.entrada.insert(0, valor)
        self._error = etiqueta(self, "", tema.ETIQUETA, color=tema.PELIGRO)
        self._error.pack(anchor="w")
        if validar:
            self.entrada.bind("<KeyRelease>", lambda _e: self.revisar())

    def valor(self) -> str:
        return self.entrada.get().strip()

    def poner(self, texto: str) -> None:
        self.entrada.delete(0, "end")
        self.entrada.insert(0, texto)

    def error(self, mensaje: str | None) -> None:
        self._error.configure(text=mensaje or "")
        self.entrada.configure(border_color=tema.PELIGRO if mensaje else tema.BORDE_CAMPO,
                               border_width=2 if mensaje else 1)

    def revisar(self) -> bool:
        mensaje = self._validar(self.valor()) if self._validar else None
        self.error(mensaje)
        return not mensaje


class Texto(ctk.CTkFrame):
    """Etiqueta y caja de texto de varias líneas."""

    def __init__(self, padre, titulo: str, valor: str = "", alto: int = 90):
        super().__init__(padre, fg_color="transparent")
        etiqueta(self, titulo, tema.ETIQUETA + 1, True).pack(anchor="w")
        self.caja = ctk.CTkTextbox(self, height=alto, corner_radius=tema.RADIO, border_width=1,
                                   border_color=tema.BORDE_CAMPO, fg_color=tema.SUPERFICIE,
                                   text_color=tema.TINTA, font=tema.fuente(tema.CUERPO), wrap="word")
        self.caja.pack(fill="x", pady=(4, 0))
        if valor:
            self.caja.insert("1.0", valor)

    def valor(self) -> str:
        return self.caja.get("1.0", "end").strip()


class Dialogo(ctk.CTkToplevel):
    """Ventana modal corta. Esc la cierra; nunca hay dos a la vez."""

    def __init__(self, padre, titulo: str, ancho: int = 640, subtitulo: str = ""):
        super().__init__(padre)
        self.withdraw()
        self.title(titulo)
        self.configure(fg_color=tema.SUPERFICIE)
        self.resizable(False, False)
        self.transient(padre.winfo_toplevel())
        self.resultado = None
        self.bind("<Escape>", lambda _e: self.cerrar())
        self.protocol("WM_DELETE_WINDOW", self.cerrar)
        self.cuerpo = ctk.CTkFrame(self, fg_color="transparent", width=ancho)
        self.cuerpo.pack(fill="both", expand=True, padx=28, pady=(24, 12))
        etiqueta(self.cuerpo, titulo, 24, True).pack(anchor="w")
        if subtitulo:
            etiqueta(self.cuerpo, subtitulo, suave=True, wraplength=ancho).pack(anchor="w", pady=(2, 0))
        self.contenido = ctk.CTkFrame(self.cuerpo, fg_color="transparent")
        self.contenido.pack(fill="both", expand=True, pady=(16, 0))
        self.error_general = etiqueta(self.cuerpo, "", color=tema.PELIGRO, wraplength=ancho)
        self.error_general.pack(anchor="w", pady=(8, 0))
        self.botones = ctk.CTkFrame(self, fg_color="transparent")
        self.botones.pack(fill="x", padx=28, pady=(0, 24))

    def mostrar(self):
        """Centra el diálogo sobre la ventana, lo hace modal y espera a que se cierre."""
        self.update_idletasks()
        raiz = self.master.winfo_toplevel()
        x = raiz.winfo_rootx() + max(0, (raiz.winfo_width() - self.winfo_reqwidth()) // 2)
        y = raiz.winfo_rooty() + max(0, (raiz.winfo_height() - self.winfo_reqheight()) // 3)
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.lift()
        self.after(50, self._enfocar)
        self.grab_set()
        self.wait_window()
        return self.resultado

    def _enfocar(self) -> None:
        try:
            self.focus_force()
        except Exception:
            pass

    def boton_principal(self, texto: str, comando: Callable) -> ctk.CTkButton:
        b = boton(self.botones, texto, comando, "principal")
        b.pack(side="right")
        self.bind("<Return>", lambda _e: comando())
        return b

    def boton_cancelar(self, texto: str = "Cancelar") -> ctk.CTkButton:
        b = boton(self.botones, texto, self.cerrar)
        b.pack(side="right", padx=(0, tema.SEP))
        return b

    def error(self, mensaje: str | None) -> None:
        self.error_general.configure(text=mensaje or "")

    def intentar(self, accion: Callable[[], object]) -> bool:
        """Ejecuta ``accion``; si una regla la rechaza, muestra el motivo y devuelve False."""
        try:
            self.resultado = accion()
        except ErrorNegocio as e:
            self.error(str(e))
            return False
        self.error(None)
        return True

    def cerrar(self) -> None:
        try:
            self.grab_release()
        finally:
            self.destroy()


def confirmar(padre, titulo: str, explicacion: str, accion: str, peligro: bool = True,
              no: str = "No, volver") -> bool:
    """Pregunta antes de algo que no se deshace. Por defecto el foco queda en 'volver'."""
    d = Dialogo(padre, titulo, ancho=460)
    etiqueta(d.contenido, explicacion, wraplength=460, suave=True).pack(anchor="w")

    def si():
        d.resultado = True
        d.cerrar()

    if peligro:
        b = ctk.CTkButton(d.botones, text=accion, command=si, height=tema.ALTO_CONTROL, corner_radius=tema.RADIO,
                          fg_color=tema.PELIGRO, hover_color=tema.PELIGRO, text_color=("#FFFFFF", "#14121D"),
                          font=tema.fuente(tema.CUERPO, True))
        b.pack(side="right")
    else:
        d.boton_principal(accion, si)
    volver = d.boton_cancelar(no)
    d.after(80, volver.focus_set)
    return bool(d.mostrar())


class Aviso(ctk.CTkFrame):
    """Franja de aviso dentro de la ventana (éxito o error). Se cierra con su botón."""

    def __init__(self, padre):
        super().__init__(padre, corner_radius=tema.RADIO, fg_color=tema.SUPERFICIE_SUAVE)
        self._texto = etiqueta(self, "", wraplength=900)
        self._texto.pack(side="left", padx=14, pady=8, fill="x", expand=True)
        ctk.CTkButton(self, text="Cerrar", width=70, height=30, fg_color="transparent",
                      hover_color=tema.HOVER_NEUTRO, text_color=tema.TINTA, command=self.ocultar,
                      font=tema.fuente(tema.ETIQUETA, True)).pack(side="right", padx=8)
        self._visible = False
        self._antes = None

    def colocar(self, antes) -> None:
        self._antes = antes

    def mostrar(self, mensaje: str, error: bool = False) -> None:
        self._texto.configure(text=mensaje, text_color=tema.PELIGRO if error else tema.TINTA)
        self.configure(fg_color=("#FDE7EA", "#3A1E24") if error else ("#EEF4D6", "#2A3311"))
        if not self._visible:
            kwargs = {"before": self._antes} if self._antes else {}
            self.pack(fill="x", padx=24, pady=(12, 0), **kwargs)
            self._visible = True

    def ocultar(self) -> None:
        if self._visible:
            self.pack_forget()
            self._visible = False


class Lista(ctk.CTkScrollableFrame):
    """Contenedor con desplazamiento y fondo transparente."""

    def __init__(self, padre, **extra):
        extra.setdefault("fg_color", "transparent")
        super().__init__(padre, **extra)

    def vaciar(self) -> None:
        for hijo in self.winfo_children():
            hijo.destroy()
