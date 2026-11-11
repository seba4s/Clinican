# Diseño de la interfaz de escritorio

Diseño aprobado e implementado en `backend/clinican/ui/`. Maquetas:
https://claude.ai/artifact/HtdrHdoHjrouHad9Aeu3fp

Plataforma: Windows 11, sin internet, CustomTkinter. El código de la interfaz va
en `backend/clinican/ui/` y solo puede usar `servicios` y `dominio`.

## Idea central

La agenda se lee como el salón: cada media hora es una fila y cada cupo es un
puesto que se ve libre u ocupado (máquina 2, grande 1, tijera 1, complicado 1).
Un puesto libre se puede tocar para agendar ahí mismo.

## Navegación

Barra lateral con cuatro secciones; la aplicación abre en Agenda.

| Sección | Contenido |
|---|---|
| Agenda | Tablero de cupos del día, panel del turno seleccionado, pendientes de abono, nuevo turno, bloquear horas |
| Clientes | Lista con búsqueda, ficha del propietario (saldo a favor, mascotas, historial, inasistencias), unir duplicados, importar Excel |
| Recordatorios | Bandeja: por enviar, enviados, fallidos (reintentar, corregir celular), descartados |
| Ajustes | Horario y bloqueos, cupos y abono, precios, razas, recordatorios y WhatsApp, respaldos, registro de cambios |

Diálogos (uno a la vez, Esc cierra): Nuevo turno, Ficha de servicio,
confirmaciones de lo que no se deshace (cancelar, inasistencia, liberar,
restaurar respaldo).

## Acciones del panel según el estado

| Estado | Principal | Otras |
|---|---|---|
| Falta abono | Registrar abono | Mover, Liberar cupo…, Cancelar… |
| Confirmado | Iniciar atención | Mover, Marcar inasistencia…, Cancelar… |
| En atención | Marcar atendido y llenar ficha | |
| Listo para entregar (atendido) | Entregar | Ver ficha |
| Entregado | Ver ficha | |

## Color

| Rol | Valor | Contraste |
|---|---|---|
| Fondo de ventana | `#F5F6F2` | |
| Superficie (tarjetas) | `#FFFFFF` | |
| Tinta (texto, foco, sección activa) | `#14121D` | 18,5:1 sobre blanco |
| Tinta suave (texto secundario) | `#5B5966` | 6,9:1 sobre blanco |
| Borde de campo y puesto libre | `#7A7D72` | 4,2:1 sobre blanco |
| Borde decorativo | `#DEDFD8` | solo decoración |
| Fucsia acción (botón principal, uno por pantalla) | `#C4006C` | blanco 5,9:1 |
| Peligro (texto de acciones destructivas) | `#B00020` | 7,3:1 sobre blanco |
| Enlace | `#087F97` | 4,7:1 sobre blanco |

El fucsia de la marca `#FE028D` da 3,75:1 con texto blanco, por eso los botones
usan `#C4006C`.

Estados del turno (siempre con texto e ícono, no solo color):

| Estado | Fondo | Texto | Contraste |
|---|---|---|---|
| Falta abono | `#FFF0D9` | `#8A4600` | 6,3:1 |
| Confirmado | `#EEF4D6` | `#4D5E12` | 6,3:1 |
| En atención | `#DDF4FA` | `#06657A` | 5,8:1 |
| Listo para entregar | `#B7CF53` (lima) | `#14121D` | 10,6:1 |
| Entregado | `#EFEFEC` | `#5B5966` | 6,0:1 |

Liberado, cancelado e inasistencia no ocupan cupo y se listan en "Fuera de
agenda" al pie del día.

## Tipografía

Segoe UI Variable (la del sistema), una sola familia, cifras tabulares en horas y
dinero.

| Estilo | Tamaño | Peso |
|---|---|---|
| Título | 28 | 600 |
| Subtítulo | 20 | 600 |
| Cuerpo | 15 | 400 |
| Etiqueta | 13 | 600 |

## Controles y teclado

- Botones y campos de 40 px de alto, 12 px entre botones.
- Foco de teclado visible: contorno de 2 px en tinta.
- Errores junto al campo, en el momento (por ejemplo, celular de 10 dígitos).
- Atajos: Ctrl+N nuevo turno, Ctrl+F buscar cliente, ← → cambiar de día,
  Inicio volver a hoy, Esc cerrar diálogo.

## Decisiones

- La aplicación sigue el modo claro u oscuro de Windows. Los colores del modo
  oscuro están en `backend/clinican/ui/tema.py`, con su contraste.
- Al entregar se cobra el precio final menos lo abonado (abono pagado más saldo
  aplicado).
