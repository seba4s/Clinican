"""Estados del turno y reglas de tiempo (RN-05, RN-07, RN-10, RN-16, RN-17)."""

from __future__ import annotations

from datetime import datetime, timedelta

from clinican.dominio.errores import DatoInvalido

FORMATO = "%Y-%m-%d %H:%M:%S"

PENDIENTE = "PENDIENTE_ABONO"
CONFIRMADO = "CONFIRMADO"
EN_PROCESO = "EN_PROCESO"
LISTA = "LISTA"
ATENDIDO = "ATENDIDO"
LIBERADO = "LIBERADO"
NO_ASISTIO_AVISO = "NO_ASISTIO_AVISO"
NO_ASISTIO_SIN_AVISO = "NO_ASISTIO_SIN_AVISO"
NO_ATENDIDO = "NO_ATENDIDO"

ESTADOS = {
    PENDIENTE: "Pendiente de abono",
    CONFIRMADO: "Confirmado",
    EN_PROCESO: "En proceso",
    LISTA: "Lista para entregar",
    ATENDIDO: "Atendido",
    LIBERADO: "Liberado",
    NO_ASISTIO_AVISO: "No asistió (avisó a tiempo)",
    NO_ASISTIO_SIN_AVISO: "No asistió (sin aviso a tiempo)",
    NO_ATENDIDO: "No se pudo atender",
}

ACTIVOS = (PENDIENTE, CONFIRMADO, EN_PROCESO, LISTA)

MOTIVOS_LIBERACION = {"EXPIRO": "Venció el plazo del abono", "OTRO_PAGO_PRIMERO": "Otro cliente pagó primero",
                      "MANUAL": "Cancelado"}
MOTIVOS_NO_ATENDIDO = {"AGRESIVIDAD": "Agresividad", "CONDUCTA": "Problemas de conducta",
                       "ENFERMEDAD_NO_INFORMADA": "Enfermedad no informada"}
MEDIOS_PAGO = {"NEQUI": "Nequi", "BREB": "Llave Bre-B", "EFECTIVO": "Efectivo"}
ESTADOS_ABONO = {"VIGENTE": "Vigente", "APLICADO": "Aplicado al cobro", "PERDIDO": "Perdido",
                 "DEVUELTO": "Devuelto", "ANULADO": "Anulado"}

# Qué pasa con el abono al cancelar o cuando no se pudo atender
A_FAVOR = "A_FAVOR"
DEVOLVER = "DEVOLVER"

TRANSICIONES = {
    PENDIENTE: {CONFIRMADO, LIBERADO},
    CONFIRMADO: {EN_PROCESO, LIBERADO, NO_ASISTIO_AVISO, NO_ASISTIO_SIN_AVISO, NO_ATENDIDO},
    EN_PROCESO: {LISTA, NO_ATENDIDO},
    LISTA: {ATENDIDO},
}


def validar_transicion(actual: str, nuevo: str) -> None:
    if nuevo not in TRANSICIONES.get(actual, set()):
        raise DatoInvalido(f"No se puede pasar el turno de «{ESTADOS[actual]}» a «{ESTADOS[nuevo]}».")


def texto(momento: datetime) -> str:
    return momento.strftime(FORMATO)


def leer(valor: str) -> datetime:
    return datetime.strptime(valor[:19], FORMATO)


def inicio_turno(fecha: str, hora: str) -> datetime:
    return datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")


def pendiente_hasta(ahora: datetime, minutos: int) -> str:
    """RN-05 y RN-07: plazo para pagar el abono."""
    return texto(ahora + timedelta(minutes=minutos))


def vencido(pendiente_hasta_txt: str | None, ahora: datetime) -> bool:
    return pendiente_hasta_txt is not None and leer(pendiente_hasta_txt) <= ahora


def segundos_restantes(pendiente_hasta_txt: str, ahora: datetime) -> int:
    return max(int((leer(pendiente_hasta_txt) - ahora).total_seconds()), 0)


def estado_no_asistencia(fecha: str, hora: str, avisado_en: datetime | None, horas_minimas: int) -> str:
    """RN-10: con aviso de al menos ``horas_minimas`` horas de anticipación → avisó a tiempo."""
    if avisado_en is None:
        return NO_ASISTIO_SIN_AVISO
    anticipacion = inicio_turno(fecha, hora) - avisado_en
    return NO_ASISTIO_AVISO if anticipacion >= timedelta(hours=horas_minimas) else NO_ASISTIO_SIN_AVISO


def leer_fecha_hora(textos: str, etiqueta: str = "La fecha y hora") -> datetime:
    """Acepta "AAAA-MM-DD HH:MM" (o con segundos)."""
    t = (textos or "").strip()
    for formato in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(t, formato)
        except ValueError:
            continue
    raise DatoInvalido(f"{etiqueta} no es válida. Use AAAA-MM-DD HH:MM, por ejemplo 2026-03-26 18:00.")


def puede_devolver(fecha: str, hora: str, ahora: datetime, horas_minimas: int) -> bool:
    """[A-10] Al cancelar, el abono se puede devolver si faltan al menos ``horas_minimas`` para el turno."""
    return inicio_turno(fecha, hora) - ahora >= timedelta(hours=horas_minimas)
