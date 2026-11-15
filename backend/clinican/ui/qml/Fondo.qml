import QtQuick
import QtQuick.Shapes

// Fondo de la ventana: tres resplandores suaves con los colores de la marca, para que los
// paneles de vidrio tengan algo que dejar ver. Solo decorativo.
Item {
    id: f
    Rectangle { anchors.fill: parent; color: tema.color.fondo }
    component Resplandor: Shape {
        id: r
        property real cx
        property real cy
        property real radio
        property color tinte
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeWidth: -1
            fillGradient: RadialGradient {
                centerX: r.cx; centerY: r.cy; centerRadius: r.radio
                focalX: r.cx; focalY: r.cy
                GradientStop { position: 0; color: r.tinte }
                GradientStop { position: 0.55; color: Qt.rgba(r.tinte.r, r.tinte.g, r.tinte.b, r.tinte.a * 0.45) }
                GradientStop { position: 1; color: "transparent" }
            }
            PathRectangle { x: 0; y: 0; width: f.width; height: f.height }
        }
    }
    Resplandor { cx: f.width * 0.08; cy: f.height * 0.05; radio: f.width * 0.45; tinte: tema.color.mancha2 }
    Resplandor { cx: f.width * 0.98; cy: f.height * 0.72; radio: f.width * 0.42; tinte: tema.color.mancha1 }
    Resplandor { cx: f.width * 0.45; cy: f.height * 1.05; radio: f.width * 0.35; tinte: tema.color.mancha3 }
}
