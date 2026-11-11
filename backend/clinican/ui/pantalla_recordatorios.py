"""Recordatorios: la bandeja de salida (por enviar, enviados, fallidos y descartados)."""

from __future__ import annotations

import customtkinter as ctk

from clinican.dominio.entidades import EstadoNotificacion as EN
from clinican.dominio.estados import EstadoTurno
from clinican.servicios import agenda, clientes, configuracion, consultas, notificaciones
from clinican.ui import formato as fmt
from clinican.ui import tema
from clinican.ui.app import Pantalla
from clinican.ui.componentes import Lista, boton, etiqueta, tarjeta

CANALES = {"whatsapp": "WhatsApp", "archivo": "Archivo de texto (recordatorios.txt)", "consola": "Consola"}


class PantallaRecordatorios(Pantalla):
    def __init__(self, app):
        super().__init__(app)
        self.cuerpo = Lista(self)
        self.cuerpo.pack(fill="both", expand=True, padx=24, pady=20)

    def refrescar(self) -> None:
        self.cuerpo.vaciar()
        c = self.cuerpo
        hoy = self.ctx.hoy()
        with self.ctx.con() as con:
            bandeja = consultas.estado_bandeja(con, limite=30)
            cfg = configuracion.cargar(con)
            datos = {}
            for n in bandeja.proximas + bandeja.fallidas_recientes:
                t = agenda.obtener_turno(con, n.turno_id)
                p = clientes.obtener_propietario(con, t.propietario_id)
                m = clientes.obtener_mascota(con, t.mascota_id)
                datos[n.id] = (t, p, m)

        cab = ctk.CTkFrame(c, fg_color="transparent")
        cab.pack(fill="x")
        etiqueta(cab, "Recordatorios", tema.TITULO, True).pack(side="left")
        canal = CANALES.get(cfg.canal_notificaciones, cfg.canal_notificaciones)
        etiqueta(cab, f"Canal: {canal} · se revisa cada minuto", tema.ETIQUETA + 1, suave=True).pack(side="right")

        conteo = bandeja.conteo
        metricas = ctk.CTkFrame(c, fg_color="transparent")
        metricas.pack(fill="x", pady=(16, 0))
        metricas.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="m")
        fondo_fallo, letra_fallo, *_ = tema.estilo_estado(EstadoTurno.PENDIENTE_ABONO)
        for i, (titulo, valor, nota, alerta) in enumerate([
            ("Por enviar", conteo.get(EN.PENDIENTE, 0), "", False),
            ("Enviados", conteo.get(EN.ENVIADA, 0), "en total", False),
            ("Fallidos", conteo.get(EN.FALLIDA, 0), "tras 3 reintentos", conteo.get(EN.FALLIDA, 0) > 0),
            ("Descartados", conteo.get(EN.DESCARTADA, 0), "turno cancelado o movido", False),
        ]):
            t = ctk.CTkFrame(metricas, corner_radius=10, fg_color=fondo_fallo if alerta else tema.SUPERFICIE)
            t.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0 if i == 3 else 6))
            color = letra_fallo if alerta else None
            etiqueta(t, titulo, tema.ETIQUETA, alerta, suave=not alerta, color=color).pack(anchor="w", padx=16, pady=(12, 0))
            etiqueta(t, str(valor), 24, True, color=color).pack(anchor="w", padx=16)
            etiqueta(t, nota, tema.ETIQUETA, suave=True, color=color).pack(anchor="w", padx=16, pady=(0, 12))

        if bandeja.fallidas_recientes:
            etiqueta(c, "Necesita atención", tema.SUBTITULO, True).pack(anchor="w", pady=(20, 6))
            for n in bandeja.fallidas_recientes:
                t, p, m = datos[n.id]
                caja = tarjeta(c)
                caja.pack(fill="x", pady=4)
                textos = ctk.CTkFrame(caja, fg_color="transparent")
                textos.pack(side="left", fill="x", expand=True, padx=16, pady=12)
                etiqueta(textos, f"{m.nombre} · {p.nombre} · {fmt.celular(p.telefono)}", tema.CUERPO, True).pack(anchor="w")
                etiqueta(textos, f"Turno {fmt.momento(t.inicio, hoy)} · {n.intentos} intentos", suave=True).pack(anchor="w")
                if n.ultimo_error:
                    etiqueta(textos, f"Respuesta del canal: {n.ultimo_error}", color=letra_fallo, wraplength=640).pack(anchor="w")
                vigente = t.estado is EstadoTurno.CONFIRMADO and t.inicio > self.ctx.ahora()
                if vigente:
                    boton(caja, "Reintentar ahora", lambda n=n: self.reintentar(n.id), "principal").pack(side="right", padx=16)
                    boton(caja, "Corregir celular", lambda p=p: self.corregir(p.id)).pack(side="right")
                else:
                    etiqueta(caja, "El turno ya pasó o cambió", suave=True).pack(side="right", padx=16)

        etiqueta(c, "Próximos", tema.SUBTITULO, True).pack(anchor="w", pady=(20, 6))
        tabla = tarjeta(c)
        tabla.pack(fill="x")
        for col, titulo in enumerate(("Sale", "Para", "Turno", "Intentos")):
            etiqueta(tabla, titulo, tema.ETIQUETA, True, suave=True).grid(row=0, column=col, sticky="w", padx=16, pady=(10, 6))
        if not bandeja.proximas:
            etiqueta(tabla, "No hay recordatorios por enviar.", suave=True).grid(row=1, column=0, columnspan=4, sticky="w",
                                                                              padx=16, pady=(0, 12))
        for r, n in enumerate(bandeja.proximas, start=1):
            t, p, m = datos[n.id]
            for col, v in enumerate((fmt.momento(n.programada_para, hoy), f"{m.nombre} · {p.nombre}",
                                     fmt.momento(t.inicio, hoy), str(n.intentos) if n.intentos else "—")):
                etiqueta(tabla, v).grid(row=r, column=col, sticky="w", padx=16, pady=4)
        ctk.CTkFrame(tabla, height=8, fg_color="transparent").grid(row=999, column=0)

        ejemplo = notificaciones.texto_recordatorio("Carlos", "Daisy", self.ctx.ahora())
        etiqueta(c, f"Cada recordatorio sale {cfg.horas_antes_recordatorio} horas antes (o de inmediato si falta menos), "
                    f"y solo si el turno sigue confirmado. Ejemplo: «{ejemplo}»", tema.ETIQUETA + 1, suave=True,
                 wraplength=900).pack(anchor="w", pady=(12, 0))

    def reintentar(self, notificacion_id: int) -> None:
        self.ejecutar(lambda con: notificaciones.reintentar(con, notificacion_id, ahora=self.ctx.ahora()),
                      "Recordatorio en cola: sale en el próximo minuto.")

    def corregir(self, propietario_id: int) -> None:
        from clinican.ui.pantalla_clientes import DialogoCliente

        with self.ctx.con() as con:
            p = clientes.obtener_propietario(con, propietario_id)
        if DialogoCliente(self, self.ctx, p).mostrar():
            self.avisar("Celular guardado. Ahora puedes reintentar el envío.")
        self.refrescar()
