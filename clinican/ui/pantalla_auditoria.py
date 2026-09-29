"""Registro de auditoría (solo la administradora)."""

from __future__ import annotations

from datetime import date, timedelta

import customtkinter as ctk

from clinican.servicios import auditoria, personal
from clinican.ui import dialogos, tema

NOMBRES_ACCION = {
    "PRIMER_ARRANQUE": "Primer arranque",
    "INICIO_SESION": "Inició sesión",
    "INICIO_SESION_FALLIDO": "Intento de inicio fallido",
    "CIERRE_SESION": "Cerró sesión",
    "CAMBIAR_PIN_PROPIO": "Cambió su PIN",
    "CAMBIAR_PIN_DE_OTRO": "Cambió el PIN de otra persona",
    "CREAR_PERSONAL": "Agregó personal",
    "EDITAR_PERSONAL": "Editó personal",
    "DESACTIVAR_PERSONAL": "Desactivó personal",
    "REACTIVAR_PERSONAL": "Reactivó personal",
    "TRANSFERIR_ADMINISTRACION": "Entregó la administración",
    "CAMBIAR_CONFIGURACION": "Cambió la configuración",
    "CREAR_PROPIETARIO": "Creó propietario",
    "EDITAR_PROPIETARIO": "Editó propietario",
    "MARCA_NUEVO_ABONO": "Cambió «requiere nuevo abono»",
    "CREAR_MASCOTA": "Creó mascota",
    "EDITAR_MASCOTA": "Editó mascota",
    "ACTIVAR_MASCOTA": "Reactivó mascota",
    "DESACTIVAR_MASCOTA": "Dio de baja mascota",
    "CORREGIR_ULTIMA_VISITA": "Corrigió última visita",
    "CREAR_RAZA": "Creó raza",
    "EDITAR_RAZA": "Editó raza",
    "NUEVA_VERSION_TEXTO_LEGAL": "Nueva versión de texto legal",
    "ACEPTAR_TERMINOS": "Registró aceptación de términos",
    "ACEPTAR_DATOS": "Registró autorización de datos",
    "ACEPTAR_RESPONSABILIDAD": "Registró responsabilidad",
    "IMPORTAR_EXCEL": "Importó desde Excel",
    "CREAR_FICHA": "Creó ficha de servicio",
    "EDITAR_FICHA": "Editó ficha de servicio",
    "ESTADO_FICHA": "Cambió estado de ficha",
    "SESION_DESENREDADO": "Registró sesión de desenredado",
    "ANULAR_SESION_DESENREDADO": "Anuló sesión de desenredado",
    "CERRAR_DESENREDADO": "Cerró desenredado",
    "CREAR_TURNO": "Agendó turno",
    "CONFIRMAR_TURNO": "Turno confirmado por abono",
    "LIBERAR_TURNO": "Turno liberado",
    "REGISTRAR_ABONO": "Registró abono",
    "CORREGIR_ABONO": "Corrigió abono",
    "DEVOLVER_ABONO": "Devolvió abono",
    "USAR_ABONO_A_FAVOR": "Usó abono a favor",
    "MOVER_TURNO": "Movió turno",
    "ESTADO_TURNO": "Cambió estado de turno",
    "LLAMADA_PROPIETARIO": "Llamó al propietario",
    "AGREGAR_FRANJA": "Agregó hora extra",
    "QUITAR_FRANJA": "Quitó hora extra",
    "BLOQUEAR_DIAS": "Bloqueó días",
    "BLOQUEAR_FRANJA": "Bloqueó franja",
    "DESBLOQUEAR": "Quitó bloqueo",
    "PLANTILLA_FRANJA": "Cambió plantilla semanal",
    "RESPALDAR": "Hizo un respaldo",
    "RESTAURAR_RESPALDO": "Restauró un respaldo",
}

TODAS = "Todas las personas"


class PantallaAuditoria(ctk.CTkFrame):
    def __init__(self, padre, ctx):
        super().__init__(padre, fg_color="transparent")
        self.ctx = ctx
        tema.titulo(self, "Registro de auditoría").pack(anchor="w", pady=(0, 12))

        filtros = tema.tarjeta(self)
        filtros.pack(fill="x", pady=(0, 14))
        fila = ctk.CTkFrame(filtros, fg_color="transparent")
        fila.pack(fill="x", padx=18, pady=16)

        lista = dialogos.ejecutar(self, personal.listar_todos, ctx.conn, ctx.sesion)
        self.personas = {} if lista is dialogos.FALLO else {f["nombre"]: f["id"] for f in lista}
        self.persona = self._filtro(fila, "Persona", lambda p: tema.selector(p, [TODAS, *self.personas], ancho=240))
        self.persona.set(TODAS)
        self.desde = self._filtro(fila, "Desde (AAAA-MM-DD)", lambda p: tema.entrada(p, ancho=170))
        self.hasta = self._filtro(fila, "Hasta (AAAA-MM-DD)", lambda p: tema.entrada(p, ancho=170))
        self.texto = self._filtro(fila, "Buscar", lambda p: tema.entrada(p, ancho=200))
        self.desde.insert(0, (date.today() - timedelta(days=30)).isoformat())
        self.hasta.insert(0, date.today().isoformat())
        tema.boton(fila, "Buscar", self._buscar, ancho=130).pack(side="left", anchor="s", padx=(8, 0))
        for e in (self.desde, self.hasta, self.texto):
            e.bind("<Return>", lambda _e: self._buscar())

        self.tabla = tema.tabla(
            self,
            [("ts", "Fecha y hora", 190), ("persona", "Persona", 170), ("accion", "Acción", 280), ("detalle", "Detalle", 420)],
            alto=14,
        )
        self.tabla.marco.pack(fill="both", expand=True)
        self.total = tema.etiqueta(self, "", tema.TAM_PEQUENO, color=tema.GRIS_TEXTO)
        self.total.pack(anchor="w", pady=(8, 0))
        self._buscar()

    @staticmethod
    def _filtro(fila, texto, fabrica):
        caja = ctk.CTkFrame(fila, fg_color="transparent")
        caja.pack(side="left", padx=(0, 12))
        tema.etiqueta(caja, texto, tema.TAM_PEQUENO, negrita=True).pack(anchor="w")
        widget = fabrica(caja)
        widget.pack(anchor="w")
        return widget

    def _buscar(self) -> None:
        persona = self.persona.get()
        filas = dialogos.ejecutar(
            self, auditoria.consultar, self.ctx.conn, self.ctx.sesion,
            personal_id=self.personas.get(persona) if persona != TODAS else None,
            desde=self.desde.get().strip() or None,
            hasta=self.hasta.get().strip() or None,
            texto=self.texto.get().strip() or None,
        )
        if filas is dialogos.FALLO:
            return
        self.tabla.delete(*self.tabla.get_children())
        for i, f in enumerate(filas):
            self.tabla.insert(
                "", "end", tags=["par"] if i % 2 else [],
                values=(f["ts"], f["persona"], NOMBRES_ACCION.get(f["accion"], f["accion"]), f["detalle"] or ""),
            )
        self.total.configure(text=f"{len(filas)} registros (se muestran como máximo 500, del más reciente al más antiguo).")
