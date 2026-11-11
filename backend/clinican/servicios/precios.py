"""Casos de uso de precios: el historial solo crece (nunca se borra un precio)."""

from __future__ import annotations

from datetime import date, datetime

from clinican.datos import repo_precios
from clinican.datos.conexion import transaccion
from clinican.dominio.abonos import validar_pesos
from clinican.dominio.cupos import CategoriaCupo
from clinican.dominio.errores import DatoInvalido, NoEncontrado
from clinican.dominio.precios import PrecioHistorico, SinPrecioVigente, formatear_pesos, precio_vigente
from clinican.servicios.auditoria import auditar


def _categoria(valor) -> CategoriaCupo:
    if not isinstance(valor, CategoriaCupo):
        raise DatoInvalido("La categoría debe ser una de: " + ", ".join(c.value for c in CategoriaCupo))
    return valor


def precio_en_fecha(con, categoria: CategoriaCupo, fecha: date) -> int:
    """Precio de la categoría vigente en ``fecha``."""
    try:
        return precio_vigente(repo_precios.historial(con, _categoria(categoria)), fecha, categoria)
    except SinPrecioVigente as error:
        raise NoEncontrado(str(error)) from None


def precios_vigentes(con, fecha: date) -> dict[CategoriaCupo, int]:
    return {c: precio_en_fecha(con, c, fecha) for c in CategoriaCupo}


def historial_precios(con, categoria: CategoriaCupo | None = None) -> list[PrecioHistorico]:
    return repo_precios.historial(con, None if categoria is None else _categoria(categoria))


def cambiar_precio(
    con, categoria: CategoriaCupo, valor: int, vigente_desde: date, *, ahora: datetime
) -> PrecioHistorico:
    """Agrega un precio nuevo al historial a partir de ``vigente_desde``."""
    _categoria(categoria)
    try:
        validar_pesos(valor, "valor")
    except (TypeError, ValueError) as error:
        raise DatoInvalido(str(error)) from None
    if isinstance(vigente_desde, datetime) or not isinstance(vigente_desde, date):
        raise DatoInvalido("vigente_desde debe ser una fecha (sin hora)")
    with transaccion(con):
        existentes = repo_precios.historial(con, categoria)
        if any(p.vigente_desde == vigente_desde for p in existentes):
            raise DatoInvalido(
                f"Ya hay un precio de {categoria.value} desde el {vigente_desde.strftime('%d/%m/%Y')}; "
                "use otra fecha de vigencia"
            )
        repo_precios.insertar(con, categoria, valor, vigente_desde, ahora)
        auditar(con, ahora, "cambiar_precio", "precio", None, categoria=categoria.value,
                valor=valor, valor_texto=formatear_pesos(valor), vigente_desde=vigente_desde.isoformat())
    return PrecioHistorico(vigente_desde, categoria, valor)
