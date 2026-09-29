"""Respaldos de la base de datos (sección 10).

- Automático con la API ``sqlite3.Connection.backup`` al cerrar el programa y una
  vez al día, en ``C:\\Clinican\\respaldos``, conservando los últimos
  ``respaldos_conservar`` (30 por defecto).
- «Respaldar ahora» a otra carpeta o a una memoria USB (ADMIN y PERSONAL).
- Restaurar (solo ADMIN): primero se guarda una copia del estado actual.

Cada respaldo es una base de datos SQLite completa que se puede abrir sola.
Nombre: ``clinican_<tipo>_<AAAA-MM-DD_HHMMSS>.db``.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from clinican import rutas
from clinican.datos import migraciones, repo_auditoria, repo_config, repo_personal, semillas
from clinican.datos.conexion import preparar
from clinican.dominio.errores import DatoInvalido
from clinican.dominio.permisos import Accion
from clinican.servicios.base import Sesion, requerir

log = logging.getLogger(__name__)

AUTOMATICO = "auto"
MANUAL = "manual"
ANTES_DE_RESTAURAR = "antes-de-restaurar"
TIPOS = {
    AUTOMATICO: "Automático",
    MANUAL: "Manual",
    ANTES_DE_RESTAURAR: "Antes de restaurar",
}
_FORMATO_FECHA = "%Y-%m-%d_%H%M%S"
_RE_NOMBRE = re.compile(r"^clinican_(auto|manual|antes-de-restaurar)_(\d{4}-\d{2}-\d{2}_\d{6})(?:_\d+)?\.db$")
_TABLAS_MINIMAS = {"personal", "config", "propietarios", "mascotas", "turnos"}


@dataclass(frozen=True)
class Respaldo:
    ruta: Path
    tipo: str
    fecha: datetime
    tamano: int  # bytes

    @property
    def nombre_tipo(self) -> str:
        return TIPOS.get(self.tipo, self.tipo)

    @property
    def tamano_texto(self) -> str:
        kb = self.tamano / 1024
        return f"{kb:.0f} KB" if kb < 1024 else f"{kb / 1024:.1f} MB".replace(".", ",")


# ------------------------------------------------------------------ copias


def _es_memoria(conn: sqlite3.Connection) -> bool:
    principal = next((f for f in conn.execute("PRAGMA database_list") if f[1] == "main"), None)
    return principal is None or not principal[2]


def _ruta_libre(carpeta: Path, tipo: str, ahora: datetime) -> Path:
    base = f"clinican_{tipo}_{ahora.strftime(_FORMATO_FECHA)}"
    ruta = carpeta / f"{base}.db"
    n = 2
    while ruta.exists():
        ruta = carpeta / f"{base}_{n}.db"
        n += 1
    return ruta


def _verificar(ruta: Path) -> None:
    """Revisa que el archivo sea una base de datos sana. Lanza ``DatoInvalido`` si no."""
    try:
        c = sqlite3.connect(f"{ruta.resolve().as_uri()}?mode=ro", uri=True)
        try:
            resultado = c.execute("PRAGMA quick_check").fetchone()[0]
        finally:
            c.close()
    except sqlite3.DatabaseError as e:
        raise DatoInvalido(f"El archivo no es una base de datos válida: {e}") from None
    if resultado != "ok":
        raise DatoInvalido(f"El archivo está dañado ({resultado}).")


def copiar(conn: sqlite3.Connection, carpeta: Path, tipo: str, ahora: datetime | None = None) -> Path:
    """Copia la base de datos completa a ``carpeta`` y verifica la copia. Devuelve la ruta."""
    if conn.in_transaction:
        raise DatoInvalido("Hay una operación en curso; intente respaldar de nuevo en un momento.")
    carpeta = Path(carpeta)
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise DatoInvalido(f"No se pudo usar la carpeta {carpeta}: {e.strerror or e}") from None
    ruta = _ruta_libre(carpeta, tipo, ahora or datetime.now())
    temporal = ruta.with_suffix(".db.tmp")
    try:
        destino = sqlite3.connect(temporal)
        try:
            conn.backup(destino)
        finally:
            destino.close()
        _verificar(temporal)
        temporal.replace(ruta)
    except OSError as e:
        temporal.unlink(missing_ok=True)
        raise DatoInvalido(f"No se pudo escribir el respaldo en {carpeta}: {e.strerror or e}. "
                           "Revise que la memoria USB esté conectada y tenga espacio.") from None
    except BaseException:
        temporal.unlink(missing_ok=True)
        raise
    return ruta


def listar(carpeta: Path | None = None) -> list[Respaldo]:
    """Respaldos de la carpeta, del más reciente al más antiguo."""
    carpeta = Path(carpeta or rutas.carpeta_respaldos())
    if not carpeta.is_dir():
        return []
    encontrados = []
    for ruta in carpeta.iterdir():
        m = _RE_NOMBRE.match(ruta.name)
        if m and ruta.is_file():
            encontrados.append(Respaldo(ruta, m.group(1), datetime.strptime(m.group(2), _FORMATO_FECHA),
                                        ruta.stat().st_size))
    return sorted(encontrados, key=lambda r: (r.fecha, r.ruta.name), reverse=True)


def limpiar(carpeta: Path, conservar: int) -> list[Path]:
    """Borra los respaldos automáticos más antiguos y deja los ``conservar`` más recientes.

    Los respaldos manuales y los de «antes de restaurar» no se borran solos.
    """
    automaticos = [r for r in listar(carpeta) if r.tipo == AUTOMATICO]
    borrados = []
    for r in automaticos[max(conservar, 1):]:
        try:
            r.ruta.unlink()
            borrados.append(r.ruta)
        except OSError:
            log.warning("No se pudo borrar el respaldo antiguo %s", r.ruta)
    return borrados


# ------------------------------------------------------------- automáticos


def automatico(conn: sqlite3.Connection, carpeta: Path | None = None, ahora: datetime | None = None) -> Path | None:
    """Respaldo automático (al cerrar y diario). No necesita sesión: lo hace el sistema.

    Devuelve la ruta del respaldo, o ``None`` si la base es temporal (en memoria).
    """
    if _es_memoria(conn):
        return None
    carpeta = Path(carpeta or rutas.carpeta_respaldos())
    ruta = copiar(conn, carpeta, AUTOMATICO, ahora)
    limpiar(carpeta, repo_config.obtener_entero(conn, "respaldos_conservar"))
    log.info("Respaldo automático creado: %s", ruta)
    return ruta


def diario(conn: sqlite3.Connection, carpeta: Path | None = None, ahora: datetime | None = None) -> Path | None:
    """Crea el respaldo del día si todavía no hay uno automático con la fecha de hoy."""
    ahora = ahora or datetime.now()
    hoy = ahora.date()
    if any(r.tipo == AUTOMATICO and r.fecha.date() == hoy for r in listar(carpeta)):
        return None
    return automatico(conn, carpeta, ahora)


# ----------------------------------------------------------------- manuales


def respaldar_ahora(conn: sqlite3.Connection, sesion: Sesion, carpeta: Path | str,
                    ahora: datetime | None = None) -> Path:
    """«Respaldar ahora» hacia la carpeta elegida (otra carpeta o una memoria USB)."""
    requerir(conn, sesion, Accion.RESPALDAR)
    if not carpeta or not str(carpeta).strip():
        raise DatoInvalido("Elija la carpeta o la memoria USB donde guardar el respaldo.")
    ruta = copiar(conn, Path(carpeta), MANUAL, ahora)
    repo_auditoria.registrar(conn, sesion.personal_id, "RESPALDAR", "respaldos", None, str(ruta))
    return ruta


# --------------------------------------------------------------- restaurar


def revisar(ruta: Path | str) -> dict:
    """Valida que el archivo sea un respaldo de CLINICAN que este programa puede abrir.

    Devuelve un resumen para mostrar antes de confirmar: versión y cuántos registros tiene.
    """
    ruta = Path(ruta)
    if not ruta.is_file():
        raise DatoInvalido(f"No se encontró el archivo {ruta}.")
    _verificar(ruta)
    c = sqlite3.connect(f"{ruta.resolve().as_uri()}?mode=ro", uri=True)
    try:
        tablas = {f[0] for f in c.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if not _TABLAS_MINIMAS <= tablas:
            raise DatoInvalido("El archivo no es un respaldo de CLINICAN.")
        version = c.execute("PRAGMA user_version").fetchone()[0]
        if version > migraciones.VERSION_ACTUAL:
            raise DatoInvalido("El respaldo es de una versión más nueva de CLINICAN. Actualice el programa primero.")
        if c.execute("SELECT COUNT(*) FROM personal WHERE activo = 1").fetchone()[0] == 0:
            raise DatoInvalido("El respaldo no tiene personal activo: nadie podría iniciar sesión.")
        conteo = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("propietarios", "mascotas", "turnos")}
    finally:
        c.close()
    return {"version": version, **conteo}


def restaurar(conn: sqlite3.Connection, sesion: Sesion, origen: Path | str, carpeta: Path | None = None,
              ahora: datetime | None = None) -> Path:
    """Reemplaza los datos actuales por los del respaldo (solo ADMIN).

    Antes guarda una copia del estado actual en la carpeta de respaldos, para
    poder deshacer. Devuelve la ruta de esa copia. Después de restaurar hay
    que volver a iniciar sesión (el personal puede ser distinto).
    """
    requerir(conn, sesion, Accion.RESTAURAR)
    origen = Path(origen)
    revisar(origen)
    ahora = ahora or datetime.now()
    carpeta = Path(carpeta or rutas.carpeta_respaldos())
    copia_previa = copiar(conn, carpeta, ANTES_DE_RESTAURAR, ahora)

    fuente = sqlite3.connect(f"{origen.resolve().as_uri()}?mode=ro", uri=True)
    try:
        fuente.backup(conn)  # copia el respaldo dentro de la base abierta
    finally:
        fuente.close()
    preparar(conn)
    migraciones.migrar(conn)  # un respaldo antiguo se pone al día
    semillas.sembrar(conn)
    quien = sesion.personal_id if repo_personal.por_id(conn, sesion.personal_id) else None
    repo_auditoria.registrar(conn, quien, "RESTAURAR_RESPALDO", "respaldos", None,
                             f"Restaurado desde {origen}; copia previa en {copia_previa}")
    log.info("Base restaurada desde %s (copia previa: %s)", origen, copia_previa)
    return copia_previa
