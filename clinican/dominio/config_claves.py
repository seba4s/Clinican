"""Descripción de cada clave de configuración: etiqueta, tipo y validación.

Los valores viven en la tabla ``config``; aquí solo está cómo mostrarlos y
validarlos en la pantalla de Configuración.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from clinican.dominio.errores import DatoInvalido
from clinican.dominio.formato import entero_pesos

DINERO = "dinero"
ENTERO = "entero"
TEXTO = "texto"
HORA = "hora"
HORAS = "horas"  # lista de horas separadas por coma
SI_NO = "si_no"
OPCION = "opcion"


@dataclass(frozen=True)
class ClaveConfig:
    clave: str
    etiqueta: str
    tipo: str
    grupo: str
    opciones: tuple[str, ...] = ()
    ayuda: str = ""


_G_NEGOCIO = "Negocio y pagos"
_G_PRECIOS = "Precios"
_G_ABONO = "Abonos y tiempos"
_G_CUPOS = "Cupos por franja"
_G_SUPUESTOS = "Supuestos por confirmar"
_G_OTROS = "Otros"

CLAVES: list[ClaveConfig] = [
    ClaveConfig("negocio_nombre", "Nombre del negocio", TEXTO, _G_NEGOCIO),
    ClaveConfig("negocio_descripcion", "Descripción", TEXTO, _G_NEGOCIO),
    ClaveConfig("negocio_direccion", "Dirección", TEXTO, _G_NEGOCIO),
    ClaveConfig("whatsapp_numero", "Teléfono y WhatsApp (recibe comprobantes)", TEXTO, _G_NEGOCIO),
    ClaveConfig("nequi_numero", "Número Nequi", TEXTO, _G_NEGOCIO),
    ClaveConfig("breb_llave", "Llave Bre-B", TEXTO, _G_NEGOCIO),
    ClaveConfig("pago_titular", "Titular de la cuenta", TEXTO, _G_NEGOCIO),
    ClaveConfig("precio_min_PEQUENA", "Precio mínimo — pequeña", DINERO, _G_PRECIOS),
    ClaveConfig("precio_min_MEDIANA", "Precio mínimo — mediana", DINERO, _G_PRECIOS),
    ClaveConfig("precio_min_GRANDE", "Precio mínimo — grande", DINERO, _G_PRECIOS),
    ClaveConfig("precio_ref_max_GRANDE", "Precio de referencia alto — grande", DINERO, _G_PRECIOS),
    ClaveConfig("tijera_total_min", "Corte con tijera — total mínimo", DINERO, _G_PRECIOS),
    ClaveConfig("extra_bano_PEQUENA", "Extra baño medicado/antipulgas — pequeña", DINERO, _G_PRECIOS),
    ClaveConfig("extra_bano_MEDIANA", "Extra baño medicado/antipulgas — mediana", DINERO, _G_PRECIOS),
    ClaveConfig("extra_bano_GRANDE", "Extra baño medicado/antipulgas — grande", DINERO, _G_PRECIOS),
    ClaveConfig("desenredado_sesion", "Sesión de desenredado", DINERO, _G_PRECIOS),
    ClaveConfig("abono_minimo", "Abono mínimo por mascota", DINERO, _G_ABONO),
    ClaveConfig("minutos_pendiente", "Minutos para pagar el abono antes de liberar el turno", ENTERO, _G_ABONO),
    ClaveConfig("horas_minimas_aviso", "Horas mínimas para avisar que no asistirá [A-4]", ENTERO, _G_ABONO),
    ClaveConfig("segundos_revision_expiracion", "Cada cuántos segundos se revisan los turnos vencidos", ENTERO, _G_ABONO),
    ClaveConfig("cupo_MAQUINA", "Cupo MÁQUINA (máquina y baño)", ENTERO, _G_CUPOS),
    ClaveConfig("cupo_GRANDE", "Cupo GRANDE", ENTERO, _G_CUPOS),
    ClaveConfig("cupo_TIJERA", "Cupo TIJERA", ENTERO, _G_CUPOS),
    ClaveConfig("cupo_COMPLICADO", "Cupo COMPLICADO (husky y similares)", ENTERO, _G_CUPOS),
    ClaveConfig(
        "pequenas_en_cupo_maquina", "Las pequeñas usan el cupo MÁQUINA [A-1]", SI_NO, _G_SUPUESTOS,
        ayuda="Si se desactiva, las pequeñas no se agendan en MÁQUINA hasta definir otra regla.",
    ),
    ClaveConfig("cupos_independientes", "Cupos independientes entre categorías [A-2]", SI_NO, _G_SUPUESTOS),
    ClaveConfig(
        "politica_grupo", "Política para varias mascotas [A-3]", OPCION, _G_SUPUESTOS,
        opciones=("CONSECUTIVAS",), ayuda="CONSECUTIVAS = una franja por mascota, seguidas.",
    ),
    ClaveConfig("inicio_grupo_manana", "Hora de inicio de grupos en la mañana [A-3]", HORA, _G_SUPUESTOS),
    ClaveConfig("inicio_grupo_tarde", "Hora de inicio de grupos en la tarde [A-3]", HORA, _G_SUPUESTOS),
    ClaveConfig("franjas_solo_individuales", "Franjas solo para turnos individuales [A-3]", HORAS, _G_SUPUESTOS),
    ClaveConfig("abono_se_conserva_con_aviso", "Si avisa a tiempo, el abono se conserva para reprogramar [A-8]", SI_NO, _G_SUPUESTOS),
    ClaveConfig(
        "horas_minimas_devolucion", "Horas de anticipación para poder devolver el abono al cancelar [A-10]", ENTERO,
        _G_SUPUESTOS, ayuda="Con menos anticipación, el abono solo puede quedar a favor o moverse con el turno.",
    ),
    ClaveConfig("personal_dia_lunes_viernes", "Personas que atienden de lunes a viernes", ENTERO, _G_OTROS),
    ClaveConfig("personal_dia_sabado", "Personas que atienden los sábados", ENTERO, _G_OTROS),
    ClaveConfig("respaldos_conservar", "Número de respaldos automáticos que se conservan", ENTERO, _G_OTROS),
]

POR_CLAVE: dict[str, ClaveConfig] = {c.clave: c for c in CLAVES}

_RE_HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _entero(texto: str, etiqueta: str) -> int:
    return entero_pesos(texto, f"«{etiqueta}»")


def normalizar(clave: str, valor: str) -> str:
    """Valida y devuelve el valor en el formato en que se guarda."""
    meta = POR_CLAVE.get(clave)
    if meta is None:
        raise DatoInvalido(f"La clave de configuración «{clave}» no existe.")
    valor = (valor or "").strip()
    if meta.tipo in (DINERO, ENTERO):
        numero = _entero(valor, meta.etiqueta)
        if meta.clave.startswith("cupo_") and numero < 1:
            raise DatoInvalido(f"«{meta.etiqueta}» debe ser al menos 1.")
        if meta.clave in ("minutos_pendiente", "segundos_revision_expiracion", "respaldos_conservar") and numero < 1:
            raise DatoInvalido(f"«{meta.etiqueta}» debe ser al menos 1.")
        return str(numero)
    if meta.tipo == HORA:
        if not _RE_HORA.match(valor):
            raise DatoInvalido(f"«{meta.etiqueta}» debe tener el formato HH:MM, por ejemplo 09:00.")
        return valor
    if meta.tipo == HORAS:
        horas = [h.strip() for h in valor.split(",") if h.strip()]
        for h in horas:
            if not _RE_HORA.match(h):
                raise DatoInvalido(f"«{meta.etiqueta}»: «{h}» no es una hora válida (HH:MM).")
        return ",".join(horas)
    if meta.tipo == SI_NO:
        if valor not in ("0", "1"):
            raise DatoInvalido(f"«{meta.etiqueta}» debe ser Sí (1) o No (0).")
        return valor
    if meta.tipo == OPCION:
        if valor not in meta.opciones:
            raise DatoInvalido(f"«{meta.etiqueta}» debe ser una de: {', '.join(meta.opciones)}.")
        return valor
    if not valor:
        raise DatoInvalido(f"«{meta.etiqueta}» no puede quedar vacío.")
    return valor
