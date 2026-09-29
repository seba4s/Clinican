"""Especie, raza (de la lista o escrita a mano), tamaño y pelaje de una mascota.

Se usa al registrar una mascota y al agendar a un cliente nuevo sin registrarlo.
Si la raza escrita no existe, se crea al guardar y la mascota lleva su propio
tamaño y pelaje (como el perro mestizo).
"""

from __future__ import annotations

import customtkinter as ctk

from clinican.dominio.catalogos import ESPECIES, TAMANOS, nombre_tamano
from clinican.dominio.formato import sin_tildes
from clinican.servicios import razas
from clinican.ui import tema

ELIJA = "— Elija —"


class SelectorRaza:
    """Crea sus campos dentro de ``padre`` (uno debajo de otro, con ``pack``)."""

    def __init__(self, padre, conn, ancho: int = 420, raza_actual_id: int | None = None):
        self.conn = conn
        todas = list(razas.listar(conn, solo_activas=True))
        if raza_actual_id is not None and raza_actual_id not in {r["id"] for r in todas}:
            todas += [r for r in razas.listar(conn, solo_activas=False) if r["id"] == raza_actual_id]
        self.razas = todas
        self.tam_opc: dict[str, str | None] = {}
        self.pel_opc: dict[str, int | None] = {}

        self._etiqueta(padre, "Especie")
        self.especie = tema.Opciones(padre, ESPECIES, self._al_cambiar_especie, "PERRO")
        self.especie.pack(anchor="w")
        self._etiqueta(padre, "Raza * (elíjala de la lista o escríbala)")
        self.raza = tema.selector(padre, [], ancho=ancho, editable=True, command=lambda _v: self.actualizar())
        self.raza.pack(anchor="w")
        self.raza.bind("<KeyRelease>", lambda _e: self.actualizar(), add="+")
        self.nota = tema.etiqueta(padre, "", tema.TAM_PEQUENO, color=tema.AZUL_OSCURO, wraplength=ancho + 100)
        self.nota.pack(anchor="w")
        self.lbl_tam = self._etiqueta(padre, "Tamaño")
        self.tamano = tema.selector(padre, [ELIJA], ancho=ancho)
        self.tamano.pack(anchor="w")
        self.lbl_pel = self._etiqueta(padre, "Pelaje complicado (husky o razas similares)")
        self.pelaje = tema.selector(padre, [ELIJA], ancho=ancho)
        self.pelaje.pack(anchor="w")
        self._al_cambiar_especie(limpiar=True)

    @staticmethod
    def _etiqueta(padre, texto):
        lbl = tema.etiqueta(padre, texto, negrita=True)
        lbl.pack(anchor="w", pady=(10, 4))
        return lbl

    # ---------------------------------------------------------------- lógica
    def _de_especie(self) -> list:
        especie = self.especie.codigo or "PERRO"
        return [r for r in self.razas if (r["especie"] or "PERRO") == especie]

    def _buscar(self, texto: str):
        clave = sin_tildes(" ".join((texto or "").split()))
        return next((r for r in self.razas if sin_tildes(r["nombre"]) == clave), None) if clave else None

    def _al_cambiar_especie(self, limpiar: bool = True) -> None:
        self.raza.configure(values=[r["nombre"] for r in self._de_especie()])
        if limpiar:
            actual = self._buscar(self.raza.get())
            if actual is not None and actual["especie"] != self.especie.codigo:
                self.raza.set("")  # una raza escrita a mano se conserva
        self.actualizar()

    def actualizar(self, tam_inicial=None, pel_inicial=None) -> None:
        """Opciones de tamaño y pelaje según la raza (la raza sin tamaño exige elegirlos)."""
        texto = self.raza.get().strip()
        r = self._buscar(texto)
        if texto and r is None:
            self.nota.configure(text=f"«{texto}» es una raza nueva: se agregará al guardar. Elija el tamaño y el pelaje.")
        else:
            self.nota.configure(text="")
        con_tamano = r is not None and r["tamano"]
        previo_tam = tam_inicial if tam_inicial is not None else self.tam_opc.get(self.tamano.get())
        previo_pel = pel_inicial if pel_inicial is not None else self.pel_opc.get(self.pelaje.get())
        self.tam_opc.clear()
        self.pel_opc.clear()
        if con_tamano:
            self.tam_opc[f"Según la raza ({nombre_tamano(r['tamano'])})"] = None
            self.pel_opc[f"Según la raza ({'Sí' if r['pelaje_complicado'] else 'No'})"] = None
            self.lbl_tam.configure(text="Tamaño")
            self.lbl_pel.configure(text="Pelaje complicado (husky o razas similares)")
        else:
            self.tam_opc[ELIJA] = None
            self.pel_opc[ELIJA] = None
            self.lbl_tam.configure(text="Tamaño * (obligatorio para esta raza)")
            self.lbl_pel.configure(text="Pelaje complicado * (obligatorio para esta raza)")
        self.tam_opc.update({v: k for k, v in TAMANOS.items()})
        self.pel_opc.update({"Sí": 1, "No": 0})
        self.tamano.configure(values=list(self.tam_opc))
        self.pelaje.configure(values=list(self.pel_opc))
        self.tamano.set(next((k for k, v in self.tam_opc.items() if v == previo_tam), list(self.tam_opc)[0]))
        self.pelaje.set(next((k for k, v in self.pel_opc.items() if v == previo_pel), list(self.pel_opc)[0]))

    # ------------------------------------------------------------- lectura
    def cargar(self, m) -> None:
        """Muestra los datos de una mascota ya registrada."""
        self.especie.codigo = m["especie"] or "PERRO"
        self._al_cambiar_especie(limpiar=False)
        self.raza.set(m["raza_nombre"])
        self.actualizar(m["tamano_manual"], m["pelaje_complicado_manual"])

    def valores(self) -> dict:
        """Argumentos para ``propietarios.crear_mascota`` / ``editar_mascota`` / ``crear_provisional``."""
        r = self._buscar(self.raza.get())
        return {
            "raza_id": r["id"] if r else None,
            "raza_texto": None if r else self.raza.get().strip() or None,
            "especie": self.especie.codigo or "PERRO",
            "tamano_manual": self.tam_opc.get(self.tamano.get()),
            "pelaje_manual": self.pel_opc.get(self.pelaje.get()),
        }
