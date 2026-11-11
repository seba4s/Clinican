from datetime import time, timedelta

from clinican.dominio.agenda import Bloqueo
from clinican.dominio.cupos import CategoriaCupo as C
from clinican.dominio.entidades import EstadoNotificacion as EN
from clinican.dominio.estados import EstadoTurno as E
from clinican.servicios import agenda, consultas
from clinican.servicios.despachador import Despachador
from conftest import AHORA, LUNES, a_las


def test_agenda_del_dia(con, esc):
    p = esc.propietario("Ana")
    t1 = esc.turno(C.MAQUINA, inicio=a_las(9), propietario=p)
    esc.turno(C.GRANDE, inicio=a_las(9))
    cancelado = esc.turno(C.TIJERA, inicio=a_las(10))
    agenda.cancelar_turno(con, cancelado.id, ahora=AHORA)
    agenda.crear_bloqueo(con, Bloqueo(LUNES, time(12), time(13)), ahora=AHORA)

    dia = consultas.agenda_del_dia(con, LUNES, ahora=AHORA)
    assert len(dia) == 14
    nueve = dia[0]
    assert nueve.franja.inicio == a_las(9)
    assert nueve.libres == {C.MAQUINA: 1, C.GRANDE: 0, C.TIJERA: 1, C.COMPLICADO: 1}
    assert [x.turno.id for x in nueve.turnos][0] == t1.id
    assert (nueve.turnos[0].propietario, nueve.turnos[0].celular) == ("Ana", "3001234567")
    diez = dia[2]
    assert diez.libres[C.TIJERA] == 1 and diez.turnos[0].turno.estado is E.CANCELADO
    # Al vencer los pendientes, sus cupos vuelven a estar libres
    despues = consultas.agenda_del_dia(con, LUNES, ahora=AHORA + timedelta(minutes=30))
    assert despues[0].libres[C.MAQUINA] == 2


def test_historial_de_mascota(con, esc):
    m = esc.mascota(C.MAQUINA)
    viejo = agenda.crear_turno(con, m.id, a_las(9), esc_servicio(), ahora=AHORA)
    agenda.registrar_abono(con, viejo.id, 20000, ahora=AHORA)
    agenda.iniciar_atencion(con, viejo.id, ahora=a_las(9))
    agenda.marcar_atendido(con, viejo.id, ahora=a_las(10), detalles_corte="#4")
    nuevo = agenda.crear_turno(con, m.id, a_las(9, dia=LUNES + timedelta(days=7)), esc_servicio(), ahora=AHORA)
    historial = consultas.historial_de_mascota(con, m.id)
    assert [t.id for t, _ in historial] == [nuevo.id, viejo.id]
    assert historial[0][1] is None
    assert historial[1][1].detalles_corte == "#4" and historial[1][1].precio_final == 45000


def esc_servicio():
    from clinican.dominio.cupos import Servicio

    return Servicio.CORTE_MAQUINA


def test_pendientes_de_abono(con, esc):
    a = esc.turno(inicio=a_las(9), ahora=AHORA)
    b = esc.turno(inicio=a_las(10), ahora=AHORA + timedelta(minutes=20))
    confirmado = esc.turno(inicio=a_las(11))
    agenda.registrar_abono(con, confirmado.id, 20000, ahora=AHORA)
    pendientes = consultas.pendientes_de_abono(con, ahora=AHORA + timedelta(minutes=35))
    assert [(p.turno.id, p.vencido) for p in pendientes] == [(a.id, True), (b.id, False)]
    assert pendientes[0].vence_en == AHORA + timedelta(minutes=30)


def test_estado_bandeja(con, esc, ruta_db):
    for hora in (9, 10, 11):
        t = esc.turno(inicio=a_las(hora))
        agenda.registrar_abono(con, t.id, 20000, ahora=AHORA)
    lejano = esc.turno(inicio=a_las(9, dia=LUNES + timedelta(days=3)))
    agenda.registrar_abono(con, lejano.id, 20000, ahora=AHORA)

    class Falla:
        llamadas = 0

        def enviar(self, mensaje):
            Falla.llamadas += 1
            if mensaje.inicio.hour == 9:
                from clinican.servicios.notificaciones import ErrorEnvio

                raise ErrorEnvio("sin señal")

    d = Despachador(ruta_db, Falla())
    momento = AHORA
    for espera in (0, 1, 5, 15):
        momento += timedelta(minutes=espera)
        d.procesar_una_vez(momento)
    estado = consultas.estado_bandeja(con)
    assert estado.conteo == {EN.PENDIENTE: 1, EN.ENVIADA: 2, EN.DESCARTADA: 0, EN.FALLIDA: 1}
    assert [n.turno_id for n in estado.proximas] == [lejano.id]
    assert estado.fallidas_recientes[0].ultimo_error == "sin señal"
