import QtQuick
import QtQuick.Layouts

DialogoMarco {
    id: dlg
    textoPrincipal: "Bloquear"
    onPrincipal: d.bloquear(fecha.texto, completo.checked, desde.texto, hasta.texto, motivo.texto)
    Campo { id: fecha; titulo: "Día (dd/mm/aaaa)"; ancho: 180; texto: dlg.d.fecha; error: dlg.d.errores.fecha || "" }
    Casilla { id: completo; text: "Todo el día"; Layout.bottomMargin: 4 }
    GridLayout {
        visible: !completo.checked
        columns: 2; columnSpacing: 16; rowSpacing: 4
        Texto { text: "Desde"; tamano: tema.medida.etiqueta + 1; negrita: true }
        Texto { text: "Hasta"; tamano: tema.medida.etiqueta + 1; negrita: true }
        CampoHora { id: desde; horas: dlg.d.horas; texto: "12:00" }
        CampoHora { id: hasta; horas: dlg.d.horas; texto: "13:00" }
    }
    Campo { id: motivo; titulo: "Motivo"; ancho: 300; texto: "Almuerzo"; Layout.topMargin: 10 }
}
