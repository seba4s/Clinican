"""Lectura de la plantilla de importación (.xlsx) con openpyxl.

openpyxl se importa solo dentro de ``leer_filas`` para no cargarlo al iniciar.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from clinican.dominio.errores import DatoInvalido
from clinican.servicios.importacion import InformeImportacion, importar_filas, mapear_encabezados

HOJA = "Mascotas"


def leer_filas(ruta: str | Path) -> list[tuple[int, dict[str, Any]]]:
    """Filas de la hoja Mascotas como (número de fila en Excel, {clave: valor})."""
    import openpyxl  # import perezoso

    ruta = Path(ruta)
    if not ruta.is_file():
        raise DatoInvalido(f"No existe el archivo {ruta}")
    try:
        libro = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    except Exception as error:
        raise DatoInvalido(f"No se pudo abrir {ruta.name} como Excel: {error}") from None
    try:
        hoja = libro[HOJA] if HOJA in libro.sheetnames else libro.worksheets[0]
        filas = hoja.iter_rows(values_only=True)
        encabezados = next(filas, None)
        if encabezados is None:
            raise DatoInvalido("El archivo está vacío")
        mapa = mapear_encabezados(encabezados)
        salida = []
        for numero, valores in enumerate(filas, start=2):
            salida.append((numero, {clave: valores[i] if i < len(valores) else None
                                    for i, clave in mapa.items()}))
        return salida
    finally:
        libro.close()


def importar_mascotas_desde_excel(con, ruta: str | Path, *, ahora: datetime) -> InformeImportacion:
    return importar_filas(con, leer_filas(ruta), ahora=ahora)
