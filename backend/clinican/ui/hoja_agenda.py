"""Agenda del día dibujada como una hoja de cálculo (columna de horas, encabezado y cuadrícula).

Se dibuja en un solo ``Canvas``: redibujar el día cuesta unos milisegundos, mientras
que crear y destruir decenas de botones hacía que la pantalla se trabara al cambiar de
pestaña. Cada franja de 30 minutos ocupa una o varias filas (un turno por fila) y su
hora queda combinada a la izquierda, como en Excel. Debajo de los turnos, una fila
«Libre» muestra los cupos que quedan; cada uno se puede tocar para agendar ahí.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

import customtkinter as ctk

from clinican.dominio.cupos import CategoriaCupo
from clinican.dominio.estados import EstadoTurno
from clinican.servicios.consultas import TurnoEnAgenda
from clinican.ui import formato as fmt
from clinican.ui import tema

# (título, peso del ancho)
COLUMNAS = (
    ("Hora", 0.75),
    ("Cupo", 0.95),
    ("Mascota", 1.15),
    ("Raza", 1.0),
    ("Servicio", 1.25),
    ("Propietario", 1.3),
    ("Celular", 1.3),
    ("Abono", 1.05),
    ("Estado", 1.4),
)
ALTO_FILA = 34
ALTO_ENCABEZADO = 36
PAD = 10

VERDE = ("#B7CF53", "#B7CF53")  # verde de la marca, como el encabezado de la hoja
TINTA_SOBRE_VERDE = ("#14121D", "#14121D")
FONDO_HORA = ("#EEF4D6", "#252D10")
FONDO_SELECCION = ("#FCE4F1", "#3B1D30")
LINEA = ("#DEDFD8", "#3A3842")


@dataclass
class FilaHoja:
    """Una fila dibujada. ``tipo``: turno, libre, pasada o bloqueo."""

    tipo: str
    inicio: datetime
    item: TurnoEnAgenda | None = None
    libres: dict[CategoriaCupo, int] = field(default_factory=dict)
    texto: str = ""
    hasta: datetime | None = None


@dataclass
class GrupoHora:
    """Las filas de una misma franja: la hora se combina en una sola celda."""

    inicio: datetime
    pasada: bool
    filas: list[FilaHoja]


class HojaAgenda(ctk.CTkFrame):
    def __init__(self, padre, al_elegir_turno: Callable[[int], None],
                 al_elegir_libre: Callable[[datetime, CategoriaCupo], None]):
        super().__init__(padre, fg_color="transparent", width=0, height=0)
        self._al_turno = al_elegir_turno
        self._al_libre = al_elegir_libre
        self._grupos: list[GrupoHora] = []
        self._seleccion: int | None = None
        self._ahora: datetime | None = None
        self._cerrado = ""
        self._zonas: list[tuple[float, float, float, float, tuple]] = []  # (x0, y0, x1, y1, acción)
        self._sobre: tuple | None = None
        self._pendiente = None
        self._bandas: list[tuple[float, float]] = []
        self._textos_banda: list = []

        self.encabezado = tk.Canvas(self, height=ALTO_ENCABEZADO, highlightthickness=0, bd=0)
        self.encabezado.grid(row=0, column=0, sticky="ew")
        self.lienzo = tk.Canvas(self, highlightthickness=0, bd=0)
        self.lienzo.grid(row=1, column=0, sticky="nsew")
        self.barra = ctk.CTkScrollbar(self, command=self.lienzo.yview, button_color=tema.BORDE_CAMPO,
                                      button_hover_color=tema.TINTA_SUAVE)
        self.barra.grid(row=1, column=1, sticky="ns")
        self.lienzo.configure(yscrollcommand=self.barra.set)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.lienzo.bind("<Configure>", lambda _e: self._programar())
        self.lienzo.bind("<Motion>", self._mover)
        self.lienzo.bind("<Leave>", lambda _e: self._resaltar(None))
        self.lienzo.bind("<Button-1>", self._clic)
        self.lienzo.bind_all("<MouseWheel>", self._rueda, add="+")
        self.lienzo.bind_all("<Button-4>", self._rueda, add="+")
        self.lienzo.bind_all("<Button-5>", self._rueda, add="+")
        ctk.AppearanceModeTracker.add(lambda _modo: self._programar(), self)

    # ------------------------------------------------------------------ datos
    def mostrar(self, grupos: list[GrupoHora], seleccion: int | None, ahora: datetime, cerrado: str = "") -> None:
        self._grupos = grupos
        self._seleccion = seleccion
        self._ahora = ahora
        self._cerrado = cerrado
        self._dibujar()

    def seleccionar(self, turno_id: int | None) -> None:
        self._seleccion = turno_id
        self._dibujar()

    def ir_a(self, turno_id: int) -> None:
        """Desplaza la hoja para que se vea la fila del turno."""
        for x0, y0, x1, y1, accion in self._zonas:
            if accion == ("turno", turno_id):
                alto_total = max(1, float(self.lienzo.cget("scrollregion").split()[3] or 1))
                visible = self.lienzo.winfo_height()
                arriba, abajo = self.lienzo.canvasy(0), self.lienzo.canvasy(visible)
                if y0 < arriba or y1 > abajo:
                    self.lienzo.yview_moveto(max(0.0, (y0 - visible / 3) / alto_total))
                return

    # ------------------------------------------------------------------ medidas y colores
    def _escala(self) -> float:
        return ctk.ScalingTracker.get_widget_scaling(self)

    def _color(self, par) -> str:
        if isinstance(par, str):
            return par
        return par[1] if ctk.get_appearance_mode() == "Dark" else par[0]

    def _fuente(self, tamano: int, negrita: bool = False) -> tkfont.Font:
        clave = (tamano, negrita, self._escala())
        cache = self.__dict__.setdefault("_fuentes", {})
        if clave not in cache:
            cache[clave] = tkfont.Font(family=tema.familia(), size=-round(tamano * self._escala()),
                                       weight="bold" if negrita else "normal")
        return cache[clave]

    def _anchos(self, total: float) -> list[float]:
        pesos = sum(p for _t, p in COLUMNAS)
        return [total * p / pesos for _t, p in COLUMNAS]

    @staticmethod
    def _recortar(texto: str, fuente: tkfont.Font, ancho: float) -> str:
        if fuente.measure(texto) <= ancho:
            return texto
        while texto and fuente.measure(texto + "…") > ancho:
            texto = texto[:-1]
        return (texto.rstrip() + "…") if texto else ""

    # ------------------------------------------------------------------ dibujo
    def _programar(self) -> None:
        if self._pendiente is None:
            self._pendiente = self.after_idle(self._dibujar)

    def _dibujar(self) -> None:
        if self._pendiente is not None:
            try:
                self.after_cancel(self._pendiente)
            except ValueError:
                pass
            self._pendiente = None
        e = self._escala()
        c = self._color
        ancho = max(self.lienzo.winfo_width(), 400)
        anchos = self._anchos(ancho)
        xs = [0.0]
        for a in anchos:
            xs.append(xs[-1] + a)
        fila_alto = ALTO_FILA * e
        pad = PAD * e
        letra = self._fuente(tema.ETIQUETA + 1)
        letra_n = self._fuente(tema.ETIQUETA + 1, True)
        linea = c(LINEA)
        fondo = c(tema.SUPERFICIE)

        # Encabezado fijo, verde como la fila de títulos de la hoja.
        cab = self.encabezado
        cab.delete("all")
        cab.configure(bg=c(VERDE), height=ALTO_ENCABEZADO * e)
        for i, (titulo, _p) in enumerate(COLUMNAS):
            cab.create_text(xs[i] + pad, ALTO_ENCABEZADO * e / 2, text=titulo, anchor="w",
                            font=letra_n, fill=c(TINTA_SOBRE_VERDE))
            if i:
                cab.create_line(xs[i], 0, xs[i], ALTO_ENCABEZADO * e, fill=c(("#9DB33C", "#9DB33C")))

        lz = self.lienzo
        lz.delete("all")
        lz.configure(bg=fondo)
        self._zonas = []
        if self._cerrado:
            lz.create_text(ancho / 2, 60 * e, text=self._cerrado, font=self._fuente(tema.SUBTITULO),
                           fill=c(tema.TINTA_SUAVE))
            lz.configure(scrollregion=(0, 0, ancho, 120 * e))
            return

        y = 0.0
        self._bandas, self._textos_banda = [], []
        ahora = self._ahora
        for grupo in self._grupos:
            y0_grupo = y
            actual = ahora is not None and grupo.inicio <= ahora < grupo.inicio + timedelta(minutes=30)
            for fila in grupo.filas:
                self._fila(fila, grupo, y, fila_alto, xs, letra, letra_n)
                y += fila_alto
                lz.create_line(xs[1], y, ancho, y, fill=linea)
            # Celda de la hora, combinada para toda la franja.
            bloqueo = grupo.filas[0].tipo == "bloqueo"
            lz.create_rectangle(0, y0_grupo, xs[1], y, fill=c(VERDE if bloqueo else FONDO_HORA), width=0)
            texto_hora = fmt.hora(grupo.inicio)
            color_hora = tema.ACCION if actual else (tema.TINTA_SUAVE if grupo.pasada else tema.TINTA)
            lz.create_text(pad, y0_grupo + fila_alto / 2, text=self._recortar(texto_hora, letra_n, xs[1] - pad * 1.5),
                           anchor="w", font=letra_n, fill=c(TINTA_SOBRE_VERDE if bloqueo else color_hora))
            if actual:
                lz.create_rectangle(0, y0_grupo, 4 * e, y, fill=c(tema.ACCION), width=0)
            lz.create_line(0, y, ancho, y, fill=linea)
        lz.create_line(xs[1], 0, xs[1], y, fill=linea)
        for grupo_y0, grupo_y1 in self._bandas:
            lz.create_rectangle(xs[1] + 1, grupo_y0 + 1, ancho, grupo_y1, fill=c(VERDE), width=0)
        for item in self._textos_banda:
            lz.create_text(*item[0], **item[1])
        # La fila seleccionada se dibuja encima con un borde fucsia.
        for x0, y0, x1, y1, accion in self._zonas:
            if accion == ("turno", self._seleccion):
                lz.create_rectangle(x0 + 1, y0 + 1, x1 - 1, y1 - 1, outline=c(tema.ACCION), width=2 * e)
        lz.configure(scrollregion=(0, 0, ancho, max(y, 1)))
        self._sobre = None

    def _fila(self, fila: FilaHoja, grupo: GrupoHora, y: float, alto: float, xs, letra, letra_n) -> None:
        lz = self.lienzo
        c = self._color
        e = self._escala()
        pad = PAD * e
        medio = y + alto / 2
        suave = c(tema.TINTA_SUAVE)
        tinta = c(tema.TINTA)

        if fila.tipo == "bloqueo":
            self._bandas.append((y, y + alto))
            self._textos_banda.append(((xs[1] + pad, medio), dict(
                text=f"Bloqueado de {fmt.hora(fila.inicio)} a {fmt.hora(fila.hasta)} · {fila.texto}", anchor="w", font=letra_n, fill=c(TINTA_SOBRE_VERDE))))
            return

        # Líneas verticales de la fila; en la fila «Libre» las celdas van combinadas.
        for x in (xs[2:3] if fila.tipo == "libre" else xs[2:-1]):
            lz.create_line(x, y, x, y + alto, fill=c(LINEA), tags="vertical")

        if fila.tipo == "pasada":
            lz.create_text(xs[1] + pad, medio, text="Sin turnos", anchor="w", font=letra, fill=suave)
            return

        if fila.tipo == "libre":
            lz.create_text(xs[1] + pad, medio, text="Libre", anchor="w", font=letra, fill=suave)
            x = xs[2] + pad / 2
            limite = xs[-1] - pad / 2
            for cat, n in fila.libres.items():
                texto = f"+ {fmt.CATEGORIA[cat]}" + (f" · {n}" if n > 1 else "")
                w = letra.measure(texto) + 18 * e
                if x + w > limite:
                    texto = f"+ {fmt.CATEGORIA[cat][:3]}." + (f" {n}" if n > 1 else "")
                    w = letra.measure(texto) + 14 * e
                    if x + w > limite:
                        break
                accion = ("libre", fila.inicio, cat)
                lz.create_rectangle(x, y + 5 * e, x + w, y + alto - 5 * e, outline=c(tema.BORDE_CAMPO),
                                    fill=c(tema.SUPERFICIE), width=1, tags=("zona", f"z{len(self._zonas)}"))
                lz.create_text(x + w / 2, medio, text=texto, font=letra, fill=suave)
                self._zonas.append((x, y + 5 * e, x + w, y + alto - 5 * e, accion))
                x += w + 6 * e
            return

        item = fila.item
        turno = item.turno
        fondo_estado, letra_estado, _borde, nombre, icono = tema.estilo_estado(turno.estado)
        seleccionado = turno.id == self._seleccion
        indice = len(self._zonas)
        lz.create_rectangle(xs[1], y, xs[-1], y + alto, width=0,
                            fill=c(FONDO_SELECCION if seleccionado else tema.SUPERFICIE),
                            tags=("zona", f"z{indice}", "fondo"))
        self._zonas.append((xs[1], y, xs[-1], y + alto, ("turno", turno.id)))
        lz.tag_raise("vertical")
        if turno.faltante > 0:
            abono = f"{fmt.pesos(turno.abono_total)} de {fmt.pesos(turno.abono_requerido)}" if turno.abono_total \
                else "Sin abono"
        else:
            abono = fmt.pesos(turno.abono_total)
        celdas = [
            fmt.CATEGORIA[turno.categoria],
            item.mascota,
            item.raza or "—",
            fmt.SERVICIO[turno.servicio],
            item.propietario,
            fmt.celular(item.celular),
            abono,
        ]
        color = suave if grupo.pasada and turno.estado is EstadoTurno.ENTREGADO else tinta
        for i, texto in enumerate(celdas, start=1):
            fuente = letra_n if i == 2 else letra
            lz.create_text(xs[i] + pad, medio, text=self._recortar(texto, fuente, xs[i + 1] - xs[i] - pad * 1.5),
                           anchor="w", font=fuente, fill=color)
        # Estado: celda con el color del estado, como un relleno condicional.
        x0, x1 = xs[-2], xs[-1]
        lz.create_rectangle(x0 + 4 * e, y + 5 * e, x1 - 4 * e, y + alto - 5 * e, fill=c(fondo_estado), width=0)
        lz.create_text(x0 + pad, medio, text=self._recortar(f"{icono} {nombre}", letra_n, x1 - x0 - pad * 1.5),
                       anchor="w", font=letra_n, fill=c(letra_estado))

    # ------------------------------------------------------------------ ratón
    def _zona_en(self, evento) -> int | None:
        x, y = self.lienzo.canvasx(evento.x), self.lienzo.canvasy(evento.y)
        for i, (x0, y0, x1, y1, _a) in enumerate(self._zonas):
            if x0 <= x <= x1 and y0 <= y <= y1:
                return i
        return None

    def _mover(self, evento) -> None:
        self._resaltar(self._zona_en(evento))

    def _resaltar(self, indice: int | None) -> None:
        if indice == self._sobre:
            return
        c = self._color
        for anterior in (self._sobre,):
            if anterior is not None and anterior < len(self._zonas):
                accion = self._zonas[anterior][4]
                normal = FONDO_SELECCION if accion == ("turno", self._seleccion) else tema.SUPERFICIE
                self.lienzo.itemconfigure(f"z{anterior}", fill=c(normal))
        self._sobre = indice
        if indice is not None:
            accion = self._zonas[indice][4]
            if accion != ("turno", self._seleccion):
                self.lienzo.itemconfigure(f"z{indice}", fill=c(tema.HOVER_NEUTRO))
        self.lienzo.configure(cursor="hand2" if indice is not None else "")

    def _clic(self, evento) -> None:
        indice = self._zona_en(evento)
        if indice is None:
            return
        accion = self._zonas[indice][4]
        if accion[0] == "turno":
            self._al_turno(accion[1])
        else:
            self._al_libre(accion[1], accion[2])

    def _rueda(self, evento) -> None:
        try:
            widget = evento.widget
            if not isinstance(widget, tk.Misc) or not str(widget).startswith(str(self.lienzo)):
                return
        except Exception:
            return
        if getattr(evento, "num", None) == 4:
            pasos = -1
        elif getattr(evento, "num", None) == 5:
            pasos = 1
        else:
            pasos = -1 if evento.delta > 0 else 1
        if self.lienzo.yview() != (0.0, 1.0):
            self.lienzo.yview_scroll(pasos * 2, "units")


def agrupar(filas_tablero, orden: tuple[CategoriaCupo, ...]) -> list[GrupoHora]:
    """Convierte las filas del tablero (franjas con puestos) en grupos de filas de la hoja.

    Las franjas bloqueadas seguidas con el mismo motivo se juntan en una sola banda.
    """
    grupos: list[GrupoHora] = []
    for f in filas_tablero:
        if f.bloqueo:
            previo = grupos[-1] if grupos else None
            fin = f.inicio + timedelta(minutes=30)
            if previo and previo.filas[0].tipo == "bloqueo" and previo.filas[0].texto == f.bloqueo \
                    and previo.filas[0].hasta == f.inicio:
                previo.filas[0].hasta = fin
                continue
            grupos.append(GrupoHora(f.inicio, f.pasada, [FilaHoja("bloqueo", f.inicio, texto=f.bloqueo, hasta=fin)]))
            continue
        filas = [FilaHoja("turno", f.inicio, item=t) for cat in orden for t in f.puestos.get(cat, []) if t]
        libres = {cat: sum(1 for t in f.puestos.get(cat, []) if t is None) for cat in orden}
        libres = {cat: n for cat, n in libres.items() if n}
        if libres and not f.pasada:
            filas.append(FilaHoja("libre", f.inicio, libres=libres))
        if not filas:
            filas.append(FilaHoja("pasada", f.inicio))
        grupos.append(GrupoHora(f.inicio, f.pasada, filas))
    return grupos
