import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

// Clientes: lista con búsqueda a la izquierda y la ficha del propietario a la derecha.
Item {
    id: pagina
    readonly property var p: app.clientes
    readonly property var d: p.detalle
    Connections {
        target: app
        function onEnfocarBusqueda() { buscar.forceActiveFocus(); buscar.selectAll() }
    }
    Connections { target: pagina.p; function onLimpiarBusqueda() { buscar.text = "" } }

    FileDialog {
        id: selector
        title: "Elegir el archivo de mascotas"
        nameFilters: ["Excel (*.xlsx)", "Todos (*)"]
        onAccepted: pagina.p.importar(selectedFile.toString())
    }

    RowLayout {
        anchors { fill: parent; leftMargin: 24; rightMargin: 24; topMargin: 20; bottomMargin: 20 }
        spacing: 24

        ColumnLayout {
            Layout.preferredWidth: 320
            Layout.fillHeight: true
            spacing: 6
            Entrada {
                id: buscar
                objectName: "buscarCliente"
                Layout.fillWidth: true
                placeholderText: "Cédula, nombre, celular o mascota"
                onTextEdited: pagina.p.buscar(text)
                background: Rectangle {
                    radius: tema.medida.radio
                    color: tema.color.superficie
                    border.width: 2
                    border.color: tema.color.tinta
                }
            }
            Texto { text: pagina.p.cuenta; tamano: tema.medida.etiqueta; suave: true }
            ListView {
                id: lista
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 2
                model: pagina.p.lista
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar { }
                Texto { visible: lista.count === 0; text: "Nadie coincide con esa búsqueda."; suave: true; y: 8 }
                delegate: Rectangle {
                    required property var modelData
                    readonly property bool elegido: modelData.id === pagina.p.seleccionado
                    width: lista.width
                    height: 54
                    radius: tema.medida.radio
                    color: elegido ? tema.color.vidrioFuerte : (zona.containsMouse ? tema.color.hoverNeutro : "transparent")
                    border.width: elegido ? 2 : 0
                    border.color: tema.color.tinta
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Column {
                        anchors { left: parent.left; right: parent.right; leftMargin: 12; rightMargin: 8; verticalCenter: parent.verticalCenter }
                        Texto { width: parent.width; text: modelData.nombre; negrita: elegido; tamano: tema.medida.etiqueta + 1; elide: Text.ElideRight; wrapMode: Text.NoWrap }
                        Texto { width: parent.width; text: modelData.linea2; tamano: tema.medida.etiqueta + 1; elide: Text.ElideRight; wrapMode: Text.NoWrap }
                    }
                    MouseArea { id: zona; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: pagina.p.elegir(modelData.id) }
                }
            }
            Boton { text: "+ Cliente nuevo"; Layout.fillWidth: true; Layout.topMargin: 4; onClicked: pagina.p.nuevo() }
            Boton { text: "Importar mascotas desde Excel…"; tipo: "enlace"; Layout.fillWidth: true
                    onClicked: if (pagina.p.puede_importar()) selector.open() }
        }

        Desplazable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            separacion: 0

            Texto { visible: pagina.d.vacio; text: "Busca un cliente o elige uno de la lista."; tamano: tema.medida.subtitulo; suave: true; topPadding: 20 }

            Column {
                visible: !pagina.d.vacio
                width: parent.width
                spacing: 0
                RowLayout {
                    width: parent.width
                    spacing: tema.medida.sep
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        Texto { text: pagina.d.nombre || ""; tamano: tema.medida.titulo; negrita: true; Layout.fillWidth: true }
                        Texto { text: pagina.d.linea || ""; suave: true; Layout.fillWidth: true }
                    }
                    Boton { text: "Editar"; onClicked: pagina.p.editar() }
                    Boton { text: "Unir con otro…"; onClicked: pagina.p.unir() }
                    Boton { text: "+ Nuevo turno"; tipo: "principal"; onClicked: pagina.p.nuevo_turno_cliente() }
                    Boton { objectName: "cerrarCliente"; text: "Cerrar"; onClicked: pagina.p.cerrar() }
                }
                Item { width: 1; height: 16 }
                RowLayout {
                    width: parent.width
                    spacing: 12
                    Repeater {
                        model: pagina.d.vacio ? [] : pagina.d.metricas
                        Tarjeta {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            Layout.fillHeight: true
                            implicitHeight: metrica.implicitHeight + 24
                            Column {
                                id: metrica
                                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16; topMargin: 12 }
                                Texto { width: parent.width; text: modelData.titulo; tamano: tema.medida.etiqueta; suave: true }
                                Texto { width: parent.width; text: modelData.valor; tamano: tema.medida.subtitulo; negrita: true }
                                Texto { width: parent.width; text: modelData.nota; tamano: tema.medida.etiqueta; suave: true }
                            }
                        }
                    }
                }
                RowLayout {
                    width: parent.width
                    Texto { text: "Mascotas"; tamano: tema.medida.subtitulo; negrita: true; Layout.fillWidth: true; topPadding: 20; bottomPadding: 6 }
                    Boton { text: "+ Mascota"; tipo: "enlace"; Layout.alignment: Qt.AlignBottom; onClicked: pagina.p.nueva_mascota() }
                }
                Texto { visible: !pagina.d.vacio && pagina.d.mascotas.length === 0; text: "Todavía no tiene mascotas."; suave: true }
                GridLayout {
                    width: parent.width
                    columns: 2
                    columnSpacing: 12
                    rowSpacing: 12
                    Repeater {
                        model: pagina.d.vacio ? [] : pagina.d.mascotas
                        Tarjeta {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            implicitHeight: tarjetaMascota.implicitHeight + 22
                            ColumnLayout {
                                id: tarjetaMascota
                                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16; topMargin: 10 }
                                spacing: 2
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 10
                                    Texto { text: modelData.nombre; tamano: 17; negrita: true; wrapMode: Text.NoWrap }
                                    Chip { texto: modelData.cupo; color: tema.color.superficieSuave }
                                    Item { Layout.fillWidth: true }
                                    Boton { text: "Turno"; tipo: "enlace"; alto: 30; onClicked: pagina.p.turno_mascota(modelData.id) }
                                    Boton { text: "Editar"; tipo: "enlace"; alto: 30; onClicked: pagina.p.editar_mascota(modelData.id) }
                                }
                                Texto { text: modelData.detalle; tamano: tema.medida.etiqueta + 1; suave: true; Layout.fillWidth: true }
                                Texto { visible: modelData.obs !== ""; text: modelData.obs; tamano: tema.medida.etiqueta; suave: true; Layout.fillWidth: true }
                            }
                        }
                    }
                }
                Texto { text: "Historial"; tamano: tema.medida.subtitulo; negrita: true; topPadding: 20; bottomPadding: 6 }
                Tarjeta {
                    width: parent.width
                    implicitHeight: tabla.implicitHeight + 20
                    GridLayout {
                        id: tabla
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16; topMargin: 10 }
                        columns: 5
                        columnSpacing: 24
                        rowSpacing: 8
                        Repeater {
                            model: ["Fecha", "Mascota", "Servicio", "Estado", "Precio final"]
                            Texto { required property string modelData; required property int index; text: modelData; tamano: tema.medida.etiqueta
                                    negrita: true; suave: true; Layout.fillWidth: index === 4; horizontalAlignment: index === 4 ? Text.AlignRight : Text.AlignLeft }
                        }
                        Texto { visible: !pagina.d.vacio && pagina.d.historial.length === 0; text: "Sin turnos todavía."; suave: true; Layout.columnSpan: 5 }
                        Repeater {
                            model: pagina.d.vacio ? [] : pagina.d.historial
                            delegate: Repeater {
                                id: celdas
                                required property var modelData
                                readonly property var fila: modelData
                                model: 5
                                Item {
                                    required property int index
                                    Layout.fillWidth: index === 4
                                    implicitHeight: 30
                                    implicitWidth: index === 4 ? enlace.implicitWidth : celda.implicitWidth
                                    Texto {
                                        id: celda
                                        visible: index < 4 || celdas.fila.precio === ""
                                        anchors.verticalCenter: parent.verticalCenter
                                        anchors.right: index === 4 ? parent.right : undefined
                                        wrapMode: Text.NoWrap
                                        text: [celdas.fila.fecha, celdas.fila.mascota, celdas.fila.servicio, celdas.fila.estado, "—"][index]
                                        suave: index === 4
                                        color: index === 3 && celdas.fila.alerta ? (tema.estados["PENDIENTE_ABONO"] || {}).letra || tema.color.tinta
                                             : (index === 4 ? tema.color.tintaSuave : tema.color.tinta)
                                    }
                                    Boton {
                                        id: enlace
                                        visible: index === 4 && celdas.fila.precio !== ""
                                        anchors.right: parent.right
                                        text: celdas.fila.precio; tipo: "enlace"; alto: 30
                                        onClicked: pagina.p.ver_ficha(celdas.fila.turnoId)
                                    }
                                }
                            }
                        }
                    }
                }
                Item { width: 1; height: 8 }
            }
        }
    }
}
