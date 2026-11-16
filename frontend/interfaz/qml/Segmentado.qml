import QtQuick
import QtQuick.Layouts

Rectangle {
    id: s
    property var opciones: []
    property string valor: ""
    signal elegido(string valor)
    implicitHeight: tema.medida.altoControl
    implicitWidth: fila.implicitWidth + 8
    radius: tema.medida.radio
    color: tema.color.superficieSuave
    border.width: 1
    border.color: tema.color.borde
    Row {
        id: fila
        anchors.centerIn: parent
        spacing: 2
        Repeater {
            model: s.opciones
            Rectangle {
                required property string modelData
                readonly property bool activo: modelData === s.valor
                width: t.implicitWidth + 28
                height: s.height - 8
                radius: tema.medida.radio - 2
                color: activo ? tema.color.tinta : (area.containsMouse ? tema.color.hoverNeutro : "transparent")
                Behavior on color { ColorAnimation { duration: 140 } }
                Texto { id: t; anchors.centerIn: parent; text: modelData; negrita: activo; color: activo ? tema.color.seleccionTexto : tema.color.tinta }
                MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: { s.valor = modelData; s.elegido(modelData) } }
            }
        }
    }
}
