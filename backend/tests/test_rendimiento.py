"""Rendimiento sobre cinco años de datos sintéticos (marcadas como `lento`)."""

import time as reloj_real
from datetime import date, datetime, timedelta

import pytest

from clinican.datos.conexion import abrir
from clinican.dominio.agenda import ZONA
from clinican.dominio.cupos import Servicio
from clinican.servicios import agenda, clientes, consultas, respaldos
from generador import generar

pytestmark = pytest.mark.lento

DIA = date(2026, 11, 6)  # viernes con datos
AHORA = datetime(2026, 11, 6, 7, 0, tzinfo=ZONA)


@pytest.fixture(scope="module")
def base_cinco_anios(tmp_path_factory):
    ruta = tmp_path_factory.mktemp("cinco_anios") / "clinica.db"
    inicio = reloj_real.perf_counter()
    resumen = generar(ruta, anios=5)
    segundos = reloj_real.perf_counter() - inicio
    print(f"\n[rendimiento] generación de 5 años: {segundos:.1f} s, {resumen}, "
          f"{ruta.stat().st_size / 1e6:.1f} MB")
    assert resumen.turnos > 40000
    return ruta


def _medir(funcion):
    inicio = reloj_real.perf_counter()
    resultado = funcion()
    return resultado, reloj_real.perf_counter() - inicio


def test_agenda_del_dia_en_menos_de_1_segundo(base_cinco_anios):
    con = abrir(base_cinco_anios)
    try:
        dia, segundos = _medir(lambda: consultas.agenda_del_dia(con, DIA, ahora=AHORA))
        print(f"\n[rendimiento] agenda del día: {segundos * 1000:.1f} ms")
        assert sum(len(f.turnos) for f in dia) == 30
        assert segundos < 1
        _, segundos = _medir(lambda: agenda.disponibilidad(con, DIA, ahora=AHORA))
        print(f"[rendimiento] disponibilidad del día: {segundos * 1000:.1f} ms")
        assert segundos < 1
    finally:
        con.close()


def test_operaciones_frecuentes_rapidas(base_cinco_anios):
    con = abrir(base_cinco_anios)
    try:
        dueno = clientes.crear_propietario(con, "Nuevo", "3119998877", cedula="99999999", ahora=AHORA)
        m = clientes.crear_mascota(con, dueno.id, "Rex", tamano=clientes.Tamano.MEDIANO, ahora=AHORA)
        lunes = datetime(2026, 11, 9, 9, 0, tzinfo=ZONA)
        tiempos = {}
        _, tiempos["crear turno"] = _medir(
            lambda: agenda.crear_turno(con, m.id, lunes, Servicio.CORTE_MAQUINA, ahora=AHORA)
        )
        _, tiempos["barrer vencidos"] = _medir(lambda: agenda.barrer_vencidos(con, ahora=AHORA))
        _, tiempos["historial de mascota"] = _medir(lambda: consultas.historial_de_mascota(con, 1))
        _, tiempos["pendientes de abono"] = _medir(lambda: consultas.pendientes_de_abono(con, ahora=AHORA))
        _, tiempos["estado de la bandeja"] = _medir(lambda: consultas.estado_bandeja(con))
        _, tiempos["buscar propietario"] = _medir(lambda: clientes.buscar_propietarios(con, "3000001"))
        for nombre, segundos in tiempos.items():
            print(f"[rendimiento] {nombre}: {segundos * 1000:.1f} ms")
            assert segundos < 1, nombre
    finally:
        con.close()


def test_restaurar_cinco_anios_en_menos_de_10_minutos(base_cinco_anios, tmp_path):
    from clinican.datos.migraciones import migrar

    actual = tmp_path / "actual.db"
    c = abrir(actual)
    migrar(c)
    c.close()
    _, segundos = _medir(
        lambda: respaldos.restaurar(actual, base_cinco_anios, ahora=AHORA + timedelta(days=1))
    )
    print(f"\n[rendimiento] restaurar 5 años: {segundos:.1f} s")
    assert segundos < 600
    con = abrir(actual)
    try:
        assert con.execute("SELECT COUNT(*) FROM turnos").fetchone()[0] > 40000
        assert con.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    finally:
        con.close()
    _, segundos = _medir(lambda: respaldos.crear_respaldo(actual, ahora=AHORA + timedelta(days=2)))
    print(f"[rendimiento] respaldo verificado de 5 años: {segundos:.1f} s")
    assert segundos < 600
