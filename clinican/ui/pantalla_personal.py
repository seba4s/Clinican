"""Gestión de personal (solo la administradora)."""

from __future__ import annotations

import customtkinter as ctk

from clinican.dominio.permisos import ADMIN
from clinican.servicios import personal
from clinican.ui import dialogos, tema


class PantallaPersonal(ctk.CTkFrame):
    def __init__(self, padre, ctx):
        super().__init__(padre, fg_color="transparent")
        self.ctx = ctx
        self.filas: dict[str, object] = {}

        arriba = ctk.CTkFrame(self, fg_color="transparent")
        arriba.pack(fill="x", pady=(0, 14))
        tema.titulo(arriba, "Personal").pack(side="left")
        tema.boton(arriba, "+ Agregar persona", self._modo_nuevo, ancho=230).pack(side="right")

        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True)
        cuerpo.grid_columnconfigure(0, weight=3)
        cuerpo.grid_columnconfigure(1, weight=2)
        cuerpo.grid_rowconfigure(0, weight=1)

        self.tabla = tema.tabla(
            cuerpo,
            [("nombre", "Nombre", 220), ("cargo", "Cargo", 220), ("rol", "Rol", 150), ("estado", "Estado", 110)],
        )
        self.tabla.marco.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        self.tabla.bind("<<TreeviewSelect>>", lambda _e: self._al_seleccionar())

        self.panel = ctk.CTkScrollableFrame(cuerpo, fg_color=tema.BLANCO, corner_radius=14, border_width=1, border_color=tema.BORDE)
        self.panel.grid(row=0, column=1, sticky="nsew")

        self._cargar()
        self._modo_nuevo()

    # ----------------------------------------------------------------- datos
    def _cargar(self) -> None:
        filas = dialogos.ejecutar(self, personal.listar_todos, self.ctx.conn, self.ctx.sesion)
        if filas is dialogos.FALLO:
            return
        self.tabla.delete(*self.tabla.get_children())
        self.filas = {}
        for i, f in enumerate(filas):
            etiquetas = ["par"] if i % 2 else []
            if not f["activo"]:
                etiquetas.append("inactivo")
            iid = str(f["id"])
            self.tabla.insert(
                "", "end", iid=iid, tags=etiquetas,
                values=(f["nombre"], f["cargo"], "Administradora" if f["rol"] == ADMIN else "Personal",
                        "Activo" if f["activo"] else "Inactivo"),
            )
            self.filas[iid] = f

    def _seleccionada(self):
        sel = self.tabla.selection()
        return self.filas.get(sel[0]) if sel else None

    # ----------------------------------------------------------------- panel
    def _limpiar_panel(self, texto: str) -> None:
        for hijo in self.panel.winfo_children():
            hijo.destroy()
        tema.subtitulo(self.panel, texto).pack(anchor="w", padx=20, pady=(18, 4))

    def _campo(self, texto: str, oculto: bool = False, valor: str = ""):
        tema.etiqueta(self.panel, texto, negrita=True).pack(anchor="w", padx=20, pady=(10, 4))
        e = tema.entrada(self.panel, ancho=340, oculto=oculto)
        e.pack(anchor="w", padx=20)
        if valor:
            e.insert(0, valor)
        return e

    def _campo_cargo(self, valor: str = ""):
        tema.etiqueta(self.panel, "Cargo", negrita=True).pack(anchor="w", padx=20, pady=(10, 4))
        c = tema.selector(self.panel, personal.CARGOS_SUGERIDOS, ancho=340, editable=True)
        c.set(valor or personal.CARGOS_SUGERIDOS[1])
        c.pack(anchor="w", padx=20)
        return c

    def _modo_nuevo(self) -> None:
        if self.tabla.selection():
            self.tabla.selection_remove(self.tabla.selection())
        self._limpiar_panel("Agregar persona")
        tema.etiqueta(self.panel, "Quedará con rol «Personal».", color=tema.GRIS_TEXTO).pack(anchor="w", padx=20)
        nombre = self._campo("Nombre (para iniciar sesión)")
        cargo = self._campo_cargo()
        pin = self._campo("PIN (4 a 6 números)", oculto=True)
        pin2 = self._campo("Repita el PIN", oculto=True)

        def guardar():
            if pin.get() != pin2.get():
                dialogos.error(self, "Los dos PIN no coinciden.")
                return
            r = dialogos.ejecutar(self, personal.crear, self.ctx.conn, self.ctx.sesion, nombre.get(), cargo.get(), pin.get())
            if r is dialogos.FALLO:
                return
            self._cargar()
            dialogos.aviso(self, "Persona agregada", f"{nombre.get().strip()} ya puede iniciar sesión con su PIN.")
            self._modo_nuevo()

        tema.boton(self.panel, "Guardar persona", guardar, ancho=340).pack(anchor="w", padx=20, pady=(22, 18))

    def _al_seleccionar(self) -> None:
        f = self._seleccionada()
        if f is None:
            return
        self._limpiar_panel(f["nombre"])
        es_admin = f["rol"] == ADMIN
        es_yo = f["id"] == self.ctx.sesion.personal_id

        nombre = self._campo("Nombre", valor=f["nombre"])
        cargo = self._campo_cargo(f["cargo"])
        tema.boton(
            self.panel, "Guardar cambios",
            lambda: self._accion(personal.editar, f["id"], nombre.get(), cargo.get(), aviso="Datos actualizados."),
            ancho=340,
        ).pack(anchor="w", padx=20, pady=(16, 6))

        pin = self._campo("PIN nuevo para esta persona", oculto=True)
        tema.boton(
            self.panel, "Cambiar PIN",
            lambda: self._accion(personal.cambiar_pin_de, f["id"], pin.get(), aviso="PIN cambiado."),
            estilo="secundario", ancho=340,
        ).pack(anchor="w", padx=20, pady=(10, 6))

        ctk.CTkFrame(self.panel, fg_color=tema.BORDE, height=2).pack(fill="x", padx=20, pady=14)

        if es_admin:
            tema.etiqueta(
                self.panel,
                "Es la administradora. Para desactivarla, primero entregue la administración a otra persona.",
                color=tema.GRIS_TEXTO, wraplength=340,
            ).pack(anchor="w", padx=20, pady=(0, 18))
            return

        if f["activo"]:
            tema.boton(self.panel, "Desactivar", lambda: self._desactivar(f), estilo="peligro", ancho=340).pack(anchor="w", padx=20, pady=6)
            if not es_yo:
                tema.boton(
                    self.panel, "Entregarle la administración", lambda: self._transferir(f),
                    estilo="secundario", ancho=340,
                ).pack(anchor="w", padx=20, pady=(6, 18))
        else:
            tema.boton(
                self.panel, "Reactivar",
                lambda: self._accion(personal.reactivar, f["id"], aviso=f"{f['nombre']} puede volver a iniciar sesión."),
                ancho=340,
            ).pack(anchor="w", padx=20, pady=(6, 18))

    # --------------------------------------------------------------- acciones
    def _accion(self, funcion, *args, aviso: str) -> None:
        seleccion = self.tabla.selection()
        r = dialogos.ejecutar(self, funcion, self.ctx.conn, self.ctx.sesion, *args)
        if r is dialogos.FALLO:
            return
        dialogos.aviso(self, "Listo", aviso)
        if args and args[0] == self.ctx.sesion.personal_id:
            self.ctx.refrescar_menu()  # su propio nombre cambió en el encabezado
            return
        self._cargar()
        if seleccion and self.tabla.exists(seleccion[0]):
            self.tabla.selection_set(seleccion[0])

    def _desactivar(self, f) -> None:
        if dialogos.confirmar(
            self, "Desactivar persona",
            f"¿Desactivar a {f['nombre']}? No podrá iniciar sesión, pero su historial se conserva.",
            si="Sí, desactivar",
        ):
            self._accion(personal.desactivar, f["id"], aviso=f"{f['nombre']} quedó inactiva.")

    def _transferir(self, f) -> None:
        pin = dialogos.pedir_pin(
            self, "Entregar la administración",
            f"{f['nombre']} pasará a ser la administradora y usted quedará con rol «Personal». "
            "Para confirmar, escriba su PIN.",
        )
        if pin is None:
            return
        r = dialogos.ejecutar(self, personal.transferir_administracion, self.ctx.conn, self.ctx.sesion, f["id"], pin)
        if r is dialogos.FALLO:
            return
        dialogos.aviso(self, "Administración entregada", f"Ahora {f['nombre']} es la administradora.")
        self.ctx.refrescar_menu()
