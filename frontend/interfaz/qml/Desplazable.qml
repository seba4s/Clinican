import QtQuick
import QtQuick.Controls

ScrollView {
    id: v
    default property alias contenido: columna.data
    property alias columna: columna
    property int separacion: 0
    clip: true
    contentWidth: availableWidth
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
    Column {
        id: columna
        width: v.availableWidth
        spacing: v.separacion
    }
}
