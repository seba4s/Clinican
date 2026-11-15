import QtQuick
import QtQuick.Layouts

// Día con flechas y las franjas que aún tienen cupo (8 por fila). d: diálogo con
// «franjas», «mover_dia» y «elegir_hora».
ColumnLayout {
    id: s
    required property var d
    readonly property var datos: d.franjas
    spacing: 10
    RowLayout {
        spacing: 10
        Boton { text: "‹"; implicitWidth: 36; alto: 34; onClicked: s.d.mover_dia(-1) }
        Texto { text: s.datos.dia || ""; negrita: true; wrapMode: Text.NoWrap }
        Boton { text: "›"; implicitWidth: 36; alto: 34; onClicked: s.d.mover_dia(1) }
    }
    Texto { visible: (s.datos.mensaje || "") !== ""; text: s.datos.mensaje || ""; suave: true; Layout.fillWidth: true }
    GridLayout {
        Layout.fillWidth: true
        columns: 8
        columnSpacing: 6
        rowSpacing: 6
        Repeater {
            model: s.datos.franjas || []
            Rectangle {
                required property var modelData
                readonly property bool lleno: modelData.lleno
                readonly property bool elegida: modelData.elegida
                objectName: "franja"
                Layout.fillWidth: true
                Layout.preferredWidth: 70
                height: 44
                radius: tema.medida.radio
                color: elegida ? tema.color.tinta : (lleno ? tema.color.superficieSuave : (zona.containsMouse ? tema.color.hoverNeutro : tema.color.superficie))
                border.width: lleno || elegida ? 0 : 1
                border.color: tema.color.bordeCampo
                scale: zona.pressed ? 0.96 : 1
                Behavior on color { ColorAnimation { duration: 120 } }
                Behavior on scale { NumberAnimation { duration: 100 } }
                Column {
                    anchors.centerIn: parent
                    Texto { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.hora; negrita: elegida; tamano: tema.medida.etiqueta + 1
                            color: elegida ? tema.color.seleccionTexto : (lleno ? tema.color.tintaSuave : tema.color.tinta) }
                    Texto { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.detalle; tamano: tema.medida.etiqueta
                            color: elegida ? tema.color.seleccionTexto : (lleno ? tema.color.tintaSuave : tema.color.tinta) }
                }
                MouseArea { id: zona; anchors.fill: parent; hoverEnabled: true; enabled: !lleno; cursorShape: Qt.PointingHandCursor
                            onClicked: s.d.elegir_hora(modelData.indice) }
            }
        }
    }
}
