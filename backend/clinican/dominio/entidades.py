"""Entidades del negocio (sin acceso a datos)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any

from clinican.dominio.cupos import CategoriaCupo, Servicio, Tamano
from clinican.dominio.estados import EstadoTurno, MotivoLiberacion


@dataclass(frozen=True)
class Propietario:
    id: int
    nombre: str
    telefono: str
    saldo_a_favor: int
    activo: bool
    fusionado_en: int | None = None


@dataclass(frozen=True)
class Raza:
    id: int
    nombre: str
    tamano: Tamano | None
    pelaje: str
    activo: bool


@dataclass(frozen=True)
class Mascota:
    id: int
    propietario_id: int
    nombre: str
    raza_id: int | None
    tamano: Tamano
    pelaje: str
    complicado: bool
    activo: bool


@dataclass(frozen=True)
class Turno:
    id: int
    mascota_id: int
    propietario_id: int
    inicio: datetime
    servicio: Servicio
    categoria: CategoriaCupo
    estado: EstadoTurno
    motivo_liberacion: MotivoLiberacion | None
    abono_requerido: int
    abono_pagado: int
    saldo_aplicado: int
    saldo_generado: int
    creado_en: datetime
    abonado_en: datetime | None = None
    aviso_inasistencia_en: datetime | None = None

    @property
    def faltante(self) -> int:
        """Pesos que faltan para completar el abono."""
        return self.abono_requerido - self.abono_pagado - self.saldo_aplicado

    @property
    def abono_total(self) -> int:
        """Lo que el cliente ya tiene puesto en el turno (pago + saldo aplicado)."""
        return self.abono_pagado + self.saldo_aplicado


@dataclass(frozen=True)
class RegistroAuditoria:
    id: int
    cuando: datetime
    accion: str
    entidad: str
    entidad_id: int | None
    detalle: dict[str, Any] = field(default_factory=dict)


class EstadoNotificacion(Enum):
    PENDIENTE = "pendiente"
    ENVIADA = "enviada"
    DESCARTADA = "descartada"
    FALLIDA = "fallida"


@dataclass(frozen=True)
class NotificacionSalida:
    id: int
    turno_id: int
    tipo: str
    programada_para: datetime
    estado: EstadoNotificacion
    intentos: int
    ultimo_error: str | None
    motivo_descarte: str | None
    creada_en: datetime
    enviada_en: datetime | None
    cerrada_en: datetime | None


@dataclass(frozen=True)
class Ficha:
    id: int
    turno_id: int
    servicios_realizados: str
    detalles_corte: str
    precio_final: int
    observaciones: str
    creada_en: datetime


@dataclass(frozen=True)
class SesionDesenredado:
    id: int
    mascota_id: int
    ficha_id: int
    numero_sesion: int
    avance: str
    porcentaje: int | None
    fecha: date
