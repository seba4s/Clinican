"""Colores, fuentes y componentes con la marca CLINICAN (sección 2).

Pautas: texto negro sobre verde lima; texto blanco solo sobre fucsia y en
negrita; letra grande; botones de al menos 40 px de alto; solo modo claro.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk
from PIL import Image

from clinican import rutas

VERDE = "#B7CF53"
VERDE_HOVER = "#A4BC42"
VERDE_SUAVE = "#EEF4D6"
FUCSIA = "#FE028D"
FUCSIA_HOVER = "#D6007A"
NEGRO = "#14121D"
AZUL = "#0EBCDE"
AZUL_OSCURO = "#087F97"  # para enlaces sobre blanco (mejor contraste)
FONDO = "#F4F5F2"
BLANCO = "#FFFFFF"
BORDE = "#CFD2C8"
GRIS_TEXTO = "#4A4854"
GRIS_BOTON = "#E6E7E2"
GRIS_BOTON_HOVER = "#D5D7D0"
ROJO_ERROR = "#B00020"

# Estado del turno -> (fondo de la tarjeta, borde). Siempre se muestra también el texto del estado.
ESTILO_ESTADO = {
    "PENDIENTE_ABONO": ("#FFE6F3", FUCSIA),
    "CONFIRMADO": ("#F1F7DC", VERDE),
    "EN_PROCESO": ("#DDF5FB", AZUL),
    "LISTA": (VERDE, NEGRO),
    "ATENDIDO": ("#EDEDEA", "#9A9AA2"),
    "LIBERADO": ("#F6F6F4", "#C9C9CE"),
    "NO_ASISTIO_AVISO": ("#F6F6F4", "#C9C9CE"),
    "NO_ASISTIO_SIN_AVISO": ("#F6F6F4", FUCSIA),
    "NO_ATENDIDO": ("#F6F6F4", FUCSIA),
}

FAMILIA = "Segoe UI"
# Tamaños en píxeles (CustomTkinter): 19 px ≈ 14 pt.
TAM_NORMAL = 19
TAM_PEQUENO = 17
TAM_SUBTITULO = 23
TAM_TITULO = 30
ALTO_BOTON = 48
ALTO_ENTRADA = 44

_cache_logo: dict[int, ctk.CTkImage] = {}


def configurar() -> None:
    _cache_logo.clear()  # las imágenes pertenecen a una ventana raíz concreta
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("green")


def fuente(tam: int = TAM_NORMAL, negrita: bool = False) -> ctk.CTkFont:
    return ctk.CTkFont(family=FAMILIA, size=tam, weight="bold" if negrita else "normal")


# ------------------------------------------------------------------ imágenes


def logo(tam: int) -> ctk.CTkImage | None:
    if tam not in _cache_logo:
        try:
            imagen = Image.open(rutas.asset("logo_perro.png"))
        except OSError:
            return None
        _cache_logo[tam] = ctk.CTkImage(light_image=imagen, size=(tam, tam))
    return _cache_logo[tam]


def poner_icono(ventana: tk.Misc) -> None:
    """Pone el icono del perro. CustomTkinter reemplaza el icono al abrir,
    por eso se vuelve a poner un momento después."""
    ruta = rutas.asset("clinican.ico")
    if not ruta.exists():
        return

    def _poner():
        try:
            ventana.iconbitmap(str(ruta))
        except tk.TclError:
            pass

    _poner()
    ventana.after(300, _poner)


# --------------------------------------------------------------- componentes

def titulo(padre, texto: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(padre, text=texto, font=fuente(TAM_TITULO, True), text_color=NEGRO, anchor="w")


def subtitulo(padre, texto: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(padre, text=texto, font=fuente(TAM_SUBTITULO, True), text_color=NEGRO, anchor="w")


def etiqueta(padre, texto: str = "", tam: int = TAM_NORMAL, negrita: bool = False, color: str = NEGRO, **kw) -> ctk.CTkLabel:
    kw.setdefault("anchor", "w")
    kw.setdefault("justify", "left")
    return ctk.CTkLabel(padre, text=texto, font=fuente(tam, negrita), text_color=color, **kw)


def entrada(padre, ancho: int = 320, oculto: bool = False, **kw) -> ctk.CTkEntry:
    return ctk.CTkEntry(
        padre, width=ancho, height=ALTO_ENTRADA, font=fuente(), text_color=NEGRO,
        fg_color=BLANCO, border_color=BORDE, border_width=2, show="•" if oculto else "", **kw,
    )


def selector(padre, valores: list[str], ancho: int = 320, editable: bool = False, **kw):
    """Lista desplegable grande. ``editable`` permite escribir un valor nuevo."""
    comun = dict(
        width=ancho, height=ALTO_ENTRADA, font=fuente(), dropdown_font=fuente(),
        text_color=NEGRO, button_color=VERDE, button_hover_color=VERDE_HOVER,
        dropdown_fg_color=BLANCO, dropdown_text_color=NEGRO, dropdown_hover_color=VERDE_SUAVE,
        values=valores, **kw,
    )
    if editable:
        return ctk.CTkComboBox(padre, fg_color=BLANCO, border_color=BORDE, border_width=2, **comun)
    return ctk.CTkOptionMenu(padre, fg_color=BLANCO, **comun)


def boton(padre, texto: str, comando, estilo: str = "primario", ancho: int = 200, **kw) -> ctk.CTkButton:
    """Estilos: primario (lima, texto negro), peligro (fucsia, texto blanco en
    negrita), secundario (gris claro, texto negro)."""
    colores = {
        "primario": (VERDE, VERDE_HOVER, NEGRO),
        "peligro": (FUCSIA, FUCSIA_HOVER, BLANCO),
        "secundario": (GRIS_BOTON, GRIS_BOTON_HOVER, NEGRO),
    }[estilo]
    return ctk.CTkButton(
        padre, text=texto, command=comando, width=ancho, height=ALTO_BOTON,
        fg_color=colores[0], hover_color=colores[1], text_color=colores[2],
        font=fuente(TAM_NORMAL, True), corner_radius=10, **kw,
    )


class Opciones(ctk.CTkSegmentedButton):
    """Botones de opción grandes. Trabaja con códigos: {código: texto visible}."""

    def __init__(self, padre, opciones: dict, comando=None, inicial=None):
        self._a_texto = dict(opciones)
        self._a_codigo = {v: k for k, v in opciones.items()}
        self._comando = comando
        super().__init__(
            padre, values=list(opciones.values()), font=fuente(TAM_NORMAL, True), height=ALTO_ENTRADA,
            fg_color=GRIS_BOTON, selected_color=VERDE, selected_hover_color=VERDE_HOVER,
            unselected_color=GRIS_BOTON, unselected_hover_color=GRIS_BOTON_HOVER, text_color=NEGRO,
            text_color_disabled=GRIS_TEXTO, command=lambda _v: comando and comando(),
        )
        self.codigo = inicial

    @property
    def codigo(self):
        return self._a_codigo.get(self.get())

    @codigo.setter
    def codigo(self, valor) -> None:
        self.set(self._a_texto.get(valor, ""))


def casilla(padre, texto: str, variable=None, comando=None, **kw) -> ctk.CTkCheckBox:
    return ctk.CTkCheckBox(
        padre, text=texto, variable=variable, command=comando, font=fuente(), text_color=NEGRO,
        fg_color=VERDE, hover_color=VERDE_HOVER, checkmark_color=NEGRO, border_color=NEGRO,
        checkbox_width=28, checkbox_height=28, onvalue=1, offvalue=0, **kw,
    )


def interruptor(padre, texto: str, variable=None, comando=None) -> ctk.CTkSwitch:
    return ctk.CTkSwitch(
        padre, text=texto, variable=variable, command=comando, font=fuente(), text_color=NEGRO,
        progress_color=FUCSIA, button_color=NEGRO, button_hover_color=GRIS_TEXTO,
        switch_width=56, switch_height=28, onvalue=1, offvalue=0,
    )


def caja_texto(padre, alto: int = 160, solo_lectura: bool = False, texto: str = "", **kw) -> ctk.CTkTextbox:
    caja = ctk.CTkTextbox(
        padre, height=alto, font=fuente(TAM_PEQUENO + 1), text_color=NEGRO, fg_color=BLANCO,
        border_color=BORDE, border_width=2, wrap="word", **kw,
    )
    if texto:
        caja.insert("1.0", texto)
    if solo_lectura:
        caja.configure(state="disabled")
    return caja


def poner_texto(caja: ctk.CTkTextbox, texto: str) -> None:
    """Reemplaza el contenido de una caja (aunque sea de solo lectura)."""
    estado = caja._textbox.cget("state")  # CTkTextbox no expone "state" en cget
    caja.configure(state="normal")
    caja.delete("1.0", "end")
    caja.insert("1.0", texto)
    caja.configure(state=estado)


def aviso_estado(padre, texto: str, correcto: bool) -> ctk.CTkLabel:
    """Etiqueta de estado con color **y** texto (no depende solo del color)."""
    return ctk.CTkLabel(
        padre, text=("✔ " if correcto else "✖ ") + texto, font=fuente(TAM_NORMAL, True),
        text_color=NEGRO if correcto else BLANCO, fg_color=VERDE_SUAVE if correcto else FUCSIA,
        corner_radius=8, anchor="w", justify="left", padx=12, pady=6,
    )


def insignia(padre, texto: str, fondo: str = VERDE) -> ctk.CTkLabel:
    """Etiqueta con fondo de color. Sobre fucsia el texto va blanco; sobre lo demás, negro."""
    return ctk.CTkLabel(padre, text=texto, font=fuente(TAM_NORMAL, True), fg_color=fondo,
                        text_color=BLANCO if fondo == FUCSIA else NEGRO, corner_radius=8, padx=14, pady=6)


def enfocar_luego(widget, ms: int = 100) -> None:
    """Pone el cursor en el campo un momento después, si el campo todavía existe."""
    widget.after(ms, lambda: widget.winfo_exists() and widget.focus_set())


def tarjeta(padre, **kw) -> ctk.CTkFrame:
    return ctk.CTkFrame(padre, fg_color=BLANCO, corner_radius=14, border_width=1, border_color=BORDE, **kw)


def configurar_tablas(raiz: tk.Misc) -> None:
    """Estilo de las tablas (ttk.Treeview) con letra grande."""
    estilo = ttk.Style(raiz)
    estilo.theme_use("clam")
    estilo.configure(
        "Clinican.Treeview", font=(FAMILIA, 14), rowheight=38, background=BLANCO,
        fieldbackground=BLANCO, foreground=NEGRO, bordercolor=BORDE, borderwidth=1,
    )
    estilo.configure(
        "Clinican.Treeview.Heading", font=(FAMILIA, 14, "bold"), background=VERDE,
        foreground=NEGRO, relief="flat", padding=(8, 8),
    )
    estilo.map("Clinican.Treeview.Heading", background=[("active", VERDE_HOVER)])
    estilo.map("Clinican.Treeview", background=[("selected", AZUL)], foreground=[("selected", NEGRO)])
    estilo.configure("Vertical.TScrollbar", arrowsize=18)


def tabla(padre, columnas: list[tuple[str, str, int]], alto: int = 12) -> ttk.Treeview:
    """``columnas`` = [(id, título, ancho)]. Devuelve el Treeview dentro de un marco con barra."""
    marco = ctk.CTkFrame(padre, fg_color=BLANCO)
    arbol = ttk.Treeview(
        marco, columns=[c[0] for c in columnas], show="headings", height=alto,
        style="Clinican.Treeview", selectmode="browse",
    )
    for ident, texto, ancho in columnas:
        arbol.heading(ident, text=texto, anchor="w")
        arbol.column(ident, width=ancho, minwidth=60, anchor="w", stretch=True)
    barra = ttk.Scrollbar(marco, orient="vertical", command=arbol.yview)
    arbol.configure(yscrollcommand=barra.set)
    arbol.pack(side="left", fill="both", expand=True)
    barra.pack(side="right", fill="y")
    arbol.tag_configure("inactivo", foreground="#8A8894")
    arbol.tag_configure("par", background="#F8F9F5")
    arbol.marco = marco  # para ubicarlo con pack/grid
    return arbol
