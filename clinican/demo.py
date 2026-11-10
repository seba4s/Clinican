"""Demostración del esqueleto de punta a punta, sin ventanas: ``python -m clinican.demo``.

Recorre las capas con una base de datos temporal y muestra, en este orden:

1. La estructura: capas y hacia dónde apuntan sus dependencias (ADR-001).
2. D2 · Integridad de la agenda: dos turnos pelean el último cupo; gana quien paga (ADR-002).
3. D1 · Sin conexión: el canal falla, el recordatorio espera y la agenda sigue (ADR-003).
4. D3 · Cambiar de canal: el mismo recordatorio sale por otro adaptador sin tocar la agenda.

Igual que ``main.py``, este archivo es una raíz de composición: arma las piezas y elige
los adaptadores. No contiene reglas de negocio.
"""

from __future__ import annotations

import ast
import logging
import sys
import tempfile
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from clinican.adaptadores import NotificadorArchivo, NotificadorConsola
from clinican.datos.conexion import conectar
from clinican.datos.migraciones import VERSION_ACTUAL
from clinican.dominio.errores import ErrorClinican
from clinican.servicios import acceso, horarios, legal, notificaciones, razas
from clinican.servicios import propietarios as sp
from clinican.servicios import turnos
from clinican.servicios.notificaciones import ErrorEnvio
from clinican.servicios.turnos import Abono

RAIZ = Path(__file__).resolve().parent
CAPAS = ("ui", "servicios", "adaptadores", "datos", "dominio")


def titulo(texto: str) -> None:
    print(f"\n{'=' * 78}\n{texto}\n{'=' * 78}")


def paso(texto: str) -> None:
    print(f"  · {texto}")


# ----------------------------------------------------------------- 1 · capas

def dependencias_reales() -> dict[str, set[str]]:
    """Lee el código y cuenta qué capa importa a cuál (lo mismo que verifica la prueba)."""
    usa: dict[str, set[str]] = defaultdict(set)
    for capa in CAPAS:
        for ruta in (RAIZ / capa).rglob("*.py"):
            for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
                modulos = []
                if isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
                    modulos = [nodo.module]
                elif isinstance(nodo, ast.Import):
                    modulos = [a.name for a in nodo.names]
                for m in modulos:
                    partes = m.split(".")
                    if partes[0] == "clinican" and len(partes) > 1 and partes[1] in CAPAS and partes[1] != capa:
                        usa[capa].add(partes[1])
    return usa


def mostrar_capas() -> None:
    titulo("1 · ESTRUCTURA: capas y dependencias, leídas del código fuente (ADR-001)")
    usa = dependencias_reales()
    for capa in CAPAS:
        destinos = ", ".join(sorted(usa.get(capa, ()))) or "nada (Python puro)"
        print(f"  {capa:<12} depende de → {destinos}")
    prohibidas = [("ui", "datos"), ("ui", "adaptadores"), ("servicios", "ui"), ("servicios", "adaptadores"),
                  ("adaptadores", "datos")] + [("dominio", c) for c in CAPAS if c != "dominio"]
    atajos = [f"{a} → {b}" for a, b in prohibidas if b in usa.get(a, ())]
    print(f"\n  Atajos prohibidos encontrados: {', '.join(atajos) if atajos else 'ninguno'}")
    paso("La prueba automática equivalente es: python -m pytest tests/test_arquitectura.py")


# ----------------------------------------------------------- datos de ejemplo

def proximo_dia_habil() -> date:
    dia = date.today() + timedelta(days=7)
    while dia.weekday() == 6:  # domingo cerrado
        dia += timedelta(days=1)
    return dia


def preparar(carpeta: Path):
    ruta = carpeta / "demo.db"
    conn = conectar(ruta)
    paso(f"Base temporal {ruta.name}: esquema en la versión {VERSION_ACTUAL} (migraciones 1 a {VERSION_ACTUAL}).")
    admin = acceso.crear_administradora_inicial(conn, "Angela", "Jefe", "1234")
    labrador = next(r["id"] for r in razas.listar(conn) if r["nombre"] == "Labrador Retriever")

    def cliente(nombre, cedula, celular, mascota):
        pid = sp.crear(conn, admin, nombre, cedula, celular, None, "Pasto")
        legal.aceptar(conn, admin, pid, ["TERMINOS", "DATOS"])  # Ley 1581: autorización para contactarlo
        return sp.crear_mascota(conn, admin, pid, mascota, labrador)

    return conn, ruta, admin, cliente("Ana Gómez", "1085000001", "3001112233", "Toby"), \
        cliente("Luis Rosero", "1085000002", "3004445566", "Max")


# ------------------------------------------------------------ 2 · integridad

def demostrar_integridad(conn, admin, toby, max_, dia: date, ahora: datetime) -> int:
    titulo("2 · D2 INTEGRIDAD DE LA AGENDA: el último cupo GRANDE de las 10:00 (ADR-002)")
    fecha = dia.isoformat()
    paso(f"Cupos libres a las 10:00 del {fecha}: GRANDE = {horarios.cupos_libres(conn, fecha, '10:00')['GRANDE']}")
    a = turnos.crear_turno(conn, admin, toby, "MAQUINA", fecha, "10:00", admin.personal_id, ahora=ahora).turnos[0]
    b = turnos.crear_turno(conn, admin, max_, "MAQUINA", fecha, "10:00", admin.personal_id, ahora=ahora).turnos[0]
    paso(f"Toby y Max (labradores, categoría GRANDE) quedan PENDIENTES DE ABONO en la misma franja (turnos {a} y {b}).")
    r = turnos.registrar_abono(conn, admin, b, Abono(20000, "NEQUI"), ahora=ahora + timedelta(minutes=3))
    paso("Max paga primero: dentro de una sola transacción (BEGIN IMMEDIATE) se vuelve a contar el cupo y se confirma.")
    for t in r.liberados:
        paso(f"El otro pendiente pasa a {t['estado']} con motivo {t['motivo_liberacion']}: el cupo no se sobrevende.")
    try:
        turnos.registrar_abono(conn, admin, a, Abono(20000, "NEQUI"), ahora=ahora + timedelta(minutes=5))
    except ErrorClinican as e:
        paso(f"Si ahora pagan por Toby, el sistema lo rechaza: «{e}»")
    paso(f"Cupos libres GRANDE a las 10:00: {horarios.cupos_libres(conn, fecha, '10:00')['GRANDE']} (ocupación = cupo).")
    return b


# --------------------------------------------------------------- 3 · sin red

class SinConexion:
    """Simula un canal sin internet: cualquier canal que falle se comporta igual."""

    nombre = "WHATSAPP (sin red)"

    def enviar(self, mensaje):
        raise ErrorEnvio("no hay conexión a internet")


def estado_bandeja(conn, turno_id: int) -> str:
    fila = next(f for f in notificaciones.bandeja(conn) if f["turno_id"] == turno_id)
    extra = f", intentos {fila['intentos']}, último error: {fila['ultimo_error']}" if fila["ultimo_error"] else ""
    return f"{fila['estado']}{extra}"


def demostrar_sin_red(conn, admin, turno_id: int, dia: date, ahora: datetime) -> None:
    titulo("3 · D1 DISPONIBILIDAD SIN CONEXIÓN: la agenda no espera a la red (ADR-003)")
    paso(f"Al confirmarse, el recordatorio del turno {turno_id} quedó en la bandeja de salida, en la misma transacción.")
    paso(f"Bandeja: {estado_bandeja(conn, turno_id)}")
    momento = ahora + timedelta(hours=8)
    notificaciones.despachar(conn, SinConexion(), ahora=momento)
    paso(f"El despachador intenta enviar sin internet → {estado_bandeja(conn, turno_id)}")
    hora = next(f.hora for f in horarios.franjas(conn, dia.isoformat()) if f.hora != "10:00")
    otro = sp.crear_mascota(conn, admin, sp.crear(conn, admin, "Sara Díaz", "1085000003", "3007778899", None, "Pasto"),
                            "Luna", next(r["id"] for r in razas.listar(conn) if r["nombre"] == "Shih Tzu"))
    t = turnos.crear_turno(conn, admin, otro, "MAQUINA", dia.isoformat(), hora, admin.personal_id,
                           Abono(20000, "EFECTIVO"), ahora=momento).turnos[0]
    paso(f"Mientras tanto la recepción sigue agendando: turno {t} de Luna a las {hora}, confirmado. Nada esperó a la red.")
    paso("(Sara, la dueña de Luna, todavía no firmó la autorización de datos: se verá en el paso 4.)")


# ------------------------------------------------------------- 4 · otro canal

def demostrar_cambio_de_canal(conn, turno_id: int, carpeta: Path, ahora: datetime) -> None:
    titulo("4 · D3 MODIFICABILIDAD: el mismo recordatorio por otros canales, sin tocar la agenda")
    vuelve = ahora + timedelta(hours=9)
    archivo = NotificadorArchivo(carpeta / "recordatorios.txt")
    r = notificaciones.despachar(conn, archivo, ahora=vuelve)
    paso(f"Vuelve la conexión y el despachador usa el adaptador {archivo.nombre}: {len(r.enviados)} enviado(s); "
         f"{len(r.descartados)} descartado(s).")
    for _f, motivo in r.descartados:
        paso(f"El recordatorio de Luna no se envía (Ley 1581): {motivo}")
    paso(f"Bandeja del turno {turno_id}: {estado_bandeja(conn, turno_id)}")
    print("  " + archivo.ruta.read_text(encoding="utf-8").strip().splitlines()[0])

    class NotificadorSMS:
        """Un canal nuevo escrito aquí mismo: solo cumple el puerto (nombre + enviar)."""

        nombre = "SMS"

        def enviar(self, mensaje):
            print(f"  [sms simulado] a +{mensaje.destino}: {mensaje.texto[:70]}…")

    print()
    paso("Ahora se cambia a un canal que no existía (SMS) y a la consola. La agenda y el dominio no cambian.")
    for canal in (NotificadorSMS(), NotificadorConsola()):
        notificaciones.reprogramar(conn, turno_id, ahora)  # como si el turno se hubiera movido
        notificaciones.despachar(conn, canal, ahora=vuelve)


def main() -> int:
    logging.getLogger("clinican").setLevel(logging.ERROR)  # la demo muestra los fallos por pantalla
    print("CLINICAN · esqueleto funcional · demostración de la arquitectura")
    mostrar_capas()
    with tempfile.TemporaryDirectory(prefix="clinican_demo_") as tmp:
        carpeta = Path(tmp)
        titulo("PREPARACIÓN")
        conn, _ruta, admin, toby, max_ = preparar(carpeta)
        dia = proximo_dia_habil()
        ahora = datetime.combine(dia - timedelta(days=1), datetime.min.time()).replace(hour=9)
        paso(f"Reloj de la demostración: {ahora:%Y-%m-%d %H:%M} (un día antes de los turnos).")
        try:
            turno = demostrar_integridad(conn, admin, toby, max_, dia, ahora)
            demostrar_sin_red(conn, admin, turno, dia, ahora)
            demostrar_cambio_de_canal(conn, turno, carpeta, ahora)
        finally:
            conn.close()
    titulo("FIN · las cuatro partes corrieron sobre las mismas capas: ui no participó y no hizo falta")
    return 0


if __name__ == "__main__":
    sys.exit(main())
