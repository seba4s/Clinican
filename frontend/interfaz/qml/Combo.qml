import QtQuick
import QtQuick.Controls

ComboBox {
    id: c
    editable: true
    implicitHeight: tema.medida.altoControl
    font.family: tema.familia
    font.pixelSize: tema.medida.cuerpo
    property string texto: editText
    contentItem: TextField {
        text: c.editText
        onTextEdited: c.editText = text
        font: c.font
        color: tema.color.tinta
        leftPadding: 12
        verticalAlignment: Text.AlignVCenter
        selectByMouse: true
        background: null
    }
    indicator: Texto { x: c.width - width - 12; y: (c.height - height) / 2; text: "▾"; suave: true }
    background: Rectangle {
        radius: tema.medida.radio
        color: tema.color.superficie
        border.width: c.activeFocus ? 2 : 1
        border.color: c.activeFocus ? tema.color.tinta : tema.color.bordeCampo
    }
    delegate: ItemDelegate {
        required property int index
        required property string modelData
        width: c.width
        highlighted: c.highlightedIndex === index
        contentItem: Texto { text: modelData; negrita: c.currentIndex === index }
        background: Rectangle { color: highlighted ? tema.color.hoverNeutro : "transparent"; radius: 6 }
    }
    popup: Popup {
        y: c.height + 4
        width: c.width
        implicitHeight: Math.min(contentItem.implicitHeight + 12, 320)
        padding: 6
        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: c.popup.visible ? c.delegateModel : null
            currentIndex: c.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator { }
        }
        background: Rectangle { radius: tema.medida.radio; color: tema.color.superficie; border.color: tema.color.bordeCampo }
    }
}
