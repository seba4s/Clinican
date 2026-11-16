"""Ajustes: horario y bloqueos, cupos y abono, precios, razas, recordatorios, respaldos y registro."""

from __future__ import annotations

from datetime import timedelta

from PySide6.QtCore import Property, Signal, Slot

from clinican.dominio.agenda import HorarioSemanal, Jornada
from clinican.dominio.cupos import CategoriaCupo, CuposPorFranja, Tamano
from clinican.dominio.errores import DatoInvalido
from clinican.servicios import agenda, auditoria, clientes, configuracion, precios, respaldos
from interfaz import formato as fmt
from interfaz.formato import leer_hora
from interfaz.puentes.base import Confirmacion, Dialogo, Pantalla, propiedad

SECCIONES = ("Horario y bloqueos", "Cupos y abono", "Precios", "Razas", "Recordatorios y WhatsApp",
             "Respaldos", "Registro de cambios")
HORAS = [f"{h:02d}:{m:02d}" for h in range(6, 21) for m in (0, 30)]
CANALES = [("archivo", "Archivo de texto"), ("whatsapp", "WhatsApp"), ("consola", "Consola (pruebas)")]


def _entero(texto: str, nombre: str, minimo: int = 0) -> int:
    limpio = texto.replace(".", "").replace("$", "").strip()
    if not limpio.isdigit() or int(limpio) < minimo:
        raise DatoInvalido(f"{nombre}: escribe un número entero{' mayor que cero' if minimo else ''}.")
    return int(limpio)


class PantallaAjustes(Pantalla):
    cambioAjustes = Signal()

    def __init__(self, app):
        super().__init__(app)
        self._seccion = SECCIONES[0]
        self._titulo_seccion = ""
        self._explicacion = ""
        self._datos: dict = {}
        self._errores: dict[str, str] = {}
        self._copias: dict[str, object] = {}
        self._precios: dict[str, list] = {}

    seccion = propiedad(str, "seccion", cambioAjustes)
    tituloSeccion = propiedad(str, "titulo_seccion", cambioAjustes)
    explicacion = propiedad(str, "explicacion", cambioAjustes)
    datos = propiedad("QVariantMap", "datos", cambioAjustes)
    errores = propiedad("QVariantMap", "errores", cambioAjustes)

    @Property("QVariantList", constant=True)
    def secciones(self) -> list[str]:
        return list(SECCIONES)

    @Property("QVariantList", constant=True)
    def horas(self) -> list[str]:
        return list(HORAS)

    @Slot(str)
    def ir(self, seccion: str) -> None:
        self.poner(seccion=seccion, errores={})
        self.refrescar()

    def refrescar_periodico(self) -> None:
        pass

    def refrescar(self) -> None:
        {
            "Horario y bloqueos": self._horario,
            "Cupos y abono": self._cupos,
            "Precios": self._datos_precios,
            "Razas": self._razas,
            "Recordatorios y WhatsApp": self._recordatorios,
            "Respaldos": self._respaldos,
            "Registro de cambios": self._registro,
        }[self._seccion]()

    def _titulo(self, titulo: str, explicacion: str, **datos) -> None:
        self.poner(titulo_seccion=titulo, explicacion=explicacion, datos=datos)

    def _guardar_config(self, pares: list[tuple[str, object]], exito: str) -> None:
        def guardar(con):
            for nombre, valor in pares:
                configuracion.guardar(con, nombre, valor, ahora=self.ctx.ahora())
        self.ejecutar(guardar, exito)

    # ------------------------------------------------------------------ horario y bloqueos
    def _horario(self) -> None:
        with self.ctx.con() as con:
            cfg = configuracion.cargar(con)
            hoy = self.ctx.hoy()
            proximos = []
            for i in range(60):
                dia = hoy + timedelta(days=i)
                proximos += agenda.bloqueos_del_dia(con, dia)
        dias = []
        for d in range(7):
            jornada = cfg.horario.dias.get(d)
            dias.append({"dia": d, "nombre": fmt.DIAS[d].capitalize(), "abierto": jornada is not None,
                         "desde": jornada.apertura.strftime("%H:%M") if jornada else "09:00",
                         "hasta": jornada.ultima_franja.strftime("%H:%M") if jornada else "16:30"})
        bloqueos = []
        for b in proximos:
            horas = "todo el día" if b.dia_completo else f"{b.desde.strftime('%H:%M')} a {b.hasta.strftime('%H:%M')}"
            bloqueos.append({"id": b.id, "texto": f"{fmt.dia_largo(b.fecha)} · {horas} · {b.motivo or 'sin motivo'}"})
        self._titulo("Horario y bloqueos", "Horas en que se reciben perros. La última franja es la última hora a la que "
                                           "puede empezar un turno (cada franja dura 30 minutos).",
                     dias=dias, bloqueos=bloqueos)

    @Slot("QVariantList")
    def guardar_horario(self, filas) -> None:
        """``filas``: una por día (lunes primero) con ``abierto``, ``desde`` y ``hasta``."""
        dias = {}
        for d, fila in enumerate(filas):
            if not fila["abierto"]:
                dias[d] = None
                continue
            try:
                dias[d] = Jornada(leer_hora(str(fila["desde"])), leer_hora(str(fila["hasta"])))
            except (DatoInvalido, ValueError) as e:
                self.avisar(f"Revisa el {fmt.DIAS[d]}: {e}.", error=True)
                return
        self._guardar_config([("horario", HorarioSemanal(dias))], "Horario guardado.")

    @Slot()
    def nuevo_bloqueo(self) -> None:
        from interfaz.puentes.dialogos_turno import DialogoBloqueo

        def listo(resultado) -> None:
            if resultado:
                self.avisar("Horas bloqueadas.")
            self.refrescar()

        self.app.abrir(DialogoBloqueo(self.ctx, self.ctx.hoy()), listo)

    @Slot(int)
    def quitar_bloqueo(self, bloqueo_id: int) -> None:
        self.ejecutar(lambda con: agenda.quitar_bloqueo(con, bloqueo_id, ahora=self.ctx.ahora()), "Bloqueo quitado.")

    # ------------------------------------------------------------------ cupos y abono
    def _cupos(self) -> None:
        with self.ctx.con() as con:
            cfg = configuracion.cargar(con)
        self._titulo("Cupos y abono", "Cuántos perros de cada categoría caben en una misma franja de 30 minutos, "
                                      "y cuánto se pide de abono para separar el turno.",
                     categorias=[{"valor": c.value, "nombre": fmt.CATEGORIA[c], "cantidad": str(cfg.cupos.capacidad(c))}
                                 for c in CategoriaCupo],
                     abono=fmt.pesos(cfg.abono), minutos=str(cfg.minutos_expiracion))

    @Slot("QVariantMap", str, str)
    def guardar_cupos(self, cantidades, abono: str, minutos: str) -> None:
        try:
            cupos = CuposPorFranja(**{c.value: _entero(str(cantidades[c.value]), fmt.CATEGORIA[c]) for c in CategoriaCupo})
            valor_abono = fmt.leer_pesos(abono)
            mins = _entero(minutos, "Minutos", 1)
        except (DatoInvalido, TypeError, ValueError) as e:
            self.avisar(str(e), error=True)
            return
        self._guardar_config([("cupos", cupos), ("abono", valor_abono), ("minutos_expiracion", mins)],
                             "Cupos y abono guardados.")

    # ------------------------------------------------------------------ precios
    def _datos_precios(self) -> None:
        hoy = self.ctx.hoy()
        with self.ctx.con() as con:
            vigentes = precios.precios_vigentes(con, hoy)
            historial = {c: precios.historial_precios(con, c) for c in CategoriaCupo}
        filas = []
        self._precios = {}
        for cat in CategoriaCupo:
            lista = sorted(historial[cat], key=lambda p: p.vigente_desde, reverse=True)[:4]
            self._precios[cat.value] = lista
            filas.append({"categoria": cat.value, "nombre": fmt.CATEGORIA[cat], "hoy": fmt.pesos(vigentes[cat]),
                          "historial": [{"indice": i, "futuro": p.vigente_desde > hoy,
                                         "texto": f"{fmt.pesos(p.valor)} desde {fmt.fecha_numerica(p.vigente_desde)}"
                                                  + ("  (próximo)" if p.vigente_desde > hoy else "")}
                                        for i, p in enumerate(lista)]})
        self._titulo("Precios", "Un precio nuevo rige desde la fecha que elijas; los turnos anteriores conservan el suyo. "
                                "«Corregir» cambia un valor ya registrado y queda en el registro de cambios.", precios=filas)

    @Slot(str, int)
    def precio(self, categoria: str, indice: int = -1) -> None:
        cat = CategoriaCupo(categoria)
        existente = self._precios[categoria][indice] if indice >= 0 else None

        def listo(resultado) -> None:
            if resultado:
                self.avisar("Precio guardado.")
            self.refrescar()

        self.app.abrir(DialogoPrecio(self.ctx, cat, existente), listo)

    # ------------------------------------------------------------------ razas
    def _razas(self) -> None:
        with self.ctx.con() as con:
            razas = clientes.buscar_razas(con)
        self._titulo("Razas", "El tamaño de la raza se propone al crear una mascota; siempre se puede cambiar en la mascota.",
                     razas=[{"id": r.id, "nombre": r.nombre, "tamano": fmt.TAMANO[r.tamano] if r.tamano else "—",
                             "pelaje": r.pelaje or "—"} for r in razas])

    @Slot(int)
    def raza(self, raza_id: int = -1) -> None:
        raza = None
        if raza_id >= 0:
            with self.ctx.con() as con:
                raza = next((r for r in clientes.buscar_razas(con) if r.id == raza_id), None)

        def listo(resultado) -> None:
            if resultado:
                self.avisar("Raza guardada.")
            self.refrescar()

        self.app.abrir(DialogoRaza(self.ctx, raza), listo)

    # ------------------------------------------------------------------ recordatorios
    def _recordatorios(self) -> None:
        with self.ctx.con() as con:
            cfg = configuracion.cargar(con)
        self._titulo("Recordatorios y WhatsApp", "Por dónde salen los recordatorios y con cuánta anticipación "
                                                 "(0 apaga ese recordatorio). El cambio de canal se aplica la "
                                                 "próxima vez que abras Clinican.",
                     canal=cfg.canal_notificaciones, horas=str(cfg.horas_antes_recordatorio),
                     horasFinal=str(cfg.horas_antes_recordatorio_final),
                     canales=[{"valor": v, "texto": t} for v, t in CANALES])

    @Slot(str, str, str)
    def guardar_recordatorios(self, canal: str, horas: str, horas_final: str) -> None:
        errores = {}
        valores = {}
        for clave, texto, nombre in (("horas", horas, "Primer recordatorio"),
                                     ("horasFinal", horas_final, "Último recordatorio")):
            try:
                valores[clave] = _entero(texto, nombre)
            except DatoInvalido as e:
                errores[clave] = str(e)
        self.poner(errores=errores)
        if errores:
            return
        self._guardar_config([("canal_notificaciones", canal),
                              ("horas_antes_recordatorio", valores["horas"]),
                              ("horas_antes_recordatorio_final", valores["horasFinal"])],
                             "Guardado. El canal nuevo se usa desde el próximo inicio.")

    # ------------------------------------------------------------------ respaldos
    def _respaldos(self) -> None:
        with self.ctx.con() as con:
            cfg = configuracion.cargar(con)
        carpeta = respaldos.carpeta_de(self.ctx.ruta_db, cfg.carpeta_respaldos)
        copias = list(reversed(respaldos.listar_respaldos(carpeta)))
        self._copias = {c.name: c for c in copias}
        self._titulo("Respaldos", f"Se hace uno cada día y otro al cerrar Clinican, y se guardan los últimos "
                                  f"{cfg.respaldos_a_conservar}. Carpeta: {carpeta}",
                     ultimo=f"Último: {copias[0].name}" if copias else "",
                     copias=[{"nombre": c.name, "tamano": f"{c.stat().st_size // 1024} KB"} for c in copias])

    @Slot()
    def respaldar(self) -> None:
        try:
            copia = respaldos.crear_respaldo(self.ctx.ruta_db, ahora=self.ctx.ahora())
        except Exception as e:
            self.avisar(f"No se pudo respaldar: {e}", error=True)
            return
        self.avisar(f"Respaldo creado y verificado: {copia.name}")
        self.refrescar()

    @Slot(str)
    def restaurar(self, nombre: str) -> None:
        copia = self._copias[nombre]

        def listo(si) -> None:
            if not si:
                return
            try:
                previa = respaldos.restaurar(self.ctx.ruta_db, copia, ahora=self.ctx.ahora())
            except Exception as e:
                self.avisar(f"No se pudo restaurar: {e}", error=True)
                return
            self.avisar(f"Base restaurada. La anterior quedó guardada como {previa.name}.")
            for pantalla in self.app.pantallas.values():
                if pantalla is not self:
                    pantalla.refrescar()
            self.refrescar()

        self.app.abrir(Confirmacion(self.ctx, f"¿Restaurar {copia.name}?",
                                    "Todo lo que se registró después de esa copia se reemplaza. Antes de restaurar se "
                                    "guarda una copia de la base actual, por si necesitas volver.", "Restaurar",
                                    no="No restaurar"), listo)

    # ------------------------------------------------------------------ registro
    def _registro(self) -> None:
        with self.ctx.con() as con:
            registros = auditoria.historial(con)
        registros = sorted(registros, key=lambda r: r.cuando, reverse=True)[:200]
        hoy = self.ctx.hoy()
        filas = []
        for reg in registros:
            detalle = ", ".join(f"{k}: {v}" for k, v in reg.detalle.items() if v not in (None, ""))
            filas.append([fmt.momento(reg.cuando, hoy),
                          f"{reg.accion} {reg.entidad}" + (f" {reg.entidad_id}" if reg.entidad_id else ""),
                          detalle[:220]])
        self._titulo("Registro de cambios", "Cada cambio queda anotado con su fecha. Se muestran los 200 más recientes.",
                     cambios=filas)


class DialogoPrecio(Dialogo):
    cambioPrecio = Signal()
    vista = "DialogoPrecio.qml"

    def __init__(self, ctx, cat: CategoriaCupo, existente=None):
        corregir = existente is not None
        super().__init__(ctx, f"{'Corregir' if corregir else 'Cambiar'} precio de {fmt.CATEGORIA[cat]}", ancho=440,
                         subtitulo=(f"Vigente desde {fmt.fecha_numerica(existente.vigente_desde)}." if corregir else
                                    "El precio nuevo rige desde la fecha que escribas."))
        self.cat = cat
        self.existente = existente
        self._corregir = corregir
        self._valor = fmt.pesos(existente.valor) if corregir else ""
        self._desde = fmt.fecha_numerica(ctx.hoy() + timedelta(days=1))

    corregir = propiedad(bool, "corregir", cambioPrecio)
    valor = propiedad(str, "valor", cambioPrecio)
    desde = propiedad(str, "desde", cambioPrecio)

    @Slot(str, str)
    def guardar(self, valor: str, desde: str) -> None:
        try:
            v = fmt.leer_pesos(valor)
            fecha = self.existente.vigente_desde if self._corregir else fmt.leer_fecha(desde)
        except DatoInvalido as e:
            self.error(str(e))
            return

        def accion():
            with self.ctx.con() as con:
                if self._corregir:
                    return precios.editar_precio(con, self.cat, fecha, v, ahora=self.ctx.ahora())
                return precios.cambiar_precio(con, self.cat, v, fecha, ahora=self.ctx.ahora())

        if self.intentar(accion):
            self.cerrar()


class DialogoRaza(Dialogo):
    cambioRaza = Signal()
    vista = "DialogoRaza.qml"

    def __init__(self, ctx, raza=None):
        super().__init__(ctx, f"Editar {raza.nombre}" if raza else "Raza nueva", ancho=460)
        self.raza = raza
        self._opciones = ["Sin definir"] + [fmt.TAMANO[t].capitalize() for t in Tamano]
        self._tamano = fmt.TAMANO[raza.tamano].capitalize() if raza and raza.tamano else "Sin definir"
        self._inicial = {"nombre": raza.nombre if raza else "", "pelaje": (raza.pelaje or "") if raza else "",
                         "editar": raza is not None}

    opciones = propiedad("QVariantList", "opciones", cambioRaza)
    tamano = propiedad(str, "tamano", cambioRaza)
    inicial = propiedad("QVariantMap", "inicial")

    @Slot(str)
    def elegir_tamano(self, valor: str) -> None:
        self.poner(tamano=valor)

    @Slot(str, str)
    def guardar(self, nombre: str, pelaje: str) -> None:
        t = next((t for t in Tamano if fmt.TAMANO[t].capitalize() == self._tamano), None)
        nombre, pelaje = nombre.strip(), pelaje.strip()

        def accion():
            with self.ctx.con() as con:
                if self.raza:
                    return clientes.editar_raza(con, self.raza.id, ahora=self.ctx.ahora(), nombre=nombre,
                                                tamano=t, pelaje=pelaje)
                return clientes.crear_raza(con, nombre, t, pelaje, ahora=self.ctx.ahora())

        if self.intentar(accion):
            self.cerrar()

    @Slot()
    def baja(self) -> None:
        def accion():
            with self.ctx.con() as con:
                return clientes.desactivar_raza(con, self.raza.id, ahora=self.ctx.ahora())

        if self.intentar(accion):
            self.cerrar()
