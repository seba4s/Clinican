import QtQuick
import QtQuick.Layouts

// Etiqueta, entrada y mensaje de error debajo (validación en el momento con «editado»).
ColumnLayout {
    id: c
    property string titulo: ""
    property alias texto: entrada.text
    property alias placeholder: entrada.placeholderText
    property alias entrada: entrada
    property string error: ""
    property int ancho: 260
    signal editado(string texto)
    signal confirmado()
    spacing: 4
    Texto { text: c.titulo; tamano: tema.medida.etiqueta + 1; negrita: true; visible: c.titulo !== "" }
    Entrada {
        id: entrada
        Layout.preferredWidth: c.ancho
        Layout.fillWidth: c.Layout.fillWidth
        conError: c.error !== ""
        onTextEdited: c.editado(text)
        onAccepted: c.confirmado()
    }
    Texto {
        text: c.error
        color: tema.color.peligro
        tamano: tema.medida.etiqueta
        Layout.preferredWidth: c.ancho
        Layout.fillWidth: c.Layout.fillWidth
        Layout.preferredHeight: c.error ? implicitHeight : 16
    }
    function enfocar() { entrada.forceActiveFocus(); entrada.selectAll() }
}
