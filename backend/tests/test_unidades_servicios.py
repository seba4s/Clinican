"""Validaciones de entrada y casos límite de los servicios que no cubren las pruebas de flujo."""

import threading
import time as reloj_real
from datetime import date, datetime

import pytest

from clinican.datos import respaldos as datos_respaldos
from clinican.dominio.cupos import CategoriaCupo as C
from clinican.dominio.cupos import Servicio
from clinican.dominio.errores import DatoInvalido, NoEncontrado, OperacionNoPermitida
from clinican.servicios import (
    agenda,
    autorizaciones,
    clientes,
    configuracion,
    fichas,
    importacion,
    notificaciones,
    precios,
    respaldos,
)
from clinican.servicios.despachador import Despachador
from escenario import AHORA, LUNES, a_las


@pytest.mark.parametrize(
    "valor, esperado",
    [(None, ""), ("  Roma ", "Roma"), (3.0, "3"), (2.5, "2.5"), (12, "12"), (0, "0")],
)
def test_importacion_texto_de_celda(valor, esperado):
    assert importacion._texto(valor) == esperado


@pytest.mark.parametrize(
    "valor, esperado",
    [(None, 0), ("", 0), ("  ", 0), (4, 4), (4.0, 4), (" 7 ", "7"), ("3", 3)],
)
def test_importacion_entero_de_celda(valor, esperado):
    assert importacion._entero(valor, "Edad") == int(esperado)


@pytest.mark.parametrize("valor", [True, False, 2.5, "dos", "3,5"])
def test_importacion_entero_invalido(valor):
    with pytest.raises(DatoInvalido, match="Edad"):
        importacion._entero(valor, "Edad")


@pytest.mark.parametrize(
    "valor, esperada",
    [
        (None, None),
        ("", None),
        (datetime(2026, 3, 4, 10, 30), date(2026, 3, 4)),
        (date(2026, 3, 4), date(2026, 3, 4)),
        (" 2026-03-04 ", date(2026, 3, 4)),
    ],
)
def test_importacion_fecha_de_celda(valor, esperada):
    assert importacion._fecha(valor) == esperada


@pytest.mark.parametrize("valor", ["04/03/2026", "ayer", "2026-13-01", 2026])
def test_importacion_fecha_invalida(valor):
    with pytest.raises(DatoInvalido):
        importacion._fecha(valor)


def test_importacion_encabezados_sin_tildes_ni_mayusculas():
    assert importacion.normalizar_encabezado("  Cédula del Propietario * ") == \
        importacion.normalizar_encabezado("cedula del propietario")


def test_importacion_archivo_sin_columnas_obligatorias():
    with pytest.raises(DatoInvalido, match="Faltan columnas"):
        importacion.mapear_encabezados(["Nombre del propietario *", "Otra"])


def _atendido(con, esc):
    turno = agenda.registrar_abono(con, esc.turno(inicio=a_las(9)).id, 20000, ahora=AHORA)
    agenda.iniciar_atencion(con, turno.id, ahora=AHORA)
    agenda.marcar_atendido(con, turno.id, ahora=AHORA)
    return fichas.ficha_de_turno(con, turno.id)


def test_ficha_de_turno_inexistente(con):
    with pytest.raises(NoEncontrado):
        fichas.crear_ficha(con, 9999, ahora=AHORA)
    with pytest.raises(NoEncontrado):
        fichas.obtener_ficha(con, 9999)
    assert fichas.ficha_de_turno(con, 9999) is None


def test_no_se_crea_ficha_de_turno_pendiente(con, esc):
    turno = esc.turno()
    with pytest.raises(OperacionNoPermitida, match="atendidos o entregados"):
        fichas.crear_ficha(con, turno.id, ahora=AHORA)


def test_turno_atendido_no_admite_segunda_ficha(con, esc):
    ficha = _atendido(con, esc)
    with pytest.raises(OperacionNoPermitida, match="ya tiene ficha"):
        fichas.crear_ficha(con, ficha.turno_id, ahora=AHORA)


@pytest.mark.parametrize("campo", ["servicios_realizados", "detalles_corte", "observaciones"])
def test_ficha_campos_deben_ser_texto(con, esc, campo):
    ficha = _atendido(con, esc)
    with pytest.raises(DatoInvalido, match="texto"):
        fichas.editar_ficha(con, ficha.id, ahora=AHORA, **{campo: 123})


def test_ficha_edicion_recorta_espacios_y_conserva_lo_demas(con, esc):
    ficha = _atendido(con, esc)
    editada = fichas.editar_ficha(con, ficha.id, ahora=AHORA, observaciones="  tranquilo  ")
    assert editada.observaciones == "tranquilo"
    assert editada.precio_final == ficha.precio_final
    assert editada.detalles_corte == ficha.detalles_corte


@pytest.mark.parametrize("precio", [0, -5000, 45000.0, True, "45000"])
def test_ficha_precio_final_invalido(con, esc, precio):
    ficha = _atendido(con, esc)
    with pytest.raises(DatoInvalido, match="precio final"):
        fichas.editar_ficha(con, ficha.id, ahora=AHORA, precio_final=precio)
    assert fichas.obtener_ficha(con, ficha.id).precio_final == ficha.precio_final


@pytest.mark.parametrize("porcentaje", [-1, 101, 50.0, True, "50"])
def test_sesion_desenredado_porcentaje_invalido(con, esc, porcentaje):
    ficha = _atendido(con, esc)
    with pytest.raises(DatoInvalido, match="porcentaje"):
        fichas.registrar_sesion_desenredado(con, ficha.id, ahora=AHORA, porcentaje=porcentaje)


def test_sesiones_de_desenredado_se_numeran_por_mascota(con, esc):
    ficha = _atendido(con, esc)
    s1 = fichas.registrar_sesion_desenredado(con, ficha.id, ahora=AHORA, avance=" nudos ", porcentaje=0)
    s2 = fichas.registrar_sesion_desenredado(con, ficha.id, ahora=AHORA, porcentaje=100)
    assert (s1.numero_sesion, s2.numero_sesion) == (1, 2)
    assert s1.avance == "nudos"
    assert s1.fecha == LUNES


def test_autorizacion_medio_se_limpia(con, esc):
    p = esc.propietario()
    vigente = autorizaciones.registrar_autorizacion(
        con, p.id, LUNES, ahora=AHORA, medio="  formato   firmado \n en papel "
    )
    assert vigente.medio == "formato firmado en papel"


def test_autorizacion_medio_debe_ser_texto(con, esc):
    p = esc.propietario()
    with pytest.raises(DatoInvalido, match="medio"):
        autorizaciones.registrar_autorizacion(con, p.id, LUNES, ahora=AHORA, medio=5)
    assert autorizaciones.historial(con, p.id) == []


def test_autorizacion_exige_ahora_con_zona(con, esc):
    p = esc.propietario()
    with pytest.raises(ValueError, match="zona horaria"):
        autorizaciones.registrar_autorizacion(con, p.id, LUNES, ahora=datetime(2026, 11, 9, 8))


def test_autorizacion_de_propietario_inexistente(con):
    with pytest.raises(NoEncontrado):
        autorizaciones.registrar_autorizacion(con, 9999, LUNES, ahora=AHORA)


@pytest.mark.parametrize("categoria", ["MAQUINA", None, Servicio.BANO])
def test_precio_con_categoria_invalida(con, categoria):
    with pytest.raises(DatoInvalido, match="categoría"):
        precios.cambiar_precio(con, categoria, 50000, date(2026, 12, 1), ahora=AHORA)
    with pytest.raises(DatoInvalido, match="categoría"):
        precios.precio_en_fecha(con, categoria, LUNES)


@pytest.mark.parametrize("fecha", [datetime(2026, 12, 1, 0, 0), "2026-12-01", None])
def test_precio_vigente_desde_debe_ser_fecha(con, fecha):
    with pytest.raises(DatoInvalido, match="vigente_desde"):
        precios.cambiar_precio(con, C.MAQUINA, 50000, fecha, ahora=AHORA)


@pytest.mark.parametrize("valor", [-1, 50000.0, "50000"])
def test_precio_con_valor_invalido(con, valor):
    with pytest.raises(DatoInvalido):
        precios.cambiar_precio(con, C.MAQUINA, valor, date(2026, 12, 1), ahora=AHORA)
    assert precios.precio_en_fecha(con, C.MAQUINA, date(2026, 12, 1)) == 45000


def test_turno_con_servicio_invalido(con, esc):
    mascota = esc.mascota()
    with pytest.raises(DatoInvalido, match="servicio"):
        agenda.crear_turno(con, mascota.id, a_las(9), "BANO", ahora=AHORA)


def test_turno_de_mascota_inexistente(con):
    with pytest.raises(NoEncontrado):
        agenda.crear_turno(con, 9999, a_las(9), Servicio.BANO, ahora=AHORA)


def test_bloqueo_debe_ser_un_bloqueo(con):
    with pytest.raises(DatoInvalido, match="Bloqueo"):
        agenda.crear_bloqueo(con, LUNES, ahora=AHORA)


def test_mascota_inexistente(con):
    with pytest.raises(NoEncontrado):
        clientes.obtener_mascota(con, 9999)


def test_reintentar_notificacion_inexistente(con):
    with pytest.raises(NoEncontrado):
        notificaciones.reintentar(con, 9999, ahora=AHORA)


@pytest.mark.parametrize(
    "clave, valor",
    [
        ("horas_antes_recordatorio", -1),
        ("horas_antes_recordatorio_final", 1.5),
        ("horas_antes_recordatorio", True),
        ("minutos_expiracion", 0),
        ("respaldos_a_conservar", -3),
    ],
)
def test_configuracion_rechaza_enteros_invalidos(con, clave, valor):
    antes = configuracion.leer(con, clave)
    with pytest.raises((DatoInvalido, TypeError, ValueError)):
        configuracion.guardar(con, clave, valor, ahora=AHORA)
    assert configuracion.leer(con, clave) == antes


def test_configuracion_acepta_recordatorio_en_cero_horas(con):
    configuracion.guardar(con, "horas_antes_recordatorio_final", 0, ahora=AHORA)
    assert configuracion.leer(con, "horas_antes_recordatorio_final") == 0


def test_listar_respaldos_de_carpeta_inexistente(tmp_path):
    assert respaldos.listar_respaldos(tmp_path / "no_existe") == []


def test_listar_respaldos_ignora_archivos_ajenos(tmp_path):
    for nombre in ("clinican_20261109_080000.db", "clinican_basura.db", "otra.db",
                   "clinican_20261108_080000.db", "clinican_20261109_080000_2.db"):
        (tmp_path / nombre).write_bytes(b"")
    assert [p.name for p in respaldos.listar_respaldos(tmp_path)] == [
        "clinican_20261108_080000.db", "clinican_20261109_080000.db", "clinican_20261109_080000_2.db",
    ]


def test_respaldo_que_no_pasa_la_verificacion_se_borra(ruta_db, monkeypatch):
    def falla(ruta):
        raise datos_respaldos.RespaldoInvalido("copia dañada")

    monkeypatch.setattr(datos_respaldos, "verificar", falla)
    with pytest.raises(datos_respaldos.RespaldoInvalido):
        respaldos.crear_respaldo(ruta_db, ahora=AHORA)
    assert respaldos.listar_respaldos(ruta_db.parent / "respaldos") == []


def _esperar(condicion, segundos=10):
    limite = reloj_real.monotonic() + segundos
    while not condicion() and reloj_real.monotonic() < limite:
        reloj_real.sleep(0.02)
    return condicion()


def test_respaldo_diario_sigue_vivo_tras_un_error(ruta_db, monkeypatch):
    llamadas = []

    def falla(ruta, *, ahora):
        llamadas.append(ahora)
        raise RuntimeError("disco lleno")

    monkeypatch.setattr(respaldos, "respaldo_diario_si_falta", falla)
    hilo = respaldos.RespaldoDiario(ruta_db, reloj=lambda: AHORA, intervalo_segundos=0.01)
    primero = hilo.iniciar()
    try:
        assert hilo.iniciar() is primero
        assert _esperar(lambda: len(llamadas) >= 2)
        assert hilo.corriendo
    finally:
        hilo.detener()
    assert not hilo.corriendo


class _Mudo:
    def enviar(self, mensaje):
        return None


def test_despachador_en_hilo_necesita_reloj(ruta_db):
    with pytest.raises(ValueError, match="reloj"):
        Despachador(ruta_db, _Mudo()).iniciar()


def test_despachador_sigue_vivo_tras_un_error(ruta_db, monkeypatch):
    llamadas = []
    despachador = Despachador(ruta_db, _Mudo(), reloj=lambda: AHORA, intervalo_segundos=0.01)

    def falla(ahora):
        llamadas.append(ahora)
        raise RuntimeError("base bloqueada")

    monkeypatch.setattr(despachador, "procesar_una_vez", falla)
    primero = despachador.iniciar()
    try:
        assert despachador.iniciar() is primero
        assert isinstance(primero, threading.Thread)
        assert _esperar(lambda: len(llamadas) >= 2)
        assert despachador.corriendo
    finally:
        despachador.detener()
    assert not despachador.corriendo
