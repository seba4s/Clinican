import QtQuick
import QtQuick.Layouts

DialogoMarco {
    id: dlg
    textoIzquierda: d.inicial.nueva ? "" : "Dar de baja…"
    onIzquierda: d.baja()
    onPrincipal: d.guardar(nombre.texto, raza.editText, complicado.checked, edad.texto, obs.texto)
    Component.onCompleted: nombre.enfocar()
    Campo { id: nombre; titulo: "Nombre"; ancho: 500; texto: dlg.d.inicial.nombre; error: dlg.d.errores.nombre || "" }
    GridLayout {
        columns: 2; columnSpacing: 20; rowSpacing: 4
        Texto { text: "Raza"; tamano: tema.medida.etiqueta + 1; negrita: true }
        Texto { text: "Tamaño"; tamano: tema.medida.etiqueta + 1; negrita: true }
        Combo {
            id: raza
            Layout.preferredWidth: 260
            model: dlg.d.nombresRazas
            Component.onCompleted: { currentIndex = Math.max(0, dlg.d.nombresRazas.indexOf(dlg.d.inicial.raza)); editText = dlg.d.inicial.raza }
            onActivated: (i) => dlg.d.raza_cambio(dlg.d.nombresRazas[i])
        }
        Segmentado { opciones: dlg.d.tamanos; valor: dlg.d.tamano; onElegido: (v) => dlg.d.elegir_tamano(v) }
    }
    Casilla { id: complicado; text: "Pelaje complicado (va al cupo COMPLICADO; obligatorio revisar en mestizos)"
              checked: dlg.d.inicial.complicado; Layout.fillWidth: true; Layout.topMargin: 6; Layout.bottomMargin: 8 }
    Campo { id: edad; visible: dlg.d.inicial.nueva; titulo: "Edad en años (opcional)"; ancho: 120; error: dlg.d.errores.edad || "" }
    AreaTexto { id: obs; titulo: "Observaciones"; alto: 70; texto: dlg.d.inicial.observaciones; Layout.fillWidth: true }
}
