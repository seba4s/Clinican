"""Validación e importación de mascotas desde Excel (sección 11).

Las mascotas con la misma cédula se agrupan bajo un solo propietario.
Se entrega un reporte con las filas rechazadas y el motivo.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from clinican.datos import importar_excel, repo_auditoria, repo_propietarios, repo_razas
from clinican.datos.conexion import transaccion
from clinican.dominio import mascotas as reglas_mascota
from clinican.dominio.catalogos import codigo_tamano
from clinican.dominio.errores import DatoInvalido
from clinican.dominio.formato import sin_tildes
from clinican.dominio.permisos import Accion
from clinican.dominio.propietarios import validar_propietario
from clinican.servicios.base import Sesion, requerir


@dataclass
class Reporte:
    filas_leidas: int = 0
    propietarios_nuevos: int = 0
    propietarios_existentes: int = 0
    mascotas_nuevas: int = 0
    rechazadas: list[tuple[int, str]] = field(default_factory=list)  # (fila, motivo)
    avisos: list[tuple[int, str]] = field(default_factory=list)
    importado: bool = False

    def resumen(self) -> str:
        verbo = "Se importaron" if self.importado else "Se pueden importar"
        lineas = [
            f"Filas leídas: {self.filas_leidas}",
            f"{verbo}: {self.mascotas_nuevas} mascota(s), {self.propietarios_nuevos} propietario(s) nuevo(s)"
            f" y {self.propietarios_existentes} propietario(s) que ya existían.",
            f"Filas rechazadas: {len(self.rechazadas)}",
        ]
        return "\n".join(lineas)


def _si_no(texto: str) -> int | None:
    t = sin_tildes(texto or "").strip()
    if t == "":
        return None
    if t in ("si", "s", "1", "x", "true"):
        return 1
    if t in ("no", "n", "0", "false"):
        return 0
    raise DatoInvalido(f"«{texto}» no es Sí o No.")


def _procesar(conn: sqlite3.Connection, filas, reporte: Reporte, guardar: bool, sesion: Sesion | None) -> None:
    propietarios: dict[str, dict] = {}  # cédula -> {"id", "datos", "fila", "nombres"}
    for numero, f in filas:
        try:
            dueno = validar_propietario(f.get("propietario"), f.get("cedula"), f.get("celular1"),
                                        f.get("celular2"), f.get("direccion"))
            raza = repo_razas.por_nombre(conn, f.get("raza") or "")
            if raza is None:
                raise DatoInvalido(f"La raza «{f.get('raza')}» no existe. Agréguela en Configuración › Razas.")
            tamano = None
            if f.get("tamano"):
                tamano = codigo_tamano(f["tamano"])
                if tamano is None:
                    raise DatoInvalido(f"Tamaño «{f['tamano']}» no válido (Pequeña, Mediana o Grande).")
            pelaje = _si_no(f.get("pelaje", ""))
            ultima = f.get("ultima_visita") or None
            datos_m = reglas_mascota.validar_mascota(
                f.get("mascota"), raza["tamano"], tamano, pelaje,
                reglas_mascota.entero_opcional(f.get("edad_anios"), "La edad en años"),
                reglas_mascota.entero_opcional(f.get("edad_meses"), "Los meses de edad"),
                ultima,
            )
            datos_m["raza_id"] = raza["id"]
            datos_m["observaciones"] = f.get("observaciones") or None

            grupo = propietarios.get(dueno["cedula"])
            if grupo is None:
                existente = repo_propietarios.propietario_por_cedula(conn, dueno["cedula"])
                grupo = {"id": existente["id"] if existente else None, "datos": dueno, "fila": numero,
                         "nombres": set(), "nuevo": existente is None}
                if existente is not None:
                    reporte.propietarios_existentes += 1
                    grupo["nombres"] = {sin_tildes(m["nombre"]) for m in repo_propietarios.mascotas_de(conn, existente["id"])}
                    if sin_tildes(existente["nombre"]) != sin_tildes(dueno["nombre"]):
                        reporte.avisos.append((numero, f"La cédula {dueno['cedula']} ya existe como «{existente['nombre']}»; "
                                                       "se usan los datos del sistema."))
                propietarios[dueno["cedula"]] = grupo
            elif sin_tildes(grupo["datos"]["nombre"]) != sin_tildes(dueno["nombre"]):
                reporte.avisos.append((numero, f"Misma cédula que la fila {grupo['fila']} con otro nombre; "
                                               f"se usa «{grupo['datos']['nombre']}»."))

            clave_mascota = sin_tildes(datos_m["nombre"])
            if clave_mascota in grupo["nombres"]:
                raise DatoInvalido(f"El propietario ya tiene una mascota llamada «{datos_m['nombre']}».")

            if guardar:
                if grupo["id"] is None:
                    grupo["id"] = repo_propietarios.insertar_propietario(conn, grupo["datos"])
                repo_propietarios.insertar_mascota(conn, grupo["id"], datos_m)
            if grupo["nuevo"] and not grupo.get("contado"):
                reporte.propietarios_nuevos += 1
                grupo["contado"] = True
            grupo["nombres"].add(clave_mascota)
            reporte.mascotas_nuevas += 1
        except DatoInvalido as e:
            reporte.rechazadas.append((numero, str(e)))


def importar(conn: sqlite3.Connection, sesion: Sesion, ruta: str | Path, solo_validar: bool = False) -> Reporte:
    """Lee el Excel, valida cada fila y, si ``solo_validar`` es falso, guarda las filas válidas."""
    requerir(conn, sesion, Accion.GESTIONAR_PROPIETARIOS)
    try:
        filas = importar_excel.leer(ruta)
    except ValueError as e:
        raise DatoInvalido(str(e)) from None
    reporte = Reporte(filas_leidas=len(filas))
    if solo_validar:
        _procesar(conn, filas, reporte, guardar=False, sesion=sesion)
        return reporte
    with transaccion(conn):
        _procesar(conn, filas, reporte, guardar=True, sesion=sesion)
        repo_auditoria.registrar(
            conn, sesion.personal_id, "IMPORTAR_EXCEL", "mascotas", None,
            f"{Path(ruta).name}: {reporte.mascotas_nuevas} mascotas, {reporte.propietarios_nuevos} propietarios nuevos, "
            f"{len(reporte.rechazadas)} filas rechazadas",
        )
    reporte.importado = True
    return reporte


def generar_plantilla(conn: sqlite3.Connection, ruta: str | Path) -> Path:
    return importar_excel.generar_plantilla(ruta, [r["nombre"] for r in repo_razas.listar(conn, solo_activas=True)])
