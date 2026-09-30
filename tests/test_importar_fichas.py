"""Importación de las fichas de peluquería que CLINICAN llenaba en Excel [A-9].

Los archivos de prueba copian el diseño de la ficha real (rótulos y posiciones) con datos inventados.
"""

from datetime import datetime

import pytest
from openpyxl import Workbook

from clinican.datos import importar_fichas_excel as lector
from clinican.dominio.errores import PermisoDenegado
from clinican.servicios import importacion
from clinican.servicios import propietarios as sp


def ficha(ruta, fecha=datetime(2026, 8, 12), mascota="LOLA", raza=" POODLE ", sexo="HEMBRA",
          propietario="ANA GOMEZ", cedula=52123456, celular="311-222-33-44", celular2="315-000-11-22",
          direccion="CRA 7 N 8-9", valor="DESCRIPCION DEL CORTE: VALOR 45 MIL", marcas=None, nota="CARA PROP BAJITO"):
    """Ficha con el mismo diseño que FORMATO_PELUQUERIA_CLINICAN.xlsx."""
    libro = Workbook()
    h = libro.active
    h.title = "Hoja1"
    h["B3"], h["C3"], h["D3"], h["E3"] = "Fecha", fecha, "Mascota", mascota
    h["B4"], h["C4"], h["D4"], h["E4"] = "Raza", raza, "Sexo", sexo
    h["B5"], h["C5"], h["D5"], h["E5"] = "Propietario", propietario, "C.C.", cedula
    h["B6"], h["C6"], h["D6"], h["E6"] = "Cel/ Tel", celular, "Dirección", direccion
    h["C7"] = celular2
    h["B8"] = valor
    izquierda = ["Tijera", "Despunte", "Baño - cepillado", "Baño medicado", "Bajar 1 cm", "Bajar 1/2 cm", "Patas rasuradas"]
    derecha = ["Barbas", "Bigotes", "Copete", "Orejas", "Cola", "Baño antipulgas", "Desparasitación"]
    marcas = {"Bajar 1/2 cm": "X", "Cola": "LEON"} if marcas is None else marcas
    for i, (a, b) in enumerate(zip(izquierda, derecha), start=9):
        h[f"B{i}"], h[f"C{i}"] = a, marcas.get(a, " ")
        h[f"D{i}"], h[f"E{i}"] = b, marcas.get(b, " ")
    h["B16"], h["C16"] = "NOTA", " "
    h["B17"] = nota
    h["B20"] = "NUESTRO SERVICIO INCLUYE:"
    h["B21"] = "Corte de uñas, limpieza de oidos, ..."
    h["B24"] = "CLAUSULAS"
    h["B37"] = "SI________X___________"
    libro.save(ruta)
    return ruta


# ------------------------------------------------------------------ lector

def test_lector_encuentra_todos_los_datos(tmp_path):
    f = lector.leer(ficha(tmp_path / "lola.xlsx"))
    assert (f.fecha, f.mascota, f.raza, f.sexo) == ("2026-08-12", "LOLA", "POODLE", "HEMBRA")
    assert (f.propietario, f.cedula, f.direccion) == ("ANA GOMEZ", "52123456", "CRA 7 N 8-9")
    assert f.celulares == ["3112223344", "3150001122"]
    assert f.marcas == {"bajar_medio_cm": "X", "cola": "LEON"}
    assert (f.valor, f.nota) == (45000, "CARA PROP BAJITO")


@pytest.mark.parametrize("texto,valor", [("DESCRIPCION DEL CORTE: VALOR 45 MIL", 45000), ("valor $50.000", 50000),
                                         ("Valor: 60000", 60000), ("DESCRIPCION DEL CORTE:", None)])
def test_valor_en_pesos(texto, valor):
    assert lector.valor_en_pesos(texto) == valor


def test_archivo_que_no_es_ficha(tmp_path):
    libro = Workbook()
    libro.active["A1"] = "Lista de compras"
    libro.save(tmp_path / "otra.xlsx")
    with pytest.raises(ValueError, match="No parece una ficha"):
        lector.leer(tmp_path / "otra.xlsx")


# ------------------------------------------------------------ importación

def test_importa_propietario_mascota_y_servicio(conn, empleada, tmp_path):
    ruta = ficha(tmp_path / "lola.xlsx")
    previo = importacion.importar_fichas(conn, empleada, [ruta], solo_validar=True)
    assert (previo.fichas_nuevas, previo.mascotas_nuevas, previo.propietarios_nuevos) == (1, 1, 1)
    assert conn.execute("SELECT COUNT(*) FROM propietarios").fetchone()[0] == 0  # la revisión no guarda

    r = importacion.importar_fichas(conn, empleada, [ruta])
    assert r.importado and r.rechazados == []
    dueno = sp.buscar(conn, empleada, "52123456")[0]
    assert (dueno["nombre"], dueno["celular1"], dueno["celular2"]) == ("Ana Gomez", "3112223344", "3150001122")
    lola = sp.mascotas(conn, empleada, dueno["id"])[0]
    assert (lola["nombre"], lola["raza_nombre"], lola["sexo"], lola["fecha_ultima_visita"]) == (
        "Lola", "Poodle (Caniche) Toy y Miniatura", "HEMBRA", "2026-08-12")
    s = sp.historial(conn, empleada, lola["id"])[0]
    assert (s["fecha"], s["tipo_servicio"], s["largo_maquina"], s["cola_leon"]) == ("2026-08-12", "MAQUINA", "MEDIO_CM", 1)
    assert (s["precio_final"], s["total"], s["estado"]) == (45000, 45000, "REALIZADO")
    assert s["observaciones"].startswith("CARA PROP BAJITO [Importada de Excel (lola.xlsx)")
    assert "IMPORTAR_FICHAS_EXCEL" in [f[0] for f in conn.execute("SELECT accion FROM auditoria")]


def test_varias_fichas_se_agrupan_y_no_se_duplican(conn, empleada, tmp_path):
    rutas = [
        ficha(tmp_path / "lola_agosto.xlsx"),
        ficha(tmp_path / "lola_sept.xlsx", fecha=datetime(2026, 9, 10), valor="VALOR 50 MIL",
              marcas={"Tijera": "X", "Baño antipulgas": "X", "Desparasitación": "X"}),
        ficha(tmp_path / "max.xlsx", mascota="MAX", raza="SCHNAUZER", sexo="MACHO"),
    ]
    r = importacion.importar_fichas(conn, empleada, rutas)
    assert (r.fichas_nuevas, r.mascotas_nuevas, r.propietarios_nuevos) == (3, 2, 1)
    dueno = sp.buscar(conn, empleada, "52123456")[0]
    mascotas = {m["nombre"]: m for m in sp.mascotas(conn, empleada, dueno["id"])}
    assert mascotas["Max"]["raza_nombre"] == "Schnauzer"  # no «Schnauzer Miniatura»
    assert mascotas["Lola"]["fecha_ultima_visita"] == "2026-09-10"
    sept = sp.historial(conn, empleada, mascotas["Lola"]["id"])[0]
    assert (sept["tipo_servicio"], sept["bano_antipulgas"], sept["desparasitacion"], sept["total"]) == ("TIJERA", 1, 1, 50000)

    otra_vez = importacion.importar_fichas(conn, empleada, rutas)
    assert (otra_vez.fichas_nuevas, otra_vez.mascotas_nuevas, otra_vez.propietarios_nuevos) == (0, 0, 0)
    assert conn.execute("SELECT COUNT(*) FROM servicios").fetchone()[0] == 3


def test_propietario_existente_y_sin_cedula(conn, empleada, tmp_path):
    pid = sp.crear(conn, empleada, "Ana Gómez", "52123456", "3112223344", None, "Cra 7")
    sin_cc = ficha(tmp_path / "sin_cc.xlsx", propietario="PEDRO RUIZ", cedula=None, celular="3170000000",
                   celular2=None, mascota="ROCKY", raza="LABRADOR")
    r = importacion.importar_fichas(conn, empleada, [ficha(tmp_path / "lola.xlsx"), sin_cc])
    assert r.propietarios_nuevos == 1 and r.rechazados == []
    assert [m["nombre"] for m in sp.mascotas(conn, empleada, pid)] == ["Lola"]  # se agregó a la que ya existía
    pedro = sp.buscar(conn, empleada, "3170000000")[0]
    assert pedro["provisional"] == 1  # sin cédula: cliente sin registrar
    assert any("sin registrar" in aviso for _a, aviso in r.avisos)


def test_rechazos_con_motivo(conn, empleada, tmp_path):
    rutas = [
        ficha(tmp_path / "rara.xlsx", mascota="KIRA", raza="DALMATA"),
        ficha(tmp_path / "criollo.xlsx", mascota="FIRULAIS", raza="CRIOLLO"),
        ficha(tmp_path / "sin_cel.xlsx", mascota="BOBO", celular="12", celular2=None),
        ficha(tmp_path / "buena.xlsx"),
    ]
    r = importacion.importar_fichas(conn, empleada, rutas)
    motivos = dict(r.rechazados)
    assert "no está en el catálogo" in motivos["rara.xlsx"]
    assert "no tiene tamaño" in motivos["criollo.xlsx"]  # criollo = mestizo: el tamaño se registra a mano
    assert "celular" in motivos["sin_cel.xlsx"]
    assert r.fichas_nuevas == 1  # los rechazos no impiden importar las demás


def test_buscar_raza(conn):
    assert importacion.buscar_raza(conn, "poodle")["nombre"] == "Poodle (Caniche) Toy y Miniatura"
    assert importacion.buscar_raza(conn, "YORKI")["nombre"] == "Yorkshire Terrier"
    assert importacion.buscar_raza(conn, "golden retriever")["nombre"] == "Golden Retriever"
    assert importacion.buscar_raza(conn, "Husky")["nombre"] == "Husky"
    assert importacion.buscar_raza(conn, "Dálmata") is None


def test_importar_fichas_requiere_sesion(conn, tmp_path):
    with pytest.raises(PermisoDenegado):
        importacion.importar_fichas(conn, None, [ficha(tmp_path / "x.xlsx")])
