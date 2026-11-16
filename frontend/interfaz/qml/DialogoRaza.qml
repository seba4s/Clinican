import QtQuick
import QtQuick.Layouts

DialogoMarco {
    id: dlg
    textoIzquierda: d.inicial.editar ? "Dar de baja" : ""
    onIzquierda: d.baja()
    onPrincipal: d.guardar(nombre.texto, pelaje.texto)
    Component.onCompleted: nombre.enfocar()
    Campo { id: nombre; objectName: "nombreRaza"; titulo: "Nombre"; ancho: 400; texto: dlg.d.inicial.nombre }
    Texto { text: "Tamaño"; tamano: tema.medida.etiqueta + 1; negrita: true }
    Segmentado { opciones: dlg.d.opciones; valor: dlg.d.tamano; onElegido: (v) => dlg.d.elegir_tamano(v); Layout.topMargin: 4; Layout.bottomMargin: 10 }
    Campo { id: pelaje; objectName: "pelajeRaza"; titulo: "Pelaje (opcional)"; ancho: 400; texto: dlg.d.inicial.pelaje }
}
