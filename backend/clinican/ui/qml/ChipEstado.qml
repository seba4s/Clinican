import QtQuick

// Estado del turno: siempre con texto e ícono, no solo color.
Chip {
    property string estado: ""
    property string texto2: ""
    readonly property var e: tema.estados[estado] || ({})
    color: e.fondo || "transparent"
    letra: e.letra || tema.color.tinta
    tamano: tema.medida.etiqueta + 1
    implicitHeight: 28
    texto: (e.icono || "") + "  " + (texto2 || e.nombre || "")
}
