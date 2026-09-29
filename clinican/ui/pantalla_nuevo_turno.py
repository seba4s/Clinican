"""Nuevo turno (pantalla 3): propietario, mascotas, fecha y franja, quién agenda y abono."""

from __future__ import annotations

from datetime import date

import customtkinter as ctk

from clinican.dominio.catalogos import TIPOS_LEGALES, TIPOS_SERVICIO
from clinican.dominio.errores import ErrorClinican
from clinican.dominio.formato import pesos
from clinican.dominio.franjas import JORNADAS, MANANA, TARDE
from clinican.dominio.propietarios import cedula_visible, formato_celular
from clinican.servicios import legal, personal, propietarios, turnos
from clinican.servicios.turnos import Abono
from clinican.ui import dialogos, tema
from clinican.ui.panel_turno import MEDIOS, SelectorHoras, avisar_liberados, datos_pago
from clinican.ui.selector_raza import SelectorRaza

SIN_ABONO = "SIN_ABONO"


class PantallaNuevoTurno(ctk.CTkFrame):
    def __init__(self, padre, ctx, fecha: str | None = None, propietario_id: int | None = None):
        super().__init__(padre, fg_color="transparent")
        self.ctx = ctx
        self.dueno = None
        self.elegidas: dict[int, dict] = {}     # mascota_id -> {"var": IntVar, "tipo": código}
        self.plan: list[tuple[int, str, str, str]] = []   # (mascota, tipo, fecha, hora)
        self.faltan: list[int] = []
        self.fecha = ctk.StringVar(value=fecha or date.today().isoformat())
        self.jornada = MANANA
        self.medio = "NEQUI"
        self.monto = ctk.StringVar()
        self.referencia = ctk.StringVar()
        self.usar_a_favor = ctk.IntVar(value=0)
        self.verificado = ctk.IntVar(value=0)
        self.activos = {p["nombre"]: p["id"] for p in personal.listar_activos(ctx.conn)}
        self.quien = ctx.sesion.nombre if ctx.sesion.nombre in self.activos else next(iter(self.activos))

        arriba = ctk.CTkFrame(self, fg_color="transparent")
        arriba.pack(fill="x", pady=(0, 10))
        tema.titulo(arriba, "Nuevo turno").pack(side="left")
        tema.boton(arriba, "Empezar de nuevo", lambda: ctx.ventana.mostrar("Nuevo turno"), estilo="secundario",
                   ancho=200).pack(side="right")
        self.cuerpo = ctk.CTkScrollableFrame(self, fg_color=tema.BLANCO, corner_radius=14, border_width=1,
                                             border_color=tema.BORDE)
        self.cuerpo.pack(fill="both", expand=True)
        if propietario_id:
            self._elegir_dueno(propietario_id)
        else:
            self._dibujar()

    # ------------------------------------------------------------- utilidades
    def _seccion(self, numero: int, titulo: str) -> ctk.CTkFrame:
        caja = ctk.CTkFrame(self.cuerpo, fg_color="transparent")
        caja.pack(fill="x", padx=20, pady=(14, 4))
        tema.subtitulo(caja, f"{numero}. {titulo}").pack(anchor="w", pady=(0, 6))
        return caja

    def _seleccionadas(self) -> list[tuple[int, str]]:
        return [(mid, d["tipo"]) for mid, d in self.elegidas.items() if d["var"].get()]

    def _reiniciar_plan(self) -> None:
        self.plan, self.faltan = [], []
        self._dibujar()

    # ---------------------------------------------------------------- dibujo
    def _dibujar(self) -> None:
        for hijo in self.cuerpo.winfo_children():
            hijo.destroy()
        self._paso_propietario()
        if self.dueno is None:
            return
        if not self._paso_consentimientos():
            return
        if not self._paso_mascotas():
            return
        self._paso_horario()
        if not self.plan or self.faltan:
            return
        self._paso_quien()
        self._paso_abono()

    def _paso_propietario(self) -> None:
        caja = self._seccion(1, "Propietario")
        if self.dueno is not None:
            fila = ctk.CTkFrame(caja, fg_color="transparent")
            fila.pack(fill="x")
            d = self.dueno
            tema.etiqueta(fila, f"{d['nombre']} · C.C. {cedula_visible(d)} · {formato_celular(d['celular1'])}",
                          negrita=True).pack(side="left")
            tema.boton(fila, "Cambiar", self._quitar_dueno, estilo="secundario", ancho=130).pack(side="left", padx=12)
            return
        fila = ctk.CTkFrame(caja, fg_color="transparent")
        fila.pack(fill="x")
        busqueda = tema.entrada(fila, ancho=460, placeholder_text="Cédula, nombre, celular o mascota")
        busqueda.pack(side="left")
        # height=1: un CTkFrame vacío mide 200 px y dejaría un hueco antes de tener resultados
        resultados = ctk.CTkFrame(caja, fg_color="transparent", height=1)
        resultados.pack(fill="x", pady=6)
        self.zona_cliente_nuevo = ctk.CTkFrame(caja, fg_color="transparent", height=1)
        self.zona_cliente_nuevo.pack(fill="x")
        tema.boton(self.zona_cliente_nuevo, "+ Cliente nuevo: agendar sin registrarlo", self._form_cliente_nuevo,
                   estilo="secundario", ancho=420).pack(anchor="w", pady=(4, 0))

        def buscar(_e=None):
            for h in resultados.winfo_children():
                h.destroy()
            filas = dialogos.ejecutar(self, propietarios.buscar, self.ctx.conn, self.ctx.sesion, busqueda.get())
            if filas is dialogos.FALLO:
                return
            if not filas:
                tema.etiqueta(resultados, "No se encontró. Si es un cliente nuevo, agéndelo con «Cliente nuevo»; "
                                          "sus datos completos se registran cuando llegue.",
                              color=tema.ROJO_ERROR, wraplength=800).pack(anchor="w")
            for f in filas[:8]:
                texto = f"{f['nombre']} · C.C. {cedula_visible(f)} · {f['mascotas'] or 'sin mascotas'}"
                tema.boton(resultados, texto, lambda i=f["id"]: self._elegir_dueno(i), estilo="secundario",
                           ancho=700, anchor="w").pack(anchor="w", pady=3)

        busqueda.bind("<Return>", buscar)
        tema.boton(fila, "Buscar", buscar, ancho=130).pack(side="left", padx=10)
        tema.enfocar_luego(busqueda)

    def _form_cliente_nuevo(self) -> None:
        """Cliente nuevo: solo nombre, celular y su mascota. El registro se completa al atenderlo."""
        z = self.zona_cliente_nuevo
        for hijo in z.winfo_children():
            hijo.destroy()
        marco = ctk.CTkFrame(z, fg_color=tema.VERDE_SUAVE, corner_radius=12)
        marco.pack(fill="x", pady=(6, 0))
        cuerpo = ctk.CTkFrame(marco, fg_color="transparent")
        cuerpo.pack(fill="x", padx=16, pady=12)
        tema.etiqueta(cuerpo, "Cliente nuevo (sin registrar)", tema.TAM_SUBTITULO, negrita=True).pack(anchor="w")
        tema.etiqueta(cuerpo, "Solo se piden estos datos para agendar. La cédula, la dirección y los consentimientos "
                              "se registran cuando llegue al servicio.", color=tema.GRIS_TEXTO,
                      wraplength=760).pack(anchor="w", pady=(2, 0))
        campos = {}
        for clave, texto in (("nombre", "Nombre del cliente *"), ("celular", "Celular *"),
                             ("mascota", "Nombre de la mascota *")):
            tema.etiqueta(cuerpo, texto, negrita=True).pack(anchor="w", pady=(10, 4))
            campos[clave] = tema.entrada(cuerpo, ancho=420)
            campos[clave].pack(anchor="w")
        raza = SelectorRaza(cuerpo, self.ctx.conn)
        self.cliente_nuevo = {**campos, "raza": raza}

        def continuar():
            r = dialogos.ejecutar(self, propietarios.crear_provisional, self.ctx.conn, self.ctx.sesion,
                                  campos["nombre"].get(), campos["celular"].get(), campos["mascota"].get(),
                                  **raza.valores())
            if r is not dialogos.FALLO:
                self._elegir_dueno(r[0])

        botones = ctk.CTkFrame(cuerpo, fg_color="transparent")
        botones.pack(anchor="w", pady=(16, 0))
        tema.boton(botones, "Continuar con este cliente", continuar, ancho=320).pack(side="left")
        tema.boton(botones, "Cancelar", self._dibujar, estilo="secundario", ancho=160).pack(side="left", padx=12)
        tema.enfocar_luego(campos["nombre"])

    def _elegir_dueno(self, propietario_id: int) -> None:
        d = dialogos.ejecutar(self, propietarios.obtener, self.ctx.conn, self.ctx.sesion, propietario_id)
        if d is dialogos.FALLO:
            return
        self.dueno = d
        self.elegidas = {}
        self.usar_a_favor.set(0)
        self._reiniciar_plan()

    def _quitar_dueno(self) -> None:
        self.dueno = None
        self.elegidas = {}
        self._reiniciar_plan()

    def _paso_consentimientos(self) -> bool:
        if self.dueno["provisional"]:
            tema.insignia(self.cuerpo, "Cliente sin registrar: cuando llegue, registre su cédula, dirección y "
                                       "consentimientos antes de atender a la mascota.", tema.VERDE).pack(
                anchor="w", padx=20, pady=(8, 0))
            return True
        try:
            legal.verificar_para_turno(self.ctx.conn, self.dueno["id"])
        except ErrorClinican:
            estado = legal.estado(self.ctx.conn, self.dueno["id"])
            faltan = ", ".join(TIPOS_LEGALES[t].lower() for t, v in estado.items() if v is None)
            caja = ctk.CTkFrame(self.cuerpo, fg_color="transparent")
            caja.pack(fill="x", padx=20, pady=10)
            tema.insignia(caja, f"No se puede agendar: falta aceptar {faltan}.", tema.FUCSIA).pack(anchor="w")
            tema.boton(caja, "Registrar consentimientos", lambda: self.ctx.ventana.mostrar(
                "Propietarios", propietario_id=self.dueno["id"], pestana="Consentimientos"), ancho=320).pack(anchor="w", pady=8)
            return False
        if self.dueno["requiere_nuevo_abono"]:
            tema.insignia(self.cuerpo, "Este propietario no asistió sin avisar a tiempo: debe pagar un abono nuevo.",
                          tema.FUCSIA).pack(anchor="w", padx=20, pady=(8, 0))
        return True

    def _paso_mascotas(self) -> bool:
        caja = self._seccion(2, "Mascotas y tipo de servicio")
        lista = [m for m in propietarios.mascotas(self.ctx.conn, self.ctx.sesion, self.dueno["id"]) if m["activa"]]
        if not lista:
            tema.etiqueta(caja, "Este propietario no tiene mascotas activas. Agréguelas en Propietarios.",
                          color=tema.ROJO_ERROR).pack(anchor="w")
            tema.boton(caja, "Ir a sus mascotas", lambda: self.ctx.ventana.mostrar(
                "Propietarios", propietario_id=self.dueno["id"], pestana="Mascotas"), estilo="secundario",
                ancho=240).pack(anchor="w", pady=4)
            return False
        anteriores = self.elegidas
        self.elegidas = {}
        for m in lista:
            fila = ctk.CTkFrame(caja, fg_color="transparent")
            fila.pack(fill="x", pady=4)
            previo = anteriores.get(m["id"])
            var = ctk.IntVar(value=previo["var"].get() if previo else (1 if len(lista) == 1 else 0))
            tema.casilla(fila, f"{m['nombre']} ({m['raza_nombre']})", var, self._reiniciar_plan, width=300).pack(side="left")
            estado = {"var": var, "tipo": previo["tipo"] if previo else "MAQUINA", "nombre": m["nombre"]}

            def al_cambiar_tipo(estado=estado):
                estado["tipo"] = estado["widget"].codigo
                self._reiniciar_plan()

            estado["widget"] = tema.Opciones(fila, TIPOS_SERVICIO, al_cambiar_tipo, estado["tipo"])
            estado["widget"].pack(side="left", padx=10)
            self.elegidas[m["id"]] = estado
        if not self._seleccionadas():
            tema.etiqueta(caja, "Marque al menos una mascota.", color=tema.GRIS_TEXTO).pack(anchor="w", pady=4)
            return False
        return True

    def _paso_horario(self) -> None:
        caja = self._seccion(3, "Fecha y hora")
        seleccion = self._seleccionadas()
        fila = ctk.CTkFrame(caja, fg_color="transparent")
        fila.pack(fill="x")
        tema.etiqueta(fila, "Fecha (AAAA-MM-DD):", negrita=True).pack(side="left")
        tema.entrada(fila, ancho=170, textvariable=self.fecha).pack(side="left", padx=8)

        if self.plan and not self.faltan:
            nombres = {mid: d["nombre"] for mid, d in self.elegidas.items()}
            for mid, tipo, fecha, hora in self.plan:
                tema.etiqueta(caja, f"✔ {nombres[mid]}: {fecha} a las {hora} — {TIPOS_SERVICIO[tipo]}",
                              negrita=True).pack(anchor="w", pady=2)
            tema.boton(caja, "Elegir otra hora", self._reiniciar_plan, estilo="secundario", ancho=220).pack(anchor="w", pady=6)
            return

        if len(seleccion) == 1:
            tema.boton(fila, "Ver horas disponibles", self._horas_individual, ancho=260).pack(side="left", padx=8)
            self.zona_horas = ctk.CTkFrame(caja, fg_color="transparent")
            self.zona_horas.pack(fill="x", pady=6)
            return

        tema.etiqueta(caja, "Varias mascotas: llegan juntas y se atienden por separado, una por franja, "
                            "en franjas seguidas.", color=tema.GRIS_TEXTO, wraplength=800).pack(anchor="w", pady=(6, 2))
        fila2 = ctk.CTkFrame(caja, fg_color="transparent")
        fila2.pack(fill="x", pady=4)
        jornada = tema.Opciones(fila2, JORNADAS, inicial=self.jornada)
        jornada.pack(side="left")

        def proponer():
            self.jornada = jornada.codigo
            self._proponer(seleccion, self.fecha.get().strip(), jornada.codigo)

        tema.boton(fila2, "Proponer horario", proponer, ancho=240).pack(side="left", padx=10)
        if self.plan and self.faltan:
            nombres = {mid: d["nombre"] for mid, d in self.elegidas.items()}
            for mid, tipo, fecha, hora in self.plan:
                tema.etiqueta(caja, f"✔ {nombres[mid]}: {fecha} a las {hora}", negrita=True).pack(anchor="w")
            faltan = ", ".join(nombres[m] for m in self.faltan)
            tema.insignia(caja, f"No alcanzan las franjas para: {faltan}", tema.FUCSIA).pack(anchor="w", pady=6)
            otra = TARDE if self.jornada == MANANA else MANANA
            opciones = ctk.CTkFrame(caja, fg_color="transparent")
            opciones.pack(anchor="w")
            tema.boton(opciones, f"Continuar en la {JORNADAS[otra].lower()}",
                       lambda: self._continuar(self.plan[-1][2] if self.plan else self.fecha.get().strip(), otra),
                       ancho=300).pack(side="left")
            tema.etiqueta(opciones, "  u otro día: escriba la fecha arriba y", color=tema.GRIS_TEXTO).pack(side="left")
            tema.boton(opciones, "Continuar en esa fecha",
                       lambda: self._continuar(self.fecha.get().strip(), jornada.codigo), estilo="secundario",
                       ancho=260).pack(side="left", padx=6)

    def _horas_individual(self) -> None:
        for h in self.zona_horas.winfo_children():
            h.destroy()
        (mid, tipo), = self._seleccionadas()
        fecha = self.fecha.get().strip()
        lista = dialogos.ejecutar(self, turnos.franjas_para, self.ctx.conn, self.ctx.sesion, fecha, mid, tipo)
        if lista is dialogos.FALLO:
            return
        if not lista:
            tema.etiqueta(self.zona_horas, "No hay horas con cupo ese día para esta mascota. Pruebe otra fecha.",
                          color=tema.ROJO_ERROR).pack(anchor="w")
            return

        def elegir(hora):
            self.plan = [(mid, tipo, fecha, hora)]
            self.faltan = []
            self._dibujar()

        SelectorHoras(self.zona_horas, lista, elegir, columnas=6).pack(anchor="w")

    def _proponer(self, seleccion, fecha, jornada) -> None:
        r = dialogos.ejecutar(self, turnos.planificar_grupo, self.ctx.conn, self.ctx.sesion, seleccion, fecha, jornada)
        if r is dialogos.FALLO:
            return
        asignadas, faltan = r
        tipos = dict(seleccion)
        self.plan = [(m, tipos[m], fecha, h) for m, h in asignadas]
        self.faltan = faltan
        self._dibujar()

    def _continuar(self, fecha: str, jornada: str) -> None:
        """RN-09: si no alcanzan las franjas, continuar en la otra jornada u otro día."""
        tipos = dict(self._seleccionadas())
        resto = [(m, tipos[m]) for m in self.faltan]
        r = dialogos.ejecutar(self, turnos.planificar_grupo, self.ctx.conn, self.ctx.sesion, resto, fecha, jornada)
        if r is dialogos.FALLO:
            return
        asignadas, faltan = r
        if not asignadas:
            dialogos.aviso(self, "Sin franjas", f"No hay franjas con cupo el {fecha} en la {JORNADAS[jornada].lower()}. "
                                                "Pruebe otro día.")
            return
        self.plan += [(m, tipos[m], fecha, h) for m, h in asignadas]
        self.faltan = faltan
        self.jornada = jornada
        self._dibujar()

    def _paso_quien(self) -> None:
        caja = self._seccion(4, "¿Quién agenda?")
        selector = tema.selector(caja, list(self.activos), ancho=320, command=lambda v: setattr(self, "quien", v))
        selector.set(self.quien)
        selector.pack(anchor="w")

    def _paso_abono(self) -> None:
        config = self.ctx.config()
        minimo = int(config["abono_minimo"])
        cantidad = len(self.plan)
        caja = self._seccion(5, "Abono")
        tema.etiqueta(caja, f"Abono mínimo: {pesos(minimo)} por mascota ({pesos(minimo * cantidad)} en total). "
                            f"Sin abono, el turno queda pendiente {config['minutos_pendiente']} minutos.",
                      wraplength=800).pack(anchor="w")
        datos_pago(caja, config).pack(anchor="w", pady=8)
        a_favor = []
        if cantidad == 1:
            a_favor = turnos.abonos_a_favor(self.ctx.conn, self.ctx.sesion, self.dueno["id"])
        if a_favor:
            a = a_favor[0]
            tema.casilla(caja, f"Usar abono a favor de {pesos(a['monto'])} (turno de {a['mascota_nombre']} del "
                               f"{a['turno_fecha']})", self.usar_a_favor).pack(anchor="w", pady=4)
        medio = tema.Opciones(caja, {**MEDIOS, SIN_ABONO: "Todavía no paga"}, inicial=self.medio,
                              comando=lambda: setattr(self, "medio", medio.codigo))
        medio.pack(anchor="w", pady=6)
        self.montos_grupo = []
        if cantidad == 1:
            fila = ctk.CTkFrame(caja, fg_color="transparent")
            fila.pack(anchor="w")
            tema.etiqueta(fila, "Monto:", negrita=True).pack(side="left")
            if not self.monto.get():
                self.monto.set(pesos(minimo).replace("$", ""))
            tema.entrada(fila, ancho=180, textvariable=self.monto).pack(side="left", padx=8)
        else:
            nombres = {mid: d["nombre"] for mid, d in self.elegidas.items()}
            tema.etiqueta(caja, "Monto de cada mascota (puede cambiarlo):", negrita=True).pack(anchor="w", pady=(4, 2))
            for mid, _tipo, fecha, hora in self.plan:
                fila = ctk.CTkFrame(caja, fg_color="transparent")
                fila.pack(anchor="w", pady=2)
                tema.etiqueta(fila, f"{nombres[mid]} ({hora})", width=220).pack(side="left")
                e = tema.entrada(fila, ancho=160)
                e.insert(0, pesos(minimo).replace("$", ""))
                e.pack(side="left")
                self.montos_grupo.append(e)
        fila = ctk.CTkFrame(caja, fg_color="transparent")
        fila.pack(anchor="w", pady=(6, 0))
        tema.etiqueta(fila, "Nota del comprobante:", negrita=True).pack(side="left")
        tema.entrada(fila, ancho=320, textvariable=self.referencia).pack(side="left", padx=8)
        tema.casilla(caja, "Verifiqué el pago: confirmar aunque el abono sea menor al mínimo (incluso $0)",
                     self.verificado).pack(anchor="w", pady=(10, 0))
        self._a_favor = a_favor
        texto = "Agendar turno" if cantidad == 1 else f"Agendar {cantidad} turnos"
        tema.boton(self.cuerpo, texto, self._agendar, ancho=360).pack(anchor="w", padx=20, pady=(14, 24))

    # ---------------------------------------------------------------- agendar
    def _agendar(self) -> None:
        agendado_por = self.activos[self.quien]
        confirmar = bool(self.verificado.get())
        sin_abono = self.medio == SIN_ABONO
        if len(self.plan) == 1:
            mid, tipo, fecha, hora = self.plan[0]
            abono = None if sin_abono else Abono(self.monto.get(), self.medio, self.referencia.get())
            a_favor = self._a_favor[0]["id"] if self._a_favor and self.usar_a_favor.get() else None
            r = dialogos.ejecutar(self, turnos.crear_turno, self.ctx.conn, self.ctx.sesion, mid, tipo, fecha, hora,
                                  agendado_por, abono, a_favor, confirmar=confirmar and not sin_abono)
        else:
            pago = None if sin_abono else Abono(0, self.medio, self.referencia.get())
            montos = None if sin_abono else [e.get() for e in self.montos_grupo]
            r = dialogos.ejecutar(self, turnos.crear_grupo, self.ctx.conn, self.ctx.sesion, self.plan, agendado_por,
                                  pago, montos=montos, confirmar=confirmar and not sin_abono)
        if r is dialogos.FALLO:
            return
        estados = [turnos.turno(self.ctx.conn, self.ctx.sesion, t)["estado"] for t in r.turnos]
        confirmados = estados.count("CONFIRMADO")
        if confirmados == len(estados):
            msg = "Turno confirmado." if len(estados) == 1 else f"{len(estados)} turnos confirmados."
        else:
            msg = (f"Quedó pendiente de abono. Recuerde: el comprobante se envía al WhatsApp "
                   f"{self.ctx.config()['whatsapp_numero']} y el turno se libera si no se paga a tiempo.")
        dialogos.aviso(self, "Turno agendado", msg)
        avisar_liberados(self, r)
        self.ctx.ventana.mostrar("Agenda", fecha=self.plan[0][2], turno_id=r.turnos[0])
