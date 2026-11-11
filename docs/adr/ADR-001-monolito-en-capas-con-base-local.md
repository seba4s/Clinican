# ADR-001 · Monolito de escritorio en capas con base de datos local

**Estado:** Aceptada · 2026-11-11

## Contexto

D1 exige que la agenda funcione sin internet: el local no tiene conexión estable y, si la agenda no abre, no se
atiende. La restricción de operación es un solo computador con Windows 11 y sin presupuesto para un servidor ni
hosting. Lo usa el personal del mostrador, que hace recepción y peluquería con un solo perfil. D2 pide que nunca
se sobrevenda una franja, lo que es más fácil de garantizar con una sola base de datos.

## Decisión

Construiremos una aplicación de escritorio en Python, un solo proceso, con cinco capas: `ui`, `servicios`,
`datos`, `adaptadores` y `dominio`. Los datos viven en SQLite embebido (`%USERPROFILE%\Clinican\clinican.db`).
Las dependencias van en una sola dirección, hacia el dominio, y las verifica `tests/test_arquitectura.py`.

## Alternativas consideradas

- **Aplicación web en la nube.** Sin internet no hay agenda: viola D1 de entrada.
- **Microservicios (agenda, fichas, notificaciones).** Mete la red entre las piezas justo donde D1 pide no
  depender de ella y obliga a coordinar el cupo entre procesos (D2). Con un equipo y un computador se pagan todos
  los costos de operación sin el beneficio, que es desplegar por separado entre equipos.
- **Servidor local con cliente web (Flask en el mismo PC).** Cumple D1, pero agrega un servidor que levantar y
  vigilar sin ganancia hoy, porque nadie más entra a la agenda.

## Consecuencias

- Buena: ningún caso de uso de la agenda cruza la red (lo prueba `tests/test_sin_red.py`).
- Buena: las transacciones ACID locales hacen posible ADR-002 sin coordinación distribuida.
- Buena: un integrante nuevo ubica el código por capa sin explicación.
- Mala: no hay acceso remoto ni uso desde varios computadores. Abrir el mismo archivo SQLite desde dos equipos
  por una carpeta de red puede corromperlo (riesgo R3).
- Mala: el disco del PC es un punto único de falla; dependemos de los respaldos (riesgo R1).
- Mala: todo cambio, aunque sea del canal de recordatorios, se instala como una versión nueva completa.
