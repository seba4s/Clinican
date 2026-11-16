"""Casos de error de los adaptadores: consola, corte de red simulado, registro de canales y Excel."""

import socket

import pytest

from clinican.adaptadores import notificadores
from clinican.adaptadores.importacion_excel import leer_filas
from clinican.adaptadores.notificadores import NotificadorConsola, linea, sin_red
from clinican.dominio.errores import DatoInvalido
from clinican.servicios.notificaciones import ErrorEnvio, Mensaje
from escenario import a_las

MENSAJE = Mensaje(
    notificacion_id=1, turno_id=7, tipo="recordatorio", telefono="", propietario="Ana",
    mascota="Toby", inicio=a_las(10), texto="Hola\nmañana tiene turno",
)


def test_linea_sin_telefono_y_en_un_solo_renglon():
    texto = linea(MENSAJE)
    assert "sin teléfono" in texto
    assert "\n" not in texto
    assert texto.startswith("2026-11-09 10:00 | turno 7 |")


class _SalidaRota:
    def write(self, texto):
        raise OSError("consola cerrada")

    def flush(self):
        pass


def test_consola_que_falla_da_error_de_envio():
    with pytest.raises(ErrorEnvio, match="consola"):
        NotificadorConsola(_SalidaRota()).enviar(MENSAJE)


def test_consola_por_defecto_escribe_en_stdout(capsys):
    NotificadorConsola().enviar(MENSAJE)
    assert capsys.readouterr().out.startswith("[recordatorio] ")


def test_sin_red_corta_y_restaura_las_conexiones():
    originales = (socket.socket, socket.create_connection, socket.getaddrinfo)
    with sin_red():
        with pytest.raises(OSError, match="sin red"):
            socket.create_connection(("example.com", 443))
        with pytest.raises(OSError, match="sin red"):
            socket.getaddrinfo("example.com", 443)
    assert (socket.socket, socket.create_connection, socket.getaddrinfo) == originales


def test_sin_red_restaura_aunque_haya_error():
    original = socket.create_connection
    with pytest.raises(RuntimeError):
        with sin_red():
            raise RuntimeError("falla dentro del bloque")
    assert socket.create_connection is original


@pytest.mark.parametrize("canal", ["sms", "", None, 3])
def test_canal_desconocido(canal, tmp_path):
    with pytest.raises(DatoInvalido, match="desconocido"):
        notificadores.notificador_para(canal, tmp_path)


def test_canal_sin_importar_mayusculas_ni_espacios(tmp_path):
    assert isinstance(notificadores.notificador_para("  CONSOLA ", tmp_path), NotificadorConsola)


def test_canales_disponibles():
    assert {"archivo", "consola", "whatsapp"} <= set(notificadores.canales())


def test_excel_que_no_es_excel(tmp_path):
    falso = tmp_path / "mascotas.xlsx"
    falso.write_text("no soy un libro de Excel")
    with pytest.raises(DatoInvalido, match="No se pudo abrir"):
        leer_filas(falso)


def test_excel_vacio(tmp_path):
    import openpyxl

    ruta = tmp_path / "vacio.xlsx"
    openpyxl.Workbook().save(ruta)
    with pytest.raises(DatoInvalido, match="vacío"):
        leer_filas(ruta)
