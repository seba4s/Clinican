"""Adaptadores: implementaciones concretas de los puertos de la capa de servicios.

Solo dependen de ``clinican.servicios`` (el puerto) y de ``clinican.dominio``. Nadie de
las capas internas los importa: el arranque (``main.py``) elige uno y se lo pasa.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from clinican.adaptadores.notificador_archivo import NotificadorArchivo, NotificadorConsola
from clinican.adaptadores.whatsapp_meta import NotificadorWhatsApp
from clinican.servicios.notificaciones import Notificador

log = logging.getLogger(__name__)

__all__ = ["NotificadorArchivo", "NotificadorConsola", "NotificadorWhatsApp", "notificador_para"]


def notificador_para(canal: str, carpeta_datos: Path) -> Notificador:
    """El canal elegido en Configuración. WhatsApp toma la cuenta de variables de entorno
    (nunca del código ni de la base de datos)."""
    if canal == "WHATSAPP":
        return NotificadorWhatsApp(
            token=os.environ.get("CLINICAN_WHATSAPP_TOKEN", ""),
            numero_id=os.environ.get("CLINICAN_WHATSAPP_NUMERO_ID", ""),
        )
    if canal != "ARCHIVO":
        log.warning("Canal de notificaciones desconocido «%s»; se usa ARCHIVO.", canal)
    return NotificadorArchivo(Path(carpeta_datos) / "recordatorios.txt")
