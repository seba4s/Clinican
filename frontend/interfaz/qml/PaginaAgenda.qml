import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: pagina
    readonly property var p: app.agenda
    readonly property bool activa: app.seccion === "Agenda" && !ventana.hayDialogo
    function sinTexto() { return !(ventana.activeFocusItem instanceof TextInput) && !(ventana.activeFocusItem instanceof TextEdit) }
    Shortcut { sequence: "Left"; enabled: pagina.activa && pagina.sinTexto(); onActivated: pagina.p.dia_anterior() }
    Shortcut { sequence: "Right"; enabled: pagina.activa && pagina.sinTexto(); onActivated: pagina.p.dia_siguiente() }
    Shortcut { sequence: "Home"; enabled: pagina.activa && pagina.sinTexto(); onActivated: pagina.p.ir_hoy() }

    ColumnLayout {
        anchors { fill: parent; leftMargin: 24; rightMargin: 24; topMargin: 20; bottomMargin: 20 }
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 4
            Boton { text: "‹"; implicitWidth: 40; onClicked: pagina.p.dia_anterior() }
            Boton { text: "Hoy"; implicitWidth: 64; onClicked: pagina.p.ir_hoy() }
            Boton { text: "›"; implicitWidth: 40; onClicked: pagina.p.dia_siguiente() }
            Texto { text: pagina.p.tituloDia; tamano: tema.medida.titulo; negrita: true; wrapMode: Text.NoWrap
                    elide: Text.ElideRight; Layout.fillWidth: true; Layout.leftMargin: 16 }
            Texto { text: pagina.p.resumen; tamano: tema.medida.etiqueta + 1; suave: true; wrapMode: Text.NoWrap; Layout.rightMargin: tema.medida.sep }
            Boton { text: "Bloquear horas"; onClicked: pagina.p.bloquear(); Layout.rightMargin: tema.medida.sep - 4 }
            Boton { text: "+ Nuevo turno  (Ctrl+N)"; tipo: "principal"; onClicked: pagina.p.nuevo() }
        }

        Flow {
            Layout.fillWidth: true
            visible: pagina.p.pendientes.length > 0
            spacing: 8
            readonly property var e: tema.estados["PENDIENTE_ABONO"] || ({})
            Texto { height: 36; text: pagina.p.pendientesTitulo; negrita: true; tamano: tema.medida.etiqueta + 1; color: parent.e.letra || tema.color.tinta; wrapMode: Text.NoWrap; rightPadding: 4 }
            Repeater {
                model: pagina.p.pendientes
                Rectangle {
                    required property var modelData
                    readonly property var e: tema.estados["PENDIENTE_ABONO"] || ({})
                    height: 36; width: t.implicitWidth + 24; radius: 10
                    color: zona.containsMouse ? e.borde : e.fondo
                    border.color: e.borde || "transparent"
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Texto { id: t; anchors.centerIn: parent; text: modelData.texto; tamano: tema.medida.etiqueta + 1; wrapMode: Text.NoWrap }
                    MouseArea { id: zona; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: pagina.p.ir_a_pendiente(modelData.indice) }
                }
            }
            Texto { height: 36; visible: text !== ""; text: pagina.p.pendientesMas; tamano: tema.medida.etiqueta; suave: true; wrapMode: Text.NoWrap }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 16
            Tarjeta {
                Layout.fillWidth: true
                Layout.fillHeight: true
                ColumnLayout {
                    anchors { fill: parent; margins: 10 }
                    spacing: 6
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 8
                        color: tema.color.superficie
                        clip: true
                        HojaAgenda { anchors.fill: parent; p: pagina.p }
                    }
                    Texto { Layout.fillWidth: true; Layout.leftMargin: 6; visible: text !== ""; text: pagina.p.fuera; tamano: tema.medida.etiqueta; suave: true }
                }
            }
            PanelTurno { p: pagina.p; Layout.preferredWidth: 320; Layout.fillHeight: true }
        }
    }
}
