"""Ficha de servicio: se llena al marcar el turno como atendido y se puede corregir después."""

from __future__ import annotations

from PySide6.QtCore import Signal, Slot

from clinican.dominio.errores import DatoInvalido
from clinican.dominio.estados import EstadoTurno
from clinican.servicios import agenda, clientes, fichas, precios
from clinican.ui import formato as fmt
from clinican.ui.puentes.base import Dialogo, propiedad
from clinican.ui.puentes.dialogos_turno import validar_monto

SERVICIOS = ["Corte a máquina", "Corte a tijera", "Baño", "Uñas", "Limpieza de oídos", "Desenredado"]


class DialogoFicha(Dialogo):
    cambioFicha = Signal()
    vista = "DialogoFicha.qml"

    def __init__(self, ctx, turno_id: int):
        with ctx.con() as con:
            self.turno = agenda.obtener_turno(con, turno_id)
            self.ficha = fichas.ficha_de_turno(con, turno_id)
            mascota = clientes.obtener_mascota(con, self.turno.mascota_id)
            raza = clientes.obtener_raza(con, mascota.raza_id).nombre if mascota.raza_id else "sin raza"
            dueno = clientes.obtener_propietario(con, self.turno.propietario_id)
            self.precio_vigente = precios.precio_en_fecha(con, self.turno.categoria, fmt.local(self.turno.inicio).date())
            self.sesiones = fichas.sesiones_de_mascota(con, mascota.id)
        self.nueva = self.ficha is None
        super().__init__(ctx, f"Ficha de servicio · {mascota.nombre}", ancho=740,
                         subtitulo=f"{raza}, {fmt.TAMANO[mascota.tamano]} · {dueno.nombre} · "
                                   f"{fmt.momento(self.turno.inicio, ctx.hoy())} · cupo {fmt.CATEGORIA[self.turno.categoria].upper()}")
        texto = self.ficha.servicios_realizados.split(",") if self.ficha else [fmt.SERVICIO[self.turno.servicio]]
        marcados = set(s.strip() for s in texto if s.strip())
        extras = [s for s in marcados if s not in SERVICIOS]
        self._servicios = [{"nombre": s, "marcado": s in marcados} for s in SERVICIOS + extras]
        self._corte = self.ficha.detalles_corte if self.ficha else ""
        self._observaciones = self.ficha.observaciones if self.ficha else ""
        n = len(self.sesiones) + 1
        previa = self.sesiones[-1] if self.sesiones else None
        sesion = f"Sesión de desenredado {n} (opcional)"
        if previa:
            sesion += f". La anterior ({fmt.dia_corto(previa.fecha, ctx.hoy())}) llegó al {previa.porcentaje or 0} %."
        self._sesion = sesion
        self._precio = fmt.pesos(self.ficha.precio_final if self.ficha else self.precio_vigente)
        self._nota_precio = (f"Precio de {fmt.CATEGORIA[self.turno.categoria].upper()} vigente el día del turno: "
                             f"{fmt.pesos(self.precio_vigente)}.\nSi lo cambias, queda en el registro de cambios.")
        self._cobrar = ""
        self._texto_guardar = "Guardar ficha · listo para entregar" if self.nueva else "Guardar cambios"
        self._texto_cancelar = "Seguir atendiendo" if self.nueva else "Cancelar"
        self._validadores["precio"] = validar_monto
        self.cuenta(self._precio)

    servicios = propiedad("QVariantList", "servicios", cambioFicha)
    corte = propiedad(str, "corte", cambioFicha)
    observaciones = propiedad(str, "observaciones", cambioFicha)
    sesion = propiedad(str, "sesion", cambioFicha)
    precio = propiedad(str, "precio", cambioFicha)
    notaPrecio = propiedad(str, "nota_precio", cambioFicha)
    cobrar = propiedad(str, "cobrar", cambioFicha)
    textoGuardar = propiedad(str, "texto_guardar", cambioFicha)
    textoCancelar = propiedad(str, "texto_cancelar", cambioFicha)

    @Slot(str)
    def cuenta(self, texto: str) -> None:
        """Lo que se cobra al entregar: el precio final menos lo abonado."""
        self.validar("precio", texto)
        try:
            precio = fmt.leer_pesos(texto)
        except DatoInvalido:
            return
        cobrar = max(0, precio - self.turno.abono_total)
        self.poner(cobrar=f"Abono {fmt.pesos(self.turno.abono_total)}  ·  Cobrar al entregar {fmt.pesos(cobrar)}")

    @Slot("QVariantList", str, str, str, str, str)
    def guardar(self, marcados, corte: str, obs: str, porcentaje_texto: str, avance: str, precio_texto: str) -> None:
        if not self.validar("precio", precio_texto):
            return
        precio = fmt.leer_pesos(precio_texto)
        marcados = [str(s) for s in marcados]
        servicios = ", ".join(s["nombre"] for s in self._servicios if s["nombre"] in marcados)
        corte, obs, avance = corte.strip(), obs.strip(), avance.strip()
        pct_texto = porcentaje_texto.replace("%", "").strip()
        porcentaje = None
        if pct_texto:
            if not pct_texto.isdigit() or int(pct_texto) > 100:
                self.error_campo("porcentaje", "De 0 a 100")
                return
            porcentaje = int(pct_texto)
        self.error_campo("porcentaje", None)

        def guardar():
            ahora = self.ctx.ahora()
            with self.ctx.con() as con:
                if self.nueva:
                    if self.turno.estado is not EstadoTurno.EN_ATENCION:
                        agenda.iniciar_atencion(con, self.turno.id, ahora=ahora)
                    agenda.marcar_atendido(con, self.turno.id, ahora=ahora, servicios_realizados=servicios,
                                           detalles_corte=corte, observaciones=obs)
                    ficha = fichas.ficha_de_turno(con, self.turno.id)
                    if precio != ficha.precio_final:
                        ficha = fichas.editar_ficha(con, ficha.id, ahora=ahora, precio_final=precio)
                else:
                    cambios = {}
                    if servicios != self.ficha.servicios_realizados:
                        cambios["servicios_realizados"] = servicios
                    if corte != self.ficha.detalles_corte:
                        cambios["detalles_corte"] = corte
                    if obs != self.ficha.observaciones:
                        cambios["observaciones"] = obs
                    if precio != self.ficha.precio_final:
                        cambios["precio_final"] = precio
                    ficha = fichas.editar_ficha(con, self.ficha.id, ahora=ahora, **cambios) if cambios else self.ficha
                if avance or porcentaje is not None:
                    fichas.registrar_sesion_desenredado(con, ficha.id, ahora=ahora, avance=avance, porcentaje=porcentaje)
                return ficha

        if self.intentar(guardar):
            self.cerrar()
