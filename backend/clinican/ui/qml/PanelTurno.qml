import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Panel del turno elegido: datos, nota y las acciones según el estado.
Tarjeta {
    id: panel
    required property var p
    readonly property var d: p.panel
    Flickable {
        anchors { fill: parent; margins: 20 }
        contentHeight: columna.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ColumnLayout {
            id: columna
            width: parent.width
            spacing: 0
            opacity: 1
            // Al cambiar de turno, el contenido aparece con un fundido corto.
            onVisibleChanged: aparecer.restart()
            Connections { target: panel; function onDChanged() { aparecer.restart() } }
            NumberAnimation { id: aparecer; target: columna; property: "opacity"; from: 0.4; to: 1; duration: 180 }

            Texto { visible: panel.d.vacio; Layout.fillWidth: true; suave: true
                    text: "Elige un turno de la hoja para ver sus datos y lo que puedes hacer con él." }
            Texto { visible: panel.d.vacio; Layout.fillWidth: true; Layout.topMargin: 12; suave: true
                    text: "En la fila «Libre» de cada hora, toca un cupo para agendar directamente ahí." }

            Texto { visible: !panel.d.vacio; text: panel.d.encabezado || ""; tamano: tema.medida.etiqueta; suave: true; Layout.fillWidth: true }
            Texto { visible: !panel.d.vacio; text: panel.d.titulo || ""; tamano: 22; negrita: true; Layout.fillWidth: true }
            Texto { visible: !panel.d.vacio; text: panel.d.dueno || ""; Layout.fillWidth: true }
            ChipEstado { visible: !panel.d.vacio; estado: panel.d.estado || ""; Layout.topMargin: 10; Layout.bottomMargin: 10 }
            GridLayout {
                visible: !panel.d.vacio
                columns: 2; columnSpacing: 16; rowSpacing: 4
                Layout.fillWidth: true
                Repeater {
                    model: panel.d.vacio ? [] : panel.d.datos
                    delegate: Texto {
                        required property int index
                        required property var modelData
                        text: modelData[0]; suave: true; wrapMode: Text.NoWrap
                        Layout.row: index; Layout.column: 0
                    }
                }
                Repeater {
                    model: panel.d.vacio ? [] : panel.d.datos
                    delegate: Texto {
                        required property int index
                        required property var modelData
                        text: modelData[1]
                        Layout.row: index; Layout.column: 1; Layout.fillWidth: true
                    }
                }
            }
            Rectangle {
                visible: !panel.d.vacio && (panel.d.nota || "") !== ""
                Layout.fillWidth: true; Layout.topMargin: 12
                implicitHeight: nota.implicitHeight + 12
                radius: 8
                color: tema.color.superficieSuave
                Texto { id: nota; anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 8 }
                        text: panel.d.nota || ""; tamano: tema.medida.etiqueta + 1 }
            }
            ColumnLayout {
                Layout.fillWidth: true; Layout.topMargin: 16
                spacing: 8
                Repeater {
                    model: panel.d.vacio ? [] : panel.d.acciones
                    Boton {
                        required property int index
                        required property var modelData
                        objectName: "accion" + index
                        Layout.fillWidth: true
                        text: modelData.texto; tipo: modelData.tipo
                        onClicked: panel.p.accion(index)
                    }
                }
            }
        }
    }
}
