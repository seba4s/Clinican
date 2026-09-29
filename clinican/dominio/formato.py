"""Formatos para mostrar valores en pantalla (pesos colombianos, fechas)."""

from __future__ import annotations

import re
import unicodedata


def pesos(valor: int | str | None) -> str:
    """45000 -> "$45.000"."""
    if valor is None or valor == "":
        return "—"
    numero = int(valor)
    signo = "-" if numero < 0 else ""
    return f"{signo}${abs(numero):,}".replace(",", ".")


def rellenar_texto(plantilla: str, valores: dict[str, str]) -> str:
    """Reemplaza marcadores {clave} con valores de configuración.

    Los montos se muestran con formato de pesos. Un marcador desconocido
    se deja tal cual, para no romper el texto legal.
    """

    def _reemplazo(m: re.Match) -> str:
        clave = m.group(1)
        if clave not in valores:
            return m.group(0)
        valor = valores[clave]
        if clave in ("abono_minimo", "desenredado_sesion") or clave.startswith(("precio_", "extra_bano_")):
            return pesos(valor)
        return valor

    return re.sub(r"\{([a-zA-Z0-9_]+)\}", _reemplazo, plantilla)


def sin_tildes(texto: str | None) -> str | None:
    """"Ángela Núñez" -> "angela nunez". Se usa para buscar sin importar tildes."""
    if texto is None:
        return None
    descompuesto = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in descompuesto if not unicodedata.combining(c)).lower()


_RE_ENTERO = re.compile(r"^\$?\s*(\d+|\d{1,3}(\.\d{3})+)$")


def entero_pesos(texto, etiqueta: str = "El valor") -> int:
    """Acepta "45000", "45.000" y "$45.000" (el punto separa miles en Colombia)."""
    from clinican.dominio.errores import DatoInvalido

    texto = str(texto if texto is not None else "").strip()
    if not _RE_ENTERO.match(texto):
        raise DatoInvalido(f"{etiqueta} debe ser un número entero sin decimales, por ejemplo 45000.")
    return int(texto.replace("$", "").replace(".", "").strip())
