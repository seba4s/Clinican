import QtQuick
import QtQuick.Layouts

// Recordatorios: la bandeja de salida.
Item {
    id: pagina
    readonly property var p: app.recordatorios
    Desplazable {
        anchors { fill: parent; leftMargin: 24; rightMargin: 24; topMargin: 20; bottomMargin: 20 }
        RowLayout {
            width: parent.width
            Texto { text: "Recordatorios"; tamano: tema.medida.titulo; negrita: true; Layout.fillWidth: true }
            Texto { text: pagina.p.canal; tamano: tema.medida.etiqueta + 1; suave: true }
        }
        Item { width: 1; height: 16 }
        RowLayout {
            width: parent.width
            spacing: 12
            Repeater {
                model: pagina.p.metricas
                Tarjeta {
                    required property var modelData
                    readonly property var e: tema.estados["PENDIENTE_ABONO"] || ({})
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.fillHeight: true
                    implicitHeight: col.implicitHeight + 24
                    color: modelData.alerta ? e.fondo : tema.color.vidrio
                    Column {
                        id: col
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16; topMargin: 12 }
                        Texto { text: modelData.titulo; tamano: tema.medida.etiqueta; negrita: modelData.alerta; suave: !modelData.alerta
                                color: modelData.alerta ? parent.parent.e.letra : tema.color.tintaSuave }
                        Texto { text: modelData.valor; tamano: 24; negrita: true; color: modelData.alerta ? parent.parent.e.letra : tema.color.tinta }
                        Texto { text: modelData.nota; tamano: tema.medida.etiqueta; color: modelData.alerta ? parent.parent.e.letra : tema.color.tintaSuave }
                    }
                }
            }
        }
        Texto { visible: pagina.p.fallidas.length > 0; text: "Necesita atención"; tamano: tema.medida.subtitulo; negrita: true; topPadding: 20; bottomPadding: 6 }
        Repeater {
            model: pagina.p.fallidas
            Item {
                required property var modelData
                width: parent.width
                height: tarjeta.height + 8
                Tarjeta {
                    id: tarjeta
                    width: parent.width
                    implicitHeight: fila.implicitHeight + 24
                    RowLayout {
                        id: fila
                        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 16 }
                        spacing: tema.medida.sep
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            Texto { text: modelData.titulo; negrita: true; Layout.fillWidth: true }
                            Texto { text: modelData.detalle; suave: true; Layout.fillWidth: true }
                            Texto { visible: modelData.error !== ""; text: modelData.error; Layout.fillWidth: true
                                    color: (tema.estados["PENDIENTE_ABONO"] || {}).letra || tema.color.tinta }
                        }
                        Boton { visible: modelData.vigente; text: "Corregir celular"; onClicked: pagina.p.corregir(modelData.propietarioId) }
                        Boton { visible: modelData.vigente; text: "Reintentar ahora"; tipo: "principal"; onClicked: pagina.p.reintentar(modelData.id) }
                        Texto { visible: !modelData.vigente; text: "El turno ya pasó o cambió"; suave: true; wrapMode: Text.NoWrap }
                    }
                }
            }
        }
        Texto { text: "Próximos"; tamano: tema.medida.subtitulo; negrita: true; topPadding: 20; bottomPadding: 6 }
        Tarjeta {
            width: parent.width
            implicitHeight: tabla.implicitHeight + 20
            GridLayout {
                id: tabla
                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16; topMargin: 10 }
                columns: 4
                columnSpacing: 32
                rowSpacing: 8
                Repeater {
                    model: ["Sale", "Para", "Turno", "Intentos"]
                    Texto { required property string modelData; text: modelData; tamano: tema.medida.etiqueta; negrita: true; suave: true }
                }
                Texto { visible: pagina.p.proximas.length === 0; text: "No hay recordatorios por enviar."; suave: true; Layout.columnSpan: 4 }
                Repeater {
                    model: pagina.p.proximas
                    delegate: Repeater {
                        id: celdas
                        required property var modelData
                        readonly property var fila: modelData
                        model: 4
                        Texto { required property int index; text: celdas.fila[index]; wrapMode: Text.NoWrap; Layout.fillWidth: index === 3 }
                    }
                }
            }
        }
        Texto { width: parent.width; text: pagina.p.explicacion; tamano: tema.medida.etiqueta + 1; suave: true; topPadding: 12 }
    }
}
