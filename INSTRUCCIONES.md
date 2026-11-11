# Cómo levantar CLINICAN

Instrucciones del esqueleto funcional para la sustentación. Requiere Windows 11 (o Linux) con Python 3.11 o más
reciente. Todo se corre desde la carpeta `backend/`.

## 1. Instalar (una sola vez)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

En Linux o macOS, el intérprete queda en `.venv/bin/python`.

## 2. Demostración de punta a punta (sin ventanas)

```powershell
.\.venv\Scripts\python.exe -m clinican.demo
```

Usa una base temporal y muestra, en orden:

1. las capas y sus dependencias reales, sin atajos (ADR-001);
2. dos hilos pidiendo a la vez el último cupo de máquina: solo uno lo obtiene (D2, ADR-002);
3. un turno agendado sin red mientras WhatsApp falla; el recordatorio queda con reintento (D1, ADR-003);
4. el cambio de canal de archivo a consola sin tocar la agenda (D3, ADR-003).

## 3. Pruebas y funciones de aptitud

```powershell
.\.venv\Scripts\python.exe -m pytest
```

- Solo la regla de capas: `.\.venv\Scripts\python.exe -m pytest tests/test_arquitectura.py`
- Sin las pruebas de rendimiento (más rápido): `.\.venv\Scripts\python.exe -m pytest -m "not lento"`

Las mismas pruebas corren en GitHub Actions en cada push y pull request (`.github/workflows/pruebas.yml`).

## 4. El programa completo

```powershell
.\.venv\Scripts\python.exe main.py
```

Abre la ventana de CLINICAN. La base queda en `%USERPROFILE%\Clinican\clinican.db` (o en la ruta de la variable
`CLINICAN_BD`). Para correr solo el backend, sin ventana, hasta Ctrl+C: `main.py --sin-interfaz`.

## Documentación

- Diseño documentado: [`docs/arquitectura/diseno_documentado.pdf`](docs/arquitectura/diseno_documentado.pdf)
  (fuente en HTML al lado).
- Decisiones de arquitectura: [`docs/adr/`](docs/adr/README.md).
- Detalle de reglas de negocio y configuración: [`backend/README.md`](backend/README.md).
