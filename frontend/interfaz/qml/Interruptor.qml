import QtQuick
import QtQuick.Controls

Switch {
    id: s
    indicator: Rectangle {
        implicitWidth: 42; implicitHeight: 24
        x: s.leftPadding; y: (s.height - height) / 2
        radius: 12
        color: s.checked ? tema.color.tinta : tema.color.bordeCampo
        border.width: s.visualFocus ? 2 : 0
        border.color: tema.color.accion
        Behavior on color { ColorAnimation { duration: 140 } }
        Rectangle {
            x: s.checked ? parent.width - width - 3 : 3
            anchors.verticalCenter: parent.verticalCenter
            width: 18; height: 18; radius: 9
            color: tema.color.superficie
            Behavior on x { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
        }
    }
}
