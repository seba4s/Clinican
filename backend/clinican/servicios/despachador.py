"""Despachador de la bandeja de salida.

Usa su propia conexión (abre una por ciclo) y un ``Notificador`` inyectado.
En cada ciclo:

1. Toma las notificaciones pendientes cuya hora ya llegó.
2. Justo antes de enviar, en una transacción, verifica que el turno siga
   CONFIRMADO y no haya empezado; si no, la DESCARTA con motivo. Si sigue
   válida, cuenta el intento y la "reserva" corriendo su hora al siguiente
   reintento (así otro despachador no la toma mientras se envía, y si el
   programa se cae a mitad, se reintenta sola).
3. Envía fuera de la transacción. Si falla, reintenta a los 1, 5 y 15 minutos;
   tras el tercer reintento fallido queda FALLIDA. Guarda intentos y último error.
4. Purga los registros cerrados de más de 90 días.

El reloj se inyecta: ``procesar_una_vez(ahora)`` o ``reloj()`` en el hilo.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from clinican.datos import repo_agenda, repo_clientes, repo_notificaciones
from clinican.datos.conexion import abrir, transaccion
from clinican.dominio.agenda import ZONA
from clinican.dominio.entidades import EstadoNotificacion as EN
from clinican.dominio.estados import EstadoTurno
from clinican.dominio.notificaciones import ESPERAS_REINTENTO, espera_tras_fallo, limite_retencion
from clinican.servicios.auditoria import auditar
from clinican.servicios.notificaciones import ErrorEnvio, Mensaje, Notificador, texto_recordatorio

registro = logging.getLogger(__name__)


@dataclass
class ResumenDespacho:
    enviadas: int = 0
    descartadas: int = 0
    reintentos: int = 0
    fallidas: int = 0
    purgadas: int = 0


class Despachador:
    def __init__(
        self,
        ruta_db: str | Path,
        notificador: Notificador,
        reloj: Callable[[], datetime] | None = None,
        intervalo_segundos: float = 60,
        lote: int = 100,
    ) -> None:
        self._ruta = ruta_db
        self._notificador = notificador
        self._reloj = reloj
        self._intervalo = intervalo_segundos
        self._lote = lote
        self._parar = threading.Event()
        self._hilo: threading.Thread | None = None

    # ------------------------------------------------------------------ ciclo

    def procesar_una_vez(self, ahora: datetime) -> ResumenDespacho:
        if ahora.tzinfo is None or ahora.utcoffset() is None:
            raise ValueError("ahora debe tener zona horaria")
        resumen = ResumenDespacho()
        con = abrir(self._ruta)
        try:
            for pendiente in repo_notificaciones.pendientes_hasta(con, ahora, self._lote):
                mensaje = self._reservar(con, pendiente.id, ahora, resumen)
                if mensaje is None:
                    continue
                error = None
                try:
                    self._notificador.enviar(mensaje)
                except ErrorEnvio as e:
                    error = str(e) or type(e).__name__
                except Exception as e:  # un fallo del canal no debe tumbar el despachador
                    error = f"Error inesperado: {e!r}"
                self._registrar_resultado(con, pendiente.id, error, ahora, resumen)
            with transaccion(con):
                resumen.purgadas = repo_notificaciones.purgar_cerradas(con, limite_retencion(ahora))
                if resumen.purgadas:
                    auditar(con, ahora, "purgar", "notificacion", None, cantidad=resumen.purgadas)
        finally:
            con.close()
        return resumen

    def _reservar(self, con, notificacion_id: int, ahora: datetime, resumen: ResumenDespacho) -> Mensaje | None:
        with transaccion(con):
            n = repo_notificaciones.obtener(con, notificacion_id)
            if n is None or n.estado is not EN.PENDIENTE or n.programada_para > ahora:
                return None  # otro despachador ya la tomó
            turno = repo_agenda.obtener_turno(con, n.turno_id)
            motivo = None
            if turno.estado is not EstadoTurno.CONFIRMADO:
                motivo = f"El turno ya no está confirmado ({turno.estado.value})"
            elif turno.inicio <= ahora:
                motivo = "El turno ya empezó"
            if motivo is not None:
                repo_notificaciones.actualizar_notificacion(
                    con, n.id, estado=EN.DESCARTADA, motivo_descarte=motivo, cerrada_en=ahora
                )
                auditar(con, ahora, "descartar", "notificacion", n.id, motivo=motivo)
                resumen.descartadas += 1
                return None
            intentos = n.intentos + 1
            plazo = espera_tras_fallo(intentos) or ESPERAS_REINTENTO[-1]
            repo_notificaciones.actualizar_notificacion(
                con, n.id, intentos=intentos, programada_para=ahora + plazo
            )
            propietario = repo_clientes.obtener_propietario(con, turno.propietario_id)
            mascota = repo_clientes.obtener_mascota(con, turno.mascota_id)
        return Mensaje(
            notificacion_id=n.id,
            turno_id=turno.id,
            tipo=n.tipo,
            telefono=propietario.telefono,
            propietario=propietario.nombre,
            mascota=mascota.nombre,
            inicio=turno.inicio.astimezone(ZONA),
            texto=texto_recordatorio(propietario.nombre, mascota.nombre, turno.inicio),
        )

    def _registrar_resultado(
        self, con, notificacion_id: int, error: str | None, ahora: datetime, resumen: ResumenDespacho
    ) -> None:
        with transaccion(con):
            n = repo_notificaciones.obtener(con, notificacion_id)
            if error is None:
                repo_notificaciones.actualizar_notificacion(
                    con, n.id, estado=EN.ENVIADA, enviada_en=ahora, cerrada_en=ahora
                )
                auditar(con, ahora, "enviar", "notificacion", n.id, intentos=n.intentos)
                resumen.enviadas += 1
                return
            espera = espera_tras_fallo(n.intentos)
            if espera is None:
                repo_notificaciones.actualizar_notificacion(
                    con, n.id, estado=EN.FALLIDA, ultimo_error=error, cerrada_en=ahora
                )
                auditar(con, ahora, "fallar", "notificacion", n.id, intentos=n.intentos, error=error)
                resumen.fallidas += 1
            else:
                repo_notificaciones.actualizar_notificacion(
                    con, n.id, ultimo_error=error, programada_para=ahora + espera
                )
                resumen.reintentos += 1

    # ------------------------------------------------------------------ hilo

    def iniciar(self) -> threading.Thread:
        """Arranca el despachador en un hilo que procesa cada ``intervalo_segundos``."""
        if self._reloj is None:
            raise ValueError("Para correr en un hilo, el despachador necesita un reloj")
        if self._hilo is not None and self._hilo.is_alive():
            return self._hilo
        self._parar.clear()
        self._hilo = threading.Thread(target=self._bucle, name="despachador", daemon=True)
        self._hilo.start()
        return self._hilo

    def detener(self, espera_segundos: float = 10) -> None:
        self._parar.set()
        if self._hilo is not None:
            self._hilo.join(espera_segundos)

    @property
    def corriendo(self) -> bool:
        return self._hilo is not None and self._hilo.is_alive()

    def _bucle(self) -> None:
        while not self._parar.is_set():
            try:
                self.procesar_una_vez(self._reloj())
            except Exception:  # se registra y se sigue en el próximo ciclo
                registro.exception("Falló un ciclo del despachador de notificaciones")
            self._parar.wait(self._intervalo)
