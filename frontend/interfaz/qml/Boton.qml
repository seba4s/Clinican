import QtQuick
import QtQuick.Controls

Button {
    id: b
    property string tipo: "secundario"
    property int alto: tema.medida.altoControl
    property bool alInicio: tipo === "peligro" || tipo === "enlace"
    readonly property bool lleno: tipo === "principal" || tipo === "peligroLleno"
    implicitHeight: alto
    implicitWidth: Math.max(alto, etiqueta.implicitWidth + 32)
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    font.family: tema.familia
    font.pixelSize: tema.medida.cuerpo
    font.weight: Font.DemiBold
    scale: b.down ? 0.97 : 1
    Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }

    contentItem: Text {
        id: etiqueta
        text: b.text
        font: b.font
        elide: Text.ElideRight
        horizontalAlignment: b.alInicio ? Text.AlignLeft : Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        opacity: b.enabled ? 1 : 0.45
        color: b.tipo === "principal" ? "#FFFFFF"
             : b.tipo === "peligroLleno" ? (tema.oscuro ? "#14121D" : "#FFFFFF")
             : b.tipo === "peligro" ? tema.color.peligro
             : b.tipo === "enlace" ? tema.color.enlace
             : tema.color.tinta
    }
    background: Rectangle {
        radius: tema.medida.radio
        color: b.tipo === "principal" ? (b.hovered ? tema.color.accionHover : tema.color.accion)
             : b.tipo === "peligroLleno" ? tema.color.peligro
             : b.tipo === "secundario" ? (b.hovered ? tema.color.hoverNeutro : tema.color.vidrioFuerte)
             : (b.hovered ? tema.color.hoverNeutro : "transparent")
        border.width: b.visualFocus ? 2 : (b.tipo === "secundario" ? 1 : 0)
        border.color: b.visualFocus ? tema.color.tinta : tema.color.bordeCampo
        opacity: b.enabled ? 1 : 0.6
        Behavior on color { ColorAnimation { duration: 140 } }
        Rectangle {
            visible: b.lleno
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 1 }
            height: parent.height / 2
            radius: parent.radius
            gradient: Gradient {
                GradientStop { position: 0; color: "#33FFFFFF" }
                GradientStop { position: 1; color: "#00FFFFFF" }
            }
        }
    }
}
