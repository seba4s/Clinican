"""Ajustes: horario y bloqueos, cupos y abono, precios, razas, recordatorios, respaldos y registro."""

from __future__ import annotations

import json
from datetime import date, time, timedelta

import customtkinter as ctk

from clinican.dominio.agenda import HorarioSemanal, Jornada
from clinican.dominio.cupos import CategoriaCupo, CuposPorFranja, Tamano
from clinican.dominio.errores import DatoInvalido
from clinican.servicios import agenda, auditoria, clientes, configuracion, precios, respaldos
from clinican.ui import formato as fmt
from clinican.ui import tema
from clinican.ui.app import Pantalla
from clinican.ui.componentes import Campo, Dialogo, Lista, boton, confirmar, etiqueta, tarjeta

SECCIONES = ("Horario y bloqueos", "Cupos y abono", "Precios", "Razas", "Recordatorios y WhatsApp",
             "Respaldos", "Registro de cambios")
HORAS = [f"{h:02d}:{m:02d}" for h in range(6, 21) for m in (0, 30)]
CANALES = [("archivo", "Archivo de texto"), ("whatsapp", "WhatsApp"), ("consola", "Consola (pruebas)")]


def _entero(texto: str, nombre: str, minimo: int = 0) -> int:
    limpio = texto.replace(".", "").replace("$", "").strip()
    if not limpio.isdigit() or int(limpio) < minimo:
        raise DatoInvalido(f"{nombre}: escribe un número entero{' mayor que cero' if minimo else ''}.")
    return int(limpio)


class PantallaAjustes(Pantalla):
    def __init__(self, app):
        super().__init__(app)
        self.seccion = SECCIONES[0]
        menu = ctk.CTkFrame(self, fg_color="transparent", width=240)
        menu.pack(side="left", fill="y", padx=(16, 0), pady=20)
        menu.pack_propagate(False)
        etiqueta(menu, "Ajustes", tema.TITULO, True).pack(anchor="w", padx=12, pady=(0, 12))
        self._botones = {}
        for s in SECCIONES:
            b = ctk.CTkButton(menu, text=s, anchor="w", height=38, corner_radius=tema.RADIO, font=tema.fuente(tema.CUERPO),
                              fg_color="transparent", text_color=tema.TINTA, hover_color=tema.HOVER_NEUTRO,
                              border_color=tema.TINTA, command=lambda s=s: self.ir(s))
            b.pack(fill="x", pady=1)
            self._botones[s] = b
        self.cuerpo = Lista(self)
        self.cuerpo.pack(side="left", fill="both", expand=True, padx=24, pady=20)

    def ir(self, seccion: str) -> None:
        self.seccion = seccion
        self.refrescar()

    def refrescar_periodico(self) -> None:
        pass

    def refrescar(self) -> None:
        for s, b in self._botones.items():
            activo = s == self.seccion
            b.configure(fg_color=tema.SUPERFICIE if activo else "transparent", border_width=2 if activo else 0,
                        font=tema.fuente(tema.CUERPO, activo))
        self.cuerpo.vaciar()
        {
            "Horario y bloqueos": self._horario,
            "Cupos y abono": self._cupos,
            "Precios": self._precios,
            "Razas": self._razas,
            "Recordatorios y WhatsApp": self._recordatorios,
            "Respaldos": self._respaldos,
            "Registro de cambios": self._registro,
        }[self.seccion]()

    def _titulo(self, titulo: str, explicacion: str) -> None:
        etiqueta(self.cuerpo, titulo, 22, True).pack(anchor="w")
        etiqueta(self.cuerpo, explicacion, suave=True, wraplength=760).pack(anchor="w", pady=(2, 16))

    def _guardar_config(self, pares: list[tuple[str, object]], exito: str) -> None:
        def guardar(con):
            for nombre, valor in pares:
                configuracion.guardar(con, nombre, valor, ahora=self.ctx.ahora())
        self.ejecutar(guardar, exito)

    # ------------------------------------------------------------------ horario y bloqueos
    def _horario(self) -> None:
        self._titulo("Horario y bloqueos", "Horas en que se reciben perros. La última franja es la última hora a la que "
                                           "puede empezar un turno (cada franja dura 30 minutos).")
        with self.ctx.con() as con:
            cfg = configuracion.cargar(con)
            hoy = self.ctx.hoy()
            proximos = []
            for i in range(60):
                dia = hoy + timedelta(days=i)
                proximos += agenda.bloqueos_del_dia(con, dia)
        t = tarjeta(self.cuerpo)
        t.pack(fill="x")
        filas = {}
        for c, titulo in enumerate(("Día", "Abierto", "Primera franja", "Última franja")):
            etiqueta(t, titulo, tema.ETIQUETA, True, suave=True).grid(row=0, column=c, sticky="w", padx=16, pady=(12, 4))
        for d in range(7):
            jornada = cfg.horario.dias.get(d)
            abierto = ctk.BooleanVar(value=jornada is not None)
            desde = ctk.CTkOptionMenu(t, values=HORAS, width=100, font=tema.fuente(tema.CUERPO))
            hasta = ctk.CTkOptionMenu(t, values=HORAS, width=100, font=tema.fuente(tema.CUERPO))
            desde.set(jornada.apertura.strftime("%H:%M") if jornada else "09:00")
            hasta.set(jornada.ultima_franja.strftime("%H:%M") if jornada else "16:30")
            etiqueta(t, fmt.DIAS[d].capitalize()).grid(row=d + 1, column=0, sticky="w", padx=16, pady=4)
            ctk.CTkCheckBox(t, text="", variable=abierto, width=24, fg_color=tema.TINTA).grid(row=d + 1, column=1, padx=16)
            desde.grid(row=d + 1, column=2, sticky="w", padx=16)
            hasta.grid(row=d + 1, column=3, sticky="w", padx=16)
            filas[d] = (abierto, desde, hasta)
        ctk.CTkFrame(t, height=8, fg_color="transparent").grid(row=99, column=0)

        def guardar():
            try:
                dias = {d: (Jornada(time.fromisoformat(a.get()), time.fromisoformat(b.get())) if ab.get() else None)
                        for d, (ab, a, b) in filas.items()}
            except ValueError as e:
                self.avisar(f"Revisa el horario: {e}.", error=True)
                return
            self._guardar_config([("horario", HorarioSemanal(dias))], "Horario guardado.")

        boton(self.cuerpo, "Guardar horario", guardar, "principal").pack(anchor="w", pady=(12, 0))

        fila = ctk.CTkFrame(self.cuerpo, fg_color="transparent")
        fila.pack(fill="x", pady=(24, 6))
        etiqueta(fila, "Bloqueos de los próximos 60 días", tema.SUBTITULO, True).pack(side="left")
        boton(fila, "Bloquear horas…", self._nuevo_bloqueo).pack(side="right")
        if not proximos:
            etiqueta(self.cuerpo, "No hay bloqueos.", suave=True).pack(anchor="w")
        for b in proximos:
            caja = tarjeta(self.cuerpo)
            caja.pack(fill="x", pady=3)
            horas = "todo el día" if b.dia_completo else f"{b.desde.strftime('%H:%M')} a {b.hasta.strftime('%H:%M')}"
            etiqueta(caja, f"{fmt.dia_largo(b.fecha)} · {horas} · {b.motivo or 'sin motivo'}").pack(side="left", padx=16, pady=10)
            boton(caja, "Quitar", lambda b=b: self.ejecutar(lambda con: agenda.quitar_bloqueo(con, b.id, ahora=self.ctx.ahora()),
                                                             "Bloqueo quitado."), "peligro", ancho=90).pack(side="right", padx=8)

    def _nuevo_bloqueo(self) -> None:
        from clinican.ui.dialogos_turno import DialogoBloqueo

        if DialogoBloqueo(self, self.ctx, self.ctx.hoy()).mostrar():
            self.avisar("Horas bloqueadas.")
        self.refrescar()

    # ------------------------------------------------------------------ cupos y abono
    def _cupos(self) -> None:
        self._titulo("Cupos y abono", "Cuántos perros de cada categoría caben en una misma franja de 30 minutos, "
                                      "y cuánto se pide de abono para separar el turno.")
        with self.ctx.con() as con:
            cfg = configuracion.cargar(con)
        t = tarjeta(self.cuerpo)
        t.pack(fill="x")
        fila = ctk.CTkFrame(t, fg_color="transparent")
        fila.pack(fill="x", padx=16, pady=12)
        campos = {}
        for cat in CategoriaCupo:
            campos[cat] = Campo(fila, fmt.CATEGORIA[cat], str(cfg.cupos.capacidad(cat)), ancho=110)
            campos[cat].pack(side="left", padx=(0, 16))
        fila2 = ctk.CTkFrame(t, fg_color="transparent")
        fila2.pack(fill="x", padx=16, pady=(0, 12))
        abono = Campo(fila2, "Abono", fmt.pesos(cfg.abono), ancho=150)
        abono.pack(side="left", padx=(0, 16))
        minutos = Campo(fila2, "Minutos para pagarlo", str(cfg.minutos_expiracion), ancho=150)
        minutos.pack(side="left")

        def guardar():
            try:
                cupos = CuposPorFranja(**{c.value: _entero(campos[c].valor(), fmt.CATEGORIA[c]) for c in CategoriaCupo})
                valor_abono = fmt.leer_pesos(abono.valor())
                mins = _entero(minutos.valor(), "Minutos", 1)
            except (DatoInvalido, TypeError, ValueError) as e:
                self.avisar(str(e), error=True)
                return
            self._guardar_config([("cupos", cupos), ("abono", valor_abono), ("minutos_expiracion", mins)],
                                 "Cupos y abono guardados.")

        boton(self.cuerpo, "Guardar", guardar, "principal").pack(anchor="w", pady=(12, 0))

    # ------------------------------------------------------------------ precios
    def _precios(self) -> None:
        self._titulo("Precios", "Un precio nuevo rige desde la fecha que elijas; los turnos anteriores conservan el suyo. "
                                "«Corregir» cambia un valor ya registrado y queda en el registro de cambios.")
        hoy = self.ctx.hoy()
        with self.ctx.con() as con:
            vigentes = precios.precios_vigentes(con, hoy)
            historial = {c: precios.historial_precios(con, c) for c in CategoriaCupo}
        t = tarjeta(self.cuerpo)
        t.pack(fill="x")
        for c, titulo in enumerate(("Cupo", "Precio hoy", "Historial")):
            etiqueta(t, titulo, tema.ETIQUETA, True, suave=True).grid(row=0, column=c, sticky="w", padx=16, pady=(12, 4))
        t.grid_columnconfigure(2, weight=1)
        for r, cat in enumerate(CategoriaCupo, start=1):
            etiqueta(t, fmt.CATEGORIA[cat], negrita=True).grid(row=r, column=0, sticky="nw", padx=16, pady=8)
            etiqueta(t, fmt.pesos(vigentes[cat])).grid(row=r, column=1, sticky="nw", padx=16, pady=8)
            caja = ctk.CTkFrame(t, fg_color="transparent")
            caja.grid(row=r, column=2, sticky="ew", padx=16, pady=4)
            for p in sorted(historial[cat], key=lambda p: p.vigente_desde, reverse=True)[:4]:
                linea = ctk.CTkFrame(caja, fg_color="transparent")
                linea.pack(fill="x")
                futuro = p.vigente_desde > hoy
                etiqueta(linea, f"{fmt.pesos(p.valor)} desde {fmt.fecha_numerica(p.vigente_desde)}" + ("  (próximo)" if futuro else ""),
                         tema.ETIQUETA + 1, futuro, suave=not futuro).pack(side="left")
                boton(linea, "Corregir", lambda cat=cat, p=p: self._precio(cat, p), "enlace", ancho=80, alto=28).pack(side="left", padx=6)
            boton(t, "Cambiar…", lambda cat=cat: self._precio(cat), ancho=100).grid(row=r, column=3, sticky="ne", padx=16, pady=6)
        ctk.CTkFrame(t, height=8, fg_color="transparent").grid(row=99, column=0)

    def _precio(self, cat: CategoriaCupo, existente=None) -> None:
        corregir = existente is not None
        d = Dialogo(self, f"{'Corregir' if corregir else 'Cambiar'} precio de {fmt.CATEGORIA[cat]}", ancho=440,
                    subtitulo=(f"Vigente desde {fmt.fecha_numerica(existente.vigente_desde)}." if corregir else
                               "El precio nuevo rige desde la fecha que escribas."))
        valor = Campo(d.contenido, "Valor", fmt.pesos(existente.valor) if corregir else "", ancho=180)
        valor.pack(anchor="w")
        desde = Campo(d.contenido, "Desde (dd/mm/aaaa)", fmt.fecha_numerica(self.ctx.hoy() + timedelta(days=1)), ancho=180)
        if not corregir:
            desde.pack(anchor="w")

        def guardar():
            try:
                v = fmt.leer_pesos(valor.valor())
                fecha = existente.vigente_desde if corregir else fmt.leer_fecha(desde.valor())
            except DatoInvalido as e:
                d.error(str(e))
                return

            def accion():
                with self.ctx.con() as con:
                    if corregir:
                        return precios.editar_precio(con, cat, fecha, v, ahora=self.ctx.ahora())
                    return precios.cambiar_precio(con, cat, v, fecha, ahora=self.ctx.ahora())

            if d.intentar(accion):
                d.cerrar()

        d.boton_principal("Guardar", guardar)
        d.boton_cancelar()
        if d.mostrar():
            self.avisar("Precio guardado.")
        self.refrescar()

    # ------------------------------------------------------------------ razas
    def _razas(self) -> None:
        self._titulo("Razas", "El tamaño de la raza se propone al crear una mascota; siempre se puede cambiar en la mascota.")
        with self.ctx.con() as con:
            razas = clientes.buscar_razas(con)
        boton(self.cuerpo, "+ Raza nueva", lambda: self._raza()).pack(anchor="w", pady=(0, 10))
        t = tarjeta(self.cuerpo)
        t.pack(fill="x")
        t.grid_columnconfigure(2, weight=1)
        for c, titulo in enumerate(("Raza", "Tamaño", "Pelaje")):
            etiqueta(t, titulo, tema.ETIQUETA, True, suave=True).grid(row=0, column=c, sticky="w", padx=16, pady=(12, 4))
        if not razas:
            etiqueta(t, "Todavía no hay razas.", suave=True).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 12))
        for r, raza in enumerate(razas, start=1):
            etiqueta(t, raza.nombre).grid(row=r, column=0, sticky="w", padx=16, pady=2)
            etiqueta(t, fmt.TAMANO[raza.tamano] if raza.tamano else "—", suave=True).grid(row=r, column=1, sticky="w", padx=16)
            etiqueta(t, raza.pelaje or "—", suave=True).grid(row=r, column=2, sticky="w", padx=16)
            boton(t, "Editar", lambda raza=raza: self._raza(raza), "enlace", ancho=70, alto=28).grid(row=r, column=3, padx=8)
        ctk.CTkFrame(t, height=8, fg_color="transparent").grid(row=999, column=0)

    def _raza(self, raza=None) -> None:
        d = Dialogo(self, f"Editar {raza.nombre}" if raza else "Raza nueva", ancho=460)
        nombre = Campo(d.contenido, "Nombre", raza.nombre if raza else "", ancho=400)
        nombre.pack(anchor="w")
        etiqueta(d.contenido, "Tamaño", tema.ETIQUETA + 1, True).pack(anchor="w")
        opciones = ["Sin definir"] + [fmt.TAMANO[t].capitalize() for t in Tamano]
        tamano = ctk.CTkSegmentedButton(d.contenido, values=opciones, font=tema.fuente(tema.CUERPO), height=tema.ALTO_CONTROL,
                                        selected_color=tema.TINTA, selected_hover_color=tema.TINTA)
        tamano.set(fmt.TAMANO[raza.tamano].capitalize() if raza and raza.tamano else "Sin definir")
        tamano.pack(anchor="w", pady=(4, 10))
        pelaje = Campo(d.contenido, "Pelaje (opcional)", raza.pelaje if raza else "", ancho=400)
        pelaje.pack(anchor="w")

        def guardar():
            t = next((t for t in Tamano if fmt.TAMANO[t].capitalize() == tamano.get()), None)

            def accion():
                with self.ctx.con() as con:
                    if raza:
                        return clientes.editar_raza(con, raza.id, ahora=self.ctx.ahora(), nombre=nombre.valor(),
                                                    tamano=t, pelaje=pelaje.valor())
                    return clientes.crear_raza(con, nombre.valor(), t, pelaje.valor(), ahora=self.ctx.ahora())

            if d.intentar(accion):
                d.cerrar()

        d.boton_principal("Guardar", guardar)
        if raza:
            def baja():
                def accion():
                    with self.ctx.con() as con:
                        return clientes.desactivar_raza(con, raza.id, ahora=self.ctx.ahora())
                if d.intentar(accion):
                    d.cerrar()
            boton(d.botones, "Dar de baja", baja, "peligro").pack(side="left")
        d.boton_cancelar()
        if d.mostrar():
            self.avisar("Raza guardada.")
        self.refrescar()

    # ------------------------------------------------------------------ recordatorios
    def _recordatorios(self) -> None:
        self._titulo("Recordatorios y WhatsApp", "Por dónde salen los recordatorios y con cuánta anticipación. "
                                                 "El cambio de canal se aplica la próxima vez que abras Clinican.")
        with self.ctx.con() as con:
            cfg = configuracion.cargar(con)
        t = tarjeta(self.cuerpo)
        t.pack(fill="x")
        etiqueta(t, "Canal", tema.ETIQUETA + 1, True).pack(anchor="w", padx=16, pady=(12, 4))
        var = ctk.StringVar(value=cfg.canal_notificaciones)
        for valor, texto in CANALES:
            ctk.CTkRadioButton(t, text=texto, value=valor, variable=var, font=tema.fuente(tema.CUERPO),
                               text_color=tema.TINTA, fg_color=tema.TINTA).pack(anchor="w", padx=16, pady=3)
        etiqueta(t, "WhatsApp necesita el token y el número de WhatsApp Business configurados en Windows "
                    "(ver README). Sin ellos, cada envío falla y queda en Recordatorios › Fallidos.",
                 tema.ETIQUETA, suave=True, wraplength=700).pack(anchor="w", padx=16, pady=(4, 8))
        horas = Campo(t, "Horas antes del turno", str(cfg.horas_antes_recordatorio), ancho=120)
        horas.pack(anchor="w", padx=16, pady=(0, 12))

        def guardar():
            try:
                h = _entero(horas.valor(), "Horas antes")
            except DatoInvalido as e:
                horas.error(str(e))
                return
            self._guardar_config([("canal_notificaciones", var.get()), ("horas_antes_recordatorio", h)],
                                 "Guardado. El canal nuevo se usa desde el próximo inicio.")

        boton(self.cuerpo, "Guardar", guardar, "principal").pack(anchor="w", pady=(12, 0))

    # ------------------------------------------------------------------ respaldos
    def _respaldos(self) -> None:
        with self.ctx.con() as con:
            cfg = configuracion.cargar(con)
        carpeta = respaldos.carpeta_de(self.ctx.ruta_db, cfg.carpeta_respaldos)
        copias = list(reversed(respaldos.listar_respaldos(carpeta)))
        self._titulo("Respaldos", f"Se hace uno cada día y otro al cerrar Clinican, y se guardan los últimos "
                                  f"{cfg.respaldos_a_conservar}. Carpeta: {carpeta}")
        fila = ctk.CTkFrame(self.cuerpo, fg_color="transparent")
        fila.pack(fill="x", pady=(0, 10))
        if copias:
            etiqueta(fila, f"Último: {copias[0].name}", tema.CUERPO).pack(side="left")
        boton(fila, "Respaldar ahora", self._respaldar, "principal").pack(side="right")
        t = tarjeta(self.cuerpo)
        t.pack(fill="x")
        if not copias:
            etiqueta(t, "Todavía no hay respaldos.", suave=True).pack(anchor="w", padx=16, pady=12)
        for copia in copias:
            linea = ctk.CTkFrame(t, fg_color="transparent")
            linea.pack(fill="x", padx=16, pady=2)
            etiqueta(linea, copia.name).pack(side="left")
            etiqueta(linea, f"{copia.stat().st_size // 1024} KB", tema.ETIQUETA, suave=True).pack(side="left", padx=12)
            boton(linea, "Restaurar…", lambda c=copia: self._restaurar(c), "peligro", ancho=110, alto=32).pack(side="right")

    def _respaldar(self) -> None:
        try:
            copia = respaldos.crear_respaldo(self.ctx.ruta_db, ahora=self.ctx.ahora())
        except Exception as e:
            self.avisar(f"No se pudo respaldar: {e}", error=True)
            return
        self.avisar(f"Respaldo creado y verificado: {copia.name}")
        self.refrescar()

    def _restaurar(self, copia) -> None:
        if not confirmar(self, f"¿Restaurar {copia.name}?",
                         "Todo lo que se registró después de esa copia se reemplaza. Antes de restaurar se guarda "
                         "una copia de la base actual, por si necesitas volver.", "Restaurar", no="No restaurar"):
            return
        try:
            previa = respaldos.restaurar(self.ctx.ruta_db, copia, ahora=self.ctx.ahora())
        except Exception as e:
            self.avisar(f"No se pudo restaurar: {e}", error=True)
            return
        self.avisar(f"Base restaurada. La anterior quedó guardada como {previa.name}.")
        for nombre, pantalla in self.app.pantallas.items():
            if pantalla is not self:
                pantalla.refrescar()
        self.refrescar()

    # ------------------------------------------------------------------ registro
    def _registro(self) -> None:
        self._titulo("Registro de cambios", "Cada cambio queda anotado con su fecha. Se muestran los 200 más recientes.")
        with self.ctx.con() as con:
            registros = auditoria.historial(con)
        registros = sorted(registros, key=lambda r: r.cuando, reverse=True)[:200]
        hoy = self.ctx.hoy()
        t = tarjeta(self.cuerpo)
        t.pack(fill="x")
        t.grid_columnconfigure(2, weight=1)
        for c, titulo in enumerate(("Cuándo", "Qué", "Detalle")):
            etiqueta(t, titulo, tema.ETIQUETA, True, suave=True).grid(row=0, column=c, sticky="w", padx=16, pady=(12, 4))
        for r, reg in enumerate(registros, start=1):
            detalle = ", ".join(f"{k}: {v}" for k, v in reg.detalle.items() if v not in (None, ""))
            etiqueta(t, fmt.momento(reg.cuando, hoy), tema.ETIQUETA + 1).grid(row=r, column=0, sticky="nw", padx=16, pady=2)
            etiqueta(t, f"{reg.accion} {reg.entidad}" + (f" {reg.entidad_id}" if reg.entidad_id else ""),
                     tema.ETIQUETA + 1).grid(row=r, column=1, sticky="nw", padx=16, pady=2)
            etiqueta(t, detalle[:220], tema.ETIQUETA, suave=True, wraplength=560).grid(row=r, column=2, sticky="nw", padx=16, pady=2)
        ctk.CTkFrame(t, height=8, fg_color="transparent").grid(row=999, column=0)
