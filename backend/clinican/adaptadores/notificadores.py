"""Registro de canales de notificación.

Agregar un canal nuevo = escribir su clase (con ``enviar(mensaje)``) y
registrarla con ``registrar("nombre", fabrica)``. La agenda y el despachador no
cambian: solo conocen el puerto ``Notificador``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from clinican.adaptadores.notificador_archivo import NotificadorArchivo
from clinican.adaptadores.notificador_consola import NotificadorConsola
from clinican.adaptadores.notificador_whatsapp import NotificadorWhatsApp
from clinican.dominio.errores import DatoInvalido
from clinican.servicios.notificaciones import Notificador

Fabrica = Callable[[Path], Notificador]

_REGISTRO: dict[str, Fabrica] = {}


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
