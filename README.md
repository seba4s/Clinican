# CLINICAN — Sistema de la peluquería canina

Programa para **CLINICAN, Unidad Médica Veterinaria (servicio de peluquería)**.
Funciona en Windows 11, sin internet, con una base de datos local.

## Estructura

| Carpeta | Contenido |
|---|---|
| `backend/` | Backend de la agenda: turnos por franjas con cupos, abonos, saldo a favor, fichas, precios, recordatorios, respaldos e importación desde Excel. Incluye sus pruebas y la plantilla `plantilla_importacion.xlsx`. |
| `assets/` | Logo (`logo_perro.png`) e icono del ejecutable (`clinican.ico`) para la interfaz. |
| `.claude/skills/` | Skill `apple-design` para revisar el diseño de la interfaz. |

La interfaz de escritorio nueva todavía no existe: `backend/clinican/ui` es el lugar reservado para ella.

Cómo instalar, correr las pruebas y usar el backend está en [`backend/README.md`](backend/README.md).

## App anterior

La primera versión del programa (con su interfaz en CustomTkinter, el módulo legal y `construir.bat`) se
retiró del repositorio. Sigue disponible en la etiqueta git `app-anterior`:

```bash
git checkout app-anterior
```
