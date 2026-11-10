"""Recordatorios por bandeja de salida (driver D3, ADR-003, escenarios E1, E3 y E5)."""

import time
from datetime import datetime, timedelta

import pytest

from clinican.adaptadores import NotificadorArchivo, NotificadorWhatsApp, notificador_para
from clinican.adaptadores.despachador import Despachador
from clinican.datos.conexion import conectar
from clinican.dominio import notificaciones as reglas
from clinican.servicios import acceso, legal, notificaciones as sn
from clinican.servicios import turnos as st
from clinican.servicios.notificaciones import ErrorEnvio, Notificador
from clinican.servicios.turnos import Abono
from tests.test_turnos import AHORA, LUNES, MARTES, _dueno, _mascota, _turno


class CanalDePrueba:
    """Un canal cualquiera: basta con cumplir el puerto (nombre + enviar)."""

    nombre = "PRUEBA"

    def __init__(self, fallar: bool = False):
        self.enviados: list[reglas.Mensaje] = []
        self.fallar = fallar

    def enviar(self, mensaje):
        if self.fallar:
            raise ErrorEnvio("sin conexión")
        self.enviados.append(mensaje)


def _salida(conn, turno_id):
    filas = conn.execute("SELECT * FROM notificaciones_salida WHERE turno_id = ?", (turno_id,)).fetchall()
    assert len(filas) == 1
    return filas[0]


# Los turnos de prueba se agendan el mismo lunes a las 07:00 para las 09:00: faltan menos de 24 h,
# así que el recordatorio queda listo de inmediato.
DIA_ANTES = AHORA + timedelta(minutes=1)


# ------------------------------------------------------------------ dominio

def test_momento_de_envio():
    inicio = datetime(2026, 11, 20, 9, 0)
    assert reglas.momento_de_envio(inicio, 24, datetime(2026, 11, 10, 8, 0)) == datetime(2026, 11, 19, 9, 0)
    tarde = datetime(2026, 11, 20, 7, 0)
    assert reglas.momento_de_envio(inicio, 24, tarde) == tarde  # ya pasó: de inmediato


@pytest.mark.parametrize("estado,horas,autorizado,celular,esperado", [
    ("CONFIRMADO", 5, True, True, None),
    ("LIBERADO", 5, True, True, "ya no está confirmado"),
    ("CONFIRMADO", -1, True, True, "ya empezó"),
    ("CONFIRMADO", 5, False, True, "Ley 1581"),
    ("CONFIRMADO", 5, True, False, "celular"),
])
def test_motivo_para_descartar(estado, horas, autorizado, celular, esperado):
    ahora = datetime(2026, 11, 10, 8, 0)
    motivo = reglas.motivo_para_descartar(estado, ahora + timedelta(hours=horas), ahora, autorizado, celular)
    assert motivo is None if esperado is None else esperado in motivo


def test_espera_creciente_y_celular_y_texto():
    assert [reglas.espera_reintento(n).seconds // 60 for n in (1, 2, 3, 10)] == [1, 2, 4, 60]
    assert reglas.celular_internacional("301 441 7194") == "573014417194"
    assert reglas.celular_internacional("573014417194") == "573014417194"
    m = reglas.recordatorio("3014417194", "María Pérez", "Toby", datetime(2026, 11, 12, 9, 30), "CLINICAN")
    assert m.parametros == ("María", "Toby", "jueves 12 de noviembre", "09:30", "CLINICAN")
    assert "Toby" in m.texto and "09:30" in m.texto and m.destino == "573014417194"


# --------------------------------------------------------- agenda → bandeja

def test_confirmar_un_turno_deja_el_recordatorio_en_la_bandeja(conn, empleada):
    t = _turno(conn, empleada)  # con abono: nace confirmado
    fila = _salida(conn, t)
    assert fila["estado"] == "PENDIENTE" and fila["plantilla"] == reglas.PLANTILLA_RECORDATORIO
    assert fila["enviar_desde"] == AHORA.strftime("%Y-%m-%d %H:%M:%S")  # faltan menos de 24 h: de inmediato


def test_un_pendiente_sin_abono_no_programa_recordatorio(conn, empleada):
    t = _turno(conn, empleada, pagar=False)
    assert conn.execute("SELECT COUNT(*) FROM notificaciones_salida WHERE turno_id = ?", (t,)).fetchone()[0] == 0
    st.registrar_abono(conn, empleada, t, Abono(20000, "NEQUI"), ahora=AHORA)
    assert _salida(conn, t)["estado"] == "PENDIENTE"


def test_mover_el_turno_reprograma_el_recordatorio(conn, empleada):
    t = _turno(conn, empleada)
    st.mover(conn, empleada, t, MARTES, "10:00", ahora=AHORA)
    assert _salida(conn, t)["enviar_desde"].startswith(f"{LUNES} 10:00")  # 24 h antes del martes 10:00


# ------------------------------------------------------------- despachador

def test_despachar_envia_y_marca(conn, empleada):
    t = _turno(conn, empleada)
    canal = CanalDePrueba()
    r = sn.despachar(conn, canal, ahora=DIA_ANTES)
    assert r.enviados == [_salida(conn, t)["id"]] and len(canal.enviados) == 1
    fila = _salida(conn, t)
    assert (fila["estado"], fila["canal"], fila["destino"]) == ("ENVIADO", "PRUEBA", "573012345678")
    assert sn.despachar(conn, canal, ahora=DIA_ANTES).enviados == []  # no se envía dos veces


def test_no_se_envia_antes_de_tiempo(conn, empleada):
    _turno(conn, empleada)
    canal = CanalDePrueba()
    assert sn.despachar(conn, canal, ahora=AHORA - timedelta(days=3)).enviados == []
    assert canal.enviados == []


def test_sin_conexion_queda_pendiente_y_se_reintenta(conn, empleada):
    """E1: si el canal falla, la agenda no se entera y el mensaje espera."""
    t = _turno(conn, empleada)
    r = sn.despachar(conn, CanalDePrueba(fallar=True), ahora=DIA_ANTES)
    assert r.fallidos and _salida(conn, t)["estado"] == "PENDIENTE"
    assert _salida(conn, t)["intentos"] == 1 and "sin conexión" in _salida(conn, t)["ultimo_error"]
    canal = CanalDePrueba()
    assert sn.despachar(conn, canal, ahora=DIA_ANTES).enviados == []  # esperando el reintento
    assert sn.despachar(conn, canal, ahora=DIA_ANTES + timedelta(minutes=2)).enviados  # vuelve la red
    assert _salida(conn, t)["estado"] == "ENVIADO"


def test_sin_autorizacion_de_datos_no_se_contacta(conn, empleada):
    """E5 / Ley 1581."""
    mid = _mascota(conn, empleada, pid=_dueno(conn, empleada, consentir=False))
    t = st.crear_turno(conn, empleada, mid, "MAQUINA", LUNES, "09:00", empleada.personal_id,
                       Abono(20000, "NEQUI"), ahora=AHORA).turnos[0]
    canal = CanalDePrueba()
    r = sn.despachar(conn, canal, ahora=DIA_ANTES)
    assert canal.enviados == [] and "Ley 1581" in r.descartados[0][1]
    assert _salida(conn, t)["estado"] == "DESCARTADO"


def test_turno_cancelado_se_descarta(conn, empleada):
    t = _turno(conn, empleada)
    st.cancelar(conn, empleada, t, "A_FAVOR", ahora=AHORA)
    canal = CanalDePrueba()
    sn.despachar(conn, canal, ahora=DIA_ANTES)
    assert canal.enviados == [] and _salida(conn, t)["estado"] == "DESCARTADO"


def test_un_canal_nuevo_no_cambia_la_agenda(conn, empleada):
    """E3: un canal nuevo (por ejemplo SMS) es solo una clase que cumple el puerto."""

    class NotificadorSMS:
        nombre = "SMS"
        enviados = []

        def enviar(self, mensaje):
            self.enviados.append((mensaje.destino, mensaje.texto[:160]))

    assert isinstance(NotificadorSMS(), Notificador)
    _turno(conn, empleada)
    sms = NotificadorSMS()
    assert sn.despachar(conn, sms, ahora=DIA_ANTES).enviados and sms.enviados


# --------------------------------------------------------------- adaptadores

def test_adaptador_archivo(conn, empleada, tmp_path):
    _turno(conn, empleada)
    canal = notificador_para("ARCHIVO", tmp_path)
    assert isinstance(canal, NotificadorArchivo)
    sn.despachar(conn, canal, ahora=DIA_ANTES)
    assert "+573012345678" in (tmp_path / "recordatorios.txt").read_text(encoding="utf-8")


def test_adaptador_whatsapp_sin_cuenta_no_envia(conn, empleada, monkeypatch):
    monkeypatch.delenv("CLINICAN_WHATSAPP_TOKEN", raising=False)
    canal = notificador_para("WHATSAPP", ".")
    assert isinstance(canal, NotificadorWhatsApp)
    t = _turno(conn, empleada)
    r = sn.despachar(conn, canal, ahora=DIA_ANTES)
    assert "no está configurada" in r.fallidos[0][1] and _salida(conn, t)["estado"] == "PENDIENTE"


def test_whatsapp_usa_plantilla():
    canal = NotificadorWhatsApp("token", "123")
    m = reglas.recordatorio("3014417194", "Ana", "Toby", datetime(2026, 11, 12, 9, 0), "CLINICAN")
    cuerpo = canal.cuerpo(m)
    assert cuerpo["to"] == "573014417194" and cuerpo["type"] == "template"
    assert cuerpo["template"]["name"] == "recordatorio_turno"
    assert [p["text"] for p in cuerpo["template"]["components"][0]["parameters"]][1] == "Toby"


def test_despachador_en_hilo_con_su_propia_conexion(tmp_path):
    ruta = tmp_path / "clinican.db"
    conn = conectar(ruta)
    s = acceso.crear_administradora_inicial(conn, "Angela", "Jefe", "1234")
    pid = _dueno(conn, s)
    mid = _mascota(conn, s, pid=pid)
    # un turno para dentro de una hora: el recordatorio sale de inmediato
    manana = datetime.now() + timedelta(days=1)
    while manana.weekday() == 6:
        manana += timedelta(days=1)
    st.crear_turno(conn, s, mid, "MAQUINA", manana.date().isoformat(), "09:00", s.personal_id,
                   Abono(20000, "NEQUI"))
    conn.execute("UPDATE notificaciones_salida SET enviar_desde = '2000-01-01 00:00:00'")
    canal = CanalDePrueba()
    d = Despachador(lambda: conectar(ruta), canal, intervalo_segundos=0.05)
    d.iniciar()
    limite = time.time() + 5
    while not canal.enviados and time.time() < limite:
        time.sleep(0.05)
    d.detener()
    assert canal.enviados
    assert sn.conteo(conn)["ENVIADO"] == 1
    conn.close()
