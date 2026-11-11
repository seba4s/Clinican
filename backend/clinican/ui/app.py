"""Ventana principal: barra lateral con cuatro secciones y el contenido a la derecha."""

from __future__ import annotations

import logging
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from clinican.dominio.entidades import EstadoNotificacion
from clinican.dominio.errores import ErrorNegocio
from clinican.servicios import consultas
from clinican.ui import tema
from clinican.ui.componentes import Aviso, etiqueta
from clinican.ui.contexto import Contexto

registro = logging.getLogger("clinican.ui")

LOGO = Path(__file__).resolve().parent / "recursos" / "logo_perro.png"
REFRESCO_MS = 30_000


class Pantalla(ctk.CTkFrame):
    """Base de cada sección. ``refrescar`` vuelve a leer la base y redibuja."""

    titulo = ""

    def __init__(self, app: "App"):
        super().__init__(app.contenido, fg_color="transparent")
        self.app = app
        self.ctx: Contexto = app.ctx

    def refrescar(self) -> None:  # pragma: no cover - cada pantalla la define
        pass

    def refrescar_periodico(self) -> None:
        """Lo que se redibuja cada 30 s; por defecto, todo."""
        self.refrescar()

    def avisar(self, mensaje: str, error: bool = False) -> None:
        self.app.aviso.mostrar(mensaje, error)

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
            self.app.aviso.ocultar()
        self.refrescar()
        self.app.actualizar_insignias()
        return True


class App(ctk.CTk):
    SECCIONES = ("Agenda", "Clientes", "Recordatorios", "Ajustes")

    def __init__(self, ctx: Contexto):
        tema.configurar()
        super().__init__(fg_color=tema.FONDO)
        self.ctx = ctx
        self.title("Clinican")
        self.geometry("1320x840")
        self.minsize(1024, 680)
        try:
            self.iconbitmap(default=str(LOGO.with_suffix(".ico")))
        except Exception:
            pass

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._barra_lateral()

        derecha = ctk.CTkFrame(self, fg_color="transparent")
        derecha.grid(row=0, column=1, sticky="nsew")
        self.aviso = Aviso(derecha)
        self.contenido = ctk.CTkFrame(derecha, fg_color="transparent")
        self.contenido.pack(fill="both", expand=True)
        self.aviso.colocar(self.contenido)

        from clinican.ui.pantalla_agenda import PantallaAgenda
        from clinican.ui.pantalla_ajustes import PantallaAjustes
        from clinican.ui.pantalla_clientes import PantallaClientes
        from clinican.ui.pantalla_recordatorios import PantallaRecordatorios

        self._clases = {
            "Agenda": PantallaAgenda,
            "Clientes": PantallaClientes,
            "Recordatorios": PantallaRecordatorios,
            "Ajustes": PantallaAjustes,
        }
        self.pantallas: dict[str, Pantalla] = {}
        self.actual: str | None = None

        self.bind_all("<Control-n>", lambda _e: self.nuevo_turno())
        self.bind_all("<Control-N>", lambda _e: self.nuevo_turno())
        self.bind_all("<Control-f>", lambda _e: self.buscar_cliente())
        self.bind_all("<Control-F>", lambda _e: self.buscar_cliente())
        for i, nombre in enumerate(self.SECCIONES, start=1):
            self.bind_all(f"<Control-Key-{i}>", lambda _e, n=nombre: self.ir(n))

        self.ir("Agenda")
        self.actualizar_insignias()
        self.after(REFRESCO_MS, self._refresco_periodico)

    # ------------------------------------------------------------------ barra lateral
    def _barra_lateral(self) -> None:
        barra = ctk.CTkFrame(self, fg_color=tema.SUPERFICIE, corner_radius=0, width=220)
        barra.grid(row=0, column=0, sticky="ns")
        barra.grid_propagate(False)
        marca = ctk.CTkFrame(barra, fg_color="transparent")
        marca.pack(fill="x", padx=20, pady=(20, 18))
        try:
            imagen = ctk.CTkImage(Image.open(LOGO), size=(36, 36))
            ctk.CTkLabel(marca, text="", image=imagen).pack(side="left")
        except Exception:
            pass
        etiqueta(marca, "Clinican", 18, True).pack(side="left", padx=10)

        self._botones_menu: dict[str, ctk.CTkButton] = {}
        for i, nombre in enumerate(self.SECCIONES, start=1):
            b = ctk.CTkButton(barra, text=nombre, anchor="w", height=tema.ALTO_CONTROL, corner_radius=tema.RADIO,
                              font=tema.fuente(tema.CUERPO), fg_color="transparent", text_color=tema.TINTA,
                              hover_color=tema.HOVER_NEUTRO, command=lambda n=nombre: self.ir(n))
            b.pack(fill="x", padx=12, pady=2)
            self._botones_menu[nombre] = b
        etiqueta(barra, "Ctrl+1 a Ctrl+4 cambian de sección", tema.ETIQUETA, suave=True,
                 wraplength=180).pack(fill="x", padx=24, pady=(16, 0))

    def _marcar_menu(self) -> None:
        for nombre, b in self._botones_menu.items():
            activo = nombre == self.actual
            b.configure(fg_color=tema.SELECCION_FONDO if activo else "transparent",
                        text_color=tema.SELECCION_TEXTO if activo else tema.TINTA,
                        hover_color=tema.SELECCION_FONDO if activo else tema.HOVER_NEUTRO,
                        font=tema.fuente(tema.CUERPO, activo))

    def actualizar_insignias(self) -> None:
        """Muestra en la barra cuántos recordatorios fallaron."""
        try:
            with self.ctx.con() as con:
                fallidas = consultas.estado_bandeja(con, limite=1).conteo.get(EstadoNotificacion.FALLIDA, 0)
        except Exception:  # la insignia nunca debe tumbar la ventana
            registro.exception("No se pudo leer la bandeja")
            return
        texto = "Recordatorios" + (f"   ·  {fallidas} fallido{'s' if fallidas != 1 else ''}" if fallidas else "")
        self._botones_menu["Recordatorios"].configure(text=texto)

    # ------------------------------------------------------------------ navegación
    def ir(self, nombre: str) -> Pantalla:
        if self.actual and self.actual in self.pantallas:
            self.pantallas[self.actual].pack_forget()
        if nombre not in self.pantallas:
            self.pantallas[nombre] = self._clases[nombre](self)
        pantalla = self.pantallas[nombre]
        pantalla.pack(fill="both", expand=True)
        self.actual = nombre
        self.aviso.ocultar()
        self._marcar_menu()
        pantalla.refrescar()
        return pantalla

    def nuevo_turno(self, **datos) -> None:
        if self._hay_dialogo():
            return
        agenda = self.ir("Agenda")
        agenda.nuevo_turno(**datos)

    def buscar_cliente(self) -> None:
        if self._hay_dialogo():
            return
        self.ir("Clientes").enfocar_busqueda()

    def _hay_dialogo(self) -> bool:
        return any(isinstance(w, ctk.CTkToplevel) and w.winfo_exists() for w in self.winfo_children())

    def _refresco_periodico(self) -> None:
        try:
            if self.actual and not self._hay_dialogo():
                self.pantallas[self.actual].refrescar_periodico()
                self.actualizar_insignias()
        except Exception:
            registro.exception("Falló el refresco periódico")
        self.after(REFRESCO_MS, self._refresco_periodico)


def ejecutar(ctx: Contexto) -> None:
    app = App(ctx)
    app.mainloop()
