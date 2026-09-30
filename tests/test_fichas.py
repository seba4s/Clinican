"""Fase 3: precios (RN-12), ficha de servicio y desenredado (RN-13)."""

from datetime import date, timedelta

import pytest

from clinican.datos import semillas
from clinican.dominio import precios
from clinican.dominio.errores import DatoInvalido, PermisoDenegado
from clinican.dominio.ficha import DetallesFicha
from clinican.servicios import configuracion, fichas
from clinican.servicios import propietarios as sp

CONFIG = semillas.CONFIG_INICIAL
HOY = date.today().isoformat()
AYER = (date.today() - timedelta(days=1)).isoformat()


# ------------------------------------------------------- precios (dominio)

@pytest.mark.parametrize(
    "tamano,maquina,tijera",
    [("PEQUENA", 45000, 50000), ("MEDIANA", 50000, 50000), ("GRANDE", 60000, 60000)],
)
def test_precio_minimo_por_tamano(tamano, maquina, tijera):
    """Criterio de aceptación: coinciden con la sección 5.2."""
    assert precios.precio_minimo(tamano, "MAQUINA", CONFIG) == maquina
    assert precios.precio_minimo(tamano, "BANO_DESLANADO", CONFIG) == maquina
    assert precios.precio_minimo(tamano, "TIJERA", CONFIG) == tijera


def test_tijera_no_se_suma_al_base():
    config = {**CONFIG, "tijera_total_min": "55000"}
    assert precios.precio_minimo("PEQUENA", "TIJERA", config) == 55000  # no 45000 + 55000
    assert precios.precio_minimo("GRANDE", "TIJERA", config) == 60000


@pytest.mark.parametrize("tamano,extra", [("PEQUENA", 5000), ("MEDIANA", 10000), ("GRANDE", 10000)])
def test_extras_de_bano_por_tamano(tamano, extra):
    assert precios.extras(tamano, True, False, 1, CONFIG) == extra
    assert precios.extras(tamano, False, True, 2, CONFIG) == 2 * extra
    assert precios.extras(tamano, True, True, 1, CONFIG) == extra  # un baño medicado y antipulgas
    assert precios.extras(tamano, False, False, 3, CONFIG) == 0


def test_total_y_advertencia():
    liq = precios.liquidar("PEQUENA", "MAQUINA", 40000, True, False, 1, 120000, CONFIG)
    assert liq.precio_minimo == 45000 and liq.extras == 5000 and liq.total == 45000
    assert liq.advertencia and "menor" in liq.advertencia  # se advierte, no se bloquea
    assert liq.gran_total == 165000
    sin_precio = precios.liquidar("GRANDE", "TIJERA", None, False, False, 1, 0, CONFIG)
    assert sin_precio.total is None and sin_precio.advertencia is None


def test_precios_vienen_de_config(conn, admin):
    configuracion.guardar(conn, admin, {"precio_min_MEDIANA": "52000"})
    assert precios.precio_minimo("MEDIANA", "MAQUINA", configuracion.valores(conn)) == 52000


# ------------------------------------------------------------ ficha (dominio)

@pytest.mark.parametrize(
    "kwargs,mensaje",
    [
        (dict(tipo_servicio="TIJERA", largo_maquina="1CM"), "largo"),
        (dict(tipo_servicio="MAQUINA", largo_maquina=None, forma_cara="REDONDA"), "corte bajito"),
        (dict(tipo_servicio="TIJERA", cola_leon=1, cola_estilo="COMPLETA"), "corte bajito"),
        (dict(tipo_servicio="MAQUINA", largo_maquina="1CM", cola_leon=0, cola_estilo="AL_RAS"), "cola de león"),
        (dict(tipo_servicio="MAQUINA", bano_medicado=True, cantidad_banos_extra=0), "baños extra"),
        (dict(tipo_servicio="CEPILLADO"), "tipo de servicio"),
    ],
)
def test_ficha_invalida(kwargs, mensaje):
    with pytest.raises(DatoInvalido, match=mensaje):
        DetallesFicha(**kwargs).validar()


def test_ficha_corte_bajito_valida():
    d = DetallesFicha(tipo_servicio="MAQUINA", largo_maquina="MEDIO_CM", copete=1, barbas=0, cola_leon=1,
                      cola_estilo="AL_RAS", forma_cara="PAREJA_AL_CUERPO", condiciones={"cond_plagas": True}).validar()
    cols = d.columnas()
    assert cols["cola_estilo"] == "AL_RAS" and cols["cond_plagas"] == 1 and cols["cond_agresiva"] == 0


# --------------------------------------------------------- servicio (datos)

_cedulas = iter(range(10_000_000, 99_999_999))


def _mascota(conn, sesion, raza="Shih Tzu", **kw):
    raza_id = conn.execute("SELECT id FROM razas WHERE nombre = ?", (raza,)).fetchone()[0]
    pid = sp.crear(conn, sesion, "María", str(next(_cedulas)), "3012345678", None, "Calle 1")
    return sp.crear_mascota(conn, sesion, pid, "Toby", raza_id, **kw)


def test_crear_ficha_calcula_precios(conn, empleada):
    mid = _mascota(conn, empleada)
    sid = fichas.crear(conn, empleada, mid, HOY, DetallesFicha("TIJERA", bano_antipulgas=True, cantidad_banos_extra=2))
    s = fichas.obtener(conn, empleada, sid)
    assert (s["precio_minimo"], s["extras"], s["total"], s["estado"]) == (50000, 10000, None, "PLANEADO")
    liq = fichas.editar(conn, empleada, sid, HOY, DetallesFicha("TIJERA", bano_antipulgas=True, cantidad_banos_extra=2),
                        precio_final="55.000")
    assert liq.total == 65000 and liq.advertencia is None
    liq = fichas.editar(conn, empleada, sid, HOY, DetallesFicha("TIJERA"), precio_final="48000")
    assert liq.total == 48000 and liq.advertencia  # menor al mínimo: advierte pero guarda
    assert fichas.obtener(conn, empleada, sid)["precio_final"] == 48000


def test_mestizo_usa_su_tamano(conn, empleada):
    mid = _mascota(conn, empleada, "Perro mestizo (sin raza)", tamano_manual="GRANDE", pelaje_manual=0)
    sid = fichas.crear(conn, empleada, mid, HOY, DetallesFicha("MAQUINA", bano_medicado=True))
    s = fichas.obtener(conn, empleada, sid)
    assert (s["precio_minimo"], s["extras"]) == (60000, 10000)


def test_calculo_en_vivo(conn, empleada):
    mid = _mascota(conn, empleada, "Labrador Retriever")
    liq = fichas.calcular(conn, empleada, mid, "BANO_DESLANADO", "70.000", True, False, 1)
    assert (liq.precio_minimo, liq.extras, liq.total) == (60000, 10000, 80000)


def test_realizado_requiere_precio_y_bloquea_cambios(conn, empleada):
    mid = _mascota(conn, empleada)
    sid = fichas.crear(conn, empleada, mid, HOY, DetallesFicha("MAQUINA", largo_maquina="1CM"))
    with pytest.raises(DatoInvalido, match="precio final"):
        fichas.cambiar_estado(conn, empleada, sid, "REALIZADO")
    fichas.editar(conn, empleada, sid, HOY, DetallesFicha("MAQUINA", largo_maquina="1CM"), precio_final=45000)
    fichas.cambiar_estado(conn, empleada, sid, "REALIZADO")
    # En una ficha realizada solo se corrigen precio y observaciones
    fichas.editar(conn, empleada, sid, HOY, DetallesFicha("TIJERA", observaciones="Se portó bien"), precio_final=47000)
    s = fichas.obtener(conn, empleada, sid)
    assert (s["tipo_servicio"], s["precio_final"], s["total"], s["observaciones"]) == ("MAQUINA", 47000, 47000, "Se portó bien")
    with pytest.raises(DatoInvalido):
        fichas.cambiar_estado(conn, empleada, sid, "PLANEADO")


def test_cancelada_no_se_edita(conn, empleada):
    sid = fichas.crear(conn, empleada, _mascota(conn, empleada), HOY, DetallesFicha("MAQUINA"))
    fichas.cambiar_estado(conn, empleada, sid, "CANCELADO")
    with pytest.raises(DatoInvalido, match="cancelada"):
        fichas.editar(conn, empleada, sid, HOY, DetallesFicha("MAQUINA"), 45000)


# ------------------------------------------------------------ desenredado

@pytest.fixture
def en_sesiones(conn, empleada):
    sid = fichas.crear(conn, empleada, _mascota(conn, empleada), HOY,
                       DetallesFicha("TIJERA", condiciones={"cond_nudos_extremos": True}))
    fichas.cambiar_estado(conn, empleada, sid, "REVISION_ESTILISTA")
    fichas.cambiar_estado(conn, empleada, sid, "EN_SESIONES")
    return sid


def test_una_sola_sesion_por_dia(conn, empleada, en_sesiones):
    """Criterio de aceptación: una sola sesión por día por servicio."""
    fichas.registrar_sesion(conn, empleada, en_sesiones, HOY)
    with pytest.raises(DatoInvalido, match="Máximo una por día"):
        fichas.registrar_sesion(conn, empleada, en_sesiones, HOY)
    fichas.registrar_sesion(conn, empleada, en_sesiones, AYER, notas="Primera parte")
    assert [s["fecha"] for s in fichas.sesiones(conn, empleada, en_sesiones)] == [AYER, HOY]
    liq = fichas.liquidacion(conn, en_sesiones)
    assert liq.desenredado == 120000


def test_restriccion_unica_en_base_de_datos(conn, empleada, en_sesiones):
    import sqlite3

    conn.execute("INSERT INTO sesiones_desenredado (servicio_id, fecha, precio) VALUES (?, ?, 60000)", (en_sesiones, HOY))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO sesiones_desenredado (servicio_id, fecha, precio) VALUES (?, ?, 60000)", (en_sesiones, HOY))


def test_sesion_usa_precio_de_config_y_no_futura(conn, admin, empleada, en_sesiones):
    configuracion.guardar(conn, admin, {"desenredado_sesion": "65000"})
    fichas.registrar_sesion(conn, empleada, en_sesiones)
    assert fichas.sesiones(conn, empleada, en_sesiones)[0]["precio"] == 65000
    manana = (date.today() + timedelta(days=1)).isoformat()
    with pytest.raises(DatoInvalido, match="futura"):
        fichas.registrar_sesion(conn, empleada, en_sesiones, manana)


def test_sesion_requiere_estado_en_sesiones(conn, empleada):
    sid = fichas.crear(conn, empleada, _mascota(conn, empleada), HOY, DetallesFicha("TIJERA"))
    with pytest.raises(DatoInvalido, match="sesiones de desenredado"):
        fichas.registrar_sesion(conn, empleada, sid, HOY)


def test_cerrar_sesiones_con_servicio_final(conn, empleada, en_sesiones):
    with pytest.raises(DatoInvalido, match="al menos una sesión"):
        fichas.cerrar_sesiones(conn, empleada, en_sesiones, "MAQUINA")
    fichas.registrar_sesion(conn, empleada, en_sesiones, AYER)
    fichas.registrar_sesion(conn, empleada, en_sesiones, HOY)
    fichas.cerrar_sesiones(conn, empleada, en_sesiones, "MAQUINA")
    s = fichas.obtener(conn, empleada, en_sesiones)
    assert (s["estado"], s["tipo_servicio"], s["precio_minimo"]) == ("PLANEADO", "MAQUINA", 45000)
    liq = fichas.editar(conn, empleada, en_sesiones, HOY, DetallesFicha("MAQUINA", largo_maquina="1CM"), 45000)
    assert liq.gran_total == 45000 + 120000
    with pytest.raises(DatoInvalido, match="desenredado en curso"):
        fichas.cerrar_sesiones(conn, empleada, en_sesiones, None)


def test_cerrar_sin_servicio_final(conn, empleada, en_sesiones):
    fichas.registrar_sesion(conn, empleada, en_sesiones, HOY)
    fichas.cerrar_sesiones(conn, empleada, en_sesiones, None)
    s = fichas.obtener(conn, empleada, en_sesiones)
    assert (s["estado"], s["total"]) == ("REALIZADO", 0)
    assert fichas.liquidacion(conn, en_sesiones).gran_total == 60000


def test_anular_sesion(conn, empleada, en_sesiones):
    nueva = fichas.registrar_sesion(conn, empleada, en_sesiones, HOY)
    fichas.anular_sesion(conn, empleada, nueva)
    assert fichas.sesiones(conn, empleada, en_sesiones) == []
    fichas.registrar_sesion(conn, empleada, en_sesiones, HOY)  # se puede volver a registrar


def test_un_desenredado_a_la_vez_por_mascota(conn, empleada, en_sesiones):
    mid = fichas.obtener(conn, empleada, en_sesiones)["mascota_id"]
    otra = fichas.crear(conn, empleada, mid, HOY, DetallesFicha("TIJERA"))
    fichas.cambiar_estado(conn, empleada, otra, "REVISION_ESTILISTA")
    with pytest.raises(DatoInvalido, match="en curso"):
        fichas.cambiar_estado(conn, empleada, otra, "EN_SESIONES")


def test_salir_de_sesiones_solo_cerrando(conn, empleada, en_sesiones):
    with pytest.raises(DatoInvalido, match="Cerrar sesiones"):
        fichas.cambiar_estado(conn, empleada, en_sesiones, "PLANEADO")


def test_fichas_requieren_sesion(conn, empleada):
    mid = _mascota(conn, empleada)
    with pytest.raises(PermisoDenegado):
        fichas.crear(conn, None, mid, HOY, DetallesFicha("MAQUINA"))


def test_historial_muestra_ficha(conn, empleada, en_sesiones):
    fichas.registrar_sesion(conn, empleada, en_sesiones, HOY)
    mid = fichas.obtener(conn, empleada, en_sesiones)["mascota_id"]
    h = sp.historial(conn, empleada, mid)
    assert h[0]["id"] == en_sesiones and h[0]["desenredado"] == 60000


# ------------------------------------------------------ corbatín y moños

def test_corbatin_y_monos_con_color(conn, empleada):
    mid = _mascota(conn, empleada)
    d = DetallesFicha("MAQUINA", corbatin=1, corbatin_color="  rojo ", monos=1, monos_color="Rosado")
    sid = fichas.crear(conn, empleada, mid, HOY, d)
    s = fichas.obtener(conn, empleada, sid)
    assert (s["corbatin"], s["corbatin_color"], s["monos"], s["monos_color"]) == (1, "Rojo", 1, "Rosado")
    # Si se quita el accesorio, el color no se guarda
    fichas.editar(conn, empleada, sid, HOY, DetallesFicha("MAQUINA", corbatin=0, corbatin_color="Rojo", monos=1))
    s = fichas.obtener(conn, empleada, sid)
    assert (s["corbatin"], s["corbatin_color"], s["monos"], s["monos_color"]) == (0, None, 1, None)


def test_color_demasiado_largo():
    with pytest.raises(DatoInvalido, match="color"):
        DetallesFicha("MAQUINA", monos=1, monos_color="x" * 41).validar()


def test_campos_del_formato_de_clinican(conn, empleada):
    """Despunte, patas rasuradas, desparasitación, bigotes y orejas, como en la ficha de Excel."""
    mid = _mascota(conn, empleada, sexo="MACHO")
    assert sp.mascota(conn, empleada, mid)["sexo"] == "MACHO"
    d = DetallesFicha("TIJERA", despunte=True, patas_rasuradas=True, desparasitacion=True, bigotes=1, orejas=0)
    s = fichas.obtener(conn, empleada, fichas.crear(conn, empleada, mid, HOY, d))
    assert (s["despunte"], s["patas_rasuradas"], s["desparasitacion"], s["bigotes"], s["orejas"]) == (1, 1, 1, 1, 0)
    with pytest.raises(DatoInvalido, match="sexo"):
        _mascota(conn, empleada, sexo="OTRO")
