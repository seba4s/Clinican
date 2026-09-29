"""Ventana raíz: decide entre primer arranque, inicio de sesión y ventana principal."""

from __future__ import annotations

import logging
import sqlite3

import customtkinter as ctk

from clinican.servicios import acceso, configuracion, respaldos
from clinican.servicios.base import Sesion
from clinican.ui import tema
from clinican.ui.acceso import PantallaInicioSesion, PantallaPrimerArranque
from clinican.ui.principal import VentanaPrincipal

log = logging.getLogger(__name__)

MS_REVISION_RESPALDO = 60 * 60 * 1000  # cada hora se revisa si ya se hizo el respaldo del día


class AplicacionClinican(ctk.CTk):
    def __init__(self, conn: sqlite3.Connection):
        tema.configurar()
        super().__init__(fg_color=tema.FONDO)
        self.conn = conn
        self.sesion: Sesion | None = None
        self.vista: ctk.CTkFrame | None = None

        self.title("CLINICAN — Peluquería canina")
        self.geometry("1280x800")
        self.minsize(1100, 700)
        tema.poner_icono(self)
        tema.configurar_tablas(self)
        self.protocol("WM_DELETE_WINDOW", self.salir)
        self.report_callback_exception = self._error_no_controlado
        self.after(0, self._maximizar)
        self._revision_respaldo = self.after(MS_REVISION_RESPALDO, self._respaldo_diario)

        self.mostrar_acceso()

    def _maximizar(self) -> None:
        try:
            self.state("zoomed")
        except Exception:
            pass

    def _cambiar_vista(self, nueva: ctk.CTkFrame) -> None:
        if self.vista is not None:
            self.vista.destroy()
        self.vista = nueva
        nueva.pack(fill="both", expand=True)

    def mostrar_acceso(self) -> None:
        self.sesion = None
        config = configuracion.valores(self.conn)
        if acceso.necesita_primer_arranque(self.conn):
            self._cambiar_vista(PantallaPrimerArranque(self, self.conn, config, self._entrar))
        else:
            self._cambiar_vista(PantallaInicioSesion(self, self.conn, config, self._entrar))

    def _entrar(self, sesion: Sesion) -> None:
        self.sesion = sesion
        self._cambiar_vista(VentanaPrincipal(self, self.conn, sesion, self._cerrar_sesion))

    def _cerrar_sesion(self) -> None:
        if self.sesion is not None:
            acceso.cerrar_sesion(self.conn, self.sesion)
        self.mostrar_acceso()

    def _error_no_controlado(self, tipo, valor, traza) -> None:
        log.error("Error no controlado en la interfaz", exc_info=(tipo, valor, traza))
        from clinican.ui import dialogos

        dialogos.error(
            self,
            "Ocurrió un error inesperado. La información ya guardada está segura.\n"
            "Si se repite, avise a quien administra el sistema (queda anotado en datos\\clinican.log).",
        )

    def _respaldo_diario(self) -> None:
        """Sección 10: un respaldo automático al día, aunque el programa no se cierre."""
        try:
            respaldos.diario(self.conn)
        except Exception:
            log.exception("Falló el respaldo diario")
        self._revision_respaldo = self.after(MS_REVISION_RESPALDO, self._respaldo_diario)

    def salir(self) -> None:
        try:
            if self.sesion is not None:
                acceso.cerrar_sesion(self.conn, self.sesion)
        except Exception:
            log.exception("No se pudo registrar el cierre de sesión")
        try:
            respaldos.automatico(self.conn)  # sección 10: respaldo al cerrar
        except Exception as e:
            log.exception("Falló el respaldo al cerrar")
            from clinican.ui import dialogos

            dialogos.error(self, f"No se pudo guardar el respaldo automático al cerrar:\n{e}\n\n"
                                 "Los datos están a salvo en la base de datos. Haga un respaldo manual en cuanto pueda.",
                           titulo="Respaldo no guardado")
        self.destroy()

    def destroy(self):
        if getattr(self, "_revision_respaldo", None):
            self.after_cancel(self._revision_respaldo)
            self._revision_respaldo = None
        super().destroy()
