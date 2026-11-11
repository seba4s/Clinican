"""Pruebas de concurrencia con varias conexiones sobre el mismo archivo.

Invariante: ninguna franja supera su cupo por categoría.
"""

from __future__ import annotations

import threading
from collections import Counter, defaultdict
from datetime import timedelta

from clinican.datos import repo_agenda
from clinican.datos.conexion import abrir
from clinican.dominio.cupos import CategoriaCupo as C
from clinican.dominio.cupos import CuposPorFranja
from clinican.dominio.errores import AbonoRechazado, SinCupo
from clinican.dominio.estados import EstadoTurno as E
from clinican.dominio.turnos import contar_ocupacion
from clinican.servicios import agenda
from clinican.servicios.auditoria import historial
from conftest import AHORA, LUNES, PERFIL, Escenario, a_las

CUPOS = CuposPorFranja()
TIEMPO_MAXIMO = 60


def _franjas(cantidad):
    """Franjas reservables consecutivas desde el lunes (sin domingos)."""
    salida, dia = [], LUNES
    while len(salida) < cantidad:
        if dia.weekday() != 6:
            for i in range(16):
                salida.append(a_las(9, 0, dia) + timedelta(minutes=30 * i))
        dia += timedelta(days=1)
    return salida[:cantidad]


def _en_paralelo(ruta_db, tareas):
    """Corre cada tarea(con) en su propio hilo y conexión, arrancando a la vez."""
    barrera = threading.Barrier(len(tareas))
    resultados = [None] * len(tareas)

    def correr(i, tarea):
        con = abrir(ruta_db)
        try:
            barrera.wait(timeout=TIEMPO_MAXIMO)
            resultados[i] = ("ok", tarea(con))
        except Exception as error:  # se inspecciona en la prueba
            resultados[i] = ("error", error)
        finally:
            con.close()

    hilos = [threading.Thread(target=correr, args=(i, t)) for i, t in enumerate(tareas)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(TIEMPO_MAXIMO)
    assert not any(h.is_alive() for h in hilos), "un hilo quedó colgado"
    return resultados


def _verificar_invariante(con, inicios, ahora=AHORA):
    for inicio in inicios:
        ocupacion = contar_ocupacion(repo_agenda.turnos_en_inicio(con, inicio), ahora, 30)
        for categoria in C:
            assert ocupacion[categoria] <= CUPOS.capacidad(categoria), (
                f"{inicio}: {categoria.name} con {ocupacion[categoria]} turnos"
            )


def test_dos_creaciones_compiten_por_el_ultimo_cupo(con, ruta_db):
    esc = Escenario(con)
    franjas = _franjas(20)
    for inicio in franjas:
        esc.turno(C.MAQUINA, inicio=inicio)  # queda 1 de 2 libre
        a, b = esc.mascota(C.MAQUINA), esc.mascota(C.MAQUINA)
        servicio = PERFIL[C.MAQUINA][2]
        resultados = _en_paralelo(ruta_db, [
            lambda c, m=a.id: agenda.crear_turno(c, m, inicio, servicio, ahora=AHORA),
            lambda c, m=b.id: agenda.crear_turno(c, m, inicio, servicio, ahora=AHORA),
        ])
        tipos = sorted(r[0] for r in resultados)
        assert tipos == ["error", "ok"], resultados
        error = next(r[1] for r in resultados if r[0] == "error")
        assert isinstance(error, SinCupo), repr(error)
    _verificar_invariante(con, franjas)


def test_turno_vence_mientras_se_registra_el_abono(con, ruta_db):
    esc = Escenario(con)
    confirmados = liberados = 0
    for ronda, inicio in enumerate(_franjas(30)):
        creado = AHORA + timedelta(hours=ronda)
        t = esc.turno(C.MAQUINA, inicio=inicio, ahora=creado)
        justo_antes = creado + timedelta(minutes=29, seconds=59)
        justo_despues = creado + timedelta(minutes=30)
        abono, barrido = _en_paralelo(ruta_db, [
            lambda c: agenda.registrar_abono(c, t.id, 20000, ahora=justo_antes),
            lambda c: agenda.barrer_vencidos(c, ahora=justo_despues),
        ])
        final = agenda.obtener_turno(con, t.id)
        liberaciones = [r for r in historial(con, "turno", t.id) if r.accion == "liberar"]
        assert barrido[0] == "ok", barrido
        if abono[0] == "ok":
            # El abono llegó primero: el barrido ya no lo encontró pendiente
            assert final.estado is E.CONFIRMADO and final.abono_pagado == 20000
            assert t.id not in barrido[1] and liberaciones == []
            confirmados += 1
        else:
            # El barrido llegó primero: el abono se rechaza y no queda dinero registrado
            assert isinstance(abono[1], AbonoRechazado), repr(abono[1])
            assert final.estado is E.LIBERADO and final.abono_pagado == 0
            assert t.id in barrido[1] and len(liberaciones) == 1
            liberados += 1
    assert confirmados + liberados == 30


def test_muchos_hilos_en_la_misma_franja(con, ruta_db):
    esc = Escenario(con)
    categorias = [C.MAQUINA] * 3 + [C.GRANDE] * 2 + [C.TIJERA] * 2 + [C.COMPLICADO]
    mascotas = [(esc.mascota(cat).id, cat) for cat in categorias]
    franjas = _franjas(50)
    barrera = threading.Barrier(len(mascotas))
    candado = threading.Lock()
    exitos: dict[int, Counter] = defaultdict(Counter)
    inesperados: list[str] = []

    def trabajador(mascota_id, categoria):
        c = abrir(ruta_db)
        try:
            for ronda, inicio in enumerate(franjas):
                barrera.wait(timeout=TIEMPO_MAXIMO)
                try:
                    agenda.crear_turno(c, mascota_id, inicio, PERFIL[categoria][2], ahora=AHORA)
                    with candado:
                        exitos[ronda][categoria] += 1
                except SinCupo:
                    pass
                except Exception as error:
                    with candado:
                        inesperados.append(repr(error))
        finally:
            c.close()

    hilos = [threading.Thread(target=trabajador, args=m) for m in mascotas]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(TIEMPO_MAXIMO * 5)
    assert not any(h.is_alive() for h in hilos)
    assert inesperados == []
    esperado = Counter({C.MAQUINA: 2, C.GRANDE: 1, C.TIJERA: 1, C.COMPLICADO: 1})
    for ronda in range(len(franjas)):
        assert exitos[ronda] == esperado, (ronda, exitos[ronda])
    _verificar_invariante(con, franjas)
    total = sum(len(repo_agenda.turnos_en_inicio(con, i)) for i in franjas)
    assert total == 5 * len(franjas)
