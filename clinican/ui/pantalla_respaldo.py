"""Respaldo (pantalla 11): «Respaldar ahora», lista de copias y restaurar (solo la administradora)."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from clinican import rutas
from clinican.dominio.permisos import Accion
from clinican.servicios import respaldos
from clinican.ui import dialogos, tema

log = logging.getLogger(__name__)


class PantallaRespaldo(ctk.CTkFrame):
    def __init__(self, padre, ctx):
        super().__init__(padre, fg_color="transparent")
        self.ctx = ctx
        self.carpeta = rutas.carpeta_respaldos()
        self.lista: dict[str, respaldos.Respaldo] = {}
        puede_restaurar = ctx.sesion.puede(Accion.RESTAURAR)

        tema.titulo(self, "Respaldo").pack(anchor="w", pady=(0, 12))

        caja = tema.tarjeta(self)
        caja.pack(fill="x", pady=(0, 14))
        cuerpo = ctk.CTkFrame(caja, fg_color="transparent")
        cuerpo.pack(fill="x", padx=22, pady=18)
        conservar = ctx.config().get("respaldos_conservar", "30")
        tema.etiqueta(
            cuerpo,
            f"El programa guarda un respaldo automático al cerrarse y una vez al día en {self.carpeta} "
            f"(se conservan los últimos {conservar}).\nPara tener una copia fuera del computador, conecte una "
            "memoria USB y pulse «Respaldar ahora en USB u otra carpeta».",
            wraplength=980,
        ).pack(anchor="w")
        self.lbl_ultimo = tema.etiqueta(cuerpo, "", negrita=True)
        self.lbl_ultimo.pack(anchor="w", pady=(10, 0))
        botones = ctk.CTkFrame(cuerpo, fg_color="transparent")
        botones.pack(anchor="w", pady=(14, 0))
        tema.boton(botones, "Respaldar ahora en USB u otra carpeta", self._elegir_carpeta, ancho=380).pack(side="left")
        tema.boton(botones, "Respaldar ahora aquí", lambda: self._respaldar_en(self.carpeta),
                   estilo="secundario", ancho=240).pack(side="left", padx=12)
        if sys.platform == "win32":
            tema.boton(botones, "Abrir carpeta de respaldos", self._abrir_carpeta, estilo="secundario",
                       ancho=270).pack(side="left")

        tema.subtitulo(self, "Copias guardadas en este computador").pack(anchor="w", pady=(4, 8))
        self.tabla = tema.tabla(
            self,
            [("fecha", "Fecha y hora", 200), ("tipo", "Tipo", 190), ("tamano", "Tamaño", 110), ("archivo", "Archivo", 460)],
            alto=10,
        )
        self.tabla.marco.pack(fill="both", expand=True)

        if puede_restaurar:
            abajo = ctk.CTkFrame(self, fg_color="transparent")
            abajo.pack(fill="x", pady=(12, 0))
            tema.boton(abajo, "Restaurar la copia elegida", self._restaurar_elegida, estilo="peligro",
                       ancho=300).pack(side="left")
            tema.boton(abajo, "Restaurar desde un archivo (USB)…", self._restaurar_archivo, estilo="secundario",
                       ancho=340).pack(side="left", padx=12)
            tema.etiqueta(self, "Restaurar reemplaza TODOS los datos actuales por los de la copia. Antes se guarda "
                                "una copia del estado actual para poder deshacerlo.",
                          tema.TAM_PEQUENO, color=tema.GRIS_TEXTO, wraplength=980).pack(anchor="w", pady=(8, 0))
        else:
            tema.etiqueta(self, "Solo la administradora puede restaurar una copia.", tema.TAM_PEQUENO,
                          color=tema.GRIS_TEXTO).pack(anchor="w", pady=(10, 0))
        self._cargar()

    # ------------------------------------------------------------------ lista
    def _cargar(self) -> None:
        self.tabla.delete(*self.tabla.get_children())
        self.lista = {}
        for i, r in enumerate(respaldos.listar(self.carpeta)):
            iid = str(i)
            self.lista[iid] = r
            self.tabla.insert("", "end", iid=iid, tags=["par"] if i % 2 else [],
                              values=(r.fecha.strftime("%Y-%m-%d %H:%M"), r.nombre_tipo, r.tamano_texto, r.ruta.name))
        automaticos = [r for r in self.lista.values() if r.tipo == respaldos.AUTOMATICO]
        if automaticos:
            self.lbl_ultimo.configure(text=f"✔ Último respaldo automático: {automaticos[0].fecha:%Y-%m-%d %H:%M}")
        else:
            self.lbl_ultimo.configure(text="Todavía no hay respaldos automáticos (se crea uno al cerrar el programa).")

    # --------------------------------------------------------------- respaldar
    def _elegir_carpeta(self) -> None:
        carpeta = filedialog.askdirectory(parent=self, title="Elija la memoria USB o la carpeta del respaldo",
                                          mustexist=True)
        if carpeta:
            self._respaldar_en(Path(carpeta))

    def _respaldar_en(self, carpeta: Path) -> None:
        ruta = dialogos.ejecutar(self, respaldos.respaldar_ahora, self.ctx.conn, self.ctx.sesion, carpeta)
        if ruta is dialogos.FALLO:
            return
        self._cargar()
        dialogos.aviso(self, "Respaldo guardado", f"La copia quedó guardada en:\n{ruta}")

    def _abrir_carpeta(self) -> None:
        try:
            self.carpeta.mkdir(parents=True, exist_ok=True)
            os.startfile(self.carpeta)  # type: ignore[attr-defined]  # solo existe en Windows
        except OSError:
            log.exception("No se pudo abrir la carpeta de respaldos")
            dialogos.error(self, f"No se pudo abrir la carpeta {self.carpeta}.")

    # --------------------------------------------------------------- restaurar
    def _restaurar_elegida(self) -> None:
        sel = self.tabla.selection()
        if not sel:
            dialogos.error(self, "Elija primero en la lista la copia que quiere restaurar.")
            return
        self._restaurar_desde(self.lista[sel[0]].ruta)

    def _restaurar_archivo(self) -> None:
        ruta = filedialog.askopenfilename(parent=self, title="Elija el respaldo de CLINICAN",
                                          filetypes=[("Respaldo de CLINICAN", "*.db"), ("Todos los archivos", "*.*")])
        if ruta:
            self._restaurar_desde(Path(ruta))

    def _restaurar_desde(self, ruta: Path) -> None:
        resumen = dialogos.ejecutar(self, respaldos.revisar, ruta)
        if resumen is dialogos.FALLO:
            return
        if not dialogos.confirmar(
            self, "Restaurar respaldo",
            f"Se reemplazarán TODOS los datos actuales por los de la copia:\n{ruta.name}\n\n"
            f"La copia tiene {resumen['propietarios']} propietario(s), {resumen['mascotas']} mascota(s) y "
            f"{resumen['turnos']} turno(s).\n\nAntes se guardará una copia del estado actual. Después deberán "
            "iniciar sesión de nuevo. ¿Continuar?",
            si="Sí, restaurar",
        ):
            return
        previa = dialogos.ejecutar(self, respaldos.restaurar, self.ctx.conn, self.ctx.sesion, ruta)
        if previa is dialogos.FALLO:
            return
        dialogos.aviso(self, "Respaldo restaurado",
                       "Los datos se restauraron. Por seguridad, inicie sesión de nuevo.\n\n"
                       f"El estado anterior quedó guardado en:\n{previa}")
        # El personal del respaldo puede ser distinto: se vuelve al inicio de sesión sin
        # registrar el cierre (la persona podría no existir en los datos restaurados).
        raiz = self.winfo_toplevel()
        raiz.after(0, raiz.mostrar_acceso)
