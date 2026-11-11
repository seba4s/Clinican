"""Raíz de composición del backend de Clinican (sin interfaz).

Abre la base (variable CLINICAN_BD o ~/Clinican/clinican.db), la migra, libera
los turnos con abono vencido, elige el canal de notificaciones según la
configuración, arranca el despachador y el respaldo diario, y queda corriendo
hasta Ctrl+C. Al cerrar hace un respaldo.

    python main.py
"""

from __future__ import annotations

import logging
import os
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
    registro.info("Clinican en marcha. Ctrl+C para salir.")

    parar = parar or threading.Event()
    ultimo_barrido = reloj()
    try:
        while not parar.wait(1):
            if (reloj() - ultimo_barrido).total_seconds() >= intervalo_barrido:
                ultimo_barrido = reloj()
                con = abrir(ruta)
                try:
                    agenda.barrer_vencidos(con, ahora=ultimo_barrido)
                finally:
                    con.close()
    except KeyboardInterrupt:
        registro.info("Cerrando...")
    finally:
        despachador.detener()
        diario.detener()
        copia = respaldos.crear_respaldo(ruta, ahora=reloj(), motivo="al cerrar")
        registro.info("Respaldo al cerrar: %s", copia)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
