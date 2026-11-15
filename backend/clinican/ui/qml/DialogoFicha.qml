import QtQuick
import QtQuick.Layouts

DialogoMarco {
    id: dlg
    textoPrincipal: d.textoGuardar
    textoCancelar: d.textoCancelar
    enterPrincipal: false
    onPrincipal: {
        var marcados = []
        for (var i = 0; i < servicios.count; i++) if (servicios.itemAt(i).checked) marcados.push(servicios.itemAt(i).text)
        d.guardar(marcados, corte.texto, obs.texto, porcentaje.texto, avance.texto, precio.texto)
    }

    Texto { text: "Servicios realizados"; tamano: tema.medida.etiqueta + 1; negrita: true }
    Flow {
        Layout.fillWidth: true
        Layout.bottomMargin: 8
        spacing: 14
        Repeater {
            id: servicios
            model: dlg.d.servicios
            Casilla { required property var modelData; text: modelData.nombre; checked: modelData.marcado }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        spacing: 16
        AreaTexto { id: corte; titulo: "Detalles del corte"; texto: dlg.d.corte; Layout.fillWidth: true; Layout.preferredWidth: 1 }
        AreaTexto { id: obs; titulo: "Observaciones"; texto: dlg.d.observaciones; Layout.fillWidth: true; Layout.preferredWidth: 1 }
    }
    Rectangle {
        Layout.fillWidth: true
        Layout.topMargin: 6
        implicitHeight: sesion.implicitHeight + 20
        radius: 10
        color: tema.color.superficieSuave
        ColumnLayout {
            id: sesion
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14; topMargin: 10 }
            Texto { text: dlg.d.sesion; tamano: tema.medida.etiqueta + 1; negrita: true; Layout.fillWidth: true }
            RowLayout {
                spacing: 14
                Campo { id: porcentaje; titulo: "Avance %"; ancho: 100; error: dlg.d.errores.porcentaje || "" }
                Campo { id: avance; titulo: "Qué se avanzó"; ancho: 480 }
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        Layout.topMargin: 6
        spacing: 16
        Campo {
            id: precio
            titulo: "Precio final"
            ancho: 180
            texto: dlg.d.precio
            error: dlg.d.errores.precio || ""
            onEditado: (t) => dlg.d.cuenta(t)
        }
        Texto { text: dlg.d.notaPrecio; tamano: tema.medida.etiqueta + 1; suave: true; Layout.fillWidth: true }
    }
    Texto { text: dlg.d.cobrar; tamano: tema.medida.subtitulo; negrita: true; Layout.alignment: Qt.AlignRight }
}
