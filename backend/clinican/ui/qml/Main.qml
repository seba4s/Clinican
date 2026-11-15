import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import QtQuick.Layouts

ApplicationWindow {
    id: ventana
    objectName: "ventana"
    width: 1320
    height: 840
    minimumWidth: 1024
    minimumHeight: 680
    visible: true
    title: "Clinican"
    color: tema.color.fondo
    font.family: tema.familia

    property var dialogoActual: app.dialogo
    readonly property bool hayDialogo: dialogoActual !== null
    property real desenfoque: hayDialogo ? 1 : 0
    Behavior on desenfoque { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

    onDialogoActualChanged: {
        if (dialogoActual) cargador.setSource(Qt.resolvedUrl(dialogoActual.archivo), { "d": dialogoActual })
        else cargador.source = ""
    }

    Fondo { anchors.fill: parent }

    // Todo lo que no es el diálogo; se desenfoca detrás del diálogo abierto (efecto vidrio).
    Item {
        id: escena
        anchors.fill: parent
        layer.enabled: ventana.desenfoque > 0
        layer.effect: MultiEffect {
            blurEnabled: true
            blurMax: 40
            blur: 0.55 * ventana.desenfoque
            saturation: -0.1 * ventana.desenfoque
        }

        RowLayout {
            anchors.fill: parent
            spacing: 0
            BarraLateral {
                Layout.preferredWidth: 220
                Layout.fillHeight: true
                Layout.margins: 12
                Layout.rightMargin: 0
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0
                Aviso { Layout.fillWidth: true; Layout.leftMargin: 24; Layout.rightMargin: 24 }
                // Las pantallas quedan cargadas y apiladas; al cambiar de sección se funden,
                // sin volver a armar sus controles.
                Item {
                    id: pila
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Repeater {
                        model: [
                            { nombre: "Agenda", archivo: "PaginaAgenda.qml" },
                            { nombre: "Clientes", archivo: "PaginaClientes.qml" },
                            { nombre: "Recordatorios", archivo: "PaginaRecordatorios.qml" },
                            { nombre: "Ajustes", archivo: "PaginaAjustes.qml" }
                        ]
                        Loader {
                            required property var modelData
                            readonly property bool activa: app.seccion === modelData.nombre
                            objectName: "pagina" + modelData.nombre
                            width: pila.width
                            height: pila.height
                            source: modelData.archivo
                            visible: opacity > 0
                            opacity: activa ? 1 : 0
                            y: activa ? 0 : 12
                            enabled: activa
                            Behavior on opacity { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
                            Behavior on y { NumberAnimation { duration: 240; easing.type: Easing.OutCubic } }
                        }
                    }
                }
            }
        }
    }

    // Capa del diálogo: velo y diálogo centrado. Bloquea los clics a la ventana de atrás.
    Item {
        id: capa
        anchors.fill: parent
        visible: ventana.desenfoque > 0
        Rectangle { anchors.fill: parent; color: tema.color.velo; opacity: 0.22 * ventana.desenfoque }
        MouseArea { anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.AllButtons; onWheel: (e) => e.accepted = true }
        Loader {
            id: cargador
            objectName: "dialogo"
            anchors.centerIn: parent
            focus: true
            onLoaded: {
                item.altoMaximo = Qt.binding(function () { return ventana.height - 40 })
                item.forceActiveFocus()
                aparecer.restart()
            }
            NumberAnimation { id: aparecer; target: cargador.item; property: "scale"; from: 0.96; to: 1; duration: 200; easing.type: Easing.OutCubic }
        }
    }

    Shortcut { sequence: "Ctrl+N"; enabled: !ventana.hayDialogo; onActivated: app.nuevoTurno() }
    Shortcut { sequence: "Ctrl+F"; enabled: !ventana.hayDialogo; onActivated: app.buscarCliente() }
    Shortcut { sequence: "Ctrl+1"; enabled: !ventana.hayDialogo; onActivated: app.ir("Agenda") }
    Shortcut { sequence: "Ctrl+2"; enabled: !ventana.hayDialogo; onActivated: app.ir("Clientes") }
    Shortcut { sequence: "Ctrl+3"; enabled: !ventana.hayDialogo; onActivated: app.ir("Recordatorios") }
    Shortcut { sequence: "Ctrl+4"; enabled: !ventana.hayDialogo; onActivated: app.ir("Ajustes") }
}
