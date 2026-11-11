# ADR-003 · Recordatorios por un puerto y una bandeja de salida en la base local

**Estado:** Aceptada · 2026-11-11

## Contexto

D3 exige cambiar el canal de recordatorios (hoy WhatsApp, mañana SMS o correo) sin tocar la agenda. D1 exige que
la agenda no espere a la red. La API de WhatsApp de Meta pide plantillas aprobadas, conexión y un token que no
puede ir en el código. El recordatorio sale 24 horas antes del turno.

## Decisión

- Al confirmar o mover un turno, `servicios/agenda.py` guarda el recordatorio en la tabla
  `notificaciones_salida`, dentro de la misma transacción.
- Un despachador (`servicios/despachador.py`), en un hilo con su propia conexión, revisa la bandeja cada 60
  segundos. Justo antes de enviar verifica que el turno siga confirmado y no haya empezado; si no, lo descarta con
  motivo. Si el envío falla, reintenta a los 1, 5 y 15 minutos y luego lo deja FALLIDO. Purga lo cerrado de más
  de 90 días.
- El despachador solo conoce el puerto `Notificador` (`servicios/notificaciones.py`). Los canales viven en
  `adaptadores/` (WhatsApp, archivo y consola) y se registran por nombre en `adaptadores/notificadores.py`.
  `main.py` elige el canal según la configuración.

## Alternativas consideradas

- **Llamar a la API de WhatsApp desde el servicio de turnos.** Es lo más rápido de escribir, pero acopla la
  agenda al canal (viola D3) y la bloquea sin red (viola D1).
- **Un microservicio de notificaciones en la nube.** Aísla bien el canal, pero exige sincronizar la agenda hacia
  la nube y pagar un servidor.
- **Un broker de mensajes (RabbitMQ o similar).** Da el mismo desacople que la bandeja, con una pieza más que
  instalar y mantener en el PC de recepción.

## Consecuencias

- Buena: un canal nuevo es una clase con `enviar(mensaje)` y una línea `registrar("nombre", fabrica)`; la agenda
  no cambia (parte 4 de `python -m clinican.demo`).
- Buena: sin red, los recordatorios esperan y salen cuando vuelve la conexión; viven en la misma base y en los
  mismos respaldos.
- Mala: el recordatorio puede llegar tarde si la red falta mucho; tras tres reintentos queda FALLIDO y hay que
  reintentarlo a mano desde la pantalla Recordatorios.
- Mala: entrega «al menos una vez»: si el programa se cae justo después de enviar y antes de marcar, el dueño
  puede recibir el mensaje dos veces.
- Mala: el envío real depende de una cuenta de Meta verificada y de una plantilla aprobada que no controlamos (R2).
