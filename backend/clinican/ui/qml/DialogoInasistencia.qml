import QtQuick
import QtQuick.Layouts

DialogoMarco {
    id: dlg
    textoPrincipal: "Marcar inasistencia"
    textoCancelar: "No, volver"
    onPrincipal: d.marcar(avisó.checked, cuando.texto)
    Opcion { id: noAvisó; text: "No avisó"; checked: true }
    Opcion { id: avisó; text: "Avisó antes" }
    Campo {
        id: cuando
        visible: avisó.checked
        titulo: "Cuándo avisó (dd/mm/aaaa hh:mm)"
        ancho: 240
        texto: dlg.d.inicial
        error: dlg.d.errores.cuando || ""
        Layout.topMargin: 8
    }
}
