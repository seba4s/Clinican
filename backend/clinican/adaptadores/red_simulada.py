"""Corte de red simulado para la demostración (la red solo se toca en adaptadores/)."""

from __future__ import annotations

import socket
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def sin_red() -> Iterator[None]:
    """Hace fallar toda conexión de red del proceso mientras dura el bloque."""
    originales = (socket.socket, socket.create_connection, socket.getaddrinfo)

    def cortada(*args, **kwargs):
        raise OSError("sin red (simulado)")

    socket.socket = socket.create_connection = socket.getaddrinfo = cortada
    try:
        yield
    finally:
        socket.socket, socket.create_connection, socket.getaddrinfo = originales
