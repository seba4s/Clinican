"""Ventana principal después de iniciar sesión: encabezado, menú y barra fucsia."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import customtkinter as ctk

from clinican.dominio.permisos import Accion
from clinican.servicios import configuracion
from clinican.servicios.base import Sesion
from clinican.ui import dialogos, tema


@dataclass
class Contexto:
    conn: object
    sesion: Sesion
    cerrar_sesion: Callable[[], None]
    refrescar_menu: Callable[[], None]
    ventana: "VentanaPrincipal" = None

    def config(self) -> dict[str, str]:
        return configuracion.valores(self.conn)

    def abrir_ficha(self, propietario_id: int, mascota_id: int, servicio_id: int | None = None,
                    volver: Callable[[], None] | None = None, menu: str = "Propietarios") -> None:
        """Abre la ficha de servicio. Por defecto «Volver» regresa a la mascota en Propietarios."""
        from clinican.ui.pantalla_ficha import PantallaFicha

        if volver is None:
            def volver():
                self.ventana.mostrar("Propietarios", propietario_id=propietario_id, pestana="Mascotas",
                                     mascota_id=mascota_id)

        def recargar(sid):
            self.abrir_ficha(propietario_id, mascota_id, sid, volver, menu)

        self.ventana.abrir(lambda padre: PantallaFicha(padre, self, mascota_id, servicio_id, volver, recargar), menu=menu)


def _entradas_menu():
    # Importación tardía para evitar ciclos.
    from clinican.ui.pantalla_auditoria import PantallaAuditoria
    from clinican.ui.pantalla_configuracion import PantallaConfiguracion
    from clinican.ui.pantalla_agenda import PantallaAgenda
    from clinican.ui.pantalla_horarios import PantallaHorarios
    from clinican.ui.pantalla_mi_pin import PantallaMiPin
    from clinican.ui.pantalla_nuevo_turno import PantallaNuevoTurno
    from clinican.ui.pantalla_personal import PantallaPersonal
    from clinican.ui.pantalla_propietarios import PantallaPropietarios
    from clinican.ui.pantalla_respaldo import PantallaRespaldo

    # (texto, pantalla, permiso necesario para verla)
    return [
        ("Agenda", PantallaAgenda, Accion.AGENDAR_TURNOS),
        ("Nuevo turno", PantallaNuevoTurno, Accion.AGENDAR_TURNOS),
        ("Propietarios", PantallaPropietarios, Accion.GESTIONAR_PROPIETARIOS),
        ("Horarios", PantallaHorarios, Accion.AJUSTAR_FRANJAS_SUELTAS),
        ("Personal", PantallaPersonal, Accion.GESTIONAR_PERSONAL),
        ("Configuración", PantallaConfiguracion, Accion.CAMBIAR_CONFIGURACION),
        ("Auditoría", PantallaAuditoria, Accion.VER_AUDITORIA),
        ("Respaldo", PantallaRespaldo, Accion.RESPALDAR),
        ("Cambiar mi PIN", PantallaMiPin, Accion.CAMBIAR_PIN_PROPIO),
    ]


class VentanaPrincipal(ctk.CTkFrame):
    def __init__(self, padre, conn, sesion: Sesion, al_cerrar_sesion: Callable[[], None]):
        super().__init__(padre, fg_color=tema.FONDO, corner_radius=0)
        self.ctx = Contexto(conn, sesion, al_cerrar_sesion, self._construir_menu)
        self.ctx.ventana = self
        self.botones_menu: dict[str, ctk.CTkButton] = {}
        self.pantalla_actual: ctk.CTkFrame | None = None
        self.nombre_actual = "Agenda"
        self._revision = None
        self._aviso = None
        self._aviso_id = None
        self._atajos: list[str] = []

        config = self.ctx.config()
        self._encabezado(config)
        self._barra_inferior(config)

        centro = ctk.CTkFrame(self, fg_color=tema.FONDO, corner_radius=0)
        centro.pack(fill="both", expand=True)
        # Con letra grande o pantalla baja, el menú se desplaza en vez de cortar opciones.
        self.menu = ctk.CTkScrollableFrame(centro, fg_color=tema.BLANCO, corner_radius=0, width=232,
                                           scrollbar_button_color=tema.BORDE_CAMPO)
        self.menu.pack(side="left", fill="y")
        self.contenido = ctk.CTkFrame(centro, fg_color=tema.FONDO, corner_radius=0)
        self.contenido.pack(side="left", fill="both", expand=True, padx=28, pady=22)

        self._construir_menu()
        self._programar_revision()
        dialogos.registrar_notificador(self.notificar)

    # ------------------------------------------------- expiración (RN-07)
    def _programar_revision(self) -> None:
        segundos = int(self.ctx.config().get("segundos_revision_expiracion", "30"))
        self._revision = self.after(segundos * 1000, self._revisar_vencidos)

    def _revisar_vencidos(self) -> None:
        """Cada 30 s (configurable) libera los turnos cuyo plazo de abono venció."""
        from clinican.servicios import turnos

        try:
            liberados = turnos.expirar_vencidos(self.ctx.conn)
            if liberados and hasattr(self.pantalla_actual, "al_expirar"):
                self.pantalla_actual.al_expirar()
        except Exception:
            import logging

            logging.getLogger(__name__).exception("Falló la revisión de turnos vencidos")
        self._programar_revision()

    def destroy(self):
        if self._revision:
            self.after_cancel(self._revision)
            self._revision = None
        if self._aviso_id:
            self.after_cancel(self._aviso_id)
            self._aviso_id = None
        dialogos.registrar_notificador(None)
        self._quitar_atajos()
        super().destroy()

    # ------------------------------------------------ avisos que no interrumpen
    def notificar(self, titulo: str, mensaje: str = "") -> None:
        """Confirma una acción con un aviso breve sobre la barra inferior; se quita solo.

        No interrumpe el trabajo (a diferencia de una ventana de aviso) y no depende
        solo del color: lleva la marca ✔ y el texto."""
        self._ocultar_aviso()
        marco = ctk.CTkFrame(self, fg_color=tema.VERDE_SUAVE, border_color=tema.VERDE_HOVER,
                             border_width=2, corner_radius=12, cursor="hand2")
        primera = mensaje.strip().splitlines()[0] if mensaje.strip() else ""
        tema.etiqueta(marco, f"✔ {titulo}", negrita=True).pack(anchor="w", padx=18, pady=(10, 0 if primera else 10))
        if primera:
            tema.etiqueta(marco, primera, tema.TAM_PEQUENO, wraplength=620).pack(anchor="w", padx=18, pady=(0, 10))
        marco.place(relx=0.5, rely=1.0, y=-62, anchor="s")
        marco.lift()
        for w in (marco, *marco.winfo_children()):
            w.bind("<Button-1>", lambda _e: self._ocultar_aviso())
        self._aviso = marco
        self._aviso_id = self.after(5000, self._ocultar_aviso)

    def _ocultar_aviso(self) -> None:
        if self._aviso_id:
            self.after_cancel(self._aviso_id)
            self._aviso_id = None
        if self._aviso is not None:
            self._aviso.destroy()
            self._aviso = None

    # ------------------------------------------------------ atajos de teclado
    def _quitar_atajos(self) -> None:
        raiz = self.winfo_toplevel()
        for secuencia in self._atajos:
            try:
                raiz.unbind(secuencia)
            except Exception:
                pass
        self._atajos = []

    def _poner_atajos(self) -> None:
        """Ctrl+1, Ctrl+2… llevan a cada sección del menú; Ctrl+Q cierra la sesión."""
        self._quitar_atajos()
        raiz = self.winfo_toplevel()
        for numero, nombre in enumerate(self.entradas, start=1):
            if numero > 9:
                break
            secuencia = f"<Control-Key-{numero}>"
            raiz.bind(secuencia, lambda _e, n=nombre: self.mostrar(n))
            self._atajos.append(secuencia)
        raiz.bind("<Control-q>", lambda _e: self._cerrar_sesion())
        self._atajos.append("<Control-q>")

    # ------------------------------------------------------------ partes fijas
    def _encabezado(self, config: dict[str, str]) -> None:
        barra = ctk.CTkFrame(self, fg_color=tema.VERDE, corner_radius=0, height=96)
        barra.pack(fill="x", side="top")
        barra.pack_propagate(False)
        imagen = tema.logo(84)
        if imagen:
            ctk.CTkLabel(barra, text="", image=imagen).pack(side="left", padx=(18, 6))
        textos = ctk.CTkFrame(barra, fg_color="transparent")
        textos.pack(side="left")
        tema.etiqueta(textos, config.get("negocio_nombre", "CLINICAN"), 34, negrita=True).pack(anchor="w")
        tema.etiqueta(textos, config.get("negocio_descripcion", ""), tema.TAM_PEQUENO, negrita=True).pack(anchor="w")

        derecha = ctk.CTkFrame(barra, fg_color="transparent")
        derecha.pack(side="right", padx=20)
        tema.boton(derecha, "Cerrar sesión", self._cerrar_sesion, estilo="secundario", ancho=170).pack(side="right", padx=(16, 0))
        self.lbl_usuario = tema.etiqueta(derecha, "", negrita=True, justify="right")
        self.lbl_usuario.pack(side="right")

    def _barra_inferior(self, config: dict[str, str]) -> None:
        barra = ctk.CTkFrame(self, fg_color=tema.FUCSIA, corner_radius=0, height=46)
        barra.pack(fill="x", side="bottom")
        barra.pack_propagate(False)
        texto = f"SERVICIO DE PELUQUERÍA     {config.get('whatsapp_numero', '')}     ·     {config.get('negocio_direccion', '')}"
        ctk.CTkLabel(barra, text=texto, font=tema.fuente(tema.TAM_NORMAL, True), text_color=tema.BLANCO).pack(expand=True)

    # ----------------------------------------------------------------- menú
    def _construir_menu(self) -> None:
        s = self.ctx.sesion
        rol = "Administradora" if s.es_admin else "Personal"
        self.lbl_usuario.configure(text=f"{s.nombre}\n{s.cargo} · {rol}")

        for hijo in self.menu.winfo_children():
            hijo.destroy()
        self.botones_menu.clear()
        tema.etiqueta(self.menu, "MENÚ", tema.TAM_PEQUENO, negrita=True, color=tema.GRIS_TEXTO).pack(anchor="w", padx=20, pady=(22, 8))
        self.entradas = {}
        for texto, clase, permiso in _entradas_menu():
            if permiso is not None and not s.puede(permiso):
                continue  # oculto en pantalla; el servicio igual lo valida
            self.entradas[texto] = clase
            b = tema.boton(self.menu, texto, lambda t=texto: self.mostrar(t), estilo="secundario", ancho=210, anchor="w")
            b.pack(padx=20, pady=5)
            self.botones_menu[texto] = b
        tema.etiqueta(self.menu, "Teclado: Ctrl + número va a cada sección.\nCtrl + Q cierra la sesión.",
                      tema.TAM_PEQUENO - 2, color=tema.GRIS_TEXTO, wraplength=210).pack(
            anchor="w", padx=20, pady=16)
        self._poner_atajos()
        destino = self.nombre_actual if self.nombre_actual in self.entradas else next(iter(self.entradas))
        self.mostrar(destino)

    def mostrar(self, nombre: str, **kwargs) -> None:
        """Muestra una pantalla del menú. ``kwargs`` permite abrirla en un punto concreto."""
        self._resaltar(nombre)
        self.nombre_actual = nombre
        self._titulo_ventana(nombre)
        self._poner(lambda padre: self.entradas[nombre](padre, self.ctx, **kwargs))

    def abrir(self, fabrica, menu: str | None = None) -> None:
        """Abre una pantalla que no está en el menú (por ejemplo, una ficha)."""
        if menu:
            self._resaltar(menu)
            self._titulo_ventana(menu)
        self._poner(fabrica)

    def _titulo_ventana(self, seccion: str) -> None:
        """La barra de título dice dónde está la persona: «Agenda — CLINICAN»."""
        try:
            self.winfo_toplevel().title(f"{seccion} — CLINICAN")
        except Exception:
            pass

    def _resaltar(self, nombre: str) -> None:
        for texto, b in self.botones_menu.items():
            activo = texto == nombre
            b.configure(
                fg_color=tema.VERDE if activo else tema.BLANCO,
                hover_color=tema.VERDE_HOVER if activo else tema.GRIS_BOTON,
            )

    def _poner(self, fabrica) -> None:
        if self.pantalla_actual is not None:
            self.pantalla_actual.destroy()
        self.pantalla_actual = fabrica(self.contenido)
        self.pantalla_actual.pack(fill="both", expand=True)

    def _cerrar_sesion(self) -> None:
        self.ctx.cerrar_sesion()
