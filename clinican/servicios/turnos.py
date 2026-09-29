"""Turnos: agenda, creación, abonos, expiración, grupos, no asistencia y entrega.

Reglas RN-02 a RN-10, RN-14 a RN-17. Todas las funciones que dependen de la
hora aceptan ``ahora`` para poder probarlas; por defecto usan el reloj del PC.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from clinican.datos import (repo_auditoria, repo_config, repo_personal, repo_propietarios, repo_servicios,
                            repo_turnos as repo)
from clinican.datos.conexion import transaccion
from clinican.dominio import cupos as reglas_cupos
from clinican.dominio import franjas as reglas_franjas
from clinican.dominio import precios
from clinican.dominio import turnos as rt
from clinican.dominio.catalogos import TIPOS_SERVICIO
from clinican.dominio.errores import DatoInvalido, NoEncontrado
from clinican.dominio.ficha import DetallesFicha
from clinican.dominio.formato import entero_pesos, pesos
from clinican.dominio.mascotas import tamano_efectivo, validar_fecha, pelaje_complicado_efectivo
from clinican.dominio.permisos import Accion
from clinican.servicios import horarios, legal
from clinican.servicios.base import Sesion, requerir

_T = Accion.AGENDAR_TURNOS
_A = Accion.REGISTRAR_ABONOS


def _ahora(ahora: datetime | None) -> datetime:
    return (ahora or datetime.now()).replace(microsecond=0)


def _turno(conn, turno_id: int) -> sqlite3.Row:
    t = repo.turno(conn, turno_id)
    if t is None:
        raise NoEncontrado("No se encontró el turno.")
    return t


def _nombre(t) -> str:
    return f"{t['mascota_nombre']} ({t['fecha']} {t['hora']})"


@dataclass
class Abono:
    monto: int | str
    medio: str
    referencia: str | None = None

    def validar(self) -> "Abono":
        self.monto = self.monto if isinstance(self.monto, int) else entero_pesos(self.monto, "El monto del abono")
        if self.monto < 0:
            raise DatoInvalido("El monto del abono no puede ser negativo.")
        if self.medio not in rt.MEDIOS_PAGO:
            raise DatoInvalido("Elija el medio de pago: Nequi, Bre-B o efectivo.")
        self.referencia = (self.referencia or "").strip() or None
        return self


@dataclass
class Resultado:
    turnos: list[int] = field(default_factory=list)
    liberados: list[sqlite3.Row] = field(default_factory=list)  # RN-08: avisar al personal


# ================================================================ expiración

def expirar_vencidos(conn, ahora: datetime | None = None) -> list[int]:
    """RN-07: libera los pendientes cuyo plazo ya pasó. Corre al iniciar y cada 30 s."""
    ahora = _ahora(ahora)
    liberados = []
    with transaccion(conn):
        for t in repo.pendientes_todos(conn):
            if rt.vencido(t["pendiente_hasta"], ahora):
                _liberar(conn, t["id"], "EXPIRO", None)
                liberados.append(t["id"])
    return liberados


def _liberar(conn, turno_id: int, motivo: str, personal_id: int | None) -> None:
    t = repo.turno(conn, turno_id)
    repo.actualizar(conn, turno_id, {"estado": rt.LIBERADO, "motivo_liberacion": motivo})
    _cancelar_ficha(conn, t)
    repo_auditoria.registrar(conn, personal_id, "LIBERAR_TURNO", "turnos", turno_id,
                             f"{_nombre(t)}: {rt.MOTIVOS_LIBERACION[motivo]}")


def _cancelar_ficha(conn, t) -> None:
    """La ficha de un turno que no se atendió queda cancelada (si aún no avanzó)."""
    if t["servicio_id"] and t["servicio_estado"] in ("PLANEADO",):
        repo_servicios.actualizar(conn, t["servicio_id"], {"estado": "CANCELADO"})


# ==================================================================== agenda

def agenda(conn, sesion: Sesion, fecha: str, ahora: datetime | None = None) -> dict:
    """Pantalla de inicio: franjas de la fecha con cupos libres y turnos."""
    requerir(conn, sesion, _T)
    fecha = validar_fecha(fecha)
    expirar_vencidos(conn, ahora)
    franjas = horarios.franjas(conn, fecha)
    turnos = repo.del_dia(conn, fecha)
    por_hora: dict[str, list] = {}
    for t in turnos:
        por_hora.setdefault(t["hora"], []).append(t)
    filas = [{"hora": f.hora, "jornada": f.jornada, "extra": f.extra,
              "libres": horarios.cupos_libres(conn, fecha, f.hora), "turnos": por_hora.pop(f.hora, [])}
             for f in franjas]
    # Turnos en horas que ya no son franjas (p. ej. históricos de una franja quitada)
    for hora, lista in sorted(por_hora.items()):
        filas.append({"hora": hora, "jornada": reglas_franjas.jornada_de(hora), "extra": False, "libres": None,
                      "turnos": lista})
    filas.sort(key=lambda f: f["hora"])
    config = repo_config.todas(conn)
    dia = reglas_franjas.dia_semana(fecha)
    personal = None if dia == 7 else int(config["personal_dia_sabado" if dia == 6 else "personal_dia_lunes_viernes"])
    bloqueo = horarios.bloqueo_del_dia(conn, fecha)
    return {"fecha": fecha, "franjas": filas, "personal_del_dia": personal,
            "bloqueo": (bloqueo["motivo"] or "Día bloqueado") if bloqueo else None,
            "cupos": reglas_cupos.cupos_configurados(config)}


# ============================================================ crear turnos

def categoria_para(conn, mascota_id: int, tipo_servicio: str) -> str:
    """RN-02 para una mascota y un tipo de servicio."""
    m = repo_propietarios.mascota(conn, mascota_id)
    if m is None:
        raise NoEncontrado("No se encontró la mascota.")
    tamano = tamano_efectivo(m["raza_tamano"], m["tamano_manual"])
    pelaje = pelaje_complicado_efectivo(m["raza_pelaje_complicado"], m["pelaje_complicado_manual"])
    return reglas_cupos.categoria_cupo(pelaje, tipo_servicio, tamano, repo_config.todas(conn))


def franjas_para(conn, sesion: Sesion, fecha: str, mascota_id: int, tipo_servicio: str,
                 ahora: datetime | None = None) -> list[tuple[str, int]]:
    """Franjas de la fecha con cupo para esa mascota: [(hora, cupos libres de su categoría)]."""
    requerir(conn, sesion, _T)
    fecha = validar_fecha(fecha)
    ahora = _ahora(ahora)
    categoria = categoria_para(conn, mascota_id, tipo_servicio)
    resultado = []
    for f in horarios.franjas(conn, fecha):
        if rt.inicio_turno(fecha, f.hora) <= ahora:
            continue
        libres = horarios.cupos_libres(conn, fecha, f.hora)[categoria]
        if libres > 0:
            resultado.append((f.hora, libres))
    return resultado


def _validar_nuevo(conn, mascota_id, tipo_servicio, fecha, hora, agendado_por, ahora, grupo: bool) -> tuple:
    if tipo_servicio not in TIPOS_SERVICIO:
        raise DatoInvalido("Elija el tipo de servicio.")
    m = repo_propietarios.mascota(conn, mascota_id)
    if m is None:
        raise NoEncontrado("No se encontró la mascota.")
    if not m["activa"]:
        raise DatoInvalido(f"{m['nombre']} está dada de baja.")
    if not m["propietario_provisional"]:
        # RN-15. Un cliente sin registrar acepta al llegar, antes de iniciar la atención.
        legal.verificar_para_turno(conn, m["propietario_id"])
    persona = repo_personal.por_id(conn, agendado_por) if agendado_por else None
    if persona is None or not persona["activo"]:
        raise DatoInvalido("Elija quién agenda el turno (una persona activa del personal).")
    if rt.inicio_turno(fecha, hora) <= ahora:
        raise DatoInvalido(f"La hora {hora} del {fecha} ya pasó. Elija otra franja.")
    if not any(f.hora == hora for f in horarios.franjas(conn, fecha)):
        raise DatoInvalido(f"No hay una franja disponible el {fecha} a las {hora}.")
    config = repo_config.todas(conn)
    if grupo and hora in _solo_individuales(config):
        raise DatoInvalido(f"La franja de las {hora} es solo para turnos individuales [A-3].")
    if repo.activo_de_mascota(conn, mascota_id, fecha):
        raise DatoInvalido(f"{m['nombre']} ya tiene un turno activo el {fecha}.")
    categoria = categoria_para(conn, mascota_id, tipo_servicio)
    if not horarios.cupos_libres(conn, fecha, hora)[categoria]:
        raise DatoInvalido(f"No hay cupo {reglas_cupos.CATEGORIAS[categoria]} a las {hora} del {fecha}.")
    return m, categoria, config


def _solo_individuales(config: dict[str, str]) -> set[str]:
    return {h.strip() for h in config.get("franjas_solo_individuales", "").split(",") if h.strip()}


def _insertar_turno(conn, sesion, m, categoria, config, tipo_servicio, fecha, hora, agendado_por, ahora,
                    grupo_id=None) -> int:
    detalles = DetallesFicha(tipo_servicio).validar()
    liq = precios.liquidar(tamano_efectivo(m["raza_tamano"], m["tamano_manual"]), tipo_servicio, None,
                           False, False, 1, 0, config)
    servicio_id = repo_servicios.insertar(conn, m["id"], fecha, detalles.columnas(), liq.precio_minimo, None,
                                          liq.extras, None, sesion.personal_id)
    turno_id = repo.insertar(conn, {
        "fecha": fecha, "hora": hora, "mascota_id": m["id"], "servicio_id": servicio_id, "grupo_id": grupo_id,
        "categoria_cupo": categoria, "estado": rt.PENDIENTE, "agendado_por": agendado_por,
        "pendiente_hasta": rt.pendiente_hasta(ahora, int(config["minutos_pendiente"])),
        "creado_en": rt.texto(ahora),
    })
    repo_auditoria.registrar(conn, sesion.personal_id, "CREAR_TURNO", "turnos", turno_id,
                             f"{m['nombre']} — {fecha} {hora} — {TIPOS_SERVICIO[tipo_servicio]} — cupo {categoria}")
    return turno_id


def crear_turno(conn, sesion: Sesion, mascota_id: int, tipo_servicio: str, fecha: str, hora: str,
                agendado_por: int, abono: Abono | None = None, abono_a_favor_id: int | None = None,
                ahora: datetime | None = None, confirmar: bool = False) -> Resultado:
    """RN-05: nace pendiente de abono (30 min). Con abono suficiente pasa directo a confirmado.

    ``confirmar``: el personal verificó el pago y confirma aunque el abono sea menor al mínimo (incluso 0).
    """
    requerir(conn, sesion, _T)
    if abono is not None:
        requerir(conn, sesion, _A)
        abono.validar()
    ahora = _ahora(ahora)
    fecha = validar_fecha(fecha, "La fecha del turno")
    hora = reglas_franjas.validar_hora(hora)
    expirar_vencidos(conn, ahora)
    with transaccion(conn):
        m, categoria, config = _validar_nuevo(conn, mascota_id, tipo_servicio, fecha, hora, agendado_por, ahora, False)
        dueno = repo_propietarios.propietario(conn, m["propietario_id"])
        if dueno["requiere_nuevo_abono"] and not (abono is not None and (abono.monto > 0 or confirmar)):
            raise DatoInvalido(f"{dueno['nombre']} no asistió a un turno sin avisar a tiempo: debe pagar un "
                               "abono nuevo antes de agendar (RN-10).")
        turno_id = _insertar_turno(conn, sesion, m, categoria, config, tipo_servicio, fecha, hora, agendado_por, ahora)
        if abono_a_favor_id is not None:
            _usar_abono_a_favor(conn, sesion, abono_a_favor_id, turno_id, m["propietario_id"])
        if abono is not None and abono.monto > 0:
            _guardar_abono(conn, sesion, turno_id, abono, ahora)
        resultado = Resultado([turno_id])
        resultado.liberados += _confirmar_si_alcanza(conn, sesion, turno_id, ahora, forzar=confirmar)
    return resultado


def _usar_abono_a_favor(conn, sesion, abono_id: int, turno_id: int, propietario_id: int) -> None:
    disponibles = {a["id"]: a for a in repo.abonos_a_favor(conn, propietario_id)}
    if abono_id not in disponibles:
        raise DatoInvalido("Ese abono no está disponible a favor de este propietario.")
    a = disponibles[abono_id]
    repo.mover_abono(conn, abono_id, turno_id)
    repo_auditoria.registrar(conn, sesion.personal_id, "USAR_ABONO_A_FAVOR", "abonos", abono_id,
                             f"{pesos(a['monto'])} del turno {a['turno_fecha']} {a['turno_hora']} → turno {turno_id}")


def _guardar_abono(conn, sesion, turno_id: int, abono: Abono, ahora: datetime) -> None:
    t = repo.turno(conn, turno_id)
    repo.insertar_abono(conn, turno_id, abono.monto, abono.medio, abono.referencia, sesion.personal_id, rt.texto(ahora))
    repo_auditoria.registrar(conn, sesion.personal_id, "REGISTRAR_ABONO", "turnos", turno_id,
                             f"{_nombre(t)}: {pesos(abono.monto)} por {rt.MEDIOS_PAGO[abono.medio]}"
                             + (f" — {abono.referencia}" if abono.referencia else ""))
    if t["requiere_nuevo_abono"]:
        repo_propietarios.fijar_requiere_nuevo_abono(conn, t["propietario_id"], False)
        repo_auditoria.registrar(conn, sesion.personal_id, "MARCA_NUEVO_ABONO", "propietarios", t["propietario_id"],
                                 f"{t['propietario_nombre']}: pagó abono nuevo")


def _vigente(conn, turno_id: int) -> int:
    return sum(a["monto"] for a in repo.abonos(conn, turno_id) if a["estado"] == "VIGENTE")


def _confirmar_si_alcanza(conn, sesion, turno_id: int, ahora: datetime, forzar: bool = False) -> list[sqlite3.Row]:
    """RN-06 y RN-08: con el abono mínimo se confirma, si aún hay cupo; al agotarse el cupo
    se liberan los demás pendientes de esa franja y categoría.

    ``forzar``: el personal verificó el pago y confirma aunque el abono sea menor al mínimo.
    """
    t = repo.turno(conn, turno_id)
    if t["estado"] != rt.PENDIENTE:
        return []
    config = repo_config.todas(conn)
    minimo = int(config["abono_minimo"])
    vigente = _vigente(conn, turno_id)
    if vigente < minimo and not forzar:
        return []
    ocupados = repo.ocupados(conn, t["fecha"], t["hora"])
    if not reglas_cupos.hay_cupo(ocupados, t["categoria_cupo"], config):
        raise DatoInvalido(
            f"El cupo {reglas_cupos.CATEGORIAS[t['categoria_cupo']]} de las {t['hora']} ya se agotó: otro "
            "cliente pagó primero. Ofrezca otra hora (puede mover este turno)."
        )
    repo.actualizar(conn, turno_id, {"estado": rt.CONFIRMADO, "pendiente_hasta": None})
    detalle = _nombre(t)
    if vigente < minimo:
        detalle += f" — confirmado por verificación del personal con abono de {pesos(vigente)} (mínimo {pesos(minimo)})"
        if t["requiere_nuevo_abono"]:
            repo_propietarios.fijar_requiere_nuevo_abono(conn, t["propietario_id"], False)
            detalle += "; se quitó la marca «requiere nuevo abono»"
    repo_auditoria.registrar(conn, sesion.personal_id, "CONFIRMAR_TURNO", "turnos", turno_id, detalle)
    liberados = []
    ocupados[t["categoria_cupo"]] = ocupados.get(t["categoria_cupo"], 0) + 1
    if not reglas_cupos.hay_cupo(ocupados, t["categoria_cupo"], config):
        for otro in repo.pendientes_en(conn, t["fecha"], t["hora"], t["categoria_cupo"], turno_id):
            _liberar(conn, otro["id"], "OTRO_PAGO_PRIMERO", sesion.personal_id)
            liberados.append(repo.turno(conn, otro["id"]))
    return liberados


# ================================================================= abonos

def registrar_abono(conn, sesion: Sesion, turno_id: int, abono: Abono, ahora: datetime | None = None,
                    confirmar: bool = False) -> Resultado:
    """Registra un abono. Con ``confirmar`` el personal verifica el pago y confirma el turno
    aunque el monto sea menor al mínimo (incluso 0)."""
    requerir(conn, sesion, _A)
    abono.validar()
    if abono.monto == 0 and not confirmar:
        raise DatoInvalido("Escriba el monto del abono, o marque que verificó el pago para confirmar el turno.")
    ahora = _ahora(ahora)
    expirar_vencidos(conn, ahora)
    with transaccion(conn):
        t = _turno(conn, turno_id)
        if t["estado"] == rt.LIBERADO:
            raise DatoInvalido(f"Este turno ya fue liberado ({rt.MOTIVOS_LIBERACION[t['motivo_liberacion']].lower()}). "
                               "Agende uno nuevo.")
        if t["estado"] not in (rt.PENDIENTE, rt.CONFIRMADO, rt.EN_PROCESO, rt.LISTA):
            raise DatoInvalido(f"No se pueden registrar abonos en un turno «{rt.ESTADOS[t['estado']]}».")
        if t["estado"] == rt.PENDIENTE and not confirmar:
            minimo = repo_config.obtener_entero(conn, "abono_minimo")
            if _vigente(conn, turno_id) + abono.monto < minimo:
                raise DatoInvalido(f"El abono mínimo es de {pesos(minimo)} por mascota. Si verificó el pago y "
                                   "quiere confirmar con un monto menor, marque «Verifiqué el pago».")
        if abono.monto > 0:
            _guardar_abono(conn, sesion, turno_id, abono, ahora)
        liberados = _confirmar_si_alcanza(conn, sesion, turno_id, ahora, forzar=confirmar)
    return Resultado([turno_id], liberados)


def _montos_por_turno(conn, turno_ids: list[int], abono: Abono, montos, confirmar: bool) -> list[int]:
    """Montos de cada turno de un grupo: los que escribió el personal, o el pago repartido (RN-09)."""
    if montos is None:
        return reglas_franjas.repartir_pago(abono.monto, len(turno_ids),
                                            repo_config.obtener_entero(conn, "abono_minimo"))
    if len(montos) != len(turno_ids):
        raise DatoInvalido("Escriba un monto para cada mascota del grupo.")
    limpios = [m if isinstance(m, int) else entero_pesos(m, "El monto de cada mascota") for m in montos]
    if any(m < 0 for m in limpios):
        raise DatoInvalido("Los montos no pueden ser negativos.")
    minimo = repo_config.obtener_entero(conn, "abono_minimo")
    if not confirmar and any(m < minimo for m in limpios):
        raise DatoInvalido(f"Cada mascota necesita al menos {pesos(minimo)}. Si verificó el pago y quiere "
                           "confirmar con montos menores, marque «Verifiqué el pago».")
    return limpios


def pagar_grupo(conn, sesion: Sesion, grupo_id: int, abono: Abono, ahora: datetime | None = None,
                montos: list | None = None, confirmar: bool = False) -> Resultado:
    """RN-09: pago del grupo. Sin ``montos`` se reparte en abonos de mínimo por turno pendiente;
    con ``montos`` el personal indica cuánto corresponde a cada mascota (en el orden del grupo)."""
    requerir(conn, sesion, _A)
    abono.validar()
    ahora = _ahora(ahora)
    expirar_vencidos(conn, ahora)
    with transaccion(conn):
        pendientes = [t for t in repo.de_grupo(conn, grupo_id) if t["estado"] == rt.PENDIENTE]
        if not pendientes:
            raise DatoInvalido("El grupo no tiene turnos pendientes de abono.")
        lista = _montos_por_turno(conn, [t["id"] for t in pendientes], abono, montos, confirmar)
        resultado = Resultado()
        for t, monto in zip(pendientes, lista):
            if monto > 0:
                _guardar_abono(conn, sesion, t["id"], Abono(monto, abono.medio, abono.referencia), ahora)
            resultado.liberados += _confirmar_si_alcanza(conn, sesion, t["id"], ahora, forzar=confirmar)
            resultado.turnos.append(t["id"])
    return resultado


def editar_abono(conn, sesion: Sesion, abono_id: int, monto, medio: str, referencia: str | None = None) -> None:
    """Corrección de un abono vigente por el personal. Con monto 0 el abono queda anulado."""
    requerir(conn, sesion, _A)
    nuevo = Abono(monto, medio, referencia).validar()
    with transaccion(conn):
        a = repo.abono(conn, abono_id)
        if a is None:
            raise NoEncontrado("No se encontró el abono.")
        if a["estado"] != "VIGENTE":
            raise DatoInvalido(f"Solo se corrigen abonos vigentes; este está «{rt.ESTADOS_ABONO[a['estado']].lower()}».")
        t = repo.turno(conn, a["turno_id"])
        if nuevo.monto == 0:
            repo.actualizar_abono(conn, abono_id, {"estado": "ANULADO"})
            detalle = f"{_nombre(t)}: abono de {pesos(a['monto'])} anulado"
        else:
            repo.actualizar_abono(conn, abono_id, {"monto": nuevo.monto, "medio": nuevo.medio,
                                                   "referencia": nuevo.referencia})
            detalle = (f"{_nombre(t)}: {pesos(a['monto'])} {rt.MEDIOS_PAGO[a['medio']]} → "
                       f"{pesos(nuevo.monto)} {rt.MEDIOS_PAGO[nuevo.medio]}")
        repo_auditoria.registrar(conn, sesion.personal_id, "CORREGIR_ABONO", "abonos", abono_id, detalle)


def abonos(conn, sesion: Sesion, turno_id: int) -> list[sqlite3.Row]:
    requerir(conn, sesion, _T)
    return repo.abonos(conn, turno_id)


def abonos_a_favor(conn, sesion: Sesion, propietario_id: int) -> list[sqlite3.Row]:
    requerir(conn, sesion, _T)
    return repo.abonos_a_favor(conn, propietario_id)


# ================================================================== grupos

def planificar_grupo(conn, sesion: Sesion, mascotas: list[tuple[int, str]], fecha: str, jornada: str,
                     ahora: datetime | None = None) -> tuple[list[tuple[int, str]], list[int]]:
    """RN-09 [A-3]: propone franjas consecutivas desde 09:00 o 14:30, una mascota por franja.

    ``mascotas`` = [(mascota_id, tipo_servicio)] en orden. Devuelve
    ([(mascota_id, hora)], [mascota_id que no alcanzaron en esa jornada]).
    """
    requerir(conn, sesion, _T)
    fecha = validar_fecha(fecha)
    ahora = _ahora(ahora)
    config = repo_config.todas(conn)
    inicio = config["inicio_grupo_manana" if jornada == reglas_franjas.MANANA else "inicio_grupo_tarde"]
    franjas = [f for f in horarios.franjas(conn, fecha) if rt.inicio_turno(fecha, f.hora) > ahora]
    libres = {f.hora: horarios.cupos_libres(conn, fecha, f.hora) for f in franjas}
    categorias = [categoria_para(conn, mid, tipo) for mid, tipo in mascotas]
    asignadas, faltan = reglas_franjas.planificar_grupo(categorias, franjas, libres, jornada, inicio,
                                                         _solo_individuales(config))
    return [(mascotas[i][0], h) for i, h in asignadas], [mascotas[i][0] for i in faltan]


def crear_grupo(conn, sesion: Sesion, items: list[tuple[int, str, str, str]], agendado_por: int,
                pago: Abono | None = None, ahora: datetime | None = None, montos: list | None = None,
                confirmar: bool = False) -> Resultado:
    """RN-09: varias mascotas del mismo propietario en una sola operación (mismo ``grupo_id``).

    ``items`` = [(mascota_id, tipo_servicio, fecha, hora)]. Todo o nada.
    """
    requerir(conn, sesion, _T)
    if pago is not None:
        requerir(conn, sesion, _A)
        pago.validar()
    if len(items) < 2:
        raise DatoInvalido("Un grupo necesita al menos dos mascotas.")
    ahora = _ahora(ahora)
    expirar_vencidos(conn, ahora)
    with transaccion(conn):
        preparados = []
        for mascota_id, tipo, fecha, hora in items:
            fecha = validar_fecha(fecha, "La fecha del turno")
            hora = reglas_franjas.validar_hora(hora)
            preparados.append((*_validar_nuevo(conn, mascota_id, tipo, fecha, hora, agendado_por, ahora, True),
                               tipo, fecha, hora))
        propietarios_ids = {m["propietario_id"] for m, *_ in preparados}
        if len(propietarios_ids) != 1:
            raise DatoInvalido("Todas las mascotas del grupo deben ser del mismo propietario.")
        if len({m["id"] for m, *_ in preparados}) != len(preparados):
            raise DatoInvalido("Una mascota aparece dos veces en el grupo.")
        dueno = repo_propietarios.propietario(conn, propietarios_ids.pop())
        if dueno["requiere_nuevo_abono"] and not (pago is not None and (pago.monto > 0 or confirmar)):
            raise DatoInvalido(f"{dueno['nombre']} debe pagar un abono nuevo antes de agendar (RN-10).")
        # Los pendientes no ocupan cupo, así que se cuentan a mano las mascotas del
        # mismo grupo que piden la misma franja y categoría.
        pedidos = Counter((fecha, hora, categoria) for _m, categoria, _c, _t, fecha, hora in preparados)
        for (fecha, hora, categoria), cantidad in pedidos.items():
            if horarios.cupos_libres(conn, fecha, hora)[categoria] < cantidad:
                raise DatoInvalido(f"No hay cupo {reglas_cupos.CATEGORIAS[categoria]} para {cantidad} mascotas a las {hora}.")
        resultado = Resultado()
        grupo_id = None
        for m, categoria, config, tipo, fecha, hora in preparados:
            turno_id = _insertar_turno(conn, sesion, m, categoria, config, tipo, fecha, hora, agendado_por, ahora, grupo_id)
            if grupo_id is None:
                grupo_id = turno_id
                repo.actualizar(conn, turno_id, {"grupo_id": grupo_id})
            resultado.turnos.append(turno_id)
        if pago is not None:
            lista = _montos_por_turno(conn, resultado.turnos, pago, montos, confirmar)
            for turno_id, monto in zip(resultado.turnos, lista):
                if monto > 0:
                    _guardar_abono(conn, sesion, turno_id, Abono(monto, pago.medio, pago.referencia), ahora)
                resultado.liberados += _confirmar_si_alcanza(conn, sesion, turno_id, ahora, forzar=confirmar)
    return resultado


# ============================================================ editar turno

def mover(conn, sesion: Sesion, turno_id: int, fecha: str, hora: str, ahora: datetime | None = None) -> Resultado:
    """Reprogramar un turno pendiente o confirmado a otra fecha u hora (conserva los abonos)."""
    requerir(conn, sesion, _T)
    ahora = _ahora(ahora)
    fecha = validar_fecha(fecha, "La fecha nueva")
    hora = reglas_franjas.validar_hora(hora)
    expirar_vencidos(conn, ahora)
    with transaccion(conn):
        t = _turno(conn, turno_id)
        if t["estado"] not in (rt.PENDIENTE, rt.CONFIRMADO):
            raise DatoInvalido("Solo se pueden mover turnos pendientes o confirmados.")
        if (t["fecha"], t["hora"]) == (fecha, hora):
            raise DatoInvalido("El turno ya está en esa fecha y hora.")
        if rt.inicio_turno(fecha, hora) <= ahora:
            raise DatoInvalido("Esa hora ya pasó.")
        if not any(f.hora == hora for f in horarios.franjas(conn, fecha)):
            raise DatoInvalido(f"No hay una franja disponible el {fecha} a las {hora}.")
        if t["grupo_id"] and hora in _solo_individuales(repo_config.todas(conn)):
            raise DatoInvalido(f"La franja de las {hora} es solo para turnos individuales [A-3].")
        if repo.activo_de_mascota(conn, t["mascota_id"], fecha, excepto=turno_id):
            raise DatoInvalido(f"{t['mascota_nombre']} ya tiene otro turno activo el {fecha}.")
        if not horarios.cupos_libres(conn, fecha, hora, excepto=turno_id)[t["categoria_cupo"]]:
            raise DatoInvalido(f"No hay cupo {reglas_cupos.CATEGORIAS[t['categoria_cupo']]} a las {hora} del {fecha}.")
        repo.actualizar(conn, turno_id, {"fecha": fecha, "hora": hora})
        if t["servicio_id"]:
            repo_servicios.actualizar(conn, t["servicio_id"], {"fecha": fecha})
        repo_auditoria.registrar(conn, sesion.personal_id, "MOVER_TURNO", "turnos", turno_id,
                                 f"{t['mascota_nombre']}: {t['fecha']} {t['hora']} → {fecha} {hora}")
        resultado = Resultado([turno_id])
        if t["estado"] == rt.CONFIRMADO:
            config = repo_config.todas(conn)
            if not reglas_cupos.hay_cupo(repo.ocupados(conn, fecha, hora), t["categoria_cupo"], config):
                for otro in repo.pendientes_en(conn, fecha, hora, t["categoria_cupo"], turno_id):
                    _liberar(conn, otro["id"], "OTRO_PAGO_PRIMERO", sesion.personal_id)
                    resultado.liberados.append(repo.turno(conn, otro["id"]))
    return resultado


def opciones_cancelacion(conn, sesion: Sesion, turno_id: int, ahora: datetime | None = None) -> dict:
    """Para la pantalla: cuánto hay abonado y si al cancelar ahora se puede devolver [A-10]."""
    requerir(conn, sesion, _T)
    t = _turno(conn, turno_id)
    horas = repo_config.obtener_entero(conn, "horas_minimas_devolucion")
    return {"abonado": _vigente(conn, turno_id), "horas": horas,
            "puede_devolver": rt.puede_devolver(t["fecha"], t["hora"], _ahora(ahora), horas)}


def _destino_abono(conn, sesion, t, destino: str, ahora: datetime) -> str:
    if destino not in (rt.A_FAVOR, rt.DEVOLVER):
        raise DatoInvalido("Indique si el abono se devuelve o queda a favor.")
    if destino == rt.DEVOLVER:
        total = repo.devolver_abonos(conn, t["id"], sesion.personal_id, rt.texto(ahora))
        if total:
            repo_auditoria.registrar(conn, sesion.personal_id, "DEVOLVER_ABONO", "turnos", t["id"],
                                     f"{_nombre(t)}: se devolvieron {pesos(total)} a {t['propietario_nombre']}")
        return f"; abono devuelto ({pesos(total)})" if total else ""
    total = _vigente(conn, t["id"])
    return f"; abono a favor ({pesos(total)})" if total else ""


def cancelar(conn, sesion: Sesion, turno_id: int, destino: str = rt.A_FAVOR, ahora: datetime | None = None) -> None:
    """Cancelación a pedido del cliente o del negocio.

    El abono queda a favor (para otro turno) o se devuelve si se cancela con al menos
    ``horas_minimas_devolucion`` de anticipación [A-10]. Para cambiar de día u hora, use ``mover``.
    """
    requerir(conn, sesion, _T)
    ahora = _ahora(ahora)
    with transaccion(conn):
        t = _turno(conn, turno_id)
        rt.validar_transicion(t["estado"], rt.LIBERADO)
        if destino == rt.DEVOLVER and _vigente(conn, turno_id):
            horas = repo_config.obtener_entero(conn, "horas_minimas_devolucion")
            if not rt.puede_devolver(t["fecha"], t["hora"], ahora, horas):
                raise DatoInvalido(f"El abono solo se devuelve si se cancela con al menos {horas} horas de "
                                   "anticipación. Puede dejarlo a favor o mover el turno a otro día y hora.")
        _liberar(conn, turno_id, "MANUAL", sesion.personal_id)
        _destino_abono(conn, sesion, t, destino, ahora)


def _cambiar(conn, sesion, turno_id: int, nuevo: str, campos: dict | None = None, detalle: str = "") -> sqlite3.Row:
    t = _turno(conn, turno_id)
    rt.validar_transicion(t["estado"], nuevo)
    repo.actualizar(conn, turno_id, {"estado": nuevo, **(campos or {})})
    repo_auditoria.registrar(conn, sesion.personal_id, "ESTADO_TURNO", "turnos", turno_id,
                             f"{_nombre(t)}: {rt.ESTADOS[t['estado']]} → {rt.ESTADOS[nuevo]}{detalle}")
    return t


def iniciar_atencion(conn, sesion: Sesion, turno_id: int) -> None:
    """La mascota llegó. Antes de atenderla, el propietario debe estar registrado y tener
    aceptados los términos y la autorización de datos vigentes (RN-15)."""
    requerir(conn, sesion, _T)
    with transaccion(conn):
        t = _turno(conn, turno_id)
        if t["propietario_provisional"]:
            raise DatoInvalido(f"{t['propietario_nombre']} es un cliente sin registrar. Antes de atender a "
                               f"{t['mascota_nombre']}, registre sus datos y sus consentimientos "
                               "(botón «Registrar datos del propietario»).")
        legal.verificar_para_turno(conn, t["propietario_id"])
        _cambiar(conn, sesion, turno_id, rt.EN_PROCESO)


def marcar_lista(conn, sesion: Sesion, turno_id: int) -> None:
    """RN-17: la mascota terminó; se destacan los celulares para llamar al dueño."""
    requerir(conn, sesion, _T)
    with transaccion(conn):
        _cambiar(conn, sesion, turno_id, rt.LISTA)


def registrar_llamada(conn, sesion: Sesion, turno_id: int, ahora: datetime | None = None) -> None:
    """RN-16 y RN-17: guarda la hora en que se llamó al propietario."""
    requerir(conn, sesion, _T)
    ahora = _ahora(ahora)
    with transaccion(conn):
        t = _turno(conn, turno_id)
        if t["estado"] not in (rt.LISTA, rt.NO_ATENDIDO):
            raise DatoInvalido("La llamada se registra cuando la mascota está lista o no se pudo atender.")
        repo.actualizar(conn, turno_id, {"llamada_en": rt.texto(ahora)})
        repo_auditoria.registrar(conn, sesion.personal_id, "LLAMADA_PROPIETARIO", "turnos", turno_id,
                                 f"{_nombre(t)}: se llamó a {t['propietario_nombre']}")


def no_atendido(conn, sesion: Sesion, turno_id: int, motivo: str, destino: str = rt.A_FAVOR,
                ahora: datetime | None = None) -> None:
    """RN-16: no se pudo atender (agresividad, conducta o enfermedad no informada).

    El personal decide si el abono se devuelve o queda a favor del propietario.
    """
    requerir(conn, sesion, _T)
    if motivo not in rt.MOTIVOS_NO_ATENDIDO:
        raise DatoInvalido("Elija el motivo por el que no se pudo atender.")
    ahora = _ahora(ahora)
    with transaccion(conn):
        t = _turno(conn, turno_id)
        rt.validar_transicion(t["estado"], rt.NO_ATENDIDO)
        texto = _destino_abono(conn, sesion, t, destino, ahora)
        _cambiar(conn, sesion, turno_id, rt.NO_ATENDIDO, {"motivo_no_atendido": motivo},
                 f" ({rt.MOTIVOS_NO_ATENDIDO[motivo]}){texto}")
        _cancelar_ficha(conn, t)


def no_asistio(conn, sesion: Sesion, turno_id: int, avisado_en: datetime | str | None,
               ahora: datetime | None = None) -> str:
    """RN-10: con aviso a tiempo el abono se conserva para reprogramar [A-4, A-8];
    sin aviso (o tarde) el abono se pierde y el propietario debe abonar de nuevo."""
    requerir(conn, sesion, _T)
    if isinstance(avisado_en, str):
        avisado_en = rt.leer_fecha_hora(avisado_en, "La fecha y hora del aviso") if avisado_en.strip() else None
    ahora = _ahora(ahora)
    if avisado_en is not None and avisado_en > ahora:
        raise DatoInvalido("La fecha del aviso no puede ser futura.")
    with transaccion(conn):
        t = _turno(conn, turno_id)
        config = repo_config.todas(conn)
        nuevo = rt.estado_no_asistencia(t["fecha"], t["hora"], avisado_en, int(config["horas_minimas_aviso"]))
        _cambiar(conn, sesion, turno_id, nuevo, {"avisado_en": rt.texto(avisado_en) if avisado_en else None})
        _cancelar_ficha(conn, t)
        conserva = nuevo == rt.NO_ASISTIO_AVISO and config.get("abono_se_conserva_con_aviso", "1") == "1"
        if not conserva:
            repo.fijar_estado_abonos(conn, turno_id, "VIGENTE", "PERDIDO")
        if nuevo == rt.NO_ASISTIO_SIN_AVISO:
            repo_propietarios.fijar_requiere_nuevo_abono(conn, t["propietario_id"], True)
            repo_auditoria.registrar(conn, sesion.personal_id, "MARCA_NUEVO_ABONO", "propietarios", t["propietario_id"],
                                     f"{t['propietario_nombre']}: no asistió sin aviso a tiempo")
    return nuevo


# ================================================================ entrega

def cobro(conn, sesion: Sesion, turno_id: int) -> dict:
    """RN-17 y [A-6]: saldo = total del servicio (con desenredado) − abonos."""
    requerir(conn, sesion, _T)
    t = _turno(conn, turno_id)
    abonado = _vigente(conn, turno_id) + sum(a["monto"] for a in repo.abonos(conn, turno_id) if a["estado"] == "APLICADO")
    total = None
    falta_precio = False
    if t["servicio_id"]:
        s = repo_servicios.obtener(conn, t["servicio_id"])
        desenredado = repo_servicios.total_desenredado(conn, t["servicio_id"])
        falta_precio = s["precio_final"] is None and s["estado"] in ("PLANEADO", "REVISION_ESTILISTA")
        total = (s["total"] or 0) + desenredado
    return {"total": total, "abonado": abonado, "saldo": None if total is None else total - abonado,
            "falta_precio": falta_precio}


def entregar(conn, sesion: Sesion, turno_id: int) -> dict:
    """RN-17: al entregar y cobrar el saldo, el turno pasa a atendido.

    La ficha queda realizada, los abonos aplicados y la última visita se
    actualiza con la fecha del turno (RN-14).
    """
    requerir(conn, sesion, _T)
    with transaccion(conn):
        t = _turno(conn, turno_id)
        rt.validar_transicion(t["estado"], rt.ATENDIDO)
        cuenta = cobro(conn, sesion, turno_id)
        if cuenta["falta_precio"]:
            raise DatoInvalido("Antes de entregar, escriba el precio final en la ficha de servicio.")
        if t["servicio_id"]:
            s = repo_servicios.obtener(conn, t["servicio_id"])
            if s["estado"] in ("PLANEADO", "REVISION_ESTILISTA"):
                repo_servicios.actualizar(conn, t["servicio_id"], {"estado": "REALIZADO"})
        repo.fijar_estado_abonos(conn, turno_id, "VIGENTE", "APLICADO")
        _cambiar(conn, sesion, turno_id, rt.ATENDIDO, detalle=f" — saldo cobrado {pesos(cuenta['saldo'] or 0)}")
        repo_propietarios.fijar_ultima_visita(conn, t["mascota_id"], t["fecha"])
    return cuenta


def turno(conn, sesion: Sesion, turno_id: int) -> sqlite3.Row:
    requerir(conn, sesion, _T)
    return _turno(conn, turno_id)


def grupo(conn, sesion: Sesion, grupo_id: int) -> list[sqlite3.Row]:
    requerir(conn, sesion, _T)
    return repo.de_grupo(conn, grupo_id)
