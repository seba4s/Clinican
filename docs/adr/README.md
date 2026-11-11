# Registros de decisión arquitectónica (ADR)

Cada ADR es corto, fechado e inmutable. Si una decisión cambia, se escribe un ADR nuevo que la reemplaza y el
anterior pasa a **Superada**; no se edita el viejo. Cada uno tiene título, estado con fecha, contexto, decisión,
alternativas consideradas y consecuencias (buenas y malas).

| ADR | Decisión | Driver | Estado |
| --- | --- | --- | --- |
| [ADR-001](ADR-001-monolito-en-capas-con-base-local.md) | Monolito de escritorio en capas con SQLite local | D1, D2 | Aceptada · 2026-11-11 |
| [ADR-002](ADR-002-cupos-protegidos-por-transaccion.md) | Cupos por categoría contados dentro de una transacción con bloqueo | D2 | Aceptada · 2026-11-11 |
| [ADR-003](ADR-003-recordatorios-por-puerto-y-bandeja-de-salida.md) | Recordatorios por un puerto y una bandeja de salida en la base | D3, D1 | Aceptada · 2026-11-11 |

Los drivers (D1 disponibilidad sin conexión, D2 integridad de la agenda, D3 modificabilidad de las
notificaciones) están en el [diseño documentado](../arquitectura/diseno_documentado.html).
