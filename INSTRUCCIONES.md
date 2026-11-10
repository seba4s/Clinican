# CLINICAN — Cómo levantar el esqueleto funcional

Proyecto integrador de Arquitectura de Software (momento evaluativo 3). El diseño está en
[`docs/arquitectura/diseno_documentado.pdf`](docs/arquitectura/diseno_documentado.pdf).

## Requisitos

- Python 3.11 o superior, con Tkinter. En Windows viene incluido; en Ubuntu: `sudo apt install python3-tk`.
- No necesita internet para funcionar. Solo lo usa la instalación de dependencias y, si se activa,
  el canal de WhatsApp.

## Instalar (una vez)

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate      Linux/macOS:  source .venv/bin/activate
pip install -r requirements.txt
```

## 1. La demostración de la arquitectura (un comando)

```bash
python -m clinican.demo
```

Corre en consola, sin ventanas, con una base de datos temporal que se borra al terminar. Muestra:

| Parte | Qué demuestra | Driver y decisión |
|---|---|---|
| 1 · Estructura | Lee el código y lista de qué capa depende cada una. Debe decir «Atajos prohibidos encontrados: ninguno». | ADR-001 |
| 2 · Integridad | Dos labradores piden el último cupo GRANDE: gana quien paga primero y el otro se libera. | D2 · ADR-002 |
| 3 · Sin conexión | El canal falla; el recordatorio queda pendiente con su error y la recepción sigue agendando. | D1 · ADR-003 |
| 4 · Otro canal | El mismo recordatorio sale por archivo, por un canal SMS escrito en la demo y por consola, sin tocar la agenda. Un dueño sin autorización de datos no recibe nada. | D3 · ADR-003 · Ley 1581 |

## 2. Verificar que las capas no tienen atajos

```bash
python -m pytest tests/test_arquitectura.py -v
```

Falla si, por ejemplo, la interfaz (`ui`) importa la capa de datos, si el dominio importa otra capa,
o si la capa de servicios ejecuta SQL por su cuenta. Incluye pruebas que plantan un atajo a propósito
para comprobar que se detecta.

## 3. Todas las pruebas

```bash
python -m pytest
```

En Linux sin pantalla, las pruebas de la interfaz necesitan `xvfb-run -a python -m pytest`; si no hay
pantalla, se omiten solas.

## 4. El programa completo (con ventanas)

```bash
python main.py
```

La primera vez pide crear la cuenta de la administradora. Los datos quedan en `datos/clinican.db` y los
respaldos en `respaldos/`. Los recordatorios salen por el canal de **Configuración › Recordatorios**:

- `ARCHIVO` (por defecto): se escriben en `datos/recordatorios.txt`. No necesita internet.
- `WHATSAPP`: API oficial de Meta. Necesita una cuenta de WhatsApp Business verificada, la plantilla
  `recordatorio_turno` aprobada y estas variables de entorno (nunca en el código):
  `CLINICAN_WHATSAPP_TOKEN` y `CLINICAN_WHATSAPP_NUMERO_ID`. Sin ellas, los mensajes quedan pendientes
  con el error «La cuenta de WhatsApp no está configurada» y la agenda sigue funcionando.

## Dónde está cada capa

```
main.py                  raíz de composición: elige el adaptador y arranca el despachador
clinican/ui/             presentación (CustomTkinter)            → servicios, dominio
clinican/servicios/      casos de uso, permisos, transacciones,  → datos, dominio
                         puerto Notificador
clinican/adaptadores/    WhatsApp (Meta), archivo, consola,       → servicios, dominio
                         despachador en hilo aparte
clinican/datos/          SQLite: repositorios, migraciones,       → dominio
                         bandeja de salida
clinican/dominio/        reglas puras (cupos, precios, estados,   → nada
                         recordatorios, legal)
clinican/demo.py         la demostración de este documento
tests/                   pruebas automáticas (pytest)
```
