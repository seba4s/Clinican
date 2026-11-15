"""Fechas y horas escritas para personas: «el día de mañana, jueves 8 de octubre (08/10/2026)», «9:00 am».

Los nombres van escritos aquí para no depender del idioma configurado en Windows.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre")


def fecha_larga(dia: date) -> str:
    """``jueves 8 de octubre (08/10/2026)``."""
    return f"{DIAS[dia.weekday()]} {dia.day} de {MESES[dia.month - 1]} ({dia.strftime('%d/%m/%Y')})"


def dia_en_texto(dia: date, hoy: date) -> str:
    """El día del turno visto desde ``hoy``: «hoy, …», «el día de mañana, …» o «el …»."""
    if dia == hoy:
        return f"hoy, {fecha_larga(dia)}"
    if dia == hoy + timedelta(days=1):
        return f"el día de mañana, {fecha_larga(dia)}"
    return f"el {fecha_larga(dia)}"


def hora_en_texto(hora: time | datetime) -> str:
    """Hora de 12 horas: ``9:00 am``, ``12:00 pm``, ``4:30 pm``."""
    sufijo = "am" if hora.hour < 12 else "pm"
    return f"{(hora.hour % 12) or 12}:{hora.minute:02d} {sufijo}"
