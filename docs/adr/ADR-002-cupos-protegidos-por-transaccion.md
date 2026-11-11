# ADR-002 · Cupos por categoría contados dentro de una transacción con bloqueo

**Estado:** Aceptada · 2026-11-11

## Contexto

D2: nunca sobrevender una franja. El negocio no asigna peluquera al agendar; trabaja con franjas fijas de 30
minutos (lunes a sábado, 9:00 a 16:30) y lo que varía es cuántas mascotas caben por categoría: MÁQUINA 2,
GRANDE 1, TIJERA 1 y COMPLICADO 1. La categoría sale de la mascota con la prioridad COMPLICADO > GRANDE >
TIJERA > MÁQUINA. Los pendientes de abono que no han vencido ocupan cupo igual que los confirmados. Hay carreras
reales: dos personas pueden pedir el último cupo a la vez, y un pendiente puede vencer justo cuando se registra
su abono.

## Decisión

- La categoría, los cupos libres y las transiciones de estado son funciones puras de `dominio/`
  (`cupos.py`, `estados.py`).
- Cada caso de uso que ocupa un cupo (crear, mover) abre `BEGIN IMMEDIATE`, vuelve a contar la ocupación de la
  franja dentro de esa transacción y escribe solo si cabe (`servicios/agenda.py`).
- Registrar un abono revisa el vencimiento dentro de la misma transacción: si ya venció, libera el turno y
  devuelve lo pagado como saldo a favor.

## Alternativas consideradas

- **Agenda por peluquera con duración variable** (la propuesta inicial). No refleja cómo trabaja el negocio y
  obliga a estimar duraciones que dependen de nudos y conducta. Se descartó tras hablar con la administradora.
- **Validar el cupo solo en la pantalla.** Entre ver el cupo libre y guardar puede llegar otra persona o vencer un
  pendiente; la validación tiene que estar donde se escribe.
- **Restricción o trigger en SQL.** Una restricción no expresa «como máximo N por categoría según la
  configuración», y un trigger escondería la regla en la base, lejos de las pruebas del dominio.
- **Bloqueo optimista con número de versión.** Sirve con muchos escritores; aquí hay uno y obligaría a reintentar
  desde la interfaz sin ganancia.

## Consecuencias

- Buena: la regla vive en un solo lugar del dominio, y `tests/test_carreras.py` reproduce la carrera con varios
  hilos y conexiones sobre el mismo archivo.
- Buena: los cupos, el abono y el horario se cambian en Ajustes, sin programar.
- Mala: un solo escritor a la vez. Con un PC no se nota; con varios equipos sería el primer cuello de botella.
- Mala: no se sabe qué peluquera atiende cada turno. Si el negocio lo pide, hay que extender el modelo.
- Mala: un pendiente que nunca paga bloquea el cupo hasta 30 minutos.
