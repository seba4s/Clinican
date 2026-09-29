"""Códigos internos y su nombre en pantalla."""

from __future__ import annotations

TAMANOS = {"PEQUENA": "Pequeña", "MEDIANA": "Mediana", "GRANDE": "Grande"}

ESPECIES = {"PERRO": "Perro", "GATO": "Gato"}

TIPOS_LEGALES = {
    "TERMINOS": "Términos y condiciones",
    "DATOS": "Autorización de tratamiento de datos",
    "RESPONSABILIDAD": "Responsabilidad por mascota difícil",
}

# Condiciones difíciles (RN-15 y ficha de servicio): columna -> texto
CONDICIONES = {
    "cond_agresiva": "Agresiva",
    "cond_nudos_extremos": "Pelo con nudos extremos",
    "cond_problemas_piel": "Problemas de piel",
    "cond_plagas": "Pulgas u otras plagas",
    "cond_edad_avanzada": "Edad avanzada",
}


TIPOS_SERVICIO = {
    "MAQUINA": "Corte a máquina",
    "TIJERA": "Corte con tijera",
    "BANO_DESLANADO": "Baño y deslanado",
}

ESTADOS_SERVICIO = {
    "PLANEADO": "Planeado",
    "REVISION_ESTILISTA": "En revisión de la estilista",
    "EN_SESIONES": "En sesiones de desenredado",
    "REALIZADO": "Realizado",
    "CANCELADO": "Cancelado",
}


def nombre_tamano(codigo: str | None) -> str:
    return TAMANOS.get(codigo or "", "Sin definir")


def codigo_tamano(texto: str | None) -> str | None:
    """Acepta el código o el nombre ("Pequeña", "pequena", "PEQUEÑA")."""
    from clinican.dominio.formato import sin_tildes

    if not texto:
        return None
    limpio = sin_tildes(texto.strip()).upper()
    return limpio if limpio in TAMANOS else None
