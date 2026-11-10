"""Esquema SQL versión 1 (sección 6 de la especificación)."""

ESQUEMA_V1 = """
-- Esquema versión 1 de CLINICAN (sección 6 de la especificación).
-- Ajustes justificados respecto al esquema de referencia:
--   * personal.nombre y razas.nombre sin distinguir mayúsculas (COLLATE NOCASE),
--     para que "angela" y "Angela" sean la misma persona al iniciar sesión.
--   * consentimientos.origen: registra si la aceptación fue en el local o por WhatsApp (Fase 6).

CREATE TABLE personal (
  id INTEGER PRIMARY KEY,
  nombre TEXT NOT NULL UNIQUE COLLATE NOCASE,
  cargo TEXT NOT NULL,
  rol TEXT NOT NULL CHECK (rol IN ('ADMIN','PERSONAL')),
  pin_hash TEXT NOT NULL,
  pin_sal TEXT NOT NULL,
  activo INTEGER NOT NULL DEFAULT 1,
  creado_en TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE UNIQUE INDEX ux_un_admin ON personal(rol) WHERE rol = 'ADMIN' AND activo = 1;

CREATE TABLE razas (
  id INTEGER PRIMARY KEY,
  nombre TEXT NOT NULL UNIQUE COLLATE NOCASE,
  tamano TEXT CHECK (tamano IN ('PEQUENA','MEDIANA','GRANDE')),
  pelaje_complicado INTEGER NOT NULL DEFAULT 0,
  activa INTEGER NOT NULL DEFAULT 1,
  creado_en TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE propietarios (
  id INTEGER PRIMARY KEY,
  nombre TEXT NOT NULL,
  cedula TEXT NOT NULL UNIQUE,
  celular1 TEXT NOT NULL,
  celular2 TEXT,
  direccion TEXT NOT NULL,
  requiere_nuevo_abono INTEGER NOT NULL DEFAULT 0,
  creado_en TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  actualizado_en TEXT
);

CREATE TABLE mascotas (
  id INTEGER PRIMARY KEY,
  propietario_id INTEGER NOT NULL REFERENCES propietarios(id),
  nombre TEXT NOT NULL,
  raza_id INTEGER NOT NULL REFERENCES razas(id),
  tamano_manual TEXT CHECK (tamano_manual IN ('PEQUENA','MEDIANA','GRANDE')),
  pelaje_complicado_manual INTEGER,
  edad_anios INTEGER,
  edad_meses INTEGER DEFAULT 0,
  fecha_ultima_visita TEXT,
  observaciones TEXT,
  activa INTEGER NOT NULL DEFAULT 1,
  creado_en TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  actualizado_en TEXT
);

CREATE TABLE textos_legales (
  id INTEGER PRIMARY KEY,
  tipo TEXT NOT NULL CHECK (tipo IN ('TERMINOS','DATOS','RESPONSABILIDAD')),
  version INTEGER NOT NULL,
  contenido TEXT NOT NULL,
  vigente INTEGER NOT NULL DEFAULT 1,
  creado_en TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  UNIQUE (tipo, version)
);

CREATE TABLE consentimientos (
  id INTEGER PRIMARY KEY,
  propietario_id INTEGER NOT NULL REFERENCES propietarios(id),
  mascota_id INTEGER REFERENCES mascotas(id),
  tipo TEXT NOT NULL CHECK (tipo IN ('TERMINOS','DATOS','RESPONSABILIDAD')),
  texto_id INTEGER NOT NULL REFERENCES textos_legales(id),
  condiciones TEXT,
  origen TEXT NOT NULL DEFAULT 'LOCAL' CHECK (origen IN ('LOCAL','WHATSAPP')),
  aceptado_en TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  registrado_por INTEGER NOT NULL REFERENCES personal(id),
  creado_en TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE servicios (
  id INTEGER PRIMARY KEY,
  mascota_id INTEGER NOT NULL REFERENCES mascotas(id),
  fecha TEXT NOT NULL,
  tipo_servicio TEXT NOT NULL CHECK (tipo_servicio IN ('MAQUINA','TIJERA','BANO_DESLANADO')),
  largo_maquina TEXT CHECK (largo_maquina IN ('1CM','MEDIO_CM')),
  bano_medicado INTEGER NOT NULL DEFAULT 0,
  bano_antipulgas INTEGER NOT NULL DEFAULT 0,
  cantidad_banos_extra INTEGER NOT NULL DEFAULT 1,
  copete INTEGER,
  barbas INTEGER,
  cola_leon INTEGER,
  cola_estilo TEXT CHECK (cola_estilo IN ('COMPLETA','AL_RAS')),
  forma_cara TEXT CHECK (forma_cara IN ('REDONDA','PROPORCIONAL','PAREJA_AL_CUERPO')),
  cond_agresiva INTEGER NOT NULL DEFAULT 0,
  cond_nudos_extremos INTEGER NOT NULL DEFAULT 0,
  cond_problemas_piel INTEGER NOT NULL DEFAULT 0,
  cond_plagas INTEGER NOT NULL DEFAULT 0,
  cond_edad_avanzada INTEGER NOT NULL DEFAULT 0,
  estado TEXT NOT NULL DEFAULT 'PLANEADO'
    CHECK (estado IN ('PLANEADO','REVISION_ESTILISTA','EN_SESIONES','REALIZADO','CANCELADO')),
  precio_minimo INTEGER NOT NULL,
  precio_final INTEGER,
  extras INTEGER NOT NULL DEFAULT 0,
  total INTEGER,
  observaciones TEXT,
  creado_por INTEGER NOT NULL REFERENCES personal(id),
  creado_en TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE sesiones_desenredado (
  id INTEGER PRIMARY KEY,
  servicio_id INTEGER NOT NULL REFERENCES servicios(id),
  fecha TEXT NOT NULL,
  precio INTEGER NOT NULL,
  notas TEXT,
  realizada_por INTEGER REFERENCES personal(id),
  creado_en TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  UNIQUE (servicio_id, fecha)
);

CREATE TABLE franjas_base (
  id INTEGER PRIMARY KEY,
  dia_semana INTEGER NOT NULL CHECK (dia_semana BETWEEN 1 AND 6),
  hora TEXT NOT NULL,
  jornada TEXT NOT NULL CHECK (jornada IN ('MANANA','TARDE')),
  activa INTEGER NOT NULL DEFAULT 1,
  creado_en TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  UNIQUE (dia_semana, hora)
);

CREATE TABLE franjas_ajuste (
  id INTEGER PRIMARY KEY,
  fecha TEXT NOT NULL,
  hora TEXT NOT NULL,
  accion TEXT NOT NULL CHECK (accion IN ('AGREGAR','QUITAR')),
  creado_por INTEGER NOT NULL REFERENCES personal(id),
  creado_en TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  UNIQUE (fecha, hora)
);

CREATE TABLE bloqueos (
  id INTEGER PRIMARY KEY,
  fecha TEXT NOT NULL,
  hora TEXT,
  motivo TEXT,
  creado_por INTEGER NOT NULL REFERENCES personal(id),
  creado_en TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  UNIQUE (fecha, hora)
);

CREATE TABLE turnos (
  id INTEGER PRIMARY KEY,
  fecha TEXT NOT NULL,
  hora TEXT NOT NULL,
  mascota_id INTEGER NOT NULL REFERENCES mascotas(id),
  servicio_id INTEGER REFERENCES servicios(id),
  grupo_id INTEGER,
  categoria_cupo TEXT NOT NULL CHECK (categoria_cupo IN ('MAQUINA','GRANDE','TIJERA','COMPLICADO')),
  estado TEXT NOT NULL DEFAULT 'PENDIENTE_ABONO'
    CHECK (estado IN ('PENDIENTE_ABONO','CONFIRMADO','EN_PROCESO','LISTA','ATENDIDO',
                      'LIBERADO','NO_ASISTIO_AVISO','NO_ASISTIO_SIN_AVISO','NO_ATENDIDO')),
  pendiente_hasta TEXT,
  motivo_liberacion TEXT CHECK (motivo_liberacion IN ('EXPIRO','OTRO_PAGO_PRIMERO','MANUAL')),
  avisado_en TEXT,
  motivo_no_atendido TEXT CHECK (motivo_no_atendido IN ('AGRESIVIDAD','CONDUCTA','ENFERMEDAD_NO_INFORMADA')),
  llamada_en TEXT,
  agendado_por INTEGER NOT NULL REFERENCES personal(id),
  origen TEXT NOT NULL DEFAULT 'LOCAL' CHECK (origen IN ('LOCAL','WHATSAPP')),
  creado_en TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  actualizado_en TEXT
);
CREATE INDEX ix_turnos_fecha_hora ON turnos(fecha, hora);

CREATE TABLE abonos (
  id INTEGER PRIMARY KEY,
  turno_id INTEGER NOT NULL REFERENCES turnos(id),
  monto INTEGER NOT NULL CHECK (monto > 0),
  medio TEXT NOT NULL CHECK (medio IN ('NEQUI','BREB','EFECTIVO')),
  recibido_en TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  registrado_por INTEGER NOT NULL REFERENCES personal(id),
  referencia TEXT,
  estado TEXT NOT NULL DEFAULT 'VIGENTE' CHECK (estado IN ('VIGENTE','APLICADO','PERDIDO')),
  creado_en TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE config (
  clave TEXT PRIMARY KEY,
  valor TEXT NOT NULL,
  creado_en TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE auditoria (
  id INTEGER PRIMARY KEY,
  personal_id INTEGER REFERENCES personal(id),
  accion TEXT NOT NULL,
  entidad TEXT NOT NULL,
  entidad_id INTEGER,
  detalle TEXT,
  ts TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX ix_auditoria_ts ON auditoria(ts);
"""
