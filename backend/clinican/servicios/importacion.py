"""Importación de mascotas (y sus propietarios) con el formato de plantilla_importacion.xlsx.

Recibe filas ya leídas (número de fila, {columna: valor}); la lectura del
archivo Excel está en ``adaptadores/importacion_excel.py``. Cada fila se valida
y se guarda en su propia transacción: una fila mala se rechaza con su motivo y
no detiene el resto.

Reglas confirmadas:
- La cédula identifica al propietario. Si ya existe, la mascota se agrega a ese
  propietario sin cambiar sus datos; si no, se crea con nombre, celular(es) y
  dirección de la fila.
- Tamaño: Pequeña -> pequeño, Mediana -> mediano, Grande -> grande; vacío ->
  tamaño de la raza (si la raza no tiene, la fila se rechaza).
- "Pelaje complicado" (Sí/No) es la marca de perro complicado (cupo COMPLICADO);
  obligatoria para perros mestizos.
- La edad (años y meses) se guarda como fecha de nacimiento aproximada.
- La fecha de última visita se guarda solo como dato de la mascota.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable, Mapping

from clinican.datos import repo_clientes
from clinican.datos.conexion import transaccion
from clinican.dominio.agenda import ZONA
from clinican.dominio.cupos import Tamano
from clinican.dominio.documentos import fecha_nacimiento_aproximada, normalizar_cedula
from clinican.dominio.errores import DatoInvalido, ErrorNegocio
from clinican.dominio.telefonos import normalizar_celular
from clinican.servicios.auditoria import auditar

COLUMNAS = {
    "cedula": "Cédula del propietario *",
    "nombre_propietario": "Nombre del propietario *",
    "celular1": "Celular 1 *",
    "celular2": "Celular 2",
    "direccion": "Dirección *",
    "nombre_mascota": "Nombre de la mascota *",
    "raza": "Raza *",
    "tamano": "Tamaño (Pequeña, Mediana o Grande)",
    "complicado": "Pelaje complicado (Sí o No)",
    "edad_anios": "Edad (años)",
    "edad_meses": "Edad (meses)",
    "ultima_visita": "Fecha última visita (AAAA-MM-DD)",
    "observaciones": "Observaciones",
}

TAMANOS = {"pequena": Tamano.PEQUENO, "mediana": Tamano.MEDIANO, "grande": Tamano.GRANDE}
SI_NO = {"si": True, "no": False}


@dataclass(frozen=True)
class FilaAceptada:
    fila: int
    propietario_id: int
    mascota_id: int
    propietario_nuevo: bool


@dataclass(frozen=True)
class FilaRechazada:
    fila: int
    motivo: str


@dataclass
class InformeImportacion:
    aceptadas: list[FilaAceptada] = field(default_factory=list)
    rechazadas: list[FilaRechazada] = field(default_factory=list)

    @property
    def resumen(self) -> str:
        lineas = [f"Filas aceptadas: {len(self.aceptadas)}. Filas rechazadas: {len(self.rechazadas)}."]
        lineas += [f"  Fila {r.fila}: {r.motivo}" for r in self.rechazadas]
        return "\n".join(lineas)


def normalizar_encabezado(texto: Any) -> str:
    """Encabezado sin tildes, sin '*', en minúscula y con espacios simples."""
    texto = "" if texto is None else str(texto)
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_tildes.replace("*", " ").lower().split())


ENCABEZADOS = {normalizar_encabezado(v): k for k, v in COLUMNAS.items()}
OBLIGATORIAS = {k for k, v in COLUMNAS.items() if v.endswith("*")}


def mapear_encabezados(encabezados: Iterable[Any]) -> dict[int, str]:
    """{índice de columna: clave}. Lanza DatoInvalido si falta alguna columna obligatoria."""
    mapa = {}
    for i, encabezado in enumerate(encabezados):
        clave = ENCABEZADOS.get(normalizar_encabezado(encabezado))
        if clave is not None:
            mapa[i] = clave
    faltan = OBLIGATORIAS - set(mapa.values())
    if faltan:
        nombres = ", ".join(COLUMNAS[k] for k in sorted(faltan, key=list(COLUMNAS).index))
        raise DatoInvalido(f"El archivo no tiene el formato de la plantilla. Faltan columnas: {nombres}")
    return mapa


# --------------------------------------------------------------------------- celdas


def _texto(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return str(valor).strip()


def _entero(valor: Any, campo: str) -> int:
    if valor is None or _texto(valor) == "":
        return 0
    if isinstance(valor, bool):
        raise DatoInvalido(f"{campo} debe ser un número entero")
    if isinstance(valor, float):
        if not valor.is_integer():
            raise DatoInvalido(f"{campo} debe ser un número entero")
        return int(valor)
    if isinstance(valor, int):
        return valor
    try:
        return int(_texto(valor))
    except ValueError:
        raise DatoInvalido(f"{campo} debe ser un número entero (se recibió {valor!r})") from None


def _fecha(valor: Any) -> date | None:
    if valor is None or _texto(valor) == "":
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(_texto(valor))
    except ValueError:
        raise DatoInvalido(
            f"Fecha de última visita inválida: {valor!r} (use AAAA-MM-DD)"
        ) from None


def _clave(texto: str) -> str:
    return normalizar_encabezado(texto)


# --------------------------------------------------------------------------- fila


@dataclass(frozen=True)
class _FilaValida:
    cedula: str
    nombre_propietario: str
    celular1: str
    celular2: str | None
    direccion: str
    nombre_mascota: str
    raza_id: int
    tamano: Tamano
    pelaje: str
    complicado: bool
    fecha_nacimiento: date | None
    ultima_visita: date | None
    observaciones: str


def _validar(con, datos: Mapping[str, Any], hoy: date) -> _FilaValida:
    errores: list[str] = []

    def intentar(funcion, *args):
        try:
            return funcion(*args)
        except ErrorNegocio as error:
            errores.append(str(error))
            return None

    def requerido(clave: str) -> str:
        valor = _texto(datos.get(clave))
        if not valor:
            errores.append(f"Falta {COLUMNAS[clave].rstrip(' *')}")
        return valor

    cedula_texto = requerido("cedula")
    cedula = intentar(normalizar_cedula, cedula_texto) if cedula_texto else None
    nombre_propietario = requerido("nombre_propietario")
    celular_texto = requerido("celular1")
    celular1 = intentar(normalizar_celular, celular_texto) if celular_texto else None
    celular2_texto = _texto(datos.get("celular2"))
    celular2 = intentar(normalizar_celular, celular2_texto) if celular2_texto else None
    direccion = requerido("direccion")
    nombre_mascota = requerido("nombre_mascota")

    raza = None
    raza_texto = requerido("raza")
    if raza_texto:
        raza = repo_clientes.obtener_raza_por_nombre(con, raza_texto)
        if raza is None or not raza.activo:
            errores.append(f"La raza {raza_texto!r} no existe; agréguela primero en Configuración")
            raza = None
    es_mestizo = raza is not None and "mestizo" in _clave(raza.nombre)

    tamano = None
    tamano_texto = _texto(datos.get("tamano"))
    if tamano_texto:
        tamano = TAMANOS.get(_clave(tamano_texto))
        if tamano is None:
            errores.append(f"Tamaño inválido {tamano_texto!r} (use Pequeña, Mediana o Grande)")
    elif raza is not None:
        tamano = raza.tamano
        if tamano is None:
            errores.append(f"Falta el tamaño (la raza {raza.nombre} no tiene uno por defecto)")

    complicado = False
    complicado_texto = _texto(datos.get("complicado"))
    if complicado_texto:
        if _clave(complicado_texto) not in SI_NO:
            errores.append(f"Pelaje complicado inválido {complicado_texto!r} (use Sí o No)")
        else:
            complicado = SI_NO[_clave(complicado_texto)]
    elif es_mestizo:
        errores.append("Pelaje complicado es obligatorio para perros mestizos (Sí o No)")

    fecha_nacimiento = None
    if _texto(datos.get("edad_anios")) or _texto(datos.get("edad_meses")):
        anios = intentar(_entero, datos.get("edad_anios"), "La edad en años")
        meses = intentar(_entero, datos.get("edad_meses"), "La edad en meses")
        if anios is not None and meses is not None:
            fecha_nacimiento = intentar(fecha_nacimiento_aproximada, anios, meses, hoy)
    ultima_visita = intentar(_fecha, datos.get("ultima_visita"))

    if errores:
        raise DatoInvalido("; ".join(errores))
    return _FilaValida(
        cedula=cedula, nombre_propietario=nombre_propietario, celular1=celular1, celular2=celular2,
        direccion=direccion, nombre_mascota=nombre_mascota, raza_id=raza.id, tamano=tamano,
        pelaje=raza.pelaje, complicado=complicado, fecha_nacimiento=fecha_nacimiento,
        ultima_visita=ultima_visita, observaciones=_texto(datos.get("observaciones")),
    )


def _propietario_destino(con, cedula: str):
    """Propietario con esa cédula (siguiendo fusiones). None si no existe."""
    propietario = repo_clientes.obtener_propietario_por_cedula(con, cedula)
    vistos = set()
    while propietario is not None and propietario.fusionado_en is not None:
        if propietario.id in vistos:
            break
        vistos.add(propietario.id)
        propietario = repo_clientes.obtener_propietario(con, propietario.fusionado_en)
    if propietario is not None and not propietario.activo:
        raise DatoInvalido(f"El propietario con cédula {cedula} está inactivo")
    return propietario


def _importar_fila(con, numero: int, datos: Mapping[str, Any], ahora: datetime) -> FilaAceptada:
    fila = _validar(con, datos, ahora.astimezone(ZONA).date())
    with transaccion(con):
        propietario = _propietario_destino(con, fila.cedula)
        nuevo = propietario is None
        if nuevo:
            pid = repo_clientes.insertar_propietario(
                con, fila.nombre_propietario, fila.celular1, fila.cedula, fila.direccion, fila.celular2
            )
            auditar(con, ahora, "importar", "propietario", pid, fila=numero, cedula=fila.cedula,
                    nombre=fila.nombre_propietario)
        else:
            pid = propietario.id
            repetidas = [
                m for m in repo_clientes.buscar_mascotas(con, propietario_id=pid)
                if _clave(m.nombre) == _clave(fila.nombre_mascota)
            ]
            if repetidas:
                raise DatoInvalido(
                    f"El propietario con cédula {fila.cedula} ya tiene una mascota llamada "
                    f"{fila.nombre_mascota}"
                )
        mid = repo_clientes.insertar_mascota(
            con, pid, fila.nombre_mascota, fila.raza_id, fila.tamano, fila.pelaje, fila.complicado,
            fila.fecha_nacimiento, fila.ultima_visita, fila.observaciones,
        )
        auditar(con, ahora, "importar", "mascota", mid, fila=numero, propietario_id=pid,
                nombre=fila.nombre_mascota, tamano=fila.tamano.value, complicado=fila.complicado)
    return FilaAceptada(numero, pid, mid, nuevo)


def importar_filas(
    con, filas: Iterable[tuple[int, Mapping[str, Any]]], *, ahora: datetime
) -> InformeImportacion:
    """Importa cada fila por separado; nunca aborta por una fila mala."""
    informe = InformeImportacion()
    for numero, datos in filas:
        if not any(_texto(v) for v in datos.values()):
            continue  # fila vacía
        try:
            informe.aceptadas.append(_importar_fila(con, numero, datos, ahora))
        except ErrorNegocio as error:
            informe.rechazadas.append(FilaRechazada(numero, str(error)))
        except Exception as error:  # una fila rara no debe detener la importación
            informe.rechazadas.append(FilaRechazada(numero, f"Error inesperado: {error}"))
    return informe
