"""Colores, letra y medidas de la interfaz (ver docs/diseno-interfaz.md).

Cada color es una pareja (modo claro, modo oscuro): la interfaz QML elige según
el modo de Windows (ver interfaz/puentes/tema.py). Contrastes medidos con WCAG sobre la superficie de cada modo.
"""

from __future__ import annotations

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

# Hoja de la agenda (encabezado verde de la marca, como la fila de títulos de Excel).
VERDE: Color = ("#B7CF53", "#B7CF53")
VERDE_LINEA: Color = ("#9DB33C", "#9DB33C")
TINTA_SOBRE_VERDE: Color = ("#14121D", "#14121D")
FONDO_HORA: Color = ("#EEF4D6", "#252D10")
FONDO_SELECCION: Color = ("#FCE4F1", "#3B1D30")
LINEA: Color = ("#DEDFD8", "#3A3842")

# Franja de aviso dentro de la ventana.
AVISO_OK: Color = ("#EEF4D6", "#2A3311")
AVISO_ERROR: Color = ("#FDE7EA", "#3A1E24")

# Vidrio (#AARRGGBB): paneles translúcidos sobre el fondo desenfocado. Bastante opacos
# para que los contrastes medidos sobre la superficie sigan valiendo.
VIDRIO: Color = ("#C8FFFFFF", "#B825232C")
VIDRIO_FUERTE: Color = ("#E6FFFFFF", "#E025232C")  # diálogos y menús
VIDRIO_BRILLO: Color = ("#FFFFFFFF", "#33FFFFFF")  # filo de luz del borde superior
VIDRIO_BORDE: Color = ("#14000000", "#1FFFFFFF")
SOMBRA: Color = ("#22000000", "#66000000")
MANCHA_1: Color = ("#55FE028D", "#40FE028D")  # fucsia de la marca, solo decorativo
MANCHA_2: Color = ("#66B7CF53", "#38B7CF53")  # lima de la marca, solo decorativo
MANCHA_3: Color = ("#4D5FD3EA", "#335FD3EA")

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

def estilo_estado(estado: EstadoTurno) -> tuple[Color, Color, Color, str, str]:
    return ESTADOS[estado]
