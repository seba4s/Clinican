import QtQuick
import QtQuick.Layouts

DialogoMarco {
    id: dlg
    textoPrincipal: "Registrar abono"
    onPrincipal: d.registrar(valor.texto)
    Component.onCompleted: valor.enfocar()
    Campo {
        id: valor
        titulo: "Valor recibido"
        ancho: 200
        texto: dlg.d.inicial
        error: dlg.d.errores.valor || ""
        onEditado: (t) => dlg.d.validar("valor", t)
    }
}
