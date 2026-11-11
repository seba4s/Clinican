"""Los casos de uso de agenda funcionan sin ningún acceso a la red."""

import socket
from datetime import time, timedelta

import pytest

from clinican.dominio.agenda import Bloqueo
from clinican.dominio.cupos import CategoriaCupo as C
from clinican.dominio.estados import EstadoTurno as E
from clinican.servicios import agenda, clientes, configuracion
from conftest import AHORA, LUNES, a_las


@pytest.fixture
def sin_red(monkeypatch):
    def prohibido(*args, **kwargs):
        raise RuntimeError("Acceso a la red prohibido en esta prueba")

    monkeypatch.setattr(socket, "socket", prohibido)
    monkeypatch.setattr(socket, "create_connection", prohibido)
    monkeypatch.setattr(socket, "getaddrinfo", prohibido)


def test_red_bloqueada(sin_red):
    with pytest.raises(RuntimeError):
        socket.create_connection(("example.com", 80))
    with pytest.raises(RuntimeError):
        socket.socket()


def test_casos_de_uso_de_agenda_sin_red(sin_red, con, esc):
    configuracion.guardar(con, "abono", 20000, ahora=AHORA)
    dueno = esc.propietario("Ana")
    t = esc.turno(C.TIJERA, inicio=a_las(9), propietario=dueno)
    agenda.registrar_abono(con, t.id, 20000, ahora=AHORA)
    agenda.mover_turno(con, t.id, a_las(10), ahora=AHORA)
    agenda.iniciar_atencion(con, t.id, ahora=a_las(10))
    agenda.marcar_atendido(con, t.id, ahora=a_las(11))
    assert agenda.marcar_entregado(con, t.id, ahora=a_las(12)).estado is E.ENTREGADO

    otro = esc.turno(C.GRANDE, inicio=a_las(14), propietario=dueno)
    agenda.registrar_abono(con, otro.id, 20000, ahora=AHORA)
    agenda.marcar_inasistencia(con, otro.id, aviso_en=a_las(14) - timedelta(hours=20),
                               ahora=a_las(14, 30))
    assert clientes.obtener_propietario(con, dueno.id).saldo_a_favor == 20000

    vencido = esc.turno(C.MAQUINA, inicio=a_las(15))
    assert agenda.barrer_vencidos(con, ahora=AHORA + timedelta(hours=1)) == [vencido.id]
    cancelado = esc.turno(C.COMPLICADO, inicio=a_las(16), ahora=a_las(9))
    agenda.cancelar_turno(con, cancelado.id, ahora=a_las(9))

    b = agenda.crear_bloqueo(con, Bloqueo(LUNES, time(15), time(17)), ahora=a_las(9))
    assert len(agenda.disponibilidad(con, LUNES, ahora=a_las(9))) == 12
    agenda.quitar_bloqueo(con, b.id, ahora=a_las(9))


def test_despachador_y_adaptadores_sin_red(sin_red, con, esc, ruta_db, tmp_path):
    """Archivo, consola y WhatsApp (con urlopen simulado) no abren sockets reales."""
    import io

    from clinican.adaptadores.notificador_archivo import NotificadorArchivo
    from clinican.adaptadores.notificador_consola import NotificadorConsola
    from clinican.adaptadores.notificador_whatsapp import NotificadorWhatsApp
    from clinican.servicios.despachador import Despachador

    class Respuesta:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    enviados = []
    whatsapp = NotificadorWhatsApp(
        entorno={"CLINICAN_WHATSAPP_TOKEN": "t", "CLINICAN_WHATSAPP_NUMERO_ID": "1"},
        abrir_url=lambda req, timeout: enviados.append(req) or Respuesta(),
    )
    for i, notificador in enumerate(
        [NotificadorArchivo(tmp_path), NotificadorConsola(io.StringIO()), whatsapp]
    ):
        t = esc.turno(C.MAQUINA, inicio=a_las(10 + i))
        agenda.registrar_abono(con, t.id, 20000, ahora=AHORA)
        assert Despachador(ruta_db, notificador).procesar_una_vez(AHORA).enviadas == 1
    assert len(enviados) == 1
    # Sin el simulador, WhatsApp no puede salir a la red: falla y queda para reintento
    t = esc.turno(C.MAQUINA, inicio=a_las(15))
    agenda.registrar_abono(con, t.id, 20000, ahora=AHORA)
    sin_simular = NotificadorWhatsApp(
        entorno={"CLINICAN_WHATSAPP_TOKEN": "t", "CLINICAN_WHATSAPP_NUMERO_ID": "1"}
    )
    resumen = Despachador(ruta_db, sin_simular).procesar_una_vez(AHORA)
    assert resumen.reintentos == 1
