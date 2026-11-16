import QtQuick
import QtQuick.Layouts

// Franja de aviso dentro de la ventana (éxito o error). Se cierra con su botón.
Item {
    id: a
    implicitHeight: app.avisoVisible ? caja.implicitHeight + 12 : 0
    clip: true
    Behavior on implicitHeight { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
    Rectangle {
        id: caja
        objectName: "aviso"
        anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: 12 }
        implicitHeight: Math.max(46, fila.implicitHeight + 16)
        radius: tema.medida.radio
        color: app.avisoError ? tema.color.avisoError : tema.color.avisoOk
        opacity: app.avisoVisible ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 180 } }
        RowLayout {
            id: fila
            anchors { fill: parent; leftMargin: 14; rightMargin: 8 }
            Texto { text: app.aviso; Layout.fillWidth: true; color: app.avisoError ? tema.color.peligro : tema.color.tinta }
            Boton { text: "Cerrar"; tipo: "enlace"; alto: 30; onClicked: app.ocultar_aviso() }
        }
    }
}
