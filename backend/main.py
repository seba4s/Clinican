"""Raíz de composición de Clinican.

Abre la base (variable CLINICAN_BD o ~/Clinican/clinican.db), la migra, libera
los turnos con abono vencido, elige el canal de notificaciones según la
configuración, arranca el despachador y el respaldo diario y abre la ventana.
Al cerrar hace un respaldo.

    python main.py                 # con interfaz
    python main.py --sin-interfaz  # solo el backend, hasta Ctrl+C
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable

from clinican.adaptadores.notificadores import notificador_para
from clinican.datos.conexion import abrir
from clinican.datos.migraciones import migrar
from clinican.dominio.agenda import ZONA
from clinican.servicios import agenda, configuracion, respaldos
from clinican.servicios.despachador import Despachador

registro = logging.getLogger("clinican")


def reloj() -> datetime:
    """Única fuente de la hora real; todo lo demás la recibe inyectada."""
    return datetime.now(ZONA)


def ruta_base() -> Path:
    valor = os.environ.get("CLINICAN_BD", "").strip()
    return Path(valor) if valor else Path.home() / "Clinican" / "clinican.db"


def main(
    parar: threading.Event | None = None,
    reloj: Callable[[], datetime] = reloj,
    intervalo_despacho: float = 60,
    intervalo_respaldo: float = 3600,
    intervalo_barrido: float = 60,
    interfaz: bool = False,
) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ruta = ruta_base()
    ruta.parent.mkdir(parents=True, exist_ok=True)

    con = abrir(ruta)
    try:
        version = migrar(con)
        liberados = agenda.barrer_vencidos(con, ahora=reloj())
        cfg = configuracion.cargar(con)
    finally:
        con.close()
    registro.info("Base %s en versión %s; %s turnos liberados por abono vencido", ruta, version, len(liberados))

    notificador = notificador_para(cfg.canal_notificaciones, ruta.parent)
    registro.info("Canal de notificaciones: %s", cfg.canal_notificaciones)
    despachador = Despachador(ruta, notificador, reloj=reloj, intervalo_segundos=intervalo_despacho)
    diario = respaldos.RespaldoDiario(ruta, reloj=reloj, intervalo_segundos=intervalo_respaldo)
    despachador.iniciar()
    diario.iniciar()
    parar = parar or threading.Event()

    def barrer() -> None:
        while not parar.wait(intervalo_barrido):
            try:
                con = abrir(ruta)
                try:
                    agenda.barrer_vencidos(con, ahora=reloj())
                finally:
                    con.close()
            except Exception:
                registro.exception("Falló el barrido de abonos vencidos")

    barrido = threading.Thread(target=barrer, name="barrido-abonos", daemon=True)
    barrido.start()
    try:
        if interfaz:
            abrir_interfaz(ruta, reloj, cfg.canal_notificaciones)
        else:
            registro.info("Clinican en marcha. Ctrl+C para salir.")
            while not parar.wait(1):
                pass
    except KeyboardInterrupt:
        registro.info("Cerrando...")
    finally:
        parar.set()
        despachador.detener()
        diario.detener()
        copia = respaldos.crear_respaldo(ruta, ahora=reloj(), motivo="al cerrar")
        registro.info("Respaldo al cerrar: %s", copia)
    return 0


def abrir_interfaz(ruta: Path, reloj: Callable[[], datetime], canal: str) -> None:
    from clinican.adaptadores.importacion_excel import importar_mascotas_desde_excel
    from clinican.ui.app import ejecutar
    from clinican.ui.contexto import Contexto

    ctx = Contexto(
        abrir=lambda: abrir(ruta),
        ruta_db=ruta,
        reloj=reloj,
        importar_excel=lambda con, archivo, ahora: importar_mascotas_desde_excel(con, archivo, ahora=ahora),
        canal=canal,
    )
    ejecutar(ctx)


if __name__ == "__main__":
    raise SystemExit(main(interfaz="--sin-interfaz" not in sys.argv[1:]))
