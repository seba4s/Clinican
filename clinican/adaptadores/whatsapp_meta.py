"""Canal WhatsApp con la API oficial de Meta (WhatsApp Cloud API).

Envía el recordatorio como **plantilla aprobada** (obligatorio fuera de la ventana de
24 horas). La cuenta se toma de variables de entorno, nunca del código:
``CLINICAN_WHATSAPP_TOKEN`` y ``CLINICAN_WHATSAPP_NUMERO_ID``.

Sin cuenta configurada no envía nada: cada intento falla con un motivo claro y el
mensaje queda en la bandeja para reintentarse (la agenda no se entera).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from clinican.dominio.notificaciones import Mensaje
from clinican.servicios.notificaciones import ErrorEnvio

URL_API = "https://graph.facebook.com/v21.0/{numero_id}/messages"


class NotificadorWhatsApp:
    nombre = "WHATSAPP"

    def __init__(self, token: str, numero_id: str, idioma: str = "es", tiempo_maximo: float = 15.0):
        self.token = token
        self.numero_id = numero_id
        self.idioma = idioma
        self.tiempo_maximo = tiempo_maximo

    def cuerpo(self, mensaje: Mensaje) -> dict:
        """El JSON que pide la API para un mensaje con plantilla."""
        return {
            "messaging_product": "whatsapp",
            "to": mensaje.destino,
            "type": "template",
            "template": {
                "name": mensaje.plantilla,
                "language": {"code": self.idioma},
                "components": [{"type": "body",
                                "parameters": [{"type": "text", "text": p} for p in mensaje.parametros]}],
            },
        }

    def enviar(self, mensaje: Mensaje) -> None:
        if not self.token or not self.numero_id:
            raise ErrorEnvio("La cuenta de WhatsApp no está configurada (faltan CLINICAN_WHATSAPP_TOKEN "
                             "y CLINICAN_WHATSAPP_NUMERO_ID).")
        peticion = urllib.request.Request(
            URL_API.format(numero_id=self.numero_id), data=json.dumps(self.cuerpo(mensaje)).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(peticion, timeout=self.tiempo_maximo) as respuesta:
                if respuesta.status >= 300:
                    raise ErrorEnvio(f"La API de WhatsApp respondió {respuesta.status}.")
        except urllib.error.HTTPError as e:
            detalle = e.read().decode("utf-8", "replace")[:300]
            raise ErrorEnvio(f"La API de WhatsApp rechazó el mensaje ({e.code}): {detalle}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ErrorEnvio(f"Sin conexión con WhatsApp: {e}") from None
