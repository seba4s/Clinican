"""Ayudas de formato que QML llama al escribir (horas en franjas de 30 minutos)."""

from __future__ import annotations

from PySide6.QtCore import QObject, Slot

from clinican.dominio.errores import DatoInvalido
from interfaz.formato import leer_hora

HORAS = [f"{h:02d}:{m:02d}" for h in range(6, 21) for m in (0, 30)]


def normalizar_hora(texto: str) -> str | None:
    """'9' -> '09:00', '4:30 pm' -> '16:30'; None si no se entiende."""
    try:
        return leer_hora(texto).strftime("%H:%M")
    except DatoInvalido:
        return None


def paso_hora(texto: str, sentido: int, horas: list[str] | None = None) -> str:
    """Sube o baja media hora dentro de la lista de franjas (↑ y ↓ en el campo)."""
    horas = list(horas or HORAS)
    actual = normalizar_hora(texto) or ""
    if actual in horas:
        i = max(0, min(len(horas) - 1, horas.index(actual) + sentido))
    else:
        i = 0
    return horas[i]


class Util(QObject):
    """``util`` en QML."""

    @Slot(str, result=str)
    def normalizarHora(self, texto: str) -> str:
        return normalizar_hora(texto) or ""

    @Slot(str, int, "QVariantList", result=str)
    def pasoHora(self, texto: str, sentido: int, horas) -> str:
        return paso_hora(texto, sentido, [str(h) for h in horas] if horas else None)

    @Slot(result="QVariantList")
    def horas(self) -> list[str]:
        return list(HORAS)
