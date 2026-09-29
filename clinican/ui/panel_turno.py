"""Panel lateral de un turno: datos, abonos y acciones según su estado."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

import customtkinter as ctk

from clinican.dominio import turnos as rt
from clinican.dominio.catalogos import TIPOS_SERVICIO
from clinican.dominio.cupos import CATEGORIAS
from clinican.dominio.formato import pesos
from clinican.dominio.propietarios import formato_celular
from clinican.servicios import turnos
from clinican.servicios.turnos import Abono
from clinican.ui import dialogos, tema

MEDIOS = rt.MEDIOS_PAGO


def avisar_liberados(padre, resultado) -> None:
    """RN-08: avisa al personal qué pendientes perdieron el cupo, para ofrecer otra hora."""
    if resultado is dialogos.FALLO or not getattr(resultado, "liberados", None):
        return
    detalle = "\n".join(
        f"• {t['mascota_nombre']} — {t['propietario_nombre']} — {formato_celular(t['celular1'])} "
        f"({t['fecha']} {t['hora']})" for t in resultado.liberados)
    dialogos.reporte(padre, "Otros turnos quedaron liberados",
                     "Otro cliente pagó primero y el cupo se agotó. Llame a estas personas para ofrecerles otra hora:",
                     detalle)


class PanelTurno(ctk.CTkScrollableFrame):
    def __init__(self, padre, ctx, turno_id: int, al_cambiar: Callable):
        super().__init__(padre, fg_color=tema.BLANCO, corner_radius=14, border_width=1, border_color=tema.BORDE)
        self.ctx = ctx
        self.tid = turno_id
        self.al_cambiar = al_cambiar
        t = dialogos.ejecutar(self, turnos.turno, ctx.conn, ctx.sesion, turno_id)
        if t is dialogos.FALLO:
            return
        self.t = t
        self._datos()
        self.zona = ctk.CTkFrame(self, fg_color="transparent")
        self.zona.pack(fill="x", padx=16, pady=(6, 16))
        self._acciones()

    # ------------------------------------------------------------------ datos
    def _datos(self) -> None:
        t = self.t
        tema.subtitulo(self, f"{t['mascota_nombre']} — {t['hora']}").pack(anchor="w", padx=16, pady=(14, 2))
        fondo = tema.FUCSIA if t["estado"] in (rt.PENDIENTE, rt.NO_ATENDIDO, rt.NO_ASISTIO_SIN_AVISO) else tema.VERDE
        texto = rt.ESTADOS[t["estado"]]
        if t["estado"] == rt.LIBERADO and t["motivo_liberacion"]:
            texto += f" — {rt.MOTIVOS_LIBERACION[t['motivo_liberacion']].lower()}"
        if t["motivo_no_atendido"]:
            texto += f" — {rt.MOTIVOS_NO_ATENDIDO[t['motivo_no_atendido']].lower()}"
        tema.insignia(self, texto, fondo).pack(anchor="w", padx=16, pady=(0, 8))
        if t["propietario_provisional"]:
            tema.insignia(self, "CLIENTE SIN REGISTRAR: al llegar, registre sus datos y consentimientos",
                          tema.FUCSIA).pack(anchor="w", padx=16, pady=(0, 8))

        llamar = t["estado"] in (rt.LISTA, rt.NO_ATENDIDO)
        if llamar:
            celulares = " / ".join(formato_celular(c) for c in (t["celular1"], t["celular2"]) if c)
            ctk.CTkLabel(self, text=f"LLAMAR A {t['propietario_nombre'].upper()}\n{celulares}",
                         font=tema.fuente(tema.TAM_SUBTITULO, True), fg_color=tema.FUCSIA, text_color=tema.BLANCO,
                         corner_radius=10, justify="left", padx=14, pady=10).pack(fill="x", padx=16, pady=(0, 6))
            if t["llamada_en"]:
                tema.etiqueta(self, f"Llamada registrada: {t['llamada_en']}", negrita=True).pack(anchor="w", padx=16)

        filas = [
            ("Fecha", f"{t['fecha']} a las {t['hora']}"),
            ("Mascota", f"{t['mascota_nombre']} ({t['raza_nombre']})"),
            ("Servicio", TIPOS_SERVICIO.get(t["tipo_servicio"], "—")),
            ("Cupo", CATEGORIAS[t["categoria_cupo"]]),
            ("Propietario", t["propietario_nombre"]),
            ("Celulares", " / ".join(formato_celular(c) for c in (t["celular1"], t["celular2"]) if c)),
            ("Agendó", t["agendado_por_nombre"]),
            ("Abonado", pesos(t["abonado"]) if t["abonado"] else "Sin abono"),
        ]
        if t["estado"] == rt.PENDIENTE and t["pendiente_hasta"]:
            filas.append(("Pagar antes de", t["pendiente_hasta"][11:16]))
        if t["avisado_en"]:
            filas.append(("Avisó", t["avisado_en"]))
        caja = ctk.CTkFrame(self, fg_color="transparent")
        caja.pack(fill="x", padx=16, pady=4)
        for i, (k, v) in enumerate(filas):
            tema.etiqueta(caja, k, tema.TAM_PEQUENO, color=tema.GRIS_TEXTO).grid(row=i, column=0, sticky="nw", padx=(0, 12), pady=2)
            tema.etiqueta(caja, v, negrita=True, wraplength=320).grid(row=i, column=1, sticky="w", pady=2)

        if t["grupo_id"]:
            otros = [g for g in turnos.grupo(self.ctx.conn, self.ctx.sesion, t["grupo_id"]) if g["id"] != t["id"]]
            if otros:
                texto = ", ".join(f"{g['mascota_nombre']} {g['fecha'][5:]} {g['hora']}" for g in otros)
                tema.etiqueta(self, f"Mismo grupo: {texto}", tema.TAM_PEQUENO, color=tema.GRIS_TEXTO,
                              wraplength=440).pack(anchor="w", padx=16, pady=(4, 0))
        self._lista_abonos()
        ctk.CTkFrame(self, fg_color=tema.BORDE, height=2).pack(fill="x", padx=16, pady=10)

    def _lista_abonos(self) -> None:
        lista = turnos.abonos(self.ctx.conn, self.ctx.sesion, self.tid)
        if not lista:
            return
        tema.etiqueta(self, "Abonos", negrita=True).pack(anchor="w", padx=16, pady=(8, 2))
        for a in lista:
            fila = ctk.CTkFrame(self, fg_color=tema.FONDO, corner_radius=8)
            fila.pack(fill="x", padx=16, pady=2)
            texto = (f"{pesos(a['monto'])} · {MEDIOS[a['medio']]} · {a['recibido_en'][:16]} · "
                     f"{rt.ESTADOS_ABONO[a['estado']]}" + (f" · {a['referencia']}" if a["referencia"] else ""))
            tema.etiqueta(fila, texto, tema.TAM_PEQUENO, wraplength=330).pack(side="left", padx=8, pady=4)
            if a["estado"] == "VIGENTE":
                ctk.CTkButton(fila, text="Corregir", width=90, height=34, fg_color=tema.GRIS_BOTON,
                              hover_color=tema.GRIS_BOTON_HOVER, text_color=tema.NEGRO,
                              font=tema.fuente(tema.TAM_PEQUENO, True),
                              command=lambda ab=a: self._form_corregir(ab)).pack(side="right", padx=6, pady=4)

    # --------------------------------------------------------------- acciones
    def _limpiar(self) -> None:
        for hijo in self.zona.winfo_children():
            hijo.destroy()

    def _boton(self, texto, accion, estilo="primario") -> None:
        tema.boton(self.zona, texto, accion, estilo=estilo, ancho=420).pack(anchor="w", pady=4)

    def _acciones(self) -> None:
        self._limpiar()
        e = self.t["estado"]
        if self.t["propietario_provisional"] and e in rt.ACTIVOS:
            self._boton("Registrar datos del propietario", lambda: self.ctx.ventana.mostrar(
                "Propietarios", propietario_id=self.t["propietario_id"], pestana="Datos"))
        if e == rt.PENDIENTE:
            self._boton("Registrar abono", self._form_abono)
            if self.t["grupo_id"]:
                self._boton("Pago único del grupo", lambda: self._form_abono(grupo=True), "secundario")
        if e == rt.CONFIRMADO:
            self._boton("Llegó: iniciar atención", lambda: self._hacer(turnos.iniciar_atencion))
        if e == rt.EN_PROCESO:
            self._boton("Mascota lista: avisar al dueño", lambda: self._hacer(turnos.marcar_lista))
        if e in (rt.LISTA, rt.NO_ATENDIDO):
            self._boton("Registrar que ya se llamó", lambda: self._hacer(turnos.registrar_llamada), "secundario")
        if e == rt.LISTA:
            self._boton("Entregar y cobrar saldo", self._entregar)
        if e in (rt.PENDIENTE, rt.CONFIRMADO):
            self._boton("Mover a otra fecha u hora", self._form_mover, "secundario")
        if e == rt.CONFIRMADO:
            self._boton("No asistió", self._form_no_asistio, "secundario")
        if e in (rt.CONFIRMADO, rt.EN_PROCESO):
            self._boton("No se pudo atender", self._form_no_atendido, "secundario")
        if self.t["servicio_id"]:
            self._boton("Abrir ficha de servicio", self._abrir_ficha, "secundario")
        if e in (rt.PENDIENTE, rt.CONFIRMADO):
            self._boton("Cancelar turno", self._cancelar, "peligro")

    def _hacer(self, funcion, *args) -> None:
        r = dialogos.ejecutar(self, funcion, self.ctx.conn, self.ctx.sesion, self.tid, *args)
        if r is not dialogos.FALLO:
            self.al_cambiar(self.tid)

    def _volver_boton(self) -> None:
        tema.boton(self.zona, "Volver", self._acciones, estilo="secundario", ancho=200).pack(anchor="w", pady=(8, 0))

    # ------------------------------------------------------------ formularios
    def _form_abono(self, grupo: bool = False) -> None:
        self._limpiar()
        config = self.ctx.config()
        minimo = int(config["abono_minimo"])
        tema.subtitulo(self.zona, "Pago del grupo" if grupo else "Registrar abono").pack(anchor="w")
        tema.etiqueta(self.zona, f"Abono mínimo sugerido: {pesos(minimo)} por mascota.", color=tema.GRIS_TEXTO).pack(anchor="w")
        datos_pago(self.zona, config).pack(fill="x", pady=8)
        entradas = []
        if grupo:
            pendientes = [g for g in turnos.grupo(self.ctx.conn, self.ctx.sesion, self.t["grupo_id"])
                          if g["estado"] == rt.PENDIENTE]
            tema.etiqueta(self.zona, "Monto de cada mascota (puede cambiarlo)", negrita=True).pack(anchor="w", pady=(6, 2))
            for g in pendientes:
                fila = ctk.CTkFrame(self.zona, fg_color="transparent")
                fila.pack(anchor="w", pady=2)
                tema.etiqueta(fila, f"{g['mascota_nombre']} ({g['hora']})", width=200).pack(side="left")
                e = tema.entrada(fila, ancho=160)
                e.insert(0, pesos(minimo).replace("$", ""))
                e.pack(side="left")
                entradas.append(e)
        else:
            tema.etiqueta(self.zona, "Monto", negrita=True).pack(anchor="w", pady=(6, 2))
            monto = tema.entrada(self.zona, ancho=220)
            monto.insert(0, pesos(minimo).replace("$", ""))
            monto.pack(anchor="w")
            entradas.append(monto)
        tema.etiqueta(self.zona, "Medio de pago", negrita=True).pack(anchor="w", pady=(8, 2))
        medio = tema.Opciones(self.zona, MEDIOS, inicial="NEQUI")
        medio.pack(anchor="w")
        tema.etiqueta(self.zona, "Nota del comprobante (opcional)", negrita=True).pack(anchor="w", pady=(8, 2))
        ref = tema.entrada(self.zona, ancho=420)
        ref.pack(anchor="w")
        verificado = ctk.IntVar(value=0)
        tema.casilla(self.zona, "Verifiqué el pago: confirmar el turno aunque sea\nmenor al mínimo (incluso $0)",
                     verificado).pack(anchor="w", pady=(10, 0))

        def guardar():
            confirmar = bool(verificado.get())
            if grupo:
                r = dialogos.ejecutar(self, turnos.pagar_grupo, self.ctx.conn, self.ctx.sesion, self.t["grupo_id"],
                                      Abono(0, medio.codigo, ref.get()), montos=[e.get() for e in entradas],
                                      confirmar=confirmar)
            else:
                r = dialogos.ejecutar(self, turnos.registrar_abono, self.ctx.conn, self.ctx.sesion, self.tid,
                                      Abono(entradas[0].get(), medio.codigo, ref.get()), confirmar=confirmar)
            if r is dialogos.FALLO:
                return
            avisar_liberados(self, r)
            self.al_cambiar(self.tid)

        tema.boton(self.zona, "Guardar abono", guardar, ancho=300).pack(anchor="w", pady=(12, 0))
        self._volver_boton()

    def _form_corregir(self, a) -> None:
        self._limpiar()
        tema.subtitulo(self.zona, "Corregir abono").pack(anchor="w")
        tema.etiqueta(self.zona, "Escriba 0 para anular el abono. El cambio queda en la auditoría.",
                      color=tema.GRIS_TEXTO).pack(anchor="w")
        tema.etiqueta(self.zona, "Monto", negrita=True).pack(anchor="w", pady=(8, 2))
        monto = tema.entrada(self.zona, ancho=220)
        monto.insert(0, pesos(a["monto"]).replace("$", ""))
        monto.pack(anchor="w")
        tema.etiqueta(self.zona, "Medio de pago", negrita=True).pack(anchor="w", pady=(8, 2))
        medio = tema.Opciones(self.zona, MEDIOS, inicial=a["medio"])
        medio.pack(anchor="w")
        tema.etiqueta(self.zona, "Nota del comprobante", negrita=True).pack(anchor="w", pady=(8, 2))
        ref = tema.entrada(self.zona, ancho=420)
        ref.insert(0, a["referencia"] or "")
        ref.pack(anchor="w")

        def guardar():
            r = dialogos.ejecutar(self, turnos.editar_abono, self.ctx.conn, self.ctx.sesion, a["id"], monto.get(),
                                  medio.codigo, ref.get())
            if r is not dialogos.FALLO:
                self.al_cambiar(self.tid)

        tema.boton(self.zona, "Guardar corrección", guardar, ancho=300).pack(anchor="w", pady=(12, 0))
        self._volver_boton()

    def _form_mover(self) -> None:
        self._limpiar()
        tema.subtitulo(self.zona, "Mover turno").pack(anchor="w")
        tema.etiqueta(self.zona, "Los abonos se conservan.", color=tema.GRIS_TEXTO).pack(anchor="w")
        tema.etiqueta(self.zona, "Fecha nueva (AAAA-MM-DD)", negrita=True).pack(anchor="w", pady=(8, 2))
        fila = ctk.CTkFrame(self.zona, fg_color="transparent")
        fila.pack(anchor="w")
        fecha = tema.entrada(fila, ancho=180)
        fecha.insert(0, self.t["fecha"])
        fecha.pack(side="left")
        horas = ctk.CTkFrame(self.zona, fg_color="transparent")
        horas.pack(fill="x", pady=8)

        def ver():
            for h in horas.winfo_children():
                h.destroy()
            lista = dialogos.ejecutar(self, turnos.franjas_para, self.ctx.conn, self.ctx.sesion, fecha.get().strip(),
                                      self.t["mascota_id"], self.t["tipo_servicio"] or "MAQUINA")
            if lista is dialogos.FALLO:
                return
            if not lista:
                tema.etiqueta(horas, "No hay horas con cupo ese día.", color=tema.ROJO_ERROR).pack(anchor="w")
                return
            SelectorHoras(horas, lista, lambda h: mover(h)).pack(fill="x")

        def mover(hora):
            r = dialogos.ejecutar(self, turnos.mover, self.ctx.conn, self.ctx.sesion, self.tid, fecha.get().strip(), hora)
            if r is dialogos.FALLO:
                return
            avisar_liberados(self, r)
            self.al_cambiar(self.tid, fecha.get().strip())

        tema.boton(fila, "Ver horas", ver, estilo="secundario", ancho=140).pack(side="left", padx=8)
        self._volver_boton()

    def _form_no_asistio(self) -> None:
        self._limpiar()
        horas = self.ctx.config()["horas_minimas_aviso"]
        tema.subtitulo(self.zona, "No asistió").pack(anchor="w")
        tema.etiqueta(self.zona, f"Si el dueño avisó con al menos {horas} horas de anticipación, el abono se conserva "
                                 "para reprogramar. Si no avisó o avisó tarde, el abono se pierde y deberá abonar "
                                 "de nuevo para su próximo turno.", wraplength=420).pack(anchor="w", pady=(0, 8))
        avisado = ctk.IntVar(value=0)
        tema.casilla(self.zona, "El dueño avisó que no vendría", avisado).pack(anchor="w")
        tema.etiqueta(self.zona, "¿Cuándo avisó? (AAAA-MM-DD HH:MM)", negrita=True).pack(anchor="w", pady=(8, 2))
        cuando = tema.entrada(self.zona, ancho=260)
        cuando.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M"))
        cuando.pack(anchor="w")

        def guardar():
            aviso = cuando.get() if avisado.get() else None
            r = dialogos.ejecutar(self, turnos.no_asistio, self.ctx.conn, self.ctx.sesion, self.tid, aviso)
            if r is dialogos.FALLO:
                return
            dialogos.aviso(self, "Registrado", rt.ESTADOS[r] + (
                ". El propietario deberá pagar un abono nuevo para agendar." if r == rt.NO_ASISTIO_SIN_AVISO
                else ". El abono queda a favor para reprogramar."))
            self.al_cambiar(self.tid)

        tema.boton(self.zona, "Guardar", guardar, ancho=240).pack(anchor="w", pady=(12, 0))
        self._volver_boton()

    def _form_no_atendido(self) -> None:
        self._limpiar()
        tema.subtitulo(self.zona, "No se pudo atender").pack(anchor="w")
        tema.etiqueta(self.zona, "Se destacarán los celulares para llamar al dueño y que retire a la mascota.",
                      wraplength=420, color=tema.GRIS_TEXTO).pack(anchor="w", pady=(0, 8))
        tema.etiqueta(self.zona, "Elija el motivo:", negrita=True).pack(anchor="w")
        for codigo, texto in rt.MOTIVOS_NO_ATENDIDO.items():
            tema.boton(self.zona, texto, lambda c=codigo: self._no_atendido(c),
                       estilo="secundario", ancho=420).pack(anchor="w", pady=3)
        self._volver_boton()

    def _no_atendido(self, motivo: str) -> None:
        destino = rt.A_FAVOR
        if self.t["abonado"]:
            destino = dialogos.elegir(
                self, "¿Qué pasa con el abono?",
                f"El propietario abonó {pesos(self.t['abonado'])}. ¿Se le devuelve o queda a su favor para otro turno?",
                [("Queda a favor", rt.A_FAVOR), ("Devolver el abono", rt.DEVOLVER)],
            )
            if destino is None:
                return
        self._hacer(turnos.no_atendido, motivo, destino)

    def _entregar(self) -> None:
        cuenta = dialogos.ejecutar(self, turnos.cobro, self.ctx.conn, self.ctx.sesion, self.tid)
        if cuenta is dialogos.FALLO:
            return
        if cuenta["falta_precio"]:
            dialogos.error(self, "Antes de entregar, escriba el precio final en la ficha de servicio.")
            self._abrir_ficha()
            return
        mensaje = (f"Total del servicio: {pesos(cuenta['total'])}\nAbonado: {pesos(cuenta['abonado'])}\n\n"
                   f"SALDO A COBRAR: {pesos(cuenta['saldo'])}")
        if dialogos.confirmar(self, "Entregar y cobrar", mensaje, si="Cobré el saldo y entregué", no="Volver"):
            self._hacer(turnos.entregar)

    def _cancelar(self) -> None:
        op = dialogos.ejecutar(self, turnos.opciones_cancelacion, self.ctx.conn, self.ctx.sesion, self.tid)
        if op is dialogos.FALLO:
            return
        if not op["abonado"]:
            if dialogos.confirmar(self, "Cancelar turno", f"¿Cancelar el turno de {self.t['mascota_nombre']}?",
                                  si="Sí, cancelar turno"):
                self._hacer(turnos.cancelar, rt.A_FAVOR)
            return
        opciones = [("Dejar el abono a favor", rt.A_FAVOR)]
        if op["puede_devolver"]:
            opciones.append(("Devolver el abono", rt.DEVOLVER))
        opciones.append(("Mejor mover el turno", "MOVER"))
        nota = ("Se puede devolver porque faltan más de {h} horas.".format(h=op["horas"]) if op["puede_devolver"]
                else f"No se puede devolver: faltan menos de {op['horas']} horas para el turno.")
        eleccion = dialogos.elegir(
            self, "Cancelar turno",
            f"El propietario abonó {pesos(op['abonado'])}. {nota} ¿Qué hacemos con el abono?", opciones)
        if eleccion == "MOVER":
            self._form_mover()
        elif eleccion is not None:
            self._hacer(turnos.cancelar, eleccion)

    def _abrir_ficha(self) -> None:
        fecha, tid = self.t["fecha"], self.tid
        ventana = self.ctx.ventana
        self.ctx.abrir_ficha(self.t["propietario_id"], self.t["mascota_id"], self.t["servicio_id"],
                             volver=lambda: ventana.mostrar("Agenda", fecha=fecha, turno_id=tid), menu="Agenda")


class SelectorHoras(ctk.CTkFrame):
    """Botones grandes con cada hora disponible y sus cupos libres."""

    def __init__(self, padre, horas: list[tuple[str, int]], al_elegir: Callable[[str], None], columnas: int = 4):
        super().__init__(padre, fg_color="transparent")
        for i, (hora, libres) in enumerate(horas):
            ctk.CTkButton(
                self, text=f"{hora}\n{libres} libre{'s' if libres != 1 else ''}", command=lambda h=hora: al_elegir(h),
                width=100, height=60, fg_color=tema.VERDE_SUAVE, hover_color=tema.VERDE, text_color=tema.NEGRO,
                border_color=tema.VERDE, border_width=2, font=tema.fuente(tema.TAM_NORMAL, True), corner_radius=10,
            ).grid(row=i // columnas, column=i % columnas, padx=4, pady=4, sticky="w")


def datos_pago(padre, config: dict[str, str]) -> ctk.CTkFrame:
    """Recuadro con los datos de pago del abono y el WhatsApp para el comprobante."""
    caja = ctk.CTkFrame(padre, fg_color=tema.VERDE_SUAVE, corner_radius=10)
    for texto, negrita in (
        (f"Nequi: {config['nequi_numero']} — {config['pago_titular']}", True),
        (f"Llave Bre-B: {config['breb_llave']} — {config['pago_titular']}", True),
        (f"Comprobante al WhatsApp {config['whatsapp_numero']} (no al número de Nequi)", False),
    ):
        tema.etiqueta(caja, texto, tema.TAM_PEQUENO, negrita=negrita, wraplength=440).pack(anchor="w", padx=12, pady=2)
    return caja
