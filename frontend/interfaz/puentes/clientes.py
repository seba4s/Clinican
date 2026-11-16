"""Clientes: búsqueda, ficha del propietario, mascotas, historial, unir duplicados e importar Excel."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from PySide6.QtCore import QUrl, Signal, Slot

from clinican.dominio.cupos import Servicio, Tamano, categoria_de_cupo
from clinican.dominio.documentos import fecha_nacimiento_aproximada
from clinican.dominio.errores import DatoInvalido
from clinican.dominio.estados import EstadoTurno
from clinican.servicios import agenda, autorizaciones, clientes, consultas
from interfaz import formato as fmt
from interfaz import tema
from interfaz.busqueda import buscar_clientes
from interfaz.puentes.base import Dialogo, Informacion, Pantalla, propiedad

E = EstadoTurno

DETALLE_VACIO = {"vacio": True}


def _validar_celular(texto: str) -> str | None:
    d = "".join(ch for ch in texto if ch.isdigit())
    if len(d) != 10:
        return f"El celular tiene 10 dígitos ({len(d)} escritos)."
    return None


def _validar_cedula(texto: str) -> str | None:
    return None if any(ch.isdigit() for ch in texto) else "La cédula es obligatoria."


class PantallaClientes(Pantalla):
    cambioClientes = Signal()
    limpiarBusqueda = Signal()

    def __init__(self, app):
        super().__init__(app)
        self.seleccion: int | None = None
        self.texto = ""
        self._cuenta = ""
        self._lista: list[dict] = []
        self._seleccionado = -1
        self._detalle: dict = DETALLE_VACIO
        self._propietario = None

    cuenta = propiedad(str, "cuenta", cambioClientes)
    lista = propiedad("QVariantList", "lista", cambioClientes)
    seleccionado = propiedad(int, "seleccionado", cambioClientes)
    detalle = propiedad("QVariantMap", "detalle", cambioClientes)

    def refrescar(self) -> None:
        self._listar()
        self._datos_detalle()

    def refrescar_periodico(self) -> None:
        pass

    # ------------------------------------------------------------------ lista
    @Slot(str)
    def buscar(self, texto: str) -> None:
        self.texto = texto.strip()
        self._listar()

    def _listar(self) -> None:
        texto = self.texto
        with self.ctx.con() as con:
            encontrados = buscar_clientes(con, texto, limite=200) if texto else clientes.buscar_propietarios(con)[:200]
            mascotas = {p.id: [m.nombre for m in clientes.buscar_mascotas(con, propietario_id=p.id)] for p in encontrados}
        repetidos = Counter(p.telefono for p in encontrados)
        lista = []
        for p in encontrados:
            duplicado = repetidos[p.telefono] > 1
            linea2 = ("Posible duplicado · " if duplicado else ", ".join(mascotas[p.id]) + " · ") + fmt.celular(p.telefono)
            lista.append({"id": p.id, "nombre": p.nombre, "linea2": linea2})
        self.poner(cuenta=f"{len(encontrados)} cliente{'s' if len(encontrados) != 1 else ''} · Ctrl+F", lista=lista,
                   seleccionado=self.seleccion if self.seleccion is not None else -1)

    @Slot(int)
    def elegir(self, propietario_id: int) -> None:
        self.seleccion = propietario_id
        self.refrescar()

    @Slot()
    def cerrar(self) -> None:
        self.seleccion = None
        self.refrescar()

    # ------------------------------------------------------------------ detalle
    def _datos_detalle(self) -> None:
        if self.seleccion is None:
            self._propietario = None
            self.poner(detalle=DETALLE_VACIO)
            return
        hoy = self.ctx.hoy()
        with self.ctx.con() as con:
            p = clientes.obtener_propietario(con, self.seleccion)
            mascotas = clientes.buscar_mascotas(con, propietario_id=p.id)
            razas = {m.raza_id: clientes.obtener_raza(con, m.raza_id) for m in mascotas if m.raza_id}
            historial = []
            for m in mascotas:
                historial += [(t, f, m) for t, f in consultas.historial_de_mascota(con, m.id)]
            inasist = agenda.inasistencias_de_propietario(con, p.id)
            autorizacion = autorizaciones.autorizacion_vigente(con, p.id)
        historial.sort(key=lambda x: x[0].inicio, reverse=True)
        self._propietario = p

        ultima = next((t for t, _f, _m in historial if t.estado in (E.ATENDIDO, E.ENTREGADO)), None)
        sin_aviso = [t for t in inasist if t.saldo_generado == 0]
        metricas = [
            ("Saldo a favor", fmt.pesos(p.saldo_a_favor), "Se usa en el próximo turno" if p.saldo_a_favor else "Sin saldo"),
            ("Última visita", fmt.dia_corto(fmt.local(ultima.inicio).date(), hoy) if ultima else "—",
             next((m.nombre for t, _f, m in historial if t is ultima), "") if ultima else "Aún no ha venido"),
            ("Inasistencias", str(len(inasist)), f"{len(sin_aviso)} sin aviso (abono perdido)" if sin_aviso else "Ninguna sin aviso"),
            ("Datos personales", "Autorizó" if autorizacion else "Sin autorización",
             f"Desde el {fmt.fecha_numerica(autorizacion.fecha)}" if autorizacion else "Ley 1581: márcala en Editar"),
        ]
        lista_mascotas = []
        for m in mascotas:
            raza = razas.get(m.raza_id)
            cat = categoria_de_cupo(raza.nombre if raza else None, m.tamano, m.pelaje, Servicio.CORTE_MAQUINA, m.complicado)
            detalle = f"{raza.nombre if raza else 'Sin raza'} · {fmt.TAMANO[m.tamano]}"
            if m.fecha_nacimiento:
                detalle += f" · {max(0, (hoy - m.fecha_nacimiento).days // 365)} años aprox."
            if m.complicado:
                detalle += " · pelaje complicado"
            lista_mascotas.append({"id": m.id, "nombre": m.nombre, "cupo": f"CUPO {fmt.CATEGORIA[cat].upper()}",
                                   "detalle": detalle, "obs": m.observaciones or ""})
        filas = []
        for t, f, m in historial[:60]:
            nombre_estado = tema.estilo_estado(t.estado)[3]
            if t.estado is E.INASISTENCIA:
                nombre_estado += " con aviso" if t.saldo_generado else " sin aviso"
            elif t.estado in (E.CANCELADO, E.LIBERADO) and t.saldo_generado:
                nombre_estado += f" · {fmt.pesos(t.saldo_generado)} a favor"
            filas.append({"fecha": fmt.momento(t.inicio, hoy), "mascota": m.nombre, "servicio": fmt.SERVICIO[t.servicio],
                          "estado": nombre_estado, "alerta": t.estado in (E.PENDIENTE_ABONO, E.INASISTENCIA),
                          "precio": fmt.pesos(f.precio_final) if f else "", "turnoId": t.id})
        self.poner(detalle={
            "vacio": False,
            "nombre": p.nombre,
            "linea": f"{fmt.cedula(p.cedula)} · {fmt.celular(p.telefono)}" + (f" · {p.direccion}" if p.direccion else ""),
            "primera": mascotas[0].id if len(mascotas) == 1 else 0,
            "metricas": [{"titulo": a, "valor": b, "nota": c} for a, b, c in metricas],
            "mascotas": lista_mascotas,
            "historial": filas,
        })

    # ------------------------------------------------------------------ acciones
    @Slot()
    def nuevo_turno_cliente(self) -> None:
        primera = self._detalle.get("primera") if not self._detalle.get("vacio") else 0
        if primera:
            self.app.nuevo_turno(mascota_id=primera)
        else:
            self.avisar("Elige la mascota con su botón «Turno», o agrégale una mascota primero.", error=True)

    @Slot(int)
    def turno_mascota(self, mascota_id: int) -> None:
        self.app.nuevo_turno(mascota_id=mascota_id)

    @Slot()
    def nuevo(self) -> None:
        self.nuevo_cliente()

    def nuevo_cliente(self, texto: str = "") -> None:
        def listo(nuevo) -> None:
            if nuevo:
                self.seleccion = nuevo.id
                self.texto = ""
                self.limpiarBusqueda.emit()
                self.avisar(f"Cliente {nuevo.nombre} creado. Agrégale su mascota.")
                self.refrescar()
                self.mascota(nuevo.id)

        self.app.abrir(DialogoCliente(self.ctx, None, texto), listo)

    @Slot()
    def editar(self) -> None:
        p = self._propietario

        def listo(resultado) -> None:
            if resultado:
                self.avisar("Datos guardados.")
                self.refrescar()

        self.app.abrir(DialogoCliente(self.ctx, p), listo)

    @Slot()
    def nueva_mascota(self) -> None:
        self.mascota(self._propietario.id)

    @Slot(int)
    def editar_mascota(self, mascota_id: int) -> None:
        with self.ctx.con() as con:
            m = clientes.obtener_mascota(con, mascota_id)
        self.mascota(m.propietario_id, m)

    def mascota(self, propietario_id: int, m=None) -> None:
        def listo(resultado) -> None:
            if resultado:
                self.avisar("Mascota guardada.")
                self.refrescar()

        self.app.abrir(DialogoMascota(self.ctx, propietario_id, m), listo)

    @Slot(int)
    def ver_ficha(self, turno_id: int) -> None:
        from interfaz.puentes.dialogo_ficha import DialogoFicha

        def listo(resultado) -> None:
            if resultado:
                self.avisar("Ficha actualizada.")
                self.refrescar()

        self.app.abrir(DialogoFicha(self.ctx, turno_id), listo)

    @Slot()
    def unir(self) -> None:
        def listo(resultado) -> None:
            if resultado:
                self.avisar("Clientes unidos.")
                self.refrescar()

        self.app.abrir(DialogoUnir(self.ctx, self._propietario), listo)

    @Slot(result=bool)
    def puede_importar(self) -> bool:
        if self.ctx.importar_excel is None:
            self.avisar("La importación desde Excel no está disponible.", error=True)
            return False
        return True

    @Slot(str)
    def importar(self, archivo: str) -> None:
        """``archivo``: ruta o URL ``file:`` que entrega el selector de archivos."""
        if not self.puede_importar() or not archivo:
            return
        ruta = Path(QUrl(archivo).toLocalFile()) if archivo.startswith("file:") else Path(archivo)
        try:
            with self.ctx.con() as con:
                informe = self.ctx.importar_excel(con, ruta, self.ctx.ahora())
        except Exception as e:  # archivo dañado, hoja faltante, etc.
            self.avisar(f"No se pudo leer el archivo: {e}", error=True)
            return
        detalle = "\n".join(f"Fila {r.fila}: {r.motivo}" for r in informe.rechazadas)
        self.app.abrir(Informacion(self.ctx, "Importación terminada",
                                   f"{len(informe.aceptadas)} filas aceptadas, {len(informe.rechazadas)} rechazadas.",
                                   detalle), lambda _r: self.refrescar())


class DialogoCliente(Dialogo):
    cambioCliente = Signal()
    vista = "DialogoCliente.qml"

    def __init__(self, ctx, p=None, texto: str = ""):
        super().__init__(ctx, "Editar cliente" if p else "Cliente nuevo", ancho=520)
        self.p = p
        digitos = "".join(ch for ch in texto if ch.isdigit())
        self.autorizacion = None
        if p:
            with ctx.con() as con:
                self.autorizacion = autorizaciones.autorizacion_vigente(con, p.id)
        fecha = self.autorizacion.fecha if self.autorizacion else ctx.hoy()
        self._inicial = {
            "nombre": p.nombre if p else ("" if digitos else texto),
            "cedula": (p.cedula or "") if p else (digitos if len(digitos) != 10 else ""),
            "celular": fmt.celular(p.telefono) if p else (digitos if len(digitos) == 10 else ""),
            "direccion": (p.direccion or "") if p else "",
            "autorizo": self.autorizacion is not None,
            "fecha": fmt.fecha_numerica(fecha),
            "medio": self.autorizacion.medio if self.autorizacion else "",
        }
        self._validadores.update(cedula=_validar_cedula, celular=_validar_celular)

    inicial = propiedad("QVariantMap", "inicial")

    @Slot(str, str, str, str, bool, str, str)
    def guardar(self, nombre: str, cedula: str, celular: str, direccion: str, autorizo: bool,
                fecha_texto: str, medio: str) -> None:
        nombre, cedula, direccion = nombre.strip(), cedula.strip(), direccion.strip()
        fecha_texto, medio = fecha_texto.strip(), medio.strip()
        ok = all([self.validar("cedula", cedula), self.validar("celular", celular)])
        self.error_campo("nombre", None if nombre else "Escribe el nombre.")
        if not nombre:
            ok = False
        if not ok:
            return
        celular = "".join(ch for ch in celular if ch.isdigit())
        ahora = self.ctx.ahora()
        cambia_autorizacion = autorizo != (self.autorizacion is not None) or (
            autorizo and self.autorizacion is not None and (
                fecha_texto != fmt.fecha_numerica(self.autorizacion.fecha) or medio != self.autorizacion.medio))
        fecha_autorizacion = None
        if cambia_autorizacion:
            try:
                fecha_autorizacion = fmt.leer_fecha(fecha_texto)
            except DatoInvalido as e:
                self.error_campo("fecha", str(e))
                return
            if fecha_autorizacion > self.ctx.hoy():
                self.error_campo("fecha", "La fecha no puede ser posterior a hoy.")
                return
            self.error_campo("fecha", None)

        def guardar():
            with self.ctx.con() as con:
                if self.p:
                    propietario = clientes.editar_propietario(con, self.p.id, ahora=ahora, nombre=nombre,
                                                              telefono=celular, cedula=cedula, direccion=direccion)
                else:
                    propietario = clientes.crear_propietario(con, nombre, celular, cedula=cedula, ahora=ahora,
                                                             direccion=direccion)
                if cambia_autorizacion:
                    registrar = (autorizaciones.registrar_autorizacion if autorizo
                                 else autorizaciones.revocar_autorizacion)
                    registrar(con, propietario.id, fecha_autorizacion, ahora=ahora, medio=medio)
                return propietario

        if self.intentar(guardar):
            self.cerrar()


class DialogoMascota(Dialogo):
    cambioMascota = Signal()
    vista = "DialogoMascota.qml"

    def __init__(self, ctx, propietario_id: int, m=None):
        super().__init__(ctx, f"Editar a {m.nombre}" if m else "Mascota nueva", ancho=560)
        self.m = m
        self.propietario_id = propietario_id
        with ctx.con() as con:
            self.razas = clientes.buscar_razas(con)
        self._nombres_razas = ["Sin raza"] + [r.nombre for r in self.razas]
        self._tamanos = [fmt.TAMANO[t].capitalize() for t in Tamano]
        self._inicial = {
            "nombre": m.nombre if m else "",
            "raza": next((r.nombre for r in self.razas if m and r.id == m.raza_id), "Sin raza"),
            "complicado": bool(m and m.complicado),
            "observaciones": (m.observaciones or "") if m else "",
            "nueva": m is None,
        }
        self._tamano = fmt.TAMANO[m.tamano].capitalize() if m else "Mediano"

    nombresRazas = propiedad("QVariantList", "nombres_razas", cambioMascota)
    tamanos = propiedad("QVariantList", "tamanos", cambioMascota)
    tamano = propiedad(str, "tamano", cambioMascota)
    inicial = propiedad("QVariantMap", "inicial")

    @Slot(str)
    def elegir_tamano(self, valor: str) -> None:
        self.poner(tamano=valor)

    @Slot(str)
    def raza_cambio(self, nombre: str) -> None:
        r = next((r for r in self.razas if r.nombre == nombre), None)
        if r and r.tamano:
            self.poner(tamano=fmt.TAMANO[r.tamano].capitalize())

    @Slot(str, str, bool, str, str)
    def guardar(self, nombre: str, raza_texto: str, complicado: bool, edad: str, observaciones: str) -> None:
        nombre, raza_texto, edad = nombre.strip(), raza_texto.strip(), edad.strip()
        if not nombre:
            self.error_campo("nombre", "Escribe el nombre.")
            return
        self.error_campo("nombre", None)
        raza = next((r for r in self.razas if r.nombre == raza_texto), None)
        if raza_texto not in ("Sin raza", "") and raza is None:
            self.error("Elige una raza de la lista (las razas nuevas se agregan en Ajustes › Razas).")
            return
        tamano = next(t for t in Tamano if fmt.TAMANO[t].capitalize() == self._tamano)
        nacimiento = None
        if edad:
            if not edad.isdigit():
                self.error_campo("edad", "Solo el número de años.")
                return
            nacimiento = fecha_nacimiento_aproximada(int(edad), 0, self.ctx.hoy())
        ahora = self.ctx.ahora()

        def guardar():
            with self.ctx.con() as con:
                datos = dict(nombre=nombre, raza_id=raza.id if raza else None, tamano=tamano,
                             complicado=complicado, observaciones=observaciones.strip())
                if self.m:
                    return clientes.editar_mascota(con, self.m.id, ahora=ahora, **datos)
                return clientes.crear_mascota(con, self.propietario_id, ahora=ahora, fecha_nacimiento=nacimiento, **datos)

        if self.intentar(guardar):
            self.cerrar()

    @Slot()
    def baja(self) -> None:
        def baja():
            with self.ctx.con() as con:
                return clientes.desactivar_mascota(con, self.m.id, ahora=self.ctx.ahora())

        if self.intentar(baja):
            self.cerrar()


class DialogoUnir(Dialogo):
    cambioUnir = Signal()
    vista = "DialogoUnir.qml"

    def __init__(self, ctx, destino):
        super().__init__(ctx, f"Unir otro cliente en {destino.nombre}", ancho=560,
                         subtitulo="Busca el registro duplicado. Sus mascotas, turnos y saldo a favor pasan a "
                                   f"{destino.nombre}, y el duplicado queda inactivo. No se puede deshacer.")
        self.destino = destino
        self.origen = None
        self._inicial = fmt.celular(destino.telefono)
        self._texto = self._inicial
        self._resultados: list[dict] = []
        self._encontrados: dict[int, object] = {}
        self._sin_resultados = False
        self.buscar(self._inicial)

    inicial = propiedad(str, "inicial")
    resultados = propiedad("QVariantList", "resultados", cambioUnir)
    sinResultados = propiedad(bool, "sin_resultados", cambioUnir)

    @Slot(str)
    def buscar(self, texto: str) -> None:
        self._texto = texto.strip()
        if len(self._texto) < 2:
            self.poner(resultados=[], sin_resultados=False)
            return
        with self.ctx.con() as con:
            encontrados = [p for p in buscar_clientes(con, self._texto, 6) if p.id != self.destino.id]
        self._encontrados = {p.id: p for p in encontrados}
        self.poner(sin_resultados=not encontrados, resultados=[
            {"id": p.id, "texto": f"{p.nombre} · {fmt.cedula(p.cedula)} · {fmt.celular(p.telefono)}",
             "elegido": self.origen is not None and p.id == self.origen.id} for p in encontrados])

    @Slot(int)
    def elegir(self, propietario_id: int) -> None:
        self.origen = self._encontrados[propietario_id]
        self.buscar(self._texto)

    @Slot()
    def aceptar(self) -> None:
        if self.origen is None:
            self.error("Elige el cliente duplicado.")
            return

        def unir():
            with self.ctx.con() as con:
                return clientes.unir_propietarios(con, self.origen.id, self.destino.id, ahora=self.ctx.ahora())

        if self.intentar(unir):
            self.cerrar()
