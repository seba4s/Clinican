import QtQuick
import QtQuick.Layouts

DialogoMarco {
    id: dlg
    textoPrincipal: "Unir"
    onPrincipal: d.aceptar()
    Campo { id: campo; titulo: "Cliente duplicado"; ancho: 500; texto: dlg.d.inicial; onEditado: (t) => dlg.d.buscar(t) }
    Texto { visible: dlg.d.sinResultados; text: "No hay otro cliente con ese dato."; suave: true }
    Repeater {
        model: dlg.d.resultados
        Rectangle {
            required property var modelData
            Layout.fillWidth: true
            height: 36; radius: 6
            color: modelData.elegido ? tema.color.tinta : (zona.containsMouse ? tema.color.hoverNeutro : "transparent")
            Texto { anchors { left: parent.left; leftMargin: 10; verticalCenter: parent.verticalCenter } text: modelData.texto
                    color: modelData.elegido ? tema.color.seleccionTexto : tema.color.tinta; wrapMode: Text.NoWrap }
            MouseArea { id: zona; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: dlg.d.elegir(modelData.id) }
        }
    }
}
