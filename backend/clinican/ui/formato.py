"""Textos para mostrar: dinero, fechas, horas y celulares, en español."""

from __future__ import annotations

import re
from datetime import date, datetime, time

from clinican.dominio.agenda import ZONA
from clinican.dominio.cupos import CategoriaCupo, Servicio, Tamano
from clinican.dominio.errores import DatoInvalido
from clinican.dominio.precios import formatear_pesos

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

CATEGORIA = {
    CategoriaCupo.MAQUINA: "Máquina",
    CategoriaCupo.GRANDE: "Grande",
    CategoriaCupo.TIJERA: "Tijera",
    CategoriaCupo.COMPLICADO: "Complicado",
}
SERVICIO = {
    Servicio.CORTE_MAQUINA: "Corte a máquina",
    Servicio.CORTE_TIJERA: "Corte a tijera",
    Servicio.BANO: "Baño",
    Servicio.DESENREDADO: "Desenredado",
}
TAMANO = {
    Tamano.MINI: "mini",
    Tamano.PEQUENO: "pequeño",
    Tamano.MEDIANO: "mediano",
    Tamano.GRANDE: "grande",
}


def pesos(valor: int) -> str:
    return formatear_pesos(int(valor))


def leer_pesos(texto: str) -> int:
    """'$15.000', '15000' o '15 000' -> 15000. Vacío -> 0."""
    limpio = re.sub(r"[\s$.]", "", texto or "")
    if not limpio:
        return 0
    if not limpio.isdigit():
        raise DatoInvalido("Escribe el valor en pesos, solo con números (por ejemplo 20000)")
    return int(limpio)


def local(momento: datetime) -> datetime:
    return momento.astimezone(ZONA)


def hora(momento: datetime) -> str:
    return local(momento).strftime("%H:%M")


def dia_largo(dia: date) -> str:
    """'Martes 11 de noviembre'."""
    return f"{DIAS[dia.weekday()].capitalize()} {dia.day} de {MESES[dia.month - 1]}"


def dia_corto(dia: date, hoy: date | None = None) -> str:
    """'Hoy', 'Mañana', 'Ayer' o '28 oct' (con año si no es el actual)."""
    if hoy is not None:
        diferencia = (dia - hoy).days
        if diferencia == 0:
            return "Hoy"
        if diferencia == 1:
            return "Mañana"
        if diferencia == -1:
            return "Ayer"
    texto = f"{dia.day} {MESES_CORTOS[dia.month - 1]}"
    if hoy is not None and dia.year != hoy.year:
        texto += f" {dia.year}"
    return texto


def momento(m: datetime, hoy: date | None = None) -> str:
    """'Hoy 10:30' o '28 oct 10:30'."""
    return f"{dia_corto(local(m).date(), hoy)} {hora(m)}"


def fecha_numerica(dia: date) -> str:
    return dia.strftime("%d/%m/%Y")


def leer_fecha(texto: str) -> date:
    """'dd/mm/aaaa' -> date."""
    try:
        return datetime.strptime(texto.strip(), "%d/%m/%Y").date()
    except ValueError:
        raise DatoInvalido("Escribe la fecha como dd/mm/aaaa, por ejemplo 01/12/2026") from None


def celular(texto: str) -> str:
    """'3005551234' -> '300 555 1234'."""
    d = re.sub(r"\D", "", texto or "")
    return f"{d[:3]} {d[3:6]} {d[6:]}" if len(d) == 10 else (texto or "")


def cedula(texto: str | None) -> str:
    if not texto:
        return "sin cédula"
    d = re.sub(r"\D", "", texto)
    if not d:
        return texto
    return "CC " + f"{int(d):,}".replace(",", ".")


def minutos_restantes(hasta: datetime, ahora: datetime) -> str:
    segundos = (hasta - ahora).total_seconds()
    if segundos <= 0:
        return "vencido"
    minutos = int(segundos // 60) + (1 if segundos % 60 else 0)
    return f"vence en {minutos} min"


def leer_hora(texto: str) -> time:
    """Hora escrita a mano en una franja de 30 minutos.

    Acepta '9', '9:30', '09.30', '930', '16:30', '4:30 pm' o '4 p. m.'.
    """
    limpio = (texto or "").strip().lower().replace(" ", "").replace(".", ":")
    tarde = limpio.endswith(("pm", "p:m:", "p:m"))
    manana = limpio.endswith(("am", "a:m:", "a:m"))
    limpio = re.sub(r"[ap]:?m:?$", "", limpio).rstrip(":").replace("h", ":")
    m = re.fullmatch(r"(\d{1,2})(?::?(\d{2}))?", limpio)
    if not m:
        raise DatoInvalido("Escribe la hora como 09:30 (o 9:30, 930, 4:30 pm)")
    hora_, minuto = int(m.group(1)), int(m.group(2) or 0)
    if tarde and hora_ < 12:
        hora_ += 12
    elif manana and hora_ == 12:
        hora_ = 0
    if hora_ > 23 or minuto > 59:
        raise DatoInvalido(f"«{texto.strip()}» no es una hora válida")
    if minuto not in (0, 30):
        raise DatoInvalido("Las franjas son de 30 minutos: usa :00 o :30")
    return time(hora_, minuto)
