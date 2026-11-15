import QtQuick

Rectangle {
    property alias texto: t.text
    property color letra: tema.color.tinta
    property int tamano: tema.medida.etiqueta
    implicitHeight: tamano + 12
    implicitWidth: t.implicitWidth + 20
    radius: height / 2
    Texto { id: t; anchors.centerIn: parent; tamano: parent.tamano; negrita: true; color: parent.letra; wrapMode: Text.NoWrap }
}
