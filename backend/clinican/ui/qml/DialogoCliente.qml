import QtQuick
import QtQuick.Layouts

DialogoMarco {
    id: dlg
    onPrincipal: d.guardar(nombre.texto, cedula.texto, celular.texto, direccion.texto, autorizo.checked, fecha.texto, medio.texto)
    Component.onCompleted: nombre.enfocar()
    Campo { id: nombre; titulo: "Nombre"; ancho: 460; texto: dlg.d.inicial.nombre; error: dlg.d.errores.nombre || "" }
    RowLayout {
        spacing: 20
        Campo { id: cedula; objectName: "cedulaCliente"; titulo: "Cédula"; ancho: 220; texto: dlg.d.inicial.cedula; error: dlg.d.errores.cedula || ""
                onEditado: (t) => dlg.d.validar("cedula", t) }
        Campo { id: celular; objectName: "celularCliente"; titulo: "Celular"; ancho: 220; texto: dlg.d.inicial.celular; error: dlg.d.errores.celular || ""
                onEditado: (t) => dlg.d.validar("celular", t) }
    }
    Campo { id: direccion; titulo: "Dirección (opcional)"; ancho: 460; texto: dlg.d.inicial.direccion }
    Casilla { id: autorizo; text: "Autorizó el tratamiento de sus datos (Ley 1581 de 2012)"; checked: dlg.d.inicial.autorizo
              Layout.fillWidth: true; Layout.topMargin: 4; Layout.bottomMargin: 6 }
    RowLayout {
        spacing: 20
        Campo { id: fecha; titulo: "Fecha de la autorización o el retiro"; ancho: 220; placeholder: "dd/mm/aaaa"
                texto: dlg.d.inicial.fecha; error: dlg.d.errores.fecha || "" }
        Campo { id: medio; titulo: "Cómo (opcional)"; ancho: 220; placeholder: "Formato firmado, WhatsApp…"; texto: dlg.d.inicial.medio }
    }
}
