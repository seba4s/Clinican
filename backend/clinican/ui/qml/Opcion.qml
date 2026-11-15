import QtQuick
import QtQuick.Controls

RadioButton {
    id: r
    font.family: tema.familia
    font.pixelSize: tema.medida.cuerpo
    spacing: 10
    indicator: Rectangle {
        implicitWidth: 22; implicitHeight: 22
        x: r.leftPadding; y: (r.height - height) / 2
        radius: 11
        color: tema.color.superficie
        border.width: r.checked || r.visualFocus ? 2 : 1
        border.color: r.checked || r.visualFocus ? tema.color.tinta : tema.color.bordeCampo
        Rectangle {
            anchors.centerIn: parent; width: 12; height: 12; radius: 6
            color: tema.color.tinta
            scale: r.checked ? 1 : 0
            Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutBack } }
        }
    }
    contentItem: Texto { text: r.text; leftPadding: r.indicator.width + r.spacing }
}
