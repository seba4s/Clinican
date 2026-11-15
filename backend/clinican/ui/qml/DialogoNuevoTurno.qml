import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

DialogoMarco {
    id: dlg
    textoPrincipal: d.textoBoton
    onPrincipal: d.agendar(abono.texto)
    Component.onCompleted: buscar.enfocar()

    Campo {
        id: buscar
        titulo: "Cliente"
        Layout.fillWidth: true
        placeholder: "Cédula, nombre, celular o mascota"
        texto: dlg.d.textoCliente
        onEditado: (t) => dlg.d.buscar(t)
    }
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 0
        RowLayout {
            visible: dlg.d.sinResultados
            Texto { text: "No hay clientes con ese dato."; suave: true }
            Boton { text: "Crear cliente nuevo"; tipo: "enlace"; onClicked: dlg.d.cliente_nuevo(buscar.texto) }
        }
        Repeater {
            model: dlg.d.resultados
            Rectangle {
                required property var modelData
                Layout.fillWidth: true
                height: 36; radius: 6
                color: zona.containsMouse ? tema.color.hoverNeutro : "transparent"
                Texto { anchors { left: parent.left; leftMargin: 10; verticalCenter: parent.verticalCenter } text: modelData.texto; wrapMode: Text.NoWrap }
                MouseArea { id: zona; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: { dlg.d.elegir_cliente(modelData.id); buscar.texto = dlg.d.textoCliente } }
            }
        }
    }
    Rectangle {
        visible: dlg.d.cliente.nombre !== undefined
        Layout.fillWidth: true
        implicitHeight: 46
        radius: 10
        color: tema.color.superficieSuave
        RowLayout {
            anchors { fill: parent; leftMargin: 14; rightMargin: 8 }
            spacing: 6
            Texto { text: dlg.d.cliente.nombre || ""; negrita: true; wrapMode: Text.NoWrap }
            Texto { text: dlg.d.cliente.linea || ""; suave: true; wrapMode: Text.NoWrap; Layout.fillWidth: true; elide: Text.ElideRight }
            Repeater {
                model: dlg.d.cliente.chips || []
                Chip {
                    required property var modelData
                    readonly property var e: tema.estados[modelData.estado] || ({})
                    texto: modelData.texto; color: e.fondo || "transparent"; letra: e.letra || tema.color.tinta
                }
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        Layout.topMargin: 8
        spacing: 20
        ColumnLayout {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.alignment: Qt.AlignTop
            spacing: 4
            Texto { text: "Mascota"; tamano: tema.medida.etiqueta + 1; negrita: true }
            Texto { visible: dlg.d.cliente.nombre !== undefined && dlg.d.listaMascotas.length === 0; Layout.fillWidth: true; suave: true
                    text: "Este cliente no tiene mascotas activas. Agrégala en Clientes." }
            Repeater {
                model: dlg.d.listaMascotas
                Opcion {
                    required property var modelData
                    text: modelData.texto
                    checked: modelData.id === dlg.d.mascotaId
                    onClicked: dlg.d.elegir_mascota(modelData.id)
                }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.alignment: Qt.AlignTop
            spacing: 4
            Texto { text: "Servicio"; tamano: tema.medida.etiqueta + 1; negrita: true }
            Repeater {
                model: dlg.d.servicios
                Opcion {
                    required property var modelData
                    text: modelData.texto
                    checked: modelData.valor === dlg.d.servicio
                    onClicked: dlg.d.elegir_servicio(modelData.valor)
                }
            }
        }
    }
    Rectangle {
        Layout.fillWidth: true
        Layout.topMargin: 4
        implicitHeight: categoria.implicitHeight + 12
        radius: 8
        color: tema.color.superficieSuave
        Texto { id: categoria; anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 8 }
                text: dlg.d.textoCategoria; tamano: tema.medida.etiqueta + 1 }
    }
    Texto { text: "Hora"; tamano: tema.medida.etiqueta + 1; negrita: true; Layout.topMargin: 6 }
    SelectorHora { d: dlg.d; Layout.fillWidth: true }
    RowLayout {
        Layout.fillWidth: true
        Layout.topMargin: 8
        Texto { text: dlg.d.resumen; Layout.fillWidth: true; Layout.alignment: Qt.AlignBottom; Layout.bottomMargin: 20 }
        Campo {
            id: abono
            titulo: "Abono recibido ahora"
            ancho: 180
            placeholder: "$0"
            error: dlg.d.errores.abono || ""
            onEditado: (t) => dlg.d.validar("abono", t)
        }
    }
}
