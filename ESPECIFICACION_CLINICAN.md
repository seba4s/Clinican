# CLINICAN — Sistema de reservas y fichas para la peluquería canina

Documento de especificación completo. Está escrito para que **Claude Code** lo lea y construya el proyecto por fases, en la carpeta `C:\Clinican` de un PC con Windows 11.

---

## 0. Instrucciones para Claude Code (leer primero)

1. Lee este documento completo antes de escribir código. Luego resume en pocas líneas lo que vas a construir y empieza por la **Fase 1**.
2. Trabaja **por fases** (sección 12). Al terminar cada fase: ejecuta las pruebas, muestra un resumen corto y espera confirmación antes de la siguiente. **No empieces la Fase 6 (WhatsApp)** sin autorización explícita.
3. La aplicación debe funcionar **100 % sin internet**. No uses librerías ni recursos que requieran conexión en tiempo de ejecución.
4. Toda la interfaz, los mensajes de error y los textos están en **español (Colombia)**. Debe ser fácil de usar para personas que no son técnicas: botones grandes, textos claros, pocas pantallas anidadas.
5. **Nada de precios, horarios, cupos o textos legales escritos a fuego en el código.** Todo va en la tabla `config` o en tablas de catálogo y se edita desde la pantalla de Configuración (solo el administrador).
6. La lógica de negocio va **separada de la interfaz** (capa `dominio`), para poder probarla sin abrir ventanas. Los permisos se validan en la capa de servicios, no solo ocultando botones.
7. Donde aparezca un supuesto marcado `[A-n]` (sección 13), impleméntalo como configurable y déjalo visible en la documentación. No detengas el trabajo por ellos.
8. Escribe pruebas automáticas (`pytest`) para cada regla `RN-nn` de la sección 7.
9. Este PC ejecuta el desarrollo, así que puedes compilar el `.exe` directamente con PyInstaller (sección 10).

---

## 1. Objetivo

Sistema de escritorio para **CLINICAN, Unidad Médica Veterinaria (servicio de peluquería)** que permita:

- Registrar propietarios y mascotas, con sus consentimientos legales.
- Registrar la ficha de cada servicio (tipo de corte, detalles y precio).
- Administrar los turnos del día con abonos, cupos y bloqueos de fechas.
- Manejar varios usuarios con roles (la jefe es la administradora).
- Funcionar sin internet, con base de datos local y copias de seguridad.
- En una fase final, permitir agendar por WhatsApp con la API oficial de Meta.

Datos del negocio:

| Dato | Valor |
|---|---|
| Nombre | CLINICAN — Unidad Médica Veterinaria, Servicio de Peluquería |
| Dirección | Calle 18A No. 2-05, Barrio Lorenzo |
| Teléfono y WhatsApp | 301 441 7194 |
| Nequi y llave Bre-B | 3046505967 — Angela Benavides |

El comprobante de pago se envía **al WhatsApp 301 441 7194**, nunca al número de Nequi.

---

## 2. Marca y diseño

Los archivos están en `assets/`: `logo_perro.png` (perro con fondo transparente) y `clinican.ico` (icono del ejecutable). La tarjeta original es `CamScanner_26-03-2026_12.45_page-0001.jpg`.

| Uso | Color aproximado (tomado de una foto; ajustar a la vista) |
|---|---|
| Verde lima (marca) | `#B7CF53` |
| Fucsia (acento, barra de estado) | `#FE028D` |
| Negro (texto, contornos) | `#14121D` |
| Azul (detalles, enlaces) | `#0EBCDE` |
| Fondo | Blanco / gris muy claro |

Pautas de diseño:

- **Texto negro sobre verde lima.** El texto blanco solo sobre fucsia y en botones grandes con letra en negrita, por contraste.
- Encabezado con el logo del perro y el nombre CLINICAN. Barra fucsia inferior con el teléfono, como en la tarjeta.
- Estados de turno con color **y** texto (no depender solo del color).
- Fuente mínima de 14 pt en formularios, botones de al menos 40 px de alto.
- Modo claro únicamente.

---

## 3. Stack y estructura

| Necesidad | Decisión |
|---|---|
| Lenguaje | Python 3.11 o superior |
| Interfaz | CustomTkinter (sobre Tkinter) |
| Base de datos | SQLite (`sqlite3` de la biblioteca estándar), un archivo local |
| Imágenes | Pillow |
| Excel (importación) | openpyxl |
| Pruebas | pytest |
| Empaquetado | PyInstaller |

Estructura de carpetas sugerida:

```
C:\Clinican\
├─ ESPECIFICACION_CLINICAN.md
├─ README.md                    (cómo instalar, usar y respaldar; en español)
├─ requirements.txt
├─ construir.bat                (compila el .exe; sección 10)
├─ main.py
├─ assets\                      (logo_perro.png, clinican.ico)
├─ clinican\
│  ├─ dominio\                  (reglas de negocio puras: cupos, precios, estados)
│  ├─ datos\                    (SQLite, migraciones, repositorios)
│  ├─ servicios\                (casos de uso + permisos por rol)
│  └─ ui\                       (pantallas CustomTkinter)
├─ tests\
├─ datos\                       (clinican.db; NO se borra al recompilar)
└─ respaldos\                   (copias automáticas)
```

Reglas técnicas:

- Dinero en **pesos colombianos como enteros** (sin decimales). Fechas en ISO (`YYYY-MM-DD`) y horas `HH:MM`, hora local de Colombia.
- Migraciones simples con `PRAGMA user_version`.
- `PRAGMA foreign_keys = ON` en cada conexión.
- Una sola PC con varios usuarios que inician sesión. Si algún día se necesitan varios PCs a la vez, es otra arquitectura y queda fuera de alcance [A-7].

---

## 4. Personal, roles y permisos

Dos roles:

- **ADMIN**: solo la jefe. Debe existir **exactamente un** administrador activo (índice único).
- **PERSONAL**: asistente de peluquería, médica veterinaria, auxiliares y cualquier persona que se agregue.

Inicio de sesión con **usuario (nombre) y PIN** de 4 a 6 dígitos, guardado con `hashlib.pbkdf2_hmac` y sal propia. En el primer arranque, un asistente crea a la jefe como ADMIN.

| Acción | ADMIN (jefe) | PERSONAL |
|---|---|---|
| Agendar, editar y cancelar turnos | Sí | Sí |
| Registrar abonos | Sí | Sí |
| Crear y editar propietarios y mascotas | Sí | Sí |
| Llenar y editar fichas de servicio | Sí | Sí |
| Agregar o quitar **franjas sueltas libres** de una fecha | Sí | Sí |
| Desactivar un **día completo** o un rango de fechas | **Sí** | No |
| Desactivar franjas específicas no agendadas de una fecha | **Sí** | No |
| Agregar, editar, desactivar personal; cambiar PIN de otros | **Sí** | No |
| Cambiar precios, cupos, horarios base y valor del abono | **Sí** | No |
| Editar textos legales | **Sí** | No |
| Respaldar y restaurar | **Sí** | Solo respaldar |
| Ver el registro de auditoría | **Sí** | No |

Cada persona puede cambiar su propio PIN. La jefe no puede desactivarse a sí misma sin antes transferir el rol de administrador a otra persona.

**Quién agendó:** cada turno guarda `agendado_por`. Al crear un turno se muestra la lista de personal activo; el sistema propone a quien inició sesión y se puede cambiar. Es obligatorio elegir a alguien.

**Personal por día (informativo):** lunes a viernes atienden 3 personas y los sábados 4. Se puede mostrar en la agenda. **No** limita los cupos; los cupos se definen por categoría (RN-02 y RN-03).

---

## 5. Catálogos y precios

### 5.1 Razas

| Raza | Tamaño | Pelaje complicado |
|---|---|---|
| Poodle (Caniche) Toy y Miniatura | PEQUEÑA | No |
| Bulldog Francés | PEQUEÑA | No |
| Yorkshire Terrier | PEQUEÑA | No |
| Shih Tzu | PEQUEÑA | No |
| Chihuahua | PEQUEÑA | No |
| Schnauzer Miniatura | PEQUEÑA | No |
| Schnauzer | MEDIANA | No |
| Pitbull y similares | MEDIANA | No |
| Labrador Retriever | GRANDE | No |
| Golden Retriever | GRANDE | No |
| Pastor Alemán | GRANDE | No |
| Husky | GRANDE | **Sí** |
| Perro mestizo (sin raza) | *se elige al registrar la mascota* | Se elige |

El administrador puede agregar razas y marcar cualquier raza como "pelaje complicado" ("husky o razas similares"). Cada mascota puede tener su propio tamaño y su propia marca de pelaje complicado, que prevalecen sobre los de la raza.

### 5.2 Precios (todos editables en Configuración)

| Concepto | Pequeña | Mediana | Grande |
|---|---|---|---|
| **Precio mínimo del servicio** | $45.000 | $50.000 en adelante | $60.000 a $70.000 en adelante |
| Extra baño medicado o antipulgas (por baño) | +$5.000 | +$10.000 | +$10.000 |

Otros valores:

| Concepto | Valor |
|---|---|
| Corte con tijera, **total mínimo** (no se suma al base) | $50.000 |
| Sesión de desenredado | $60.000 por sesión, máximo una por día |
| Abono mínimo | $20.000 **por mascota** |

Claves de configuración sugeridas: `precio_min_PEQUENA=45000`, `precio_min_MEDIANA=50000`, `precio_min_GRANDE=60000`, `precio_ref_max_GRANDE=70000`, `tijera_total_min=50000`, `extra_bano_PEQUENA=5000`, `extra_bano_MEDIANA=10000`, `extra_bano_GRANDE=10000`, `desenredado_sesion=60000`, `abono_minimo=20000`, `minutos_pendiente=30`, `horas_minimas_aviso=12` [A-4].

El precio **lo define la estilista** el día del servicio según nudos, piel, pulgas, agresividad o tamaño. El sistema **sugiere** el mínimo y muestra una advertencia (no un bloqueo) si escribe un valor menor.

### 5.3 Franjas base de turnos

Lunes a sábado (los sábados con el mismo horario). Domingo cerrado.

| Jornada | Horas |
|---|---|
| Mañana | 08:30, 09:00, 09:30, 10:00, 10:30, 11:00, 11:30 |
| Tarde | 14:30, 15:00, 15:30, 16:00, 16:30 |

### 5.4 Cupos por franja

Cada franja admite, **como máximo**, este número de mascotas por categoría de cupo (configurable):

| Categoría de cupo | Cupo por franja |
|---|---|
| `MAQUINA` (corte a máquina y baño y deslanado; mascotas medianas, y pequeñas según [A-1]) | 2 |
| `GRANDE` | 1 |
| `TIJERA` | 1 |
| `COMPLICADO` (husky o razas similares) | 1 |

Los cupos son **independientes entre categorías** [A-2]: una misma franja puede tener a la vez 2 de `MAQUINA`, 1 `GRANDE`, 1 `TIJERA` y 1 `COMPLICADO`.

---

## 6. Modelo de datos (SQLite)

Esquema de referencia. Claude Code puede ajustar nombres o tipos si lo justifica, sin cambiar el significado. Todas las tablas llevan `creado_en` (por defecto `datetime('now','localtime')`).

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE personal (
  id INTEGER PRIMARY KEY,
  nombre TEXT NOT NULL UNIQUE,
  cargo TEXT NOT NULL,                       -- 'Jefe', 'Asistente de peluquería', 'Médica veterinaria', ...
  rol TEXT NOT NULL CHECK (rol IN ('ADMIN','PERSONAL')),
  pin_hash TEXT NOT NULL,
  pin_sal TEXT NOT NULL,
  activo INTEGER NOT NULL DEFAULT 1,
  creado_en TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE UNIQUE INDEX ux_un_admin ON personal(rol) WHERE rol = 'ADMIN' AND activo = 1;

CREATE TABLE razas (
  id INTEGER PRIMARY KEY,
  nombre TEXT NOT NULL UNIQUE,
  tamano TEXT CHECK (tamano IN ('PEQUENA','MEDIANA','GRANDE')),   -- NULL = se define por mascota
  pelaje_complicado INTEGER NOT NULL DEFAULT 0,
  activa INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE propietarios (
  id INTEGER PRIMARY KEY,
  nombre TEXT NOT NULL,
  cedula TEXT NOT NULL UNIQUE,
  celular1 TEXT NOT NULL,
  celular2 TEXT,
  direccion TEXT NOT NULL,
  requiere_nuevo_abono INTEGER NOT NULL DEFAULT 0,   -- RN-10
  creado_en TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  actualizado_en TEXT
);

CREATE TABLE mascotas (
  id INTEGER PRIMARY KEY,
  propietario_id INTEGER NOT NULL REFERENCES propietarios(id),
  nombre TEXT NOT NULL,
  raza_id INTEGER NOT NULL REFERENCES razas(id),
  tamano_manual TEXT CHECK (tamano_manual IN ('PEQUENA','MEDIANA','GRANDE')),  -- obligatorio si la raza no define tamaño
  pelaje_complicado_manual INTEGER,          -- NULL = usar el de la raza
  edad_anios INTEGER,
  edad_meses INTEGER DEFAULT 0,
  fecha_ultima_visita TEXT,                  -- editable a mano (RN-14)
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
  UNIQUE (tipo, version)
);

CREATE TABLE consentimientos (
  id INTEGER PRIMARY KEY,
  propietario_id INTEGER NOT NULL REFERENCES propietarios(id),
  mascota_id INTEGER REFERENCES mascotas(id),         -- solo para RESPONSABILIDAD
  tipo TEXT NOT NULL CHECK (tipo IN ('TERMINOS','DATOS','RESPONSABILIDAD')),
  texto_id INTEGER NOT NULL REFERENCES textos_legales(id),
  condiciones TEXT,                                    -- JSON con las casillas marcadas (RESPONSABILIDAD)
  aceptado_en TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  registrado_por INTEGER NOT NULL REFERENCES personal(id)
);

CREATE TABLE servicios (                                -- la "ficha de servicio"
  id INTEGER PRIMARY KEY,
  mascota_id INTEGER NOT NULL REFERENCES mascotas(id),
  fecha TEXT NOT NULL,
  tipo_servicio TEXT NOT NULL CHECK (tipo_servicio IN ('MAQUINA','TIJERA','BANO_DESLANADO')),
  largo_maquina TEXT CHECK (largo_maquina IN ('1CM','MEDIO_CM')),   -- solo con MAQUINA
  bano_medicado INTEGER NOT NULL DEFAULT 0,
  bano_antipulgas INTEGER NOT NULL DEFAULT 0,
  cantidad_banos_extra INTEGER NOT NULL DEFAULT 1,      -- veces que se cobra el extra
  copete INTEGER,                                       -- 1 = se deja, 0 = no
  barbas INTEGER,
  cola_leon INTEGER,
  cola_estilo TEXT CHECK (cola_estilo IN ('COMPLETA','AL_RAS')),    -- solo corte bajito [A-5]
  forma_cara TEXT CHECK (forma_cara IN ('REDONDA','PROPORCIONAL','PAREJA_AL_CUERPO')),  -- solo corte bajito
  cond_agresiva INTEGER NOT NULL DEFAULT 0,
  cond_nudos_extremos INTEGER NOT NULL DEFAULT 0,
  cond_problemas_piel INTEGER NOT NULL DEFAULT 0,
  cond_plagas INTEGER NOT NULL DEFAULT 0,
  cond_edad_avanzada INTEGER NOT NULL DEFAULT 0,
  estado TEXT NOT NULL DEFAULT 'PLANEADO'
    CHECK (estado IN ('PLANEADO','REVISION_ESTILISTA','EN_SESIONES','REALIZADO','CANCELADO')),
  precio_minimo INTEGER NOT NULL,                       -- sugerido por el sistema
  precio_final INTEGER,                                 -- lo escribe la estilista
  extras INTEGER NOT NULL DEFAULT 0,                    -- baños medicados/antipulgas
  total INTEGER,
  observaciones TEXT,
  creado_por INTEGER NOT NULL REFERENCES personal(id),
  creado_en TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE sesiones_desenredado (
  id INTEGER PRIMARY KEY,
  servicio_id INTEGER NOT NULL REFERENCES servicios(id),
  fecha TEXT NOT NULL,
  precio INTEGER NOT NULL,                              -- 60000 por defecto
  notas TEXT,
  realizada_por INTEGER REFERENCES personal(id),
  UNIQUE (servicio_id, fecha)                           -- máximo una por día (RN-13)
);

CREATE TABLE franjas_base (                             -- plantilla semanal
  id INTEGER PRIMARY KEY,
  dia_semana INTEGER NOT NULL CHECK (dia_semana BETWEEN 1 AND 6),  -- 1 = lunes ... 6 = sábado
  hora TEXT NOT NULL,
  jornada TEXT NOT NULL CHECK (jornada IN ('MANANA','TARDE')),
  activa INTEGER NOT NULL DEFAULT 1,
  UNIQUE (dia_semana, hora)
);

CREATE TABLE franjas_ajuste (                           -- cambios puntuales por fecha
  id INTEGER PRIMARY KEY,
  fecha TEXT NOT NULL,
  hora TEXT NOT NULL,
  accion TEXT NOT NULL CHECK (accion IN ('AGREGAR','QUITAR')),
  creado_por INTEGER NOT NULL REFERENCES personal(id),
  UNIQUE (fecha, hora)
);

CREATE TABLE bloqueos (                                 -- solo ADMIN (RN-11)
  id INTEGER PRIMARY KEY,
  fecha TEXT NOT NULL,
  hora TEXT,                                            -- NULL = todo el día
  motivo TEXT,
  creado_por INTEGER NOT NULL REFERENCES personal(id),
  UNIQUE (fecha, hora)
);

CREATE TABLE turnos (
  id INTEGER PRIMARY KEY,
  fecha TEXT NOT NULL,
  hora TEXT NOT NULL,
  mascota_id INTEGER NOT NULL REFERENCES mascotas(id),
  servicio_id INTEGER REFERENCES servicios(id),
  grupo_id INTEGER,                                     -- mismo propietario, misma visita (RN-09)
  categoria_cupo TEXT NOT NULL CHECK (categoria_cupo IN ('MAQUINA','GRANDE','TIJERA','COMPLICADO')),
  estado TEXT NOT NULL DEFAULT 'PENDIENTE_ABONO'
    CHECK (estado IN ('PENDIENTE_ABONO','CONFIRMADO','EN_PROCESO','LISTA','ATENDIDO',
                      'LIBERADO','NO_ASISTIO_AVISO','NO_ASISTIO_SIN_AVISO','NO_ATENDIDO')),
  pendiente_hasta TEXT,                                 -- creado_en + 30 min (RN-07)
  motivo_liberacion TEXT CHECK (motivo_liberacion IN ('EXPIRO','OTRO_PAGO_PRIMERO','MANUAL')),
  avisado_en TEXT,                                      -- cuándo avisó el dueño que no iría (RN-10)
  motivo_no_atendido TEXT CHECK (motivo_no_atendido IN ('AGRESIVIDAD','CONDUCTA','ENFERMEDAD_NO_INFORMADA')),
  llamada_en TEXT,                                      -- cuándo se llamó al dueño (RN-16 y aviso de mascota lista)
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
  referencia TEXT,                                      -- nota sobre el comprobante recibido por WhatsApp
  estado TEXT NOT NULL DEFAULT 'VIGENTE' CHECK (estado IN ('VIGENTE','APLICADO','PERDIDO'))
);

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
```

Datos iniciales (semillas): razas de la sección 5.1, franjas base de la 5.3, valores de la 5.2 y 5.4, datos de pago y los textos legales de la sección 9.

---

## 7. Reglas de negocio

**RN-01 Permisos.** Se aplican según la tabla de la sección 4, validados en la capa de servicios. Toda acción sensible queda en `auditoria`.

**RN-02 Categoría de cupo.** Se calcula al crear el turno, en este orden:
1. Si la mascota tiene pelaje complicado (por raza o marca manual) → `COMPLICADO`.
2. Si el servicio es `TIJERA` → `TIJERA`.
3. Si el tamaño es `GRANDE` → `GRANDE`.
4. En cualquier otro caso (mediana o pequeña, corte a máquina o baño y deslanado) → `MAQUINA` [A-1].

**RN-03 Cupos.** Una franja acepta un turno nuevo solo si, para su categoría, los turnos `CONFIRMADO`, `EN_PROCESO` y `LISTA` de esa fecha y hora no superan el cupo configurado (sección 5.4). El sistema muestra los cupos libres por categoría en cada franja. La validación se repite dentro de una transacción al confirmar.

**RN-04 Franjas disponibles de una fecha** = `franjas_base` del día de la semana − franjas `QUITAR` + franjas `AGREGAR` − `bloqueos`. Domingo no tiene franjas salvo que se agreguen a mano.

**RN-05 Crear un turno.** Requiere: mascota, servicio (al menos el tipo), fecha, hora, `agendado_por` y que el propietario tenga aceptados los términos y la autorización de datos (RN-15). El turno nace `PENDIENTE_ABONO` con `pendiente_hasta` = ahora + 30 minutos. Si se registra el abono en el mismo momento, pasa directo a `CONFIRMADO`. Si el propietario tiene `requiere_nuevo_abono = 1`, el sistema exige el abono antes de crear el turno.

**RN-06 Confirmación por abono.** El turno pasa a `CONFIRMADO` cuando se registra un abono de **al menos $20.000 para esa mascota** (medios: Nequi, Bre-B o efectivo). El abono se descuenta del total del servicio (saldo = total − abonos) [A-6].

**RN-07 Expiración.** Un turno `PENDIENTE_ABONO` cuyo `pendiente_hasta` ya pasó pasa a `LIBERADO` con motivo `EXPIRO`. La revisión corre cada 30 segundos mientras la app está abierta y también al iniciar. Los pendientes vigentes se muestran con cuenta regresiva.

**RN-08 Quien paga primero.** Varios pendientes pueden pedir el mismo cupo. Gana el primero en registrar el abono. Al confirmarse, si el cupo se agota, los demás pendientes de esa franja y categoría pasan a `LIBERADO` con motivo `OTRO_PAGO_PRIMERO` y el sistema avisa al personal para que ofrezca otra hora.

**RN-09 Varias mascotas del mismo propietario.** Se agendan en una sola operación: se crea un turno por mascota con el mismo `grupo_id`.
- Las mascotas llegan juntas y se atienden por separado.
- El bloque inicia a las **09:00** en la mañana o a las **14:30** en la tarde, y ocupa **franjas consecutivas, una mascota por franja**, según el orden en que se listan [A-3]. La política y las horas de inicio son configurables (`politica_grupo`, `inicio_grupo_manana`, `inicio_grupo_tarde`).
- La franja de 08:30 queda para turnos individuales.
- Si no alcanzan las franjas de la jornada, el sistema propone continuar en la otra jornada u otro día, y la persona elige.
- El abono es de $20.000 por mascota. Puede registrarse un pago único para el grupo, que se reparte en abonos de $20.000 por turno.

**RN-10 No asistencia.**
- El personal marca el turno como no asistido y puede registrar `avisado_en` (cuándo avisó el dueño).
- Si el aviso se dio con **al menos `horas_minimas_aviso` horas** de anticipación (por defecto 12) → `NO_ASISTIO_AVISO`. El abono **no se reembolsa**, pero se conserva para reprogramar [A-4, A-8].
- Si no avisó, o avisó fuera de plazo → `NO_ASISTIO_SIN_AVISO`. El abono pasa a `PERDIDO` y el propietario queda con `requiere_nuevo_abono = 1` hasta pagar un nuevo abono.

**RN-11 Bloqueos.** Solo el ADMIN puede desactivar un día, un rango de fechas o franjas específicas. Solo se pueden bloquear franjas **sin turnos activos**. Si un día ya tiene turnos, el sistema lista los turnos afectados y el ADMIN decide cómo resolverlos (mover, cancelar o cancelar el bloqueo). El personal solo agrega o quita franjas sueltas libres (`franjas_ajuste`).

**RN-12 Precios.**
- `precio_minimo` = mínimo por tamaño (5.2). Si el servicio es `TIJERA`: `max(mínimo por tamaño, tijera_total_min)`. El corte con tijera **no se suma** al base.
- `extras` = número de baños extra × valor del extra según tamaño, si hay baño medicado o antipulgas.
- `total` = `precio_final` + `extras`. Si `precio_final` es menor que `precio_minimo`, se advierte pero se permite.
- Las sesiones de desenredado se cobran aparte (RN-13) y se muestran sumadas en la ficha.

**RN-13 Desenredado por sesiones.** Se ofrece cuando la estilista revisa una mascota con muchos nudos, sobre todo si se pidió corte con tijera. El servicio pasa a `REVISION_ESTILISTA` y luego a `EN_SESIONES`.
- Cada sesión cuesta $60.000. Máximo **una por día** (restricción única).
- El proceso puede durar varios días, y cada sesión queda con su fecha.
- Al terminar, la estilista cierra las sesiones y define el servicio final.

**RN-14 Última visita.** `fecha_ultima_visita` se actualiza sola al marcar un turno `ATENDIDO`, pero siempre se puede corregir a mano.

**RN-15 Consentimientos.**
- Antes de crear un turno debe existir aceptación vigente de **términos** y de **tratamiento de datos** del propietario (una vez, con fecha y versión del texto).
- Al registrar una mascota, o en cada servicio, se puede marcar la sección de **responsabilidad** con las condiciones difíciles: agresiva, nudos extremos, problemas de piel, plagas, edad avanzada. Esa aceptación se guarda con fecha.
- Si cambia el texto legal, se crea una nueva versión y se pide nueva aceptación.

**RN-16 Servicio imposible.** Si no se puede atender a la mascota (agresividad, problemas de conducta o enfermedad no informada), el turno pasa a `NO_ATENDIDO` con su motivo. El sistema resalta el celular del propietario y registra la hora de la llamada para que retire a la mascota.

**RN-17 Aviso de mascota lista.** Cuando la mascota termina, el turno pasa a `LISTA`, se destacan los dos celulares y se registra la hora de la llamada. Al entregarla y cobrar el saldo, pasa a `ATENDIDO`.

### Estados del turno

```
PENDIENTE_ABONO → CONFIRMADO → EN_PROCESO → LISTA → ATENDIDO
        │              │
        ├─→ LIBERADO   ├─→ NO_ASISTIO_AVISO
                       ├─→ NO_ASISTIO_SIN_AVISO
                       └─→ NO_ATENDIDO  (también desde EN_PROCESO)
```

---

## 8. Pantallas

1. **Inicio de sesión** (usuario y PIN) y asistente del primer arranque.
2. **Inicio / Agenda del día:** dos bloques (mañana y tarde) con las franjas, sus turnos en tarjetas y los cupos libres. Cada tarjeta muestra: hora, nombre de la mascota, **raza**, **propietario**, **celular**, **tipo de servicio** (corte a máquina, corte a tijera, baño y deslanado), **si hizo o no el abono** y quién agendó. Colores por estado. Cuenta regresiva en los pendientes.
3. **Nuevo turno:** buscar propietario por cédula o nombre; elegir una o varias mascotas; elegir fecha, franja y tipo de servicio; **"¿Quién agenda?"**; registrar abono (monto, medio). Muestra los datos de pago (Nequi / Bre-B) y el WhatsApp para el comprobante.
4. **Propietarios y mascotas:** búsqueda, alta y edición, historial de servicios, fecha de última visita editable y marca "requiere nuevo abono".
5. **Ficha de servicio:** tipo de corte, largo, extras, copete, barbas, cola de león y su estilo, forma de la cara (estos dos últimos solo si el corte es bajito), casillas de condiciones difíciles, edad, observaciones, precio mínimo sugerido, precio final y total.
6. **Desenredado:** sesiones por fecha, total acumulado y botón para cerrar el proceso.
7. **Términos y consentimientos:** texto vigente, casillas de aceptación, condiciones de responsabilidad y fecha de aceptación guardada.
8. **Administración de horarios** (solo ADMIN): calendario para bloquear días o franjas y editar la plantilla semanal. El personal solo ve agregar o quitar franjas sueltas libres.
9. **Personal** (solo ADMIN): alta, edición, desactivación y cambio de PIN.
10. **Configuración** (solo ADMIN): precios, cupos, abono, datos de pago, horas de aviso, razas y tamaños, textos legales.
11. **Respaldo:** botón "Respaldar ahora" y lista de copias.

---

## 9. Textos legales (versión inicial)

Se guardan en `textos_legales` (versión 1). Los marcadores `{...}` se reemplazan con valores de `config`.

### 9.1 Términos y condiciones

> **TÉRMINOS Y CONDICIONES DEL SERVICIO DE PELUQUERÍA — CLINICAN**
>
> 1. **Responsabilidad.** CLINICAN no será responsable en caso de muerte accidental (por ejemplo, un ataque al corazón), ni por conducta agresiva de la mascota, ni en el caso de mascotas de edad avanzada, mascotas que no están acostumbradas a la peluquería, mascotas nerviosas o enfermas. En caso fortuito, CLINICAN hará todo lo que esté en sus manos para que no ocurra ningún imprevisto durante el servicio.
> 2. **Información y prioridad.** CLINICAN explicará y responderá las dudas del propietario al momento del servicio, dando prioridad a la integridad y la salud de la mascota.
> 3. **Estado de la mascota y precio.** El propietario declara el estado real de su mascota. El precio final lo define la estilista el día del servicio, según el estado del pelaje (nudos), la piel, la presencia de pulgas o plagas, el tamaño y el comportamiento. Cuando el pelaje tenga nudos extremos, la estilista podrá proponer sesiones de desenredado ($60.000 por sesión, una sesión por día, pudiendo durar varios días para no estresar a la mascota).
> 4. **Abono y agendamiento.** El turno solo se agenda una vez realizado el abono mínimo de {abono_minimo} por mascota, pagado por Nequi, llave Bre-B o en efectivo en el local. El comprobante debe enviarse al WhatsApp {whatsapp_numero}. Si el turno se solicita y no se paga el abono, se pierde automáticamente después de {minutos_pendiente} minutos. Si otra persona toma o paga primero el mismo turno, se da prioridad a quien pague primero.
> 5. **No asistencia.** El abono no es reembolsable en caso de no asistir al turno. Si no se asiste y no se informa con al menos {horas_minimas_aviso} horas de anticipación, se deberá abonar de nuevo para agendar otro turno.
> 6. **Imposibilidad de prestar el servicio.** Si no es posible atender a la mascota por agresividad, problemas de conducta o enfermedades no especificadas por el propietario, CLINICAN llamará al propietario para que retire a su mascota de las instalaciones.

### 9.2 Autorización de tratamiento de datos personales (Ley 1581 de 2012)

> Autorizo a **CLINICAN — Unidad Médica Veterinaria** (Calle 18A No. 2-05, Barrio Lorenzo; teléfono y WhatsApp {whatsapp_numero}) para recolectar, almacenar y usar mis datos personales (nombre, cédula, celulares y dirección) con las siguientes finalidades: agendar y prestar el servicio de peluquería, llevar el historial de mi mascota, registrar los abonos y pagos, y contactarme por llamada o WhatsApp sobre mis turnos y el estado de mi mascota.
>
> Conozco que, como titular, tengo derecho a conocer, actualizar, rectificar y solicitar la supresión de mis datos, y a revocar esta autorización, comunicándome al {whatsapp_numero}. Mis datos no se venden ni se comparten con terceros, salvo obligación legal.

### 9.3 Responsabilidad por mascota difícil

> Declaro que mi mascota presenta las condiciones que marqué a continuación: ☐ agresiva ☐ pelo con nudos extremos ☐ problemas de piel ☐ pulgas u otras plagas ☐ edad avanzada.
>
> Entiendo que estas condiciones pueden aumentar el precio, requerir sesiones de desenredado o la revisión de la estilista, y que CLINICAN podrá suspender el servicio si la seguridad de la mascota o del personal está en riesgo, sin responsabilidad por las consecuencias de estas condiciones, según los términos y condiciones.

**Nota legal:** estos textos son un borrador redactado con las reglas del negocio y **no son asesoría jurídica**. Deben ser revisados por un abogado, especialmente la cláusula 1 (una exoneración de responsabilidad puede no aplicar en casos de negligencia) y la política de tratamiento de datos, que la ley exige tener disponible por escrito.

---

## 10. Empaquetado, instalación y respaldo

**Ejecutable.** Un archivo `construir.bat` que, con doble clic:
1. Crea un entorno virtual (`.venv`) e instala `requirements.txt`.
2. Ejecuta PyInstaller en modo carpeta (más estable con CustomTkinter):
   ```
   pyinstaller --noconfirm --windowed --name CLINICAN --icon assets\clinican.ico ^
     --collect-all customtkinter --add-data "assets;assets" main.py
   ```
3. Crea un **acceso directo en el escritorio** a `dist\CLINICAN\CLINICAN.exe` con el icono del perro.

La base de datos vive en `C:\Clinican\datos\clinican.db`, fuera de `dist`, para no perderse al recompilar. El programa debe funcionar tanto ejecutado con Python como ya empaquetado (rutas correctas con `sys.frozen`).

**Respaldo.**
- Copia automática con la API `sqlite3.Connection.backup` al cerrar la app y una vez al día, en `C:\Clinican\respaldos\`, conservando las últimas 30.
- Botón "Respaldar ahora" que copia a otra carpeta o a una memoria USB.
- Función de restaurar (solo ADMIN), que primero hace una copia del estado actual.

**Manual corto.** Un `MANUAL_USUARIO.md` de una o dos páginas en español, con los flujos: agendar un turno, registrar un abono, atender una mascota, bloquear un día y respaldar.

---

## 11. Importación de mascotas desde Excel

Hoy cada mascota está en su propio archivo de Excel. **No hay archivo de ejemplo todavía** [A-9], así que:
- En la Fase 2 no se construye la importación real. Solo se entrega una **plantilla `plantilla_importacion.xlsx`** (una fila por mascota) y una herramienta que la carga y valida.
- Al conseguir un Excel real, se adapta el lector (`importar_excel.py`) a su formato.
- Al importar, si dos mascotas comparten cédula, se agrupan bajo el mismo propietario. Se muestra un reporte de filas rechazadas.

---

## 12. Fases y criterios de aceptación

| Fase | Contenido | Criterio de aceptación |
|---|---|---|
| **1. Base y seguridad** | Proyecto, esquema y migraciones, semillas, tema visual, login con PIN, primer arranque, gestión de personal, auditoría | La jefe crea personal; un PERSONAL no ve ni puede ejecutar acciones de ADMIN; hay un solo ADMIN activo |
| **2. Propietarios, mascotas y legal** | CRUD, búsqueda, razas, textos legales y consentimientos con fecha y versión, plantilla de importación | No se puede crear turno sin consentimientos; una mascota mestiza exige elegir tamaño |
| **3. Ficha y precios** | Ficha de servicio completa, cálculo de precios, extras, desenredado por sesiones | Los precios sugeridos coinciden con la sección 5.2; una sola sesión por día por servicio |
| **4. Turnos** | Agenda, franjas, ajustes, bloqueos, cupos, abonos, expiración, quien paga primero, varias mascotas, no asistencia, estados | Se cumplen RN-03 a RN-11 y RN-15 a RN-17 |
| **5. Empaquetado** | `construir.bat`, `.exe`, acceso directo, respaldo automático y manual, manual de usuario | Instalación limpia en Windows 11 sin internet; respaldo y restauración probados |
| **6. WhatsApp** | Sección 14; solo con autorización explícita | Ver sección 14 |

**Pruebas mínimas (`pytest`)**
- Categoría de cupo (RN-02) para cada raza de ejemplo, incluido el husky y el mestizo.
- Cupos por categoría en una misma franja (2 `MAQUINA`, 1 `GRANDE`, 1 `TIJERA`, 1 `COMPLICADO`) y rechazo del excedente.
- Expiración a los 30 minutos y liberación del cupo.
- Dos pendientes por el mismo cupo: gana el primero en pagar y el otro queda `LIBERADO`.
- Grupo de 5 mascotas: turnos consecutivos desde las 09:00 y desde las 14:30, con desborde a otra jornada.
- Aviso de ausencia con 11 h y con 12 h de anticipación; marca `requiere_nuevo_abono`.
- Precio mínimo con y sin tijera para cada tamaño; extras de baño por tamaño.
- Una sola sesión de desenredado por día.
- Bloqueo de un día con turnos activos (debe rechazar) y sin turnos (debe permitir).
- Permisos por rol para cada acción de la tabla de la sección 4.
- Respaldo y restauración.

---

## 13. Supuestos por confirmar

Están implementados como configurables. Se pueden cambiar sin reescribir código.

| Id | Supuesto |
|---|---|
| A-1 | Las mascotas **pequeñas** con corte a máquina o baño comparten el cupo `MAQUINA` (2 por franja). La usuaria solo mencionó medianas. |
| A-2 | Los cupos por categoría son independientes: una franja puede tener 2 + 1 + 1 + 1 mascotas a la vez. |
| A-3 | En un grupo de mascotas, se usa una franja por mascota, desde las 09:00 (mañana) o 14:30 (tarde). La franja de 08:30 es solo para turnos individuales. |
| A-4 | Se dijo "mínimo 2 a 12 horas para avisar". Se usa **12 horas** por defecto en `horas_minimas_aviso` (editable). El texto legal usa ese valor. |
| A-5 | "Cola de león, completa o al ras del cuerpo" se interpretó como el **estilo de la cola de león**, disponible solo en cortes bajitos (1 cm o ½ cm), igual que la forma de la cara. |
| A-6 | El abono se descuenta del total: saldo = total − abonos. |
| A-7 | Una sola PC con varios usuarios; no hay acceso simultáneo desde varios equipos. |
| A-8 | Si el dueño avisa a tiempo que no irá, el abono no se devuelve en dinero, pero se conserva para reprogramar. |
| A-9 | No hay Excel de ejemplo; la importación se adapta cuando exista uno. |

---

## 14. Fase 6 — WhatsApp con la API oficial de Meta (al final)

**No implementar hasta terminar y aceptar las fases 1 a 5 y recibir autorización.**

**Objetivo:** que el cliente agende por WhatsApp de forma automática, se le informen los términos y se le pida el abono.

**Flujo:**
1. El cliente escribe; el bot pide los datos del propietario y de la mascota (o los reconoce por la cédula).
2. Envía los **términos y condiciones** y pide su aceptación explícita, que se guarda como consentimiento (`origen = WHATSAPP`).
3. Ofrece franjas libres según cupos, con varias mascotas si aplica.
4. Crea el turno `PENDIENTE_ABONO` y da los datos de pago (Nequi y Bre-B 3046505967, Angela Benavides, y $20.000 por mascota).
5. El cliente envía el **comprobante por este mismo chat**. El personal lo revisa en la app y pulsa "Confirmar abono". No se intenta verificar pagos automáticamente.
6. Si pasan 30 minutos sin abono, el turno se libera y el bot avisa.

**Puntos técnicos y de decisión (resolver al llegar a esta fase):**
- La API necesita un **servidor con dirección pública HTTPS** (webhook), pero la base de datos es local. Opciones: (a) exponer un servicio local con un túnel seguro; (b) un servicio pequeño en la nube que guarde una copia de las franjas y cupos y sincronice con la app local. Elegir con la usuaria.
- Requiere cuenta de Meta Business verificada, número de teléfono y plantillas de mensajes aprobadas. Los mensajes que inicia el negocio fuera de la ventana de 24 horas requieren plantilla. Verificar en ese momento las **tarifas vigentes por conversación en Colombia**.
- **Si el número 301 441 7194 pasa a la API**, revisar antes cómo afecta su uso normal en WhatsApp o WhatsApp Business (Meta ha cambiado esta política; consultar la documentación vigente).
- Guardar el token de acceso fuera del código (variables de entorno o archivo cifrado).

---

## 15. Fuera de alcance

- Impresión de fichas o de comprobantes de abono (la usuaria indicó que no hace falta).
- Verificación automática de pagos de Nequi o Bre-B.
- Facturación electrónica, inventario o contabilidad.
- Uso simultáneo desde varios computadores.
- Aplicación móvil.
