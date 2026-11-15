import QtQuick
import QtQuick.Layouts

// Barra lateral flotante de vidrio: logo, las cuatro secciones y la sección activa invertida.
Tarjeta {
    id: barra
    radius: 18
    ColumnLayout {
        anchors { fill: parent; margins: 12 }
        spacing: 2
        RowLayout {
            Layout.leftMargin: 8; Layout.topMargin: 8; Layout.bottomMargin: 18
            spacing: 10
            Image { source: logo; sourceSize.width: 72; sourceSize.height: 72; Layout.preferredWidth: 36; Layout.preferredHeight: 36; smooth: true; mipmap: true }
            Texto { text: "Clinican"; tamano: 18; negrita: true }
        }
        Item {
            id: menu
            Layout.fillWidth: true
            Layout.preferredHeight: app.secciones.length * 42
            // Indicador que se desliza hasta la sección activa.
            Rectangle {
                id: indicador
                width: parent.width; height: 40; radius: tema.medida.radio
                color: tema.color.seleccionFondo
                y: Math.max(0, app.secciones.indexOf(app.seccion)) * 42
                Behavior on y { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }
            }
            Repeater {
                model: app.secciones
                Rectangle {
                    required property string modelData
                    required property int index
                    readonly property bool activo: modelData === app.seccion
                    objectName: "menu" + modelData
                    width: menu.width; height: 40; y: index * 42
                    radius: tema.medida.radio
                    color: !activo && zona.containsMouse ? tema.color.hoverNeutro : "transparent"
                    Texto {
                        anchors { left: parent.left; leftMargin: 14; right: parent.right; verticalCenter: parent.verticalCenter }
                        text: modelData === "Recordatorios" ? app.insignia : modelData
                        negrita: activo
                        color: activo ? tema.color.seleccionTexto : tema.color.tinta
                        elide: Text.ElideRight
                        wrapMode: Text.NoWrap
                        Behavior on color { ColorAnimation { duration: 200 } }
                    }
                    MouseArea { id: zona; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: app.ir(modelData) }
                }
            }
        }
        Texto {
            text: "Ctrl+1 a Ctrl+4 cambian de sección"
            tamano: tema.medida.etiqueta; suave: true
            Layout.fillWidth: true; Layout.leftMargin: 12; Layout.topMargin: 16
        }
        Item { Layout.fillHeight: true }
    }
}
