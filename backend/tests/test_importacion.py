from datetime import date, datetime
from pathlib import Path

import pytest

from clinican.adaptadores.importacion_excel import importar_mascotas_desde_excel, leer_filas
from clinican.dominio.cupos import Tamano
from clinican.dominio.errores import DatoInvalido
from clinican.servicios import clientes
from clinican.servicios.auditoria import historial
from clinican.servicios.importacion import COLUMNAS, mapear_encabezados
from conftest import AHORA

PLANTILLA_REAL = Path(__file__).resolve().parents[2] / "plantilla_importacion.xlsx"
ENCABEZADOS = list(COLUMNAS.values())


def _xlsx(ruta: Path, filas, encabezados=ENCABEZADOS, hoja="Mascotas") -> Path:
    import openpyxl

    libro = openpyxl.Workbook()
    ws = libro.active
    ws.title = hoja
    ws.append(encabezados)
    for fila in filas:
        ws.append(list(fila))
    libro.save(ruta)
    return ruta


def _fila(**cambios):
    base = {
        "cedula": "1098765432", "nombre_propietario": "María Pérez", "celular1": "3001234567",
        "celular2": None, "direccion": "Calle 10 # 5-20", "nombre_mascota": "Toby",
        "raza": "Shih Tzu", "tamano": "Pequeña", "complicado": None, "edad_anios": 3,
        "edad_meses": 0, "ultima_visita": "2026-02-15", "observaciones": "Nervioso con el secador",
    }
    base.update(cambios)
    return [base[k] for k in COLUMNAS]


@pytest.mark.skipif(not PLANTILLA_REAL.exists(), reason="plantilla del repositorio no disponible")
def test_encabezados_de_la_plantilla_real():
    import openpyxl

    libro = openpyxl.load_workbook(PLANTILLA_REAL, read_only=True)
    encabezados = next(libro["Mascotas"].iter_rows(values_only=True))
    libro.close()
    assert set(mapear_encabezados(encabezados).values()) == set(COLUMNAS)
    assert leer_filas(PLANTILLA_REAL) == []  # solo encabezados


def test_importa_fila_de_ejemplo_de_la_plantilla(con, tmp_path):
    ruta = _xlsx(tmp_path / "m.xlsx", [_fila()])
    informe = importar_mascotas_desde_excel(con, ruta, ahora=AHORA)
    assert informe.rechazadas == [] and len(informe.aceptadas) == 1
    a = informe.aceptadas[0]
    assert a.fila == 2 and a.propietario_nuevo
    p = clientes.obtener_propietario(con, a.propietario_id)
    assert (p.cedula, p.nombre, p.telefono, p.direccion) == (
        "1098765432", "María Pérez", "3001234567", "Calle 10 # 5-20"
    )
    m = clientes.obtener_mascota(con, a.mascota_id)
    assert (m.nombre, m.tamano, m.complicado) == ("Toby", Tamano.PEQUENO, False)
    assert m.fecha_nacimiento == date(2023, 11, 9)
    assert m.ultima_visita == date(2026, 2, 15)
    assert m.observaciones == "Nervioso con el secador"
    assert [r.accion for r in historial(con, "mascota", m.id)] == ["importar"]


def test_informe_acepta_y_rechaza_sin_abortar(con, tmp_path):
    filas = [
        _fila(),                                                         # 2 ok
        _fila(nombre_mascota="Luna", tamano="Grande", edad_anios=None,
              edad_meses=None, ultima_visita=datetime(2026, 3, 26)),     # 3 ok, mismo dueño
        _fila(cedula=None),                                              # 4 sin cédula
        _fila(cedula="555", celular1="12345"),                           # 5 cédula y celular malos
        _fila(cedula="2222", raza="Dálmata"),                            # 6 raza inexistente
        _fila(cedula="3333", raza="Perro mestizo (sin raza)", tamano="Mediana"),  # 7 falta pelaje
        _fila(cedula="4444", tamano=None),                               # 8 sin tamaño
        _fila(cedula="5555", tamano="Enorme", complicado="Tal vez"),     # 9 valores inválidos
        _fila(cedula="6666", edad_meses=14),                             # 10 meses fuera de rango
        _fila(cedula="7777", ultima_visita="26/03/2026"),                # 11 fecha mal escrita
        [None] * len(COLUMNAS),                                          # 12 vacía: se ignora
        _fila(),                                                         # 13 mascota repetida
        _fila(cedula="8888", direccion=None, nombre_mascota=None),       # 14 faltan datos
        _fila(cedula=" 9.999.999 ", celular1="300 765 4321", raza="perro MESTIZO (sin raza)",
              tamano="mediana", complicado="SÍ", celular2="3107654321"), # 15 ok
    ]
    informe = importar_mascotas_desde_excel(con, _xlsx(tmp_path / "m.xlsx", filas), ahora=AHORA)
    assert [a.fila for a in informe.aceptadas] == [2, 3, 15]
    assert [a.propietario_nuevo for a in informe.aceptadas] == [True, False, True]
    motivos = {r.fila: r.motivo for r in informe.rechazadas}
    assert sorted(motivos) == [4, 5, 6, 7, 8, 9, 10, 11, 13, 14]
    assert "Falta Cédula del propietario" in motivos[4]
    assert "Cédula inválida" in motivos[5] and "10 dígitos" in motivos[5]
    assert "Dálmata" in motivos[6]
    assert "mestizos" in motivos[7]
    assert "Falta el tamaño" in motivos[8]
    assert "Tamaño inválido" in motivos[9] and "Pelaje complicado inválido" in motivos[9]
    assert "meses" in motivos[10]
    assert "AAAA-MM-DD" in motivos[11]
    assert "ya tiene una mascota llamada Toby" in motivos[13]
    assert "Falta Dirección" in motivos[14] and "Falta Nombre de la mascota" in motivos[14]
    assert "Fila 4:" in informe.resumen and informe.resumen.startswith("Filas aceptadas: 3.")
    nuevo = clientes.obtener_por_cedula(con, "9999999")
    assert (nuevo.telefono, nuevo.celular2) == ("3007654321", "3107654321")
    [mestizo] = clientes.buscar_mascotas(con, propietario_id=nuevo.id)
    assert mestizo.complicado and mestizo.tamano is Tamano.MEDIANO
    # Las filas rechazadas no dejaron propietarios a medias
    assert clientes.obtener_por_cedula(con, "2222") is None


def test_cedula_existente_no_cambia_datos_del_propietario(con, esc, tmp_path):
    existente = clientes.crear_propietario(
        con, "Nombre Original", "3110000000", cedula="1098765432", direccion="Original",
        ahora=AHORA,
    )
    ruta = _xlsx(tmp_path / "m.xlsx", [_fila(nombre_mascota="Kira")])
    informe = importar_mascotas_desde_excel(con, ruta, ahora=AHORA)
    assert informe.aceptadas[0].propietario_id == existente.id
    assert not informe.aceptadas[0].propietario_nuevo
    p = clientes.obtener_propietario(con, existente.id)
    assert (p.nombre, p.telefono, p.direccion) == ("Nombre Original", "3110000000", "Original")


def test_cedula_de_propietario_fusionado_va_al_destino(con, tmp_path):
    origen = clientes.crear_propietario(con, "Dup", "3110000000", cedula="1098765432", ahora=AHORA)
    destino = clientes.crear_propietario(con, "Real", "3110000001", cedula="11111", ahora=AHORA)
    clientes.unir_propietarios(con, origen.id, destino.id, ahora=AHORA)
    informe = importar_mascotas_desde_excel(con, _xlsx(tmp_path / "m.xlsx", [_fila()]), ahora=AHORA)
    assert informe.aceptadas[0].propietario_id == destino.id


def test_cedula_numerica_de_excel(con, tmp_path):
    ruta = _xlsx(tmp_path / "m.xlsx", [_fila(cedula=1098765432, celular1=3001234567)])
    informe = importar_mascotas_desde_excel(con, ruta, ahora=AHORA)
    assert informe.rechazadas == []
    assert clientes.obtener_por_cedula(con, "1098765432").telefono == "3001234567"


def test_archivo_sin_formato_de_plantilla(con, tmp_path):
    ruta = _xlsx(tmp_path / "otro.xlsx", [["x"]], encabezados=["Nombre", "Teléfono"])
    with pytest.raises(DatoInvalido, match="Faltan columnas"):
        importar_mascotas_desde_excel(con, ruta, ahora=AHORA)
    malo = tmp_path / "no_es_excel.xlsx"
    malo.write_text("hola")
    with pytest.raises(DatoInvalido, match="Excel"):
        importar_mascotas_desde_excel(con, malo, ahora=AHORA)
    with pytest.raises(DatoInvalido, match="No existe"):
        importar_mascotas_desde_excel(con, tmp_path / "nada.xlsx", ahora=AHORA)


def test_openpyxl_se_importa_solo_al_leer():
    import subprocess
    import sys

    codigo = (
        "import sys; import clinican.adaptadores.importacion_excel, clinican.servicios.importacion; "
        "print('openpyxl' in sys.modules)"
    )
    salida = subprocess.run(
        [sys.executable, "-c", codigo], capture_output=True, text=True,
        cwd=Path(__file__).resolve().parents[1], check=True,
    ).stdout.strip()
    assert salida == "False"
