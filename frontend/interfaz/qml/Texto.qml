import QtQuick

Text {
    property int tamano: tema.medida.cuerpo
    property bool negrita: false
    property bool suave: false
    font.family: tema.familia
    font.pixelSize: tamano
    font.weight: negrita ? Font.DemiBold : Font.Normal
    font.features: { "tnum": 1 }
    color: suave ? tema.color.tintaSuave : tema.color.tinta
    wrapMode: Text.WordWrap
    textFormat: Text.PlainText
    verticalAlignment: Text.AlignVCenter
}
