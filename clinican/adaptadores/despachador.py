"""Despachador periódico de la bandeja de salida, en un hilo aparte.

Abre su **propia** conexión a la base (SQLite no comparte una conexión entre hilos) y
cada cierto tiempo entrega los recordatorios pendientes con el canal recibido. Así la
espera a la red nunca congela las pantallas ni la agenda (drivers D1 y D3).
"""

from __future__ import annotations

import logging
import threading
from typing import Callable

from clinican.servicios import notificaciones
from clinican.servicios.notificaciones import Notificador

log = logging.getLogger(__name__)


class Despachador:
    def __init__(self, abrir_conexion: Callable, notificador: Notificador, intervalo_segundos: float = 60.0):
        self._abrir = abrir_conexion
        self.notificador = notificador
        self.intervalo = intervalo_segundos
        self._parar = threading.Event()
        self._hilo: threading.Thread | None = None

    def iniciar(self) -> None:
        self._hilo = threading.Thread(target=self._bucle, name="despachador-notificaciones", daemon=True)
        self._hilo.start()

    def detener(self, esperar: float = 5.0) -> None:
        self._parar.set()
        if self._hilo is not None:
            self._hilo.join(esperar)

    def _bucle(self) -> None:
        conn = self._abrir()
        try:
            while not self._parar.is_set():
                try:
                    r = notificaciones.despachar(conn, self.notificador)
                    if r.enviados or r.fallidos:
                        log.info("Recordatorios: %d enviados, %d fallidos, %d descartados",
                                 len(r.enviados), len(r.fallidos), len(r.descartados))
                except Exception:
                    log.exception("Falló el despacho de recordatorios")
                self._parar.wait(self.intervalo)
        finally:
            conn.close()
