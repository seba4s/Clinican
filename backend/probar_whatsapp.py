"""Prueba real del canal WhatsApp: envía un recordatorio de ejemplo a un celular.

No crea turnos ni toca la base. Sirve para confirmar que el token, el id del
número y la plantilla aprobada funcionan antes de activar el canal en Ajustes.

    python probar_whatsapp.py 3001234567
    python probar_whatsapp.py 3001234567 --mascota Roma

El ejemplo es un turno para mañana a las 9:00 am. Con el número de prueba de
Meta, el celular debe estar en su lista de destinatarios permitidos.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from typing import Callable, Mapping, TextIO

from clinican.adaptadores.notificador_whatsapp import NotificadorWhatsApp, normalizar_telefono
from clinican.dominio.agenda import ZONA
from clinican.servicios.notificaciones import ErrorEnvio, Mensaje, parametros_recordatorio, texto_recordatorio


def main(
    argv: list[str] | None = None,
    entorno: Mapping[str, str] | None = None,
    abrir_url: Callable | None = None,
    salida: TextIO | None = None,
) -> int:
    salida = salida or sys.stdout
    opciones = argparse.ArgumentParser(description="Envía un recordatorio de prueba por WhatsApp.")
    opciones.add_argument("celular", help="Celular de 10 dígitos que recibirá la prueba")
    opciones.add_argument("--mascota", default="Roma", help="Nombre de mascota del ejemplo")
    args = opciones.parse_args(argv)

    whatsapp = NotificadorWhatsApp(entorno=entorno, abrir_url=abrir_url)
    if not whatsapp.activo:
        print("Falta configurar WhatsApp: ejecuta configurar_whatsapp.ps1 y abre una consola nueva.", file=salida)
        return 1

    ahora = datetime.now(ZONA)
    inicio = (ahora + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    mensaje = Mensaje(
        notificacion_id=0, turno_id=0, tipo="prueba", telefono=args.celular, propietario="Prueba",
        mascota=args.mascota, inicio=inicio,
        texto=texto_recordatorio(args.mascota, inicio, ahora),
        parametros=parametros_recordatorio(args.mascota, inicio, ahora),
    )
    print(f"Enviando a +{normalizar_telefono(args.celular)} con la plantilla «{whatsapp.plantilla}»:", file=salida)
    print(f"  {mensaje.texto}", file=salida)
    try:
        id_mensaje = whatsapp.enviar(mensaje)
    except ErrorEnvio as error:
        print(f"No se pudo enviar. {error}", file=salida)
        return 1
    print(f"Meta aceptó el mensaje (id {id_mensaje or 'sin id'}). Revisa el WhatsApp de ese celular.", file=salida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
