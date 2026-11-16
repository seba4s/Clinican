import QtQuick
import QtQuick.Layouts

DialogoMarco {
    id: dlg
    onPrincipal: d.guardar(valor.texto, desde.texto)
    Component.onCompleted: valor.enfocar()
    Campo { id: valor; objectName: "valorPrecio"; titulo: "Valor"; ancho: 180; texto: dlg.d.valor }
    Campo { id: desde; objectName: "desdePrecio"; visible: !dlg.d.corregir; titulo: "Desde (dd/mm/aaaa)"; ancho: 180; texto: dlg.d.desde }
}
