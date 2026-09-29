"""Datos iniciales: configuración, razas, franjas base y textos legales (secciones 1, 5 y 9).

``sembrar`` corre en cada arranque y solo agrega lo que falta: nunca pisa un
valor que la administradora ya cambió.
"""

from __future__ import annotations

import sqlite3

CONFIG_INICIAL: dict[str, str] = {
    # Negocio y pagos (sección 1)
    "negocio_nombre": "CLINICAN",
    "negocio_descripcion": "Unidad Médica Veterinaria — Servicio de Peluquería",
    "negocio_direccion": "Calle 18A No. 2-05, Barrio Lorenzo",
    "whatsapp_numero": "301 441 7194",
    "nequi_numero": "3046505967",
    "breb_llave": "3046505967",
    "pago_titular": "Angela Benavides",
    # Precios (sección 5.2)
    "precio_min_PEQUENA": "45000",
    "precio_min_MEDIANA": "50000",
    "precio_min_GRANDE": "60000",
    "precio_ref_max_GRANDE": "70000",
    "tijera_total_min": "50000",
    "extra_bano_PEQUENA": "5000",
    "extra_bano_MEDIANA": "10000",
    "extra_bano_GRANDE": "10000",
    "desenredado_sesion": "60000",
    # Abonos y tiempos
    "abono_minimo": "20000",
    "minutos_pendiente": "30",
    "horas_minimas_aviso": "12",
    "segundos_revision_expiracion": "30",
    # Cupos por franja (sección 5.4)
    "cupo_MAQUINA": "2",
    "cupo_GRANDE": "1",
    "cupo_TIJERA": "1",
    "cupo_COMPLICADO": "1",
    # Supuestos por confirmar (sección 13)
    "pequenas_en_cupo_maquina": "1",
    "cupos_independientes": "1",
    "politica_grupo": "CONSECUTIVAS",
    "inicio_grupo_manana": "09:00",
    "inicio_grupo_tarde": "14:30",
    "franjas_solo_individuales": "08:30",
    "abono_se_conserva_con_aviso": "1",
    "horas_minimas_devolucion": "12",
    # Otros
    "personal_dia_lunes_viernes": "3",
    "personal_dia_sabado": "4",
    "respaldos_conservar": "30",
}

# (nombre, tamaño o None si se elige por mascota, pelaje complicado)
RAZAS: list[tuple[str, str | None, int]] = [
    ("Poodle (Caniche) Toy y Miniatura", "PEQUENA", 0),
    ("Bulldog Francés", "PEQUENA", 0),
    ("Yorkshire Terrier", "PEQUENA", 0),
    ("Shih Tzu", "PEQUENA", 0),
    ("Chihuahua", "PEQUENA", 0),
    ("Schnauzer Miniatura", "PEQUENA", 0),
    ("Schnauzer", "MEDIANA", 0),
    ("Pitbull y similares", "MEDIANA", 0),
    ("Labrador Retriever", "GRANDE", 0),
    ("Golden Retriever", "GRANDE", 0),
    ("Pastor Alemán", "GRANDE", 0),
    ("Husky", "GRANDE", 1),
    ("Perro mestizo (sin raza)", None, 0),
]

FRANJAS_MANANA = ["08:30", "09:00", "09:30", "10:00", "10:30", "11:00", "11:30"]
FRANJAS_TARDE = ["14:30", "15:00", "15:30", "16:00", "16:30"]
DIAS_ATENCION = range(1, 7)  # lunes a sábado; domingo cerrado

TEXTOS_LEGALES: dict[str, str] = {
    "TERMINOS": """TÉRMINOS Y CONDICIONES DEL SERVICIO DE PELUQUERÍA — CLINICAN

1. Responsabilidad. CLINICAN no será responsable en caso de muerte accidental (por ejemplo, un ataque al corazón), ni por conducta agresiva de la mascota, ni en el caso de mascotas de edad avanzada, mascotas que no están acostumbradas a la peluquería, mascotas nerviosas o enfermas. En caso fortuito, CLINICAN hará todo lo que esté en sus manos para que no ocurra ningún imprevisto durante el servicio.

2. Información y prioridad. CLINICAN explicará y responderá las dudas del propietario al momento del servicio, dando prioridad a la integridad y la salud de la mascota.

3. Estado de la mascota y precio. El propietario declara el estado real de su mascota. El precio final lo define la estilista el día del servicio, según el estado del pelaje (nudos), la piel, la presencia de pulgas o plagas, el tamaño y el comportamiento. Cuando el pelaje tenga nudos extremos, la estilista podrá proponer sesiones de desenredado ({desenredado_sesion} por sesión, una sesión por día, pudiendo durar varios días para no estresar a la mascota).

4. Abono y agendamiento. El turno solo se agenda una vez realizado el abono mínimo de {abono_minimo} por mascota, pagado por Nequi, llave Bre-B o en efectivo en el local. El comprobante debe enviarse al WhatsApp {whatsapp_numero}. Si el turno se solicita y no se paga el abono, se pierde automáticamente después de {minutos_pendiente} minutos. Si otra persona toma o paga primero el mismo turno, se da prioridad a quien pague primero.

5. No asistencia. El abono no es reembolsable en caso de no asistir al turno. Si no se asiste y no se informa con al menos {horas_minimas_aviso} horas de anticipación, se deberá abonar de nuevo para agendar otro turno.

6. Imposibilidad de prestar el servicio. Si no es posible atender a la mascota por agresividad, problemas de conducta o enfermedades no especificadas por el propietario, CLINICAN llamará al propietario para que retire a su mascota de las instalaciones.""",
    "DATOS": """AUTORIZACIÓN DE TRATAMIENTO DE DATOS PERSONALES (Ley 1581 de 2012)

Autorizo a CLINICAN — Unidad Médica Veterinaria (Calle 18A No. 2-05, Barrio Lorenzo; teléfono y WhatsApp {whatsapp_numero}) para recolectar, almacenar y usar mis datos personales (nombre, cédula, celulares y dirección) con las siguientes finalidades: agendar y prestar el servicio de peluquería, llevar el historial de mi mascota, registrar los abonos y pagos, y contactarme por llamada o WhatsApp sobre mis turnos y el estado de mi mascota.

Conozco que, como titular, tengo derecho a conocer, actualizar, rectificar y solicitar la supresión de mis datos, y a revocar esta autorización, comunicándome al {whatsapp_numero}. Mis datos no se venden ni se comparten con terceros, salvo obligación legal.""",
    "RESPONSABILIDAD": """RESPONSABILIDAD POR MASCOTA DIFÍCIL

Declaro que mi mascota presenta las condiciones que marqué a continuación: ☐ agresiva ☐ pelo con nudos extremos ☐ problemas de piel ☐ pulgas u otras plagas ☐ edad avanzada.

Entiendo que estas condiciones pueden aumentar el precio, requerir sesiones de desenredado o la revisión de la estilista, y que CLINICAN podrá suspender el servicio si la seguridad de la mascota o del personal está en riesgo, sin responsabilidad por las consecuencias de estas condiciones, según los términos y condiciones.""",
}


def sembrar_razas(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT COUNT(*) FROM razas").fetchone()[0] == 0:
        conn.executemany("INSERT INTO razas (nombre, tamano, pelaje_complicado) VALUES (?, ?, ?)", RAZAS)


def sembrar(conn: sqlite3.Connection) -> None:
    """Agrega lo que falte, sin cambiar lo existente."""
    from clinican.datos.conexion import transaccion
    from clinican.dominio.franjas import jornada_de

    with transaccion(conn):
        conn.executemany("INSERT OR IGNORE INTO config (clave, valor) VALUES (?, ?)", CONFIG_INICIAL.items())
        sembrar_razas(conn)
        if conn.execute("SELECT COUNT(*) FROM franjas_base").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO franjas_base (dia_semana, hora, jornada) VALUES (?, ?, ?)",
                [(dia, hora, jornada_de(hora)) for dia in DIAS_ATENCION for hora in FRANJAS_MANANA + FRANJAS_TARDE],
            )
        for tipo, contenido in TEXTOS_LEGALES.items():
            existe = conn.execute("SELECT 1 FROM textos_legales WHERE tipo = ?", (tipo,)).fetchone()
            if existe is None:
                conn.execute("INSERT INTO textos_legales (tipo, version, contenido, vigente) VALUES (?, 1, ?, 1)",
                             (tipo, contenido))
