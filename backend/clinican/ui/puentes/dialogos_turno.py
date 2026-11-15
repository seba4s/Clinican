"""Diálogos del turno: nuevo turno, mover, abono, inasistencia y bloqueo de horas."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Callable

from PySide6.QtCore import Property, Signal, Slot

from clinican.dominio.agenda import ZONA, Bloqueo
from clinican.dominio.cupos import CategoriaCupo, Servicio, categoria_de_cupo
from clinican.dominio.errores import DatoInvalido
from clinican.dominio.estados import EstadoTurno
from clinican.servicios import agenda, clientes, configuracion, precios
from clinican.ui import formato as fmt
from clinican.ui.busqueda import buscar_clientes
from clinican.ui.formato import leer_hora
from clinican.ui.puentes.base import Dialogo, propiedad

POR_QUE = {
    CategoriaCupo.COMPLICADO: "La mascota está marcada como de pelaje complicado.",
    CategoriaCupo.GRANDE: "La mascota es de tamaño grande.",
    CategoriaCupo.TIJERA: "El corte es a tijera.",
    CategoriaCupo.MAQUINA: "No es grande, ni complicada, ni corte a tijera.",
}


def validar_monto(texto: str) -> str | None:
    try:
        fmt.leer_pesos(texto)
    except DatoInvalido as e:
        return str(e)
    return None


class SelectorHora:
    """Día con flechas y las franjas que aún tienen cupo para una categoría."""

    def __init__(self, ctx, dia: date, al_cambiar: Callable[[], None], al_elegir: Callable[[], None] | None = None):
        self.ctx = ctx
        self.dia = dia
        self.categoria: CategoriaCupo | None = None
        self.elegida: datetime | None = None
        self.al_cambiar = al_cambiar
        self.al_elegir = al_elegir
        self._franjas: list[datetime] = []
        self.datos: dict = {}

    def mover_dia(self, delta: int) -> None:
        self.dia += timedelta(days=delta)
        self.elegida = None
        self.dibujar()
        if self.al_elegir:
            self.al_elegir()

    def poner(self, categoria: CategoriaCupo | None, elegida: datetime | None = None) -> None:
        self.categoria = categoria
        if elegida is not None:
            self.elegida = elegida
        self.dibujar()

    def dibujar(self) -> None:
        dia = fmt.dia_largo(self.dia) + (" (hoy)" if self.dia == self.ctx.hoy() else "")
        self._franjas = []
        if self.categoria is None:
            self.datos = {"dia": dia, "mensaje": "Elige cliente, mascota y servicio para ver las horas con cupo.",
                          "franjas": []}
            self.al_cambiar()
            return
        ahora = self.ctx.ahora()
        with self.ctx.con() as con:
            disp = [(f, libres[self.categoria]) for f, libres in agenda.disponibilidad(con, self.dia, ahora=ahora)
                    if f.inicio > ahora]
        if not disp:
            self.datos = {"dia": dia, "mensaje": "No quedan horas este día. Prueba con otro día.", "franjas": []}
            self.al_cambiar()
            return
        if self.elegida and not any(f.inicio == self.elegida and n for f, n in disp):
            self.elegida = None
        franjas = []
        for i, (franja, n) in enumerate(disp):
            self._franjas.append(franja.inicio)
            franjas.append({"indice": i, "hora": fmt.hora(franja.inicio),
                            "detalle": "Lleno" if n <= 0 else ("1 libre" if n == 1 else f"{n} libres"),
                            "lleno": n <= 0, "elegida": franja.inicio == self.elegida})
        self.datos = {"dia": dia, "mensaje": "", "franjas": franjas}
        self.al_cambiar()

    def elegir(self, inicio: datetime) -> None:
        self.elegida = inicio
        self.dibujar()
        if self.al_elegir:
            self.al_elegir()

    def elegir_indice(self, indice: int) -> None:
        self.elegir(self._franjas[indice])


class DialogoNuevoTurno(Dialogo):
    cambioNuevoTurno = Signal()
    vista = "DialogoNuevoTurno.qml"

    def __init__(self, pantalla, ctx, dia: date, inicio: datetime | None = None,
                 categoria: CategoriaCupo | None = None, mascota_id: int | None = None):
        super().__init__(ctx, "Nuevo turno", ancho=760)
        self.pantalla = pantalla
        self.propietario = None
        self.mascotas = []
        self.razas = {}
        self.categoria_sugerida = categoria
        with ctx.con() as con:
            self.cfg = configuracion.cargar(con)
        self._texto_cliente = ""
        self._resultados: list[dict] = []
        self._sin_resultados = False
        self._cliente: dict = {}
        self._lista_mascotas: list[dict] = []
        self._mascota_id = 0
        self._servicio = Servicio.CORTE_MAQUINA.value
        self._texto_categoria = ""
        self._selector: dict = {}
        self._resumen = ""
        self._texto_boton = "Agendar"
        self._encontrados: dict[int, object] = {}
        self._validadores["abono"] = validar_monto
        self.selector = SelectorHora(ctx, dia, self._al_selector, al_elegir=self._actualizar_resumen)
        self.selector.elegida = inicio

        if mascota_id:
            with ctx.con() as con:
                m = clientes.obtener_mascota(con, mascota_id)
                self._elegir_cliente(clientes.obtener_propietario(con, m.propietario_id), m.id)
        if categoria is CategoriaCupo.TIJERA:
            self._servicio = Servicio.CORTE_TIJERA.value
        self._actualizar()

    textoCliente = propiedad(str, "texto_cliente", cambioNuevoTurno)
    resultados = propiedad("QVariantList", "resultados", cambioNuevoTurno)
    sinResultados = propiedad(bool, "sin_resultados", cambioNuevoTurno)
    cliente = propiedad("QVariantMap", "cliente", cambioNuevoTurno)
    listaMascotas = propiedad("QVariantList", "lista_mascotas", cambioNuevoTurno)
    mascotaId = propiedad(int, "mascota_id", cambioNuevoTurno)
    servicio = propiedad(str, "servicio", cambioNuevoTurno)
    textoCategoria = propiedad(str, "texto_categoria", cambioNuevoTurno)
    franjas = propiedad("QVariantMap", "selector", cambioNuevoTurno)
    resumen = propiedad(str, "resumen", cambioNuevoTurno)
    textoBoton = propiedad(str, "texto_boton", cambioNuevoTurno)

    @Property("QVariantList", constant=True)
    def servicios(self) -> list[dict]:
        return [{"valor": s.value, "texto": fmt.SERVICIO[s]} for s in Servicio]

    # -------------------------------------------------------------- cliente y mascota
    @Slot(str)
    def buscar(self, texto: str) -> None:
        texto = texto.strip()
        if len(texto) < 2:
            self.poner(resultados=[], sin_resultados=False)
            return
        with self.ctx.con() as con:
            encontrados = buscar_clientes(con, texto, limite=5)
        self._encontrados = {p.id: p for p in encontrados}
        self.poner(resultados=[{"id": p.id, "texto": f"{p.nombre}   ·   {fmt.cedula(p.cedula)}   ·   {fmt.celular(p.telefono)}"}
                               for p in encontrados], sin_resultados=not encontrados)

    @Slot(str)
    def cliente_nuevo(self, texto: str) -> None:
        pantalla, dia, inicio, cat = self.pantalla, self.selector.dia, self.selector.elegida, self.categoria_sugerida
        self.cerrar()
        pantalla.cliente_nuevo_para_turno(texto.strip(), dia, inicio, cat)

    @Slot(int)
    def elegir_cliente(self, propietario_id: int) -> None:
        self._elegir_cliente(self._encontrados[propietario_id])

    def _elegir_cliente(self, p, mascota_id: int | None = None) -> None:
        self.propietario = p
        with self.ctx.con() as con:
            self.mascotas = clientes.buscar_mascotas(con, propietario_id=p.id)
            self.razas = {m.raza_id: clientes.obtener_raza(con, m.raza_id) for m in self.mascotas if m.raza_id}
            sin_aviso = [t for t in agenda.inasistencias_de_propietario(con, p.id) if t.saldo_generado == 0]
        chips = []
        if sin_aviso:
            chips.append({"texto": f"{len(sin_aviso)} inasistencia{'s' if len(sin_aviso) != 1 else ''} sin aviso",
                          "estado": EstadoTurno.PENDIENTE_ABONO.name})
        if p.saldo_a_favor:
            chips.append({"texto": f"Saldo a favor {fmt.pesos(p.saldo_a_favor)}", "estado": EstadoTurno.CONFIRMADO.name})
        lista = []
        for m in self.mascotas:
            raza = self.razas.get(m.raza_id)
            lista.append({"id": m.id, "texto": f"{m.nombre} · {raza.nombre if raza else 'sin raza'}, {fmt.TAMANO[m.tamano]}"
                                               + (" · complicado" if m.complicado else "")})
        elegida = mascota_id or (self.mascotas[0].id if len(self.mascotas) == 1 else 0)
        self.poner(texto_cliente=p.nombre, resultados=[], sin_resultados=False, lista_mascotas=lista, mascota_id=elegida,
                   cliente={"nombre": p.nombre, "linea": f"{fmt.cedula(p.cedula)} · {fmt.celular(p.telefono)}",
                            "chips": chips})
        self._actualizar()

    @Slot(int)
    def elegir_mascota(self, mascota_id: int) -> None:
        self.poner(mascota_id=mascota_id)
        self._actualizar()

    @Slot(str)
    def elegir_servicio(self, valor: str) -> None:
        self.poner(servicio=valor)
        self._actualizar()

    def _mascota(self):
        return next((m for m in self.mascotas if m.id == self._mascota_id), None)

    # -------------------------------------------------------------- categoría, hora y resumen
    def _categoria(self) -> CategoriaCupo | None:
        m = self._mascota()
        if m is None:
            return None
        raza = self.razas.get(m.raza_id)
        return categoria_de_cupo(raza.nombre if raza else None, m.tamano, m.pelaje, Servicio(self._servicio), m.complicado)

    def _actualizar(self) -> None:
        cat = self._categoria()
        if cat is None:
            texto = "El cupo se calcula solo al elegir la mascota y el servicio."
        else:
            with self.ctx.con() as con:
                precio = precios.precio_en_fecha(con, cat, self.selector.dia)
            texto = f"Va al cupo {fmt.CATEGORIA[cat].upper()}. {POR_QUE[cat]} Precio vigente {fmt.pesos(precio)}."
        self.poner(texto_categoria=texto)
        self.selector.poner(cat)
        self._actualizar_resumen()

    def _al_selector(self) -> None:
        self.poner(selector=dict(self.selector.datos))

    @Slot(int)
    def mover_dia(self, delta: int) -> None:
        self.selector.mover_dia(delta)

    @Slot(int)
    def elegir_hora(self, indice: int) -> None:
        self.selector.elegir_indice(indice)

    def _actualizar_resumen(self) -> None:
        abono = self.cfg.abono
        saldo = min(self.propietario.saldo_a_favor, abono) if self.propietario else 0
        falta = abono - saldo
        partes = [f"Abono {fmt.pesos(abono)}"]
        if saldo:
            partes.append(f"saldo a favor − {fmt.pesos(saldo)}")
        partes.append(f"falta pagar {fmt.pesos(falta)} en {self.cfg.minutos_expiracion} min" if falta else "queda confirmado")
        boton = f"Agendar a las {fmt.hora(self.selector.elegida)}" if self.selector.elegida else "Agendar"
        self.poner(resumen=" · ".join(partes), texto_boton=boton)

    @Slot(str)
    def agendar(self, abono: str) -> None:
        if self.propietario is None:
            self.error("Elige el cliente.")
            return
        m = self._mascota()
        if m is None:
            self.error("Elige la mascota.")
            return
        if self.selector.elegida is None:
            self.error("Elige la hora.")
            return
        if not self.validar("abono", abono):
            return
        monto = fmt.leer_pesos(abono)
        servicio = Servicio(self._servicio)
        inicio = self.selector.elegida

        def crear():
            with self.ctx.con() as con:
                turno = agenda.crear_turno(con, m.id, inicio, servicio, ahora=self.ctx.ahora())
                if monto and turno.estado is EstadoTurno.PENDIENTE_ABONO:
                    turno = agenda.registrar_abono(con, turno.id, monto, ahora=self.ctx.ahora())
                return turno

        if self.intentar(crear):
            self.cerrar()
        else:
            self.selector.dibujar()


class DialogoMover(Dialogo):
    cambioMover = Signal()
    vista = "DialogoMover.qml"

    def __init__(self, ctx, turno):
        super().__init__(ctx, "Mover turno", ancho=680,
                         subtitulo=f"Ahora: {fmt.momento(turno.inicio, ctx.hoy())}, cupo {fmt.CATEGORIA[turno.categoria]}. "
                                   "Solo se muestran las horas con cupo para esa categoría.")
        self.turno = turno
        self._selector: dict = {}
        self.selector = SelectorHora(ctx, fmt.local(turno.inicio).date(), self._al_selector)
        self.selector.poner(turno.categoria)

    franjas = propiedad("QVariantMap", "selector", cambioMover)

    def _al_selector(self) -> None:
        self.poner(selector=dict(self.selector.datos))

    @Slot(int)
    def mover_dia(self, delta: int) -> None:
        self.selector.mover_dia(delta)

    @Slot(int)
    def elegir_hora(self, indice: int) -> None:
        self.selector.elegir_indice(indice)

    @Slot()
    def aceptar(self) -> None:
        if not self.selector.elegida:
            self.error("Elige la nueva hora.")
            return

        def mover():
            with self.ctx.con() as con:
                return agenda.mover_turno(con, self.turno.id, self.selector.elegida, ahora=self.ctx.ahora())

        if self.intentar(mover):
            self.cerrar()


class DialogoAbono(Dialogo):
    cambioAbono = Signal()
    vista = "DialogoAbono.qml"

    def __init__(self, ctx, turno):
        super().__init__(ctx, "Registrar abono", ancho=440,
                         subtitulo=f"Pagado {fmt.pesos(turno.abono_total)} de {fmt.pesos(turno.abono_requerido)}. "
                                   "Si paga de más, el excedente queda como saldo a favor.")
        self.turno = turno
        self._inicial = fmt.pesos(turno.faltante)
        self._validadores["valor"] = lambda t: None if self._monto(t) else "Escribe un valor mayor que cero"

    inicial = propiedad(str, "inicial")

    @staticmethod
    def _monto(texto: str) -> int:
        try:
            return fmt.leer_pesos(texto)
        except DatoInvalido:
            return 0

    @Slot(str)
    def registrar(self, texto: str) -> None:
        if not self.validar("valor", texto):
            return
        monto = self._monto(texto)

        def registrar():
            with self.ctx.con() as con:
                return agenda.registrar_abono(con, self.turno.id, monto, ahora=self.ctx.ahora())

        if self.intentar(registrar):
            self.cerrar()


class DialogoInasistencia(Dialogo):
    cambioInasistencia = Signal()
    vista = "DialogoInasistencia.qml"

    def __init__(self, ctx, turno):
        super().__init__(ctx, "Marcar inasistencia", ancho=480,
                         subtitulo="Si el cliente avisó con 12 horas o más de anticipación, el abono queda a favor; "
                                   "si no, se pierde. Esto no se puede deshacer.")
        self.turno = turno
        self._inicial = fmt.local(ctx.ahora()).strftime("%d/%m/%Y %H:%M")

    inicial = propiedad(str, "inicial")

    @Slot(bool, str)
    def marcar(self, avisó: bool, cuando: str) -> None:
        aviso = None
        if avisó:
            try:
                aviso = datetime.strptime(cuando.strip(), "%d/%m/%Y %H:%M").replace(tzinfo=ZONA)
            except ValueError:
                self.error_campo("cuando", "Escribe la fecha y hora así: 10/11/2026 15:30")
                return
        self.error_campo("cuando", None)

        def marcar():
            with self.ctx.con() as con:
                return agenda.marcar_inasistencia(con, self.turno.id, aviso, ahora=self.ctx.ahora())

        if self.intentar(marcar):
            self.cerrar()


class DialogoBloqueo(Dialogo):
    cambioBloqueo = Signal()
    vista = "DialogoBloqueo.qml"

    def __init__(self, ctx, dia: date):
        super().__init__(ctx, "Bloquear horas", ancho=480,
                         subtitulo="No se puede bloquear un rango que ya tenga turnos activos.")
        self._fecha = fmt.fecha_numerica(dia)
        self._horas = [f"{h:02d}:{m:02d}" for h in range(7, 21) for m in (0, 30)]

    fecha = propiedad(str, "fecha", cambioBloqueo)
    horas = propiedad("QVariantList", "horas", cambioBloqueo)

    @Slot(str, bool, str, str, str)
    def bloquear(self, fecha_texto: str, completo: bool, desde: str, hasta: str, motivo: str) -> None:
        try:
            fecha = fmt.leer_fecha(fecha_texto)
        except DatoInvalido as e:
            self.error_campo("fecha", str(e))
            return
        self.error_campo("fecha", None)
        try:
            if completo:
                bloqueo = Bloqueo(fecha, motivo=motivo.strip())
            else:
                bloqueo = Bloqueo(fecha, leer_hora(desde), leer_hora(hasta), motivo.strip())
        except DatoInvalido as e:
            self.error(f"Revisa las horas: {e}.")
            return
        except ValueError:
            self.error("La hora «hasta» debe ser posterior a «desde».")
            return

        def crear():
            with self.ctx.con() as con:
                return agenda.crear_bloqueo(con, bloqueo, ahora=self.ctx.ahora())

        if self.intentar(crear):
            self.cerrar()
