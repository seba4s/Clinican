"""Cálculo de precios (RN-12). Todos los valores vienen de la tabla config.

- precio mínimo = mínimo por tamaño; con tijera, max(mínimo por tamaño, tijera_total_min).
  El corte con tijera NO se suma al base.
- extras = baños extra × valor del extra según tamaño, si hay baño medicado o antipulgas.
  Un mismo baño puede ser medicado y antipulgas a la vez: se cobra una vez por baño.
- total = precio final + extras. Si el precio final es menor al mínimo, se advierte pero se permite.
- Las sesiones de desenredado se cobran aparte (RN-13) y se suman en la ficha.
"""

from __future__ import annotations

from dataclasses import dataclass

from clinican.dominio.catalogos import TAMANOS, TIPOS_SERVICIO
from clinican.dominio.errores import DatoInvalido


def _valor(config: dict[str, str], clave: str) -> int:
    try:
        return int(config[clave])
    except (KeyError, ValueError):
        raise DatoInvalido(f"Falta o es inválido el valor de configuración «{clave}».") from None


def precio_minimo(tamano: str, tipo_servicio: str, config: dict[str, str]) -> int:
    if tamano not in TAMANOS:
        raise DatoInvalido("La mascota no tiene un tamaño válido.")
    if tipo_servicio not in TIPOS_SERVICIO:
        raise DatoInvalido("Tipo de servicio no válido.")
    minimo = _valor(config, f"precio_min_{tamano}")
    if tipo_servicio == "TIJERA":
        return max(minimo, _valor(config, "tijera_total_min"))
    return minimo


def extras(tamano: str, bano_medicado: bool, bano_antipulgas: bool, cantidad_banos: int, config: dict[str, str]) -> int:
    if not (bano_medicado or bano_antipulgas):
        return 0
    if cantidad_banos < 1:
        raise DatoInvalido("La cantidad de baños extra debe ser al menos 1.")
    return cantidad_banos * _valor(config, f"extra_bano_{tamano}")


def total(precio_final: int | None, valor_extras: int) -> int | None:
    if precio_final is None:
        return None
    return precio_final + valor_extras


@dataclass(frozen=True)
class Liquidacion:
    precio_minimo: int
    precio_final: int | None
    extras: int
    total: int | None
    desenredado: int
    advertencia: str | None

    @property
    def gran_total(self) -> int | None:
        """Total del servicio más las sesiones de desenredado."""
        if self.total is None:
            return self.desenredado or None
        return self.total + self.desenredado


def liquidar(
    tamano: str,
    tipo_servicio: str,
    precio_final: int | None,
    bano_medicado: bool,
    bano_antipulgas: bool,
    cantidad_banos: int,
    desenredado: int,
    config: dict[str, str],
) -> Liquidacion:
    minimo = precio_minimo(tamano, tipo_servicio, config)
    if precio_final is not None and precio_final < 0:
        raise DatoInvalido("El precio final no puede ser negativo.")
    valor_extras = extras(tamano, bano_medicado, bano_antipulgas, cantidad_banos, config)
    advertencia = None
    if precio_final is not None and precio_final < minimo:
        from clinican.dominio.formato import pesos

        advertencia = f"El precio final ({pesos(precio_final)}) es menor que el mínimo sugerido ({pesos(minimo)})."
    return Liquidacion(minimo, precio_final, valor_extras, total(precio_final, valor_extras), desenredado, advertencia)
