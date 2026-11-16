# CLINICAN — Agenda de la peluquería canina

Programa de escritorio para **CLINICAN, Unidad Médica Veterinaria (servicio de peluquería)**:
turnos por franjas de 30 minutos con cupos por categoría, abonos, saldo a favor, fichas de
servicio, recordatorios por WhatsApp con bandeja de salida, respaldos e importación desde Excel.
Funciona en Windows 11 sin internet, con una base SQLite local. Solo el canal de WhatsApp usa la
red, y si falla, los recordatorios quedan pendientes y se reintentan.

| Carpeta | Contenido |
|---|---|
| `backend/` | Reglas de negocio, base de datos, servicios, adaptadores (WhatsApp, Excel), demostración y sus pruebas. También la plantilla `plantilla_importacion.xlsx` y los scripts de WhatsApp. |
| `frontend/` | Interfaz de escritorio en PySide6/QML, `main.py` (abre el programa), el acceso directo y las pruebas de la ventana. |

La primera versión del programa (interfaz en CustomTkinter) sigue en la etiqueta git
`app-anterior`.

## Instalación en Windows (una sola vez)

Requiere Python 3.11 o más reciente. Desde la carpeta del repositorio:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r frontend\requirements.txt
```

`frontend\requirements.txt` instala también lo del backend. En Linux o macOS, el intérprete queda
en `.venv/bin/python`.

## Abrir el programa

```powershell
.\.venv\Scripts\python.exe frontend\main.py
```

Para abrirlo desde el escritorio, sin consola, crea el acceso directo una sola vez (queda con el
ícono del perro; si falta el `.venv`, lo crea):

```powershell
powershell -ExecutionPolicy Bypass -File .\frontend\crear_acceso_directo.ps1
```

La base queda en `%USERPROFILE%\Clinican\clinican.db` (o en la ruta de la variable `CLINICAN_BD`).
Para correr solo el backend, sin ventana, hasta Ctrl+C: `frontend\main.py --sin-interfaz`.

Al iniciar, el programa abre la base, aplica las migraciones pendientes, libera los turnos con abono
vencido, elige el canal de notificaciones según la configuración y arranca el despachador de
recordatorios (cada 60 s), el respaldo diario y el barrido de abonos vencidos (cada 60 s). Al cerrar
la ventana (o con Ctrl+C sin interfaz) hace un respaldo.

## Demostración de punta a punta (sin ventanas)

```powershell
cd backend
..\.venv\Scripts\python.exe -m clinican.demo
```

Usa una base temporal y muestra, en orden:

1. las capas y sus dependencias reales, sin atajos;
2. dos hilos pidiendo a la vez el último cupo de máquina: solo uno lo obtiene;
3. un turno agendado sin red mientras WhatsApp falla: el recordatorio queda con reintento;
4. el cambio de canal de archivo a consola sin tocar la agenda.

## Pruebas

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest
cd ..\frontend
..\.venv\Scripts\python.exe -m pytest
```

- Solo la regla de capas: `..\.venv\Scripts\python.exe -m pytest tests/test_arquitectura.py` (en `backend`).
- Sin las pruebas de rendimiento sobre cinco años de datos (más rápido): agrega `-m "not lento"`.

Las mismas pruebas corren en GitHub Actions, en Windows y Ubuntu, en cada push y pull request
(`.github/workflows/pruebas.yml`).

## Interfaz (`frontend/`)

Hecha en PySide6 con QML: paneles
de vidrio translúcido sobre un fondo desenfocado, esquinas redondeadas y
transiciones suaves. Sigue el modo claro u oscuro de Windows.

| Sección | Qué hay |
|---|---|
| Agenda | Hoja del día tipo Excel (hora, cupo, mascota, raza, servicio, propietario, celular, abono y estado; los cupos «Libre» de cada hora agendan ahí mismo), pendientes de abono con su cuenta regresiva, panel del turno con las acciones de su estado, nuevo turno, mover, abono, inasistencia, ficha de servicio, bloquear horas |
| Clientes | Búsqueda por cédula, nombre, celular o mascota; datos, saldo a favor, autorización de datos (Ley 1581), mascotas, historial con fichas, unir duplicados, importar Excel |
| Recordatorios | Por enviar, enviados, fallidos (reintentar o corregir el celular) y descartados |
| Ajustes | Horario y bloqueos, cupos y abono, precios, razas, canal de recordatorios, respaldos y registro de cambios |

Atajos: Ctrl+N nuevo turno, Ctrl+F buscar cliente, Ctrl+1 a Ctrl+4 secciones,
← → cambiar de día en la agenda, Inicio volver a hoy, Esc cerrar un diálogo.

## Configuración

| Dónde | Qué |
|---|---|
| `CLINICAN_BD` (variable de entorno) | Ruta de la base. Por defecto `%USERPROFILE%\Clinican\clinican.db`. |
| `CLINICAN_WHATSAPP_TOKEN` | Token de acceso de WhatsApp Business (Graph API de Meta). |
| `CLINICAN_WHATSAPP_NUMERO_ID` | Id del número emisor de WhatsApp. |
| `CLINICAN_WHATSAPP_PLANTILLA` | Nombre de la plantilla aprobada. Por defecto `recordatorio_turno`. |
| `CLINICAN_WHATSAPP_IDIOMA` | Idioma de la plantilla. Por defecto `es`. |
| `CLINICAN_WHATSAPP_VERSION` | Versión de la Graph API. Por defecto `v25.0`. |

Si falta el token o el id del número, WhatsApp queda inactivo: cada envío falla,
se reintenta a los 1, 5 y 15 minutos y luego queda como FALLIDO.

Los celulares se guardan con 10 dígitos. Al enviar por WhatsApp se les antepone 57.

La configuración guardada en la base (tabla `configuracion`; si una clave falta,
se usa su valor por defecto):

| Clave | Por defecto |
|---|---|
| `cupos` | máquina 2, grande 1, tijera 1, complicado 1 |
| `abono` | 20000 |
| `minutos_expiracion` | 30 |
| `horario` | lunes a sábado, franjas de 9:00 a 16:30; domingo cerrado |
| `canal_notificaciones` | `archivo` (también `consola` y `whatsapp`) |
| `carpeta_respaldos` | `respaldos` (junto a la base si es relativa) |
| `respaldos_a_conservar` | 30 |
| `horas_antes_recordatorio` | 24 |
| `horas_antes_recordatorio_final` | 1 |

Con el canal `archivo`, los recordatorios se escriben, uno por línea, en
`recordatorios.txt`, en la carpeta de la base.

## Recordatorios por WhatsApp

Cada turno confirmado recibe dos recordatorios: **24 horas antes** y **1 hora antes**
(ambos configurables en Ajustes; 0 apaga uno). Si el turno se agenda con menos de
24 h de anticipación solo sale el de 1 h, y con menos de 1 h no sale ninguno. Si el
PC estuvo apagado, los pendientes salen al abrir Clinican; si ya es hora del de 1 h,
el de 24 h atrasado se descarta. «Hoy» o «el día de mañana» se calcula al enviar.

Activarlo:

1. En WhatsApp Manager de Meta, crea la plantilla **`recordatorio_turno`**, categoría
   **Utilidad**, idioma **Español**, con este cuerpo exacto:

   > Estimado cliente, le recordamos que {{1}}, tiene un turno de peluquería para {{2}}, a las {{3}}. En caso de no poder asistir, avisar con anterioridad para evitar pérdida del saldo abonado. Muchas gracias.

   Ejemplos para la revisión: {{1}} `el día de mañana, jueves 8 de octubre (08/10/2026)`,
   {{2}} `Roma`, {{3}} `9:00 am`.
2. Guarda el token y el id del número (sin escribirlos en ningún archivo):
   desde `backend`, `powershell -ExecutionPolicy Bypass -File .\configurar_whatsapp.ps1`
3. Prueba el envío sin crear turnos: desde `backend`, `..\.venv\Scripts\python.exe probar_whatsapp.py 3001234567`
   (con el número de prueba de Meta, ese celular debe estar en su lista de destinatarios).
4. En Clinican › Ajustes › Recordatorios y WhatsApp elige **WhatsApp**, guarda y vuelve a abrir Clinican.

Si un envío falla, Recordatorios › Fallidos muestra la causa en español (token vencido,
plantilla no aprobada, número no permitido, etc.). «Enviado» significa que Meta aceptó
el mensaje; la confirmación de entrega o lectura no se consulta (necesitaría un servidor
público para los webhooks).

## Importar mascotas desde Excel

Use `plantilla_importacion.xlsx` (en `backend/`), hoja **Mascotas**, una
fila por mascota:

```python
from clinican.adaptadores.importacion_excel import importar_mascotas_desde_excel
informe = importar_mascotas_desde_excel(con, "mascotas.xlsx", ahora=ahora)
print(informe.resumen)  # filas aceptadas y rechazadas, con el motivo de cada rechazo
```

Una fila mala no detiene la importación. Para cada fila:

- El propietario se busca por **cédula**. Si ya existe, la mascota se le agrega
  sin cambiar sus datos.
- El tamaño Pequeña, Mediana o Grande se guarda como pequeño, mediano o grande.
  Si se deja vacío, se usa el de la raza.
- "Pelaje complicado" es la marca que envía al cupo COMPLICADO. Es obligatoria
  para perros mestizos.
- La edad se guarda como fecha de nacimiento aproximada.
- La fecha de última visita se guarda solo como dato de la mascota.

## Reglas de negocio confirmadas

- **Un solo perfil**: no hay usuarios, roles, permisos ni PIN; el programa abre directo.
- **Horario**: lunes a sábado se reciben perros de 9:00 a 16:30. La última
  franja empieza a las 16:30, así que hay 16 franjas por día. La peluquería
  atiende hasta las 18:30. El domingo está cerrado. Se pueden bloquear días
  completos o rangos de horas, pero no si hay turnos activos en ese rango.
- **Cupos por franja**: 2 de máquina, 1 grande, 1 tijera y 1 complicado. Cada
  turno ocupa una sola franja.
  - Categoría: si la mascota está marcada como complicada, es COMPLICADO. Si
    no, y es grande, es GRANDE. Si no, y el corte es a tijera, es TIJERA. Si
    no, es MÁQUINA.
  - Ocupan cupo los pendientes de abono que no han vencido y los confirmados,
    en atención, atendidos y entregados.
  - El cupo se cuenta dentro de la misma transacción que crea el turno, así que
    dos personas no pueden tomar el último cupo a la vez.
- **Estados del turno**: pendiente de abono → confirmado → en atención →
  atendido → entregado. Un pendiente se puede liberar (con motivo) o cancelar.
  Un confirmado se puede cancelar o marcar como inasistencia.
- **Abono**: $20.000, que vence 30 minutos después de creado el turno.
  - Se aceptan abonos parciales (se van sumando) y pagos de más (el excedente
    queda como saldo a favor).
  - Si el abono vence, lo ya pagado y el saldo aplicado vuelven a quedar a favor
    del propietario.
- **Saldo a favor**: se aplica solo al siguiente turno del cliente. Si cubre
  todo el abono, el turno nace confirmado.
- **Cancelar**: lo pagado (abono más saldo aplicado) queda como saldo a favor,
  sin importar con cuánta anticipación se cancele.
- **Inasistencia**: si el cliente avisó con 12 horas o más de anticipación, el
  abono queda a favor; si no, se pierde.
- **Precios**: máquina $45.000, grande $70.000, tijera $50.000 y complicado
  $50.000, vigentes desde el 01/01/2000.
  - Cambiar un precio agrega una fila nueva con su fecha de vigencia.
  - También se puede corregir el valor de un precio ya registrado; queda auditado.
  - Todo el dinero se maneja en pesos enteros, sin decimales.
- **Ficha de servicio**: se crea al marcar el turno como atendido. Su precio
  final es el vigente en la fecha del turno y se puede editar (queda auditado).
- **Recordatorios**: dos por turno confirmado, 24 horas y 1 hora antes (configurables);
  si se agenda con menos anticipación, ese recordatorio no sale. Antes de enviarlo
  se verifica que el turno siga confirmado y no haya empezado.
- **Propietario**: la cédula es obligatoria y única, y el celular tiene
  exactamente 10 dígitos. Dos propietarios duplicados se pueden unir.
- **Autorización de datos (Ley 1581 de 2012)**: en Editar cliente se marca si el dueño
  autorizó el tratamiento de sus datos, con la fecha (no puede ser futura) y, si se quiere,
  cómo lo hizo (formato firmado, WhatsApp…). Retirarla es otro registro: el historial no se
  borra y cada cambio queda en la auditoría. Al unir duplicados, el historial pasa al cliente
  que queda. No bloquea turnos ni recordatorios; solo deja la evidencia.
- **Auditoría**: cada escritura deja registrado qué se hizo y cuándo.
- **Respaldos**: diario y al cerrar, verificados con `PRAGMA quick_check`. Se
  conservan los últimos 30. Antes de restaurar se respalda la base actual.

## Arquitectura

```
backend/
  clinican/
    dominio/      reglas puras (sin base de datos ni red)
    datos/        SQLite: conexión, migraciones, repositorios (único lugar con SQL)
    servicios/    casos de uso (transacciones, auditoría, bandeja, despachador, respaldos)
    adaptadores/  canales de notificación (archivo, consola, WhatsApp) e importación Excel
    demo.py       demostración (raíz de composición)
  tests/          pruebas del backend y de la regla de capas
frontend/
  interfaz/       interfaz PySide6/QML (solo usa servicios y dominio)
    puentes/      presentadores en Python: llaman a los servicios y le pasan datos a QML
    qml/          pantallas y componentes QML (solo dibujan)
    recursos/     logo e ícono
  tests/          pruebas de la ventana y del arranque
  main.py         arranque: base, servicios en segundo plano y ventana (raíz de composición)
```

`backend/tests/test_arquitectura.py` revisa las dos carpetas y verifica las dependencias entre
capas: el SQL solo puede estar en `datos/` y la red solo en `adaptadores/`. Para agregar un canal
de notificación basta con escribir su clase (con `enviar(mensaje)`) y llamar a
`notificadores.registrar("nombre", fabrica)`.
