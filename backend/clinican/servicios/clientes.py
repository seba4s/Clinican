"""Casos de uso de propietarios, razas y mascotas.

Cada escritura corre en su propia transacción e inserta su registro de auditoría
dentro de ella.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from clinican.datos import repo_agenda, repo_autorizaciones, repo_clientes
from clinican.datos.conexion import transaccion
from clinican.dominio.cupos import Tamano
from clinican.dominio.entidades import Mascota, Propietario, Raza
from clinican.dominio.errores import DatoInvalido, NoEncontrado, OperacionNoPermitida
from clinican.dominio.documentos import normalizar_cedula
from clinican.dominio.telefonos import normalizar_celular
from clinican.servicios.auditoria import auditar


class _SinCambio:
    def __repr__(self) -> str:
        return "SIN_CAMBIO"


SIN_CAMBIO: Any = _SinCambio()


def _texto(valor: Any, campo: str, requerido: bool = True) -> str:
    if not isinstance(valor, str):
        raise DatoInvalido(f"El campo {campo} debe ser texto")
    valor = valor.strip()
    if requerido and not valor:
        raise DatoInvalido(f"El campo {campo} es obligatorio")
    return valor


def _tamano(valor: Any) -> Tamano | None:
    if valor is None or isinstance(valor, Tamano):
        return valor
    raise DatoInvalido("El tamaño debe ser uno de: " + ", ".join(t.value for t in Tamano))


def _fecha(valor: Any, campo: str) -> date | None:
    if valor is None:
        return None
    if isinstance(valor, datetime) or not isinstance(valor, date):
        raise DatoInvalido(f"La {campo} debe ser una fecha")
    return valor


def _cambios(**campos: Any) -> dict[str, Any]:
    return {k: v for k, v in campos.items() if v is not SIN_CAMBIO}


# --------------------------------------------------------------------------- propietarios


def obtener_propietario(con, propietario_id: int) -> Propietario:
    propietario = repo_clientes.obtener_propietario(con, propietario_id)
    if propietario is None:
        raise NoEncontrado(f"No existe el propietario {propietario_id}")
    return propietario


def _propietario_activo(con, propietario_id: int) -> Propietario:
    propietario = obtener_propietario(con, propietario_id)
    if not propietario.activo:
        raise OperacionNoPermitida(f"El propietario {propietario.nombre} está inactivo")
    return propietario


def _celular2(valor: Any) -> str | None:
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None
    return normalizar_celular(valor)


def cedula_libre(con, cedula: str, excepto: int | None = None) -> None:
    """Lanza DatoInvalido si otro propietario ya tiene esa cédula."""
    existente = repo_clientes.obtener_propietario_por_cedula(con, cedula)
    if existente is not None and existente.id != excepto:
        raise DatoInvalido(f"Ya existe un propietario con la cédula {cedula} ({existente.nombre})")


def obtener_por_cedula(con, cedula: str) -> Propietario | None:
    return repo_clientes.obtener_propietario_por_cedula(con, normalizar_cedula(cedula))


def crear_propietario(
    con,
    nombre: str,
    telefono: str,
    *,
    cedula: str,
    ahora: datetime,
    direccion: str = "",
    celular2: str | None = None,
) -> Propietario:
    """Crea el propietario. La cédula es obligatoria y única; los celulares, de 10 dígitos."""
    nombre = _texto(nombre, "nombre")
    telefono = normalizar_celular(telefono)
    cedula = normalizar_cedula(cedula)
    direccion = _texto(direccion, "dirección", requerido=False)
    celular2 = _celular2(celular2)
    with transaccion(con):
        cedula_libre(con, cedula)
        pid = repo_clientes.insertar_propietario(con, nombre, telefono, cedula, direccion, celular2)
        auditar(con, ahora, "crear", "propietario", pid, nombre=nombre, telefono=telefono,
                cedula=cedula, direccion=direccion, celular2=celular2)
    return obtener_propietario(con, pid)


def editar_propietario(
    con,
    propietario_id: int,
    *,
    ahora: datetime,
    nombre: Any = SIN_CAMBIO,
    telefono: Any = SIN_CAMBIO,
    cedula: Any = SIN_CAMBIO,
    direccion: Any = SIN_CAMBIO,
    celular2: Any = SIN_CAMBIO,
) -> Propietario:
    """Edita el propietario. Si no tenía cédula (datos anteriores), hay que darla al editar."""
    cambios = _cambios(
        nombre=nombre if nombre is SIN_CAMBIO else _texto(nombre, "nombre"),
        telefono=telefono if telefono is SIN_CAMBIO else normalizar_celular(telefono),
        cedula=cedula if cedula is SIN_CAMBIO else normalizar_cedula(cedula),
        direccion=direccion if direccion is SIN_CAMBIO else _texto(direccion, "dirección", False),
        celular2=celular2 if celular2 is SIN_CAMBIO else _celular2(celular2),
    )
    with transaccion(con):
        actual = obtener_propietario(con, propietario_id)
        if "cedula" in cambios:
            cedula_libre(con, cambios["cedula"], excepto=propietario_id)
        elif actual.cedula is None:
            raise DatoInvalido(f"Indique la cédula de {actual.nombre} para guardar los cambios")
        repo_clientes.actualizar_propietario(con, propietario_id, **cambios)
        auditar(con, ahora, "editar", "propietario", propietario_id, **cambios)
    return obtener_propietario(con, propietario_id)


def desactivar_propietario(con, propietario_id: int, *, ahora: datetime) -> Propietario:
    with transaccion(con):
        obtener_propietario(con, propietario_id)
        repo_clientes.actualizar_propietario(con, propietario_id, activo=False)
        auditar(con, ahora, "desactivar", "propietario", propietario_id)
    return obtener_propietario(con, propietario_id)


def buscar_propietarios(con, texto: str = "", incluir_inactivos: bool = False) -> list[Propietario]:
    texto = texto.strip()
    if texto and re.fullmatch(r"[\d\s\-]+", texto):
        texto = re.sub(r"[\s\-]", "", texto)  # buscar "300 123" igual que "300123"
    return repo_clientes.buscar_propietarios(con, texto, incluir_inactivos)


def buscar_por_celular(con, telefono: str) -> list[Propietario]:
    """Propietarios activos con exactamente ese celular (10 dígitos)."""
    celular = normalizar_celular(telefono)
    return [p for p in repo_clientes.buscar_propietarios(con, celular) if p.telefono == celular]


def unir_propietarios(con, origen_id: int, destino_id: int, *, ahora: datetime) -> Propietario:
    """Fusiona el propietario duplicado ``origen`` en ``destino``.

    Mueve mascotas, turnos (con su historial de inasistencias) y el historial de
    autorizaciones de datos (vale el registro más reciente), suma el saldo a
    favor, marca el origen como inactivo y fusionado en el destino.
    """
    if origen_id == destino_id:
        raise OperacionNoPermitida("No se puede unir un propietario consigo mismo")
    with transaccion(con):
        origen = _propietario_activo(con, origen_id)
        destino = _propietario_activo(con, destino_id)
        mascotas = repo_clientes.mover_mascotas(con, origen.id, destino.id)
        turnos = repo_agenda.mover_turnos_de_propietario(con, origen.id, destino.id)
        autorizaciones = repo_autorizaciones.mover(con, origen.id, destino.id)
        if origen.saldo_a_favor:
            repo_clientes.sumar_saldo(con, destino.id, origen.saldo_a_favor)
        repo_clientes.actualizar_propietario(
            con, origen.id, saldo_a_favor=0, activo=False, fusionado_en=destino.id
        )
        auditar(
            con, ahora, "unir", "propietario", destino.id,
            origen_id=origen.id, origen_nombre=origen.nombre, mascotas_movidas=mascotas,
            turnos_movidos=turnos, autorizaciones_movidas=autorizaciones,
            saldo_trasladado=origen.saldo_a_favor,
        )
    return obtener_propietario(con, destino_id)


# --------------------------------------------------------------------------- razas


def obtener_raza(con, raza_id: int) -> Raza:
    raza = repo_clientes.obtener_raza(con, raza_id)
    if raza is None:
        raise NoEncontrado(f"No existe la raza {raza_id}")
    return raza


def _nombre_raza_libre(con, nombre: str, excepto: int | None = None) -> None:
    existente = repo_clientes.obtener_raza_por_nombre(con, nombre)
    if existente is not None and existente.id != excepto:
        raise DatoInvalido(f"Ya existe la raza {existente.nombre}")


def crear_raza(
    con, nombre: str, tamano: Tamano | None = None, pelaje: str = "", *, ahora: datetime
) -> Raza:
    nombre = _texto(nombre, "nombre")
    tamano = _tamano(tamano)
    pelaje = _texto(pelaje, "pelaje", requerido=False)
    with transaccion(con):
        _nombre_raza_libre(con, nombre)
        rid = repo_clientes.insertar_raza(con, nombre, tamano, pelaje)
        auditar(con, ahora, "crear", "raza", rid, nombre=nombre,
                tamano=None if tamano is None else tamano.value, pelaje=pelaje)
    return obtener_raza(con, rid)


def editar_raza(
    con, raza_id: int, *, ahora: datetime,
    nombre: Any = SIN_CAMBIO, tamano: Any = SIN_CAMBIO, pelaje: Any = SIN_CAMBIO,
) -> Raza:
    cambios = _cambios(
        nombre=nombre if nombre is SIN_CAMBIO else _texto(nombre, "nombre"),
        tamano=tamano if tamano is SIN_CAMBIO else _tamano(tamano),
        pelaje=pelaje if pelaje is SIN_CAMBIO else _texto(pelaje, "pelaje", False),
    )
    with transaccion(con):
        obtener_raza(con, raza_id)
        if "nombre" in cambios:
            _nombre_raza_libre(con, cambios["nombre"], excepto=raza_id)
        repo_clientes.actualizar_raza(con, raza_id, **cambios)
        auditar(con, ahora, "editar", "raza", raza_id,
                **{k: getattr(v, "value", v) for k, v in cambios.items()})
    return obtener_raza(con, raza_id)


def desactivar_raza(con, raza_id: int, *, ahora: datetime) -> Raza:
    with transaccion(con):
        obtener_raza(con, raza_id)
        repo_clientes.actualizar_raza(con, raza_id, activo=False)
        auditar(con, ahora, "desactivar", "raza", raza_id)
    return obtener_raza(con, raza_id)


def buscar_razas(con, texto: str = "", incluir_inactivas: bool = False) -> list[Raza]:
    return repo_clientes.buscar_razas(con, texto.strip(), incluir_inactivas)


# --------------------------------------------------------------------------- mascotas


def obtener_mascota(con, mascota_id: int) -> Mascota:
    mascota = repo_clientes.obtener_mascota(con, mascota_id)
    if mascota is None:
        raise NoEncontrado(f"No existe la mascota {mascota_id}")
    return mascota


def crear_mascota(
    con,
    propietario_id: int,
    nombre: str,
    *,
    ahora: datetime,
    raza_id: int | None = None,
    tamano: Tamano | None = None,
    pelaje: str | None = None,
    complicado: bool = False,
    fecha_nacimiento: date | None = None,
    ultima_visita: date | None = None,
    observaciones: str = "",
) -> Mascota:
    """Crea la mascota; si no se da tamaño o pelaje, se toman de la raza."""
    fecha_nacimiento = _fecha(fecha_nacimiento, "fecha de nacimiento")
    ultima_visita = _fecha(ultima_visita, "fecha de última visita")
    observaciones = _texto(observaciones, "observaciones", requerido=False)
    nombre = _texto(nombre, "nombre")
    tamano = _tamano(tamano)
    with transaccion(con):
        _propietario_activo(con, propietario_id)
        raza = None if raza_id is None else obtener_raza(con, raza_id)
        if tamano is None and raza is not None:
            tamano = raza.tamano
        if tamano is None:
            raise DatoInvalido("Indique el tamaño de la mascota (la raza no tiene uno por defecto)")
        if pelaje is None:
            pelaje = raza.pelaje if raza is not None else ""
        pelaje = _texto(pelaje, "pelaje", requerido=False)
        mid = repo_clientes.insertar_mascota(
            con, propietario_id, nombre, raza_id, tamano, pelaje, bool(complicado),
            fecha_nacimiento, ultima_visita, observaciones,
        )
        auditar(con, ahora, "crear", "mascota", mid, propietario_id=propietario_id, nombre=nombre,
                raza_id=raza_id, tamano=tamano.value, pelaje=pelaje, complicado=bool(complicado),
                fecha_nacimiento=fecha_nacimiento, ultima_visita=ultima_visita,
                observaciones=observaciones)
    return obtener_mascota(con, mid)


def editar_mascota(
    con, mascota_id: int, *, ahora: datetime,
    nombre: Any = SIN_CAMBIO, raza_id: Any = SIN_CAMBIO, tamano: Any = SIN_CAMBIO,
    pelaje: Any = SIN_CAMBIO, complicado: Any = SIN_CAMBIO,
    fecha_nacimiento: Any = SIN_CAMBIO, ultima_visita: Any = SIN_CAMBIO,
    observaciones: Any = SIN_CAMBIO,
) -> Mascota:
    if tamano is None:
        raise DatoInvalido("La mascota debe tener un tamaño")
    cambios = _cambios(
        nombre=nombre if nombre is SIN_CAMBIO else _texto(nombre, "nombre"),
        raza_id=raza_id,
        tamano=tamano if tamano is SIN_CAMBIO else _tamano(tamano),
        pelaje=pelaje if pelaje is SIN_CAMBIO else _texto(pelaje, "pelaje", False),
        complicado=complicado if complicado is SIN_CAMBIO else bool(complicado),
        fecha_nacimiento=fecha_nacimiento if fecha_nacimiento is SIN_CAMBIO
        else _fecha(fecha_nacimiento, "fecha de nacimiento"),
        ultima_visita=ultima_visita if ultima_visita is SIN_CAMBIO
        else _fecha(ultima_visita, "fecha de última visita"),
        observaciones=observaciones if observaciones is SIN_CAMBIO
        else _texto(observaciones, "observaciones", False),
    )
    with transaccion(con):
        obtener_mascota(con, mascota_id)
        if cambios.get("raza_id") is not None:
            obtener_raza(con, cambios["raza_id"])
        repo_clientes.actualizar_mascota(con, mascota_id, **cambios)
        auditar(con, ahora, "editar", "mascota", mascota_id,
                **{k: getattr(v, "value", v) for k, v in cambios.items()})
    return obtener_mascota(con, mascota_id)


def desactivar_mascota(con, mascota_id: int, *, ahora: datetime) -> Mascota:
    with transaccion(con):
        obtener_mascota(con, mascota_id)
        repo_clientes.actualizar_mascota(con, mascota_id, activo=False)
        auditar(con, ahora, "desactivar", "mascota", mascota_id)
    return obtener_mascota(con, mascota_id)


def buscar_mascotas(
    con, texto: str = "", propietario_id: int | None = None, incluir_inactivas: bool = False
) -> list[Mascota]:
    return repo_clientes.buscar_mascotas(con, texto.strip(), propietario_id, incluir_inactivas)
