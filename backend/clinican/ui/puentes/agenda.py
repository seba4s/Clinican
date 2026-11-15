"""Agenda del día: hoja tipo Excel con los turnos, pendientes de abono y panel del turno."""

from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import Signal, Slot

from clinican.dominio.abonos import vence_en
from clinican.dominio.cupos import CategoriaCupo
from clinican.dominio.estados import EstadoTurno, MotivoLiberacion
from clinican.servicios import agenda, clientes, configuracion, consultas, fichas, precios
from clinican.servicios.consultas import TurnoEnAgenda
from clinican.ui import formato as fmt
from clinican.ui import tema
from clinican.ui.puentes.base import Confirmacion, Pantalla, propiedad
from clinican.ui.tablero import ORDEN_CATEGORIAS, GrupoHora, agrupar, armar_tablero

E = EstadoTurno

PANEL_VACIO = {"vacio": True}


class PantallaAgenda(Pantalla):
    cambioAgenda = Signal()
    irAFila = Signal(int)

    def __init__(self, app):
        super().__init__(app)
        self.dia = self.ctx.hoy()
        self.seleccion: int | None = None
        self._turnos: dict[int, TurnoEnAgenda] = {}
        self._libres: list[tuple[datetime, CategoriaCupo]] = []
        self._lista_pendientes: list = []
        self._acciones_panel: list = []
        self._titulo_dia = ""
        self._resumen = ""
        self._pendientes: list[dict] = []
        self._pendientes_titulo = ""
        self._pendientes_mas = ""
        self._grupos: list[dict] = []
        self._cerrado = ""
        self._fuera = ""
        self._seleccionado = -1
        self._panel: dict = PANEL_VACIO

    tituloDia = propiedad(str, "titulo_dia", cambioAgenda)
    resumen = propiedad(str, "resumen", cambioAgenda)
    pendientes = propiedad("QVariantList", "pendientes", cambioAgenda)
    pendientesTitulo = propiedad(str, "pendientes_titulo", cambioAgenda)
    pendientesMas = propiedad(str, "pendientes_mas", cambioAgenda)
    grupos = propiedad("QVariantList", "grupos", cambioAgenda)
    cerrado = propiedad(str, "cerrado", cambioAgenda)
    fuera = propiedad(str, "fuera", cambioAgenda)
    seleccionado = propiedad(int, "seleccionado", cambioAgenda)
    panel = propiedad("QVariantMap", "panel", cambioAgenda)

    # ------------------------------------------------------------------ navegación por días
    @Slot()
    def dia_anterior(self) -> None:
        self.dia -= timedelta(days=1)
        self.seleccion = None
        self.refrescar()

    @Slot()
    def dia_siguiente(self) -> None:
        self.dia += timedelta(days=1)
        self.seleccion = None
        self.refrescar()

    @Slot()
    def ir_hoy(self) -> None:
        self.dia = self.ctx.hoy()
        self.seleccion = None
        self.refrescar()

    # ------------------------------------------------------------------ datos
    def refrescar(self, periodico: bool = False) -> None:
        ahora = self.ctx.ahora()
        hoy = self.ctx.hoy()
        with self.ctx.con() as con:
            filas, fuera, libres = armar_tablero(con, self.dia, ahora)
            pendientes = [p for p in consultas.pendientes_de_abono(con, ahora=ahora) if not p.vencido]
        titulo = fmt.dia_largo(self.dia)
        if self.dia == hoy:
            titulo = "Hoy, " + titulo[0].lower() + titulo[1:]
        turnos = [t for f in filas for lista in f.puestos.values() for t in lista if t]
        self._turnos = {t.turno.id: t for t in turnos + fuera}
        if not filas:
            resumen = "Cerrado"
        else:
            resumen = f"{len(turnos)} turno{'s' if len(turnos) != 1 else ''} · {libres} cupos libres"
        if self.seleccion not in self._turnos:
            self.seleccion = None
        if fuera:
            partes = [f"{t.mascota} ({tema.estilo_estado(t.turno.estado)[3].lower()}, {fmt.hora(t.turno.inicio)})"
                      for t in fuera]
            texto_fuera = "Fuera de agenda: " + " · ".join(partes)
        else:
            texto_fuera = ""
        self.poner(titulo_dia=titulo, resumen=resumen, cerrado="" if filas else "Este día la peluquería está cerrada.",
                   fuera=texto_fuera, grupos=self._hoja(agrupar(filas, ORDEN_CATEGORIAS), ahora),
                   seleccionado=self.seleccion if self.seleccion is not None else -1)
        self._datos_pendientes(pendientes, ahora)
        self._datos_panel()

    def refrescar_periodico(self) -> None:
        self.refrescar(periodico=True)

    def _hoja(self, grupos: list[GrupoHora], ahora: datetime) -> list[dict]:
        """Grupos de la hoja como datos simples para QML (la hora se combina por franja)."""
        self._libres = []
        datos = []
        for grupo in grupos:
            filas = []
            for fila in grupo.filas:
                if fila.tipo == "bloqueo":
                    filas.append({"tipo": "bloqueo", "texto": f"Bloqueado de {fmt.hora(fila.inicio)} a "
                                                              f"{fmt.hora(fila.hasta)} · {fila.texto}"})
                elif fila.tipo == "pasada":
                    filas.append({"tipo": "pasada"})
                elif fila.tipo == "libre":
                    # Cada cupo libre es una fila vacía de la tabla, lista para llenar.
                    for cat, n in fila.libres.items():
                        for _ in range(n):
                            filas.append({"tipo": "libre", "cupo": fmt.CATEGORIA[cat], "clave": len(self._libres)})
                            self._libres.append((fila.inicio, cat))
                else:
                    item = fila.item
                    turno = item.turno
                    if turno.faltante > 0:
                        abono = (f"{fmt.pesos(turno.abono_total)} de {fmt.pesos(turno.abono_requerido)}"
                                 if turno.abono_total else "Sin abono")
                    else:
                        abono = fmt.pesos(turno.abono_total)
                    _f, _l, _b, nombre, icono = tema.estilo_estado(turno.estado)
                    filas.append({
                        "tipo": "turno",
                        "id": turno.id,
                        "celdas": [fmt.CATEGORIA[turno.categoria], item.mascota, item.raza or "—",
                                   fmt.SERVICIO[turno.servicio], item.propietario, fmt.celular(item.celular), abono],
                        "estado": turno.estado.name,
                        "estadoTexto": f"{icono} {nombre}",
                        "atenuado": grupo.pasada and turno.estado is E.ENTREGADO,
                    })
            datos.append({
                "hora": fmt.hora(grupo.inicio),
                "actual": grupo.inicio <= ahora < grupo.inicio + timedelta(minutes=30),
                "pasada": grupo.pasada,
                "bloqueo": grupo.filas[0].tipo == "bloqueo",
                "filas": filas,
            })
        return datos

    def _datos_pendientes(self, pendientes, ahora) -> None:
        self._lista_pendientes = [p.turno for p in pendientes[:4]]
        n = len(pendientes)
        chips = []
        for i, p in enumerate(pendientes[:4]):
            chips.append({"indice": i, "texto": (
                f"{fmt.dia_corto(fmt.local(p.turno.inicio).date(), self.ctx.hoy())} {fmt.hora(p.turno.inicio)} · "
                f"{p.mascota} · {p.propietario}   {fmt.minutos_restantes(p.vence_en, ahora)}   "
                f"{fmt.pesos(p.turno.abono_total)} de {fmt.pesos(p.turno.abono_requerido)}")})
        self.poner(pendientes=chips,
                   pendientes_titulo=f"◷  Falta{'n' if n != 1 else ''} {n} abono{'s' if n != 1 else ''}" if n else "",
                   pendientes_mas=f"y {n - 4} más" if n > 4 else "")

    @Slot(int)
    def ir_a_pendiente(self, indice: int) -> None:
        self._ir_a_turno(self._lista_pendientes[indice])

    def _ir_a_turno(self, turno) -> None:
        self.dia = fmt.local(turno.inicio).date()
        self.seleccion = turno.id
        self.refrescar()
        self.irAFila.emit(turno.id)

    @Slot(int)
    def seleccionar(self, turno_id: int) -> None:
        """Marca el turno en la hoja y muestra su panel, sin volver a armar la hoja."""
        if turno_id not in self._turnos:
            self.refrescar()
            return
        self.seleccion = turno_id
        self.poner(seleccionado=turno_id)
        self._datos_panel()

    @Slot(int)
    def elegir_libre(self, clave: int) -> None:
        inicio, categoria = self._libres[clave]
        self.nuevo_turno(inicio=inicio, categoria=categoria)

    # ------------------------------------------------------------------ panel del turno
    def _datos_panel(self) -> None:
        item = self._turnos.get(self.seleccion) if self.seleccion is not None else None
        if item is None:
            self._acciones_panel = []
            self.poner(panel=PANEL_VACIO)
            return
        turno = item.turno
        ahora = self.ctx.ahora()
        with self.ctx.con() as con:
            mascota = clientes.obtener_mascota(con, turno.mascota_id)
            raza = clientes.obtener_raza(con, mascota.raza_id).nombre if mascota.raza_id else "Sin raza"
            dueno = clientes.obtener_propietario(con, turno.propietario_id)
            precio = precios.precio_en_fecha(con, turno.categoria, fmt.local(turno.inicio).date())
            ficha = fichas.ficha_de_turno(con, turno.id)
            minutos = configuracion.cargar(con).minutos_expiracion

        precio_final = ficha.precio_final if ficha else precio
        datos = [
            ["Servicio", fmt.SERVICIO[turno.servicio]],
            ["Precio", fmt.pesos(precio_final) + ("" if ficha else " (vigente)")],
            ["Abono", f"{fmt.pesos(turno.abono_total)} de {fmt.pesos(turno.abono_requerido)}"
                      + (f" (saldo {fmt.pesos(turno.saldo_aplicado)})" if turno.saldo_aplicado else "")],
            ["Saldo a favor", fmt.pesos(dueno.saldo_a_favor)],
        ]
        nota = ""
        if turno.estado is E.PENDIENTE_ABONO:
            limite = vence_en(turno.creado_en, minutos)
            nota = (f"Vence a las {fmt.hora(limite)} ({fmt.minutos_restantes(limite, ahora)}). "
                    "Si vence, el cupo se libera solo.")
        elif turno.estado is E.ATENDIDO and ficha:
            nota = f"Cobrar al entregar: {fmt.pesos(max(0, ficha.precio_final - turno.abono_total))}"
        elif turno.estado is E.INASISTENCIA:
            nota = f"Saldo a favor generado: {fmt.pesos(turno.saldo_generado)}"
        elif turno.estado in (E.CANCELADO, E.LIBERADO) and turno.saldo_generado:
            nota = f"Pasó al saldo a favor: {fmt.pesos(turno.saldo_generado)}"
        self._acciones_panel = self._acciones(turno, ficha)
        self.poner(panel={
            "vacio": False,
            "encabezado": f"{fmt.dia_corto(fmt.local(turno.inicio).date(), self.ctx.hoy())} {fmt.hora(turno.inicio)} · "
                          f"cupo {fmt.CATEGORIA[turno.categoria]}",
            "titulo": f"{item.mascota} · {raza}",
            "dueno": f"{dueno.nombre} · {fmt.celular(dueno.telefono)}",
            "estado": turno.estado.name,
            "datos": datos,
            "nota": nota,
            "acciones": [{"texto": texto, "tipo": tipo} for texto, _c, tipo in self._acciones_panel],
        })

    def _acciones(self, turno, ficha):
        t = turno.id
        if turno.estado is E.PENDIENTE_ABONO:
            return [("Registrar abono", lambda: self.registrar_abono(turno), "principal"),
                    ("Mover turno", lambda: self.mover(turno), "secundario"),
                    ("Liberar cupo…", lambda: self.liberar(turno), "peligro"),
                    ("Cancelar turno…", lambda: self.cancelar(turno), "peligro")]
        if turno.estado is E.CONFIRMADO:
            return [("Iniciar atención", lambda: self.ejecutar(lambda con: agenda.iniciar_atencion(con, t, ahora=self.ctx.ahora())), "principal"),
                    ("Mover turno", lambda: self.mover(turno), "secundario"),
                    ("Marcar inasistencia…", lambda: self.inasistencia(turno), "peligro"),
                    ("Cancelar turno…", lambda: self.cancelar(turno), "peligro")]
        if turno.estado is E.EN_ATENCION:
            return [("Marcar atendido y llenar ficha", lambda: self.ficha(turno), "principal")]
        if turno.estado is E.ATENDIDO:
            return [("Entregar", lambda: self.ejecutar(lambda con: agenda.marcar_entregado(con, t, ahora=self.ctx.ahora()),
                                                       "Entregado."), "principal"),
                    ("Ver ficha", lambda: self.ficha(turno), "secundario")]
        if turno.estado is E.ENTREGADO and ficha:
            return [("Ver ficha", lambda: self.ficha(turno), "secundario")]
        return []

    @Slot(int)
    def accion(self, indice: int) -> None:
        if 0 <= indice < len(self._acciones_panel):
            self._acciones_panel[indice][1]()

    # ------------------------------------------------------------------ acciones
    @Slot()
    def nuevo(self) -> None:
        self.nuevo_turno()

    def nuevo_turno(self, inicio: datetime | None = None, categoria: CategoriaCupo | None = None,
                    mascota_id: int | None = None) -> None:
        from clinican.ui.puentes.dialogos_turno import DialogoNuevoTurno

        def listo(turno) -> None:
            if turno:
                self._ir_a_turno(turno)
                estado = "confirmado" if turno.estado is E.CONFIRMADO else f"falta el abono ({fmt.pesos(turno.faltante)})"
                self.avisar(f"Turno agendado a las {fmt.hora(turno.inicio)}: {estado}.")
                self.app.actualizar_insignias()

        self.app.abrir(DialogoNuevoTurno(self, self.ctx, dia=fmt.local(inicio).date() if inicio else self.dia,
                                         inicio=inicio, categoria=categoria, mascota_id=mascota_id), listo)

    def registrar_abono(self, turno) -> None:
        from clinican.ui.puentes.dialogos_turno import DialogoAbono

        def listo(nuevo) -> None:
            if nuevo:
                self.avisar("Abono completo: turno confirmado." if nuevo.estado is E.CONFIRMADO
                            else f"Abono registrado. Falta {fmt.pesos(nuevo.faltante)}.")
            self.refrescar()

        self.app.abrir(DialogoAbono(self.ctx, turno), listo)

    def mover(self, turno) -> None:
        from clinican.ui.puentes.dialogos_turno import DialogoMover

        def listo(nuevo) -> None:
            if nuevo:
                self._ir_a_turno(nuevo)
                self.avisar(f"Turno movido a {fmt.momento(nuevo.inicio, self.ctx.hoy())}.")

        self.app.abrir(DialogoMover(self.ctx, turno), listo)

    def liberar(self, turno) -> None:
        def listo(si) -> None:
            if si:
                self.ejecutar(lambda con: agenda.liberar_turno(con, turno.id, MotivoLiberacion.OTRO,
                                                               ahora=self.ctx.ahora()), "Cupo liberado.")

        self.app.abrir(Confirmacion(self.ctx, "¿Liberar el cupo?", "El turno sale de la agenda y lo que el cliente "
                                    "ya había pagado queda como saldo a favor.", "Liberar cupo"), listo)

    def cancelar(self, turno) -> None:
        pagado = turno.abono_total
        texto = "El turno sale de la agenda."
        if pagado:
            texto += f" Lo pagado ({fmt.pesos(pagado)}) queda como saldo a favor del cliente."

        def listo(si) -> None:
            if si:
                self.ejecutar(lambda con: agenda.cancelar_turno(con, turno.id, ahora=self.ctx.ahora()),
                              "Turno cancelado.")

        self.app.abrir(Confirmacion(self.ctx, "¿Cancelar el turno?", texto, "Cancelar turno"), listo)

    def inasistencia(self, turno) -> None:
        from clinican.ui.puentes.dialogos_turno import DialogoInasistencia

        def listo(resultado) -> None:
            if resultado:
                self.avisar("Inasistencia registrada.")
            self.refrescar()

        self.app.abrir(DialogoInasistencia(self.ctx, turno), listo)

    def ficha(self, turno) -> None:
        from clinican.ui.puentes.dialogo_ficha import DialogoFicha

        def listo(resultado) -> None:
            if resultado:
                self.avisar("Ficha guardada. El turno está listo para entregar."
                            if turno.estado is E.EN_ATENCION else "Ficha actualizada.")
            self.refrescar()

        self.app.abrir(DialogoFicha(self.ctx, turno.id), listo)

    @Slot()
    def bloquear(self) -> None:
        from clinican.ui.puentes.dialogos_turno import DialogoBloqueo

        def listo(resultado) -> None:
            if resultado:
                self.avisar("Horas bloqueadas.")
            self.refrescar()

        self.app.abrir(DialogoBloqueo(self.ctx, self.dia), listo)
