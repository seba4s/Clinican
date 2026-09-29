"""Ficha de servicio, precios (RN-12) y desenredado por sesiones (RN-13)."""

from __future__ import annotations

import sqlite3
from datetime import date

from clinican.datos import repo_auditoria, repo_config, repo_personal, repo_propietarios, repo_servicios as repo
from clinican.datos.conexion import transaccion
from clinican.dominio import ficha as reglas
from clinican.dominio import precios
from clinican.dominio.catalogos import ESTADOS_SERVICIO, TIPOS_SERVICIO
from clinican.dominio.errores import DatoInvalido, NoEncontrado
from clinican.dominio.formato import entero_pesos, pesos
from clinican.dominio.mascotas import tamano_efectivo, validar_fecha
from clinican.dominio.permisos import Accion
from clinican.servicios.base import Sesion, requerir

_F = Accion.GESTIONAR_FICHAS


def _precio(texto) -> int | None:
    if texto is None or str(texto).strip() == "":
        return None
    if isinstance(texto, int):
        return texto
    return entero_pesos(texto, "El precio final")


def _tamano_mascota(conn, mascota_id: int) -> str:
    m = repo_propietarios.mascota(conn, mascota_id)
    if m is None:
        raise NoEncontrado("No se encontró la mascota.")
    return tamano_efectivo(m["raza_tamano"], m["tamano_manual"])


def _obtener(conn, servicio_id: int) -> sqlite3.Row:
    fila = repo.obtener(conn, servicio_id)
    if fila is None:
        raise NoEncontrado("No se encontró la ficha de servicio.")
    return fila


# ------------------------------------------------------------------ lectura

def obtener(conn, sesion: Sesion, servicio_id: int) -> sqlite3.Row:
    requerir(conn, sesion, _F)
    return _obtener(conn, servicio_id)


def liquidacion(conn, servicio_id: int) -> precios.Liquidacion:
    """Valores guardados de la ficha más el acumulado de desenredado."""
    s = _obtener(conn, servicio_id)
    advertencia = None
    if s["precio_final"] is not None and s["precio_final"] < s["precio_minimo"]:
        advertencia = (f"El precio final ({pesos(s['precio_final'])}) es menor que el mínimo "
                       f"sugerido ({pesos(s['precio_minimo'])}).")
    return precios.Liquidacion(s["precio_minimo"], s["precio_final"], s["extras"], s["total"],
                               repo.total_desenredado(conn, servicio_id), advertencia)


def calcular(conn, sesion: Sesion, mascota_id: int, tipo_servicio: str, precio_final=None,
             bano_medicado=False, bano_antipulgas=False, cantidad_banos=1, servicio_id: int | None = None) -> precios.Liquidacion:
    """Cálculo en vivo para la pantalla, sin guardar nada."""
    requerir(conn, sesion, _F)
    desenredado = repo.total_desenredado(conn, servicio_id) if servicio_id else 0
    return precios.liquidar(_tamano_mascota(conn, mascota_id), tipo_servicio, _precio(precio_final),
                            bano_medicado, bano_antipulgas, int(cantidad_banos or 1), desenredado,
                            repo_config.todas(conn))


def sesiones(conn, sesion: Sesion, servicio_id: int) -> list[sqlite3.Row]:
    requerir(conn, sesion, _F)
    return repo.sesiones(conn, servicio_id)


# ------------------------------------------------------------ crear / editar

def crear(conn, sesion: Sesion, mascota_id: int, fecha: str, detalles: reglas.DetallesFicha,
          precio_final=None) -> int:
    requerir(conn, sesion, _F)
    detalles.validar()
    fecha = validar_fecha(fecha, "La fecha del servicio")
    final = _precio(precio_final)
    with transaccion(conn):
        m = repo_propietarios.mascota(conn, mascota_id)
        if m is None:
            raise NoEncontrado("No se encontró la mascota.")
        if not m["activa"]:
            raise DatoInvalido(f"{m['nombre']} está dada de baja; reactívela para registrar servicios.")
        liq = precios.liquidar(tamano_efectivo(m["raza_tamano"], m["tamano_manual"]), detalles.tipo_servicio,
                               final, detalles.bano_medicado, detalles.bano_antipulgas,
                               detalles.cantidad_banos_extra, 0, repo_config.todas(conn))
        nuevo = repo.insertar(conn, mascota_id, fecha, detalles.columnas(), liq.precio_minimo, final,
                              liq.extras, liq.total, sesion.personal_id)
        repo_auditoria.registrar(conn, sesion.personal_id, "CREAR_FICHA", "servicios", nuevo,
                                 f"{m['nombre']} — {TIPOS_SERVICIO[detalles.tipo_servicio]} — {fecha}")
    return nuevo


def editar(conn, sesion: Sesion, servicio_id: int, fecha: str, detalles: reglas.DetallesFicha,
           precio_final=None) -> precios.Liquidacion:
    """Guarda la ficha y recalcula precios. Devuelve la liquidación (con advertencia si aplica).

    En una ficha ya REALIZADA solo se corrigen el precio final y las observaciones;
    el mínimo y los extras quedan como se cobraron.
    """
    requerir(conn, sesion, _F)
    final = _precio(precio_final)
    with transaccion(conn):
        s = _obtener(conn, servicio_id)
        if s["estado"] == reglas.CANCELADO:
            raise DatoInvalido("La ficha está cancelada y no se puede editar.")
        if s["estado"] == reglas.REALIZADO:
            obs = (detalles.observaciones or "").strip() or None
            if final is None:
                raise DatoInvalido("Un servicio realizado debe tener precio final.")
            campos = {"precio_final": final, "total": precios.total(final, s["extras"]), "observaciones": obs}
        else:
            detalles.validar()
            fecha = validar_fecha(fecha, "La fecha del servicio")
            liq = precios.liquidar(tamano_efectivo(s["raza_tamano"], s["tamano_manual"]), detalles.tipo_servicio,
                                   final, detalles.bano_medicado, detalles.bano_antipulgas,
                                   detalles.cantidad_banos_extra, 0, repo_config.todas(conn))
            campos = {**detalles.columnas(), "fecha": fecha, "precio_minimo": liq.precio_minimo,
                      "precio_final": final, "extras": liq.extras, "total": liq.total}
        cambios = [f"{c}: {s[c]} → {v}" for c, v in campos.items() if s[c] != v]
        repo.actualizar(conn, servicio_id, campos)
        if cambios:
            repo_auditoria.registrar(conn, sesion.personal_id, "EDITAR_FICHA", "servicios", servicio_id,
                                     f"{s['mascota_nombre']}: " + "; ".join(cambios))
    return liquidacion(conn, servicio_id)


# ------------------------------------------------------------------ estados

def cambiar_estado(conn, sesion: Sesion, servicio_id: int, nuevo: str) -> None:
    requerir(conn, sesion, _F)
    with transaccion(conn):
        s = _obtener(conn, servicio_id)
        reglas.validar_transicion(s["estado"], nuevo)
        if nuevo == reglas.REALIZADO and s["precio_final"] is None:
            raise DatoInvalido("Antes de marcar el servicio como realizado, escriba el precio final.")
        if nuevo == reglas.EN_SESIONES:
            otro = repo.en_sesiones_de_mascota(conn, s["mascota_id"], servicio_id)
            if otro:
                raise DatoInvalido(f"{s['mascota_nombre']} ya tiene un desenredado en curso (ficha del {otro['fecha']}).")
        if nuevo == reglas.PLANEADO and s["estado"] == reglas.EN_SESIONES:
            raise DatoInvalido("Para salir de las sesiones use «Cerrar sesiones y definir servicio final».")
        repo.actualizar(conn, servicio_id, {"estado": nuevo})
        repo_auditoria.registrar(conn, sesion.personal_id, "ESTADO_FICHA", "servicios", servicio_id,
                                 f"{s['mascota_nombre']}: {ESTADOS_SERVICIO[s['estado']]} → {ESTADOS_SERVICIO[nuevo]}")


# -------------------------------------------------------------- desenredado

def registrar_sesion(conn, sesion: Sesion, servicio_id: int, fecha: str | None = None, notas: str | None = None,
                     realizada_por: int | None = None) -> int:
    """RN-13: $60.000 (configurable) por sesión, máximo una por día."""
    requerir(conn, sesion, _F)
    fecha = validar_fecha(fecha, "La fecha de la sesión") if fecha else date.today().isoformat()
    if fecha > date.today().isoformat():
        raise DatoInvalido("No se puede registrar una sesión de desenredado en una fecha futura.")
    realizada_por = realizada_por or sesion.personal_id
    with transaccion(conn):
        s = _obtener(conn, servicio_id)
        if s["estado"] != reglas.EN_SESIONES:
            raise DatoInvalido("Primero pase el servicio a «sesiones de desenredado».")
        persona = repo_personal.por_id(conn, realizada_por)
        if persona is None or not persona["activo"]:
            raise DatoInvalido("Elija a una persona activa del personal.")
        if any(x["fecha"] == fecha for x in repo.sesiones(conn, servicio_id)):
            raise DatoInvalido(f"Ya hay una sesión de desenredado el {fecha} para este servicio. Máximo una por día.")
        precio = repo_config.obtener_entero(conn, "desenredado_sesion")
        nueva = repo.insertar_sesion(conn, servicio_id, fecha, precio, (notas or "").strip() or None, realizada_por)
        repo_auditoria.registrar(conn, sesion.personal_id, "SESION_DESENREDADO", "servicios", servicio_id,
                                 f"{s['mascota_nombre']}: sesión del {fecha} ({pesos(precio)})")
    return nueva


def anular_sesion(conn, sesion: Sesion, sesion_id: int) -> None:
    requerir(conn, sesion, _F)
    with transaccion(conn):
        d = repo.sesion(conn, sesion_id)
        if d is None:
            raise NoEncontrado("No se encontró la sesión.")
        s = _obtener(conn, d["servicio_id"])
        if s["estado"] != reglas.EN_SESIONES:
            raise DatoInvalido("Solo se pueden anular sesiones mientras el desenredado está en curso.")
        repo.borrar_sesion(conn, sesion_id)
        repo_auditoria.registrar(conn, sesion.personal_id, "ANULAR_SESION_DESENREDADO", "servicios", s["id"],
                                 f"{s['mascota_nombre']}: sesión del {d['fecha']} ({pesos(d['precio'])})")


def cerrar_sesiones(conn, sesion: Sesion, servicio_id: int, tipo_final: str | None) -> None:
    """La estilista termina el desenredado y define el servicio final.

    - Con ``tipo_final``: la ficha vuelve a «Planeado» con ese tipo y el mínimo recalculado.
    - Sin servicio final (``None``): la ficha queda «Realizada» y solo se cobran las sesiones.
    """
    requerir(conn, sesion, _F)
    with transaccion(conn):
        s = _obtener(conn, servicio_id)
        if s["estado"] != reglas.EN_SESIONES:
            raise DatoInvalido("El servicio no tiene un desenredado en curso.")
        cantidad = len(repo.sesiones(conn, servicio_id))
        if cantidad == 0:
            raise DatoInvalido("Registre al menos una sesión antes de cerrar el desenredado.")
        if tipo_final is None:
            campos = {"estado": reglas.REALIZADO, "precio_final": 0, "extras": 0, "total": 0,
                      "bano_medicado": 0, "bano_antipulgas": 0}
            texto = "sin servicio final (solo sesiones)"
        else:
            if tipo_final not in TIPOS_SERVICIO:
                raise DatoInvalido("Tipo de servicio final no válido.")
            tamano = tamano_efectivo(s["raza_tamano"], s["tamano_manual"])
            config = repo_config.todas(conn)
            minimo = precios.precio_minimo(tamano, tipo_final, config)
            extras = precios.extras(tamano, s["bano_medicado"], s["bano_antipulgas"], s["cantidad_banos_extra"], config)
            campos = {"estado": reglas.PLANEADO, "tipo_servicio": tipo_final, "precio_minimo": minimo,
                      "extras": extras, "total": precios.total(s["precio_final"], extras)}
            if tipo_final != "MAQUINA":
                campos.update(largo_maquina=None, cola_estilo=None, forma_cara=None)
            texto = f"servicio final: {TIPOS_SERVICIO[tipo_final]}"
        repo.actualizar(conn, servicio_id, campos)
        repo_auditoria.registrar(conn, sesion.personal_id, "CERRAR_DESENREDADO", "servicios", servicio_id,
                                 f"{s['mascota_nombre']}: {cantidad} sesión(es); {texto}")
