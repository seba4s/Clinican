import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: pagina
    readonly property var p: app.ajustes
    readonly property var datos: p.datos

    RowLayout {
        anchors { fill: parent; leftMargin: 16; rightMargin: 24; topMargin: 20; bottomMargin: 20 }
        spacing: 24

        ColumnLayout {
            Layout.preferredWidth: 240
            Layout.maximumWidth: 240
            Layout.fillHeight: true
            spacing: 2
            Texto { text: "Ajustes"; tamano: tema.medida.titulo; negrita: true; leftPadding: 12; bottomPadding: 12 }
            Repeater {
                model: pagina.p.secciones
                Button {
                    id: b
                    required property string modelData
                    readonly property bool activo: modelData === pagina.p.seccion
                    objectName: "seccion" + modelData
                    Layout.fillWidth: true
                    implicitHeight: 38
                    hoverEnabled: true
                    focusPolicy: Qt.StrongFocus
                    onClicked: pagina.p.ir(modelData)
                    background: Rectangle {
                        radius: tema.medida.radio
                        color: b.activo ? tema.color.superficie : (b.hovered ? tema.color.hoverNeutro : "transparent")
                        border.width: b.activo || b.visualFocus ? 2 : 0
                        border.color: b.visualFocus && !b.activo ? tema.color.accion : tema.color.tinta
                        Behavior on color { ColorAnimation { duration: 120 } }
                    }
                    contentItem: Texto { text: b.modelData; negrita: b.activo; wrapMode: Text.NoWrap; elide: Text.ElideRight
                                         leftPadding: 4; verticalAlignment: Text.AlignVCenter }
                }
            }
            Item { Layout.fillHeight: true }
        }

        Desplazable {
            id: cuerpo
            objectName: "cuerpoAjustes"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Texto { text: pagina.p.tituloSeccion; tamano: 22; negrita: true }
            Texto { width: parent.width; text: pagina.p.explicacion; suave: true; topPadding: 2; bottomPadding: 16 }
            Loader {
                id: seccion
                objectName: "seccionAjustes"
                width: parent.width
                sourceComponent: ({
                    "Horario y bloqueos": horario,
                    "Cupos y abono": cupos,
                    "Precios": preciosC,
                    "Razas": razas,
                    "Recordatorios y WhatsApp": recordatorios,
                    "Respaldos": respaldosC,
                    "Registro de cambios": registro
                })[pagina.p.tituloSeccion] || null
                onLoaded: { item.opacity = 0; aparecer.restart() }
                NumberAnimation { id: aparecer; target: seccion.item; property: "opacity"; to: 1; duration: 180; easing.type: Easing.OutCubic }
            }
        }
    }

    component Columna: Texto { tamano: tema.medida.etiqueta; negrita: true; suave: true; wrapMode: Text.NoWrap }
    component Subtitulo: Texto { tamano: tema.medida.subtitulo; negrita: true }

    Component {
        id: horario
        Column {
            id: h
            function guardarHorario() {
                var filas = []
                for (var d = 0; d < dias.count; d++) {
                    var f = dias.itemAt(d)
                    filas.push({ abierto: f.abierto, desde: f.desde.texto, hasta: f.hasta.texto })
                }
                pagina.p.guardar_horario(filas)
            }
            Tarjeta {
                width: parent.width
                implicitHeight: tabla.implicitHeight + 28
                ColumnLayout {
                    id: tabla
                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16; topMargin: 14 }
                    spacing: 10
                    RowLayout {
                        spacing: 16
                        Columna { text: "Día"; Layout.preferredWidth: 100 }
                        Columna { text: "Abierto"; Layout.preferredWidth: 46 }
                        Columna { text: "Primera franja"; Layout.preferredWidth: 124 + 10 + 10 }
                        Columna { text: "Última franja" }
                    }
                    Repeater {
                        id: dias
                        model: pagina.datos.dias || []
                        RowLayout {
                            id: fila
                            required property var modelData
                            property bool abierto: modelData.abierto
                            property alias desde: desde
                            property alias hasta: hasta
                            spacing: 16
                            Texto { text: fila.modelData.nombre; negrita: fila.abierto; suave: !fila.abierto
                                    wrapMode: Text.NoWrap; Layout.preferredWidth: 100 }
                            Interruptor { checked: fila.abierto; onToggled: fila.abierto = checked; Layout.preferredWidth: 46 }
                            CampoHora { id: desde; horas: pagina.p.horas; texto: fila.modelData.desde; habilitado: fila.abierto }
                            Texto { text: "a"; suave: true; Layout.leftMargin: -6; Layout.rightMargin: -6 }
                            CampoHora { id: hasta; horas: pagina.p.horas; texto: fila.modelData.hasta; habilitado: fila.abierto }
                        }
                    }
                    Texto {
                        Layout.fillWidth: true
                        Layout.topMargin: 2
                        text: "Escribe la hora (por ejemplo 9, 9:30 o 4:30 pm) o elígela con ▾. Las flechas ↑ ↓ suben o bajan media hora."
                        tamano: tema.medida.etiqueta; suave: true
                    }
                }
            }
            Item { width: 1; height: 12 }
            Boton { objectName: "guardarHorario"; text: "Guardar horario"; tipo: "principal"; onClicked: h.guardarHorario() }
            Item { width: 1; height: 24 }
            RowLayout {
                width: parent.width
                Subtitulo { text: "Bloqueos de los próximos 60 días"; Layout.fillWidth: true }
                Boton { objectName: "bloquearHoras"; text: "Bloquear horas…"; onClicked: pagina.p.nuevo_bloqueo() }
            }
            Item { width: 1; height: 6 }
            Texto { visible: (pagina.datos.bloqueos || []).length === 0; text: "No hay bloqueos."; suave: true }
            Repeater {
                model: pagina.datos.bloqueos || []
                Item {
                    required property var modelData
                    width: parent.width
                    height: caja.height + 6
                    Tarjeta {
                        id: caja
                        width: parent.width
                        implicitHeight: 52
                        RowLayout {
                            anchors { fill: parent; leftMargin: 16; rightMargin: 8 }
                            Texto { text: modelData.texto; Layout.fillWidth: true }
                            Boton { objectName: "quitarBloqueo"; text: "Quitar"; tipo: "peligro"; onClicked: pagina.p.quitar_bloqueo(modelData.id) }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: cupos
        Column {
            spacing: 12
            Tarjeta {
                width: parent.width
                implicitHeight: campos.implicitHeight + 24
                ColumnLayout {
                    id: campos
                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16; topMargin: 12 }
                    spacing: 4
                    RowLayout {
                        spacing: 16
                        Repeater {
                            id: categorias
                            model: pagina.datos.categorias || []
                            Campo { required property var modelData; titulo: modelData.nombre; texto: modelData.cantidad; ancho: 110 }
                        }
                    }
                    RowLayout {
                        spacing: 16
                        Campo { id: abono; objectName: "abono"; titulo: "Abono"; texto: pagina.datos.abono || ""; ancho: 150 }
                        Campo { id: minutos; titulo: "Minutos para pagarlo"; texto: pagina.datos.minutos || ""; ancho: 150 }
                    }
                }
            }
            Boton {
                text: "Guardar"; tipo: "principal"
                onClicked: {
                    var cantidades = {}
                    var lista = pagina.datos.categorias || []
                    for (var i = 0; i < lista.length; i++) cantidades[lista[i].valor] = categorias.itemAt(i).texto
                    pagina.p.guardar_cupos(cantidades, abono.texto, minutos.texto)
                }
            }
        }
    }

    Component {
        id: preciosC
        Tarjeta {
            implicitHeight: tabla.implicitHeight + 24
            ColumnLayout {
                id: tabla
                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16; topMargin: 12 }
                spacing: 10
                RowLayout {
                    spacing: 24
                    Columna { text: "Cupo"; Layout.preferredWidth: 130 }
                    Columna { text: "Precio hoy"; Layout.preferredWidth: 100 }
                    Columna { text: "Historial"; Layout.fillWidth: true }
                }
                Repeater {
                    model: pagina.datos.precios || []
                    RowLayout {
                        id: fila
                        required property var modelData
                        spacing: 24
                        Texto { text: fila.modelData.nombre; negrita: true; wrapMode: Text.NoWrap; topPadding: 4
                                Layout.preferredWidth: 130; Layout.alignment: Qt.AlignTop }
                        Texto { text: fila.modelData.hoy; wrapMode: Text.NoWrap; topPadding: 4
                                Layout.preferredWidth: 100; Layout.alignment: Qt.AlignTop }
                        Column {
                            Layout.fillWidth: true
                            Layout.alignment: Qt.AlignTop
                            Repeater {
                                model: fila.modelData.historial
                                Row {
                                    required property var modelData
                                    spacing: 6
                                    Texto { anchors.verticalCenter: parent.verticalCenter; text: modelData.texto
                                            tamano: tema.medida.etiqueta + 1; negrita: modelData.futuro; suave: !modelData.futuro; wrapMode: Text.NoWrap }
                                    Boton { objectName: "corregir" + fila.modelData.categoria; text: "Corregir"; tipo: "enlace"; alto: 28
                                            onClicked: pagina.p.precio(fila.modelData.categoria, modelData.indice) }
                                }
                            }
                        }
                        Boton { objectName: "cambiar" + fila.modelData.categoria; text: "Cambiar…"; Layout.alignment: Qt.AlignTop
                                onClicked: pagina.p.precio(fila.modelData.categoria, -1) }
                    }
                }
            }
        }
    }

    Component {
        id: razas
        Column {
            spacing: 10
            Boton { objectName: "razaNueva"; text: "+ Raza nueva"; onClicked: pagina.p.raza(-1) }
            Tarjeta {
                width: parent.width
                implicitHeight: tabla.implicitHeight + 24
                ColumnLayout {
                    id: tabla
                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16; topMargin: 12 }
                    spacing: 2
                    RowLayout {
                        spacing: 24
                        Columna { text: "Raza"; Layout.preferredWidth: 220 }
                        Columna { text: "Tamaño"; Layout.preferredWidth: 110 }
                        Columna { text: "Pelaje"; Layout.fillWidth: true }
                    }
                    Repeater {
                        model: pagina.datos.razas || []
                        RowLayout {
                            id: fila
                            required property var modelData
                            spacing: 24
                            Texto { text: fila.modelData.nombre; Layout.preferredWidth: 220 }
                            Texto { text: fila.modelData.tamano; suave: true; Layout.preferredWidth: 110 }
                            Texto { text: fila.modelData.pelaje; suave: true; Layout.fillWidth: true }
                            Boton { objectName: "editarRaza"; text: "Editar"; tipo: "enlace"; alto: 30
                                    onClicked: pagina.p.raza(fila.modelData.id) }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: recordatorios
        Column {
            id: r
            spacing: 12
            property string canal: pagina.datos.canal || ""
            Tarjeta {
                width: parent.width
                implicitHeight: contenido.implicitHeight + 24
                ColumnLayout {
                    id: contenido
                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16; topMargin: 12 }
                    spacing: 2
                    Texto { text: "Canal"; tamano: tema.medida.etiqueta + 1; negrita: true }
                    ButtonGroup { id: grupo }
                    Repeater {
                        model: pagina.datos.canales || []
                        Opcion {
                            required property var modelData
                            objectName: "canal" + modelData.valor
                            text: modelData.texto
                            checked: modelData.valor === r.canal
                            ButtonGroup.group: grupo
                            onClicked: r.canal = modelData.valor
                        }
                    }
                    Texto {
                        Layout.fillWidth: true
                        Layout.topMargin: 4; Layout.bottomMargin: 8
                        text: "WhatsApp necesita el token y el número de WhatsApp Business configurados en Windows (ver README). "
                              + "Sin ellos, cada envío falla y queda en Recordatorios › Fallidos."
                        tamano: tema.medida.etiqueta; suave: true
                    }
                    RowLayout {
                        spacing: 16
                        Campo { id: horas; objectName: "horasAntes"; titulo: "Primer recordatorio (horas antes)"; ancho: 200
                                texto: pagina.datos.horas || ""; error: pagina.p.errores.horas || "" }
                        Campo { id: horasFinal; objectName: "horasAntesFinal"; titulo: "Último recordatorio (horas antes)"; ancho: 200
                                texto: pagina.datos.horasFinal || ""; error: pagina.p.errores.horasFinal || "" }
                    }
                }
            }
            Boton { objectName: "guardarRecordatorios"; text: "Guardar"; tipo: "principal"
                    onClicked: pagina.p.guardar_recordatorios(r.canal, horas.texto, horasFinal.texto) }
        }
    }

    Component {
        id: respaldosC
        Column {
            spacing: 10
            RowLayout {
                width: parent.width
                Texto { text: pagina.datos.ultimo || ""; Layout.fillWidth: true }
                Boton { objectName: "respaldar"; text: "Respaldar ahora"; tipo: "principal"; onClicked: pagina.p.respaldar() }
            }
            Tarjeta {
                width: parent.width
                implicitHeight: lista.implicitHeight + 20
                Column {
                    id: lista
                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16; topMargin: 10 }
                    spacing: 2
                    Texto { visible: (pagina.datos.copias || []).length === 0; text: "Todavía no hay respaldos."; suave: true }
                    Repeater {
                        model: pagina.datos.copias || []
                        RowLayout {
                            required property var modelData
                            width: parent.width
                            spacing: 12
                            Texto { text: modelData.nombre; wrapMode: Text.NoWrap }
                            Texto { text: modelData.tamano; tamano: tema.medida.etiqueta; suave: true; Layout.fillWidth: true }
                            Boton { objectName: "restaurar"; text: "Restaurar…"; tipo: "peligro"; alto: 32
                                    onClicked: pagina.p.restaurar(modelData.nombre) }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: registro
        Tarjeta {
            implicitHeight: tabla.implicitHeight + 24
            GridLayout {
                id: tabla
                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16; topMargin: 12 }
                columns: 3
                columnSpacing: 32
                rowSpacing: 4
                Columna { text: "Cuándo" }
                Columna { text: "Qué" }
                Columna { text: "Detalle"; Layout.fillWidth: true }
                Texto { visible: (pagina.datos.cambios || []).length === 0; text: "Todavía no hay cambios registrados."
                        suave: true; Layout.columnSpan: 3 }
                Repeater {
                    model: pagina.datos.cambios || []
                    delegate: Repeater {
                        id: celdas
                        required property var modelData
                        readonly property var fila: modelData
                        model: 3
                        Texto {
                            required property int index
                            text: celdas.fila[index]
                            tamano: index === 2 ? tema.medida.etiqueta : tema.medida.etiqueta + 1
                            suave: index === 2
                            wrapMode: index === 2 ? Text.WordWrap : Text.NoWrap
                            Layout.fillWidth: index === 2
                            Layout.preferredWidth: index === 2 ? 200 : -1
                            Layout.alignment: Qt.AlignTop
                        }
                    }
                }
            }
        }
    }
}
