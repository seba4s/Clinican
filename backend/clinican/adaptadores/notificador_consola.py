"""Notificador que imprime el recordatorio en la consola (útil para pruebas y demo)."""

from __future__ import annotations

import sys
from typing import TextIO

from clinican.adaptadores.notificador_archivo import linea
from clinican.servicios.notificaciones import ErrorEnvio, Mensaje


class NotificadorConsola:
    def __init__(self, salida: TextIO | None = None) -> None:
        self._salida = salida

    def enviar(self, mensaje: Mensaje) -> None:
        salida = self._salida or sys.stdout
        try:
            print(f"[recordatorio] {linea(mensaje)}", file=salida, flush=True)
        except (OSError, ValueError) as error:
            raise ErrorEnvio(f"No se pudo escribir en la consola: {error}") from error
