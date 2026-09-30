"""Inicio / Agenda del día (pantalla 2): franjas de mañana y tarde con cupos y turnos."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import customtkinter as ctk

from clinican.dominio import turnos as rt
from clinican.dominio.catalogos import TIPOS_SERVICIO
from clinican.dominio.cupos import CATEGORIAS
from clinican.dominio.formato import pesos
from clinican.dominio.franjas import JORNADAS, MANANA, TARDE
from clinican.dominio.propietarios import formato_celular
from clinican.servicios import turnos
from clinican.ui import dialogos, tema
from clinican.ui.panel_turno import PanelTurno

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
COLUMNAS_TARJETAS = 2


def fecha_larga(d: date) -> str:
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]} de {d.year}"


def cuenta_regresiva(segundos: int) -> str:
    return f"{segundos // 60:02d}:{segundos % 60:02d}"


class PantallaAgenda(ctk.CTkFrame):
    def __init__(self, padre, ctx, fecha: str | None = None, turno_id: int | None = None):
        super().__init__(padre, fg_color="transparent")
        self.ctx = ctx
        self.fecha = date.fromisoformat(fecha) if fecha else date.today()
        self.seleccionado = turno_id
        self.relojes: list[tuple[ctk.CTkLabel, str]] = []
        self._tic = None

        arriba = ctk.CTkFrame(self, fg_color="transparent")
        arriba.pack(fill="x", pady=(0, 8))
        tema.boton(arriba, "◀", lambda: self._ir(-1), estilo="secundario", ancho=56).pack(side="left")
        tema.boton(arriba, "Hoy", self._hoy, estilo="secundario", ancho=90).pack(side="left", padx=6)
        tema.boton(arriba, "▶", lambda: self._ir(1), estilo="secundario", ancho=56).pack(side="left")
        self.lbl_fecha = tema.titulo(arriba, "")
        self.lbl_fecha.pack(side="left", padx=16)
        tema.boton(arriba, "+ Nuevo turno", self._nuevo, ancho=210).pack(side="right")
        self.ir_a = tema.entrada(arriba, ancho=150, placeholder_text="AAAA-MM-DD")
        self.ir_a.pack(side="right", padx=(0, 8))
        self.ir_a.bind("<Return>", lambda _e: self._ir_a_fecha())

        self.lbl_info = tema.etiqueta(self, "", color=tema.GRIS_TEXTO)
        self.lbl_info.pack(anchor="w", pady=(0, 8))

        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True)
        cuerpo.grid_columnconfigure(0, weight=3, uniform="a")
        cuerpo.grid_columnconfigure(1, weight=2, uniform="a")
        cuerpo.grid_rowconfigure(0, weight=1)
        self.lista = ctk.CTkScrollableFrame(cuerpo, fg_color=tema.FONDO)
        self.lista.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.panel = ctk.CTkFrame(cuerpo, fg_color="transparent")
        self.panel.grid(row=0, column=1, sticky="nsew")

        self.cargar()
        self._tic = self.after(1000, self._contar)

    def destroy(self):
        if self._tic:
            self.after_cancel(self._tic)
            self._tic = None
        super().destroy()

    # ------------------------------------------------------------ navegación
    def _ir(self, dias: int) -> None:
        self.fecha += timedelta(days=dias)
        self.seleccionado = None
        self.cargar()

    def _hoy(self) -> None:
        self.fecha = date.today()
        self.seleccionado = None
        self.cargar()

    def _ir_a_fecha(self) -> None:
        try:
            self.fecha = date.fromisoformat(self.ir_a.get().strip())
        except ValueError:
            dialogos.error(self, "Escriba la fecha como AAAA-MM-DD, por ejemplo 2026-10-05.")
            return
        self.ir_a.delete(0, "end")
        self.seleccionado = None
        self.cargar()

    def _nuevo(self) -> None:
        self.ctx.ventana.mostrar("Nuevo turno", fecha=self.fecha.isoformat())

    def al_expirar(self) -> None:
        """La ventana principal avisa que se liberaron turnos vencidos."""
        self.cargar()

    # ----------------------------------------------------------------- carga
    def cargar(self) -> None:
        datos = dialogos.ejecutar(self, turnos.agenda, self.ctx.conn, self.ctx.sesion, self.fecha.isoformat())
        if datos is dialogos.FALLO:
            return
        self.lbl_fecha.configure(text=fecha_larga(self.fecha).capitalize())
        partes = []
        if datos["personal_del_dia"] is not None:
            partes.append(f"Personal que atiende: {datos['personal_del_dia']} personas (informativo)")
        cupos = ", ".join(f"{CATEGORIAS[c]} {n}" for c, n in datos["cupos"].items())
        partes.append(f"Cupos por franja: {cupos}")
        self.lbl_info.configure(text="   ·   ".join(partes))

        for hijo in self.lista.winfo_children():
            hijo.destroy()
        self.relojes = []
        if datos["bloqueo"]:
            tema.insignia(self.lista, f"Día bloqueado: {datos['bloqueo']}", tema.FUCSIA).pack(fill="x", pady=(0, 10))
        if not datos["franjas"]:
            texto = "Domingo: la peluquería está cerrada." if self.fecha.weekday() == 6 else "No hay franjas para esta fecha."
            tema.etiqueta(self.lista, texto, tema.TAM_SUBTITULO, color=tema.GRIS_TEXTO).pack(pady=40)
        for jornada in (MANANA, TARDE):
            filas = [f for f in datos["franjas"] if f["jornada"] == jornada]
            if not filas:
                continue
            tema.subtitulo(self.lista, JORNADAS[jornada].upper()).pack(anchor="w", pady=(10, 4))
            for f in filas:
                self._franja(f)
        self._mostrar_panel()

    def _franja(self, f: dict) -> None:
        caja = tema.tarjeta(self.lista)
        caja.pack(fill="x", pady=5)
        cab = ctk.CTkFrame(caja, fg_color="transparent")
        cab.pack(fill="x", padx=14, pady=(10, 4))
        tema.etiqueta(cab, f["hora"], tema.TAM_SUBTITULO, negrita=True).pack(side="left")
        if f["extra"]:
            tema.insignia(cab, "franja extra", tema.AZUL).pack(side="left", padx=8)
        if f["libres"] is not None:
            libres = "   ".join(f"{CATEGORIAS[c]}: {n}" for c, n in f["libres"].items())
            tema.etiqueta(cab, f"Libres → {libres}", tema.TAM_PEQUENO, color=tema.GRIS_TEXTO).pack(side="right")
        if not f["turnos"]:
            return
        rejilla = ctk.CTkFrame(caja, fg_color="transparent")
        rejilla.pack(fill="x", padx=10, pady=(0, 10))
        for c in range(COLUMNAS_TARJETAS):
            rejilla.grid_columnconfigure(c, weight=1, uniform="t")
        for i, t in enumerate(f["turnos"]):
            self._tarjeta_turno(rejilla, t).grid(row=i // COLUMNAS_TARJETAS, column=i % COLUMNAS_TARJETAS,
                                                 sticky="nsew", padx=4, pady=4)

    def _tarjeta_turno(self, padre, t) -> ctk.CTkFrame:
        fondo, borde = tema.ESTILO_ESTADO[t["estado"]]
        elegido = t["id"] == self.seleccionado
        tarjeta = ctk.CTkFrame(padre, fg_color=fondo, border_color=tema.NEGRO if elegido else borde,
                               border_width=4 if elegido else 2, corner_radius=12)
        inactivo = t["estado"] not in rt.ACTIVOS and t["estado"] != rt.ATENDIDO
        color = tema.GRIS_TEXTO if inactivo else tema.NEGRO
        lineas = [
            (f"{t['hora']} · {t['mascota_nombre']}", True, tema.TAM_NORMAL),
            (f"{t['raza_nombre']} · {TIPOS_SERVICIO.get(t['tipo_servicio'], '')}", False, tema.TAM_PEQUENO),
            (f"{t['propietario_nombre']}{' (sin registrar)' if t['propietario_provisional'] else ''} · "
             f"{formato_celular(t['celular1'])}", False, tema.TAM_PEQUENO),
            ((f"Abono: {pesos(t['abonado'])} ✔" if t["abonado"] else "Sin abono ✖")
             + f"   ·   Agendó: {t['agendado_por_nombre']}", False, tema.TAM_PEQUENO),
        ]
        for texto, negrita, tam in lineas:
            tema.etiqueta(tarjeta, texto, tam, negrita=negrita, color=color, wraplength=360).pack(anchor="w", padx=12, pady=(4, 0))
        pie = ctk.CTkFrame(tarjeta, fg_color="transparent")
        pie.pack(fill="x", padx=12, pady=(4, 10))
        tema.etiqueta(pie, rt.ESTADOS[t["estado"]].upper(), tam=tema.TAM_PEQUENO, negrita=True, color=color).pack(side="left")
        if t["grupo_id"]:
            tema.etiqueta(pie, "· grupo", tema.TAM_PEQUENO, color=tema.GRIS_TEXTO).pack(side="left", padx=6)
        if t["estado"] == rt.PENDIENTE and t["pendiente_hasta"]:
            reloj = tema.etiqueta(pie, "", tema.TAM_PEQUENO, negrita=True, color=tema.ROJO_ERROR)
            reloj.pack(side="right")
            self.relojes.append((reloj, t["pendiente_hasta"]))
        self._clic(tarjeta, lambda: self._elegir(t["id"]))
        return tarjeta

    def _clic(self, widget, accion) -> None:
        widget.bind("<Button-1>", lambda _e: accion())
        widget.configure(cursor="hand2")
        for hijo in widget.winfo_children():
            self._clic(hijo, accion)

    def _elegir(self, turno_id: int) -> None:
        self.seleccionado = turno_id
        self.cargar()

    def _mostrar_panel(self) -> None:
        for hijo in self.panel.winfo_children():
            hijo.destroy()
        if self.seleccionado is None:
            t = tema.tarjeta(self.panel)
            t.pack(fill="both", expand=True)
            tema.etiqueta(t, "Toque un turno para ver sus datos\ny las acciones disponibles.",
                          tema.TAM_SUBTITULO, color=tema.GRIS_TEXTO, justify="center", anchor="center").pack(expand=True)
            return
        self.panel_turno = PanelTurno(self.panel, self.ctx, self.seleccionado, al_cambiar=self._tras_accion)
        self.panel_turno.pack(fill="both", expand=True)

    def _tras_accion(self, turno_id: int | None = None, fecha: str | None = None) -> None:
        if fecha:
            self.fecha = date.fromisoformat(fecha)
        self.seleccionado = turno_id
        self.cargar()

    # ------------------------------------------------------ cuenta regresiva
    def _contar(self) -> None:
        ahora = datetime.now()
        vencio = False
        for etiqueta, hasta in self.relojes:
            segundos = rt.segundos_restantes(hasta, ahora)
            vencio = vencio or segundos == 0
            try:
                etiqueta.configure(text=f"Vence en {cuenta_regresiva(segundos)}")
            except Exception:
                pass
        if vencio:
            self.cargar()  # la agenda ejecuta la expiración (RN-07)
        self._tic = self.after(1000, self._contar)
