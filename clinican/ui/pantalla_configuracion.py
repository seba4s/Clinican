"""Configuración (solo la administradora): valores, razas y textos legales."""

from __future__ import annotations

from itertools import groupby

import customtkinter as ctk

from clinican.dominio import config_claves as cc
from clinican.dominio.catalogos import TAMANOS, TIPOS_LEGALES, nombre_tamano
from clinican.dominio.formato import rellenar_texto
from clinican.servicios import configuracion, legal, razas
from clinican.ui import dialogos, tema

SE_ELIGE = "Se elige por mascota"


class PantallaConfiguracion(ctk.CTkFrame):
    def __init__(self, padre, ctx):
        super().__init__(padre, fg_color="transparent")
        self.ctx = ctx
        tema.titulo(self, "Configuración").pack(anchor="w", pady=(0, 10))
        self.pestanas = ctk.CTkTabview(
            self, fg_color=tema.BLANCO, border_width=1, border_color=tema.BORDE, corner_radius=14,
            segmented_button_fg_color=tema.GRIS_BOTON, segmented_button_selected_color=tema.VERDE,
            segmented_button_selected_hover_color=tema.VERDE_HOVER, segmented_button_unselected_color=tema.GRIS_BOTON,
            segmented_button_unselected_hover_color=tema.GRIS_BOTON_HOVER, text_color=tema.NEGRO,
        )
        self.pestanas._segmented_button.configure(font=tema.fuente(tema.TAM_NORMAL, True), height=44)
        self.pestanas.pack(fill="both", expand=True)
        for nombre in ("Precios y valores", "Razas", "Textos legales"):
            self.pestanas.add(nombre)
        self._valores(self.pestanas.tab("Precios y valores"))
        self.tab_razas = self.pestanas.tab("Razas")
        self._razas()
        self._textos(self.pestanas.tab("Textos legales"))

    # ============================================================ valores
    def _valores(self, tab) -> None:
        arriba = ctk.CTkFrame(tab, fg_color="transparent")
        arriba.pack(fill="x", padx=10, pady=(6, 4))
        tema.etiqueta(arriba, "Los montos van en pesos, sin decimales (por ejemplo 45000 o 45.000).",
                      color=tema.GRIS_TEXTO).pack(side="left")
        tema.boton(arriba, "Guardar cambios", self._guardar_valores, ancho=220).pack(side="right")

        zona = ctk.CTkScrollableFrame(tab, fg_color=tema.BLANCO)
        zona.pack(fill="both", expand=True)
        zona.grid_columnconfigure(0, weight=0)
        zona.grid_columnconfigure(1, weight=1)
        actuales = configuracion.valores(self.ctx.conn)
        self.widgets: dict[str, tuple[cc.ClaveConfig, object]] = {}
        fila = 0
        for grupo, claves in groupby(cc.CLAVES, key=lambda c: c.grupo):
            tema.subtitulo(zona, grupo).grid(row=fila, column=0, columnspan=2, sticky="w", padx=12, pady=(18, 6))
            fila += 1
            for meta in claves:
                texto = meta.etiqueta + (f"\n{meta.ayuda}" if meta.ayuda else "")
                tema.etiqueta(zona, texto, wraplength=460).grid(row=fila, column=0, sticky="w", padx=(12, 20), pady=5)
                valor = actuales.get(meta.clave, "")
                if meta.tipo == cc.SI_NO:
                    w = tema.selector(zona, ["Sí", "No"], ancho=180)
                    w.set("Sí" if valor == "1" else "No")
                elif meta.tipo == cc.OPCION:
                    w = tema.selector(zona, list(meta.opciones), ancho=260)
                    w.set(valor)
                else:
                    ancho = 420 if meta.tipo == cc.TEXTO else 200
                    w = tema.entrada(zona, ancho=ancho)
                    w.insert(0, valor)
                w.grid(row=fila, column=1, sticky="w", pady=5)
                self.widgets[meta.clave] = (meta, w)
                fila += 1

    def _guardar_valores(self) -> None:
        cambios = {}
        for clave, (meta, w) in self.widgets.items():
            valor = w.get()
            if meta.tipo == cc.SI_NO:
                valor = "1" if valor == "Sí" else "0"
            cambios[clave] = valor
        r = dialogos.ejecutar(self, configuracion.guardar, self.ctx.conn, self.ctx.sesion, cambios)
        if r is dialogos.FALLO:
            return
        if not r:
            dialogos.aviso(self, "Sin cambios", "No había cambios para guardar.")
            return
        nombres = "\n".join(f"• {cc.POR_CLAVE[c].etiqueta}" for c in r)
        dialogos.aviso(self, "Configuración guardada", f"Se cambiaron {len(r)} valor(es):\n{nombres}")

    # ============================================================== razas
    def _razas(self, seleccionar: int | None = None) -> None:
        tab = self.tab_razas
        for hijo in tab.winfo_children():
            hijo.destroy()
        tab.grid_columnconfigure(0, weight=3)
        tab.grid_columnconfigure(1, weight=2)
        tab.grid_rowconfigure(0, weight=1)
        t = tema.tabla(tab, [("nombre", "Raza", 260), ("tamano", "Tamaño", 170), ("pelaje", "Pelaje complicado", 150),
                             ("activa", "Estado", 100)])
        t.marco.grid(row=0, column=0, sticky="nsew", padx=(6, 14), pady=6)
        filas = {str(r["id"]): r for r in razas.listar(self.ctx.conn, solo_activas=False)}
        for i, r in enumerate(filas.values()):
            etiquetas = (["par"] if i % 2 else []) + ([] if r["activa"] else ["inactivo"])
            t.insert("", "end", iid=str(r["id"]), tags=etiquetas, values=(
                r["nombre"], nombre_tamano(r["tamano"]) if r["tamano"] else SE_ELIGE,
                "Sí" if r["pelaje_complicado"] else "No", "Activa" if r["activa"] else "Inactiva"))
        panel = ctk.CTkFrame(tab, fg_color="transparent")
        panel.grid(row=0, column=1, sticky="nsew", pady=6)

        def formulario(r=None):
            for hijo in panel.winfo_children():
                hijo.destroy()
            tema.subtitulo(panel, r["nombre"] if r else "Nueva raza").pack(anchor="w", pady=(0, 8))
            tema.etiqueta(panel, "Nombre", negrita=True).pack(anchor="w", pady=(6, 4))
            nombre = tema.entrada(panel, ancho=340)
            nombre.pack(anchor="w")
            tema.etiqueta(panel, "Tamaño", negrita=True).pack(anchor="w", pady=(10, 4))
            opciones = {**{v: k for k, v in TAMANOS.items()}, SE_ELIGE: None}
            tamano = tema.selector(panel, list(opciones), ancho=340)
            tamano.pack(anchor="w")
            pelaje = ctk.IntVar(value=r["pelaje_complicado"] if r else 0)
            tema.casilla(panel, "Pelaje complicado (husky o razas similares)", pelaje).pack(anchor="w", pady=(14, 0))
            activa = ctk.IntVar(value=r["activa"] if r else 1)
            tema.casilla(panel, "Activa (aparece al registrar mascotas)", activa).pack(anchor="w", pady=(10, 0))
            if r:
                nombre.insert(0, r["nombre"])
                tamano.set(nombre_tamano(r["tamano"]) if r["tamano"] else SE_ELIGE)
            else:
                tamano.set("Mediana")

            def guardar():
                args = (nombre.get(), opciones[tamano.get()], bool(pelaje.get()))
                if r is None:
                    res = dialogos.ejecutar(self, razas.crear, self.ctx.conn, self.ctx.sesion, *args)
                    rid = res
                else:
                    res = dialogos.ejecutar(self, razas.editar, self.ctx.conn, self.ctx.sesion, r["id"], *args, bool(activa.get()))
                    rid = r["id"]
                if res is not dialogos.FALLO:
                    dialogos.aviso(self, "Raza guardada", f"Se guardó la raza «{nombre.get().strip()}».")
                    self._razas(seleccionar=rid)

            tema.boton(panel, "Guardar raza", guardar, ancho=340).pack(anchor="w", pady=(20, 6))
            if r:
                tema.boton(panel, "+ Nueva raza", lambda: (t.selection_remove(t.selection()), formulario(None)),
                           estilo="secundario", ancho=340).pack(anchor="w", pady=6)

        t.bind("<<TreeviewSelect>>", lambda _e: t.selection() and formulario(filas[t.selection()[0]]))
        if seleccionar is not None and t.exists(str(seleccionar)):
            t.selection_set(str(seleccionar))
            t.see(str(seleccionar))
        else:
            formulario(None)

    # ===================================================== textos legales
    def _textos(self, tab) -> None:
        arriba = ctk.CTkFrame(tab, fg_color="transparent")
        arriba.pack(fill="x", padx=10, pady=(6, 4))
        tipos = {v: k for k, v in TIPOS_LEGALES.items()}
        self.tipo_texto = tema.selector(arriba, list(tipos), ancho=420, command=lambda _v: self._cargar_texto())
        self.tipo_texto.pack(side="left")
        self.tipos_texto = tipos
        self.lbl_version = tema.etiqueta(arriba, "", negrita=True)
        self.lbl_version.pack(side="left", padx=16)

        marcadores = ", ".join("{" + c.clave + "}" for c in cc.CLAVES if c.grupo in ("Negocio y pagos", "Precios", "Abonos y tiempos"))
        tema.etiqueta(tab, f"Puede usar marcadores que se reemplazan por la configuración: {marcadores}",
                      tema.TAM_PEQUENO, color=tema.GRIS_TEXTO, wraplength=1000).pack(anchor="w", padx=12, pady=(2, 6))
        self.caja_legal = tema.caja_texto(tab, alto=380)
        self.caja_legal.pack(fill="both", expand=True, padx=10)

        abajo = ctk.CTkFrame(tab, fg_color="transparent")
        abajo.pack(fill="x", padx=10, pady=10)
        tema.boton(abajo, "Guardar como versión nueva", self._guardar_texto, ancho=320).pack(side="left")
        tema.boton(abajo, "Ver cómo queda", self._vista_previa, estilo="secundario", ancho=200).pack(side="left", padx=12)
        tema.etiqueta(tab, "Nota: estos textos son un borrador y no son asesoría jurídica; deben revisarlos un abogado.",
                      tema.TAM_PEQUENO, color=tema.GRIS_TEXTO).pack(anchor="w", padx=12, pady=(0, 8))
        self.tipo_texto.set(list(tipos)[0])
        self._cargar_texto()

    def _tipo_actual(self) -> str:
        return self.tipos_texto[self.tipo_texto.get()]

    def _cargar_texto(self) -> None:
        fila, _ = legal.texto_vigente(self.ctx.conn, self._tipo_actual())
        self.lbl_version.configure(text=f"Versión vigente: {fila['version']} (desde {fila['creado_en']})")
        tema.poner_texto(self.caja_legal, fila["contenido"])

    def _vista_previa(self) -> None:
        texto = rellenar_texto(self.caja_legal.get("1.0", "end").strip(), configuracion.valores(self.ctx.conn))
        dialogos.reporte(self, "Vista previa", "Así lo verá el propietario:", texto)

    def _guardar_texto(self) -> None:
        tipo = self._tipo_actual()
        if not dialogos.confirmar(
            self, "Crear versión nueva",
            f"Se creará una versión nueva de «{TIPOS_LEGALES[tipo]}». Todos los propietarios deberán aceptarla "
            "de nuevo antes de su próximo turno. ¿Continuar?",
            si="Sí, crear versión",
        ):
            return
        r = dialogos.ejecutar(self, legal.nueva_version, self.ctx.conn, self.ctx.sesion, tipo, self.caja_legal.get("1.0", "end"))
        if r is not dialogos.FALLO:
            dialogos.aviso(self, "Versión guardada", f"Ahora está vigente la versión {r}.")
            self._cargar_texto()
