"""Cada persona puede cambiar su propio PIN."""

from __future__ import annotations

import customtkinter as ctk

from clinican.servicios import acceso
from clinican.ui import dialogos, tema


class PantallaMiPin(ctk.CTkFrame):
    def __init__(self, padre, ctx):
        super().__init__(padre, fg_color="transparent")
        self.ctx = ctx
        tema.titulo(self, "Cambiar mi PIN").pack(anchor="w", pady=(0, 16))

        t = tema.tarjeta(self)
        t.pack(anchor="w")
        cuerpo = ctk.CTkFrame(t, fg_color="transparent")
        cuerpo.pack(padx=32, pady=24)

        def campo(texto):
            tema.etiqueta(cuerpo, texto, negrita=True).pack(anchor="w", pady=(10, 4))
            e = tema.entrada(cuerpo, ancho=360, oculto=True)
            e.pack(anchor="w")
            return e

        self.actual = campo("PIN actual")
        self.nuevo = campo("PIN nuevo (4 a 6 números)")
        self.repetir = campo("Repita el PIN nuevo")
        self.repetir.bind("<Return>", lambda _e: self._guardar())
        tema.boton(cuerpo, "Guardar PIN nuevo", self._guardar, ancho=360).pack(anchor="w", pady=(22, 0))

    def _guardar(self) -> None:
        if self.nuevo.get() != self.repetir.get():
            dialogos.error(self, "El PIN nuevo y su repetición no coinciden.")
            return
        r = dialogos.ejecutar(self, acceso.cambiar_mi_pin, self.ctx.conn, self.ctx.sesion, self.actual.get(), self.nuevo.get())
        for e in (self.actual, self.nuevo, self.repetir):
            e.delete(0, "end")
        if r is not dialogos.FALLO:
            dialogos.aviso(self, "PIN cambiado", "Su PIN quedó cambiado. Úselo la próxima vez que inicie sesión.")
