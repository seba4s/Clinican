"""Administración de horarios (pantalla 8).

- Todos: agregar o quitar franjas sueltas (horas extra) de una fecha.
- Solo la administradora: bloquear días, rangos y franjas; editar la plantilla semanal.
"""

from __future__ import annotations

from datetime import date, timedelta

import customtkinter as ctk

from clinican.dominio import turnos as rt
from clinican.dominio.errores import ErrorClinican
from clinican.dominio.franjas import JORNADAS
from clinican.dominio.permisos import Accion
from clinican.dominio.propietarios import formato_celular
from clinican.servicios import horarios
from clinican.ui import dialogos, tema
from clinican.ui.pantalla_agenda import fecha_larga

DIAS_CORTOS = {1: "Lun", 2: "Mar", 3: "Mié", 4: "Jue", 5: "Vie", 6: "Sáb"}


class PantallaHorarios(ctk.CTkFrame):
    def __init__(self, padre, ctx):
        super().__init__(padre, fg_color="transparent")
        self.ctx = ctx
        self.fecha = date.today()
        self.admin = ctx.sesion.puede(Accion.BLOQUEAR_DIAS)

        tema.titulo(self, "Horarios").pack(anchor="w", pady=(0, 10))
        if self.admin:
            self.pestanas = ctk.CTkTabview(
                self, fg_color=tema.BLANCO, border_width=1, border_color=tema.BORDE, corner_radius=14,
                segmented_button_fg_color=tema.GRIS_BOTON, segmented_button_selected_color=tema.VERDE,
                segmented_button_selected_hover_color=tema.VERDE_HOVER, segmented_button_unselected_color=tema.GRIS_BOTON,
                segmented_button_unselected_hover_color=tema.GRIS_BOTON_HOVER, text_color=tema.NEGRO,
            )
            self.pestanas._segmented_button.configure(font=tema.fuente(tema.TAM_NORMAL, True), height=44)
            self.pestanas.pack(fill="both", expand=True)
            for n in ("Franjas de una fecha", "Bloqueos", "Plantilla semanal"):
                self.pestanas.add(n)
            self.zona_fecha = ctk.CTkScrollableFrame(self.pestanas.tab("Franjas de una fecha"), fg_color=tema.BLANCO)
            self.zona_fecha.pack(fill="both", expand=True)
            self.zona_bloqueos = ctk.CTkScrollableFrame(self.pestanas.tab("Bloqueos"), fg_color=tema.BLANCO)
            self.zona_bloqueos.pack(fill="both", expand=True)
            self.zona_plantilla = ctk.CTkScrollableFrame(self.pestanas.tab("Plantilla semanal"), fg_color=tema.BLANCO)
            self.zona_plantilla.pack(fill="both", expand=True)
            self._bloqueos()
            self._plantilla()
        else:
            self.zona_fecha = ctk.CTkScrollableFrame(self, fg_color=tema.BLANCO, corner_radius=14, border_width=1,
                                                     border_color=tema.BORDE)
            self.zona_fecha.pack(fill="both", expand=True)
        self._franjas_fecha()

    # ================================================== franjas de una fecha
    def _franjas_fecha(self) -> None:
        z = self.zona_fecha
        for h in z.winfo_children():
            h.destroy()
        nav = ctk.CTkFrame(z, fg_color="transparent")
        nav.pack(fill="x", padx=12, pady=(10, 6))
        tema.boton(nav, "◀", lambda: self._mover_fecha(-1), estilo="secundario", ancho=56).pack(side="left")
        tema.boton(nav, "▶", lambda: self._mover_fecha(1), estilo="secundario", ancho=56).pack(side="left", padx=6)
        tema.subtitulo(nav, fecha_larga(self.fecha).capitalize()).pack(side="left", padx=10)
        ir = tema.entrada(nav, ancho=150, placeholder_text="AAAA-MM-DD")
        ir.pack(side="right")

        def ir_a(_e=None):
            try:
                self.fecha = date.fromisoformat(ir.get().strip())
            except ValueError:
                dialogos.error(self, "Escriba la fecha como AAAA-MM-DD.")
                return
            self._franjas_fecha()

        ir.bind("<Return>", ir_a)
        fecha = self.fecha.isoformat()
        bloqueo = horarios.bloqueo_del_dia(self.ctx.conn, fecha)
        if bloqueo:
            tema.insignia(z, f"Día bloqueado: {bloqueo['motivo'] or 'sin motivo'}", tema.FUCSIA).pack(anchor="w", padx=12, pady=4)
        lista = horarios.franjas(self.ctx.conn, fecha)
        extras = {a["hora"] for a in horarios.ajustes(self.ctx.conn, fecha) if a["accion"] == "AGREGAR"}
        if not lista:
            tema.etiqueta(z, "No hay franjas este día.", color=tema.GRIS_TEXTO).pack(anchor="w", padx=12, pady=6)
        for f in lista:
            fila = ctk.CTkFrame(z, fg_color=tema.FONDO, corner_radius=10)
            fila.pack(fill="x", padx=12, pady=3)
            activos = len(horarios.turnos_activos(self.ctx.conn, fecha, f.hora))
            texto = f"{f.hora}   {JORNADAS[f.jornada]}   ·   {'Hora extra' if f.hora in extras else 'Plantilla'}"
            texto += f"   ·   {activos} turno(s) activo(s)" if activos else ""
            tema.etiqueta(fila, texto, negrita=True).pack(side="left", padx=12, pady=8)
            if f.hora in extras:
                tema.boton(fila, "Quitar hora extra", lambda h=f.hora: self._quitar_extra(h), estilo="secundario",
                           ancho=200).pack(side="right", padx=6, pady=4)
            elif self.admin:
                tema.boton(fila, "Bloquear franja", lambda h=f.hora: self._bloquear_franja(h), estilo="secundario",
                           ancho=200).pack(side="right", padx=6, pady=4)

        agregar = ctk.CTkFrame(z, fg_color=tema.VERDE_SUAVE, corner_radius=10)
        agregar.pack(fill="x", padx=12, pady=(12, 6))
        tema.etiqueta(agregar, "Agregar una hora extra libre este día (HH:MM):", negrita=True).pack(side="left", padx=12, pady=10)
        hora = tema.entrada(agregar, ancho=110)
        hora.pack(side="left")

        def agregar_hora():
            if dialogos.ejecutar(self, horarios.agregar_franja_suelta, self.ctx.conn, self.ctx.sesion, fecha,
                                 hora.get()) is not dialogos.FALLO:
                self._franjas_fecha()

        tema.boton(agregar, "Agregar", agregar_hora, ancho=140).pack(side="left", padx=10)

        if self.admin and not bloqueo:
            motivo = ctk.StringVar()
            fila = ctk.CTkFrame(z, fg_color="transparent")
            fila.pack(fill="x", padx=12, pady=(12, 16))
            tema.etiqueta(fila, "Motivo:", negrita=True).pack(side="left")
            tema.entrada(fila, ancho=300, textvariable=motivo).pack(side="left", padx=8)
            tema.boton(fila, "Bloquear este día completo", lambda: self._bloquear_dias(fecha, fecha, motivo.get()),
                       estilo="peligro", ancho=320).pack(side="left", padx=8)

    def _mover_fecha(self, dias: int) -> None:
        self.fecha += timedelta(days=dias)
        self._franjas_fecha()

    def _quitar_extra(self, hora: str) -> None:
        if dialogos.ejecutar(self, horarios.quitar_franja_suelta, self.ctx.conn, self.ctx.sesion,
                             self.fecha.isoformat(), hora) is not dialogos.FALLO:
            self._franjas_fecha()

    def _bloquear_franja(self, hora: str) -> None:
        if not dialogos.confirmar(self, "Bloquear franja", f"¿Bloquear la franja de las {hora} del {self.fecha.isoformat()}?",
                                  si="Sí, bloquear"):
            return
        self._con_turnos(horarios.bloquear_franja, self.fecha.isoformat(), hora)

    def _bloquear_dias(self, desde: str, hasta: str, motivo: str) -> None:
        texto = desde if desde == hasta else f"del {desde} al {hasta}"
        if not dialogos.confirmar(self, "Bloquear", f"¿Bloquear {texto}? No se podrán agendar turnos.", si="Sí, bloquear"):
            return
        self._con_turnos(horarios.bloquear_dias, desde, hasta, motivo)

    def _con_turnos(self, funcion, *args) -> None:
        """Ejecuta un bloqueo; si hay turnos activos, los lista para que la administradora decida (RN-11)."""
        try:
            funcion(self.ctx.conn, self.ctx.sesion, *args)
        except horarios.BloqueoConTurnos as e:
            detalle = "\n".join(f"• {t['fecha']} {t['hora']} — {t['mascota_nombre']} — {t['propietario_nombre']} "
                                f"— {formato_celular(t['celular1'])} — {rt.ESTADOS[t['estado']]}" for t in e.turnos)
            if dialogos.reporte(self, "Hay turnos activos", str(e) + "\n\nPuede moverlos o cancelarlos desde la agenda.",
                                detalle, si="Ir a la agenda de ese día", no="No bloquear"):
                self.ctx.ventana.mostrar("Agenda", fecha=e.turnos[0]["fecha"], turno_id=e.turnos[0]["id"])
            return
        except ErrorClinican as e:
            dialogos.error(self, str(e))
            return
        dialogos.aviso(self, "Bloqueado", "Listo. El bloqueo quedó guardado.")
        self._franjas_fecha()
        if self.admin:
            self._bloqueos()

    # ============================================================ bloqueos
    def _bloqueos(self) -> None:
        z = self.zona_bloqueos
        for h in z.winfo_children():
            h.destroy()
        tema.subtitulo(z, "Bloquear un rango de fechas").pack(anchor="w", padx=12, pady=(12, 6))
        fila = ctk.CTkFrame(z, fg_color="transparent")
        fila.pack(fill="x", padx=12)
        desde, hasta, motivo = ctk.StringVar(value=date.today().isoformat()), ctk.StringVar(), ctk.StringVar()
        for texto, var, ancho in (("Desde", desde, 150), ("Hasta", hasta, 150), ("Motivo", motivo, 280)):
            tema.etiqueta(fila, texto + ":", negrita=True).pack(side="left", padx=(0, 6))
            tema.entrada(fila, ancho=ancho, textvariable=var).pack(side="left", padx=(0, 14))
        tema.boton(z, "Bloquear rango", lambda: self._bloquear_dias(desde.get().strip(), hasta.get().strip() or desde.get().strip(),
                                                                     motivo.get()), estilo="peligro", ancho=260).pack(anchor="w", padx=12, pady=10)

        tema.subtitulo(z, "Bloqueos vigentes").pack(anchor="w", padx=12, pady=(16, 6))
        lista = horarios.bloqueos_desde(self.ctx.conn)
        if not lista:
            tema.etiqueta(z, "No hay bloqueos desde hoy.", color=tema.GRIS_TEXTO).pack(anchor="w", padx=12)
        for b in lista:
            fila = ctk.CTkFrame(z, fg_color=tema.FONDO, corner_radius=10)
            fila.pack(fill="x", padx=12, pady=3)
            texto = f"{b['fecha']}   {b['hora'] or 'Día completo'}   ·   {b['motivo'] or 'sin motivo'}   ·   por {b['creado_por_nombre']}"
            tema.etiqueta(fila, texto).pack(side="left", padx=12, pady=8)
            tema.boton(fila, "Quitar bloqueo", lambda i=b["id"]: self._desbloquear(i), estilo="secundario",
                       ancho=180).pack(side="right", padx=6, pady=4)

    def _desbloquear(self, bloqueo_id: int) -> None:
        if dialogos.ejecutar(self, horarios.desbloquear, self.ctx.conn, self.ctx.sesion, bloqueo_id) is not dialogos.FALLO:
            self._bloqueos()
            self._franjas_fecha()

    # ================================================== plantilla semanal
    def _plantilla(self) -> None:
        z = self.zona_plantilla
        for h in z.winfo_children():
            h.destroy()
        tema.etiqueta(z, "Marque las horas que se atienden cada día. Domingo está cerrado (use horas extra si hace falta).",
                      color=tema.GRIS_TEXTO).pack(anchor="w", padx=12, pady=(10, 6))
        filas = horarios.plantilla(self.ctx.conn)
        horas = sorted({f["hora"] for f in filas})
        estado = {(f["dia_semana"], f["hora"]): f["activa"] for f in filas}
        rejilla = ctk.CTkFrame(z, fg_color="transparent")
        rejilla.pack(anchor="w", padx=12)
        for c, (dia, nombre) in enumerate(DIAS_CORTOS.items(), start=1):
            tema.etiqueta(rejilla, nombre, negrita=True).grid(row=0, column=c, padx=10, pady=4)
        for r, hora in enumerate(horas, start=1):
            tema.etiqueta(rejilla, hora, negrita=True).grid(row=r, column=0, padx=(0, 10), sticky="w")
            for c, dia in enumerate(DIAS_CORTOS, start=1):
                var = ctk.IntVar(value=estado.get((dia, hora), 0))
                chk = tema.casilla(rejilla, "", var, lambda d=dia, h=hora, v=var: self._cambiar_base(d, h, v), width=30)
                chk.grid(row=r, column=c, padx=10, pady=2)
        fila = ctk.CTkFrame(z, fg_color=tema.VERDE_SUAVE, corner_radius=10)
        fila.pack(fill="x", padx=12, pady=12)
        tema.etiqueta(fila, "Agregar hora a la plantilla (HH:MM):", negrita=True).pack(side="left", padx=12, pady=10)
        nueva = tema.entrada(fila, ancho=110)
        nueva.pack(side="left")

        def agregar():
            for dia in DIAS_CORTOS:
                if dialogos.ejecutar(self, horarios.fijar_franja_base, self.ctx.conn, self.ctx.sesion, dia,
                                     nueva.get(), True) is dialogos.FALLO:
                    break
            self._plantilla()

        tema.boton(fila, "Agregar a lunes–sábado", agregar, ancho=260).pack(side="left", padx=10)

    def _cambiar_base(self, dia: int, hora: str, var) -> None:
        if dialogos.ejecutar(self, horarios.fijar_franja_base, self.ctx.conn, self.ctx.sesion, dia, hora,
                             bool(var.get())) is dialogos.FALLO:
            var.set(0 if var.get() else 1)
