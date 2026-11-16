"""Canales de notificación y su registro.

Agregar un canal nuevo = escribir su clase (con ``enviar(mensaje)``) y
registrarla con ``registrar("nombre", fabrica)``. La agenda y el despachador no
cambian: solo conocen el puerto ``Notificador``.
"""

from __future__ import annotations

import socket
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, TextIO

from clinican.adaptadores.notificador_whatsapp import NotificadorWhatsApp
from clinican.dominio.errores import DatoInvalido
from clinican.servicios.notificaciones import ErrorEnvio, Mensaje, Notificador

NOMBRE_ARCHIVO = "recordatorios.txt"

Fabrica = Callable[[Path], Notificador]

_REGISTRO: dict[str, Fabrica] = {}


def linea(mensaje: Mensaje) -> str:
    return (
        f"{mensaje.inicio.strftime('%Y-%m-%d %H:%M')} | turno {mensaje.turno_id} | "
        f"{mensaje.telefono or 'sin teléfono'} | {mensaje.texto}"
    ).replace("\n", " ")


class NotificadorArchivo:
    """Escribe una línea por recordatorio en un archivo de texto."""

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


class NotificadorConsola:
    """Imprime el recordatorio en la consola (útil para pruebas y demo)."""

    def __init__(self, salida: TextIO | None = None) -> None:
        self._salida = salida

    def enviar(self, mensaje: Mensaje) -> None:
        salida = self._salida or sys.stdout
        try:
            print(f"[recordatorio] {linea(mensaje)}", file=salida, flush=True)
        except (OSError, ValueError) as error:
            raise ErrorEnvio(f"No se pudo escribir en la consola: {error}") from error


@contextmanager
def sin_red() -> Iterator[None]:
    """Corte de red simulado para la demostración: hace fallar toda conexión mientras dura el bloque."""
    originales = (socket.socket, socket.create_connection, socket.getaddrinfo)

    def cortada(*args, **kwargs):
        raise OSError("sin red (simulado)")

    socket.socket = socket.create_connection = socket.getaddrinfo = cortada
    try:
        yield
    finally:
        socket.socket, socket.create_connection, socket.getaddrinfo = originales


def registrar(canal: str, fabrica: Fabrica) -> None:
    _REGISTRO[canal.strip().lower()] = fabrica


def canales() -> list[str]:
    return sorted(_REGISTRO)


def notificador_para(canal: str, carpeta: str | Path) -> Notificador:
    """Notificador del canal configurado en ``canal_notificaciones``."""
    try:
        fabrica = _REGISTRO[canal.strip().lower()]
    except (KeyError, AttributeError):
        raise DatoInvalido(
            f"Canal de notificaciones desconocido: {canal!r}. Disponibles: {', '.join(canales())}"
        ) from None
    return fabrica(Path(carpeta))


registrar("archivo", lambda carpeta: NotificadorArchivo(carpeta))
registrar("consola", lambda carpeta: NotificadorConsola())
registrar("whatsapp", lambda carpeta: NotificadorWhatsApp())
