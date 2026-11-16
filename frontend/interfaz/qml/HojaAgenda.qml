import QtQuick
import QtQuick.Controls

Item {
    id: hoja
    required property var p
    readonly property var pesos: [0.75, 0.95, 1.15, 1.0, 1.25, 1.3, 1.3, 1.05, 1.4]
    readonly property var titulos: ["Hora", "Cupo", "Mascota", "Raza", "Servicio", "Propietario", "Celular", "Abono", "Estado"]
    readonly property real totalPesos: 10.4
    readonly property int anchoHora: 64
    readonly property int altoFila: 34
    readonly property int pad: 10
    property var xs: {
        var r = [0, anchoHora], ancho = Math.max(0, lista.width - anchoHora)
        for (var i = 1; i < pesos.length; i++) r.push(r[i] + ancho * pesos[i] / totalPesos)
        return r
    }
    function irA(turnoId) {
        var g = p.grupos
        for (var i = 0; i < g.length; i++)
            for (var j = 0; j < g[i].filas.length; j++)
                if (g[i].filas[j].id === turnoId) { lista.positionViewAtIndex(i, ListView.Contain); return }
    }

    property var grupos: p.grupos
    onGruposChanged: {
        var y = lista.contentY
        lista.model = grupos
        lista.contentY = Math.max(0, Math.min(y, lista.contentHeight - lista.height))
    }
    Connections { target: hoja.p; function onIrAFila(id) { Qt.callLater(hoja.irA, id) } }

    Rectangle {
        id: encabezado
        width: parent.width - 10
        height: 36
        radius: 8
        color: tema.color.verde
        Rectangle { anchors { left: parent.left; right: parent.right; bottom: parent.bottom } height: 8; color: parent.color }
        Repeater {
            model: hoja.titulos
            Item {
                required property int index
                required property string modelData
                x: hoja.xs[index]; width: hoja.xs[index + 1] - hoja.xs[index]; height: 36
                Rectangle { visible: index > 0; width: 1; height: parent.height; color: tema.color.verdeLinea }
                Texto { x: hoja.pad; anchors.verticalCenter: parent.verticalCenter; text: modelData; negrita: true
                        tamano: tema.medida.etiqueta + 1; color: tema.color.tintaSobreVerde }
            }
        }
    }

    Texto {
        anchors { top: encabezado.bottom; topMargin: 48; horizontalCenter: encabezado.horizontalCenter }
        visible: hoja.p.cerrado !== ""
        text: hoja.p.cerrado; tamano: tema.medida.subtitulo; suave: true
    }

    ListView {
        id: lista
        objectName: "hojaLista"
        anchors { top: encabezado.bottom; left: parent.left; right: parent.right; bottom: parent.bottom; rightMargin: 10 }
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { parent: hoja; x: hoja.width - width; y: lista.y; height: lista.height; policy: ScrollBar.AsNeeded }
        delegate: Item {
            id: grupo
            required property var modelData
            readonly property var g: modelData
            width: lista.width
            readonly property real filasFranja: (g.filas[0].tipo === "turno" || g.filas[0].tipo === "libre")
                                                ? Math.max(2, g.filas.length) : g.filas.length
            readonly property real alturaFila: height / g.filas.length
            height: filasFranja * hoja.altoFila

            Rectangle {
                width: hoja.xs[1]; height: parent.height
                color: grupo.g.bloqueo ? tema.color.verde : tema.color.fondoHora
                Rectangle { visible: grupo.g.actual; width: 4; height: parent.height; color: tema.color.accion }
                Texto {
                    x: hoja.pad; y: (grupo.height - height) / 2
                    width: parent.width - hoja.pad * 1.5
                    text: grupo.g.hora; negrita: true; tamano: tema.medida.etiqueta + 1; elide: Text.ElideRight; wrapMode: Text.NoWrap
                    color: grupo.g.bloqueo ? tema.color.tintaSobreVerde
                         : grupo.g.actual ? tema.color.accion : (grupo.g.pasada ? tema.color.tintaSuave : tema.color.tinta)
                }
            }
            Column {
                x: hoja.xs[1]
                width: parent.width - x
                Repeater {
                    model: grupo.g.filas
                    delegate: Fila { required property var modelData; f: modelData; alto: grupo.alturaFila; width: parent.width }
                }
            }
            Rectangle { x: hoja.xs[1]; width: 1; height: parent.height; color: tema.color.linea }
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: tema.color.linea }
        }
    }

    component Fila: Item {
        id: fila
        property var f
        property real alto: hoja.altoFila
        readonly property bool esTurno: f.tipo === "turno"
        readonly property bool elegida: esTurno && f.id === hoja.p.seleccionado
        readonly property real x0: hoja.xs[1]
        height: alto
        function cx(i) { return hoja.xs[i] - x0 }
        function ancho(i) { return hoja.xs[i + 1] - hoja.xs[i] }

        Rectangle {
            anchors.fill: parent
            visible: fila.f.tipo === "bloqueo"
            color: tema.color.verde
            Texto { x: hoja.pad; anchors.verticalCenter: parent.verticalCenter; text: fila.f.texto || ""; negrita: true
                    tamano: tema.medida.etiqueta + 1; color: tema.color.tintaSobreVerde; elide: Text.ElideRight
                    width: parent.width - 2 * hoja.pad; wrapMode: Text.NoWrap }
        }
        Texto {
            visible: fila.f.tipo === "pasada"
            x: hoja.pad; anchors.verticalCenter: parent.verticalCenter
            text: "Sin turnos"
            tamano: tema.medida.etiqueta + 1; suave: true
        }
        Rectangle { visible: fila.f.tipo !== "bloqueo"; x: fila.cx(2); width: 1; height: parent.height; color: tema.color.linea }
        Rectangle { visible: fila.f.tipo !== "bloqueo"; anchors.bottom: parent.bottom; width: parent.width; height: 1; color: tema.color.linea }

        Item {
            objectName: "libre"
            anchors.fill: parent
            visible: fila.f.tipo === "libre"
            Rectangle {
                anchors.fill: parent
                color: zonaLibre.containsMouse ? tema.color.hoverNeutro : "transparent"
                Behavior on color { ColorAnimation { duration: 120 } }
            }
            Repeater {
                model: fila.f.tipo === "libre" ? 8 : 0
                Item {
                    required property int index
                    x: fila.cx(index + 1); width: fila.ancho(index + 1); height: fila.alto
                    Rectangle { visible: index > 0; width: 1; height: parent.height; color: tema.color.linea }
                    Texto {
                        visible: index === 7
                        x: hoja.pad; width: parent.width - hoja.pad * 1.5
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Libre"
                        suave: true; elide: Text.ElideRight; wrapMode: Text.NoWrap
                        tamano: tema.medida.etiqueta + 1
                    }
                }
            }
            MouseArea { id: zonaLibre; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        enabled: fila.f.tipo === "libre"; onClicked: hoja.p.elegir_libre(fila.f.clave) }
        }

        Item {
            anchors.fill: parent
            visible: fila.esTurno
            Rectangle {
                anchors.fill: parent
                color: fila.elegida ? tema.color.fondoSeleccion : (zonaTurno.containsMouse ? tema.color.hoverNeutro : "transparent")
                Behavior on color { ColorAnimation { duration: 120 } }
            }
            Repeater {
                model: fila.esTurno ? fila.f.celdas : []
                Item {
                    required property int index
                    required property string modelData
                    x: fila.cx(index + 1); width: fila.ancho(index + 1); height: fila.alto
                    Rectangle { visible: index > 0; width: 1; height: parent.height; color: tema.color.linea }
                    Texto {
                        x: hoja.pad; width: parent.width - hoja.pad * 1.5
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData; elide: Text.ElideRight; wrapMode: Text.NoWrap
                        tamano: tema.medida.etiqueta + 1; negrita: index === 1
                        color: fila.f.atenuado ? tema.color.tintaSuave : tema.color.tinta
                    }
                }
            }
            Rectangle {
                readonly property var e: fila.esTurno ? (tema.estados[fila.f.estado] || ({})) : ({})
                x: fila.cx(8) + 4; width: fila.ancho(8) - 8
                height: Math.min(fila.alto - 10, 26); y: (fila.alto - height) / 2; radius: 4
                color: e.fondo || "transparent"
                Rectangle { x: -4; width: 1; height: fila.alto; y: -parent.y; color: tema.color.linea }
                Texto { x: hoja.pad - 4; width: parent.width - hoja.pad; anchors.verticalCenter: parent.verticalCenter
                        text: fila.f.estadoTexto || ""; negrita: true; tamano: tema.medida.etiqueta + 1
                        color: parent.e.letra || tema.color.tinta; elide: Text.ElideRight; wrapMode: Text.NoWrap }
            }
            Rectangle { anchors.fill: parent; anchors.margins: 1; color: "transparent"; visible: fila.elegida
                        border.width: 2; border.color: tema.color.accion }
            MouseArea { id: zonaTurno; anchors.fill: parent; hoverEnabled: true; enabled: fila.esTurno; cursorShape: Qt.PointingHandCursor
                        onClicked: hoja.p.seleccionar(fila.f.id) }
        }
    }
}
