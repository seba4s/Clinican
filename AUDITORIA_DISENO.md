# CLINICAN — Auditoría de diseño de la interfaz

Hecha con la skill `apple-design` (principios de las Human Interface Guidelines de Apple, traducidos a una
aplicación de escritorio en Windows con CustomTkinter). Apple habla de macOS e iOS; aquí se aplicó **el principio**,
no la apariencia de Apple: la identidad de CLINICAN (verde lima, fucsia, perro) se conserva.

**Valoración:** Buena. Sin fallos críticos de accesibilidad. Antes de los cambios había 3 hallazgos altos y varios
medios; todos los que aplican a este proyecto quedaron resueltos.

**Lo que define el diseño:** letra grande, botones de 48 px y la marca lima/fucsia con estados siempre escritos
(no solo de color). Es una herramienta de trabajo, y el diseño ya la trata como tal.

## Hallazgos y qué se cambió

| # | Gravedad | Hallazgo (con números) | Principio | Cambio hecho |
|---|---|---|---|---|
| 1 | Alta | Bordes de los campos `#CFD2C8` sobre blanco: **1,5 : 1** (mínimo 3 : 1). Los campos casi no se veían. | `accessibility.md`, `color.md` (contraste) | Borde de campos `#7A7D72`: **4,2 : 1**. Los bordes de tarjetas, que son solo decoración, quedan como estaban. |
| 2 | Alta | Los botones **no se alcanzaban con Tab** ni mostraban foco; Enter y Espacio no los activaban. | `keyboards.md` (acceso completo con teclado), `focus-and-selection.md` | Todos los botones entran en el orden de Tab, muestran un borde oscuro de 3 px con el foco y responden a Enter y Espacio. |
| 3 | Alta | 20 avisos de «guardado» eran **ventanas que interrumpen** (había que pulsar «Entendido» en cada guardado). | `alerts.md` («Avoid using an alert merely to provide information»), `feedback.md` | Nuevo aviso breve ✔ sobre la barra inferior, que se quita solo a los 5 s o al hacer clic. Las ventanas quedan para lo que hay que leer o copiar (rutas, datos para el cliente, advertencias). |
| 4 | Media | Texto de elementos inactivos `#8A8894`: **3,4 : 1** (mínimo 4,5 : 1). | `accessibility.md` | `#6B6975`: **5,4 : 1**. |
| 5 | Media | Los botones de confirmación decían «Sí, continuar / No, volver». | `alerts.md` (verbos específicos, «Cancel») | «Continuar / Cancelar» por defecto y verbos concretos: «Bloquear», «Restaurar», «Dar de baja», «Importar»… Cancelar un turno o una ficha ofrece «Conservar turno / Conservar ficha» para no confundir «Cancelar» con «Cancelar turno». |
| 6 | Media | Enter no hacía nada en los avisos; en las confirmaciones el foco no se veía. | `alerts.md`, `keyboards.md` | Enter cierra los avisos informativos. En las confirmaciones **no** decide por la persona: el foco visible queda en la primera opción y se elige con Tab/Espacio o con el ratón. |
| 7 | Media | Sin atajos de teclado para moverse entre secciones. | `keyboards.md`, `designing-for-macos.md` | **Ctrl + 1…9** abre cada sección del menú; **Ctrl + Q** cierra la sesión. Hay una nota al pie del menú. |
| 8 | Media | La barra de título siempre decía lo mismo: no se sabía en qué sección se estaba. | `windows.md` (la ubicación siempre visible) | «Agenda — CLINICAN», «Propietarios — CLINICAN»… |
| 9 | Media | Tamaño de letra fijo: no se adapta a personas con baja visión ni a pantallas grandes. | `accessibility.md` (Dynamic Type), flexibilidad | Configuración › Pantalla › **Tamaño de letra y botones**: Normal, Grande (115 %), Muy grande (130 %). Se aplica al guardar, sin reiniciar. Incluye tablas y el tamaño mínimo de la ventana. |
| 10 | Media | Con letra grande el menú lateral cortaba las últimas opciones. | `layout.md` (el contenido no se corta) | El menú ahora se desplaza si no cabe. |
| 11 | Baja | Los controles no daban señal de «se puede pulsar» con el puntero. | `pointing-devices.md` | Cursor de mano en botones, casillas e interruptores. |
| 12 | Baja | Acciones largas (importar, restaurar) no mostraban que el programa trabajaba. | `loading.md`, `feedback.md` | Cursor de espera mientras se ejecuta una acción del negocio. |

## Lo que ya funcionaba (se conservó)

- Estados del turno con **color y texto**, nunca solo color.
- Letra de 19 px, botones de 48 px y campos de 44 px (mínimo de escritorio: 28 px).
- Contraste de la paleta: negro sobre lima **10,6 : 1**, gris de apoyo **8,2 : 1**, rojo de error **7,3 : 1**,
  enlaces azul oscuro **4,7 : 1**, blanco sobre fucsia en negrita **3,75 : 1** (pasa para texto en negrita grande).
  Una prueba automática (`test_contraste_de_la_paleta`) impide que una futura edición baje de esos mínimos.
- Mensajes de error que dicen qué pasó y qué hacer; PIN siempre oculto y nunca prellenado.
- Confirmación antes de acciones destructivas o difíciles de deshacer; Esc cierra cualquier ventana.

## Lo que no se aplicó, y por qué

| Principio | Motivo |
|---|---|
| Modo oscuro y colores del sistema (`dark-mode.md`) | La especificación de CLINICAN fija la marca clara (lima y fucsia). Es una decisión de la marca, no un descuido. Se puede abrir como mejora aparte. |
| Barra de menús nativa, ventanas múltiples, menús contextuales | Convención de macOS. En Windows 11 con CustomTkinter se imitaría con piezas no nativas; el menú lateral ya cubre todas las secciones y ahora tiene atajos. |
| Liquid Glass, materiales translúcidas | No aplica: no hay capas flotantes sobre contenido y el cristal haría peor el contraste. |
| Pestañas inferiores, hojas (sheets), gestos | Son de móvil; la aplicación es de escritorio con ratón y teclado. |
| Lector de pantalla | CustomTkinter dibuja en un lienzo y no expone etiquetas de accesibilidad; no se puede resolver sin cambiar de tecnología. Se deja anotado como límite. |
| Movimiento y animaciones | La aplicación casi no tiene animaciones; solo el aviso ✔, que aparece y se quita sin movimiento. |

## Pendiente de revisar en el PC real

- Probar el tamaño «Grande» y «Muy grande» en la pantalla de la peluquería (con 1920×1080 caben bien; con
  pantallas pequeñas el tamaño mínimo de la ventana crece y puede requerir «Normal»).
- Confirmar con la administradora si prefiere que «Cobré el saldo y entregué» se llame «Cobrar y entregar».
