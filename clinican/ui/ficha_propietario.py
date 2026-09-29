"""Detalle de un propietario: pestañas Datos, Mascotas y Consentimientos."""

from __future__ import annotations

import json
from typing import Callable

import customtkinter as ctk

from clinican.dominio.catalogos import CONDICIONES, ESTADOS_SERVICIO, TIPOS_LEGALES, TIPOS_SERVICIO
from clinican.dominio.formato import pesos
from clinican.dominio.propietarios import formato_celular
from clinican.servicios import legal, propietarios
from clinican.ui import dialogos, tema
from clinican.ui.selector_raza import SelectorRaza

P_DATOS, P_MASCOTAS, P_CONSENT = "Datos", "Mascotas", "Consentimientos"


class DetallePropietario(ctk.CTkFrame):
    def __init__(self, padre, ctx, propietario_id: int | None, al_guardar: Callable, pestana: str | None = None,
                 mascota_id: int | None = None):
        super().__init__(padre, fg_color="transparent")
        self.ctx = ctx
        self.mascota_inicial = mascota_id
        self.pid = propietario_id
        self.al_guardar = al_guardar
        self.fila = None
        if propietario_id is not None:
            fila = dialogos.ejecutar(self, propietarios.obtener, ctx.conn, ctx.sesion, propietario_id)
            if fila is dialogos.FALLO:
                return
            self.fila = fila

        titulo = self.fila["nombre"] if self.fila else "Nuevo propietario"
        self.provisional = bool(self.fila and self.fila["provisional"])
        tema.subtitulo(self, titulo + (" (sin registrar)" if self.provisional else "")).pack(anchor="w", pady=(0, 6))
        if self.provisional:
            tema.insignia(self, "Cliente sin registrar: complete la cédula y la dirección en «Datos» y luego "
                                "los consentimientos, antes de atender a su mascota.", tema.FUCSIA).pack(anchor="w", pady=(0, 6))

        self.pestanas = ctk.CTkTabview(
            self, fg_color=tema.BLANCO, border_width=1, border_color=tema.BORDE, corner_radius=14,
            segmented_button_fg_color=tema.GRIS_BOTON, segmented_button_selected_color=tema.VERDE,
            segmented_button_selected_hover_color=tema.VERDE_HOVER,
            segmented_button_unselected_color=tema.GRIS_BOTON,
            segmented_button_unselected_hover_color=tema.GRIS_BOTON_HOVER, text_color=tema.NEGRO,
        )
        self.pestanas._segmented_button.configure(font=tema.fuente(tema.TAM_NORMAL, True), height=44)
        self.pestanas.pack(fill="both", expand=True)

        nombres = [P_DATOS] if self.fila is None else [P_DATOS, P_MASCOTAS, P_CONSENT]
        for n in nombres:
            self.pestanas.add(n)
        self._pestana_datos(self._zona(P_DATOS))
        if self.fila is not None:
            self._pestana_mascotas(self._zona(P_MASCOTAS))
            self._pestana_consentimientos(self._zona(P_CONSENT))
            if pestana in nombres:
                self.pestanas.set(pestana)

    def _zona(self, nombre: str) -> ctk.CTkScrollableFrame:
        zona = ctk.CTkScrollableFrame(self.pestanas.tab(nombre), fg_color=tema.BLANCO)
        zona.pack(fill="both", expand=True)
        return zona

    # ================================================================ Datos
    def _pestana_datos(self, z) -> None:
        f = self.fila
        campos = {}
        for clave, texto in (
            ("nombre", "Nombre completo *"), ("cedula", "Cédula *"), ("celular1", "Celular principal *"),
            ("celular2", "Otro celular"), ("direccion", "Dirección *"),
        ):
            tema.etiqueta(z, texto, negrita=True).pack(anchor="w", padx=16, pady=(10, 4))
            e = tema.entrada(z, ancho=460)
            e.pack(anchor="w", padx=16)
            if f is not None and f[clave] and not (clave == "cedula" and self.provisional):
                e.insert(0, formato_celular(f[clave]) if clave.startswith("celular") else f[clave])
            campos[clave] = e
        self.campos_datos = campos
        if self.provisional:
            tema.etiqueta(z, "Si la cédula ya está registrada, el cliente y sus mascotas se unen a ese propietario.",
                          tema.TAM_PEQUENO, color=tema.GRIS_TEXTO, wraplength=520).pack(anchor="w", padx=16, pady=(6, 0))

        def guardar():
            valores = {k: e.get() for k, e in campos.items()}
            if f is None:
                nuevo = dialogos.ejecutar(self, propietarios.crear, self.ctx.conn, self.ctx.sesion, **valores)
                if nuevo is dialogos.FALLO:
                    return
                dialogos.aviso(self, "Propietario creado",
                               "Ahora registre la aceptación de los términos y la autorización de datos, "
                               "y agregue sus mascotas.")
                self.al_guardar(nuevo, P_CONSENT)
            else:
                r = dialogos.ejecutar(self, propietarios.editar, self.ctx.conn, self.ctx.sesion, f["id"], **valores)
                if r is dialogos.FALLO:
                    return
                if self.provisional:
                    dialogos.aviso(self, "Cliente registrado",
                                   "Ahora registre la aceptación de los términos y la autorización de datos.")
                    self.al_guardar(r, P_CONSENT)
                    return
                dialogos.aviso(self, "Guardado", "Los datos del propietario quedaron actualizados.")
                self.al_guardar(f["id"], P_DATOS)

        texto = "Crear propietario" if f is None else ("Registrar cliente" if self.provisional else "Guardar cambios")
        tema.boton(z, texto, guardar, ancho=460).pack(anchor="w", padx=16, pady=(20, 10))

        if f is None:
            return
        ctk.CTkFrame(z, fg_color=tema.BORDE, height=2).pack(fill="x", padx=16, pady=14)
        var = ctk.IntVar(value=f["requiere_nuevo_abono"])

        def cambiar_marca():
            r = dialogos.ejecutar(self, propietarios.fijar_requiere_nuevo_abono, self.ctx.conn, self.ctx.sesion,
                                  f["id"], bool(var.get()))
            if r is dialogos.FALLO:
                var.set(f["requiere_nuevo_abono"])

        tema.interruptor(z, "Requiere nuevo abono", var, cambiar_marca).pack(anchor="w", padx=16)
        tema.etiqueta(
            z, "Se activa sola cuando no asiste a un turno sin avisar a tiempo. Mientras esté activa, "
               "se exige el abono antes de crear un turno.",
            tema.TAM_PEQUENO, color=tema.GRIS_TEXTO, wraplength=520,
        ).pack(anchor="w", padx=16, pady=(4, 16))

    # ============================================================= Mascotas
    def _pestana_mascotas(self, z) -> None:
        self.z_mascotas = z
        lista = dialogos.ejecutar(self, propietarios.mascotas, self.ctx.conn, self.ctx.sesion, self.pid)
        if lista is dialogos.FALLO:
            return
        self.lista_mascotas = lista
        fila = ctk.CTkFrame(z, fg_color="transparent")
        fila.pack(fill="x", padx=16, pady=(8, 4))
        tema.boton(fila, "+ Agregar mascota", lambda: self._form_mascota(None), ancho=220).pack(side="left")
        for m in lista:
            texto = m["nombre"] + ("" if m["activa"] else " (inactiva)")
            tema.boton(fila, texto, lambda mm=m: self._form_mascota(mm), estilo="secundario", ancho=140).pack(side="left", padx=(10, 0))
        self.form_m = ctk.CTkFrame(z, fg_color="transparent")
        self.form_m.pack(fill="both", expand=True, padx=16, pady=(8, 0))
        elegida = next((m for m in lista if m["id"] == self.mascota_inicial), lista[0] if lista else None)
        self._form_mascota(elegida)

    def _form_mascota(self, m) -> None:
        z = self.form_m
        for hijo in z.winfo_children():
            hijo.destroy()
        tema.subtitulo(z, m["nombre"] if m else "Nueva mascota").pack(anchor="w", pady=(6, 0))

        def etiqueta(texto):
            lbl = tema.etiqueta(z, texto, negrita=True)
            lbl.pack(anchor="w", pady=(10, 4))
            return lbl

        etiqueta("Nombre *")
        nombre = tema.entrada(z, ancho=420)
        nombre.pack(anchor="w")
        raza = SelectorRaza(z, self.ctx.conn, raza_actual_id=m["raza_id"] if m else None)
        self.selector_raza = raza

        edad = ctk.CTkFrame(z, fg_color="transparent")
        edad.pack(anchor="w", pady=(10, 0))
        tema.etiqueta(edad, "Edad: años", negrita=True).pack(side="left")
        anios = tema.entrada(edad, ancho=80)
        anios.pack(side="left", padx=(8, 16))
        tema.etiqueta(edad, "meses", negrita=True).pack(side="left")
        meses = tema.entrada(edad, ancho=80)
        meses.pack(side="left", padx=(8, 0))

        etiqueta("Fecha de la última visita (AAAA-MM-DD)")
        ultima = tema.entrada(z, ancho=220)
        ultima.pack(anchor="w")
        tema.etiqueta(z, "Se actualiza sola al atender un turno; aquí se puede corregir.", tema.TAM_PEQUENO,
                      color=tema.GRIS_TEXTO).pack(anchor="w")
        etiqueta("Observaciones")
        obs = tema.caja_texto(z, alto=90, width=520)
        obs.pack(anchor="w")

        if m is not None:
            nombre.insert(0, m["nombre"])
            raza.cargar(m)
            anios.insert(0, "" if m["edad_anios"] is None else str(m["edad_anios"]))
            meses.insert(0, "" if m["edad_meses"] is None else str(m["edad_meses"]))
            ultima.insert(0, m["fecha_ultima_visita"] or "")
            obs.insert("1.0", m["observaciones"] or "")

        def guardar():
            datos = dict(
                nombre=nombre.get(), **raza.valores(),
                edad_anios=anios.get(), edad_meses=meses.get(),
                fecha_ultima_visita=ultima.get().strip() or None, observaciones=obs.get("1.0", "end"),
            )
            if m is None:
                res = dialogos.ejecutar(self, propietarios.crear_mascota, self.ctx.conn, self.ctx.sesion, self.pid, **datos)
            else:
                res = dialogos.ejecutar(self, propietarios.editar_mascota, self.ctx.conn, self.ctx.sesion, m["id"], **datos)
            if res is dialogos.FALLO:
                return
            dialogos.aviso(self, "Mascota guardada", f"Se guardó a {nombre.get().strip()}.")
            self.al_guardar(self.pid, P_MASCOTAS, res if m is None else m["id"])

        botones = ctk.CTkFrame(z, fg_color="transparent")
        botones.pack(anchor="w", pady=(20, 10))
        tema.boton(botones, "Guardar mascota", guardar, ancho=260).pack(side="left")
        if m is not None:
            texto = "Dar de baja" if m["activa"] else "Reactivar"
            tema.boton(botones, texto, lambda: self._baja_mascota(m), estilo="secundario", ancho=180).pack(side="left", padx=(12, 0))
            self._historial_mascota(z, m)

    def _baja_mascota(self, m) -> None:
        activar = not m["activa"]
        if not activar and not dialogos.confirmar(
            self, "Dar de baja", f"¿Dar de baja a {m['nombre']}? No aparecerá para nuevos turnos; su historial se conserva.",
            si="Sí, dar de baja",
        ):
            return
        r = dialogos.ejecutar(self, propietarios.fijar_mascota_activa, self.ctx.conn, self.ctx.sesion, m["id"], activar)
        if r is not dialogos.FALLO:
            self.al_guardar(self.pid, P_MASCOTAS, m["id"])

    def _historial_mascota(self, z, m) -> None:
        arriba = ctk.CTkFrame(z, fg_color="transparent")
        arriba.pack(fill="x", pady=(18, 6))
        tema.subtitulo(arriba, "Fichas de servicio").pack(side="left")
        if m["activa"]:
            tema.boton(arriba, "+ Nueva ficha de servicio", lambda: self.ctx.abrir_ficha(self.pid, m["id"]),
                       ancho=270).pack(side="right")
        filas = dialogos.ejecutar(self, propietarios.historial, self.ctx.conn, self.ctx.sesion, m["id"])
        if filas is dialogos.FALLO:
            return
        if not filas:
            tema.etiqueta(z, "Todavía no tiene servicios registrados.", color=tema.GRIS_TEXTO).pack(anchor="w", pady=(0, 16))
            return
        t = tema.tabla(z, [("fecha", "Fecha", 110), ("tipo", "Servicio", 170), ("estado", "Estado", 190), ("total", "Total", 110)],
                       alto=min(len(filas), 8))
        t.marco.pack(fill="x", pady=(0, 6))
        for s in filas:
            total = (s["total"] or 0) + (s["desenredado"] or 0)
            t.insert("", "end", iid=str(s["id"]), values=(s["fecha"], TIPOS_SERVICIO.get(s["tipo_servicio"], s["tipo_servicio"]),
                                        ESTADOS_SERVICIO.get(s["estado"], s["estado"]), pesos(total) if total else "—"))

        def abrir(_e=None):
            if t.selection():
                self.ctx.abrir_ficha(self.pid, m["id"], int(t.selection()[0]))

        t.bind("<Double-1>", abrir)
        tema.boton(z, "Abrir la ficha seleccionada", abrir, estilo="secundario", ancho=300).pack(anchor="w", pady=(4, 16))

    # ====================================================== Consentimientos
    def _pestana_consentimientos(self, z) -> None:
        estado = legal.estado(self.ctx.conn, self.pid)
        tema.etiqueta(z, "Para agendar turnos, el propietario debe aceptar los dos documentos (versión vigente).",
                      wraplength=600).pack(anchor="w", padx=16, pady=(10, 8))
        variables = {}
        for tipo in ("TERMINOS", "DATOS"):
            fila_texto, texto = legal.texto_vigente(self.ctx.conn, tipo)
            aceptado = estado[tipo]
            tema.subtitulo(z, TIPOS_LEGALES[tipo]).pack(anchor="w", padx=16, pady=(14, 6))
            if aceptado:
                msg = (f"Aceptado (versión {aceptado['version']}) el {aceptado['aceptado_en']} — "
                       f"registró {aceptado['registrado_por_nombre']}")
            else:
                msg = f"Falta aceptar la versión {fila_texto['version']}"
            tema.aviso_estado(z, msg, bool(aceptado)).pack(anchor="w", padx=16, pady=(0, 6))
            tema.caja_texto(z, alto=170, solo_lectura=True, texto=texto).pack(fill="x", padx=16)
            if not aceptado:
                var = ctk.IntVar(value=0)
                frase = ("El propietario leyó y acepta los términos y condiciones" if tipo == "TERMINOS"
                         else "El propietario autoriza el tratamiento de sus datos personales")
                tema.casilla(z, f"{frase} (versión {fila_texto['version']})", var).pack(anchor="w", padx=16, pady=(8, 0))
                variables[tipo] = var

        if variables:
            def guardar():
                tipos = [t for t, v in variables.items() if v.get()]
                r = dialogos.ejecutar(self, legal.aceptar, self.ctx.conn, self.ctx.sesion, self.pid, tipos)
                if r is not dialogos.FALLO:
                    dialogos.aviso(self, "Aceptación guardada", "Quedó registrada con la fecha y la versión del texto.")
                    self.al_guardar(self.pid, P_CONSENT)

            tema.boton(z, "Guardar aceptación", guardar, ancho=300).pack(anchor="w", padx=16, pady=(16, 6))

        self._seccion_responsabilidad(z)
        self._historial_consentimientos(z)

    def _seccion_responsabilidad(self, z) -> None:
        ctk.CTkFrame(z, fg_color=tema.BORDE, height=2).pack(fill="x", padx=16, pady=(18, 4))
        tema.subtitulo(z, TIPOS_LEGALES["RESPONSABILIDAD"]).pack(anchor="w", padx=16, pady=(10, 4))
        activas = [m for m in propietarios.mascotas(self.ctx.conn, self.ctx.sesion, self.pid) if m["activa"]]
        if not activas:
            tema.etiqueta(z, "Primero agregue una mascota en la pestaña «Mascotas».", color=tema.GRIS_TEXTO).pack(anchor="w", padx=16)
            return
        _, texto = legal.texto_vigente(self.ctx.conn, "RESPONSABILIDAD")
        tema.caja_texto(z, alto=130, solo_lectura=True, texto=texto).pack(fill="x", padx=16, pady=(4, 8))
        por_nombre = {m["nombre"]: m["id"] for m in activas}
        fila = ctk.CTkFrame(z, fg_color="transparent")
        fila.pack(anchor="w", padx=16)
        tema.etiqueta(fila, "Mascota:", negrita=True).pack(side="left", padx=(0, 8))
        mascota = tema.selector(fila, list(por_nombre), ancho=280)
        mascota.pack(side="left")
        variables = {}
        for clave, texto_c in CONDICIONES.items():
            v = ctk.IntVar(value=0)
            tema.casilla(z, texto_c, v).pack(anchor="w", padx=16, pady=(8, 0))
            variables[clave] = v

        def guardar():
            condiciones = {c: bool(v.get()) for c, v in variables.items()}
            r = dialogos.ejecutar(self, legal.registrar_responsabilidad, self.ctx.conn, self.ctx.sesion,
                                  por_nombre[mascota.get()], condiciones)
            if r is not dialogos.FALLO:
                dialogos.aviso(self, "Declaración guardada", "La declaración de responsabilidad quedó registrada con su fecha.")
                self.al_guardar(self.pid, P_CONSENT)

        tema.boton(z, "Guardar declaración", guardar, ancho=300).pack(anchor="w", padx=16, pady=(14, 6))

    def _historial_consentimientos(self, z) -> None:
        filas = dialogos.ejecutar(self, legal.historial, self.ctx.conn, self.ctx.sesion, self.pid)
        if filas is dialogos.FALLO or not filas:
            return
        ctk.CTkFrame(z, fg_color=tema.BORDE, height=2).pack(fill="x", padx=16, pady=(18, 4))
        tema.subtitulo(z, "Historial de aceptaciones").pack(anchor="w", padx=16, pady=(10, 6))
        t = tema.tabla(z, [("fecha", "Fecha", 160), ("doc", "Documento", 200), ("v", "Versión", 70),
                           ("detalle", "Detalle", 230), ("quien", "Registró", 110)], alto=min(len(filas), 8))
        t.marco.pack(fill="x", padx=16, pady=(0, 16))
        for c in filas:
            detalle = ""
            if c["tipo"] == "RESPONSABILIDAD":
                marcadas = [CONDICIONES[k].lower() for k, v in json.loads(c["condiciones"] or "{}").items() if v]
                detalle = f"{c['mascota_nombre']}: {', '.join(marcadas)}"
            version = f"{c['version']}" + ("" if c["texto_vigente"] else " (anterior)")
            t.insert("", "end", values=(c["aceptado_en"], TIPOS_LEGALES[c["tipo"]], version, detalle, c["registrado_por_nombre"]))
