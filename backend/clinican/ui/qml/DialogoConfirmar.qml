import QtQuick
import QtQuick.Layouts

DialogoMarco {
    textoPrincipal: d.accion
    principalPeligro: d.peligro
    textoCancelar: d.no
    enfocarCancelar: true
    enterPrincipal: false
    onPrincipal: d.aceptar()
    Texto { text: d.explicacion; suave: true; Layout.fillWidth: true }
}
