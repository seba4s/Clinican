# CLINICAN — Resumen de avance

_Fecha: 29 de septiembre de 2026_

Programa de escritorio (Python + CustomTkinter + SQLite, 100 % sin internet) para la peluquería canina de
CLINICAN. Se construye por fases según `ESPECIFICACION_CLINICAN.md` (sección 12).

**Estado general:** fases 1 a 4 terminadas. Faltan la 5 (empaquetado y respaldos) y la 6 (WhatsApp, que necesita
autorización). Las **242 pruebas automáticas pasan** (`.venv\Scripts\python -m pytest`).

| Fase | Contenido | Estado |
|---|---|---|
| 1. Base y seguridad | Base de datos, semillas, tema, login con PIN, primer arranque, personal, auditoría | ✅ Terminada |
| 2. Propietarios, mascotas y legal | CRUD, razas, textos legales con versiones, consentimientos, plantilla Excel, Configuración | ✅ Terminada |
| 3. Ficha y precios | Ficha de servicio, precios sugeridos, extras de baño, desenredado por sesiones | ✅ Terminada |
| 4. Turnos | Agenda, franjas, cupos, abonos, expiración, quien paga primero, grupos, no asistencia, entrega | ✅ Terminada |
| 5. Empaquetado y respaldos | `construir.bat`, `.exe`, acceso directo, respaldos, manual | ⏳ Pendiente |
| 6. WhatsApp | API oficial de Meta (sección 14) | ⏳ Pendiente, **necesita autorización** |

---

## Lo que ya está hecho

### Fase 1 — Base y seguridad
- Esquema SQLite con migraciones (`PRAGMA user_version`) y semillas con todos los valores configurables.
- Rutas que funcionan con Python o empaquetado (`sys.frozen`). Los datos van en `C:\Clinican\datos\` y se puede cambiar con `CLINICAN_HOME`.
- Tema visual con la marca CLINICAN y librería de componentes (`ui/tema.py`).
- Inicio de sesión con usuario y PIN, y asistente del primer arranque para crear a la administradora.
- Gestión de personal: alta, edición, desactivación, cambio de PIN y **entrega de la administración** (solo una ADMIN activa).
- Matriz de permisos por rol (RN-01) validada en la capa de servicios, no solo ocultando botones.
- Auditoría de acciones sensibles, con búsqueda y filtros.
- Pantalla «Mi PIN» para el personal.

### Fase 2 — Propietarios, mascotas y legal
- Propietarios y mascotas: búsqueda, alta, edición, historial, última visita editable y marca «requiere nuevo abono».
- Razas con tamaño y categoría. Las mestizas exigen elegir tamaño.
- Textos legales con versiones: términos, autorización de datos (Ley 1581) y responsabilidad por mascota.
- Consentimientos guardados con fecha, versión, quién los registró y el texto exacto mostrado.
- Plantilla `plantilla_importacion.xlsx` e importador con revisión previa y reporte de filas rechazadas.
- Pantalla de Configuración (solo ADMIN): precios, cupos, abono, datos de pago, horas de aviso, razas y textos legales.

### Fase 3 — Ficha y precios
- Ficha de servicio completa. Cola de león y forma de la cara solo aparecen en corte bajito [A-5].
- Precio mínimo sugerido por tamaño y por tijera (se toma el mayor, no se suman). Si el precio final es menor, se advierte.
- Extras de baño por tamaño; un baño medicado y antipulgas se cobra una sola vez.
- Desenredado: revisión de la estilista, sesiones (máximo una por día) y cierre con el servicio final.
- Una ficha realizada solo permite corregir el precio final y las observaciones.

### Fase 4 — Turnos
- Agenda del día (pantalla de inicio): mañana y tarde, cupos libres por categoría, tarjetas con color y texto según el estado, y cuenta regresiva en los pendientes.
- Nuevo turno en pasos: propietario → mascotas y servicio → fecha y hora → ¿quién agenda? → abono.
- Sin consentimientos no se puede agendar (RN-15).
- Expiración automática de los pendientes a los 30 min (RN-07) y regla de «gana quien paga primero» (RN-08).
- Varias mascotas: franjas consecutivas desde 09:00 o 14:30, con desborde a la otra jornada u otro día, y pago único repartido (RN-09).
- No asistencia con o sin aviso de 12 h (RN-10). Servicio imposible (RN-16), mascota lista (RN-17), entrega y cobro con el saldo.
- Horarios: todos pueden agregar o quitar horas extra; solo la ADMIN bloquea (si no hay turnos activos) y edita la plantilla semanal (RN-11).

### Documentación y pruebas
- `README.md` con el estado, la instalación para desarrollo, los flujos principales y los supuestos A-1 a A-9.
- 242 pruebas `pytest`: base de datos, seguridad, permisos, personal, configuración, propietarios, legal, importación, fichas, turnos, rutas y una prueba de humo de la interfaz.

---

## Lo que falta

### Fase 5 — Empaquetado y respaldos (siguiente paso)
- [ ] **`construir.bat`**: crear `.venv`, instalar `requirements.txt` y ejecutar PyInstaller en modo carpeta con el icono y `assets`.
- [ ] Compilar `dist\CLINICAN\CLINICAN.exe` y comprobar que abre y usa `C:\Clinican\datos\clinican.db`.
- [ ] **Acceso directo en el escritorio** con el icono del perro.
- [ ] **Respaldo automático** con `sqlite3.Connection.backup` al cerrar la app y una vez al día, en `C:\Clinican\respaldos\`, conservando las últimas 30.
- [ ] Pantalla **Respaldo** (pantalla 11 de la especificación): botón «Respaldar ahora» hacia otra carpeta o una USB y lista de copias.
- [ ] **Restaurar** (solo ADMIN), que primero haga una copia del estado actual.
- [ ] Pruebas de respaldo y restauración (exigidas en la sección 12).
- [ ] **`MANUAL_USUARIO.md`** (una o dos páginas): agendar un turno, registrar un abono, atender una mascota, bloquear un día y respaldar.
- [ ] Criterio de aceptación: instalación limpia en Windows 11 sin internet, con el respaldo y la restauración probados.
- [ ] Actualizar la tabla de estado del `README.md`.

### Fase 6 — WhatsApp (solo con autorización explícita)
- [ ] Decidir con la usuaria la arquitectura del webhook: un túnel seguro hacia el PC o un servicio pequeño en la nube que se sincronice.
- [ ] Cuenta de Meta Business verificada, número, plantillas aprobadas y revisión de las tarifas vigentes en Colombia.
- [ ] Revisar qué pasa con el uso normal del número 301 441 7194 si pasa a la API.
- [ ] Bot: datos del propietario y la mascota, aceptación de términos (`origen = WHATSAPP`), oferta de franjas, turno `PENDIENTE_ABONO`, datos de pago, comprobante revisado por el personal y aviso cuando se libere.
- [ ] Guardar el token fuera del código.

### Pendientes externos (no dependen del código)
- [ ] Conseguir un **Excel real** de mascotas para adaptar `clinican/datos/importar_excel.py` [A-9].
- [ ] Que la usuaria **confirme los supuestos A-1 a A-9** (sección 13). Ya son configurables, así que cambiarlos no requiere tocar el código.
- [ ] Que un **abogado revise los textos legales**: son un borrador y no son asesoría jurídica.
- [ ] Si aparece el **PNG original del logo**, reemplazar `assets\logo_perro.png`, que hoy se sacó del `.ico`.
- [ ] Opcional: iniciar un repositorio **git** para el proyecto (hoy no hay control de versiones).
