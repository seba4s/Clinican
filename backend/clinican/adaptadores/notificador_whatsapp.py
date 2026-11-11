"""Notificador por WhatsApp Business (Graph API de Meta) con una plantilla aprobada.

Se configura con variables de entorno:

- ``CLINICAN_WHATSAPP_TOKEN``: token de acceso (obligatorio).
- ``CLINICAN_WHATSAPP_NUMERO_ID``: id del número emisor (obligatorio).
- ``CLINICAN_WHATSAPP_PLANTILLA``: nombre de la plantilla aprobada
  (por defecto ``recordatorio_turno``, PROVISIONAL).
- ``CLINICAN_WHATSAPP_IDIOMA``: código de idioma de la plantilla (por defecto ``es``).

Si falta el token o el número, el notificador queda inactivo y cada envío lanza
``ErrorEnvio`` (la bandeja lo reintenta y luego lo marca FALLIDA).

La plantilla recibe 4 parámetros de cuerpo, en este orden: nombre del
propietario, nombre de la mascota, fecha (dd/mm/aaaa) y hora (HH:MM).
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Callable, Mapping

from clinican.servicios.notificaciones import ErrorEnvio, Mensaje

VERSION_API = "v21.0"
URL_BASE = "https://graph.facebook.com"
TIEMPO_ESPERA = 15


def normalizar_telefono(telefono: str) -> str:
    """Deja solo dígitos; a un celular colombiano de 10 dígitos le antepone 57."""
    digitos = re.sub(r"\D", "", telefono or "")
    if len(digitos) == 10 and digitos.startswith("3"):
        digitos = "57" + digitos
    return digitos


class NotificadorWhatsApp:
    def __init__(
        self,
        entorno: Mapping[str, str] | None = None,
        abrir_url: Callable | None = None,
        version_api: str = VERSION_API,
    ) -> None:
        entorno = os.environ if entorno is None else entorno
        self._token = entorno.get("CLINICAN_WHATSAPP_TOKEN", "").strip()
        self._numero_id = entorno.get("CLINICAN_WHATSAPP_NUMERO_ID", "").strip()
        self.plantilla = entorno.get("CLINICAN_WHATSAPP_PLANTILLA", "").strip() or "recordatorio_turno"
        self.idioma = entorno.get("CLINICAN_WHATSAPP_IDIOMA", "").strip() or "es"
        self._abrir_url = abrir_url
        self._version = version_api

    @property
    def activo(self) -> bool:
        return bool(self._token and self._numero_id)

    @property
    def url(self) -> str:
        return f"{URL_BASE}/{self._version}/{self._numero_id}/messages"

    def cuerpo(self, mensaje: Mensaje) -> dict:
        parametros = [
            mensaje.propietario,
            mensaje.mascota,
            mensaje.inicio.strftime("%d/%m/%Y"),
            mensaje.inicio.strftime("%H:%M"),
        ]
        return {
            "messaging_product": "whatsapp",
            "to": normalizar_telefono(mensaje.telefono),
            "type": "template",
            "template": {
                "name": self.plantilla,
                "language": {"code": self.idioma},
                "components": [
                    {"type": "body", "parameters": [{"type": "text", "text": p} for p in parametros]}
                ],
            },
        }

    def enviar(self, mensaje: Mensaje) -> None:
        if not self.activo:
            raise ErrorEnvio(
                "WhatsApp inactivo: faltan CLINICAN_WHATSAPP_TOKEN o CLINICAN_WHATSAPP_NUMERO_ID"
            )
        if len(normalizar_telefono(mensaje.telefono)) < 8:
            raise ErrorEnvio(f"Teléfono inválido para WhatsApp: {mensaje.telefono!r}")
        solicitud = urllib.request.Request(
            self.url,
            data=json.dumps(self.cuerpo(mensaje)).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        abrir = self._abrir_url or urllib.request.urlopen
        try:
            with abrir(solicitud, timeout=TIEMPO_ESPERA) as respuesta:
                estado = getattr(respuesta, "status", 200)
                if estado >= 300:
                    raise ErrorEnvio(f"WhatsApp respondió HTTP {estado}")
        except urllib.error.HTTPError as error:
            detalle = ""
            try:
                detalle = error.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            raise ErrorEnvio(f"WhatsApp respondió HTTP {error.code}: {detalle}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            razon = getattr(error, "reason", error)
            raise ErrorEnvio(f"No se pudo conectar con WhatsApp: {razon}") from None
