"""Clientes: búsqueda, ficha del propietario, mascotas, historial, unir duplicados e importar Excel."""

from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from clinican.dominio.cupos import Servicio, Tamano, categoria_de_cupo
from clinican.dominio.documentos import fecha_nacimiento_aproximada
from clinican.dominio.errores import DatoInvalido
from clinican.dominio.estados import EstadoTurno
from clinican.servicios import agenda, autorizaciones, clientes, consultas
from clinican.ui import formato as fmt
from clinican.ui import tema
from clinican.ui.app import Pantalla
from clinican.ui.busqueda import buscar_clientes
from clinican.ui.componentes import Campo, Dialogo, Lista, Texto, boton, chip, confirmar, etiqueta, tarjeta

E = EstadoTurno


def _validar_celular(texto: str) -> str | None:
    d = "".join(ch for ch in texto if ch.isdigit())
    if len(d) != 10:
        return f"El celular tiene 10 dígitos ({len(d)} escritos)."
    return None


def _validar_cedula(texto: str) -> str | None:
    return None if any(ch.isdigit() for ch in texto) else "La cédula es obligatoria."


class PantallaClientes(Pantalla):
    def __init__(self, app):
        super().__init__(app)
        self.seleccion: int | None = None

        izq = ctk.CTkFrame(self, fg_color="transparent", width=320)
        izq.pack(side="left", fill="y", padx=(24, 0), pady=20)
        izq.pack_propagate(False)
        self.buscar = ctk.CTkEntry(izq, height=tema.ALTO_CONTROL, corner_radius=tema.RADIO, border_width=2,
                                   border_color=tema.TINTA, fg_color=tema.SUPERFICIE, text_color=tema.TINTA,
                                   placeholder_text="Cédula, nombre, celular o mascota", font=tema.fuente(tema.CUERPO))
        self.buscar.pack(fill="x")
        self.buscar.bind("<KeyRelease>", lambda _e: self._listar())
        self.lbl_cuenta = etiqueta(izq, "", tema.ETIQUETA, suave=True)
        self.lbl_cuenta.pack(anchor="w", pady=(6, 4))
        self.lista = Lista(izq)
        self.lista.pack(fill="both", expand=True)
        boton(izq, "+ Cliente nuevo", lambda: self.nuevo_cliente()).pack(fill="x", pady=(10, 0))
        boton(izq, "Importar mascotas desde Excel…", self.importar, "enlace").pack(fill="x", pady=(4, 0))

        self.detalle = Lista(self)
        self.detalle.pack(side="left", fill="both", expand=True, padx=24, pady=20)

    def enfocar_busqueda(self) -> None:
        self.buscar.focus_set()
        self.buscar.select_range(0, "end")

    def refrescar(self) -> None:
        self._listar()
        self._dibujar_detalle()

    def refrescar_periodico(self) -> None:
        pass

    # ------------------------------------------------------------------ lista
    def _listar(self) -> None:
        self.lista.vaciar()
        texto = self.buscar.get().strip()
        with self.ctx.con() as con:
            encontrados = buscar_clientes(con, texto, limite=200) if texto else clientes.buscar_propietarios(con)[:200]
            mascotas = {p.id: [m.nombre for m in clientes.buscar_mascotas(con, propietario_id=p.id)] for p in encontrados}
        repetidos = Counter(p.telefono for p in encontrados)
        self.lbl_cuenta.configure(text=f"{len(encontrados)} cliente{'s' if len(encontrados) != 1 else ''} · Ctrl+F")
        if not encontrados:
            etiqueta(self.lista, "Nadie coincide con esa búsqueda.", suave=True).pack(anchor="w", pady=8)
        for p in encontrados:
            sel = p.id == self.seleccion
            duplicado = repetidos[p.telefono] > 1
            linea2 = ("Posible duplicado · " if duplicado else ", ".join(mascotas[p.id]) + " · ") + fmt.celular(p.telefono)
            b = ctk.CTkButton(self.lista, text=f"{p.nombre}\n{linea2}", anchor="w", height=52, corner_radius=tema.RADIO,
                              fg_color=tema.SUPERFICIE if sel else "transparent", hover_color=tema.HOVER_NEUTRO,
                              border_width=2 if sel else 0, border_color=tema.TINTA,
                              text_color=tema.TINTA, font=tema.fuente(tema.ETIQUETA + 1, sel),
                              command=lambda p=p: self.elegir(p.id))
            b.pack(fill="x", pady=2)

    def elegir(self, propietario_id: int) -> None:
        self.seleccion = propietario_id
        self.refrescar()

    # ------------------------------------------------------------------ detalle
    def _dibujar_detalle(self) -> None:
        self.detalle.vaciar()
        d = self.detalle
        if self.seleccion is None:
            etiqueta(d, "Busca un cliente o elige uno de la lista.", tema.SUBTITULO, suave=True).pack(anchor="w", pady=20)
            return
        hoy = self.ctx.hoy()
        with self.ctx.con() as con:
            p = clientes.obtener_propietario(con, self.seleccion)
            mascotas = clientes.buscar_mascotas(con, propietario_id=p.id)
            razas = {m.raza_id: clientes.obtener_raza(con, m.raza_id) for m in mascotas if m.raza_id}
            historial = []
            for m in mascotas:
                historial += [(t, f, m) for t, f in consultas.historial_de_mascota(con, m.id)]
            inasist = agenda.inasistencias_de_propietario(con, p.id)
            autorizacion = autorizaciones.autorizacion_vigente(con, p.id)
        historial.sort(key=lambda x: x[0].inicio, reverse=True)

        cab = ctk.CTkFrame(d, fg_color="transparent", width=0, height=0)
        cab.pack(fill="x")
        textos = ctk.CTkFrame(cab, fg_color="transparent", width=0, height=0)
        textos.pack(side="left", fill="x", expand=True)
        etiqueta(textos, p.nombre, tema.TITULO, True).pack(anchor="w")
        linea = f"{fmt.cedula(p.cedula)} · {fmt.celular(p.telefono)}" + (f" · {p.direccion}" if p.direccion else "")
        etiqueta(textos, linea, suave=True).pack(anchor="w")
        primera = mascotas[0].id if len(mascotas) == 1 else None
        boton(cab, "+ Nuevo turno", lambda: self.app.nuevo_turno(mascota_id=primera) if primera else self._turno_sin_mascota(),
              "principal").pack(side="right")
        boton(cab, "Unir con otro…", lambda: self.unir(p)).pack(side="right", padx=tema.SEP)
        boton(cab, "Editar", lambda: self.editar(p)).pack(side="right")

        metricas = ctk.CTkFrame(d, fg_color="transparent", width=0, height=0)
        metricas.pack(fill="x", pady=(16, 0))
        metricas.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="m")
        ultima = next((t for t, _f, _m in historial if t.estado in (E.ATENDIDO, E.ENTREGADO)), None)
        sin_aviso = [t for t in inasist if t.saldo_generado == 0]
        datos = [
            ("Saldo a favor", fmt.pesos(p.saldo_a_favor), "Se usa en el próximo turno" if p.saldo_a_favor else "Sin saldo"),
            ("Última visita", fmt.dia_corto(fmt.local(ultima.inicio).date(), hoy) if ultima else "—",
             next((m.nombre for t, _f, m in historial if t is ultima), "") if ultima else "Aún no ha venido"),
            ("Inasistencias", str(len(inasist)), f"{len(sin_aviso)} sin aviso (abono perdido)" if sin_aviso else "Ninguna sin aviso"),
            ("Datos personales", "Autorizó" if autorizacion else "Sin autorización",
             f"Desde el {fmt.fecha_numerica(autorizacion.fecha)}" if autorizacion else "Ley 1581: márcala en Editar"),
        ]
        for i, (titulo, valor, nota) in enumerate(datos):
            t = tarjeta(metricas)
            t.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0 if i == len(datos) - 1 else 6))
            etiqueta(t, titulo, tema.ETIQUETA, suave=True).pack(anchor="w", padx=16, pady=(12, 0))
            etiqueta(t, valor, tema.SUBTITULO, True).pack(anchor="w", padx=16)
            etiqueta(t, nota, tema.ETIQUETA, suave=True).pack(anchor="w", padx=16, pady=(0, 12))

        fila = ctk.CTkFrame(d, fg_color="transparent", width=0, height=0)
        fila.pack(fill="x", pady=(20, 6))
        etiqueta(fila, "Mascotas", tema.SUBTITULO, True).pack(side="left")
        boton(fila, "+ Mascota", lambda: self.mascota(p.id), "enlace", ancho=110).pack(side="right")
        rejilla = ctk.CTkFrame(d, fg_color="transparent", width=0, height=0)
        rejilla.pack(fill="x")
        rejilla.grid_columnconfigure((0, 1), weight=1, uniform="r")
        if not mascotas:
            etiqueta(rejilla, "Todavía no tiene mascotas.", suave=True).grid(row=0, column=0, sticky="w")
        for i, m in enumerate(mascotas):
            raza = razas.get(m.raza_id)
            cat = categoria_de_cupo(raza.nombre if raza else None, m.tamano, m.pelaje, Servicio.CORTE_MAQUINA, m.complicado)
            t = tarjeta(rejilla)
            t.grid(row=i // 2, column=i % 2, sticky="nsew", padx=(0 if i % 2 == 0 else 6, 6 if i % 2 == 0 else 0), pady=6)
            arriba = ctk.CTkFrame(t, fg_color="transparent", width=0, height=0)
            arriba.pack(fill="x", padx=16, pady=(12, 0))
            etiqueta(arriba, m.nombre, 17, True).pack(side="left")
            chip(arriba, f"CUPO {fmt.CATEGORIA[cat].upper()}", tema.SUPERFICIE_SUAVE, tema.TINTA).pack(side="left", padx=10)
            boton(arriba, "Editar", lambda m=m: self.mascota(p.id, m), "enlace", ancho=70, alto=30).pack(side="right")
            boton(arriba, "Turno", lambda m=m: self.app.nuevo_turno(mascota_id=m.id), "enlace", ancho=70, alto=30).pack(side="right")
            detalle = f"{raza.nombre if raza else 'Sin raza'} · {fmt.TAMANO[m.tamano]}"
            if m.fecha_nacimiento:
                detalle += f" · {max(0, (hoy - m.fecha_nacimiento).days // 365)} años aprox."
            if m.complicado:
                detalle += " · pelaje complicado"
            etiqueta(t, detalle, tema.ETIQUETA + 1, suave=True, wraplength=380).pack(anchor="w", padx=16)
            if m.observaciones:
                etiqueta(t, m.observaciones, tema.ETIQUETA, suave=True, wraplength=380).pack(anchor="w", padx=16)
            ctk.CTkFrame(t, height=10, fg_color="transparent").pack()

        etiqueta(d, "Historial", tema.SUBTITULO, True).pack(anchor="w", pady=(20, 6))
        tabla = tarjeta(d)
        tabla.pack(fill="x")
        tabla.grid_columnconfigure(4, weight=1)
        for c, titulo in enumerate(("Fecha", "Mascota", "Servicio", "Estado", "Precio final")):
            etiqueta(tabla, titulo, tema.ETIQUETA, True, suave=True).grid(row=0, column=c, sticky="e" if c == 4 else "w",
                                                                          padx=16, pady=(10, 6))
        if not historial:
            etiqueta(tabla, "Sin turnos todavía.", suave=True).grid(row=1, column=0, columnspan=5, sticky="w", padx=16, pady=(0, 12))
        for r, (t, f, m) in enumerate(historial[:60], start=1):
            nombre_estado = tema.estilo_estado(t.estado)[3]
            if t.estado is E.INASISTENCIA:
                nombre_estado += " con aviso" if t.saldo_generado else " sin aviso"
            elif t.estado in (E.CANCELADO, E.LIBERADO) and t.saldo_generado:
                nombre_estado += f" · {fmt.pesos(t.saldo_generado)} a favor"
            color = tema.estilo_estado(E.PENDIENTE_ABONO)[1] if t.estado in (E.PENDIENTE_ABONO, E.INASISTENCIA) else None
            valores = (fmt.momento(t.inicio, hoy), m.nombre, fmt.SERVICIO[t.servicio], nombre_estado)
            for c, v in enumerate(valores):
                etiqueta(tabla, v, color=color if c == 3 else None).grid(row=r, column=c, sticky="w", padx=16, pady=4)
            if f:
                boton(tabla, fmt.pesos(f.precio_final), lambda t=t: self.ver_ficha(t.id), "enlace", ancho=100,
                      alto=30).grid(row=r, column=4, sticky="e", padx=10)
            else:
                etiqueta(tabla, "—", suave=True).grid(row=r, column=4, sticky="e", padx=16)
        ctk.CTkFrame(tabla, height=8, fg_color="transparent").grid(row=999, column=0)

    def _turno_sin_mascota(self) -> None:
        self.avisar("Elige la mascota con su botón «Turno», o agrégale una mascota primero.", error=True)

    # ------------------------------------------------------------------ acciones
    def nuevo_cliente(self, texto: str = "") -> None:
        nuevo = DialogoCliente(self, self.ctx, None, texto).mostrar()
        if nuevo:
            self.seleccion = nuevo.id
            self.buscar.delete(0, "end")
            self.avisar(f"Cliente {nuevo.nombre} creado. Agrégale su mascota.")
            self.refrescar()
            self.mascota(nuevo.id)

    def editar(self, p) -> None:
        if DialogoCliente(self, self.ctx, p).mostrar():
            self.avisar("Datos guardados.")
            self.refrescar()

    def mascota(self, propietario_id: int, m=None) -> None:
        if DialogoMascota(self, self.ctx, propietario_id, m).mostrar():
            self.avisar("Mascota guardada.")
            self.refrescar()

    def ver_ficha(self, turno_id: int) -> None:
        from clinican.ui.dialogo_ficha import DialogoFicha

        if DialogoFicha(self, self.ctx, turno_id).mostrar():
            self.avisar("Ficha actualizada.")
            self.refrescar()

    def unir(self, destino) -> None:
        if DialogoUnir(self, self.ctx, destino).mostrar():
            self.avisar("Clientes unidos.")
            self.refrescar()

    def importar(self) -> None:
        if self.ctx.importar_excel is None:
            self.avisar("La importación desde Excel no está disponible.", error=True)
            return
        ruta = filedialog.askopenfilename(parent=self, title="Elegir el archivo de mascotas",
                                          filetypes=[("Excel", "*.xlsx"), ("Todos", "*.*")])
        if not ruta:
            return
        try:
            with self.ctx.con() as con:
                informe = self.ctx.importar_excel(con, Path(ruta), self.ctx.ahora())
        except Exception as e:  # archivo dañado, hoja faltante, etc.
            self.avisar(f"No se pudo leer el archivo: {e}", error=True)
            return
        d = Dialogo(self, "Importación terminada", ancho=560,
                    subtitulo=f"{len(informe.aceptadas)} filas aceptadas, {len(informe.rechazadas)} rechazadas.")
        if informe.rechazadas:
            caja = ctk.CTkTextbox(d.contenido, height=220, width=560, font=tema.fuente(tema.ETIQUETA + 1),
                                  fg_color=tema.SUPERFICIE_SUAVE, text_color=tema.TINTA)
            caja.insert("1.0", "\n".join(f"Fila {r.fila}: {r.motivo}" for r in informe.rechazadas))
            caja.configure(state="disabled")
            caja.pack(fill="x")
        d.boton_principal("Listo", d.cerrar)
        d.mostrar()
        self.refrescar()


class DialogoCliente(Dialogo):
    def __init__(self, padre, ctx, p=None, texto: str = ""):
        super().__init__(padre, "Editar cliente" if p else "Cliente nuevo", ancho=520)
        self.ctx = ctx
        self.p = p
        digitos = "".join(ch for ch in texto if ch.isdigit())
        c = self.contenido
        self.nombre = Campo(c, "Nombre", p.nombre if p else ("" if digitos else texto), ancho=460)
        self.nombre.pack(anchor="w")
        fila = ctk.CTkFrame(c, fg_color="transparent", width=0, height=0)
        fila.pack(anchor="w")
        self.cedula = Campo(fila, "Cédula", (p.cedula or "") if p else (digitos if len(digitos) != 10 else ""),
                            ancho=220, validar=_validar_cedula)
        self.cedula.pack(side="left")
        self.celular = Campo(fila, "Celular", fmt.celular(p.telefono) if p else (digitos if len(digitos) == 10 else ""),
                             ancho=220, validar=_validar_celular)
        self.celular.pack(side="left", padx=(20, 0))
        self.direccion = Campo(c, "Dirección (opcional)", p.direccion if p else "", ancho=460)
        self.direccion.pack(anchor="w")
        self.autorizacion = None
        if p:
            with ctx.con() as con:
                self.autorizacion = autorizaciones.autorizacion_vigente(con, p.id)
        self.autorizo = ctk.BooleanVar(value=self.autorizacion is not None)
        ctk.CTkCheckBox(c, text="Autorizó el tratamiento de sus datos (Ley 1581 de 2012)",
                        variable=self.autorizo, font=tema.fuente(tema.CUERPO), text_color=tema.TINTA,
                        fg_color=tema.TINTA).pack(anchor="w", pady=(4, 6))
        fila_aut = ctk.CTkFrame(c, fg_color="transparent")
        fila_aut.pack(anchor="w")
        fecha = self.autorizacion.fecha if self.autorizacion else ctx.hoy()
        self.fecha_autorizacion = Campo(fila_aut, "Fecha de la autorización o el retiro", fmt.fecha_numerica(fecha),
                                        ancho=220, placeholder="dd/mm/aaaa")
        self.fecha_autorizacion.pack(side="left")
        self.medio_autorizacion = Campo(fila_aut, "Cómo (opcional)", self.autorizacion.medio if self.autorizacion else "",
                                        ancho=220, placeholder="Formato firmado, WhatsApp…")
        self.medio_autorizacion.pack(side="left", padx=(20, 0))
        self.boton_principal("Guardar", self._guardar)
        self.boton_cancelar()
        self.after(80, self.nombre.entrada.focus_set)

    def _guardar(self) -> None:
        ok = all([self.cedula.revisar(), self.celular.revisar()])
        if not self.nombre.valor():
            self.nombre.error("Escribe el nombre.")
            ok = False
        if not ok:
            return
        celular = "".join(ch for ch in self.celular.valor() if ch.isdigit())
        ahora = self.ctx.ahora()
        autorizo = self.autorizo.get()
        cambia_autorizacion = autorizo != (self.autorizacion is not None) or (
            autorizo and self.autorizacion is not None and (
                self.fecha_autorizacion.valor() != fmt.fecha_numerica(self.autorizacion.fecha)
                or self.medio_autorizacion.valor() != self.autorizacion.medio))
        fecha_autorizacion = None
        if cambia_autorizacion:
            try:
                fecha_autorizacion = fmt.leer_fecha(self.fecha_autorizacion.valor())
            except DatoInvalido as e:
                self.fecha_autorizacion.error(str(e))
                return
            if fecha_autorizacion > self.ctx.hoy():
                self.fecha_autorizacion.error("La fecha no puede ser posterior a hoy.")
                return
            self.fecha_autorizacion.error(None)

        def guardar():
            with self.ctx.con() as con:
                if self.p:
                    propietario = clientes.editar_propietario(con, self.p.id, ahora=ahora, nombre=self.nombre.valor(),
                                                              telefono=celular, cedula=self.cedula.valor(),
                                                              direccion=self.direccion.valor())
                else:
                    propietario = clientes.crear_propietario(con, self.nombre.valor(), celular,
                                                             cedula=self.cedula.valor(), ahora=ahora,
                                                             direccion=self.direccion.valor())
                if cambia_autorizacion:
                    registrar = (autorizaciones.registrar_autorizacion if autorizo
                                 else autorizaciones.revocar_autorizacion)
                    registrar(con, propietario.id, fecha_autorizacion, ahora=ahora,
                              medio=self.medio_autorizacion.valor())
                return propietario

        if self.intentar(guardar):
            self.cerrar()


class DialogoMascota(Dialogo):
    def __init__(self, padre, ctx, propietario_id: int, m=None):
        super().__init__(padre, f"Editar a {m.nombre}" if m else "Mascota nueva", ancho=560)
        self.ctx = ctx
        self.m = m
        self.propietario_id = propietario_id
        with ctx.con() as con:
            self.razas = clientes.buscar_razas(con)
        c = self.contenido
        self.nombre = Campo(c, "Nombre", m.nombre if m else "", ancho=500)
        self.nombre.pack(anchor="w")
        fila = ctk.CTkFrame(c, fg_color="transparent", width=0, height=0)
        fila.pack(anchor="w", fill="x")
        etiqueta(fila, "Raza", tema.ETIQUETA + 1, True).grid(row=0, column=0, sticky="w")
        etiqueta(fila, "Tamaño", tema.ETIQUETA + 1, True).grid(row=0, column=1, sticky="w", padx=(20, 0))
        nombres = ["Sin raza"] + [r.nombre for r in self.razas]
        actual = next((r.nombre for r in self.razas if m and r.id == m.raza_id), "Sin raza")
        self.raza = ctk.CTkComboBox(fila, values=nombres, width=260, height=tema.ALTO_CONTROL, font=tema.fuente(tema.CUERPO),
                                    dropdown_font=tema.fuente(tema.CUERPO), command=self._raza_cambio,
                                    fg_color=tema.SUPERFICIE, text_color=tema.TINTA, border_color=tema.BORDE_CAMPO)
        self.raza.set(actual)
        self.raza.grid(row=1, column=0, sticky="w", pady=(4, 10))
        self.tamano = ctk.CTkSegmentedButton(fila, values=[fmt.TAMANO[t].capitalize() for t in Tamano], height=tema.ALTO_CONTROL,
                                             font=tema.fuente(tema.CUERPO), selected_color=tema.TINTA,
                                             selected_hover_color=tema.TINTA, text_color=(tema.TINTA[0], tema.TINTA[1]))
        self.tamano.set(fmt.TAMANO[m.tamano].capitalize() if m else "Mediano")
        self.tamano.grid(row=1, column=1, sticky="w", padx=(20, 0), pady=(4, 10))
        self.complicado = ctk.BooleanVar(value=bool(m and m.complicado))
        ctk.CTkCheckBox(c, text="Pelaje complicado (va al cupo COMPLICADO; obligatorio revisar en mestizos)",
                        variable=self.complicado, font=tema.fuente(tema.CUERPO), text_color=tema.TINTA,
                        fg_color=tema.TINTA).pack(anchor="w", pady=(0, 8))
        self.edad = Campo(c, "Edad en años (opcional)", "", ancho=120)
        if not m:
            self.edad.pack(anchor="w")
        self.obs = Texto(c, "Observaciones", m.observaciones if m else "", alto=70)
        self.obs.pack(fill="x")
        self.boton_principal("Guardar", self._guardar)
        if m:
            b = boton(self.botones, "Dar de baja…", self._baja, "peligro")
            b.pack(side="left")
        self.boton_cancelar()
        self.after(80, self.nombre.entrada.focus_set)

    def _raza_cambio(self, nombre: str) -> None:
        r = next((r for r in self.razas if r.nombre == nombre), None)
        if r and r.tamano:
            self.tamano.set(fmt.TAMANO[r.tamano].capitalize())

    def _guardar(self) -> None:
        if not self.nombre.valor():
            self.nombre.error("Escribe el nombre.")
            return
        raza = next((r for r in self.razas if r.nombre == self.raza.get()), None)
        if self.raza.get() not in ("Sin raza", "") and raza is None:
            self.error("Elige una raza de la lista (las razas nuevas se agregan en Ajustes › Razas).")
            return
        tamano = next(t for t in Tamano if fmt.TAMANO[t].capitalize() == self.tamano.get())
        nacimiento = None
        if self.edad.valor():
            if not self.edad.valor().isdigit():
                self.edad.error("Solo el número de años.")
                return
            nacimiento = fecha_nacimiento_aproximada(int(self.edad.valor()), 0, self.ctx.hoy())
        ahora = self.ctx.ahora()

        def guardar():
            with self.ctx.con() as con:
                datos = dict(nombre=self.nombre.valor(), raza_id=raza.id if raza else None, tamano=tamano,
                             complicado=self.complicado.get(), observaciones=self.obs.valor())
                if self.m:
                    return clientes.editar_mascota(con, self.m.id, ahora=ahora, **datos)
                return clientes.crear_mascota(con, self.propietario_id, ahora=ahora, fecha_nacimiento=nacimiento, **datos)

        if self.intentar(guardar):
            self.cerrar()

    def _baja(self) -> None:
        def baja():
            with self.ctx.con() as con:
                return clientes.desactivar_mascota(con, self.m.id, ahora=self.ctx.ahora())

        if self.intentar(baja):
            self.cerrar()


class DialogoUnir(Dialogo):
    def __init__(self, padre, ctx, destino):
        super().__init__(padre, f"Unir otro cliente en {destino.nombre}", ancho=560,
                         subtitulo="Busca el registro duplicado. Sus mascotas, turnos y saldo a favor pasan a "
                                   f"{destino.nombre}, y el duplicado queda inactivo. No se puede deshacer.")
        self.ctx = ctx
        self.destino = destino
        self.origen = None
        self.campo = Campo(self.contenido, "Cliente duplicado", fmt.celular(destino.telefono), ancho=500)
        self.campo.pack(anchor="w")
        self.campo.entrada.bind("<KeyRelease>", lambda _e: self._buscar())
        self.res = ctk.CTkFrame(self.contenido, fg_color="transparent", width=0, height=0)
        self.res.pack(fill="x")
        self.boton_principal("Unir", self._unir)
        self.boton_cancelar()
        self._buscar()

    def _buscar(self) -> None:
        for w in self.res.winfo_children():
            w.destroy()
        texto = self.campo.valor()
        if len(texto) < 2:
            return
        with self.ctx.con() as con:
            encontrados = [p for p in buscar_clientes(con, texto, 6) if p.id != self.destino.id]
        if not encontrados:
            etiqueta(self.res, "No hay otro cliente con ese dato.", suave=True).pack(anchor="w")
        for p in encontrados:
            sel = self.origen is not None and p.id == self.origen.id
            ctk.CTkButton(self.res, text=f"{p.nombre} · {fmt.cedula(p.cedula)} · {fmt.celular(p.telefono)}", anchor="w",
                          height=36, fg_color=tema.TINTA if sel else "transparent", hover_color=tema.HOVER_NEUTRO,
                          text_color=tema.SELECCION_TEXTO if sel else tema.TINTA, font=tema.fuente(tema.CUERPO),
                          command=lambda p=p: self._elegir(p)).pack(fill="x")

    def _elegir(self, p) -> None:
        self.origen = p
        self._buscar()

    def _unir(self) -> None:
        if self.origen is None:
            self.error("Elige el cliente duplicado.")
            return

        def unir():
            with self.ctx.con() as con:
                return clientes.unir_propietarios(con, self.origen.id, self.destino.id, ahora=self.ctx.ahora())

        if self.intentar(unir):
            self.cerrar()
