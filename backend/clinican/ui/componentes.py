"""Piezas reutilizables: botones, chips de estado, campos con error y diálogos."""

from __future__ import annotations

import tkinter as tk
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
        # Los botones se empacan primero, abajo: si la pantalla es baja, se recorta el
        # contenido y los botones siguen a la vista.
        self.botones = ctk.CTkFrame(self, fg_color="transparent", width=0, height=0)
        self.botones.pack(side="bottom", fill="x", padx=28, pady=(0, 24))
        self.cuerpo = ctk.CTkFrame(self, fg_color="transparent", width=ancho)
        self.cuerpo.pack(fill="both", expand=True, padx=28, pady=(24, 12))
        etiqueta(self.cuerpo, titulo, 24, True).pack(anchor="w")
        if subtitulo:
            etiqueta(self.cuerpo, subtitulo, suave=True, wraplength=ancho).pack(anchor="w", pady=(2, 0))
        self.contenido = ctk.CTkFrame(self.cuerpo, fg_color="transparent", width=0, height=0)
        self.contenido.pack(fill="both", expand=True, pady=(16, 0))
        self.error_general = etiqueta(self.cuerpo, "", color=tema.PELIGRO, wraplength=ancho)
        self.error_general.pack(anchor="w", pady=(8, 0))

    def mostrar(self):
        """Centra el diálogo sobre la ventana, lo hace modal y espera a que se cierre."""
        self.update_idletasks()
        raiz = self.master.winfo_toplevel()
        x = raiz.winfo_rootx() + max(0, (raiz.winfo_width() - self.winfo_reqwidth()) // 2)
        y = raiz.winfo_rooty() + max(0, (raiz.winfo_height() - self.winfo_reqheight()) // 3)
        alto_max = self.winfo_screenheight() - 90  # deja ver la barra de tareas
        y = max(10, min(y, self.winfo_screenheight() - self.winfo_reqheight() - 60))
        if self.winfo_reqheight() > alto_max:
            escala = self._get_window_scaling()
            self.geometry(f"{round(self.winfo_reqwidth() / escala)}x{round(alto_max / escala)}+{x}+10")
        else:
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


class CampoHora(ctk.CTkFrame):
    """Hora en franjas de 30 minutos: se escribe (9, 9:30, 930, 4:30 pm) o se elige de una cuadrícula.

    Con las flechas ↑ y ↓ sube o baja media hora. Al salir del campo, la hora queda
    escrita como 09:30; si no se entiende, el borde se pone rojo y ``hora()`` lanza
    ``DatoInvalido`` con el motivo.
    """

    COLUMNAS = 4

    def __init__(self, padre, valor: str = "", horas: list[str] | None = None, ancho: int = 124):
        super().__init__(padre, width=ancho, height=tema.ALTO_CONTROL, corner_radius=tema.RADIO,
                         fg_color=tema.SUPERFICIE, border_width=1, border_color=tema.BORDE_CAMPO)
        self.grid_propagate(False)
        self.horas = horas or [f"{h:02d}:{m:02d}" for h in range(6, 21) for m in (0, 30)]
        self._popup = None
        self.entrada = ctk.CTkEntry(self, width=ancho - 52, height=tema.ALTO_CONTROL - 6, border_width=0,
                                    fg_color=tema.SUPERFICIE, text_color=tema.TINTA, font=tema.fuente(tema.CUERPO),
                                    corner_radius=0)
        self.entrada.grid(row=0, column=0, sticky="w", padx=(8, 0), pady=3)
        self.boton = ctk.CTkButton(self, text="▾", width=28, height=28, corner_radius=6, fg_color="transparent",
                                   hover_color=tema.HOVER_NEUTRO, text_color=tema.TINTA_SUAVE,
                                   font=tema.fuente(tema.CUERPO), command=self.abrir)
        self.boton.grid(row=0, column=1, padx=(0, 6), pady=6)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        if valor:
            self.set(valor)
        self.entrada.bind("<FocusOut>", lambda _e: self.normalizar())
        self.entrada.bind("<Return>", lambda _e: self.normalizar(), add="+")
        self.entrada.bind("<Up>", lambda _e: self._paso(-1))
        self.entrada.bind("<Down>", lambda _e: self._paso(1))
        self.entrada.bind("<Alt-Down>", lambda _e: self.abrir())

    # ------------------------------------------------------------------ valor
    def get(self) -> str:
        return self.entrada.get().strip()

    def set(self, texto: str) -> None:
        self.entrada.delete(0, "end")
        self.entrada.insert(0, texto)
        self.normalizar()

    def hora(self):
        from clinican.ui.formato import leer_hora

        return leer_hora(self.get())

    def normalizar(self) -> bool:
        """Escribe la hora como HH:MM; marca el borde en rojo si no se entiende."""
        from clinican.dominio.errores import DatoInvalido

        try:
            texto = self.hora().strftime("%H:%M")
        except DatoInvalido:
            self.configure(border_color=tema.PELIGRO, border_width=2)
            return False
        if texto != self.entrada.get():
            self.entrada.delete(0, "end")
            self.entrada.insert(0, texto)
        self.configure(border_color=tema.BORDE_CAMPO, border_width=1)
        return True

    def habilitar(self, activo: bool) -> None:
        estado = "normal" if activo else "disabled"
        self.entrada.configure(state=estado, text_color=tema.TINTA if activo else tema.TINTA_SUAVE)
        self.boton.configure(state=estado)
        self.configure(fg_color=tema.SUPERFICIE if activo else tema.SUPERFICIE_SUAVE)
        self.entrada.configure(fg_color=tema.SUPERFICIE if activo else tema.SUPERFICIE_SUAVE)

    def _paso(self, sentido: int) -> str:
        actual = self.get() if self.normalizar() else ""
        if actual in self.horas:
            i = max(0, min(len(self.horas) - 1, self.horas.index(actual) + sentido))
        else:
            i = 0
        self.set(self.horas[i])
        return "break"

    # ------------------------------------------------------------------ cuadrícula de horas
    def abrir(self) -> None:
        if self._popup is not None:
            self.cerrar()
            return
        self.normalizar()
        raiz = self.winfo_toplevel()
        # Toplevel simple (sin la barra de título que CustomTkinter retoca en Windows).
        oscuro = ctk.get_appearance_mode() == "Dark"
        popup = tk.Toplevel(raiz, bg=tema.BORDE_CAMPO[1 if oscuro else 0])
        popup.withdraw()
        popup.overrideredirect(True)
        self._popup = popup
        self._grab_previo = raiz.grab_current()
        marco = ctk.CTkFrame(popup, fg_color=tema.SUPERFICIE, corner_radius=0)
        marco.pack(fill="both", expand=True, padx=1, pady=1)
        actual = self.get()
        for i, h in enumerate(self.horas):
            elegido = h == actual
            b = ctk.CTkButton(marco, text=h, width=64, height=30, corner_radius=6,
                              fg_color=tema.SELECCION_FONDO if elegido else "transparent",
                              text_color=tema.SELECCION_TEXTO if elegido else tema.TINTA,
                              hover_color=tema.SELECCION_FONDO if elegido else tema.HOVER_NEUTRO,
                              font=tema.fuente(tema.ETIQUETA + 1, elegido),
                              command=lambda h=h: self._elegir(h))
            b.grid(row=i // self.COLUMNAS, column=i % self.COLUMNAS, padx=3, pady=2)
        popup.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 4
        alto = popup.winfo_reqheight()
        if y + alto > self.winfo_screenheight() - 40:
            y = max(0, self.winfo_rooty() - alto - 4)
        popup.geometry(f"+{x}+{y}")
        popup.deiconify()
        popup.lift()
        popup.bind("<Escape>", lambda _e: self.cerrar())
        popup.bind("<Button-1>", self._clic_fuera, add="+")
        try:
            popup.grab_set()
            popup.focus_force()
        except Exception:
            pass

    def _clic_fuera(self, evento) -> None:
        p = self._popup
        if p is None:
            return
        x, y = evento.x_root, evento.y_root
        if not (p.winfo_rootx() <= x < p.winfo_rootx() + p.winfo_width()
                and p.winfo_rooty() <= y < p.winfo_rooty() + p.winfo_height()):
            self.cerrar()

    def _elegir(self, h: str) -> None:
        self.cerrar()
        self.set(h)
        self.entrada.focus_set()

    def cerrar(self) -> None:
        p, self._popup = self._popup, None
        if p is None:
            return
        try:
            p.grab_release()
        except Exception:
            pass
        p.destroy()
        previo = getattr(self, "_grab_previo", None)
        if previo is not None:
            try:
                previo.grab_set()
            except Exception:
                pass
