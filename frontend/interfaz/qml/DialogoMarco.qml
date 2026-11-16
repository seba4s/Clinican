import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import QtQuick.Layouts

// Marco de todos los diálogos: título, contenido, error general y botones abajo (siempre a
// la vista aunque la pantalla sea baja). Esc cierra; Enter equivale al botón principal.
FocusScope {
    id: marco
    required property var d
    property string textoPrincipal: "Guardar"
    property bool mostrarPrincipal: true
    property bool principalPeligro: false
    property string textoCancelar: "Cancelar"
    property bool mostrarCancelar: true
    property string textoIzquierda: ""
    property bool enfocarCancelar: false
    property bool enterPrincipal: true
    property real altoMaximo: 600
    property real anchoMaximo: 1200
    default property alias contenido: cuerpo.data
    signal principal()
    signal izquierda()

    // Como mínimo el ancho pedido; crece si el contenido lo necesita (sin pasar la ventana).
    width: Math.min(Math.max(d.ancho, cuerpo.implicitWidth) + 56, anchoMaximo)
    height: Math.min(columna.implicitHeight + 48, altoMaximo)
    focus: true

    Keys.onEscapePressed: d.cancelar()
    Shortcut {
        sequences: ["Return", "Enter"]
        enabled: marco.enterPrincipal && marco.mostrarPrincipal
        onActivated: marco.principal()
    }
    Component.onCompleted: if (enfocarCancelar) botonCancelar.forceActiveFocus()

    RectangularShadow {
        anchors.fill: fondo
        radius: fondo.radius
        blur: 48
        spread: 0
        offset.y: 16
        color: tema.color.sombra
    }
    Tarjeta {
        id: fondo
        anchors.fill: parent
        fuerte: true
        radius: 18
    }
    ColumnLayout {
        id: columna
        anchors { fill: parent; margins: 28; topMargin: 24; bottomMargin: 24 }
        spacing: 0
        Texto { text: marco.d.titulo; tamano: 24; negrita: true; Layout.fillWidth: true }
        Texto {
            text: marco.d.subtitulo; suave: true; visible: text !== ""
            Layout.fillWidth: true; Layout.topMargin: 2
        }
        ScrollView {
            id: desplaza
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.topMargin: 16
            Layout.preferredHeight: cuerpo.implicitHeight
            contentWidth: availableWidth
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ColumnLayout {
                id: cuerpo
                width: desplaza.availableWidth
                spacing: 8
            }
        }
        Texto {
            text: marco.d.error_general; color: tema.color.peligro; visible: text !== ""
            Layout.fillWidth: true; Layout.topMargin: 8
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 16
            spacing: tema.medida.sep
            Boton { visible: marco.textoIzquierda !== ""; text: marco.textoIzquierda; tipo: "peligro"; onClicked: marco.izquierda() }
            Item { Layout.fillWidth: true }
            Boton { id: botonCancelar; visible: marco.mostrarCancelar; text: marco.textoCancelar; onClicked: marco.d.cancelar() }
            Boton {
                id: botonPrincipal
                objectName: "botonPrincipal"
                visible: marco.mostrarPrincipal
                text: marco.textoPrincipal
                tipo: marco.principalPeligro ? "peligroLleno" : "principal"
                onClicked: marco.principal()
            }
        }
    }
}
