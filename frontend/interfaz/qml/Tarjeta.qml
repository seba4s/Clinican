import QtQuick

// Panel de vidrio: translúcido sobre el fondo desenfocado, con filo de luz arriba.
Rectangle {
    property bool fuerte: false
    property int relleno: 16
    radius: tema.medida.radioTarjeta
    color: fuerte ? tema.color.vidrioFuerte : tema.color.vidrio
    border.width: 1
    border.color: tema.color.vidrioBorde
    Rectangle {
        anchors { left: parent.left; right: parent.right; top: parent.top; leftMargin: parent.radius; rightMargin: parent.radius }
        height: 1
        color: tema.color.vidrioBrillo
        opacity: 0.9
    }
}
