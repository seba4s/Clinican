# CLINICAN — Sistema de la peluquería canina

Programa para **CLINICAN, Unidad Médica Veterinaria (servicio de peluquería)**.
Funciona en Windows 11, sin internet, con una base de datos local.

## Estructura

| Carpeta | Contenido |
|---|---|
| `backend/` | El programa: agenda por franjas con cupos, abonos, saldo a favor, fichas, precios, recordatorios, respaldos e importación desde Excel, con su interfaz de escritorio en CustomTkinter (`backend/clinican/ui`). Incluye sus pruebas y la plantilla `plantilla_importacion.xlsx`. |
| `docs/arquitectura/` | Diseño documentado del proyecto integrador (drivers, escenarios, estilo, C4, tácticas, riesgos), en HTML y PDF. |
| `docs/adr/` | Registros de decisión arquitectónica (ADR-001 a 003). |
| `docs/diseno-interfaz.md` | Diseño acordado de la interfaz. |
| `assets/` | Logo (`logo_perro.png`) e icono del ejecutable (`clinican.ico`) para la interfaz. |
| `.claude/skills/` | Skill `apple-design` para revisar el diseño de la interfaz. |
| `.github/workflows/` | GitHub Actions: corre las pruebas y la demostración en Windows y Ubuntu en cada cambio. |

Cómo levantarlo para la sustentación (demostración, pruebas y programa completo) está en
[`INSTRUCCIONES.md`](INSTRUCCIONES.md). El detalle de reglas de negocio y configuración está en
[`backend/README.md`](backend/README.md).

## App anterior

La primera versión del programa (con su interfaz en CustomTkinter, el módulo legal y `construir.bat`) se
retiró del repositorio. Sigue disponible en la etiqueta git `app-anterior`:

```bash
git checkout app-anterior
```
