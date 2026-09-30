"""Pantallas de inicio de sesión y asistente del primer arranque."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from clinican.dominio.errores import ErrorClinican
from clinican.servicios import acceso, personal
from clinican.servicios.base import Sesion
from clinican.ui import tema


class _PantallaCentrada(ctk.CTkFrame):
    """Fondo claro con una tarjeta blanca al centro y la marca arriba."""

    def __init__(self, padre, config: dict[str, str]):
        super().__init__(padre, fg_color=tema.FONDO, corner_radius=0)
        self.tarjeta = tema.tarjeta(self)
        self.tarjeta.place(relx=0.5, rely=0.5, anchor="center")

        marca = ctk.CTkFrame(self.tarjeta, fg_color=tema.VERDE, corner_radius=12)
        marca.pack(fill="x", padx=18, pady=(18, 8))
        imagen = tema.logo(110)
        if imagen:
            ctk.CTkLabel(marca, text="", image=imagen).pack(side="left", padx=(16, 8), pady=10)
        textos = ctk.CTkFrame(marca, fg_color="transparent")
        textos.pack(side="left", padx=(0, 24), pady=10)
        tema.etiqueta(textos, config.get("negocio_nombre", "CLINICAN"), 40, negrita=True).pack(anchor="w")
        tema.etiqueta(textos, config.get("negocio_descripcion", ""), tema.TAM_PEQUENO, negrita=True).pack(anchor="w")

        self.cuerpo = ctk.CTkFrame(self.tarjeta, fg_color="transparent")
        self.cuerpo.pack(fill="both", padx=40, pady=(12, 32))

        self.mensaje = tema.etiqueta(self.tarjeta, "", color=tema.ROJO_ERROR, negrita=True, wraplength=520)

    def mostrar_error(self, texto: str) -> None:
        self.mensaje.configure(text=texto)
        self.mensaje.pack(before=self.cuerpo, padx=40, pady=(6, 0), anchor="w")

    def campo(self, texto: str, widget_fabrica) -> ctk.CTkBaseClass:
        tema.etiqueta(self.cuerpo, texto, negrita=True).pack(anchor="w", pady=(12, 4))
        widget = widget_fabrica(self.cuerpo)
        widget.pack(anchor="w", fill="x")
        return widget


class PantallaInicioSesion(_PantallaCentrada):
    def __init__(self, padre, conn, config: dict[str, str], al_entrar: Callable[[Sesion], None]):
        super().__init__(padre, config)
        self.conn = conn
        self.al_entrar = al_entrar

        tema.subtitulo(self.cuerpo, "Iniciar sesión").pack(anchor="w", pady=(0, 4))
        nombres = [f["nombre"] for f in personal.listar_activos(conn)]
        self.usuario = self.campo("¿Quién es usted?", lambda p: tema.selector(p, nombres, ancho=420))
        self.usuario.set(nombres[0] if nombres else "")
        self.pin = self.campo("PIN (4 a 6 números)", lambda p: tema.entrada(p, ancho=420, oculto=True))
        self.pin.bind("<Return>", lambda _e: self._entrar())

        tema.boton(self.cuerpo, "Entrar", self._entrar, ancho=420).pack(anchor="w", pady=(24, 0))
        tema.enfocar_luego(self.pin, 200)

    def _entrar(self) -> None:
        try:
            sesion = acceso.iniciar_sesion(self.conn, self.usuario.get(), self.pin.get())
        except ErrorClinican as e:
            self.pin.delete(0, "end")
            self.mostrar_error(str(e))
            return
        self.al_entrar(sesion)


class PantallaPrimerArranque(_PantallaCentrada):
    def __init__(self, padre, conn, config: dict[str, str], al_entrar: Callable[[Sesion], None]):
        super().__init__(padre, config)
        self.conn = conn
        self.al_entrar = al_entrar

        tema.subtitulo(self.cuerpo, "¡Bienvenida a CLINICAN!").pack(anchor="w")
        tema.etiqueta(
            self.cuerpo,
            "Es la primera vez que se abre el programa. Cree la cuenta de la administradora "
            "(la jefe). Después podrá agregar al resto del personal.",
            wraplength=520,
        ).pack(anchor="w", pady=(4, 0))

        self.nombre = self.campo("Nombre (con este nombre iniciará sesión)", lambda p: tema.entrada(p, ancho=420))
        self.cargo = self.campo("Cargo", lambda p: tema.entrada(p, ancho=420))
        self.cargo.insert(0, "Jefe")
        self.pin = self.campo("PIN de 4 a 6 números", lambda p: tema.entrada(p, ancho=420, oculto=True))
        self.pin2 = self.campo("Repita el PIN", lambda p: tema.entrada(p, ancho=420, oculto=True))
        self.pin2.bind("<Return>", lambda _e: self._crear())

        tema.boton(self.cuerpo, "Crear cuenta y entrar", self._crear, ancho=420).pack(anchor="w", pady=(24, 0))
        tema.enfocar_luego(self.nombre, 200)

    def _crear(self) -> None:
        if self.pin.get() != self.pin2.get():
            self.mostrar_error("Los dos PIN no coinciden. Escríbalos de nuevo.")
            return
        try:
            sesion = acceso.crear_administradora_inicial(self.conn, self.nombre.get(), self.cargo.get(), self.pin.get())
        except ErrorClinican as e:
            self.mostrar_error(str(e))
            return
        self.al_entrar(sesion)
