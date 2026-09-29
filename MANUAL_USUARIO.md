# CLINICAN — Manual corto de uso

Para abrir el programa, haga doble clic en el icono del perro **CLINICAN** del escritorio.
Elija su nombre, escriba su PIN y pulse **Entrar**. Al terminar el día, pulse **Cerrar sesión**
o cierre la ventana: el programa guarda solo un respaldo al cerrarse.

En la agenda, cada turno tiene un color **y** un texto con su estado:

| Estado | Qué significa |
|---|---|
| PENDIENTE DE ABONO | Agendado, sin abono. Muestra cuántos minutos quedan para pagar; si no paga, el turno se libera solo. |
| CONFIRMADO | Ya pagó el abono. El cupo es suyo. |
| EN PROCESO | La mascota está siendo atendida. |
| LISTA PARA ENTREGAR | Terminó: hay que llamar al dueño. |
| ATENDIDO | Se entregó y se cobró. |

---

## 1. Agendar un turno

1. En el menú, pulse **Nuevo turno**.
2. **Propietario:** escriba la cédula, el nombre, el celular o el nombre de la mascota y pulse **Buscar**. Elija al propietario.
   - Si no existe, regístrelo antes en **Propietarios › + Nuevo propietario** y agréguele sus mascotas.
   - Si el programa dice que faltan los **términos** o la **autorización de datos**, pulse **Registrar consentimientos**, lea el texto al propietario, marque las casillas y pulse **Guardar aceptación**. Sin esto no se puede agendar.
3. **Mascotas y tipo de servicio:** marque la mascota (o varias, si vienen juntas) y elija *corte a máquina*, *corte con tijera* o *baño y deslanado*.
4. **Fecha y hora:** escriba la fecha y pulse **Ver horas disponibles**. Solo aparecen las horas con cupo para esa mascota. Con varias mascotas, pulse **Proponer horario**: el programa las pone seguidas desde las 9:00 (mañana) o las 2:30 (tarde).
5. **¿Quién agenda?:** aparece su nombre; cámbielo si agendó otra persona.
6. **Abono:** si ya pagó, escriba el monto y el medio (Nequi, Bre-B o efectivo). Si no, déjelo vacío: el turno queda pendiente y se libera solo si no paga a tiempo.
7. Pulse **Agendar turno**. El programa muestra los datos de pago (Nequi / Bre-B) para dárselos al cliente. **El comprobante se recibe en el WhatsApp 301 441 7194.**

## 2. Registrar un abono

1. En la **Agenda**, busque el día (con ◀ ▶ o **Hoy**) y toque la tarjeta del turno **PENDIENTE DE ABONO**.
2. Pulse **Registrar abono**, escriba el monto, elija el medio y, si quiere, una nota del comprobante (por ejemplo, el número de la transferencia).
3. Pulse **Guardar abono**. Con el abono mínimo ($20.000 por mascota) el turno pasa a **CONFIRMADO**.
   - Si otro cliente pidió la misma hora, **gana quien paga primero**: el programa avisa a quién hay que llamar para ofrecerle otra hora.
   - Si revisó el pago y quiere confirmar con un monto menor, marque **Verifiqué el pago**.
   - Para varias mascotas del mismo dueño use **Pago único del grupo**.

## 3. Atender una mascota

1. Cuando llegue, toque su turno en la **Agenda** y pulse **Llegó: iniciar atención**.
2. Pulse **Abrir ficha de servicio**: marque el corte, los extras (baño medicado o antipulgas), las condiciones de la mascota y escriba el **precio final**. El programa sugiere el precio mínimo y avisa si el precio es menor. Pulse **Guardar ficha** y luego **← Volver**.
3. Al terminar, pulse **Mascota lista: avisar al dueño**. En pantalla aparecen los celulares del dueño: llame y pulse **Registrar que ya se llamó**.
4. Cuando la recojan, pulse **Entregar y cobrar saldo**. El programa muestra el total, lo abonado y el **saldo a cobrar**.

Otros casos, desde la tarjeta del turno:
- **No asistió:** escriba cuándo avisó el dueño (si avisó). Con aviso de al menos 12 horas, el abono queda a su favor para otro turno; si no, se pierde y deberá abonar de nuevo.
- **No se pudo atender** (agresividad, conducta o enfermedad no informada): elija el motivo y si el abono se devuelve o queda a favor. Llame al dueño para que recoja la mascota.
- **Mover a otra fecha u hora** o **Cancelar turno**, si el cliente lo pide.

## 4. Bloquear un día (solo la administradora)

1. En el menú, pulse **Horarios**.
2. **Un día:** en la pestaña **Franjas de una fecha**, elija la fecha, escriba el motivo (por ejemplo «Festivo») y pulse **Bloquear este día completo**. Ahí mismo puede bloquear una sola hora con **Bloquear franja**.
3. **Varios días seguidos** (vacaciones): en la pestaña **Bloqueos**, escriba **Desde**, **Hasta** y el motivo, y pulse **Bloquear rango**.
4. Si esos días ya tienen turnos, el programa **no bloquea** y muestra la lista: muévalos o cancélelos primero y vuelva a intentarlo.
5. Para deshacerlo, en la pestaña **Bloqueos** pulse **Quitar bloqueo** al lado del día.

El personal puede agregar o quitar **horas extra** libres de una fecha en **Horarios**, pero no bloquear días.

## 5. Respaldar

El programa guarda un **respaldo automático** al cerrarse y una vez al día, en `C:\Clinican\respaldos` (se conservan los últimos 30). Además, **una vez por semana** conviene guardar una copia fuera del computador:

1. Conecte una memoria USB.
2. En el menú, pulse **Respaldo** y luego **Respaldar ahora en USB u otra carpeta**.
3. Elija la memoria USB y acepte. El programa confirma dónde quedó la copia (un archivo `clinican_manual_…db`).

**Restaurar** (solo la administradora, en caso de daño o de cambio de computador): en **Respaldo**, elija una copia de la lista y pulse **Restaurar la copia elegida**, o use **Restaurar desde un archivo (USB)…**. Antes de restaurar, el programa guarda una copia del estado actual por si hay que deshacerlo. Después, todos deben iniciar sesión de nuevo.

---

¿Algo no funciona? Anote lo que pasó y avise a la administradora. Los errores quedan registrados en `C:\Clinican\datos\clinican.log`.
