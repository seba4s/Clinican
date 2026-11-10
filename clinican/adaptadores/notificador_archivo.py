"""Canales sin internet: escriben el mensaje en un archivo o en la consola.

Sirven para operar sin cuenta de WhatsApp (el personal puede leer el archivo y avisar
por su cuenta), para las pruebas y para la demostración.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from clinican.dominio.notificaciones import Mensaje
from clinican.servicios.notificaciones import ErrorEnvio


class NotificadorArchivo:
    nombre = "ARCHIVO"

    def __init__(self, ruta: Path):
        self.ruta = Path(ruta)

    def enviar(self, mensaje: Mensaje) -> None:
        linea = f"{datetime.now():%Y-%m-%d %H:%M:%S}\t+{mensaje.destino}\t{mensaje.texto}\n"
        try:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            with self.ruta.open("a", encoding="utf-8") as archivo:
                archivo.write(linea)
        except OSError as e:
            raise ErrorEnvio(f"No se pudo escribir en {self.ruta}: {e}") from None


class NotificadorConsola:
    nombre = "CONSOLA"

    def __init__(self, escribir=print):
        self._escribir = escribir

    def enviar(self, mensaje: Mensaje) -> None:
        self._escribir(f"  [consola] para +{mensaje.destino}: {mensaje.texto}")
