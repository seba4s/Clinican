import io
import json
import urllib.error
from pathlib import Path

import pytest

from clinican.adaptadores import notificador_whatsapp, notificadores
from clinican.adaptadores.notificadores import NotificadorArchivo, NotificadorConsola
from clinican.adaptadores.notificador_whatsapp import NotificadorWhatsApp, normalizar_telefono
from clinican.dominio.errores import DatoInvalido
from clinican.servicios import agenda
from clinican.servicios.despachador import Despachador
from clinican.servicios.notificaciones import ErrorEnvio, Mensaje, Notificador
from escenario import AHORA, a_las

MENSAJE = Mensaje(
    notificacion_id=1, turno_id=7, tipo="recordatorio", telefono="300 123 4567",
    propietario="Ana", mascota="Toby", inicio=a_las(10),
    texto="Estimado cliente, le recordamos que hoy, lunes 9 de noviembre (09/11/2026), tiene un turno...",
    parametros=("hoy, lunes 9 de noviembre (09/11/2026)", "Toby", "10:00 am"),
)
ENTORNO = {"CLINICAN_WHATSAPP_TOKEN": "secreto-123", "CLINICAN_WHATSAPP_NUMERO_ID": "555"}


def test_archivo_una_linea_por_recordatorio(tmp_path):
    n = NotificadorArchivo(tmp_path / "salida")
    n.enviar(MENSAJE)
    n.enviar(MENSAJE)
    lineas = (tmp_path / "salida" / "recordatorios.txt").read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 2
    assert lineas[0] == (
        "2026-11-09 10:00 | turno 7 | 300 123 4567 | " + MENSAJE.texto
    )


def test_archivo_error_de_escritura(tmp_path):
    bloqueo = tmp_path / "archivo_no_carpeta"
    bloqueo.write_text("x")
    with pytest.raises(ErrorEnvio):
        NotificadorArchivo(bloqueo).enviar(MENSAJE)


def test_consola():
    salida = io.StringIO()
    NotificadorConsola(salida).enviar(MENSAJE)
    assert salida.getvalue().startswith("[recordatorio] 2026-11-09 10:00 | turno 7")


class RespuestaFalsa:
    def __init__(self, status=200, cuerpo=b'{"messages": [{"id": "wamid.ABC"}]}'):
        self.status = status
        self._cuerpo = cuerpo

    def read(self):
        return self._cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_whatsapp_inactivo_sin_variables():
    n = NotificadorWhatsApp(entorno={})
    assert not n.activo
    with pytest.raises(ErrorEnvio, match="CLINICAN_WHATSAPP_TOKEN"):
        n.enviar(MENSAJE)
    assert not NotificadorWhatsApp(entorno={"CLINICAN_WHATSAPP_TOKEN": "x"}).activo


def test_whatsapp_envia_plantilla_por_https():
    solicitudes = []

    def abrir(solicitud, timeout):
        solicitudes.append((solicitud, timeout))
        return RespuestaFalsa(200)

    assert NotificadorWhatsApp(entorno=ENTORNO, abrir_url=abrir).enviar(MENSAJE) == "wamid.ABC"
    [(req, timeout)] = solicitudes
    assert req.full_url == "https://graph.facebook.com/v25.0/555/messages"
    assert req.get_method() == "POST" and timeout == 15
    assert req.get_header("Authorization") == "Bearer secreto-123"
    cuerpo = json.loads(req.data)
    assert cuerpo["to"] == "573001234567"
    assert cuerpo["type"] == "template"
    assert cuerpo["template"]["name"] == "recordatorio_turno"
    assert cuerpo["template"]["language"] == {"code": "es_CO"}
    textos = [p["text"] for p in cuerpo["template"]["components"][0]["parameters"]]
    assert textos == ["hoy, lunes 9 de noviembre (09/11/2026)", "Toby", "10:00 am"]


def test_whatsapp_usa_urlopen_por_defecto(monkeypatch):
    llamadas = []
    monkeypatch.setattr(
        notificador_whatsapp.urllib.request, "urlopen",
        lambda req, timeout: llamadas.append(req) or RespuestaFalsa(),
    )
    NotificadorWhatsApp(entorno={**ENTORNO, "CLINICAN_WHATSAPP_PLANTILLA": "otra"}).enviar(MENSAJE)
    assert json.loads(llamadas[0].data)["template"]["name"] == "otra"


@pytest.mark.parametrize(
    "falla, texto",
    [
        (urllib.error.HTTPError("u", 401, "No autorizado", {}, io.BytesIO(b'{"error":"token"}')), "401"),
        (urllib.error.URLError("sin conexión"), "sin conexión"),
        (TimeoutError("tiempo"), "tiempo"),
    ],
)
def test_whatsapp_errores_se_convierten_en_error_envio(falla, texto):
    def abrir(solicitud, timeout):
        raise falla

    with pytest.raises(ErrorEnvio, match=texto) as info:
        NotificadorWhatsApp(entorno=ENTORNO, abrir_url=abrir).enviar(MENSAJE)
    assert "secreto-123" not in str(info.value)


def test_whatsapp_version_configurable():
    n = NotificadorWhatsApp(entorno={**ENTORNO, "CLINICAN_WHATSAPP_VERSION": "v26.0"})
    assert n.url == "https://graph.facebook.com/v26.0/555/messages"


def test_whatsapp_sin_parametros_no_envia():
    from dataclasses import replace

    llamadas = []
    with pytest.raises(ErrorEnvio, match="parámetros"):
        NotificadorWhatsApp(entorno=ENTORNO, abrir_url=lambda r, timeout: llamadas.append(r)).enviar(
            replace(MENSAJE, parametros=())
        )
    assert llamadas == []


def _error_meta(http, codigo, mensaje="algo"):
    cuerpo = json.dumps({"error": {"message": mensaje, "type": "OAuthException", "code": codigo}})
    return urllib.error.HTTPError("u", http, "x", {}, io.BytesIO(cuerpo.encode()))


@pytest.mark.parametrize(
    "http, codigo, texto",
    [
        (401, 190, "token de WhatsApp venció o no es válido"),
        (400, 131030, "no está en la lista de destinatarios"),
        (404, 132001, "plantilla no existe o aún no está aprobada"),
        (400, 132000, "no coincide con la plantilla"),
        (400, 131026, "no puede recibir mensajes de WhatsApp"),
        (429, 130429, "limitó los envíos"),
        (400, 131042, "método de pago"),
        (400, 133010, "no está registrado"),
    ],
)
def test_whatsapp_errores_de_meta_en_espanol(http, codigo, texto):
    def abrir(solicitud, timeout):
        raise _error_meta(http, codigo)

    with pytest.raises(ErrorEnvio, match=texto) as info:
        NotificadorWhatsApp(entorno=ENTORNO, abrir_url=abrir).enviar(MENSAJE)
    assert f"código {codigo}" in str(info.value) and f"HTTP {http}" in str(info.value)
    assert "secreto-123" not in str(info.value)


def test_whatsapp_error_desconocido_muestra_el_mensaje_de_meta():
    def abrir(solicitud, timeout):
        raise _error_meta(400, 999, "Algo raro pasó")

    with pytest.raises(ErrorEnvio, match="HTTP 400: Algo raro pasó \\(código 999\\)"):
        NotificadorWhatsApp(entorno=ENTORNO, abrir_url=abrir).enviar(MENSAJE)


def test_whatsapp_respuesta_sin_id_igual_cuenta_como_enviado():
    n = NotificadorWhatsApp(entorno=ENTORNO, abrir_url=lambda r, timeout: RespuestaFalsa(cuerpo=b"no json"))
    assert n.enviar(MENSAJE) is None


def test_despachador_audita_el_id_del_mensaje(con, esc, ruta_db):
    from clinican.servicios.auditoria import historial
    from clinican.servicios.notificaciones import notificaciones_de_turno

    t = esc.turno(inicio=a_las(10))
    agenda.registrar_abono(con, t.id, 20000, ahora=AHORA)
    whatsapp = NotificadorWhatsApp(entorno=ENTORNO, abrir_url=lambda r, timeout: RespuestaFalsa())
    assert Despachador(ruta_db, whatsapp).procesar_una_vez(a_las(9)).enviadas == 1
    [n] = notificaciones_de_turno(con, t.id)
    assert "wamid.ABC" in str(historial(con, "notificacion", n.id)[-1])


def test_whatsapp_estado_http_no_exitoso():
    with pytest.raises(ErrorEnvio, match="500"):
        NotificadorWhatsApp(entorno=ENTORNO, abrir_url=lambda r, timeout: RespuestaFalsa(500)).enviar(MENSAJE)


def test_whatsapp_telefono_invalido():
    from dataclasses import replace

    with pytest.raises(ErrorEnvio, match="Teléfono"):
        NotificadorWhatsApp(entorno=ENTORNO, abrir_url=lambda r, timeout: RespuestaFalsa()).enviar(
            replace(MENSAJE, telefono="")
        )


@pytest.mark.parametrize(
    "entrada, salida",
    [("300 123 4567", "573001234567"), ("+57 300-123-4567", "573001234567"), ("6012345678", "6012345678")],
)
def test_normalizar_telefono(entrada, salida):
    assert normalizar_telefono(entrada) == salida


def test_notificador_para_cada_canal(tmp_path):
    assert isinstance(notificadores.notificador_para("archivo", tmp_path), NotificadorArchivo)
    assert isinstance(notificadores.notificador_para("Consola", tmp_path), NotificadorConsola)
    assert isinstance(notificadores.notificador_para("whatsapp", tmp_path), NotificadorWhatsApp)
    for canal in ("archivo", "consola", "whatsapp"):
        assert isinstance(notificadores.notificador_para(canal, tmp_path), Notificador)
    with pytest.raises(DatoInvalido, match="desconocido"):
        notificadores.notificador_para("paloma", tmp_path)


def test_canal_configurado_de_extremo_a_extremo(con, esc, ruta_db, tmp_path):
    from clinican.servicios import configuracion

    canal = configuracion.cargar(con).canal_notificaciones
    assert canal == "archivo"
    t = esc.turno(inicio=a_las(10))
    agenda.registrar_abono(con, t.id, 20000, ahora=AHORA)
    Despachador(ruta_db, notificadores.notificador_para(canal, tmp_path)).procesar_una_vez(a_las(9))
    contenido = (tmp_path / "recordatorios.txt").read_text(encoding="utf-8")
    assert f"turno {t.id}" in contenido


class NotificadorSMSFalso:
    """Canal nuevo: solo su clase y su nombre en el registro."""

    enviados: list = []

    def enviar(self, mensaje):
        NotificadorSMSFalso.enviados.append((mensaje.telefono, mensaje.texto))


def test_agregar_canal_sms_sin_tocar_la_agenda(con, esc, ruta_db, tmp_path, monkeypatch):
    monkeypatch.setattr(notificadores, "_REGISTRO", dict(notificadores._REGISTRO))
    NotificadorSMSFalso.enviados = []
    notificadores.registrar("sms", lambda carpeta: NotificadorSMSFalso())
    assert "sms" in notificadores.canales()

    t = esc.turno(inicio=a_las(10))
    agenda.registrar_abono(con, t.id, 20000, ahora=AHORA)
    Despachador(ruta_db, notificadores.notificador_para("sms", tmp_path)).procesar_una_vez(a_las(9))
    assert NotificadorSMSFalso.enviados == [("3001234567", agenda_texto(con, t.id, a_las(9)))]

    servicios = Path(agenda.__file__).parent
    for archivo in ("agenda.py", "despachador.py", "notificaciones.py"):
        codigo = (servicios / archivo).read_text(encoding="utf-8").lower()
        for nombre in ("whatsapp", "sms", "notificadorarchivo", "adaptadores"):
            assert nombre not in codigo, (archivo, nombre)


def agenda_texto(con, turno_id, ahora):
    from clinican.servicios.notificaciones import texto_recordatorio
    from clinican.servicios import clientes

    t = agenda.obtener_turno(con, turno_id)
    return texto_recordatorio(clientes.obtener_mascota(con, t.mascota_id).nombre, t.inicio, ahora)
