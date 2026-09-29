# CLINICAN — Sistema de la peluquería canina

Programa de escritorio para **CLINICAN, Unidad Médica Veterinaria (servicio de peluquería)**.
Funciona en Windows 11, **sin internet**, con una base de datos local.

La especificación completa está en `ESPECIFICACION_CLINICAN.md`. El manual para el personal está en
`MANUAL_USUARIO.md`.

## Estado del proyecto

| Fase | Contenido | Estado |
|---|---|---|
| 1. Base y seguridad | Base de datos, semillas, tema visual, inicio de sesión con PIN, primer arranque, personal, auditoría | **Terminada** |
| 2. Propietarios, mascotas y legal | Propietarios, mascotas, razas, textos legales con versiones, consentimientos, plantilla de Excel, pantalla de Configuración | **Terminada** |
| 3. Ficha y precios | Ficha de servicio, precios sugeridos, extras de baño, desenredado por sesiones | **Terminada** |
| 4. Turnos | Agenda, franjas, horas extra, bloqueos, cupos, abonos, expiración, quien paga primero, grupos, no asistencia, entrega | **Terminada** |
| 5. Empaquetado y respaldos | `construir.bat`, `.exe`, acceso directo, respaldo automático y manual, restaurar, manual de usuario | **Terminada** (falta la prueba de instalación limpia en el PC de la peluquería) |
| 6. WhatsApp | Solo con autorización | Pendiente |

## Instalar el programa (.exe)

Se necesita Python 3.11 o superior instalado en el PC (python.org, marcando «Add python.exe to PATH»).
Copie la carpeta del proyecto en `C:\Clinican` y haga **doble clic en `construir.bat`**. Este archivo:

1. Crea el entorno `.venv` e instala `requirements.txt` (**solo esta primera vez necesita internet**).
2. Corre las pruebas automáticas y, si pasan, compila `dist\CLINICAN\CLINICAN.exe` con PyInstaller.
3. Crea el acceso directo **CLINICAN** con el icono del perro en el escritorio.

Después, el programa funciona sin internet. Para actualizarlo, se reemplaza el código y se vuelve a
ejecutar `construir.bat`: la base de datos (`datos\`) y los respaldos (`respaldos\`) no se tocan.

## Abrir el programa sin compilar (para desarrollo)

Se necesita Python 3.11 o superior. La primera vez, en una ventana de comandos dentro de `C:\Clinican`:

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

Este paso es el único que necesita internet. Después, para abrir el programa:

```
.venv\Scripts\python main.py
```

La primera vez aparece un asistente para crear la cuenta de la **administradora** (la jefe).
Luego ella agrega al resto del personal desde **Personal**.

## Mascotas y razas

- Cada mascota es **perro o gato**. La raza se elige de la lista (filtrada por especie) o se **escribe a mano**.
- Una raza escrita a mano que no existe se agrega al catálogo al guardar (lo puede hacer todo el personal y
  queda en la auditoría). Se crea **sin tamaño**, así que cada mascota de esa raza lleva su propio tamaño y
  pelaje, como el perro mestizo. La administradora puede completarla en Configuración › Razas.
- «Gato (sin raza definida)» viene en el catálogo y pide elegir tamaño y pelaje.

## Importar mascotas desde Excel

1. En **Propietarios › Importar desde Excel › Guardar plantilla vacía** (o use `plantilla_importacion.xlsx`).
2. Llene una fila por mascota. Si un propietario tiene varias mascotas, repita su cédula: quedan agrupadas.
3. Vuelva a **Importar desde Excel › Elegir archivo lleno**. Primero se muestra una revisión con las
   filas rechazadas y el motivo; nada se guarda hasta confirmar.

Los consentimientos no se importan: cada propietario los acepta antes de su primer turno.
Cuando se consiga un Excel real [A-9], se adapta `clinican/datos/importar_excel.py` (solo la lectura).

## Consentimientos

- Los **términos** y la **autorización de datos** se aceptan **al llegar al servicio**, en la ficha de
  servicio (sección «Términos y condiciones»), y se guardan al pulsar «Guardar ficha». **No se piden al
  agendar.** Sin ellos (versión vigente) no se puede iniciar la atención.
- Se guarda la fecha, la versión, quién lo registró y el texto exacto que se le mostró. También se pueden
  registrar en Propietarios › Consentimientos.
- Si la administradora cambia un texto legal (Configuración › Textos legales), se crea una versión
  nueva y todos deben aceptarla otra vez.
- La declaración de **responsabilidad** se registra por mascota con las condiciones marcadas.

## Ficha de servicio y precios

Se abre desde **Propietarios › Mascotas › + Nueva ficha de servicio** (o con doble clic en el historial).

- El sistema **sugiere** el precio mínimo según el tamaño; con tijera, el mínimo es el mayor entre el del
  tamaño y el total mínimo de tijera (no se suman). Si el precio final es menor, se advierte pero se guarda.
- Extras: baños extra × valor según tamaño, si el baño es medicado o antipulgas. Un mismo baño que es
  medicado y antipulgas se cobra una vez.
- Estilo de la cola de león y forma de la cara solo aparecen en corte bajito (máquina 1 cm o ½ cm) [A-5].
- Accesorios: **corbatín** y **moños en las orejas** (sí / no), cada uno con su color (de la lista o
  escrito a mano). El color solo se guarda si se le pone el accesorio.
- Desenredado: la ficha pasa a «revisión de la estilista» y luego a «sesiones de desenredado». Cada sesión
  cuesta el valor configurado, máximo una por día. Al cerrar, se elige el servicio final (o ninguno, y solo
  se cobran las sesiones).
- Una ficha **realizada** solo permite corregir el precio final y las observaciones.

## Turnos

- **Agenda** (pantalla de inicio): mañana y tarde, cupos libres por categoría en cada franja y tarjetas
  con estado (color **y** texto). Los pendientes muestran la cuenta regresiva. Toque un turno para ver
  sus acciones.
- **Nuevo turno**: propietario → mascotas y tipo de servicio → fecha y hora → ¿quién agenda? → abono.
- **Cliente nuevo**: en Nuevo turno, «+ Cliente nuevo: agendar sin registrarlo» pide solo el **nombre del
  propietario, el celular, el nombre de la mascota, la raza y el tipo de servicio** (el tamaño solo si la raza
  no lo define, por ejemplo una raza escrita a mano o un gato). El cliente queda **sin registrar** (así aparece
  en la agenda y en Propietarios). Cuando llega, el turno muestra **Registrar cliente y términos (ficha)**: en
  la ficha de servicio se completan la cédula y la dirección y se marcan los términos; al guardar la ficha
  queda registrado y ya se puede iniciar la atención. Si la cédula ya existía, el cliente se une a ese
  propietario y sus mascotas, turnos y fichas pasan a él (una mascota con el mismo nombre se toma como la misma).
- Sin abono, el turno queda **pendiente** 30 minutos (configurable) y luego se libera solo. Los
  pendientes no apartan cupo: **gana quien paga primero**, y el sistema avisa a quién llamar.
- **Varias mascotas**: una franja por mascota, seguidas, desde las 09:00 o las 14:30; si no alcanzan,
  se ofrece seguir en la otra jornada u otro día. Se puede hacer un pago único que se reparte.
- **No asistió**: con aviso de al menos 12 horas (configurable) el abono queda **a favor** para
  reprogramar; sin aviso se pierde y el propietario debe abonar de nuevo.
- **Entregar y cobrar**: muestra el saldo (total − abonos), aplica los abonos, marca la ficha como
  realizada y actualiza la última visita.
- **Horarios**: todos pueden agregar o quitar **horas extra** libres de una fecha. Solo la
  administradora bloquea días, rangos o franjas (solo si no tienen turnos activos; si los hay, se
  listan para moverlos o cancelarlos) y edita la plantilla semanal.

## Dónde quedan los datos

| Qué | Dónde |
|---|---|
| Base de datos | `C:\Clinican\datos\clinican.db` |
| Registro de errores | `C:\Clinican\datos\clinican.log` |
| Respaldos automáticos | `C:\Clinican\respaldos\` |

La carpeta `datos` está fuera de la carpeta de compilación, así que no se pierde al recompilar.
Para usar otra carpeta, defina la variable de entorno `CLINICAN_HOME`.

## Roles

- **Administradora** (solo una activa a la vez): todo, incluido personal, configuración y auditoría.
- **Personal**: agenda, abonos, propietarios, mascotas y fichas; puede cambiar su propio PIN.

Los permisos se validan en la capa de servicios, no solo ocultando botones. Para que la jefe deje
de ser administradora, primero debe **entregar la administración** a otra persona desde **Personal**.

## Supuestos configurables (sección 13)

Todos se cambian desde Configuración (solo la administradora), sin tocar el código.

| Id | Supuesto | Clave en `config` | Valor inicial |
|---|---|---|---|
| A-1 | Las pequeñas usan el cupo MÁQUINA | `pequenas_en_cupo_maquina` | 1 (sí) |
| A-2 | Cupos independientes entre categorías | `cupos_independientes` | 1 (sí) |
| A-3 | Grupos: una franja por mascota, desde 09:00 / 14:30; 08:30 solo individual | `politica_grupo`, `inicio_grupo_manana`, `inicio_grupo_tarde`, `franjas_solo_individuales` | CONSECUTIVAS, 09:00, 14:30, 08:30 |
| A-4 | Horas mínimas para avisar la inasistencia | `horas_minimas_aviso` | 12 |
| A-5 | Estilo de cola de león y forma de cara solo en corte bajito | (regla de la ficha, Fase 3) | — |
| A-6 | Saldo = total − abonos | (regla de cobro, Fase 4) | — |
| A-7 | Un solo PC con varios usuarios | (arquitectura) | — |
| A-8 | Con aviso a tiempo, el abono se conserva para reprogramar | `abono_se_conserva_con_aviso` | 1 (sí) |
| A-9 | Importación de Excel se adapta cuando exista un archivo real | (Fase 2) | — |
| A-10 | Al cancelar, el abono solo se devuelve con esta anticipación; si no, queda a favor o se mueve con el turno | `horas_minimas_devolucion` | 12 |

## Respaldos

- **Automático:** al cerrar el programa y una vez al día (al abrirlo, o cada hora si queda abierto), con la
  API `sqlite3.Connection.backup`, en `C:\Clinican\respaldos\`. Se conservan los últimos 30
  (Configuración › Otros › `respaldos_conservar`). Cada copia es un archivo `clinican_auto_AAAA-MM-DD_HHMMSS.db`
  que se puede abrir solo.
- **Respaldar ahora** (menú **Respaldo**, todo el personal): copia a una memoria USB u otra carpeta
  (`clinican_manual_….db`). Recomendado una vez por semana, fuera del computador.
- **Restaurar** (solo la administradora): se elige una copia de la lista o un archivo de la USB. El programa
  revisa que sea un respaldo sano de CLINICAN, guarda antes una copia del estado actual
  (`clinican_antes-de-restaurar_….db`) y, al terminar, pide iniciar sesión de nuevo. Un respaldo de una
  versión anterior del programa se actualiza solo.

## Estructura del código

```
clinican\
  dominio\    reglas de negocio puras (permisos, PIN, validación de configuración)
  datos\      SQLite: esquema, migraciones (PRAGMA user_version), semillas y repositorios
  servicios\  casos de uso con validación de permisos y auditoría
  ui\         pantallas CustomTkinter
tests\        pruebas automáticas (pytest)
```

## Pruebas

```
.venv\Scripts\python -m pytest
```

275 pruebas. Las de rutas `C:\...` solo corren en Windows, y la prueba de humo de la interfaz se omite si
el equipo no tiene pantalla.

## Notas

- El logo `assets\logo_perro.png` se sacó del icono `clinican.ico` (256×256) porque no se tenía el PNG
  original. Si se consigue el archivo original, basta con reemplazarlo con el mismo nombre.
- Los textos legales son un borrador y **no son asesoría jurídica**; deben revisarlos un abogado.
