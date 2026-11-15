import QtQuick
import QtQuick.Controls

// Caja de texto de una línea con el estilo del tema.
TextField {
    id: f
    property bool conError: false
    implicitHeight: tema.medida.altoControl
    font.family: tema.familia
    font.pixelSize: tema.medida.cuerpo
    color: enabled ? tema.color.tinta : tema.color.tintaSuave
    placeholderTextColor: tema.color.tintaSuave
    selectByMouse: true
    selectionColor: tema.color.fondoSeleccion
    selectedTextColor: tema.color.tinta
    leftPadding: 12
    rightPadding: 12
    verticalAlignment: TextInput.AlignVCenter
    background: Rectangle {
        radius: tema.medida.radio
        color: f.enabled ? tema.color.superficie : tema.color.superficieSuave
        border.width: f.conError || f.activeFocus ? 2 : 1
        border.color: f.conError ? tema.color.peligro : (f.activeFocus ? tema.color.tinta : tema.color.bordeCampo)
        Behavior on border.color { ColorAnimation { duration: 120 } }
    }
}
