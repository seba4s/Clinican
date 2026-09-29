"""Roles y permisos (sección 4 de la especificación, regla RN-01).

Esta tabla es la única fuente de verdad. La capa de servicios la consulta
antes de cada acción; la interfaz solo la usa para ocultar botones.
"""

from __future__ import annotations

from enum import Enum

ADMIN = "ADMIN"
PERSONAL = "PERSONAL"
ROLES = (ADMIN, PERSONAL)


class Accion(str, Enum):
    AGENDAR_TURNOS = "Agendar, editar y cancelar turnos"
    REGISTRAR_ABONOS = "Registrar abonos"
    GESTIONAR_PROPIETARIOS = "Crear y editar propietarios y mascotas"
    GESTIONAR_FICHAS = "Llenar y editar fichas de servicio"
    AJUSTAR_FRANJAS_SUELTAS = "Agregar o quitar franjas sueltas libres de una fecha"
    BLOQUEAR_DIAS = "Desactivar un día completo o un rango de fechas"
    BLOQUEAR_FRANJAS = "Desactivar franjas específicas no agendadas de una fecha"
    GESTIONAR_PERSONAL = "Agregar, editar, desactivar personal; cambiar PIN de otros"
    CAMBIAR_CONFIGURACION = "Cambiar precios, cupos, horarios base y valor del abono"
    EDITAR_TEXTOS_LEGALES = "Editar textos legales"
    RESPALDAR = "Respaldar"
    RESTAURAR = "Restaurar un respaldo"
    VER_AUDITORIA = "Ver el registro de auditoría"
    CAMBIAR_PIN_PROPIO = "Cambiar su propio PIN"


_SOLO_ADMIN = {
    Accion.BLOQUEAR_DIAS,
    Accion.BLOQUEAR_FRANJAS,
    Accion.GESTIONAR_PERSONAL,
    Accion.CAMBIAR_CONFIGURACION,
    Accion.EDITAR_TEXTOS_LEGALES,
    Accion.RESTAURAR,
    Accion.VER_AUDITORIA,
}

PERMISOS: dict[str, frozenset[Accion]] = {
    ADMIN: frozenset(Accion),
    PERSONAL: frozenset(set(Accion) - _SOLO_ADMIN),
}


def puede(rol: str, accion: Accion) -> bool:
    return accion in PERMISOS.get(rol, frozenset())
