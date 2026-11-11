"""Respaldos de la base: copia verificada, rotación, respaldo diario y restauración.

Las copias se guardan en ``carpeta_respaldos`` (configuración; si es relativa,
se toma junto a la base) con nombre ``clinican_AAAAMMDD_HHMMSS.db``. Se conservan
las últimas ``respaldos_a_conservar`` (30 por defecto).
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable

from clinican.datos import respaldos as datos_respaldos
from clinican.datos.conexion import abrir, transaccion
from clinican.datos.migraciones import MIGRACIONES, BaseMasNueva, migrar
from clinican.dominio.agenda import ZONA
from clinican.dominio.errores import DatoInvalido, NoEncontrado
from clinican.servicios import configuracion
from clinican.servicios.auditoria import auditar

registro = logging.getLogger(__name__)

PREFIJO = "clinican_"
FORMATO = "%Y%m%d_%H%M%S"


def carpeta_de(ruta_db: str | Path, carpeta_config: str) -> Path:
    carpeta = Path(carpeta_config)
    return carpeta if carpeta.is_absolute() else Path(ruta_db).resolve().parent / carpeta


def _config(ruta_db) -> tuple[Path, int]:
    con = abrir(ruta_db)
    try:
        cfg = configuracion.cargar(con)
    finally:
        con.close()
    return carpeta_de(ruta_db, cfg.carpeta_respaldos), cfg.respaldos_a_conservar


def _fecha_de(ruta: Path) -> datetime | None:
    try:
        return datetime.strptime(ruta.stem[len(PREFIJO):len(PREFIJO) + 15], FORMATO)
    except ValueError:
        return None


def listar_respaldos(carpeta: str | Path) -> list[Path]:
    """Copias de la carpeta, de la más antigua a la más reciente."""
    carpeta = Path(carpeta)
    if not carpeta.is_dir():
        return []
    copias = [p for p in carpeta.glob(f"{PREFIJO}*.db") if _fecha_de(p) is not None]
    return sorted(copias, key=lambda p: (_fecha_de(p), p.name))


def _auditar(ruta_db, ahora: datetime, accion: str, **detalle) -> None:
    con = abrir(ruta_db)
    try:
        with transaccion(con):
            auditar(con, ahora, accion, "respaldo", None, **detalle)
    finally:
        con.close()


def crear_respaldo(ruta_db: str | Path, *, ahora: datetime, motivo: str = "manual") -> Path:
    """Copia la base, la verifica con quick_check y rota las copias viejas."""
    carpeta, conservar = _config(ruta_db)
    base = carpeta / f"{PREFIJO}{ahora.astimezone(ZONA).strftime(FORMATO)}"
    destino, n = base.with_suffix(".db"), 1
    while destino.exists():  # dos copias en el mismo segundo
        destino = base.parent / f"{base.name}_{n}.db"
        n += 1
    datos_respaldos.copiar(ruta_db, destino)
    try:
        datos_respaldos.verificar(destino)
    except datos_respaldos.RespaldoInvalido:
        destino.unlink(missing_ok=True)
        raise
    borradas = rotar(carpeta, conservar)
    _auditar(ruta_db, ahora, "crear", archivo=destino.name, motivo=motivo,
             borradas=[p.name for p in borradas])
    return destino


def rotar(carpeta: str | Path, conservar: int) -> list[Path]:
    """Deja solo las ``conservar`` copias más recientes; devuelve las borradas."""
    copias = listar_respaldos(carpeta)
    sobran = copias[:-conservar] if conservar > 0 else copias
    for copia in sobran:
        copia.unlink(missing_ok=True)
    return sobran


def hay_respaldo_del_dia(ruta_db: str | Path, ahora: datetime) -> bool:
    carpeta, _ = _config(ruta_db)
    hoy = ahora.astimezone(ZONA).date()
    return any(_fecha_de(p).date() == hoy for p in listar_respaldos(carpeta))


def respaldo_diario_si_falta(ruta_db: str | Path, *, ahora: datetime) -> Path | None:
    if hay_respaldo_del_dia(ruta_db, ahora):
        return None
    return crear_respaldo(ruta_db, ahora=ahora, motivo="diario")


def restaurar(ruta_db: str | Path, copia: str | Path, *, ahora: datetime) -> Path:
    """Restaura ``copia`` sobre la base. Antes respalda la base actual.

    Devuelve la ruta del respaldo previo. La copia se verifica antes de tocar
    nada y, si es de una versión anterior, se migra al terminar.
    """
    copia = Path(copia)
    if not copia.is_file():
        raise NoEncontrado(f"No existe la copia {copia}")
    try:
        datos_respaldos.verificar(copia)
    except datos_respaldos.RespaldoInvalido as error:
        raise DatoInvalido(str(error)) from None
    if datos_respaldos.version(copia) > len(MIGRACIONES):
        raise BaseMasNueva("La copia es de una versión más nueva de Clinican")
    previo = crear_respaldo(ruta_db, ahora=ahora, motivo="antes de restaurar")
    datos_respaldos.restaurar_sobre(copia, ruta_db)
    con = abrir(ruta_db)
    try:
        migrar(con)
    finally:
        con.close()
    _auditar(ruta_db, ahora, "restaurar", archivo=copia.name, respaldo_previo=previo.name)
    return previo


class RespaldoDiario:
    """Hilo que revisa cada ``intervalo_segundos`` si ya hay copia de hoy y, si no, la hace."""

    def __init__(self, ruta_db: str | Path, reloj: Callable[[], datetime], intervalo_segundos: float = 3600):
        self._ruta = ruta_db
        self._reloj = reloj
        self._intervalo = intervalo_segundos
        self._parar = threading.Event()
        self._hilo: threading.Thread | None = None

    def iniciar(self) -> threading.Thread:
        if self._hilo is not None and self._hilo.is_alive():
            return self._hilo
        self._parar.clear()
        self._hilo = threading.Thread(target=self._bucle, name="respaldo-diario", daemon=True)
        self._hilo.start()
        return self._hilo

    def detener(self, espera_segundos: float = 30) -> None:
        self._parar.set()
        if self._hilo is not None:
            self._hilo.join(espera_segundos)

    @property
    def corriendo(self) -> bool:
        return self._hilo is not None and self._hilo.is_alive()

    def _bucle(self) -> None:
        while not self._parar.is_set():
            try:
                respaldo_diario_si_falta(self._ruta, ahora=self._reloj())
            except Exception:
                registro.exception("Falló el respaldo diario")
            self._parar.wait(self._intervalo)
