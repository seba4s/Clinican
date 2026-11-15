import QtQuick
import QtQuick.Controls

CheckBox {
    id: c
    font.family: tema.familia
    font.pixelSize: tema.medida.cuerpo
    spacing: 10
    indicator: Rectangle {
        implicitWidth: 22; implicitHeight: 22
        x: c.leftPadding; y: (c.height - height) / 2
        radius: 6
        color: c.checked ? tema.color.tinta : tema.color.superficie
        border.width: c.visualFocus ? 2 : 1
        border.color: c.checked || c.visualFocus ? tema.color.tinta : tema.color.bordeCampo
        Behavior on color { ColorAnimation { duration: 120 } }
        Text { anchors.centerIn: parent; text: "✓"; visible: c.checked; color: tema.color.seleccionTexto; font.pixelSize: 15; font.bold: true }
    }
    contentItem: Texto {
        text: c.text
        leftPadding: c.indicator.width + c.spacing
        wrapMode: Text.WordWrap
    }
}
