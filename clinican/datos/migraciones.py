"""Esquema de la base de datos y migraciones con ``PRAGMA user_version``.

Cada versión es una función que recibe la conexión con una transacción ya
abierta y ejecuta sentencias sueltas (nunca ``executescript``, que confirma
por su cuenta). ``migrar`` aplica en orden las que falten.
"""

from __future__ import annotations

import sqlite3


def _ejecutar(conn: sqlite3.Connection, script: str) -> None:
    for sentencia in script.split(";\n"):
        if sentencia.strip():
            conn.execute(sentencia)


# ---------------------------------------------------------------- versión 1
# Esquema de la sección 6 de la especificación.

_ESQUEMA_V1 = """
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
CREATE INDEX ix_mascotas_propietario ON mascotas(propietario_id);

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
  aceptado_en TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  registrado_por INTEGER NOT NULL REFERENCES personal(id)
);
CREATE INDEX ix_consentimientos_propietario ON consentimientos(propietario_id);

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
CREATE INDEX ix_servicios_mascota ON servicios(mascota_id);

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
CREATE INDEX ix_bloqueos_fecha ON bloqueos(fecha);

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
CREATE INDEX ix_turnos_estado ON turnos(estado);
CREATE INDEX ix_turnos_grupo ON turnos(grupo_id);

CREATE TABLE abonos (
  id INTEGER PRIMARY KEY,
  turno_id INTEGER NOT NULL REFERENCES turnos(id),
  monto INTEGER NOT NULL CHECK (monto > 0),
  medio TEXT NOT NULL CHECK (medio IN ('NEQUI','BREB','EFECTIVO')),
  recibido_en TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  registrado_por INTEGER NOT NULL REFERENCES personal(id),
  referencia TEXT,
  estado TEXT NOT NULL DEFAULT 'VIGENTE' CHECK (estado IN ('VIGENTE','APLICADO','PERDIDO'))
);
CREATE INDEX ix_abonos_turno ON abonos(turno_id);

CREATE TABLE config (clave TEXT PRIMARY KEY, valor TEXT NOT NULL);

CREATE TABLE auditoria (
  id INTEGER PRIMARY KEY,
  personal_id INTEGER REFERENCES personal(id),
  accion TEXT NOT NULL,
  entidad TEXT NOT NULL,
  entidad_id INTEGER,
  detalle TEXT,
  ts TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX ix_auditoria_ts ON auditoria(ts)
"""


def _v1(conn: sqlite3.Connection) -> None:
    from clinican.datos import semillas

    _ejecutar(conn, _ESQUEMA_V1)
    # El catálogo de razas nace con el esquema para que las mascotas puedan referenciarlo.
    semillas.sembrar_razas(conn)


# ---------------------------------------------------------------- versión 2
# Consentimientos: texto exacto mostrado y origen (LOCAL o WHATSAPP).

def _v2(conn: sqlite3.Connection) -> None:
    _ejecutar(conn, """
ALTER TABLE consentimientos ADD COLUMN texto_mostrado TEXT;
ALTER TABLE consentimientos ADD COLUMN origen TEXT NOT NULL DEFAULT 'LOCAL' CHECK (origen IN ('LOCAL','WHATSAPP'))
""")


# ---------------------------------------------------------------- versión 3
# Abonos: estados DEVUELTO y ANULADO, y quién/cuándo se devolvió [A-10].
# SQLite no permite cambiar un CHECK: se reconstruye la tabla conservando los datos.

def _v3(conn: sqlite3.Connection) -> None:
    _ejecutar(conn, """
CREATE TABLE abonos_nuevo (
  id INTEGER PRIMARY KEY,
  turno_id INTEGER NOT NULL REFERENCES turnos(id),
  monto INTEGER NOT NULL CHECK (monto > 0),
  medio TEXT NOT NULL CHECK (medio IN ('NEQUI','BREB','EFECTIVO')),
  recibido_en TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  registrado_por INTEGER NOT NULL REFERENCES personal(id),
  referencia TEXT,
  estado TEXT NOT NULL DEFAULT 'VIGENTE'
    CHECK (estado IN ('VIGENTE','APLICADO','PERDIDO','DEVUELTO','ANULADO')),
  devuelto_por INTEGER REFERENCES personal(id),
  devuelto_en TEXT
);
INSERT INTO abonos_nuevo (id, turno_id, monto, medio, recibido_en, registrado_por, referencia, estado)
  SELECT id, turno_id, monto, medio, recibido_en, registrado_por, referencia, estado FROM abonos;
DROP TABLE abonos;
ALTER TABLE abonos_nuevo RENAME TO abonos;
CREATE INDEX ix_abonos_turno ON abonos(turno_id)
""")


# ---------------------------------------------------------------- versión 4
# - Propietarios «sin registrar»: se agenda solo con nombre y celular; la cédula
#   y la dirección se completan al momento del servicio.
# - Especie de la raza (perro o gato) y la raza «Gato (sin raza definida)».
# - Ficha: corbatín y moños en las orejas, con su color.

def _v4(conn: sqlite3.Connection) -> None:
    from clinican.datos import semillas

    _ejecutar(conn, """
ALTER TABLE propietarios ADD COLUMN provisional INTEGER NOT NULL DEFAULT 0;
ALTER TABLE razas ADD COLUMN especie TEXT NOT NULL DEFAULT 'PERRO' CHECK (especie IN ('PERRO','GATO'));
ALTER TABLE servicios ADD COLUMN corbatin INTEGER;
ALTER TABLE servicios ADD COLUMN corbatin_color TEXT;
ALTER TABLE servicios ADD COLUMN monos INTEGER;
ALTER TABLE servicios ADD COLUMN monos_color TEXT
""")
    conn.executemany("INSERT OR IGNORE INTO razas (nombre, tamano, pelaje_complicado, especie) VALUES (?, ?, ?, ?)",
                     semillas.RAZAS_GATO)


# ---------------------------------------------------------------- versión 5
# Formato real de CLINICAN (ficha de peluquería en Excel y autorización en papel):
# - Sexo de la mascota.
# - Ficha: despunte, patas rasuradas, bigotes, orejas y desparasitación.
# - Términos: si siguen con el borrador inicial, se crea una versión nueva con el texto real
#   (quienes aceptaron el borrador deberán aceptar la versión nueva, RN-15).

def _v5(conn: sqlite3.Connection) -> None:
    from clinican.datos import semillas

    _ejecutar(conn, """
ALTER TABLE mascotas ADD COLUMN sexo TEXT CHECK (sexo IN ('HEMBRA','MACHO'));
ALTER TABLE servicios ADD COLUMN despunte INTEGER NOT NULL DEFAULT 0;
ALTER TABLE servicios ADD COLUMN patas_rasuradas INTEGER NOT NULL DEFAULT 0;
ALTER TABLE servicios ADD COLUMN desparasitacion INTEGER NOT NULL DEFAULT 0;
ALTER TABLE servicios ADD COLUMN bigotes INTEGER;
ALTER TABLE servicios ADD COLUMN orejas INTEGER
""")
    vigente = conn.execute(
        "SELECT version, contenido FROM textos_legales WHERE tipo = 'TERMINOS' AND vigente = 1 ORDER BY version DESC LIMIT 1"
    ).fetchone()
    if vigente is not None and vigente[1].strip() == semillas.TERMINOS_BORRADOR.strip():
        conn.execute("UPDATE textos_legales SET vigente = 0 WHERE tipo = 'TERMINOS'")
        conn.execute("INSERT INTO textos_legales (tipo, version, contenido, vigente) VALUES ('TERMINOS', ?, ?, 1)",
                     (vigente[0] + 1, semillas.TERMINOS_CLINICAN))


MIGRACIONES = {1: _v1, 2: _v2, 3: _v3, 4: _v4, 5: _v5}
VERSION_ACTUAL = max(MIGRACIONES)


def version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrar(conn: sqlite3.Connection) -> None:
    actual = version(conn)
    if actual > VERSION_ACTUAL:
        raise RuntimeError(
            f"La base de datos es de una versión más nueva del programa ({actual}) que la instalada "
            f"({VERSION_ACTUAL}). Actualice CLINICAN antes de abrirla."
        )
    for numero in range(actual + 1, VERSION_ACTUAL + 1):
        conn.execute("BEGIN IMMEDIATE")
        try:
            MIGRACIONES[numero](conn)
            conn.execute(f"PRAGMA user_version = {numero}")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")
