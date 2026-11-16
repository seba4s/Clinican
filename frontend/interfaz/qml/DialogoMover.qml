import QtQuick
import QtQuick.Layouts

DialogoMarco {
    id: dlg
    textoPrincipal: "Mover"
    onPrincipal: d.aceptar()
    SelectorHora { d: dlg.d; Layout.fillWidth: true }
}
