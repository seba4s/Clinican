"""Categoría de cupo (RN-02) y cupos por franja (RN-03, [A-1], [A-2])."""

from __future__ import annotations

from clinican.dominio.errores import DatoInvalido

CATEGORIAS = {
    "MAQUINA": "Máquina",
    "GRANDE": "Grande",
    "TIJERA": "Tijera",
    "COMPLICADO": "Complicado",
}

# Estados que ocupan cupo. Los pendientes de abono NO ocupan: gana quien paga primero (RN-08).
OCUPAN_CUPO = ("CONFIRMADO", "EN_PROCESO", "LISTA")


def categoria_cupo(pelaje_complicado: bool, tipo_servicio: str, tamano: str, config: dict[str, str]) -> str:
    """RN-02, en este orden: complicado, tijera, grande, y en otro caso máquina [A-1]."""
    if pelaje_complicado:
        return "COMPLICADO"
    if tipo_servicio == "TIJERA":
        return "TIJERA"
    if tamano == "GRANDE":
        return "GRANDE"
    if tamano == "PEQUENA" and config.get("pequenas_en_cupo_maquina", "1") != "1":
        raise DatoInvalido(
            "La configuración [A-1] indica que las mascotas pequeñas no usan el cupo MÁQUINA y no hay otra "
            "regla definida. Revise Configuración › Supuestos por confirmar."
        )
    return "MAQUINA"


def cupos_configurados(config: dict[str, str]) -> dict[str, int]:
    return {c: int(config.get(f"cupo_{c}", "0")) for c in CATEGORIAS}


def cupos_libres(ocupados: dict[str, int], config: dict[str, str]) -> dict[str, int]:
    """Cupos libres por categoría en una franja.

    [A-2] Con cupos independientes (valor 1) cada categoría tiene su propio cupo.
    Si se desactiva (valor 0), una franja atiende una sola categoría a la vez:
    cuando ya hay mascotas de una categoría, las demás quedan en 0.
    """
    cupos = cupos_configurados(config)
    libres = {c: max(cupos[c] - ocupados.get(c, 0), 0) for c in CATEGORIAS}
    if config.get("cupos_independientes", "1") != "1":
        usadas = [c for c in CATEGORIAS if ocupados.get(c, 0) > 0]
        if usadas:
            libres = {c: (libres[c] if c in usadas else 0) for c in CATEGORIAS}
    return libres


def hay_cupo(ocupados: dict[str, int], categoria: str, config: dict[str, str]) -> bool:
    return cupos_libres(ocupados, config)[categoria] > 0
