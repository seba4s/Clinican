"""Notificador que escribe una línea por recordatorio en un archivo de texto."""

from __future__ import annotations

import threading
from pathlib import Path

from clinican.servicios.notificaciones import ErrorEnvio, Mensaje

NOMBRE_ARCHIVO = "recordatorios.txt"


def linea(mensaje: Mensaje) -> str:
    return (
        f"{mensaje.inicio.strftime('%Y-%m-%d %H:%M')} | turno {mensaje.turno_id} | "
        f"{mensaje.telefono or 'sin teléfono'} | {mensaje.texto}"
    ).replace("\n", " ")


class NotificadorArchivo:
    def __init__(self, carpeta: str | Path, nombre: str = NOMBRE_ARCHIVO) -> None:
        self.ruta = Path(carpeta) / nombre
        self._candado = threading.Lock()

    def enviar(self, mensaje: Mensaje) -> None:
        try:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            with self._candado, self.ruta.open("a", encoding="utf-8", newline="\n") as archivo:
                archivo.write(linea(mensaje) + "\n")
        except OSError as error:
            raise ErrorEnvio(f"No se pudo escribir en {self.ruta}: {error}") from error
