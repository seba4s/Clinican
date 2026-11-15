"""Recordatorios: la bandeja de salida (por enviar, enviados, fallidos y descartados)."""

from __future__ import annotations

from PySide6.QtCore import Signal, Slot

from clinican.dominio.entidades import EstadoNotificacion as EN
from clinican.dominio.estados import EstadoTurno
from clinican.servicios import agenda, clientes, configuracion, consultas, notificaciones
from clinican.ui import formato as fmt
from clinican.ui.puentes.base import Pantalla, propiedad

CANALES = {"whatsapp": "WhatsApp", "archivo": "Archivo de texto (recordatorios.txt)", "consola": "Consola"}


class PantallaRecordatorios(Pantalla):
    cambioRecordatorios = Signal()

    def __init__(self, app):
        super().__init__(app)
        self._canal = ""
        self._metricas: list[dict] = []
        self._fallidas: list[dict] = []
        self._proximas: list[dict] = []
        self._explicacion = ""

    canal = propiedad(str, "canal", cambioRecordatorios)
    metricas = propiedad("QVariantList", "metricas", cambioRecordatorios)
    fallidas = propiedad("QVariantList", "fallidas", cambioRecordatorios)
    proximas = propiedad("QVariantList", "proximas", cambioRecordatorios)
    explicacion = propiedad(str, "explicacion", cambioRecordatorios)

    def refrescar(self) -> None:
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

        canal = CANALES.get(cfg.canal_notificaciones, cfg.canal_notificaciones)
        conteo = bandeja.conteo
        metricas = [
            ("Por enviar", conteo.get(EN.PENDIENTE, 0), "", False),
            ("Enviados", conteo.get(EN.ENVIADA, 0), "en total", False),
            ("Fallidos", conteo.get(EN.FALLIDA, 0), "tras 3 reintentos", conteo.get(EN.FALLIDA, 0) > 0),
            ("Descartados", conteo.get(EN.DESCARTADA, 0), "turno cancelado o movido", False),
        ]
        fallidas = []
        for n in bandeja.fallidas_recientes:
            t, p, m = datos[n.id]
            fallidas.append({
                "id": n.id, "propietarioId": p.id,
                "titulo": f"{m.nombre} · {p.nombre} · {fmt.celular(p.telefono)}",
                "detalle": f"Turno {fmt.momento(t.inicio, hoy)} · {n.intentos} intentos",
                "error": f"Respuesta del canal: {n.ultimo_error}" if n.ultimo_error else "",
                "vigente": t.estado is EstadoTurno.CONFIRMADO and t.inicio > self.ctx.ahora(),
            })
        proximas = []
        for n in bandeja.proximas:
            t, p, m = datos[n.id]
            proximas.append([fmt.momento(n.programada_para, hoy), f"{m.nombre} · {p.nombre}",
                             fmt.momento(t.inicio, hoy), str(n.intentos) if n.intentos else "—"])
        ejemplo = notificaciones.texto_recordatorio("Carlos", "Daisy", self.ctx.ahora())
        self.poner(
            canal=f"Canal: {canal} · se revisa cada minuto",
            metricas=[{"titulo": a, "valor": str(b), "nota": c, "alerta": d} for a, b, c, d in metricas],
            fallidas=fallidas, proximas=proximas,
            explicacion=f"Cada recordatorio sale {cfg.horas_antes_recordatorio} horas antes (o de inmediato si falta "
                        f"menos), y solo si el turno sigue confirmado. Ejemplo: «{ejemplo}»")

    @Slot(int)
    def reintentar(self, notificacion_id: int) -> None:
        self.ejecutar(lambda con: notificaciones.reintentar(con, notificacion_id, ahora=self.ctx.ahora()),
                      "Recordatorio en cola: sale en el próximo minuto.")

    @Slot(int)
    def corregir(self, propietario_id: int) -> None:
        from clinican.ui.puentes.clientes import DialogoCliente

        with self.ctx.con() as con:
            p = clientes.obtener_propietario(con, propietario_id)

        def listo(resultado) -> None:
            if resultado:
                self.avisar("Celular guardado. Ahora puedes reintentar el envío.")
            self.refrescar()

        self.app.abrir(DialogoCliente(self.ctx, p), listo)
