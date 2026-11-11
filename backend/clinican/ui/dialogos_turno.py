"""Diálogos del turno: nuevo turno, mover, abono, inasistencia y bloqueo de horas."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import customtkinter as ctk

from clinican.dominio.agenda import Bloqueo, ZONA
from clinican.dominio.cupos import CategoriaCupo, Servicio, categoria_de_cupo
from clinican.dominio.errores import DatoInvalido
from clinican.dominio.estados import EstadoTurno
from clinican.servicios import agenda, clientes, configuracion, precios
from clinican.ui import formato as fmt
from clinican.ui import tema
from clinican.ui.busqueda import buscar_clientes
from clinican.ui.componentes import Campo, CampoHora, Dialogo, boton, chip, etiqueta

POR_QUE = {
    CategoriaCupo.COMPLICADO: "La mascota está marcada como de pelaje complicado.",
    CategoriaCupo.GRANDE: "La mascota es de tamaño grande.",
    CategoriaCupo.TIJERA: "El corte es a tijera.",
    CategoriaCupo.MAQUINA: "No es grande, ni complicada, ni corte a tijera.",
}


COLUMNAS = 8  # 16 franjas en dos filas


class SelectorHora(ctk.CTkFrame):
    """Día con flechas y las franjas que aún tienen cupo para una categoría."""

    def __init__(self, padre, ctx, dia: date, al_elegir=None):
        super().__init__(padre, fg_color="transparent")
        self.ctx = ctx
        self.dia = dia
        self.categoria: CategoriaCupo | None = None
        self.elegida: datetime | None = None
        self.al_elegir = al_elegir
        fila = ctk.CTkFrame(self, fg_color="transparent", width=0, height=0)
        fila.pack(fill="x")
        boton(fila, "‹", lambda: self.mover_dia(-1), ancho=36, alto=34).pack(side="left")
        self.lbl = etiqueta(fila, "", tema.CUERPO, True)
        self.lbl.pack(side="left", padx=10)
        boton(fila, "›", lambda: self.mover_dia(1), ancho=36, alto=34).pack(side="left")
        self.rejilla = ctk.CTkFrame(self, fg_color="transparent", width=0, height=0)
        self.rejilla.pack(fill="x", pady=(10, 0))
        for c in range(COLUMNAS):
            self.rejilla.grid_columnconfigure(c, weight=1, uniform="h")

    def mover_dia(self, delta: int) -> None:
        self.dia += timedelta(days=delta)
        self.elegida = None
        self.dibujar()
        if self.al_elegir:
            self.al_elegir()

    def poner(self, categoria: CategoriaCupo | None, elegida: datetime | None = None) -> None:
        self.categoria = categoria
        if elegida is not None:
            self.elegida = elegida
        self.dibujar()

    def dibujar(self) -> None:
        for w in self.rejilla.winfo_children():
            w.destroy()
        self.lbl.configure(text=fmt.dia_largo(self.dia) + (" (hoy)" if self.dia == self.ctx.hoy() else ""))
        if self.categoria is None:
            etiqueta(self.rejilla, "Elige cliente, mascota y servicio para ver las horas con cupo.",
                     suave=True).grid(row=0, column=0, columnspan=COLUMNAS, sticky="w")
            return
        ahora = self.ctx.ahora()
        with self.ctx.con() as con:
            disp = [(f, libres[self.categoria]) for f, libres in agenda.disponibilidad(con, self.dia, ahora=ahora)
                    if f.inicio > ahora]
        if not disp:
            etiqueta(self.rejilla, "No quedan horas este día. Prueba con otro día.", suave=True).grid(
                row=0, column=0, columnspan=COLUMNAS, sticky="w")
            return
        if self.elegida and not any(f.inicio == self.elegida and n for f, n in disp):
            self.elegida = None
        for i, (franja, n) in enumerate(disp):
            lleno = n <= 0
            sel = franja.inicio == self.elegida
            texto = f"{fmt.hora(franja.inicio)}\n{'Lleno' if lleno else ('1 libre' if n == 1 else f'{n} libres')}"
            b = ctk.CTkButton(
                self.rejilla, text=texto, height=44, width=70, corner_radius=tema.RADIO,
                font=tema.fuente(tema.ETIQUETA + 1, sel),
                fg_color=tema.TINTA if sel else (tema.SUPERFICIE_SUAVE if lleno else tema.SUPERFICIE),
                text_color=tema.SELECCION_TEXTO if sel else (tema.TINTA_SUAVE if lleno else tema.TINTA),
                hover_color=tema.TINTA if sel else tema.HOVER_NEUTRO, border_width=0 if lleno else 1,
                border_color=tema.BORDE_CAMPO, state="disabled" if lleno else "normal",
                command=lambda inicio=franja.inicio: self.elegir(inicio))
            b.grid(row=i // COLUMNAS, column=i % COLUMNAS, sticky="ew", padx=3, pady=3)

    def elegir(self, inicio: datetime) -> None:
        self.elegida = inicio
        self.dibujar()
        if self.al_elegir:
            self.al_elegir()


class DialogoNuevoTurno(Dialogo):
    def __init__(self, padre, ctx, dia: date, inicio: datetime | None = None,
                 categoria: CategoriaCupo | None = None, mascota_id: int | None = None):
        super().__init__(padre, "Nuevo turno", ancho=760)
        self.ctx = ctx
        self.pantalla = padre
        self.propietario = None
        self.mascotas = []
        self.razas = {}
        self.categoria_sugerida = categoria
        with ctx.con() as con:
            self.cfg = configuracion.cargar(con)
        c = self.contenido

        self.campo_buscar = Campo(c, "Cliente", ancho=700, placeholder="Cédula, nombre, celular o mascota")
        self.campo_buscar.pack(fill="x")
        self.campo_buscar.entrada.bind("<KeyRelease>", lambda _e: self._buscar())
        self.resultados = ctk.CTkFrame(c, fg_color="transparent", width=0, height=0)
        self.resultados.pack(fill="x")
        self.ficha_cliente = ctk.CTkFrame(c, fg_color="transparent", width=0, height=0)
        self.ficha_cliente.pack(fill="x")

        medio = ctk.CTkFrame(c, fg_color="transparent", width=0, height=0)
        medio.pack(fill="x", pady=(8, 0))
        medio.grid_columnconfigure((0, 1), weight=1, uniform="m")
        izq = ctk.CTkFrame(medio, fg_color="transparent", width=0, height=0)
        izq.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        etiqueta(izq, "Mascota", tema.ETIQUETA + 1, True).pack(anchor="w")
        self.var_mascota = ctk.IntVar(value=0)
        self.caja_mascotas = ctk.CTkFrame(izq, fg_color="transparent", width=0, height=0)
        self.caja_mascotas.pack(fill="x", pady=(4, 0))
        der = ctk.CTkFrame(medio, fg_color="transparent", width=0, height=0)
        der.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        etiqueta(der, "Servicio", tema.ETIQUETA + 1, True).pack(anchor="w")
        self.var_servicio = ctk.StringVar(value=Servicio.CORTE_MAQUINA.value)
        for s in Servicio:
            ctk.CTkRadioButton(der, text=fmt.SERVICIO[s], value=s.value, variable=self.var_servicio,
                               font=tema.fuente(tema.CUERPO), text_color=tema.TINTA,
                               fg_color=tema.TINTA, hover_color=tema.TINTA_SUAVE,
                               command=self._actualizar).pack(anchor="w", pady=4)

        self.lbl_categoria = ctk.CTkLabel(c, text="", anchor="w", justify="left", fg_color=tema.SUPERFICIE_SUAVE,
                                          corner_radius=8, text_color=tema.TINTA, font=tema.fuente(tema.ETIQUETA + 1),
                                          wraplength=690)
        self.lbl_categoria.pack(fill="x", pady=(12, 0), ipady=6, ipadx=8)

        etiqueta(c, "Hora", tema.ETIQUETA + 1, True).pack(anchor="w", pady=(14, 4))
        self.selector = SelectorHora(c, ctx, dia, al_elegir=self._resumen)
        self.selector.elegida = inicio
        self.selector.pack(fill="x")

        pie = ctk.CTkFrame(c, fg_color="transparent", width=0, height=0)
        pie.pack(fill="x", pady=(16, 0))
        self.lbl_resumen = etiqueta(pie, "", tema.CUERPO)
        self.lbl_resumen.pack(side="left", anchor="s")
        self.campo_abono = Campo(pie, "Abono recibido ahora", ancho=180, placeholder="$0",
                                 validar=self._validar_monto)
        self.campo_abono.pack(side="right")

        self.boton_principal("Agendar", self._agendar)
        self.boton_cancelar()
        self.after(80, self.campo_buscar.entrada.focus_set)

        if mascota_id:
            with ctx.con() as con:
                m = clientes.obtener_mascota(con, mascota_id)
                self._elegir_cliente(clientes.obtener_propietario(con, m.propietario_id), m.id)
        if categoria is CategoriaCupo.TIJERA:
            self.var_servicio.set(Servicio.CORTE_TIJERA.value)
        self._actualizar()

    # -------------------------------------------------------------- cliente y mascota
    def _buscar(self) -> None:
        for w in self.resultados.winfo_children():
            w.destroy()
        texto = self.campo_buscar.valor()
        if len(texto) < 2:
            return
        with self.ctx.con() as con:
            encontrados = buscar_clientes(con, texto, limite=5)
        if not encontrados:
            fila = ctk.CTkFrame(self.resultados, fg_color="transparent", width=0, height=0)
            fila.pack(fill="x")
            etiqueta(fila, "No hay clientes con ese dato.", suave=True).pack(side="left")
            boton(fila, "Crear cliente nuevo", self._cliente_nuevo, "enlace").pack(side="left", padx=8)
            return
        for p in encontrados:
            ctk.CTkButton(self.resultados, text=f"{p.nombre}   ·   {fmt.cedula(p.cedula)}   ·   {fmt.celular(p.telefono)}",
                          anchor="w", height=36, fg_color="transparent", hover_color=tema.HOVER_NEUTRO,
                          text_color=tema.TINTA, font=tema.fuente(tema.CUERPO),
                          command=lambda p=p: self._elegir_cliente(p)).pack(fill="x")

    def _cliente_nuevo(self) -> None:
        texto = self.campo_buscar.valor()
        app = self.pantalla.app
        self.cerrar()
        app.ir("Clientes").nuevo_cliente(texto)

    def _elegir_cliente(self, p, mascota_id: int | None = None) -> None:
        self.propietario = p
        for w in self.resultados.winfo_children():
            w.destroy()
        for w in self.ficha_cliente.winfo_children():
            w.destroy()
        with self.ctx.con() as con:
            self.mascotas = clientes.buscar_mascotas(con, propietario_id=p.id)
            self.razas = {m.raza_id: clientes.obtener_raza(con, m.raza_id) for m in self.mascotas if m.raza_id}
            sin_aviso = [t for t in agenda.inasistencias_de_propietario(con, p.id) if t.saldo_generado == 0]
        self.campo_buscar.poner(p.nombre)
        caja = ctk.CTkFrame(self.ficha_cliente, fg_color=tema.SUPERFICIE_SUAVE, corner_radius=10)
        caja.pack(fill="x", pady=(4, 0))
        etiqueta(caja, f"{p.nombre}", tema.CUERPO, True).pack(side="left", padx=(14, 6), pady=10)
        etiqueta(caja, f"{fmt.cedula(p.cedula)} · {fmt.celular(p.telefono)}", suave=True).pack(side="left")
        if sin_aviso:
            f, l, _b, _n, _i = tema.estilo_estado(EstadoTurno.PENDIENTE_ABONO)
            chip(caja, f"{len(sin_aviso)} inasistencia{'s' if len(sin_aviso) != 1 else ''} sin aviso", f, l).pack(side="right", padx=8)
        if p.saldo_a_favor:
            f, l, _b, _n, _i = tema.estilo_estado(EstadoTurno.CONFIRMADO)
            chip(caja, f"Saldo a favor {fmt.pesos(p.saldo_a_favor)}", f, l).pack(side="right", padx=8)

        for w in self.caja_mascotas.winfo_children():
            w.destroy()
        if not self.mascotas:
            etiqueta(self.caja_mascotas, "Este cliente no tiene mascotas activas. Agrégala en Clientes.",
                     suave=True, wraplength=320).pack(anchor="w")
        for m in self.mascotas:
            raza = self.razas.get(m.raza_id)
            texto = f"{m.nombre} · {raza.nombre if raza else 'sin raza'}, {fmt.TAMANO[m.tamano]}" + (" · complicado" if m.complicado else "")
            ctk.CTkRadioButton(self.caja_mascotas, text=texto, value=m.id, variable=self.var_mascota,
                               font=tema.fuente(tema.CUERPO), text_color=tema.TINTA, fg_color=tema.TINTA,
                               hover_color=tema.TINTA_SUAVE, command=self._actualizar).pack(anchor="w", pady=4)
        elegida = mascota_id or (self.mascotas[0].id if len(self.mascotas) == 1 else 0)
        self.var_mascota.set(elegida)
        self._actualizar()

    def _mascota(self):
        return next((m for m in self.mascotas if m.id == self.var_mascota.get()), None)

    # -------------------------------------------------------------- categoría, hora y resumen
    def _categoria(self) -> CategoriaCupo | None:
        m = self._mascota()
        if m is None:
            return None
        raza = self.razas.get(m.raza_id)
        return categoria_de_cupo(raza.nombre if raza else None, m.tamano, m.pelaje,
                                 Servicio(self.var_servicio.get()), m.complicado)

    def _actualizar(self) -> None:
        cat = self._categoria()
        if cat is None:
            self.lbl_categoria.configure(text="El cupo se calcula solo al elegir la mascota y el servicio.")
        else:
            with self.ctx.con() as con:
                precio = precios.precio_en_fecha(con, cat, self.selector.dia)
            self.lbl_categoria.configure(text=f"Va al cupo {fmt.CATEGORIA[cat].upper()}. {POR_QUE[cat]} "
                                              f"Precio vigente {fmt.pesos(precio)}.")
        self.selector.poner(cat)
        self._resumen()

    def _validar_monto(self, texto: str) -> str | None:
        try:
            fmt.leer_pesos(texto)
        except DatoInvalido as e:
            return str(e)
        return None

    def _resumen(self) -> None:
        abono = self.cfg.abono
        saldo = min(self.propietario.saldo_a_favor, abono) if self.propietario else 0
        falta = abono - saldo
        partes = [f"Abono {fmt.pesos(abono)}"]
        if saldo:
            partes.append(f"saldo a favor − {fmt.pesos(saldo)}")
        partes.append(f"falta pagar {fmt.pesos(falta)} en {self.cfg.minutos_expiracion} min" if falta else "queda confirmado")
        self.lbl_resumen.configure(text=" · ".join(partes))
        if self.selector.elegida:
            self.botones.winfo_children()[0].configure(text=f"Agendar a las {fmt.hora(self.selector.elegida)}")

    def _agendar(self) -> None:
        if self.propietario is None:
            self.error("Elige el cliente.")
            return
        m = self._mascota()
        if m is None:
            self.error("Elige la mascota.")
            return
        if self.selector.elegida is None:
            self.error("Elige la hora.")
            return
        if not self.campo_abono.revisar():
            return
        monto = fmt.leer_pesos(self.campo_abono.valor())
        servicio = Servicio(self.var_servicio.get())
        inicio = self.selector.elegida

        def crear():
            with self.ctx.con() as con:
                turno = agenda.crear_turno(con, m.id, inicio, servicio, ahora=self.ctx.ahora())
                if monto and turno.estado is EstadoTurno.PENDIENTE_ABONO:
                    turno = agenda.registrar_abono(con, turno.id, monto, ahora=self.ctx.ahora())
                return turno

        if self.intentar(crear):
            self.cerrar()
        else:
            self.selector.dibujar()


class DialogoMover(Dialogo):
    def __init__(self, padre, ctx, turno):
        super().__init__(padre, "Mover turno", ancho=680,
                         subtitulo=f"Ahora: {fmt.momento(turno.inicio, ctx.hoy())}, cupo {fmt.CATEGORIA[turno.categoria]}. "
                                   "Solo se muestran las horas con cupo para esa categoría.")
        self.ctx = ctx
        self.turno = turno
        self.selector = SelectorHora(self.contenido, ctx, fmt.local(turno.inicio).date())
        self.selector.pack(fill="x")
        self.selector.poner(turno.categoria)
        self.boton_principal("Mover", self._mover)
        self.boton_cancelar()

    def _mover(self) -> None:
        if not self.selector.elegida:
            self.error("Elige la nueva hora.")
            return

        def mover():
            with self.ctx.con() as con:
                return agenda.mover_turno(con, self.turno.id, self.selector.elegida, ahora=self.ctx.ahora())

        if self.intentar(mover):
            self.cerrar()


class DialogoAbono(Dialogo):
    def __init__(self, padre, ctx, turno):
        super().__init__(padre, "Registrar abono", ancho=440,
                         subtitulo=f"Pagado {fmt.pesos(turno.abono_total)} de {fmt.pesos(turno.abono_requerido)}. "
                                   "Si paga de más, el excedente queda como saldo a favor.")
        self.ctx = ctx
        self.turno = turno
        self.campo = Campo(self.contenido, "Valor recibido", fmt.pesos(turno.faltante), ancho=200,
                           validar=lambda t: None if self._monto(t) else "Escribe un valor mayor que cero")
        self.campo.pack(anchor="w")
        self.boton_principal("Registrar abono", self._registrar)
        self.boton_cancelar()
        self.after(80, lambda: (self.campo.entrada.focus_set(), self.campo.entrada.select_range(0, "end")))

    @staticmethod
    def _monto(texto: str) -> int:
        try:
            return fmt.leer_pesos(texto)
        except DatoInvalido:
            return 0

    def _registrar(self) -> None:
        if not self.campo.revisar():
            return
        monto = self._monto(self.campo.valor())

        def registrar():
            with self.ctx.con() as con:
                return agenda.registrar_abono(con, self.turno.id, monto, ahora=self.ctx.ahora())

        if self.intentar(registrar):
            self.cerrar()


class DialogoInasistencia(Dialogo):
    def __init__(self, padre, ctx, turno):
        super().__init__(padre, "Marcar inasistencia", ancho=480,
                         subtitulo="Si el cliente avisó con 12 horas o más de anticipación, el abono queda a favor; "
                                   "si no, se pierde. Esto no se puede deshacer.")
        self.ctx = ctx
        self.turno = turno
        self.var = ctk.StringVar(value="no")
        for valor, texto in (("no", "No avisó"), ("si", "Avisó antes")):
            ctk.CTkRadioButton(self.contenido, text=texto, value=valor, variable=self.var, font=tema.fuente(tema.CUERPO),
                               text_color=tema.TINTA, fg_color=tema.TINTA, command=self._cambio).pack(anchor="w", pady=4)
        self.campo = Campo(self.contenido, "Cuándo avisó (dd/mm/aaaa hh:mm)",
                           fmt.local(ctx.ahora()).strftime("%d/%m/%Y %H:%M"), ancho=240)
        self.boton_principal("Marcar inasistencia", self._marcar)
        self.boton_cancelar("No, volver")

    def _cambio(self) -> None:
        if self.var.get() == "si":
            self.campo.pack(anchor="w", pady=(8, 0))
        else:
            self.campo.pack_forget()

    def _marcar(self) -> None:
        aviso = None
        if self.var.get() == "si":
            try:
                aviso = datetime.strptime(self.campo.valor(), "%d/%m/%Y %H:%M").replace(tzinfo=ZONA)
            except ValueError:
                self.campo.error("Escribe la fecha y hora así: 10/11/2026 15:30")
                return

        def marcar():
            with self.ctx.con() as con:
                return agenda.marcar_inasistencia(con, self.turno.id, aviso, ahora=self.ctx.ahora())

        if self.intentar(marcar):
            self.cerrar()


class DialogoBloqueo(Dialogo):
    def __init__(self, padre, ctx, dia: date):
        super().__init__(padre, "Bloquear horas", ancho=480,
                         subtitulo="No se puede bloquear un rango que ya tenga turnos activos.")
        self.ctx = ctx
        self.campo_fecha = Campo(self.contenido, "Día (dd/mm/aaaa)", fmt.fecha_numerica(dia), ancho=180)
        self.campo_fecha.pack(anchor="w")
        self.var_completo = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self.contenido, text="Todo el día", variable=self.var_completo, font=tema.fuente(tema.CUERPO),
                        text_color=tema.TINTA, fg_color=tema.TINTA, command=self._cambio).pack(anchor="w", pady=(4, 8))
        self.horas = ctk.CTkFrame(self.contenido, fg_color="transparent", width=0, height=0)
        self.horas.pack(anchor="w")
        opciones = [f"{h:02d}:{m:02d}" for h in range(7, 21) for m in (0, 30)]
        etiqueta(self.horas, "Desde", tema.ETIQUETA + 1, True).grid(row=0, column=0, sticky="w")
        etiqueta(self.horas, "Hasta", tema.ETIQUETA + 1, True).grid(row=0, column=1, sticky="w", padx=(16, 0))
        self.desde = CampoHora(self.horas, "12:00", opciones)
        self.desde.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.hasta = CampoHora(self.horas, "13:00", opciones)
        self.hasta.grid(row=1, column=1, sticky="w", padx=(16, 0), pady=(4, 0))
        self.campo_motivo = Campo(self.contenido, "Motivo", "Almuerzo", ancho=300)
        self.campo_motivo.pack(anchor="w", pady=(10, 0))
        self.boton_principal("Bloquear", self._bloquear)
        self.boton_cancelar()

    def _cambio(self) -> None:
        if self.var_completo.get():
            self.horas.pack_forget()
        else:
            self.horas.pack(anchor="w", before=self.campo_motivo)

    def _bloquear(self) -> None:
        try:
            fecha = fmt.leer_fecha(self.campo_fecha.valor())
        except DatoInvalido as e:
            self.campo_fecha.error(str(e))
            return
        self.campo_fecha.error(None)
        try:
            if self.var_completo.get():
                bloqueo = Bloqueo(fecha, motivo=self.campo_motivo.valor())
            else:
                bloqueo = Bloqueo(fecha, self.desde.hora(), self.hasta.hora(), self.campo_motivo.valor())
        except DatoInvalido as e:
            self.error(f"Revisa las horas: {e}.")
            return
        except ValueError:
            self.error("La hora «hasta» debe ser posterior a «desde».")
            return

        def crear():
            with self.ctx.con() as con:
                return agenda.crear_bloqueo(con, bloqueo, ahora=self.ctx.ahora())

        if self.intentar(crear):
            self.cerrar()
