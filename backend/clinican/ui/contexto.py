"""Lo que la interfaz recibe de la raíz de composición (main.py).

La interfaz no abre la base ni conoce los adaptadores: recibe una función que
abre una conexión, el reloj y, si existe, el importador de Excel.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Iterator


@dataclass
class Contexto:
    abrir: Callable[[], Any]
    ruta_db: Path
    reloj: Callable[[], datetime]
    importar_excel: Callable[[Any, Path, datetime], Any] | None = None
    canal: str = ""

    @contextmanager
    def con(self) -> Iterator[Any]:
        conexion = self.abrir()
        try:
            yield conexion
        finally:
            conexion.close()

    def ahora(self) -> datetime:
        return self.reloj()

    def hoy(self) -> date:
        from clinican.ui.formato import local

        return local(self.reloj()).date()
