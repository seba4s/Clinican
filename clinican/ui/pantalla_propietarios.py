"""Propietarios y mascotas: búsqueda, alta, edición, consentimientos e importación."""

from __future__ import annotations

from tkinter import filedialog

import customtkinter as ctk

from clinican.dominio.propietarios import formato_celular
from clinican.servicios import importacion, propietarios
from clinican.ui import dialogos, tema
from clinican.ui.ficha_propietario import DetallePropietario


class PantallaPropietarios(ctk.CTkFrame):
    def __init__(self, padre, ctx, propietario_id: int | None = None, pestana: str | None = None,
                 mascota_id: int | None = None):
        super().__init__(padre, fg_color="transparent")
        self.ctx = ctx
        self.detalle: ctk.CTkFrame | None = None
        self._mascota_inicial = mascota_id
        self._pid_detalle = None

        arriba = ctk.CTkFrame(self, fg_color="transparent")
        arriba.pack(fill="x", pady=(0, 12))
        tema.titulo(arriba, "Propietarios y mascotas").pack(side="left")
        tema.boton(arriba, "Importar desde Excel", self._importar, estilo="secundario", ancho=220).pack(side="right")
        tema.boton(arriba, "+ Nuevo propietario", self._nuevo, ancho=230).pack(side="right", padx=(0, 12))

        busqueda = ctk.CTkFrame(self, fg_color="transparent")
        busqueda.pack(fill="x", pady=(0, 12))
        self.texto = tema.entrada(busqueda, ancho=520, placeholder_text="Cédula, nombre, celular o nombre de la mascota")
        self.texto.pack(side="left")
        self.texto.bind("<Return>", lambda _e: self.buscar())
        tema.boton(busqueda, "Buscar", self.buscar, ancho=140).pack(side="left", padx=(12, 0))

        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True)
        cuerpo.grid_columnconfigure(0, weight=2, uniform="c")
        cuerpo.grid_columnconfigure(1, weight=3, uniform="c")
        cuerpo.grid_rowconfigure(0, weight=1)

        self.tabla = tema.tabla(
            cuerpo,
            [("nombre", "Propietario", 200), ("cedula", "Cédula", 120), ("celular", "Celular", 130), ("mascotas", "Mascotas", 180)],
        )
        self.tabla.marco.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        self.tabla.bind("<<TreeviewSelect>>", lambda _e: self._al_seleccionar())

        self.zona_detalle = ctk.CTkFrame(cuerpo, fg_color="transparent")
        self.zona_detalle.grid(row=0, column=1, sticky="nsew")
        self._mostrar_vacio()
        self.buscar()
        if propietario_id is not None:
            self.buscar(seleccionar=propietario_id)  # dispara la selección
            self._mostrar_detalle(propietario_id, pestana)
        self.after(150, self.texto.focus_set)

    # --------------------------------------------------------------- lista
    def buscar(self, seleccionar: int | None = None) -> None:
        filas = dialogos.ejecutar(self, propietarios.buscar, self.ctx.conn, self.ctx.sesion, self.texto.get())
        if filas is dialogos.FALLO:
            return
        self.tabla.delete(*self.tabla.get_children())
        for i, f in enumerate(filas):
            self.tabla.insert(
                "", "end", iid=str(f["id"]), tags=["par"] if i % 2 else [],
                values=(f["nombre"], f["cedula"], formato_celular(f["celular1"]), f["mascotas"] or "—"),
            )
        if seleccionar is not None and self.tabla.exists(str(seleccionar)):
            self.tabla.selection_set(str(seleccionar))
            self.tabla.see(str(seleccionar))

    def _al_seleccionar(self) -> None:
        sel = self.tabla.selection()
        # selection_set() también dispara este evento; si ese propietario ya está
        # abierto no se reconstruye (se perdería la pestaña elegida).
        if sel and int(sel[0]) != self._pid_detalle:
            self._mostrar_detalle(int(sel[0]))

    # ------------------------------------------------------------- detalle
    def _limpiar_detalle(self) -> None:
        for hijo in self.zona_detalle.winfo_children():
            hijo.destroy()

    def _mostrar_vacio(self) -> None:
        self._limpiar_detalle()
        self._pid_detalle = None
        t = tema.tarjeta(self.zona_detalle)
        t.pack(fill="both", expand=True)
        tema.etiqueta(
            t, "Busque y elija un propietario de la lista,\no pulse «+ Nuevo propietario».",
            tema.TAM_SUBTITULO, color=tema.GRIS_TEXTO, justify="center", anchor="center",
        ).pack(expand=True)

    def _mostrar_detalle(self, propietario_id: int | None, pestana: str | None = None) -> None:
        self._limpiar_detalle()
        self._pid_detalle = propietario_id
        mascota, self._mascota_inicial = self._mascota_inicial, None
        self.detalle = DetallePropietario(self.zona_detalle, self.ctx, propietario_id, self._al_guardar, pestana, mascota)
        self.detalle.pack(fill="both", expand=True)

    def _nuevo(self) -> None:
        if self.tabla.selection():
            self.tabla.selection_remove(self.tabla.selection())
        self._mostrar_detalle(None)

    def _al_guardar(self, propietario_id: int, pestana: str | None = None, mascota_id: int | None = None) -> None:
        """Después de crear o editar: refresca la lista y reabre el detalle."""
        self._mascota_inicial = mascota_id
        self.buscar(seleccionar=propietario_id)
        self._mostrar_detalle(propietario_id, pestana)

    # ---------------------------------------------------------- importación
    def _importar(self) -> None:
        eleccion = dialogos.elegir(
            self, "Importar mascotas desde Excel",
            "Use la plantilla de importación (una fila por mascota). Primero se revisa el archivo "
            "y se le muestra qué se importará, antes de guardar nada.",
            [("Elegir archivo lleno", "importar"), ("Guardar plantilla vacía", "plantilla")],
            detalle="Pasos:\n1. Guarde la plantilla y llénela en Excel.\n2. Vuelva aquí y pulse «Elegir archivo lleno».\n"
            "3. Revise el reporte y confirme.\n\nLos consentimientos no se importan: cada propietario debe "
            "aceptarlos antes de su primer turno.",
        )
        if eleccion == "importar":
            self._importar_archivo()
        elif eleccion == "plantilla":
            self._guardar_plantilla()

    def _guardar_plantilla(self) -> None:
        ruta = filedialog.asksaveasfilename(
            parent=self, title="Guardar plantilla", defaultextension=".xlsx",
            initialfile="plantilla_importacion.xlsx", filetypes=[("Excel", "*.xlsx")],
        )
        if not ruta:
            return
        if dialogos.ejecutar(self, importacion.generar_plantilla, self.ctx.conn, ruta) is not dialogos.FALLO:
            dialogos.aviso(self, "Plantilla guardada", f"Se guardó en:\n{ruta}")

    def _importar_archivo(self) -> None:
        ruta = filedialog.askopenfilename(parent=self, title="Elegir archivo de Excel", filetypes=[("Excel", "*.xlsx")])
        if not ruta:
            return
        previo = dialogos.ejecutar(self, importacion.importar, self.ctx.conn, self.ctx.sesion, ruta, solo_validar=True)
        if previo is dialogos.FALLO:
            return
        if previo.mascotas_nuevas == 0:
            dialogos.reporte(self, "Nada para importar", previo.resumen(), _detalle(previo))
            return
        if not dialogos.reporte(self, "Revisión del archivo", previo.resumen(), _detalle(previo),
                                si=f"Importar {previo.mascotas_nuevas} mascota(s)", no="Cancelar"):
            return
        final = dialogos.ejecutar(self, importacion.importar, self.ctx.conn, self.ctx.sesion, ruta)
        if final is dialogos.FALLO:
            return
        dialogos.reporte(self, "Importación terminada", final.resumen(), _detalle(final))
        self.texto.delete(0, "end")
        self.buscar()


def _detalle(reporte) -> str:
    partes = []
    if reporte.rechazadas:
        partes.append("FILAS RECHAZADAS (no se importan):")
        partes += [f"  Fila {n}: {motivo}" for n, motivo in reporte.rechazadas]
    if reporte.avisos:
        partes.append("\nAVISOS:")
        partes += [f"  Fila {n}: {motivo}" for n, motivo in reporte.avisos]
    return "\n".join(partes) or "Todas las filas son válidas."
