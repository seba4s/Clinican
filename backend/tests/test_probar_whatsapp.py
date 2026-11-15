"""Herramienta para probar el envío real por WhatsApp sin crear turnos."""

import io
import json
import urllib.error

import probar_whatsapp

ENTORNO = {"CLINICAN_WHATSAPP_TOKEN": "secreto-123", "CLINICAN_WHATSAPP_NUMERO_ID": "555"}


class Respuesta:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return b'{"messages": [{"id": "wamid.XYZ"}]}'


def test_envia_un_recordatorio_de_ejemplo():
    enviados, salida = [], io.StringIO()
    codigo = probar_whatsapp.main(["300 123 4567", "--mascota", "Roma"], entorno=ENTORNO,
                                  abrir_url=lambda r, timeout: enviados.append(r) or Respuesta(), salida=salida)
    assert codigo == 0
    cuerpo = json.loads(enviados[0].data)
    assert cuerpo["to"] == "573001234567"
    dia, mascota, hora = [p["text"] for p in cuerpo["template"]["components"][0]["parameters"]]
    assert dia.startswith("el día de mañana, ") and mascota == "Roma" and hora == "9:00 am"
    texto = salida.getvalue()
    assert "wamid.XYZ" in texto and "Estimado cliente" in texto and "secreto-123" not in texto


def test_sin_configuracion_explica_que_falta():
    salida = io.StringIO()
    assert probar_whatsapp.main(["3001234567"], entorno={}, salida=salida) == 1
    assert "configurar_whatsapp.ps1" in salida.getvalue()


def test_error_de_meta_se_muestra_en_espanol():
    def abrir(r, timeout):
        cuerpo = json.dumps({"error": {"message": "x", "code": 131030}}).encode()
        raise urllib.error.HTTPError("u", 400, "x", {}, io.BytesIO(cuerpo))

    salida = io.StringIO()
    assert probar_whatsapp.main(["3001234567"], entorno=ENTORNO, abrir_url=abrir, salida=salida) == 1
    assert "lista de destinatarios" in salida.getvalue()
