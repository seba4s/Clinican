"""Ficha de servicio: validación de los detalles del corte y estados (RN-13, [A-5])."""

from __future__ import annotations

from dataclasses import dataclass, field

from clinican.dominio.catalogos import CONDICIONES, TIPOS_SERVICIO
from clinican.dominio.errores import DatoInvalido

LARGOS = {"1CM": "1 cm", "MEDIO_CM": "½ cm"}
COLA_ESTILOS = {"COMPLETA": "Completa", "AL_RAS": "Al ras del cuerpo"}
FORMAS_CARA = {"REDONDA": "Redonda", "PROPORCIONAL": "Proporcional", "PAREJA_AL_CUERPO": "Pareja al cuerpo"}
MAX_BANOS_EXTRA = 5
LARGO_MAX_COLOR = 40
# Colores sugeridos para corbatín y moños; también se puede escribir otro.
COLORES = ["Rojo", "Rosado", "Fucsia", "Morado", "Azul", "Azul claro", "Verde", "Amarillo", "Naranja",
           "Blanco", "Negro", "Dorado", "Plateado", "Estampado"]

# ---------------------------------------------------------------- estados
PLANEADO = "PLANEADO"
REVISION = "REVISION_ESTILISTA"
EN_SESIONES = "EN_SESIONES"
REALIZADO = "REALIZADO"
CANCELADO = "CANCELADO"

TRANSICIONES = {
    PLANEADO: {REVISION, REALIZADO, CANCELADO},
    REVISION: {PLANEADO, EN_SESIONES, REALIZADO, CANCELADO},
    EN_SESIONES: {PLANEADO, REALIZADO, CANCELADO},  # al cerrar las sesiones
    REALIZADO: set(),
    CANCELADO: set(),
}


def validar_transicion(actual: str, nuevo: str) -> None:
    if nuevo not in TRANSICIONES.get(actual, set()):
        from clinican.dominio.catalogos import ESTADOS_SERVICIO

        raise DatoInvalido(
            f"No se puede pasar el servicio de «{ESTADOS_SERVICIO.get(actual, actual)}» "
            f"a «{ESTADOS_SERVICIO.get(nuevo, nuevo)}»."
        )


def es_corte_bajito(tipo_servicio: str, largo_maquina: str | None) -> bool:
    """[A-5] Corte bajito = corte a máquina de 1 cm o ½ cm."""
    return tipo_servicio == "MAQUINA" and largo_maquina in LARGOS


def _si_no(valor, etiqueta: str) -> int | None:
    if valor is None or valor == "":
        return None
    if valor in (0, 1, True, False):
        return int(valor)
    raise DatoInvalido(f"«{etiqueta}» debe ser sí o no.")


def _color(lleva: int | None, color: str | None, que: str) -> str | None:
    """El color solo se guarda si se le pone el accesorio."""
    color = " ".join(str(color or "").split())
    if lleva != 1 or not color:
        return None
    if len(color) > LARGO_MAX_COLOR:
        raise DatoInvalido(f"El color del {que} es demasiado largo (máximo {LARGO_MAX_COLOR} letras).")
    return color[0].upper() + color[1:]


@dataclass
class DetallesFicha:
    tipo_servicio: str
    largo_maquina: str | None = None
    bano_medicado: bool = False
    bano_antipulgas: bool = False
    cantidad_banos_extra: int = 1
    copete: int | None = None
    barbas: int | None = None
    cola_leon: int | None = None
    cola_estilo: str | None = None
    forma_cara: str | None = None
    condiciones: dict[str, bool] = field(default_factory=dict)
    observaciones: str | None = None
    corbatin: int | None = None
    corbatin_color: str | None = None
    monos: int | None = None
    monos_color: str | None = None

    def validar(self) -> "DetallesFicha":
        if self.tipo_servicio not in TIPOS_SERVICIO:
            raise DatoInvalido("Elija el tipo de servicio: corte a máquina, corte con tijera o baño y deslanado.")
        if self.largo_maquina is not None:
            if self.tipo_servicio != "MAQUINA":
                raise DatoInvalido("El largo de la máquina solo aplica al corte a máquina.")
            if self.largo_maquina not in LARGOS:
                raise DatoInvalido("El largo de la máquina debe ser 1 cm o ½ cm.")
        self.copete = _si_no(self.copete, "Copete")
        self.barbas = _si_no(self.barbas, "Barbas")
        self.cola_leon = _si_no(self.cola_leon, "Cola de león")
        self.corbatin = _si_no(self.corbatin, "Corbatín")
        self.monos = _si_no(self.monos, "Moños en las orejas")
        self.corbatin_color = _color(self.corbatin, self.corbatin_color, "corbatín")
        self.monos_color = _color(self.monos, self.monos_color, "moños")
        bajito = es_corte_bajito(self.tipo_servicio, self.largo_maquina)
        if self.cola_estilo is not None:
            if not bajito:
                raise DatoInvalido("El estilo de la cola de león solo aplica al corte bajito (máquina de 1 cm o ½ cm).")
            if self.cola_leon != 1:
                raise DatoInvalido("El estilo de la cola solo se elige si se deja cola de león.")
            if self.cola_estilo not in COLA_ESTILOS:
                raise DatoInvalido("El estilo de la cola debe ser completa o al ras del cuerpo.")
        if self.forma_cara is not None:
            if not bajito:
                raise DatoInvalido("La forma de la cara solo aplica al corte bajito (máquina de 1 cm o ½ cm).")
            if self.forma_cara not in FORMAS_CARA:
                raise DatoInvalido("Forma de la cara no válida.")
        hay_bano = self.bano_medicado or self.bano_antipulgas
        if hay_bano and not (1 <= int(self.cantidad_banos_extra) <= MAX_BANOS_EXTRA):
            raise DatoInvalido(f"La cantidad de baños extra debe estar entre 1 y {MAX_BANOS_EXTRA}.")
        if not hay_bano:
            self.cantidad_banos_extra = 1
        desconocidas = set(self.condiciones) - set(CONDICIONES)
        if desconocidas:
            raise DatoInvalido("Condición desconocida.")
        self.condiciones = {c: bool(self.condiciones.get(c)) for c in CONDICIONES}
        self.observaciones = (self.observaciones or "").strip() or None
        return self

    def columnas(self) -> dict:
        """Campos tal como se guardan en la tabla ``servicios``."""
        return {
            "tipo_servicio": self.tipo_servicio,
            "largo_maquina": self.largo_maquina,
            "bano_medicado": int(bool(self.bano_medicado)),
            "bano_antipulgas": int(bool(self.bano_antipulgas)),
            "cantidad_banos_extra": int(self.cantidad_banos_extra),
            "copete": self.copete,
            "barbas": self.barbas,
            "cola_leon": self.cola_leon,
            "cola_estilo": self.cola_estilo,
            "forma_cara": self.forma_cara,
            "corbatin": self.corbatin,
            "corbatin_color": self.corbatin_color,
            "monos": self.monos,
            "monos_color": self.monos_color,
            **{c: int(v) for c, v in self.condiciones.items()},
            "observaciones": self.observaciones,
        }
