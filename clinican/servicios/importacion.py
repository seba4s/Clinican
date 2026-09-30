"""Validación e importación de mascotas desde Excel (sección 11).

Las mascotas con la misma cédula se agrupan bajo un solo propietario.
Se entrega un reporte con las filas rechazadas y el motivo.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from clinican.datos import (importar_excel, importar_fichas_excel, repo_auditoria, repo_config, repo_propietarios,
                            repo_razas, repo_servicios)
from clinican.datos.conexion import transaccion
from clinican.dominio import mascotas as reglas_mascota
from clinican.dominio import precios
from clinican.dominio.catalogos import codigo_tamano
from clinican.dominio.errores import DatoInvalido
from clinican.dominio.formato import sin_tildes
from clinican.dominio.permisos import Accion
from clinican.dominio.ficha import DetallesFicha
from clinican.dominio.propietarios import normalizar_cedula, normalizar_celular, validar_propietario
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


# ================================================== fichas antiguas en Excel [A-9]
# El formato real de CLINICAN: un archivo por ficha (una mascota, una visita).

# Nombres que se usan en la peluquería -> raza del catálogo
ALIAS_RAZAS = {
    "criollo": "Perro mestizo (sin raza)", "criolla": "Perro mestizo (sin raza)",
    "mestizo": "Perro mestizo (sin raza)", "mestiza": "Perro mestizo (sin raza)",
    "french": "Bulldog Francés", "bulldog": "Bulldog Francés", "frances": "Bulldog Francés",
    "yorki": "Yorkshire Terrier", "yorkie": "Yorkshire Terrier", "yorky": "Yorkshire Terrier",
    "shitzu": "Shih Tzu", "shitsu": "Shih Tzu", "shih-tzu": "Shih Tzu", "shih tzu": "Shih Tzu",
    "golden": "Golden Retriever", "labrador": "Labrador Retriever", "pastor": "Pastor Alemán",
    "pitbull": "Pitbull y similares", "pit bull": "Pitbull y similares", "gato": "Gato (sin raza definida)",
}


@dataclass
class ReporteFichas:
    archivos_leidos: int = 0
    propietarios_nuevos: int = 0
    mascotas_nuevas: int = 0
    fichas_nuevas: int = 0
    rechazados: list[tuple[str, str]] = field(default_factory=list)  # (archivo, motivo)
    avisos: list[tuple[str, str]] = field(default_factory=list)
    importado: bool = False

    def resumen(self) -> str:
        verbo = "Se importaron" if self.importado else "Se pueden importar"
        return "\n".join([
            f"Archivos leídos: {self.archivos_leidos}",
            f"{verbo}: {self.fichas_nuevas} ficha(s) de servicio, {self.mascotas_nuevas} mascota(s) nueva(s) y "
            f"{self.propietarios_nuevos} propietario(s) nuevo(s).",
            f"Archivos rechazados: {len(self.rechazados)}",
        ])


def buscar_raza(conn: sqlite3.Connection, texto: str | None) -> sqlite3.Row | None:
    """Raza del catálogo para lo escrito en la ficha ("POODLE" -> "Poodle (Caniche) Toy y Miniatura")."""
    limpio = " ".join(sin_tildes(texto or "").split())
    if not limpio:
        return None
    exacta = repo_razas.por_nombre(conn, limpio)
    if exacta is not None:
        return exacta
    if limpio in ALIAS_RAZAS:
        return repo_razas.por_nombre(conn, ALIAS_RAZAS[limpio])
    # Una sola raza cuyo nombre contenga todas las palabras escritas
    palabras = limpio.split()
    candidatas = [r for r in repo_razas.listar(conn, solo_activas=True)
                  if all(p in sin_tildes(r["nombre"]).replace("(", " ").replace(")", " ").split() for p in palabras)]
    if len(candidatas) == 1:
        return candidatas[0]
    # La más corta si todas empiezan igual ("schnauzer" -> "Schnauzer", no "Schnauzer Miniatura")
    return min(candidatas, key=lambda r: len(r["nombre"])) if candidatas else None


def _nombre_propio(texto: str | None) -> str:
    """"ANA GOMEZ" -> "Ana Gomez" (en las fichas de Excel los nombres vienen en mayúsculas)."""
    limpio = " ".join((texto or "").split())
    return limpio.title() if limpio.isupper() else limpio


def _detalles_de_ficha(ficha, nota_extra: str):
    m = ficha.marcas
    if "tijera" in m:
        tipo = "TIJERA"
    elif "bajar_1cm" in m or "bajar_medio_cm" in m:
        tipo = "MAQUINA"
    elif "bano_cepillado" in m:
        tipo = "BANO_DESLANADO"
    else:
        tipo = "MAQUINA"
    largo = None
    if tipo == "MAQUINA":
        largo = "1CM" if "bajar_1cm" in m else "MEDIO_CM" if "bajar_medio_cm" in m else None
    marcas = ", ".join(f"{importar_fichas_excel.NOMBRE_MARCA[k]}" + (f": {v}" if v.strip().upper() != "X" else "") for k, v in m.items())
    observaciones = " ".join(p for p in (ficha.nota, f"[Importada de Excel ({ficha.archivo})"
                                          + (f". Marcado: {marcas}" if marcas else "") + nota_extra + "]") if p)
    return DetallesFicha(
        tipo_servicio=tipo, largo_maquina=largo,
        bano_medicado="bano_medicado" in m, bano_antipulgas="bano_antipulgas" in m,
        despunte="despunte" in m, patas_rasuradas="patas_rasuradas" in m, desparasitacion="desparasitacion" in m,
        cola_leon=1 if "leon" in sin_tildes(m.get("cola", "")) else None,
        observaciones=observaciones,
    ).validar()


def _procesar_fichas(conn, fichas, reporte: ReporteFichas, guardar: bool, sesion: Sesion) -> None:
    config = repo_config.todas(conn)
    duenos: dict[str, dict] = {}        # clave del dueño -> {"id", "nombre", "nuevo", "mascotas": {nombre: id}}
    visitas: set[tuple] = set()         # (dueño, mascota, fecha) ya vistas en este lote
    for ficha in fichas:
        try:
            nombre = _nombre_propio(ficha.propietario)
            if not nombre:
                raise DatoInvalido("La ficha no tiene el nombre del propietario.")
            if not ficha.celulares:
                raise DatoInvalido("La ficha no tiene un celular válido del propietario.")
            celular1 = normalizar_celular(ficha.celulares[0], True, "El celular")
            celular2 = normalizar_celular(ficha.celulares[1], False) if len(ficha.celulares) > 1 else None
            cedula = normalizar_cedula(ficha.cedula) if ficha.cedula else None
            mascota = _nombre_propio(ficha.mascota)
            if not mascota:
                raise DatoInvalido("La ficha no tiene el nombre de la mascota.")
            fecha = reglas_mascota.validar_fecha(ficha.fecha, "La fecha de la ficha") if ficha.fecha else None

            # ------------------------------------------------ propietario
            clave = cedula or f"{sin_tildes(nombre)}|{celular1}"
            dueno = duenos.get(clave)
            if dueno is None:
                existente = (repo_propietarios.propietario_por_cedula(conn, cedula) if cedula else
                             conn.execute("SELECT * FROM propietarios WHERE provisional = 1 AND celular1 = ? "
                                          "AND sin_tildes(nombre) = sin_tildes(?)", (celular1, nombre)).fetchone())
                dueno = {"id": existente["id"] if existente else None, "nombre": nombre, "nuevo": existente is None,
                         "mascotas": {}}
                if existente is not None:
                    dueno["mascotas"] = {sin_tildes(m["nombre"]): m["id"]
                                         for m in repo_propietarios.mascotas_de(conn, existente["id"])}
                    if sin_tildes(existente["nombre"]) != sin_tildes(nombre):
                        reporte.avisos.append((ficha.archivo, f"La cédula {cedula} ya existe como «{existente['nombre']}»; "
                                                              "se usan los datos del sistema."))
                duenos[clave] = dueno
            if dueno["id"] is None and guardar:
                if cedula:
                    dueno["id"] = repo_propietarios.insertar_propietario(conn, {
                        "nombre": nombre, "cedula": cedula, "celular1": celular1,
                        "celular2": celular2 if celular2 != celular1 else None, "direccion": ficha.direccion or ""})
                else:
                    dueno["id"] = repo_propietarios.insertar_provisional(conn, nombre, celular1)
            if dueno["nuevo"] and not dueno.get("contado"):
                reporte.propietarios_nuevos += 1
                dueno["contado"] = True
                if not cedula:
                    reporte.avisos.append((ficha.archivo, f"{nombre} no tiene cédula en la ficha: queda como cliente "
                                                          "sin registrar."))
                elif not ficha.direccion:
                    reporte.avisos.append((ficha.archivo, f"{nombre} no tiene dirección en la ficha: complétela."))

            # ---------------------------------------------------- mascota
            clave_m = sin_tildes(mascota)
            mid = dueno["mascotas"].get(clave_m)
            nueva_mascota = clave_m not in dueno["mascotas"]
            raza = None
            if nueva_mascota:
                raza = buscar_raza(conn, ficha.raza)
                if raza is None:
                    raise DatoInvalido(f"La raza «{ficha.raza or 'vacía'}» no está en el catálogo. Agréguela en "
                                       "Configuración › Razas (con su tamaño) y vuelva a importar.")
                if not raza["tamano"]:
                    raise DatoInvalido(f"La raza «{raza['nombre']}» no tiene tamaño y la ficha no lo dice. Registre a "
                                       f"{mascota} a mano en Propietarios (con su tamaño) y vuelva a importar.")
                datos_m = reglas_mascota.validar_mascota(mascota, raza["tamano"], None, None, None, None, fecha,
                                                         ficha.sexo)
                datos_m.update(raza_id=raza["id"], observaciones=None)
                if guardar:
                    mid = repo_propietarios.insertar_mascota(conn, dueno["id"], datos_m)
                dueno["mascotas"][clave_m] = mid
                reporte.mascotas_nuevas += 1

            # ---------------------------------------------- ficha histórica
            if fecha is None:
                reporte.avisos.append((ficha.archivo, "La ficha no tiene fecha: se importan el propietario y la mascota, "
                                                      "pero no el servicio."))
                continue
            visita = (clave, clave_m, fecha)
            repetida = visita in visitas or (mid is not None and conn.execute(
                "SELECT 1 FROM servicios WHERE mascota_id = ? AND fecha = ? AND observaciones LIKE '%[Importada de Excel%'",
                (mid, fecha)).fetchone())
            if repetida:
                reporte.avisos.append((ficha.archivo, f"La ficha de {mascota} del {fecha} ya estaba importada."))
                continue
            visitas.add(visita)
            detalles = _detalles_de_ficha(ficha, "" if ficha.valor else ". Sin valor en la ficha")
            if guardar:
                m = repo_propietarios.mascota(conn, mid)
                minimo = precios.precio_minimo(reglas_mascota.tamano_efectivo(m["raza_tamano"], m["tamano_manual"]),
                                               detalles.tipo_servicio, config)
                sid = repo_servicios.insertar(conn, mid, fecha, detalles.columnas(), minimo, ficha.valor, 0,
                                              ficha.valor, sesion.personal_id)
                repo_servicios.actualizar(conn, sid, {"estado": "REALIZADO"})
                if not m["fecha_ultima_visita"] or m["fecha_ultima_visita"] < fecha:
                    repo_propietarios.fijar_ultima_visita(conn, mid, fecha)
            reporte.fichas_nuevas += 1
        except DatoInvalido as e:
            reporte.rechazados.append((ficha.archivo, str(e)))


def importar_fichas(conn: sqlite3.Connection, sesion: Sesion, rutas: list[str | Path],
                    solo_validar: bool = False) -> ReporteFichas:
    """Importa fichas antiguas de Excel (una por archivo): propietario, mascota y el servicio realizado.

    Con ``solo_validar`` no guarda nada y devuelve el reporte para revisarlo antes.
    Volver a importar los mismos archivos no duplica nada.
    """
    requerir(conn, sesion, Accion.GESTIONAR_PROPIETARIOS)
    if not rutas:
        raise DatoInvalido("Elija al menos un archivo de Excel.")
    reporte = ReporteFichas(archivos_leidos=len(rutas))
    fichas = []
    for ruta in rutas:
        try:
            fichas.append(importar_fichas_excel.leer(ruta))
        except ValueError as e:
            reporte.rechazados.append((Path(ruta).name, str(e)))
    fichas.sort(key=lambda f: (f.fecha or "", f.archivo))  # de la más antigua a la más reciente
    if solo_validar:
        _procesar_fichas(conn, fichas, reporte, guardar=False, sesion=sesion)
        return reporte
    with transaccion(conn):
        _procesar_fichas(conn, fichas, reporte, guardar=True, sesion=sesion)
        repo_auditoria.registrar(
            conn, sesion.personal_id, "IMPORTAR_FICHAS_EXCEL", "servicios", None,
            f"{len(rutas)} archivo(s): {reporte.fichas_nuevas} fichas, {reporte.mascotas_nuevas} mascotas, "
            f"{reporte.propietarios_nuevos} propietarios nuevos, {len(reporte.rechazados)} rechazados",
        )
    reporte.importado = True
    return reporte
