"""Fase 4: turnos, cupos, abonos, expiración, grupos, no asistencia y bloqueos."""

from datetime import date, datetime, timedelta
from itertools import count

import pytest

from clinican.datos import semillas
from clinican.dominio import cupos
from clinican.dominio.errores import DatoInvalido, PermisoDenegado
from clinican.dominio.ficha import DetallesFicha
from clinican.servicios import configuracion, fichas, horarios, legal
from clinican.servicios import propietarios as sp
from clinican.servicios import turnos as st
from clinican.servicios.turnos import Abono

# Un lunes futuro, para que ninguna fecha del ensayo sea pasada.
_hoy = date.today()
LUNES = (_hoy + timedelta(days=7 + (7 - _hoy.weekday()) % 7)).isoformat()
MARTES = (date.fromisoformat(LUNES) + timedelta(days=1)).isoformat()
DOMINGO = (date.fromisoformat(LUNES) + timedelta(days=6)).isoformat()
AHORA = datetime.fromisoformat(f"{LUNES} 07:00:00")
_cedulas = count(10_000_000)


def _raza(conn, nombre):
    return conn.execute("SELECT id FROM razas WHERE nombre = ?", (nombre,)).fetchone()[0]


def _dueno(conn, s, consentir=True):
    pid = sp.crear(conn, s, "María Pérez", str(next(_cedulas)), "3012345678", "3109998877", "Calle 10")
    if consentir:
        legal.aceptar(conn, s, pid, ["TERMINOS", "DATOS"])
    return pid


def _mascota(conn, s, raza="Shih Tzu", pid=None, nombre=None, **kw):
    pid = pid or _dueno(conn, s)
    return sp.crear_mascota(conn, s, pid, nombre or f"M{next(_cedulas)}", _raza(conn, raza), **kw)


def _turno(conn, s, raza="Shih Tzu", tipo="MAQUINA", hora="09:00", fecha=LUNES, pagar=True, ahora=AHORA, **kw):
    mid = _mascota(conn, s, raza, **kw)
    abono = Abono(20000, "NEQUI") if pagar else None
    return st.crear_turno(conn, s, mid, tipo, fecha, hora, s.personal_id, abono, ahora=ahora).turnos[0]


def _estado(conn, turno_id):
    return conn.execute("SELECT estado, motivo_liberacion FROM turnos WHERE id = ?", (turno_id,)).fetchone()


# =============================================================== RN-02

@pytest.mark.parametrize(
    "raza,tipo,esperada",
    [
        ("Poodle (Caniche) Toy y Miniatura", "MAQUINA", "MAQUINA"),
        ("Bulldog Francés", "BANO_DESLANADO", "MAQUINA"),
        ("Yorkshire Terrier", "MAQUINA", "MAQUINA"),
        ("Shih Tzu", "TIJERA", "TIJERA"),
        ("Chihuahua", "MAQUINA", "MAQUINA"),
        ("Schnauzer Miniatura", "MAQUINA", "MAQUINA"),
        ("Schnauzer", "MAQUINA", "MAQUINA"),
        ("Pitbull y similares", "BANO_DESLANADO", "MAQUINA"),
        ("Labrador Retriever", "MAQUINA", "GRANDE"),
        ("Golden Retriever", "TIJERA", "TIJERA"),
        ("Pastor Alemán", "BANO_DESLANADO", "GRANDE"),
        ("Husky", "MAQUINA", "COMPLICADO"),
        ("Husky", "TIJERA", "COMPLICADO"),
    ],
)
def test_categoria_cupo_por_raza(conn, empleada, raza, tipo, esperada):
    mid = _mascota(conn, empleada, raza)
    assert st.categoria_para(conn, mid, tipo) == esperada


@pytest.mark.parametrize(
    "tamano,pelaje,tipo,esperada",
    [("PEQUENA", 0, "MAQUINA", "MAQUINA"), ("MEDIANA", 0, "BANO_DESLANADO", "MAQUINA"),
     ("GRANDE", 0, "MAQUINA", "GRANDE"), ("MEDIANA", 0, "TIJERA", "TIJERA"), ("GRANDE", 1, "TIJERA", "COMPLICADO")],
)
def test_categoria_cupo_mestizo(conn, empleada, tamano, pelaje, tipo, esperada):
    mid = _mascota(conn, empleada, "Perro mestizo (sin raza)", tamano_manual=tamano, pelaje_manual=pelaje)
    assert st.categoria_para(conn, mid, tipo) == esperada


def test_supuesto_a1_pequenas(conn, admin, empleada):
    mid = _mascota(conn, empleada, "Chihuahua")
    configuracion.guardar(conn, admin, {"pequenas_en_cupo_maquina": "0"})
    with pytest.raises(DatoInvalido, match="A-1"):
        st.categoria_para(conn, mid, "MAQUINA")


# =============================================================== RN-03

def test_cupos_por_categoria_en_una_franja(conn, empleada):
    """2 MÁQUINA + 1 GRANDE + 1 TIJERA + 1 COMPLICADO a la vez [A-2]; el excedente se rechaza."""
    for raza, tipo in [("Shih Tzu", "MAQUINA"), ("Schnauzer", "MAQUINA"), ("Labrador Retriever", "MAQUINA"),
                       ("Poodle (Caniche) Toy y Miniatura", "TIJERA"), ("Husky", "BANO_DESLANADO")]:
        t = _turno(conn, empleada, raza, tipo)
        assert _estado(conn, t)["estado"] == "CONFIRMADO"
    assert horarios.cupos_libres(conn, LUNES, "09:00") == {"MAQUINA": 0, "GRANDE": 0, "TIJERA": 0, "COMPLICADO": 0}
    for raza, tipo in [("Chihuahua", "MAQUINA"), ("Golden Retriever", "BANO_DESLANADO"),
                       ("Shih Tzu", "TIJERA"), ("Husky", "MAQUINA")]:
        with pytest.raises(DatoInvalido, match="No hay cupo"):
            _turno(conn, empleada, raza, tipo)
    # Otra franja sigue libre
    assert _estado(conn, _turno(conn, empleada, "Chihuahua", hora="09:30"))["estado"] == "CONFIRMADO"


def test_pendientes_no_ocupan_cupo(conn, empleada):
    _turno(conn, empleada, "Labrador Retriever", pagar=False)
    assert horarios.cupos_libres(conn, LUNES, "09:00")["GRANDE"] == 1


def test_cupos_no_independientes(conn, admin, empleada):
    """[A-2] desactivado: una franja atiende una sola categoría a la vez."""
    configuracion.guardar(conn, admin, {"cupos_independientes": "0"})
    _turno(conn, empleada, "Labrador Retriever")
    with pytest.raises(DatoInvalido, match="No hay cupo"):
        _turno(conn, empleada, "Shih Tzu")


def test_cupo_configurable(conn, admin, empleada):
    configuracion.guardar(conn, admin, {"cupo_GRANDE": "2"})
    _turno(conn, empleada, "Labrador Retriever")
    _turno(conn, empleada, "Golden Retriever")
    with pytest.raises(DatoInvalido):
        _turno(conn, empleada, "Pastor Alemán")


# ========================================================== RN-05 / RN-15

def test_sin_consentimientos_no_se_agenda(conn, empleada):
    pid = _dueno(conn, empleada, consentir=False)
    mid = _mascota(conn, empleada, pid=pid)
    with pytest.raises(DatoInvalido, match="términos"):
        st.crear_turno(conn, empleada, mid, "MAQUINA", LUNES, "09:00", empleada.personal_id, ahora=AHORA)


def test_turno_nace_pendiente_con_plazo_y_ficha(conn, empleada):
    t = _turno(conn, empleada, pagar=False)
    fila = conn.execute("SELECT * FROM turnos WHERE id = ?", (t,)).fetchone()
    assert fila["estado"] == "PENDIENTE_ABONO"
    assert fila["pendiente_hasta"] == f"{LUNES} 07:30:00"
    assert fila["agendado_por"] == empleada.personal_id
    ficha = fichas.obtener(conn, empleada, fila["servicio_id"])
    assert ficha["tipo_servicio"] == "MAQUINA" and ficha["fecha"] == LUNES and ficha["precio_minimo"] == 45000


def test_con_abono_nace_confirmado(conn, empleada):
    assert _estado(conn, _turno(conn, empleada))["estado"] == "CONFIRMADO"


@pytest.mark.parametrize(
    "hora,fecha,mensaje",
    [("09:15", LUNES, "No hay una franja"), ("12:00", LUNES, "No hay una franja"),
     ("09:00", DOMINGO, "No hay una franja"), ("06:00", LUNES, "ya pasó")],
)
def test_franja_invalida(conn, empleada, hora, fecha, mensaje):
    with pytest.raises(DatoInvalido, match=mensaje):
        _turno(conn, empleada, hora=hora, fecha=fecha)


def test_quien_agenda_obligatorio(conn, empleada):
    mid = _mascota(conn, empleada)
    with pytest.raises(DatoInvalido, match="quién agenda"):
        st.crear_turno(conn, empleada, mid, "MAQUINA", LUNES, "09:00", None, ahora=AHORA)


def test_agendado_por_puede_ser_otra_persona(conn, admin, empleada):
    mid = _mascota(conn, empleada)
    t = st.crear_turno(conn, empleada, mid, "MAQUINA", LUNES, "09:00", admin.personal_id, ahora=AHORA).turnos[0]
    assert st.turno(conn, empleada, t)["agendado_por_nombre"] == "Angela"


def test_una_mascota_un_turno_por_dia(conn, empleada):
    mid = _mascota(conn, empleada)
    st.crear_turno(conn, empleada, mid, "MAQUINA", LUNES, "09:00", empleada.personal_id, ahora=AHORA)
    with pytest.raises(DatoInvalido, match="ya tiene un turno"):
        st.crear_turno(conn, empleada, mid, "MAQUINA", LUNES, "10:00", empleada.personal_id, ahora=AHORA)


# ========================================================== RN-06 / RN-07

def test_abono_minimo_por_mascota(conn, empleada):
    t = _turno(conn, empleada, pagar=False)
    with pytest.raises(DatoInvalido, match="mínimo"):
        st.registrar_abono(conn, empleada, t, Abono("15.000", "EFECTIVO"), ahora=AHORA)
    st.registrar_abono(conn, empleada, t, Abono("$20.000", "BREB", "Comprobante 123"), ahora=AHORA)
    assert _estado(conn, t)["estado"] == "CONFIRMADO"
    assert st.abonos(conn, empleada, t)[0]["referencia"] == "Comprobante 123"


def test_expiracion_a_los_30_minutos(conn, empleada):
    t = _turno(conn, empleada, pagar=False)
    assert st.expirar_vencidos(conn, AHORA + timedelta(minutes=29, seconds=59)) == []
    assert _estado(conn, t)["estado"] == "PENDIENTE_ABONO"
    assert st.expirar_vencidos(conn, AHORA + timedelta(minutes=30)) == [t]
    assert tuple(_estado(conn, t)) == ("LIBERADO", "EXPIRO")
    # Ya liberado: no se puede pagar y la franja queda libre para otro
    with pytest.raises(DatoInvalido, match="liberado"):
        st.registrar_abono(conn, empleada, t, Abono(20000, "NEQUI"), ahora=AHORA + timedelta(minutes=31))
    ficha = conn.execute("SELECT s.estado FROM servicios s JOIN turnos t ON t.servicio_id = s.id WHERE t.id = ?", (t,)).fetchone()
    assert ficha[0] == "CANCELADO"


def test_pagar_tarde_expira_primero(conn, empleada):
    t = _turno(conn, empleada, pagar=False)
    with pytest.raises(DatoInvalido, match="liberado"):
        st.registrar_abono(conn, empleada, t, Abono(20000, "NEQUI"), ahora=AHORA + timedelta(minutes=45))
    assert _estado(conn, t)["estado"] == "LIBERADO"


# =============================================================== RN-08

def test_gana_quien_paga_primero(conn, empleada):
    a = _turno(conn, empleada, "Shih Tzu", "TIJERA", pagar=False)
    b = _turno(conn, empleada, "Poodle (Caniche) Toy y Miniatura", "TIJERA", pagar=False)
    resultado = st.registrar_abono(conn, empleada, b, Abono(20000, "NEQUI"), ahora=AHORA + timedelta(minutes=5))
    assert _estado(conn, b)["estado"] == "CONFIRMADO"
    assert tuple(_estado(conn, a)) == ("LIBERADO", "OTRO_PAGO_PRIMERO")
    assert [x["id"] for x in resultado.liberados] == [a]  # para avisar al personal
    with pytest.raises(DatoInvalido, match="liberado"):
        st.registrar_abono(conn, empleada, a, Abono(20000, "NEQUI"), ahora=AHORA + timedelta(minutes=6))


def test_otro_pendiente_sigue_si_queda_cupo(conn, empleada):
    a = _turno(conn, empleada, "Shih Tzu", pagar=False)
    b = _turno(conn, empleada, "Chihuahua", pagar=False)
    st.registrar_abono(conn, empleada, b, Abono(20000, "NEQUI"), ahora=AHORA)
    assert _estado(conn, a)["estado"] == "PENDIENTE_ABONO"  # MÁQUINA tiene 2 cupos


# =============================================================== RN-09

@pytest.fixture
def cinco(conn, empleada):
    pid = _dueno(conn, empleada)
    razas = ["Shih Tzu", "Chihuahua", "Schnauzer", "Labrador Retriever", "Husky"]
    return pid, [(sp.crear_mascota(conn, empleada, pid, f"Perro{i}", _raza(conn, r)), "MAQUINA") for i, r in enumerate(razas)]


def test_grupo_de_5_desde_las_9(conn, empleada, cinco):
    _, mascotas = cinco
    plan, faltan = st.planificar_grupo(conn, empleada, mascotas, LUNES, "MANANA", ahora=AHORA)
    assert [h for _, h in plan] == ["09:00", "09:30", "10:00", "10:30", "11:00"] and faltan == []
    assert [m for m, _ in plan] == [m for m, _ in mascotas]  # en el orden en que se listan


def test_grupo_de_5_desde_las_1430(conn, empleada, cinco):
    _, mascotas = cinco
    plan, faltan = st.planificar_grupo(conn, empleada, mascotas, LUNES, "TARDE", ahora=AHORA)
    assert [h for _, h in plan] == ["14:30", "15:00", "15:30", "16:00", "16:30"] and faltan == []


def test_grupo_desborda_a_la_otra_jornada(conn, empleada, cinco):
    pid, mascotas = cinco
    mascotas += [(sp.crear_mascota(conn, empleada, pid, f"Extra{i}", _raza(conn, "Shih Tzu")), "MAQUINA") for i in range(2)]
    plan, faltan = st.planificar_grupo(conn, empleada, mascotas, LUNES, "MANANA", ahora=AHORA)
    assert [h for _, h in plan] == ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30"]
    assert "08:30" not in [h for _, h in plan]  # 08:30 solo para individuales [A-3]
    assert faltan == [mascotas[6][0]]
    resto = [(m, t) for m, t in mascotas if m in faltan]
    plan2, faltan2 = st.planificar_grupo(conn, empleada, resto, LUNES, "TARDE", ahora=AHORA)
    assert plan2 == [(mascotas[6][0], "14:30")] and faltan2 == []


def test_grupo_salta_franja_sin_cupo(conn, empleada, cinco):
    _, mascotas = cinco
    _turno(conn, empleada, "Golden Retriever", hora="10:30")  # ocupa el cupo GRANDE de las 10:30
    plan, _ = st.planificar_grupo(conn, empleada, mascotas, LUNES, "MANANA", ahora=AHORA)
    # La 4.ª mascota (labrador, GRANDE) no cabe a las 10:30 y pasa a las 11:00
    assert [h for _, h in plan] == ["09:00", "09:30", "10:00", "11:00", "11:30"]


def test_crear_grupo_con_pago_unico(conn, empleada, cinco):
    _, mascotas = cinco
    plan, _ = st.planificar_grupo(conn, empleada, mascotas, LUNES, "MANANA", ahora=AHORA)
    items = [(m, "MAQUINA", LUNES, h) for m, h in plan]
    with pytest.raises(DatoInvalido, match="al menos"):
        st.crear_grupo(conn, empleada, items, empleada.personal_id, Abono(90000, "EFECTIVO"), ahora=AHORA)
    r = st.crear_grupo(conn, empleada, items, empleada.personal_id, Abono(110000, "EFECTIVO"), ahora=AHORA)
    filas = st.grupo(conn, empleada, r.turnos[0])
    assert len(filas) == 5 and {f["grupo_id"] for f in filas} == {r.turnos[0]}
    assert all(f["estado"] == "CONFIRMADO" for f in filas)
    assert [f["abonado"] for f in filas] == [30000, 20000, 20000, 20000, 20000]


def test_grupo_pago_despues(conn, empleada, cinco):
    _, mascotas = cinco
    items = [(m, "MAQUINA", LUNES, h) for (m, _), h in zip(mascotas[:2], ["09:00", "09:30"])]
    r = st.crear_grupo(conn, empleada, items, empleada.personal_id, ahora=AHORA)
    assert all(f["estado"] == "PENDIENTE_ABONO" for f in st.grupo(conn, empleada, r.turnos[0]))
    st.pagar_grupo(conn, empleada, r.turnos[0], Abono(40000, "NEQUI"), ahora=AHORA)
    assert all(f["estado"] == "CONFIRMADO" for f in st.grupo(conn, empleada, r.turnos[0]))


def test_grupo_no_usa_franja_individual_ni_otro_dueno(conn, empleada, cinco):
    _, mascotas = cinco
    with pytest.raises(DatoInvalido, match="individuales"):
        st.crear_grupo(conn, empleada, [(mascotas[0][0], "MAQUINA", LUNES, "08:30"),
                                        (mascotas[1][0], "MAQUINA", LUNES, "09:00")], empleada.personal_id, ahora=AHORA)
    ajena = _mascota(conn, empleada)
    with pytest.raises(DatoInvalido, match="mismo propietario"):
        st.crear_grupo(conn, empleada, [(mascotas[0][0], "MAQUINA", LUNES, "09:00"),
                                        (ajena, "MAQUINA", LUNES, "09:30")], empleada.personal_id, ahora=AHORA)
    assert conn.execute("SELECT COUNT(*) FROM turnos").fetchone()[0] == 0  # todo o nada


# =============================================================== RN-10

def _no_asistio(conn, s, horas_antes):
    t = _turno(conn, s, hora="09:00")
    aviso = datetime.fromisoformat(f"{LUNES} 09:00:00") - timedelta(hours=horas_antes) if horas_antes is not None else None
    ahora = datetime.fromisoformat(f"{LUNES} 10:00:00")
    return t, st.no_asistio(conn, s, t, aviso, ahora=ahora)


def test_aviso_con_12_horas(conn, empleada):
    t, estado = _no_asistio(conn, empleada, 12)
    assert estado == "NO_ASISTIO_AVISO"
    assert st.abonos(conn, empleada, t)[0]["estado"] == "VIGENTE"  # se conserva para reprogramar [A-8]
    pid = st.turno(conn, empleada, t)["propietario_id"]
    assert sp.obtener(conn, empleada, pid)["requiere_nuevo_abono"] == 0
    assert len(st.abonos_a_favor(conn, empleada, pid)) == 1


@pytest.mark.parametrize("horas", [11, None])
def test_aviso_con_11_horas_o_sin_aviso(conn, empleada, horas):
    t, estado = _no_asistio(conn, empleada, horas)
    assert estado == "NO_ASISTIO_SIN_AVISO"
    assert st.abonos(conn, empleada, t)[0]["estado"] == "PERDIDO"
    pid = st.turno(conn, empleada, t)["propietario_id"]
    assert sp.obtener(conn, empleada, pid)["requiere_nuevo_abono"] == 1
    assert st.abonos_a_favor(conn, empleada, pid) == []


def test_requiere_nuevo_abono_para_agendar(conn, empleada):
    t, _ = _no_asistio(conn, empleada, None)
    pid = st.turno(conn, empleada, t)["propietario_id"]
    mid = _mascota(conn, empleada, pid=pid)
    with pytest.raises(DatoInvalido, match="abono nuevo"):
        st.crear_turno(conn, empleada, mid, "MAQUINA", MARTES, "09:00", empleada.personal_id, ahora=AHORA)
    st.crear_turno(conn, empleada, mid, "MAQUINA", MARTES, "09:00", empleada.personal_id, Abono(20000, "NEQUI"), ahora=AHORA)
    assert sp.obtener(conn, empleada, pid)["requiere_nuevo_abono"] == 0


def test_horas_de_aviso_configurables(conn, admin, empleada):
    configuracion.guardar(conn, admin, {"horas_minimas_aviso": "2"})
    _, estado = _no_asistio(conn, empleada, 3)
    assert estado == "NO_ASISTIO_AVISO"


def test_abono_a_favor_se_usa_al_reprogramar(conn, empleada):
    t, _ = _no_asistio(conn, empleada, 24)
    fila = st.turno(conn, empleada, t)
    a_favor = st.abonos_a_favor(conn, empleada, fila["propietario_id"])[0]
    r = st.crear_turno(conn, empleada, fila["mascota_id"], "MAQUINA", MARTES, "10:00", empleada.personal_id,
                       abono_a_favor_id=a_favor["id"], ahora=AHORA)
    assert _estado(conn, r.turnos[0])["estado"] == "CONFIRMADO"
    assert st.abonos_a_favor(conn, empleada, fila["propietario_id"]) == []


# =========================================================== RN-16 / RN-17

def test_flujo_completo_hasta_entregar(conn, empleada):
    t = _turno(conn, empleada, "Shih Tzu", hora="09:00")
    st.iniciar_atencion(conn, empleada, t)
    st.marcar_lista(conn, empleada, t)
    st.registrar_llamada(conn, empleada, t, ahora=datetime.fromisoformat(f"{LUNES} 11:15:00"))
    assert st.turno(conn, empleada, t)["llamada_en"] == f"{LUNES} 11:15:00"
    with pytest.raises(DatoInvalido, match="precio final"):
        st.entregar(conn, empleada, t)
    fila = st.turno(conn, empleada, t)
    fichas.editar(conn, empleada, fila["servicio_id"], LUNES, DetallesFicha("MAQUINA", bano_antipulgas=True), "50.000")
    assert st.cobro(conn, empleada, t) == {"total": 55000, "abonado": 20000, "saldo": 35000, "falta_precio": False}
    cuenta = st.entregar(conn, empleada, t)
    assert cuenta["saldo"] == 35000
    assert _estado(conn, t)["estado"] == "ATENDIDO"
    assert st.abonos(conn, empleada, t)[0]["estado"] == "APLICADO"
    assert fichas.obtener(conn, empleada, fila["servicio_id"])["estado"] == "REALIZADO"
    assert sp.mascota(conn, empleada, fila["mascota_id"])["fecha_ultima_visita"] == LUNES  # RN-14


def test_no_se_pudo_atender(conn, empleada):
    t = _turno(conn, empleada)
    st.iniciar_atencion(conn, empleada, t)
    with pytest.raises(DatoInvalido):
        st.no_atendido(conn, empleada, t, "OTRO")
    st.no_atendido(conn, empleada, t, "AGRESIVIDAD")
    fila = st.turno(conn, empleada, t)
    assert (fila["estado"], fila["motivo_no_atendido"]) == ("NO_ATENDIDO", "AGRESIVIDAD")
    st.registrar_llamada(conn, empleada, t, ahora=AHORA)


@pytest.mark.parametrize("accion", ["marcar_lista", "entregar"])
def test_transiciones_invalidas(conn, empleada, accion):
    t = _turno(conn, empleada)  # confirmado
    with pytest.raises(DatoInvalido, match="No se puede pasar"):
        getattr(st, accion)(conn, empleada, t)


# ============================================================ mover / cancelar

def test_mover_conserva_abono(conn, empleada):
    t = _turno(conn, empleada, hora="09:00")
    st.mover(conn, empleada, t, MARTES, "15:00", ahora=AHORA)
    fila = st.turno(conn, empleada, t)
    assert (fila["fecha"], fila["hora"], fila["estado"], fila["abonado"]) == (MARTES, "15:00", "CONFIRMADO", 20000)
    assert fichas.obtener(conn, empleada, fila["servicio_id"])["fecha"] == MARTES


def test_mover_a_franja_llena(conn, empleada):
    _turno(conn, empleada, "Labrador Retriever", hora="10:00")
    t = _turno(conn, empleada, "Golden Retriever", hora="09:00")
    with pytest.raises(DatoInvalido, match="No hay cupo"):
        st.mover(conn, empleada, t, LUNES, "10:00", ahora=AHORA)


def test_cancelar_deja_abono_a_favor(conn, empleada):
    t = _turno(conn, empleada)
    st.cancelar(conn, empleada, t)
    assert tuple(_estado(conn, t)) == ("LIBERADO", "MANUAL")
    assert len(st.abonos_a_favor(conn, empleada, st.turno(conn, empleada, t)["propietario_id"])) == 1


# ======================================================== RN-04 / RN-11

def test_franjas_de_una_fecha(conn, empleada):
    horas = [f.hora for f in horarios.franjas(conn, LUNES)]
    assert horas == semillas.FRANJAS_MANANA + semillas.FRANJAS_TARDE
    assert horarios.franjas(conn, DOMINGO) == []
    horarios.agregar_franja_suelta(conn, empleada, DOMINGO, "10:00")
    assert [f.hora for f in horarios.franjas(conn, DOMINGO)] == ["10:00"]


def test_franjas_sueltas(conn, empleada):
    horarios.agregar_franja_suelta(conn, empleada, LUNES, "12:00")
    assert "12:00" in [f.hora for f in horarios.franjas(conn, LUNES)]
    with pytest.raises(DatoInvalido, match="Ya existe"):
        horarios.agregar_franja_suelta(conn, empleada, LUNES, "09:00")
    _turno(conn, empleada, hora="12:00", pagar=False)
    with pytest.raises(DatoInvalido, match="turnos activos"):
        horarios.quitar_franja_suelta(conn, empleada, LUNES, "12:00")
    with pytest.raises(DatoInvalido, match="plantilla"):
        horarios.quitar_franja_suelta(conn, empleada, LUNES, "09:30")


def test_bloquear_dia_con_turnos_se_rechaza(conn, admin, empleada):
    t = _turno(conn, empleada, pagar=False)
    with pytest.raises(horarios.BloqueoConTurnos) as e:
        horarios.bloquear_dias(conn, admin, LUNES, motivo="Capacitación")
    assert [x["id"] for x in e.value.turnos] == [t]
    assert horarios.franjas(conn, LUNES)  # no se bloqueó nada


def test_bloquear_dia_sin_turnos(conn, admin, empleada):
    assert horarios.bloquear_dias(conn, admin, LUNES, motivo="Festivo") == 1
    assert horarios.franjas(conn, LUNES) == []
    with pytest.raises(DatoInvalido, match="No hay una franja"):
        _turno(conn, empleada, hora="09:00")
    with pytest.raises(DatoInvalido, match="bloqueado"):
        horarios.agregar_franja_suelta(conn, empleada, LUNES, "12:00")
    b = horarios.bloqueos_desde(conn)[0]
    assert b["motivo"] == "Festivo"
    horarios.desbloquear(conn, admin, b["id"])
    assert horarios.franjas(conn, LUNES)


def test_bloquear_rango(conn, admin, empleada):
    assert horarios.bloquear_dias(conn, admin, LUNES, MARTES) == 2
    _turno_otro_dia = (date.fromisoformat(LUNES) + timedelta(days=2)).isoformat()
    t = _turno(conn, empleada, fecha=_turno_otro_dia, pagar=False)
    fin = (date.fromisoformat(LUNES) + timedelta(days=3)).isoformat()
    with pytest.raises(horarios.BloqueoConTurnos):
        horarios.bloquear_dias(conn, admin, LUNES, fin)
    assert t


def test_bloquear_franja(conn, admin, empleada):
    horarios.bloquear_franja(conn, admin, LUNES, "10:00")
    assert "10:00" not in [f.hora for f in horarios.franjas(conn, LUNES)]
    _turno(conn, empleada, hora="10:30", pagar=False)
    with pytest.raises(horarios.BloqueoConTurnos):
        horarios.bloquear_franja(conn, admin, LUNES, "10:30")


def test_plantilla_semanal(conn, admin):
    horarios.fijar_franja_base(conn, admin, 6, "16:30", False)
    sabado = (date.fromisoformat(LUNES) + timedelta(days=5)).isoformat()
    assert "16:30" not in [f.hora for f in horarios.franjas(conn, sabado)]
    horarios.fijar_franja_base(conn, admin, 6, "17:00", True)
    assert "17:00" in [f.hora for f in horarios.franjas(conn, sabado)]


# ============================================================ permisos RN-01

def test_personal_no_bloquea(conn, empleada):
    with pytest.raises(PermisoDenegado):
        horarios.bloquear_dias(conn, empleada, LUNES)
    with pytest.raises(PermisoDenegado):
        horarios.bloquear_franja(conn, empleada, LUNES, "09:00")
    with pytest.raises(PermisoDenegado):
        horarios.fijar_franja_base(conn, empleada, 1, "09:00", False)


def test_personal_no_quita_bloqueo(conn, admin, empleada):
    horarios.bloquear_dias(conn, admin, LUNES)
    with pytest.raises(PermisoDenegado):
        horarios.desbloquear(conn, empleada, horarios.bloqueos_desde(conn)[0]["id"])


def test_agenda_del_dia(conn, empleada):
    t = _turno(conn, empleada, pagar=False)
    ag = st.agenda(conn, empleada, LUNES, ahora=AHORA)
    fila = next(f for f in ag["franjas"] if f["hora"] == "09:00")
    assert fila["turnos"][0]["id"] == t and fila["libres"]["MAQUINA"] == 2
    assert ag["personal_del_dia"] == 3 and ag["bloqueo"] is None
    sabado = (date.fromisoformat(LUNES) + timedelta(days=5)).isoformat()
    assert st.agenda(conn, empleada, sabado, ahora=AHORA)["personal_del_dia"] == 4


def test_categorias_de_dominio():
    assert cupos.cupos_libres({"MAQUINA": 1}, semillas.CONFIG_INICIAL)["MAQUINA"] == 1


# ============================== Ajustes pedidos: verificación, corrección y devolución

def test_personal_verifica_y_confirma_abono_menor(conn, empleada):
    t = _turno(conn, empleada, pagar=False)
    st.registrar_abono(conn, empleada, t, Abono("10.000", "EFECTIVO"), ahora=AHORA, confirmar=True)
    assert _estado(conn, t)["estado"] == "CONFIRMADO"
    detalle = conn.execute("SELECT detalle FROM auditoria WHERE accion='CONFIRMAR_TURNO'").fetchone()[0]
    assert "verificación del personal" in detalle and "$10.000" in detalle


def test_confirmar_con_abono_cero(conn, empleada):
    t = _turno(conn, empleada, pagar=False)
    with pytest.raises(DatoInvalido, match="monto"):
        st.registrar_abono(conn, empleada, t, Abono(0, "EFECTIVO"), ahora=AHORA)
    st.registrar_abono(conn, empleada, t, Abono(0, "EFECTIVO"), ahora=AHORA, confirmar=True)
    assert _estado(conn, t)["estado"] == "CONFIRMADO"
    assert st.abonos(conn, empleada, t) == []  # no se guarda un abono de $0


def test_crear_turno_confirmado_por_verificacion(conn, empleada):
    mid = _mascota(conn, empleada)
    r = st.crear_turno(conn, empleada, mid, "MAQUINA", LUNES, "09:00", empleada.personal_id,
                       Abono(5000, "NEQUI"), ahora=AHORA, confirmar=True)
    assert _estado(conn, r.turnos[0])["estado"] == "CONFIRMADO"


def test_corregir_y_anular_abono(conn, empleada):
    t = _turno(conn, empleada)
    a = st.abonos(conn, empleada, t)[0]
    st.editar_abono(conn, empleada, a["id"], "25.000", "BREB", "Corregido")
    a = st.abonos(conn, empleada, t)[0]
    assert (a["monto"], a["medio"], a["referencia"]) == (25000, "BREB", "Corregido")
    st.editar_abono(conn, empleada, a["id"], 0, "BREB")
    assert st.abonos(conn, empleada, t)[0]["estado"] == "ANULADO"
    assert st.turno(conn, empleada, t)["abonado"] == 0
    with pytest.raises(DatoInvalido, match="vigentes"):
        st.editar_abono(conn, empleada, a["id"], 1000, "BREB")


def test_pago_de_grupo_editable(conn, empleada, cinco):
    _, mascotas = cinco
    items = [(m, "MAQUINA", LUNES, h) for (m, _), h in zip(mascotas[:3], ["09:00", "09:30", "10:00"])]
    r = st.crear_grupo(conn, empleada, items, empleada.personal_id, ahora=AHORA)
    with pytest.raises(DatoInvalido, match="Verifiqué"):
        st.pagar_grupo(conn, empleada, r.turnos[0], Abono(0, "NEQUI"), ahora=AHORA, montos=[20000, 10000, 20000])
    st.pagar_grupo(conn, empleada, r.turnos[0], Abono(0, "NEQUI"), ahora=AHORA, montos=[30000, 10000, 0],
                   confirmar=True)
    filas = st.grupo(conn, empleada, r.turnos[0])
    assert [f["abonado"] for f in filas] == [30000, 10000, 0]
    assert all(f["estado"] == "CONFIRMADO" for f in filas)


def test_crear_grupo_con_montos(conn, empleada, cinco):
    _, mascotas = cinco
    items = [(m, "MAQUINA", LUNES, h) for (m, _), h in zip(mascotas[:2], ["09:00", "09:30"])]
    r = st.crear_grupo(conn, empleada, items, empleada.personal_id, Abono(0, "EFECTIVO"), ahora=AHORA,
                       montos=["20.000", "15.000"], confirmar=True)
    assert [f["abonado"] for f in st.grupo(conn, empleada, r.turnos[0])] == [20000, 15000]


def test_cancelar_y_devolver_con_anticipacion(conn, empleada):
    t = _turno(conn, empleada, hora="09:00")  # AHORA es 07:00 del mismo día: 2 horas antes
    assert st.opciones_cancelacion(conn, empleada, t, ahora=AHORA)["puede_devolver"] is False
    with pytest.raises(DatoInvalido, match="12 horas"):
        st.cancelar(conn, empleada, t, "DEVOLVER", ahora=AHORA)
    assert _estado(conn, t)["estado"] == "CONFIRMADO"  # no se canceló nada
    dia_antes = AHORA - timedelta(days=1)
    assert st.opciones_cancelacion(conn, empleada, t, ahora=dia_antes)["puede_devolver"] is True
    st.cancelar(conn, empleada, t, "DEVOLVER", ahora=dia_antes)
    a = st.abonos(conn, empleada, t)[0]
    assert a["estado"] == "DEVUELTO" and a["devuelto_por"] == empleada.personal_id
    assert st.abonos_a_favor(conn, empleada, st.turno(conn, empleada, t)["propietario_id"]) == []


def test_horas_de_devolucion_configurables(conn, admin, empleada):
    configuracion.guardar(conn, admin, {"horas_minimas_devolucion": "1"})
    t = _turno(conn, empleada, hora="09:00")
    st.cancelar(conn, empleada, t, "DEVOLVER", ahora=AHORA)
    assert st.abonos(conn, empleada, t)[0]["estado"] == "DEVUELTO"


@pytest.mark.parametrize("destino,estado_abono,a_favor", [("DEVOLVER", "DEVUELTO", 0), ("A_FAVOR", "VIGENTE", 1)])
def test_no_atendido_personal_decide_el_abono(conn, empleada, destino, estado_abono, a_favor):
    t = _turno(conn, empleada)
    st.iniciar_atencion(conn, empleada, t)
    st.no_atendido(conn, empleada, t, "ENFERMEDAD_NO_INFORMADA", destino, ahora=AHORA)
    assert st.abonos(conn, empleada, t)[0]["estado"] == estado_abono
    pid = st.turno(conn, empleada, t)["propietario_id"]
    assert len(st.abonos_a_favor(conn, empleada, pid)) == a_favor
