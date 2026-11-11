"""Agenda del día: tablero de cupos, pendientes de abono y panel del turno."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import customtkinter as ctk

from clinican.dominio.abonos import vence_en
from clinican.dominio.agenda import Bloqueo, generar_franjas
from clinican.dominio.cupos import CategoriaCupo
from clinican.dominio.estados import EstadoTurno, MotivoLiberacion, ocupa_cupo
from clinican.servicios import agenda, clientes, configuracion, consultas, fichas, precios
from clinican.servicios.consultas import TurnoEnAgenda
from clinican.ui import formato as fmt
from clinican.ui import tema
from clinican.ui.app import Pantalla
from clinican.ui.componentes import boton, chip_estado, confirmar, etiqueta, tarjeta

E = EstadoTurno
ORDEN_CATEGORIAS = (CategoriaCupo.MAQUINA, CategoriaCupo.GRANDE, CategoriaCupo.TIJERA, CategoriaCupo.COMPLICADO)


@dataclass
class FilaTablero:
    inicio: datetime
    pasada: bool
    bloqueo: str | None = None
    puestos: dict[CategoriaCupo, list[TurnoEnAgenda | None]] = field(default_factory=dict)


def capacidad(cupos, categoria: CategoriaCupo) -> int:
    return cupos.capacidad(categoria)


def armar_tablero(con, dia: date, ahora: datetime) -> tuple[list[FilaTablero], list[TurnoEnAgenda], int]:
    """Filas del día (también las bloqueadas), turnos fuera de agenda y cupos libres."""
    cfg = configuracion.cargar(con)
    bloqueos = agenda.bloqueos_del_dia(con, dia)
    reservables = {f.franja.inicio: f for f in consultas.agenda_del_dia(con, dia, ahora=ahora)}
    filas: list[FilaTablero] = []
    fuera: list[TurnoEnAgenda] = []
    libres = 0
    for franja in generar_franjas(dia, cfg.horario):
        fila = FilaTablero(franja.inicio, pasada=franja.fin <= ahora)
        datos = reservables.get(franja.inicio)
        if datos is None:
            motivo = next((b.motivo for b in bloqueos if b.cubre(franja)), "")
            fila.bloqueo = motivo or "sin motivo"
            filas.append(fila)
            continue
        for categoria in ORDEN_CATEGORIAS:
            fila.puestos[categoria] = []
        for t in datos.turnos:
            vencido = t.turno.estado is E.PENDIENTE_ABONO and vence_en(t.turno.creado_en, cfg.minutos_expiracion) <= ahora
            if ocupa_cupo(t.turno.estado) and not vencido:
                fila.puestos[t.turno.categoria].append(t)
            else:
                fuera.append(t)
        for categoria in ORDEN_CATEGORIAS:
            cap = capacidad(cfg.cupos, categoria)
            ocupados = fila.puestos[categoria]
            vacios = max(0, cap - len(ocupados))
            if not fila.pasada:
                libres += vacios
            fila.puestos[categoria] = ocupados + [None] * vacios
        filas.append(fila)
    return filas, fuera, libres


class PantallaAgenda(Pantalla):
    def __init__(self, app):
        super().__init__(app)
        self.dia = self.ctx.hoy()
        self.seleccion: int | None = None
        self._turnos: dict[int, TurnoEnAgenda] = {}

        cab = ctk.CTkFrame(self, fg_color="transparent", width=0, height=0)
        cab.pack(fill="x", padx=24, pady=(20, 0))
        boton(cab, "‹", self.dia_anterior, ancho=40).pack(side="left")
        boton(cab, "Hoy", self.ir_hoy, ancho=64).pack(side="left", padx=4)
        boton(cab, "›", self.dia_siguiente, ancho=40).pack(side="left")
        self.lbl_dia = etiqueta(cab, "", tema.TITULO, True)
        self.lbl_dia.pack(side="left", padx=16)
        boton(cab, "+ Nuevo turno  (Ctrl+N)", lambda: self.nuevo_turno(), "principal").pack(side="right")
        boton(cab, "Bloquear horas", self.bloquear).pack(side="right", padx=tema.SEP)
        self.lbl_resumen = etiqueta(cab, "", tema.ETIQUETA + 1, suave=True)
        self.lbl_resumen.pack(side="right", padx=tema.SEP)

        self.pendientes = ctk.CTkFrame(self, fg_color="transparent", width=0, height=0)
        self.pendientes.pack(fill="x", padx=24, pady=(12, 0))

        cuerpo = ctk.CTkFrame(self, fg_color="transparent", width=0, height=0)
        cuerpo.pack(fill="both", expand=True, padx=24, pady=(12, 20))
        self.panel = tarjeta(cuerpo, width=340)
        self.panel.pack(side="right", fill="y", padx=(16, 0))
        self.panel.pack_propagate(False)
        marco = tarjeta(cuerpo)
        marco.pack(side="left", fill="both", expand=True)
        self.tablero = ctk.CTkScrollableFrame(marco, fg_color="transparent")
        self.tablero.pack(fill="both", expand=True, padx=8, pady=8)
        self.lbl_fuera = etiqueta(marco, "", tema.ETIQUETA, suave=True, wraplength=760)
        self.lbl_fuera.pack(fill="x", padx=16, pady=(0, 10))

        for tecla, accion in (("<Left>", self.dia_anterior), ("<Right>", self.dia_siguiente), ("<Home>", self.ir_hoy)):
            self.app.bind_all(tecla, lambda e, a=accion: self._tecla(e, a), add="+")

    # ------------------------------------------------------------------ navegación por días
    def _tecla(self, evento, accion) -> None:
        if self.app.actual != "Agenda" or self.app._hay_dialogo():
            return
        if evento.widget.winfo_class() in ("Entry", "Text", "TEntry"):
            return
        accion()

    def dia_anterior(self) -> None:
        self.dia -= timedelta(days=1)
        self.seleccion = None
        self.refrescar()

    def dia_siguiente(self) -> None:
        self.dia += timedelta(days=1)
        self.seleccion = None
        self.refrescar()

    def ir_hoy(self) -> None:
        self.dia = self.ctx.hoy()
        self.seleccion = None
        self.refrescar()

    # ------------------------------------------------------------------ dibujo
    def refrescar(self) -> None:
        ahora = self.ctx.ahora()
        hoy = self.ctx.hoy()
        with self.ctx.con() as con:
            filas, fuera, libres = armar_tablero(con, self.dia, ahora)
            pendientes = [p for p in consultas.pendientes_de_abono(con, ahora=ahora) if not p.vencido]
            cfg = configuracion.cargar(con)
        titulo = fmt.dia_largo(self.dia)
        if self.dia == hoy:
            titulo = "Hoy, " + titulo[0].lower() + titulo[1:]
        self.lbl_dia.configure(text=titulo)
        turnos = [t for f in filas for lista in f.puestos.values() for t in lista if t]
        self._turnos = {t.turno.id: t for t in turnos + fuera}
        if not filas:
            self.lbl_resumen.configure(text="Cerrado")
        else:
            self.lbl_resumen.configure(text=f"{len(turnos)} turno{'s' if len(turnos) != 1 else ''} · {libres} cupos libres")
        self._dibujar_pendientes(pendientes, ahora)
        self._dibujar_tablero(filas, cfg)
        if fuera:
            partes = [f"{t.mascota} ({tema.estilo_estado(t.turno.estado)[3].lower()}, {fmt.hora(t.turno.inicio)})" for t in fuera]
            self.lbl_fuera.configure(text="Fuera de agenda: " + " · ".join(partes))
        else:
            self.lbl_fuera.configure(text="")
        if self.seleccion not in self._turnos:
            self.seleccion = None
        self._dibujar_panel()

    def refrescar_periodico(self) -> None:
        self.refrescar()

    def _dibujar_pendientes(self, pendientes, ahora) -> None:
        for w in self.pendientes.winfo_children():
            w.destroy()
        if not pendientes:
            self.pendientes.pack_forget()
            return
        if not self.pendientes.winfo_manager():
            self.pendientes.pack(fill="x", padx=24, pady=(12, 0), before=self.pendientes.master.winfo_children()[-1])
        fondo, letra, borde, _n, _i = tema.estilo_estado(E.PENDIENTE_ABONO)
        n = len(pendientes)
        etiqueta(self.pendientes, f"◷  Falta{'n' if n != 1 else ''} {n} abono{'s' if n != 1 else ''}",
                 tema.ETIQUETA + 1, True, color=letra).pack(side="left", padx=(0, 12))
        for p in pendientes[:4]:
            texto = (f"{fmt.dia_corto(fmt.local(p.turno.inicio).date(), self.ctx.hoy())} {fmt.hora(p.turno.inicio)} · "
                     f"{p.mascota} · {p.propietario}   {fmt.minutos_restantes(p.vence_en, ahora)}   "
                     f"{fmt.pesos(p.turno.abono_total)} de {fmt.pesos(p.turno.abono_requerido)}")
            ctk.CTkButton(self.pendientes, text=texto, height=36, corner_radius=10, fg_color=fondo, text_color=tema.TINTA,
                          hover_color=borde, border_width=1, border_color=borde, font=tema.fuente(tema.ETIQUETA + 1),
                          command=lambda p=p: self._ir_a_turno(p.turno)).pack(side="left", padx=(0, 8))
        if n > 4:
            etiqueta(self.pendientes, f"y {n - 4} más", tema.ETIQUETA, suave=True).pack(side="left")

    def _ir_a_turno(self, turno) -> None:
        self.dia = fmt.local(turno.inicio).date()
        self.seleccion = turno.id
        self.refrescar()

    def _dibujar_tablero(self, filas: list[FilaTablero], cfg) -> None:
        for w in self.tablero.winfo_children():
            w.destroy()
        if not filas:
            etiqueta(self.tablero, "Este día la peluquería está cerrada.", tema.SUBTITULO, suave=True).pack(pady=40)
            return
        t = self.tablero
        t.grid_columnconfigure(0, minsize=64)
        for i, cat in enumerate(ORDEN_CATEGORIAS, start=1):
            t.grid_columnconfigure(i, weight=capacidad(cfg.cupos, cat))
        etiqueta(t, "Hora", tema.ETIQUETA, True, suave=True).grid(row=0, column=0, sticky="w", padx=4, pady=(0, 6))
        for i, cat in enumerate(ORDEN_CATEGORIAS, start=1):
            etiqueta(t, f"{fmt.CATEGORIA[cat].upper()} · {capacidad(cfg.cupos, cat)}", tema.ETIQUETA, True,
                     suave=True).grid(row=0, column=i, sticky="w", padx=4, pady=(0, 6))
        ahora = self.ctx.ahora()
        for r, fila in enumerate(filas, start=1):
            actual = fila.inicio <= ahora < fila.inicio + timedelta(minutes=30)
            hora = fmt.hora(fila.inicio)
            etiqueta(t, hora, tema.CUERPO, not fila.pasada, suave=fila.pasada,
                     color=tema.ACCION if actual else None).grid(row=r, column=0, sticky="w", padx=4, pady=3)
            if fila.bloqueo:
                ctk.CTkLabel(t, text=f"Bloqueado · {fila.bloqueo}", height=32, corner_radius=6, anchor="w",
                             fg_color=("#EFEFEC", "#2E2C36"), text_color=tema.TINTA_SUAVE,
                             font=tema.fuente(tema.ETIQUETA)).grid(row=r, column=1, columnspan=4, sticky="ew", padx=4, pady=3)
                continue
            for c, cat in enumerate(ORDEN_CATEGORIAS, start=1):
                celda = ctk.CTkFrame(t, fg_color="transparent", width=0, height=0)
                celda.grid(row=r, column=c, sticky="ew", padx=4, pady=3)
                for turno in fila.puestos[cat]:
                    self._puesto(celda, turno, fila, cat).pack(side="left", fill="x", expand=True, padx=(0, 4))

    def _puesto(self, padre, item: TurnoEnAgenda | None, fila: FilaTablero, cat: CategoriaCupo):
        if item is None:
            if fila.pasada:
                return ctk.CTkFrame(padre, width=60, height=32, fg_color="transparent")
            return ctk.CTkButton(padre, text="Libre", height=32, width=60, corner_radius=6, fg_color="transparent",
                                 hover_color=tema.HOVER_NEUTRO, text_color=tema.TINTA_SUAVE, border_width=1,
                                 border_color=tema.BORDE_CAMPO, font=tema.fuente(tema.ETIQUETA),
                                 command=lambda: self.nuevo_turno(inicio=fila.inicio, categoria=cat))
        turno = item.turno
        fondo, letra, borde, _n, icono = tema.estilo_estado(turno.estado)
        seleccionado = turno.id == self.seleccion
        return ctk.CTkButton(padre, text=f"{icono} {item.mascota}", height=32, width=60, corner_radius=6, anchor="w",
                             fg_color=fondo, hover_color=borde, text_color=letra,
                             border_width=2 if seleccionado else 1,
                             border_color=tema.TINTA if seleccionado else borde,
                             font=tema.fuente(tema.ETIQUETA, True),
                             command=lambda: self.seleccionar(turno.id))

    def seleccionar(self, turno_id: int) -> None:
        self.seleccion = turno_id
        self.refrescar()

    # ------------------------------------------------------------------ panel del turno
    def _dibujar_panel(self) -> None:
        for w in self.panel.winfo_children():
            w.destroy()
        p = ctk.CTkFrame(self.panel, fg_color="transparent", width=0, height=0)
        p.pack(fill="both", expand=True, padx=20, pady=20)
        if self.seleccion is None:
            etiqueta(p, "Elige un turno del tablero para ver sus datos y lo que puedes hacer con él.",
                     suave=True, wraplength=290).pack(anchor="w")
            etiqueta(p, "Un puesto «Libre» agenda directamente en esa hora y cupo.", suave=True,
                     wraplength=290).pack(anchor="w", pady=(12, 0))
            return
        item = self._turnos[self.seleccion]
        turno = item.turno
        ahora = self.ctx.ahora()
        with self.ctx.con() as con:
            mascota = clientes.obtener_mascota(con, turno.mascota_id)
            raza = clientes.obtener_raza(con, mascota.raza_id).nombre if mascota.raza_id else "Sin raza"
            dueno = clientes.obtener_propietario(con, turno.propietario_id)
            precio = precios.precio_en_fecha(con, turno.categoria, fmt.local(turno.inicio).date())
            ficha = fichas.ficha_de_turno(con, turno.id)
            minutos = configuracion.cargar(con).minutos_expiracion

        etiqueta(p, f"{fmt.dia_corto(fmt.local(turno.inicio).date(), self.ctx.hoy())} {fmt.hora(turno.inicio)} · "
                    f"cupo {fmt.CATEGORIA[turno.categoria]}", tema.ETIQUETA, suave=True).pack(anchor="w")
        etiqueta(p, f"{item.mascota} · {raza}", 22, True, wraplength=290).pack(anchor="w")
        etiqueta(p, f"{dueno.nombre} · {fmt.celular(dueno.telefono)}", wraplength=290).pack(anchor="w")
        chip_estado(p, turno.estado).pack(anchor="w", pady=(10, 10))

        datos = ctk.CTkFrame(p, fg_color="transparent", width=0, height=0)
        datos.pack(fill="x")
        precio_final = ficha.precio_final if ficha else precio
        filas = [
            ("Servicio", fmt.SERVICIO[turno.servicio]),
            ("Precio", fmt.pesos(precio_final) + ("" if ficha else " (vigente)")),
            ("Abono", f"{fmt.pesos(turno.abono_total)} de {fmt.pesos(turno.abono_requerido)}"
                      + (f" (saldo {fmt.pesos(turno.saldo_aplicado)})" if turno.saldo_aplicado else "")),
            ("Saldo a favor", fmt.pesos(dueno.saldo_a_favor)),
        ]
        for i, (k, v) in enumerate(filas):
            etiqueta(datos, k, suave=True).grid(row=i, column=0, sticky="w", pady=2)
            etiqueta(datos, v, wraplength=190).grid(row=i, column=1, sticky="w", padx=(16, 0), pady=2)

        nota = None
        if turno.estado is E.PENDIENTE_ABONO:
            limite = vence_en(turno.creado_en, minutos)
            nota = (f"Vence a las {fmt.hora(limite)} ({fmt.minutos_restantes(limite, ahora)}). "
                    "Si vence, el cupo se libera solo.")
        elif turno.estado is E.ATENDIDO and ficha:
            nota = f"Cobrar al entregar: {fmt.pesos(max(0, ficha.precio_final - turno.abono_total))}"
        elif turno.estado is E.INASISTENCIA:
            nota = f"Saldo a favor generado: {fmt.pesos(turno.saldo_generado)}"
        elif turno.estado in (E.CANCELADO, E.LIBERADO) and turno.saldo_generado:
            nota = f"Pasó al saldo a favor: {fmt.pesos(turno.saldo_generado)}"
        if nota:
            ctk.CTkLabel(p, text=nota, fg_color=tema.SUPERFICIE_SUAVE, corner_radius=8, anchor="w", justify="left",
                         wraplength=280, text_color=tema.TINTA, font=tema.fuente(tema.ETIQUETA + 1)).pack(fill="x", pady=(12, 0), ipady=6, ipadx=8)

        acciones = ctk.CTkFrame(p, fg_color="transparent", width=0, height=0)
        acciones.pack(fill="x", pady=(16, 0))
        for texto, comando, tipo in self._acciones(turno, ficha):
            boton(acciones, texto, comando, tipo).pack(fill="x", pady=(0, 8))

    def _acciones(self, turno, ficha):
        t = turno.id
        if turno.estado is E.PENDIENTE_ABONO:
            return [("Registrar abono", lambda: self.registrar_abono(turno), "principal"),
                    ("Mover turno", lambda: self.mover(turno), "secundario"),
                    ("Liberar cupo…", lambda: self.liberar(turno), "peligro"),
                    ("Cancelar turno…", lambda: self.cancelar(turno), "peligro")]
        if turno.estado is E.CONFIRMADO:
            return [("Iniciar atención", lambda: self.ejecutar(lambda con: agenda.iniciar_atencion(con, t, ahora=self.ctx.ahora())), "principal"),
                    ("Mover turno", lambda: self.mover(turno), "secundario"),
                    ("Marcar inasistencia…", lambda: self.inasistencia(turno), "peligro"),
                    ("Cancelar turno…", lambda: self.cancelar(turno), "peligro")]
        if turno.estado is E.EN_ATENCION:
            return [("Marcar atendido y llenar ficha", lambda: self.ficha(turno), "principal")]
        if turno.estado is E.ATENDIDO:
            return [("Entregar", lambda: self.ejecutar(lambda con: agenda.marcar_entregado(con, t, ahora=self.ctx.ahora()),
                                                       "Entregado."), "principal"),
                    ("Ver ficha", lambda: self.ficha(turno), "secundario")]
        if turno.estado is E.ENTREGADO and ficha:
            return [("Ver ficha", lambda: self.ficha(turno), "secundario")]
        return []

    # ------------------------------------------------------------------ acciones
    def nuevo_turno(self, inicio: datetime | None = None, categoria: CategoriaCupo | None = None,
                    mascota_id: int | None = None) -> None:
        from clinican.ui.dialogos_turno import DialogoNuevoTurno

        turno = DialogoNuevoTurno(self, self.ctx, dia=fmt.local(inicio).date() if inicio else self.dia,
                                  inicio=inicio, categoria=categoria, mascota_id=mascota_id).mostrar()
        if turno:
            self._ir_a_turno(turno)
            estado = "confirmado" if turno.estado is E.CONFIRMADO else f"falta el abono ({fmt.pesos(turno.faltante)})"
            self.avisar(f"Turno agendado a las {fmt.hora(turno.inicio)}: {estado}.")
            self.app.actualizar_insignias()

    def registrar_abono(self, turno) -> None:
        from clinican.ui.dialogos_turno import DialogoAbono

        nuevo = DialogoAbono(self, self.ctx, turno).mostrar()
        if nuevo:
            self.avisar("Abono completo: turno confirmado." if nuevo.estado is E.CONFIRMADO
                        else f"Abono registrado. Falta {fmt.pesos(nuevo.faltante)}.")
        self.refrescar()

    def mover(self, turno) -> None:
        from clinican.ui.dialogos_turno import DialogoMover

        nuevo = DialogoMover(self, self.ctx, turno).mostrar()
        if nuevo:
            self._ir_a_turno(nuevo)
            self.avisar(f"Turno movido a {fmt.momento(nuevo.inicio, self.ctx.hoy())}.")

    def liberar(self, turno) -> None:
        if confirmar(self, "¿Liberar el cupo?", "El turno sale de la agenda y lo que el cliente ya había "
                     "pagado queda como saldo a favor.", "Liberar cupo"):
            self.ejecutar(lambda con: agenda.liberar_turno(con, turno.id, MotivoLiberacion.OTRO, ahora=self.ctx.ahora()),
                          "Cupo liberado.")

    def cancelar(self, turno) -> None:
        pagado = turno.abono_total
        texto = "El turno sale de la agenda."
        if pagado:
            texto += f" Lo pagado ({fmt.pesos(pagado)}) queda como saldo a favor del cliente."
        if confirmar(self, "¿Cancelar el turno?", texto, "Cancelar turno"):
            self.ejecutar(lambda con: agenda.cancelar_turno(con, turno.id, ahora=self.ctx.ahora()), "Turno cancelado.")

    def inasistencia(self, turno) -> None:
        from clinican.ui.dialogos_turno import DialogoInasistencia

        if DialogoInasistencia(self, self.ctx, turno).mostrar():
            self.avisar("Inasistencia registrada.")
        self.refrescar()

    def ficha(self, turno) -> None:
        from clinican.ui.dialogo_ficha import DialogoFicha

        if DialogoFicha(self, self.ctx, turno.id).mostrar():
            self.avisar("Ficha guardada. El turno está listo para entregar."
                        if turno.estado is E.EN_ATENCION else "Ficha actualizada.")
        self.refrescar()

    def bloquear(self) -> None:
        from clinican.ui.dialogos_turno import DialogoBloqueo

        if DialogoBloqueo(self, self.ctx, self.dia).mostrar():
            self.avisar("Horas bloqueadas.")
        self.refrescar()
