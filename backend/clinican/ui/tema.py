"""Colores, letra y medidas de la interfaz (ver docs/diseno-interfaz.md).

Cada color es una pareja (modo claro, modo oscuro): CustomTkinter elige según
el modo de Windows. Contrastes medidos con WCAG sobre la superficie de cada modo.
"""

from __future__ import annotations

import tkinter.font as tkfont

import customtkinter as ctk

from clinican.dominio.estados import EstadoTurno

Color = tuple[str, str]

FONDO: Color = ("#F5F6F2", "#1B1A21")
SUPERFICIE: Color = ("#FFFFFF", "#25232C")
SUPERFICIE_SUAVE: Color = ("#F5F6F2", "#2E2C36")  # bloques dentro de una tarjeta
TINTA: Color = ("#14121D", "#F2F1F5")  # 18,5:1 / 13,8:1
TINTA_SUAVE: Color = ("#5B5966", "#ADABB8")  # 6,9:1 / 6,9:1
BORDE_CAMPO: Color = ("#7A7D72", "#8E8C99")  # 4,2:1 / 4,7:1
BORDE: Color = ("#DEDFD8", "#3A3842")  # solo decorativo
ACCION: Color = ("#C4006C", "#C4006C")  # botón principal; texto blanco 5,9:1
ACCION_HOVER: Color = ("#A3005A", "#DB1A85")
PELIGRO: Color = ("#B00020", "#FF7A8E")  # 7,3:1 / 6,2:1
ENLACE: Color = ("#087F97", "#5FD3EA")  # 4,7:1 / 8,9:1
SELECCION_FONDO: Color = TINTA  # sección activa: invertida
SELECCION_TEXTO: Color = ("#FFFFFF", "#14121D")
HOVER_NEUTRO: Color = ("#ECEDE8", "#34323C")
VELO = ("#14121D", "#000000")

# Estado del turno -> (fondo, texto, borde, texto corto, ícono). Siempre se muestra el texto.
ESTADOS: dict[EstadoTurno, tuple[Color, Color, Color, str, str]] = {
    EstadoTurno.PENDIENTE_ABONO: (("#FFF0D9", "#3D2A0E"), ("#8A4600", "#FFC56B"), ("#F0C98A", "#6B4A16"), "Falta abono", "◷"),
    EstadoTurno.CONFIRMADO: (("#EEF4D6", "#2A3311"), ("#4D5E12", "#C9DE7A"), ("#C9D98F", "#4A5A1E"), "Confirmado", "✓"),
    EstadoTurno.EN_ATENCION: (("#DDF4FA", "#0E3540"), ("#06657A", "#7FDBEE"), ("#9ED9E6", "#1E5A68"), "En atención", "✂"),
    EstadoTurno.ATENDIDO: (("#B7CF53", "#B7CF53"), ("#14121D", "#14121D"), ("#9DB33C", "#9DB33C"), "Listo para entregar", "●"),
    EstadoTurno.ENTREGADO: (("#EFEFEC", "#33313A"), ("#5B5966", "#ADABB8"), ("#DEDFD8", "#45434D"), "Entregado", "→"),
    EstadoTurno.LIBERADO: (("#EFEFEC", "#33313A"), ("#5B5966", "#ADABB8"), ("#DEDFD8", "#45434D"), "Cupo liberado", "–"),
    EstadoTurno.CANCELADO: (("#EFEFEC", "#33313A"), ("#5B5966", "#ADABB8"), ("#DEDFD8", "#45434D"), "Cancelado", "–"),
    EstadoTurno.INASISTENCIA: (("#EFEFEC", "#33313A"), ("#5B5966", "#ADABB8"), ("#DEDFD8", "#45434D"), "Inasistencia", "–"),
}

# Medidas (px). Windows pide 32 px como mínimo cómodo; usamos 40.
ALTO_CONTROL = 40
RADIO = 8
RADIO_TARJETA = 12
SEP = 12

TITULO = 28
SUBTITULO = 20
CUERPO = 15
ETIQUETA = 13

_familia: str | None = None


def familia() -> str:
    """Segoe UI Variable si existe (Windows 11), si no Segoe UI o la del sistema."""
    global _familia
    if _familia is None:
        disponibles = set(tkfont.families())
        for nombre in ("Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI"):
            if nombre in disponibles:
                _familia = nombre
                break
        else:
            _familia = "TkDefaultFont"
    return _familia


def fuente(tamano: int = CUERPO, negrita: bool = False) -> ctk.CTkFont:
    return ctk.CTkFont(family=familia(), size=tamano, weight="bold" if negrita else "normal")


def configurar() -> None:
    """Sigue el modo claro u oscuro de Windows."""
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")


def estilo_estado(estado: EstadoTurno) -> tuple[Color, Color, Color, str, str]:
    return ESTADOS[estado]
