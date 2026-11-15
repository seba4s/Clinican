import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

DialogoMarco {
    textoPrincipal: "Listo"
    mostrarCancelar: false
    onPrincipal: d.aceptar()
    ScrollView {
        visible: d.detalle !== ""
        Layout.fillWidth: true
        Layout.preferredHeight: 220
        TextArea {
            readOnly: true
            text: d.detalle
            wrapMode: TextEdit.Wrap
            font.family: tema.familia
            font.pixelSize: tema.medida.etiqueta + 1
            color: tema.color.tinta
            background: Rectangle { radius: tema.medida.radio; color: tema.color.superficieSuave }
        }
    }
}
