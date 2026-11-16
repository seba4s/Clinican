"""Notificador por WhatsApp Business (Graph API de Meta) con una plantilla aprobada.

Se configura con variables de entorno:

- ``CLINICAN_WHATSAPP_TOKEN``: token de acceso (obligatorio).
- ``CLINICAN_WHATSAPP_NUMERO_ID``: id del número emisor (obligatorio).
- ``CLINICAN_WHATSAPP_PLANTILLA``: nombre de la plantilla aprobada
  (por defecto ``recordatorio_turno``).
- ``CLINICAN_WHATSAPP_IDIOMA``: código de idioma de la plantilla (por defecto ``es``).
- ``CLINICAN_WHATSAPP_VERSION``: versión de la Graph API (por defecto ``v25.0``).

Si falta el token o el número, el notificador queda inactivo y cada envío lanza
``ErrorEnvio`` (la bandeja lo reintenta y luego lo marca FALLIDA).

La plantilla recibe 3 parámetros de cuerpo, en este orden: el día en palabras
(«el día de mañana, jueves 8 de octubre (08/10/2026)»), el nombre de la mascota
y la hora («9:00 am»). Los errores de Meta se traducen a español para la
pantalla Recordatorios. El token nunca aparece en los mensajes de error.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Callable, Mapping

from clinican.servicios.notificaciones import ErrorEnvio, Mensaje

VERSION_API = "v25.0"
URL_BASE = "https://graph.facebook.com"
TIEMPO_ESPERA = 15

ERRORES_META = {
    190: "El token de WhatsApp venció o no es válido. Genera uno nuevo y guárdalo con configurar_whatsapp.ps1",
    131030: "Ese celular no está en la lista de destinatarios permitidos del número de prueba de Meta",
    132001: "La plantilla no existe o aún no está aprobada en ese idioma (revisa WhatsApp Manager)",
    132000: "La cantidad de datos del mensaje no coincide con la plantilla aprobada",
    131026: "Ese celular no puede recibir mensajes de WhatsApp",
    130429: "Meta limitó los envíos por ahora; se reintentará",
    131056: "Meta limitó los envíos por ahora; se reintentará",
    80007: "Meta limitó los envíos por ahora; se reintentará",
    131042: "Hay un problema con el método de pago de la cuenta de WhatsApp",
    133010: "El número emisor no está registrado en la API de WhatsApp",
}


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
        self._version = entorno.get("CLINICAN_WHATSAPP_VERSION", "").strip() or version_api

    @property
    def activo(self) -> bool:
        return bool(self._token and self._numero_id)

    @property
    def url(self) -> str:
        return f"{URL_BASE}/{self._version}/{self._numero_id}/messages"

    def cuerpo(self, mensaje: Mensaje) -> dict:
        parametros = list(mensaje.parametros)
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

    def enviar(self, mensaje: Mensaje) -> str | None:
        """Envía la plantilla; devuelve el id del mensaje que asigna Meta (si lo informa)."""
        if not self.activo:
            raise ErrorEnvio(
                "WhatsApp inactivo: faltan CLINICAN_WHATSAPP_TOKEN o CLINICAN_WHATSAPP_NUMERO_ID"
            )
        if len(normalizar_telefono(mensaje.telefono)) < 8:
            raise ErrorEnvio(f"Teléfono inválido para WhatsApp: {mensaje.telefono!r}")
        if not mensaje.parametros:
            raise ErrorEnvio("El recordatorio no trae los parámetros de la plantilla")
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
                return _id_mensaje(respuesta)
        except urllib.error.HTTPError as error:
            raise ErrorEnvio(f"WhatsApp respondió HTTP {error.code}: {_detalle_error(error)}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            razon = getattr(error, "reason", error)
            raise ErrorEnvio(f"No se pudo conectar con WhatsApp: {razon}") from None


def _id_mensaje(respuesta) -> str | None:
    """El ``wamid`` de la respuesta exitosa, o None si no se puede leer."""
    try:
        datos = json.loads(respuesta.read().decode("utf-8"))
        return str(datos["messages"][0]["id"])
    except Exception:
        return None


def _detalle_error(error: urllib.error.HTTPError) -> str:
    """Explicación en español del error de Meta (o su texto, si no se conoce)."""
    try:
        crudo = error.read().decode("utf-8", "replace")
    except Exception:
        return ""
    try:
        datos = json.loads(crudo)["error"]
        codigo = datos.get("code")
        texto = ERRORES_META.get(codigo) or datos.get("message") or "error desconocido"
        return f"{texto} (código {codigo})"
    except Exception:
        return crudo[:300]
