import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: c
    objectName: "campoHora"
    property var horas: util.horas()
    property alias texto: entrada.text
    property alias entrada: entrada
    property bool valido: true
    property bool habilitado: true
    readonly property bool abierto: cuadricula.opened
    implicitWidth: 124
    implicitHeight: tema.medida.altoControl
    radius: tema.medida.radio
    color: habilitado ? tema.color.superficie : tema.color.superficieSuave
    border.width: !valido || entrada.activeFocus ? 2 : 1
    border.color: !valido ? tema.color.peligro : (entrada.activeFocus ? tema.color.tinta : tema.color.bordeCampo)

    function normalizar() {
        var n = util.normalizarHora(entrada.text)
        if (n === "") { valido = false; return false }
        if (n !== entrada.text) entrada.text = n
        valido = true
        return true
    }
    function poner(t) { entrada.text = t; normalizar() }
    function paso(sentido) { poner(util.pasoHora(entrada.text, sentido, horas)) }
    function abrir() { if (cuadricula.opened) cuadricula.close(); else { normalizar(); cuadricula.open() } }
    function elegir(h) { cuadricula.close(); poner(h); entrada.forceActiveFocus() }
    Component.onCompleted: if (entrada.text !== "") normalizar()

    TextInput {
        id: entrada
        enabled: c.habilitado
        anchors { left: parent.left; right: flecha.left; verticalCenter: parent.verticalCenter; leftMargin: 12 }
        font.family: tema.familia
        font.pixelSize: tema.medida.cuerpo
        font.features: { "tnum": 1 }
        color: c.habilitado ? tema.color.tinta : tema.color.tintaSuave
        selectByMouse: true
        selectionColor: tema.color.fondoSeleccion
        selectedTextColor: tema.color.tinta
        clip: true
        onEditingFinished: c.normalizar()
        Keys.onUpPressed: c.paso(-1)
        Keys.onDownPressed: (evento) => { if (evento.modifiers & Qt.AltModifier) c.abrir(); else c.paso(1) }
    }
    Rectangle {
        id: flecha
        width: 28; height: 28; radius: 6
        anchors { right: parent.right; rightMargin: 6; verticalCenter: parent.verticalCenter }
        color: zona.containsMouse && c.habilitado ? tema.color.hoverNeutro : "transparent"
        Texto { anchors.centerIn: parent; text: "▾"; suave: true }
        MouseArea { id: zona; anchors.fill: parent; hoverEnabled: true; enabled: c.habilitado; cursorShape: Qt.PointingHandCursor; onClicked: c.abrir() }
    }
    Popup {
        id: cuadricula
        y: c.height + 4
        padding: 6
        modal: false
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent
        background: Rectangle { radius: tema.medida.radio; color: tema.color.vidrioFuerte; border.color: tema.color.bordeCampo }
        enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 120 } }
        contentItem: Grid {
            columns: 4
            spacing: 4
            Repeater {
                model: c.horas
                Rectangle {
                    required property string modelData
                    readonly property bool elegida: modelData === entrada.text
                    width: 64; height: 30; radius: 6
                    color: elegida ? tema.color.seleccionFondo : (m.containsMouse ? tema.color.hoverNeutro : "transparent")
                    Texto { anchors.centerIn: parent; text: modelData; tamano: tema.medida.etiqueta + 1; negrita: elegida
                            color: elegida ? tema.color.seleccionTexto : tema.color.tinta }
                    MouseArea { id: m; anchors.fill: parent; hoverEnabled: true; onClicked: c.elegir(modelData) }
                }
            }
        }
    }
}
