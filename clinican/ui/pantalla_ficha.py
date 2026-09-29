"""Ficha de servicio (pantalla 5) con precios en vivo y desenredado por sesiones (pantalla 6)."""

from __future__ import annotations

from datetime import date
from typing import Callable

import customtkinter as ctk

from clinican.dominio import ficha as reglas
from clinican.dominio.catalogos import CONDICIONES, ESTADOS_SERVICIO, TIPOS_SERVICIO, nombre_tamano
from clinican.dominio.errores import ErrorClinican
from clinican.dominio.formato import pesos
from clinican.servicios import fichas, legal, personal, propietarios
from clinican.ui import dialogos, tema

SI_NO = {1: "Se deja", 0: "No", None: "Sin definir"}
SI_NO_ACCESORIO = {1: "Sí", 0: "No", None: "Sin definir"}
LARGOS = {None: "Sin definir", **reglas.LARGOS}


class PantallaFicha(ctk.CTkFrame):
    def __init__(self, padre, ctx, mascota_id: int, servicio_id: int | None, al_volver: Callable[[], None],
                 al_recargar: Callable[[int], None] | None = None):
        super().__init__(padre, fg_color="transparent")
        self.ctx = ctx
        self.al_recargar = al_recargar
        self.mascota_id = mascota_id
        self.sid = servicio_id
        self.al_volver = al_volver
        self.s = None
        if servicio_id is not None:
            s = dialogos.ejecutar(self, fichas.obtener, ctx.conn, ctx.sesion, servicio_id)
            if s is dialogos.FALLO:
                return
            self.s = s
        m = dialogos.ejecutar(self, propietarios.mascota, ctx.conn, ctx.sesion, mascota_id)
        if m is dialogos.FALLO:
            return
        self.m = m
        self.estado = self.s["estado"] if self.s else reglas.PLANEADO
        self.realizado = self.estado in (reglas.REALIZADO, reglas.CANCELADO)
        self._encabezado()

        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True)
        cuerpo.grid_columnconfigure(0, weight=3, uniform="f")
        cuerpo.grid_columnconfigure(1, weight=2, uniform="f")
        cuerpo.grid_rowconfigure(0, weight=1)
        self.izq = ctk.CTkScrollableFrame(cuerpo, fg_color=tema.BLANCO, corner_radius=14, border_width=1, border_color=tema.BORDE)
        self.izq.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        self.der = ctk.CTkScrollableFrame(cuerpo, fg_color=tema.BLANCO, corner_radius=14, border_width=1, border_color=tema.BORDE)
        self.der.grid(row=0, column=1, sticky="nsew")

        self._detalles()
        self._precios()
        self._acciones()
        if self.s and (self.estado == reglas.EN_SESIONES or fichas.sesiones(ctx.conn, ctx.sesion, self.sid)):
            self._desenredado()
        self._visibilidad()
        self._recalcular()

    # ================================================================ partes
    def _encabezado(self) -> None:
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.pack(fill="x", pady=(0, 12))
        tema.boton(barra, "← Volver", self.al_volver, estilo="secundario", ancho=140).pack(side="left")
        texto = f"Ficha de servicio — {self.m['nombre']}"
        tema.titulo(barra, texto).pack(side="left", padx=16)
        estado = ESTADOS_SERVICIO[self.estado] if self.s else "Nueva"
        tema.insignia(barra, f"Estado: {estado}", tema.FUCSIA if self.estado == reglas.CANCELADO else tema.VERDE).pack(side="right")
        tamano = propietarios.perfil(self.m)["tamano"]
        edad = ""
        if self.m["edad_anios"] is not None:
            edad = f" · {self.m['edad_anios']} años" + (f" y {self.m['edad_meses']} meses" if self.m["edad_meses"] else "")
        tema.etiqueta(self, f"{self.m['raza_nombre']} · {nombre_tamano(tamano)}{edad}",
                      color=tema.GRIS_TEXTO).pack(anchor="w", pady=(0, 10))

    def _fila(self, texto: str) -> ctk.CTkFrame:
        caja = ctk.CTkFrame(self.izq, fg_color="transparent")
        caja.pack(fill="x", padx=16, pady=(10, 0))
        tema.etiqueta(caja, texto, negrita=True).pack(anchor="w", pady=(0, 4))
        return caja

    def _detalles(self) -> None:
        s = self.s
        z = self.izq
        caja = self._fila("Fecha del servicio (AAAA-MM-DD)")
        self.fecha = tema.entrada(caja, ancho=220)
        self.fecha.insert(0, s["fecha"] if s else date.today().isoformat())
        self.fecha.pack(anchor="w")

        caja = self._fila("Tipo de servicio")
        self.tipo = tema.Opciones(caja, TIPOS_SERVICIO, self._al_cambiar, s["tipo_servicio"] if s else "MAQUINA")
        self.tipo.pack(anchor="w")

        self.caja_largo = self._fila("Largo de la máquina")
        self.largo = tema.Opciones(self.caja_largo, LARGOS, self._al_cambiar, s["largo_maquina"] if s else None)
        self.largo.pack(anchor="w")

        self.opc = {}
        for campo, texto in (("copete", "Copete"), ("barbas", "Barbas"), ("cola_leon", "Cola de león")):
            caja = self._fila(texto)
            self.opc[campo] = tema.Opciones(caja, SI_NO, self._al_cambiar, s[campo] if s else None)
            self.opc[campo].pack(anchor="w")

        self.caja_cola = self._fila("Estilo de la cola de león (solo corte bajito)")
        self.cola_estilo = tema.Opciones(self.caja_cola, {None: "Sin definir", **reglas.COLA_ESTILOS}, None,
                                         s["cola_estilo"] if s else None)
        self.cola_estilo.pack(anchor="w")
        self.caja_cara = self._fila("Forma de la cara (solo corte bajito)")
        self.forma_cara = tema.Opciones(self.caja_cara, {None: "Sin definir", **reglas.FORMAS_CARA}, None,
                                        s["forma_cara"] if s else None)
        self.forma_cara.pack(anchor="w")

        # Accesorios: corbatín y moños en las orejas, con el color que se escoja
        self.accesorios = {}
        for campo, texto in (("corbatin", "Corbatín"), ("monos", "Moños en las orejas")):
            caja = self._fila(texto)
            fila = ctk.CTkFrame(caja, fg_color="transparent")
            fila.pack(anchor="w")
            lleva = tema.Opciones(fila, SI_NO_ACCESORIO, lambda c=campo: self._al_cambiar_accesorio(c),
                                  s[campo] if s else None)
            lleva.pack(side="left")
            tema.etiqueta(fila, "Color:").pack(side="left", padx=(16, 6))
            color = tema.selector(fila, reglas.COLORES, ancho=200, editable=True)
            color.set((s[f"{campo}_color"] if s else None) or "")
            color.pack(side="left")
            self.accesorios[campo] = (lleva, color)
            self._al_cambiar_accesorio(campo)

        caja = self._fila("Baños extra (se cobran según el tamaño)")
        self.medicado = ctk.IntVar(value=s["bano_medicado"] if s else 0)
        self.antipulgas = ctk.IntVar(value=s["bano_antipulgas"] if s else 0)
        tema.casilla(caja, "Baño medicado", self.medicado, self._recalcular).pack(anchor="w", pady=2)
        tema.casilla(caja, "Baño antipulgas", self.antipulgas, self._recalcular).pack(anchor="w", pady=2)
        fila = ctk.CTkFrame(caja, fg_color="transparent")
        fila.pack(anchor="w", pady=(6, 0))
        tema.etiqueta(fila, "Cantidad de baños extra:").pack(side="left")
        self.cantidad = tema.entrada(fila, ancho=70)
        self.cantidad.insert(0, str(s["cantidad_banos_extra"] if s else 1))
        self.cantidad.pack(side="left", padx=8)
        self.cantidad.bind("<KeyRelease>", lambda _e: self._recalcular())

        caja = self._fila("Condiciones difíciles")
        self.condiciones = {}
        for c, texto in CONDICIONES.items():
            v = ctk.IntVar(value=s[c] if s else 0)
            tema.casilla(caja, texto, v).pack(anchor="w", pady=2)
            self.condiciones[c] = v
        self.registrar_resp = ctk.IntVar(value=0)
        self.chk_resp = tema.casilla(
            caja, "Al guardar, registrar la declaración de responsabilidad del propietario con estas condiciones",
            self.registrar_resp,
        )
        self.chk_resp.pack(anchor="w", pady=(10, 0))

        caja = self._fila("Observaciones")
        self.obs = tema.caja_texto(caja, alto=100)
        if s and s["observaciones"]:
            self.obs.insert("1.0", s["observaciones"])
        self.obs.pack(fill="x", pady=(0, 16))

        if self.realizado:
            texto = ("Servicio realizado: solo se pueden corregir el precio final y las observaciones."
                     if self.estado == reglas.REALIZADO else "Ficha cancelada: no se puede editar.")
            tema.etiqueta(z, texto, color=tema.GRIS_TEXTO, wraplength=560).pack(anchor="w", padx=16, pady=(0, 16))
            self._bloquear_detalles()
            if self.estado == reglas.CANCELADO:
                self.obs.configure(state="disabled")

    def _al_cambiar_accesorio(self, campo: str) -> None:
        """El color solo se escoge si se le pone el accesorio."""
        lleva, color = self.accesorios[campo]
        color.configure(state="normal" if lleva.codigo == 1 and not self.realizado else "disabled")

    def _bloquear_detalles(self) -> None:
        for w in (self.fecha, self.tipo, self.largo, self.cola_estilo, self.forma_cara, self.cantidad,
                  self.chk_resp, *self.opc.values(), *(w for par in self.accesorios.values() for w in par)):
            w.configure(state="disabled")
        for hijo in self.izq.winfo_children():
            for nieto in hijo.winfo_children():
                if isinstance(nieto, ctk.CTkCheckBox):
                    nieto.configure(state="disabled")

    def _precios(self) -> None:
        z = self.der
        tema.subtitulo(z, "Precio").pack(anchor="w", padx=16, pady=(14, 8))
        self.lbl = {}
        for clave, texto in (("minimo", "Precio mínimo sugerido"), ("extras", "Extras de baño")):
            fila = ctk.CTkFrame(z, fg_color="transparent")
            fila.pack(fill="x", padx=16, pady=3)
            tema.etiqueta(fila, texto).pack(side="left")
            self.lbl[clave] = tema.etiqueta(fila, "—", negrita=True)
            self.lbl[clave].pack(side="right")
        tema.etiqueta(z, "Precio final (lo define la estilista)", negrita=True).pack(anchor="w", padx=16, pady=(12, 4))
        self.precio_final = tema.entrada(z, ancho=240, placeholder_text="Ej.: 50.000")
        if self.s and self.s["precio_final"] is not None:
            self.precio_final.insert(0, pesos(self.s["precio_final"]).replace("$", ""))
        self.precio_final.pack(anchor="w", padx=16)
        self.precio_final.bind("<KeyRelease>", lambda _e: self._recalcular())
        if self.estado == reglas.CANCELADO:
            self.precio_final.configure(state="disabled")
        self.lbl_aviso = tema.etiqueta(z, "", tema.TAM_PEQUENO, negrita=True, color=tema.ROJO_ERROR, wraplength=380)
        self.lbl_aviso.pack(anchor="w", padx=16, pady=(6, 0))
        for clave, texto in (("total", "Total del servicio"), ("desenredado", "Sesiones de desenredado"),
                             ("gran_total", "TOTAL A COBRAR")):
            fila = ctk.CTkFrame(z, fg_color=tema.VERDE_SUAVE if clave == "gran_total" else "transparent", corner_radius=8)
            fila.pack(fill="x", padx=16, pady=3)
            tema.etiqueta(fila, texto, negrita=clave == "gran_total").pack(side="left", padx=6, pady=4)
            self.lbl[clave] = tema.etiqueta(fila, "—", tema.TAM_SUBTITULO if clave == "gran_total" else tema.TAM_NORMAL, negrita=True)
            self.lbl[clave].pack(side="right", padx=6)
        tema.etiqueta(z, "El abono del turno se descuenta al cobrar (saldo = total − abonos).",
                      tema.TAM_PEQUENO, color=tema.GRIS_TEXTO, wraplength=380).pack(anchor="w", padx=16, pady=(6, 0))

    def _acciones(self) -> None:
        z = self.der
        ctk.CTkFrame(z, fg_color=tema.BORDE, height=2).pack(fill="x", padx=16, pady=14)
        if self.estado != reglas.CANCELADO:
            tema.boton(z, "Guardar ficha", self._guardar, ancho=360).pack(anchor="w", padx=16, pady=4)
        if self.s is None:
            return
        acciones = {
            reglas.PLANEADO: [("Enviar a revisión de la estilista", reglas.REVISION, "secundario"),
                              ("Marcar como realizado", reglas.REALIZADO, "primario")],
            reglas.REVISION: [("Iniciar sesiones de desenredado", reglas.EN_SESIONES, "primario"),
                              ("No necesita desenredado", reglas.PLANEADO, "secundario"),
                              ("Marcar como realizado", reglas.REALIZADO, "secundario")],
        }.get(self.estado, [])
        for texto, nuevo, estilo in acciones:
            tema.boton(z, texto, lambda n=nuevo: self._cambiar_estado(n), estilo=estilo, ancho=360).pack(anchor="w", padx=16, pady=4)
        if self.estado in (reglas.PLANEADO, reglas.REVISION, reglas.EN_SESIONES):
            tema.boton(z, "Cancelar ficha", lambda: self._cambiar_estado(reglas.CANCELADO), estilo="peligro",
                       ancho=360).pack(anchor="w", padx=16, pady=(4, 16))

    def _desenredado(self) -> None:
        z = self.izq
        ctk.CTkFrame(z, fg_color=tema.BORDE, height=2).pack(fill="x", padx=16, pady=(8, 4))
        tema.subtitulo(z, "Desenredado por sesiones").pack(anchor="w", padx=16, pady=(8, 2))
        valor = self.ctx.config().get("desenredado_sesion", "0")
        tema.etiqueta(z, f"{pesos(valor)} por sesión · máximo una sesión por día.", color=tema.GRIS_TEXTO).pack(anchor="w", padx=16)
        filas = fichas.sesiones(self.ctx.conn, self.ctx.sesion, self.sid)
        self.tabla_ses = tema.tabla(z, [("fecha", "Fecha", 120), ("precio", "Valor", 100), ("quien", "Realizó", 150),
                                        ("notas", "Notas", 240)], alto=max(min(len(filas), 6), 2))
        self.tabla_ses.marco.pack(fill="x", padx=16, pady=(8, 4))
        for d in filas:
            self.tabla_ses.insert("", "end", iid=str(d["id"]), values=(d["fecha"], pesos(d["precio"]),
                                                                        d["realizada_por_nombre"] or "", d["notas"] or ""))
        total = sum(d["precio"] for d in filas)
        tema.etiqueta(z, f"{len(filas)} sesión(es) · acumulado {pesos(total)}", negrita=True).pack(anchor="w", padx=16, pady=(0, 8))
        if self.estado != reglas.EN_SESIONES:
            return

        form = ctk.CTkFrame(z, fg_color=tema.VERDE_SUAVE, corner_radius=12)
        form.pack(fill="x", padx=16, pady=(4, 8))
        tema.etiqueta(form, "Registrar sesión", negrita=True).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 4))
        tema.etiqueta(form, "Fecha").grid(row=1, column=0, sticky="w", padx=12)
        fecha = tema.entrada(form, ancho=160)
        fecha.insert(0, date.today().isoformat())
        fecha.grid(row=2, column=0, sticky="w", padx=12)
        tema.etiqueta(form, "Realizó").grid(row=1, column=1, sticky="w", padx=12)
        activos = {p["nombre"]: p["id"] for p in personal.listar_activos(self.ctx.conn)}
        quien = tema.selector(form, list(activos), ancho=240)
        quien.set(self.ctx.sesion.nombre if self.ctx.sesion.nombre in activos else next(iter(activos)))
        quien.grid(row=2, column=1, sticky="w", padx=12)
        tema.etiqueta(form, "Notas").grid(row=3, column=0, columnspan=2, sticky="w", padx=12, pady=(8, 0))
        notas = tema.entrada(form, ancho=420)
        notas.grid(row=4, column=0, columnspan=2, sticky="w", padx=12)

        def registrar():
            r = dialogos.ejecutar(self, fichas.registrar_sesion, self.ctx.conn, self.ctx.sesion, self.sid,
                                  fecha.get(), notas.get(), activos[quien.get()])
            if r is not dialogos.FALLO:
                self._recargar()

        tema.boton(form, "Registrar sesión", registrar, ancho=240).grid(row=5, column=0, sticky="w", padx=12, pady=12)

        fila = ctk.CTkFrame(z, fg_color="transparent")
        fila.pack(fill="x", padx=16, pady=(0, 16))
        tema.boton(fila, "Anular sesión seleccionada", self._anular_sesion, estilo="secundario", ancho=280).pack(side="left")
        tema.boton(fila, "Cerrar sesiones y definir servicio final", self._cerrar_sesiones, ancho=400).pack(side="left", padx=(12, 0))

    # ============================================================ lógica UI
    def _al_cambiar(self) -> None:
        self._visibilidad()
        self._recalcular()

    def _visibilidad(self) -> None:
        """Muestra el largo solo con máquina, y estilo de cola/forma de cara solo en corte bajito [A-5]."""
        maquina = self.tipo.codigo == "MAQUINA"
        bajito = reglas.es_corte_bajito(self.tipo.codigo, self.largo.codigo if maquina else None)
        despues = self.opc["cola_leon"].master
        for caja, visible in ((self.caja_largo, maquina), (self.caja_cola, bajito and self.opc["cola_leon"].codigo == 1),
                              (self.caja_cara, bajito)):
            if visible and not caja.winfo_manager():
                caja.pack(fill="x", padx=16, pady=(10, 0), after=despues if caja is not self.caja_largo else self.tipo.master)
            elif not visible and caja.winfo_manager():
                caja.pack_forget()
        # Orden: forma de la cara va después del estilo de cola
        if self.caja_cara.winfo_manager() and self.caja_cola.winfo_manager():
            self.caja_cara.pack_configure(after=self.caja_cola)

    def _detalles_actuales(self) -> reglas.DetallesFicha:
        maquina = self.tipo.codigo == "MAQUINA"
        largo = self.largo.codigo if maquina else None
        bajito = reglas.es_corte_bajito(self.tipo.codigo, largo)
        cola = self.opc["cola_leon"].codigo
        try:
            cantidad = int(self.cantidad.get().strip() or 1)
        except ValueError:
            cantidad = 0
        return reglas.DetallesFicha(
            tipo_servicio=self.tipo.codigo, largo_maquina=largo,
            bano_medicado=bool(self.medicado.get()), bano_antipulgas=bool(self.antipulgas.get()),
            cantidad_banos_extra=cantidad, copete=self.opc["copete"].codigo, barbas=self.opc["barbas"].codigo,
            cola_leon=cola, cola_estilo=self.cola_estilo.codigo if bajito and cola == 1 else None,
            forma_cara=self.forma_cara.codigo if bajito else None,
            corbatin=self.accesorios["corbatin"][0].codigo, corbatin_color=self.accesorios["corbatin"][1].get(),
            monos=self.accesorios["monos"][0].codigo, monos_color=self.accesorios["monos"][1].get(),
            condiciones={c: bool(v.get()) for c, v in self.condiciones.items()},
            observaciones=self.obs.get("1.0", "end"),
        )

    def _recalcular(self) -> None:
        if self.realizado and self.s is not None:
            liq = fichas.liquidacion(self.ctx.conn, self.sid)
            try:
                final = fichas._precio(self.precio_final.get())
            except ErrorClinican:
                final = liq.precio_final
            from clinican.dominio import precios as p

            liq = p.Liquidacion(liq.precio_minimo, final, liq.extras, p.total(final, liq.extras), liq.desenredado,
                                None if final is None or final >= liq.precio_minimo else "El precio final es menor que el mínimo sugerido.")
        else:
            d = self._detalles_actuales()
            try:
                liq = fichas.calcular(self.ctx.conn, self.ctx.sesion, self.mascota_id, d.tipo_servicio,
                                      self.precio_final.get(), d.bano_medicado, d.bano_antipulgas,
                                      max(d.cantidad_banos_extra, 1), self.sid)
            except ErrorClinican as e:
                self.lbl_aviso.configure(text=str(e))
                return
        self.lbl["minimo"].configure(text=pesos(liq.precio_minimo))
        self.lbl["extras"].configure(text=pesos(liq.extras))
        self.lbl["total"].configure(text=pesos(liq.total))
        self.lbl["desenredado"].configure(text=pesos(liq.desenredado))
        self.lbl["gran_total"].configure(text=pesos(liq.gran_total))
        self.lbl_aviso.configure(text=("Atención: " + liq.advertencia + " Se permite guardar.") if liq.advertencia else "")

    def _guardar(self, silencioso: bool = False) -> bool:
        d = self._detalles_actuales()
        if self.s is None:
            r = dialogos.ejecutar(self, fichas.crear, self.ctx.conn, self.ctx.sesion, self.mascota_id,
                                  self.fecha.get(), d, self.precio_final.get())
            if r is dialogos.FALLO:
                return False
            self.sid = r
            aviso = None
        else:
            r = dialogos.ejecutar(self, fichas.editar, self.ctx.conn, self.ctx.sesion, self.sid,
                                  self.fecha.get(), d, self.precio_final.get())
            if r is dialogos.FALLO:
                return False
            aviso = r.advertencia
        if self.registrar_resp.get() and not self.realizado:
            if dialogos.ejecutar(self, legal.registrar_responsabilidad, self.ctx.conn, self.ctx.sesion,
                                 self.mascota_id, d.condiciones) is dialogos.FALLO:
                return False
        if not silencioso:
            texto = "La ficha quedó guardada."
            if aviso:
                texto += f"\n\nAtención: {aviso}"
            dialogos.aviso(self, "Ficha guardada", texto)
            self._recargar()
        return True

    def _recargar(self) -> None:
        if self.al_recargar:
            self.al_recargar(self.sid)
        else:
            self.ctx.abrir_ficha(self.m["propietario_id"], self.mascota_id, self.sid)

    def _cambiar_estado(self, nuevo: str) -> None:
        if nuevo == reglas.CANCELADO and not dialogos.confirmar(
            self, "Cancelar ficha", "¿Cancelar esta ficha de servicio? Ya no se podrá editar.", si="Sí, cancelar ficha"
        ):
            return
        if nuevo != reglas.CANCELADO and not self._guardar(silencioso=True):
            return
        r = dialogos.ejecutar(self, fichas.cambiar_estado, self.ctx.conn, self.ctx.sesion, self.sid, nuevo)
        if r is not dialogos.FALLO:
            self._recargar()

    def _anular_sesion(self) -> None:
        sel = self.tabla_ses.selection()
        if not sel:
            dialogos.aviso(self, "Elija una sesión", "Seleccione en la lista la sesión que desea anular.")
            return
        if dialogos.confirmar(self, "Anular sesión", "¿Anular la sesión seleccionada? Quedará registrado en la auditoría.",
                              si="Sí, anular"):
            if dialogos.ejecutar(self, fichas.anular_sesion, self.ctx.conn, self.ctx.sesion, int(sel[0])) is not dialogos.FALLO:
                self._recargar()

    def _cerrar_sesiones(self) -> None:
        opciones = [(texto, codigo) for codigo, texto in TIPOS_SERVICIO.items()] + [("Sin servicio final", "NINGUNO")]
        eleccion = dialogos.elegir(
            self, "Cerrar el desenredado",
            "¿Qué servicio se le hará a la mascota ahora? Si no se hará ninguno, solo se cobran las sesiones.",
            opciones,
        )
        if eleccion is None:
            return
        r = dialogos.ejecutar(self, fichas.cerrar_sesiones, self.ctx.conn, self.ctx.sesion, self.sid,
                              None if eleccion == "NINGUNO" else eleccion)
        if r is not dialogos.FALLO:
            self._recargar()
