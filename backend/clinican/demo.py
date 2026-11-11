"""Demostración en consola con una base temporal:  python -m clinican.demo

1. Capas y dependencias reales del código.
2. El último cupo en disputa entre dos hilos.
3. Agendar sin red mientras el canal falla (los recordatorios quedan con reintento).
4. Cambio de canal de archivo a consola sin tocar la agenda.

Es raíz de composición: puede usar todas las capas.
"""

from __future__ import annotations

import ast
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path

from clinican.adaptadores.notificador_whatsapp import NotificadorWhatsApp
from clinican.adaptadores.notificadores import notificador_para
from clinican.adaptadores.red_simulada import sin_red
from clinican.datos.conexion import abrir
from clinican.datos.migraciones import migrar
from clinican.dominio.agenda import ZONA
from clinican.dominio.cupos import Servicio, Tamano
from clinican.dominio.errores import ErrorNegocio
from clinican.servicios import agenda, clientes, configuracion, consultas
from clinican.servicios.despachador import Despachador

CAPAS = ("dominio", "datos", "servicios", "adaptadores", "ui")
PERMITIDAS = {
    "dominio": set(),
    "datos": {"dominio"},
    "servicios": {"dominio", "datos"},
    "adaptadores": {"dominio", "servicios"},
    "ui": {"dominio", "servicios"},
}
AHORA = datetime(2026, 11, 9, 8, 0, tzinfo=ZONA)  # lunes 8:00 (reloj fijo de la demo)


def _titulo(texto: str) -> None:
    print(f"\n{'=' * 70}\n{texto}\n{'=' * 70}")


def _a_las(hora: int, minuto: int = 0) -> datetime:
    return AHORA.replace(hour=hora, minute=minuto)


# --------------------------------------------------------------------------- 1


def dependencias_reales() -> dict[str, set[str]]:
    raiz = Path(__file__).resolve().parent
    deps = {c: set() for c in CAPAS}
    for capa in CAPAS:
        for archivo in (raiz / capa).rglob("*.py"):
            for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
                nombres = []
                if isinstance(nodo, ast.ImportFrom) and nodo.module and not nodo.level:
                    nombres = [nodo.module]
                elif isinstance(nodo, ast.Import):
                    nombres = [a.name for a in nodo.names]
                for nombre in nombres:
                    partes = nombre.split(".")
                    if partes[0] == "clinican" and len(partes) > 1 and partes[1] in CAPAS and partes[1] != capa:
                        deps[capa].add(partes[1])
    return deps


def seccion_capas() -> None:
    _titulo("1) Capas y dependencias")
    reales = dependencias_reales()
    for capa in CAPAS:
        permitidas = ", ".join(sorted(PERMITIDAS[capa])) or "ninguna"
        usadas = ", ".join(sorted(reales[capa])) or "ninguna"
        estado = "OK" if reales[capa] <= PERMITIDAS[capa] else "VIOLACIÓN"
        print(f"  {capa:<12} puede usar: {permitidas:<22} usa: {usadas:<22} [{estado}]")
    print("  SQL solo en datos/; red solo en adaptadores/ (lo verifica tests/test_arquitectura.py).")


# --------------------------------------------------------------------------- base de la demo


def _preparar(carpeta: Path) -> Path:
    ruta = carpeta / "demo.db"
    con = abrir(ruta)
    try:
        migrar(con)
    finally:
        con.close()
    return ruta


def _mascota(con, nombre: str, celular: str):
    dueno = clientes.crear_propietario(
        con, f"Dueño de {nombre}", celular, cedula=celular[-8:], ahora=AHORA
    )
    return clientes.crear_mascota(con, dueno.id, nombre, tamano=Tamano.MEDIANO, ahora=AHORA)


# --------------------------------------------------------------------------- 2


def seccion_ultimo_cupo(ruta: Path) -> None:
    _titulo("2) Último cupo de máquina a las 9:00, dos hilos a la vez")
    con = abrir(ruta)
    try:
        primero = _mascota(con, "Toby", "3001112233")
        agenda.crear_turno(con, primero.id, _a_las(9), Servicio.CORTE_MAQUINA, ahora=AHORA)
        a = _mascota(con, "Luna", "3002223344")
        b = _mascota(con, "Rocky", "3003334455")
    finally:
        con.close()
    print("  Ya hay 1 de 2 cupos de máquina ocupados. Luna y Rocky lo piden al mismo tiempo...")
    barrera = threading.Barrier(2)
    resultados: dict[str, str] = {}

    def pedir(mascota):
        c = abrir(ruta)
        try:
            barrera.wait()
            t = agenda.crear_turno(c, mascota.id, _a_las(9), Servicio.CORTE_MAQUINA, ahora=AHORA)
            resultados[mascota.nombre] = f"obtuvo el turno #{t.id}"
        except ErrorNegocio as error:
            resultados[mascota.nombre] = f"rechazado: {error}"
        finally:
            c.close()

    hilos = [threading.Thread(target=pedir, args=(m,)) for m in (a, b)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    for nombre in sorted(resultados):
        print(f"  {nombre}: {resultados[nombre]}")


# --------------------------------------------------------------------------- 3


def seccion_sin_red(ruta: Path) -> None:
    _titulo("3) Agendar sin red mientras WhatsApp falla")
    whatsapp = NotificadorWhatsApp(
        entorno={"CLINICAN_WHATSAPP_TOKEN": "demo", "CLINICAN_WHATSAPP_NUMERO_ID": "demo"}
    )
    with sin_red():
        con = abrir(ruta)
        try:
            m = _mascota(con, "Kira", "3004445566")
            t = agenda.crear_turno(con, m.id, _a_las(10), Servicio.BANO, ahora=AHORA)
            t = agenda.registrar_abono(con, t.id, 20000, ahora=AHORA)
            print(f"  Turno #{t.id} de Kira a las 10:00: {t.estado.value} (sin red, sin problema)")
        finally:
            con.close()
        resumen = Despachador(ruta, whatsapp).procesar_una_vez(AHORA)
    con = abrir(ruta)
    try:
        estado = consultas.estado_bandeja(con)
    finally:
        con.close()
    print(f"  Despachador: {resumen.enviadas} enviadas, {resumen.reintentos} con reintento")
    for n in estado.proximas:
        hora = n.programada_para.astimezone(ZONA).strftime("%H:%M")
        print(f"  Recordatorio #{n.id}: intento {n.intentos}, próximo a las {hora}. Error: {n.ultimo_error}")


# --------------------------------------------------------------------------- 4


def seccion_cambio_de_canal(ruta: Path) -> None:
    _titulo("4) Cambio de canal: de archivo a consola")
    con = abrir(ruta)
    try:
        for canal, nombre, celular, hora in (
            ("archivo", "Max", "3005556677", 11),
            ("consola", "Nala", "3006667788", 12),
        ):
            configuracion.guardar(con, "canal_notificaciones", canal, ahora=AHORA)
            m = _mascota(con, nombre, celular)
            t = agenda.crear_turno(con, m.id, _a_las(hora), Servicio.CORTE_TIJERA, ahora=AHORA)
            agenda.registrar_abono(con, t.id, 20000, ahora=AHORA)
            elegido = configuracion.cargar(con).canal_notificaciones
            notificador = notificador_para(elegido, ruta.parent)
            print(f"  Canal configurado: {elegido} -> {type(notificador).__name__}")
            # El recordatorio de Kira (sección 3) no sale aquí: su reintento aún no llega.
            Despachador(ruta, notificador).procesar_una_vez(AHORA + timedelta(seconds=1))
            if canal == "archivo":
                lineas = (ruta.parent / "recordatorios.txt").read_text(encoding="utf-8").splitlines()
                print(f"  recordatorios.txt -> {lineas[-1]}")
    finally:
        con.close()
    print("  La agenda no cambió: solo cambió el valor de configuración.")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="clinican_demo_") as carpeta:
        ruta = _preparar(Path(carpeta))
        seccion_capas()
        seccion_ultimo_cupo(ruta)
        seccion_sin_red(ruta)
        seccion_cambio_de_canal(ruta)
    print("\nDemo terminada.")


if __name__ == "__main__":
    main()
