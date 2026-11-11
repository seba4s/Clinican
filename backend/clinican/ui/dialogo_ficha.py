"""Ficha de servicio: se llena al marcar el turno como atendido y se puede corregir después."""

from __future__ import annotations

import customtkinter as ctk

from clinican.dominio.errores import DatoInvalido
from clinican.dominio.estados import EstadoTurno
from clinican.servicios import agenda, clientes, fichas, precios
from clinican.ui import formato as fmt
from clinican.ui import tema
from clinican.ui.componentes import Campo, Dialogo, Texto, etiqueta

SERVICIOS = ["Corte a máquina", "Corte a tijera", "Baño", "Uñas", "Limpieza de oídos", "Desenredado"]


class DialogoFicha(Dialogo):
    def __init__(self, padre, ctx, turno_id: int):
        self.ctx = ctx
        with ctx.con() as con:
            self.turno = agenda.obtener_turno(con, turno_id)
            self.ficha = fichas.ficha_de_turno(con, turno_id)
            mascota = clientes.obtener_mascota(con, self.turno.mascota_id)
            raza = clientes.obtener_raza(con, mascota.raza_id).nombre if mascota.raza_id else "sin raza"
            dueno = clientes.obtener_propietario(con, self.turno.propietario_id)
            self.precio_vigente = precios.precio_en_fecha(con, self.turno.categoria, fmt.local(self.turno.inicio).date())
            self.sesiones = fichas.sesiones_de_mascota(con, mascota.id)
        self.nueva = self.ficha is None
        super().__init__(padre, f"Ficha de servicio · {mascota.nombre}", ancho=740,
                         subtitulo=f"{raza}, {fmt.TAMANO[mascota.tamano]} · {dueno.nombre} · "
                                   f"{fmt.momento(self.turno.inicio, ctx.hoy())} · cupo {fmt.CATEGORIA[self.turno.categoria].upper()}")
        c = self.contenido

        etiqueta(c, "Servicios realizados", tema.ETIQUETA + 1, True).pack(anchor="w")
        fila = ctk.CTkFrame(c, fg_color="transparent")
        fila.pack(fill="x", pady=(4, 12))
        marcados = set(s.strip() for s in (self.ficha.servicios_realizados.split(",") if self.ficha else [fmt.SERVICIO[self.turno.servicio]]) if s.strip())
        extras = [s for s in marcados if s not in SERVICIOS]
        self.vars: dict[str, ctk.BooleanVar] = {}
        for s in SERVICIOS + extras:
            v = ctk.BooleanVar(value=s in marcados)
            self.vars[s] = v
            ctk.CTkCheckBox(fila, text=s, variable=v, font=tema.fuente(tema.CUERPO), text_color=tema.TINTA,
                            fg_color=tema.TINTA, hover_color=tema.TINTA_SUAVE).pack(side="left", padx=(0, 14))

        textos = ctk.CTkFrame(c, fg_color="transparent")
        textos.pack(fill="x")
        textos.grid_columnconfigure((0, 1), weight=1, uniform="t")
        self.corte = Texto(textos, "Detalles del corte", self.ficha.detalles_corte if self.ficha else "")
        self.corte.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.obs = Texto(textos, "Observaciones", self.ficha.observaciones if self.ficha else "")
        self.obs.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        caja = ctk.CTkFrame(c, fg_color=tema.SUPERFICIE_SUAVE, corner_radius=10)
        caja.pack(fill="x", pady=(14, 0))
        n = len(self.sesiones) + 1
        previa = self.sesiones[-1] if self.sesiones else None
        texto = f"Sesión de desenredado {n} (opcional)"
        if previa:
            texto += f". La anterior ({fmt.dia_corto(previa.fecha, ctx.hoy())}) llegó al {previa.porcentaje or 0} %."
        etiqueta(caja, texto, tema.ETIQUETA + 1, True).pack(anchor="w", padx=14, pady=(10, 4))
        des = ctk.CTkFrame(caja, fg_color="transparent")
        des.pack(fill="x", padx=14, pady=(0, 8))
        self.porcentaje = Campo(des, "Avance %", ancho=100)
        self.porcentaje.pack(side="left")
        self.avance = Campo(des, "Qué se avanzó", ancho=480)
        self.avance.pack(side="left", padx=(14, 0))

        cuenta = ctk.CTkFrame(c, fg_color="transparent")
        cuenta.pack(fill="x", pady=(14, 0))
        precio = self.ficha.precio_final if self.ficha else self.precio_vigente
        self.precio = Campo(cuenta, "Precio final", fmt.pesos(precio), ancho=180, validar=self._validar_precio)
        self.precio.pack(side="left")
        self.precio.entrada.bind("<KeyRelease>", lambda _e: (self.precio.revisar(), self._cuenta()), add="+")
        etiqueta(cuenta, f"Precio de {fmt.CATEGORIA[self.turno.categoria].upper()} vigente el día del turno: "
                         f"{fmt.pesos(self.precio_vigente)}.\nSi lo cambias, queda en el registro de cambios.",
                 tema.ETIQUETA + 1, suave=True).pack(side="left", padx=16)
        self.lbl_cobrar = etiqueta(cuenta, "", tema.SUBTITULO, True)
        self.lbl_cobrar.pack(side="right")
        self._cuenta()

        if self.nueva:
            self.boton_principal("Guardar ficha · listo para entregar", self._guardar)
            self.boton_cancelar("Seguir atendiendo")
        else:
            self.boton_principal("Guardar cambios", self._guardar)
            self.boton_cancelar()

    def _validar_precio(self, texto: str) -> str | None:
        try:
            fmt.leer_pesos(texto)
        except DatoInvalido as e:
            return str(e)
        return None

    def _cuenta(self) -> None:
        try:
            precio = fmt.leer_pesos(self.precio.valor())
        except DatoInvalido:
            return
        cobrar = max(0, precio - self.turno.abono_total)
        self.lbl_cobrar.configure(text=f"Abono {fmt.pesos(self.turno.abono_total)}  ·  Cobrar al entregar {fmt.pesos(cobrar)}")

    def _guardar(self) -> None:
        if not self.precio.revisar():
            return
        precio = fmt.leer_pesos(self.precio.valor())
        servicios = ", ".join(s for s, v in self.vars.items() if v.get())
        corte, obs = self.corte.valor(), self.obs.valor()
        avance = self.avance.valor()
        pct_texto = self.porcentaje.valor().replace("%", "").strip()
        porcentaje = None
        if pct_texto:
            if not pct_texto.isdigit() or int(pct_texto) > 100:
                self.porcentaje.error("De 0 a 100")
                return
            porcentaje = int(pct_texto)

        def guardar():
            ahora = self.ctx.ahora()
            with self.ctx.con() as con:
                if self.nueva:
                    if self.turno.estado is not EstadoTurno.EN_ATENCION:
                        agenda.iniciar_atencion(con, self.turno.id, ahora=ahora)
                    agenda.marcar_atendido(con, self.turno.id, ahora=ahora, servicios_realizados=servicios,
                                           detalles_corte=corte, observaciones=obs)
                    ficha = fichas.ficha_de_turno(con, self.turno.id)
                    if precio != ficha.precio_final:
                        ficha = fichas.editar_ficha(con, ficha.id, ahora=ahora, precio_final=precio)
                else:
                    cambios = {}
                    if servicios != self.ficha.servicios_realizados:
                        cambios["servicios_realizados"] = servicios
                    if corte != self.ficha.detalles_corte:
                        cambios["detalles_corte"] = corte
                    if obs != self.ficha.observaciones:
                        cambios["observaciones"] = obs
                    if precio != self.ficha.precio_final:
                        cambios["precio_final"] = precio
                    ficha = fichas.editar_ficha(con, self.ficha.id, ahora=ahora, **cambios) if cambios else self.ficha
                if avance or porcentaje is not None:
                    fichas.registrar_sesion_desenredado(con, ficha.id, ahora=ahora, avance=avance, porcentaje=porcentaje)
                return ficha

        if self.intentar(guardar):
            self.cerrar()
