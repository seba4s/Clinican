"""Punto de entrada de CLINICAN."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler


def _configurar_registro() -> None:
    from clinican import rutas

    rutas.carpeta_datos().mkdir(parents=True, exist_ok=True)
    manejador = RotatingFileHandler(
        rutas.carpeta_datos() / "clinican.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    manejador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[manejador])


def _identidad_windows() -> None:
    """Hace que la barra de tareas muestre el icono del perro y no el de Python."""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Clinican.Peluqueria")
        except Exception:
            pass


def main() -> int:
    _configurar_registro()
    _identidad_windows()
    log = logging.getLogger("clinican")

    from clinican import rutas
    from clinican.datos.conexion import conectar
    from clinican.ui.app import AplicacionClinican

    try:
        conn = conectar(rutas.ruta_bd())
    except Exception as e:
        log.exception("No se pudo abrir la base de datos")
        import tkinter.messagebox as mb

        mb.showerror("CLINICAN", f"No se pudo abrir la base de datos:\n{rutas.ruta_bd()}\n\n{e}")
        return 1

    log.info("CLINICAN iniciado. Base de datos: %s", rutas.ruta_bd())
    from clinican.servicios import turnos

    liberados = turnos.expirar_vencidos(conn)  # RN-07: también al iniciar
    if liberados:
        log.info("Turnos liberados por vencimiento al iniciar: %s", liberados)
    try:
        AplicacionClinican(conn).mainloop()
    finally:
        conn.close()
        log.info("CLINICAN cerrado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
