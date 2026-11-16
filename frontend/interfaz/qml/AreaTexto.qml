import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Etiqueta y caja de texto de varias líneas.
ColumnLayout {
    id: c
    property string titulo: ""
    property alias texto: area.text
    property int alto: 90
    spacing: 4
    Texto { text: c.titulo; tamano: tema.medida.etiqueta + 1; negrita: true }
    ScrollView {
        Layout.fillWidth: true
        Layout.preferredHeight: c.alto
        TextArea {
            id: area
            font.family: tema.familia
            font.pixelSize: tema.medida.cuerpo
            color: tema.color.tinta
            wrapMode: TextEdit.Wrap
            selectByMouse: true
            selectionColor: tema.color.fondoSeleccion
            selectedTextColor: tema.color.tinta
            background: Rectangle {
                radius: tema.medida.radio
                color: tema.color.superficie
                border.width: area.activeFocus ? 2 : 1
                border.color: area.activeFocus ? tema.color.tinta : tema.color.bordeCampo
            }
        }
    }
}
