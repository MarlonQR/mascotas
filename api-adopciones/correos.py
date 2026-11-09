"""Avisos por correo a las personas que hicieron una solicitud de adopción.

Se usa Gmail con una contraseña de aplicación. Si las variables
CORREO_REMITENTE y CORREO_CLAVE no están definidas, no se envía nada.

Las funciones notificar_* se llaman después de guardar la decisión y nunca
lanzan excepciones: si el correo falla, la aprobación o el rechazo siguen
siendo válidos.
"""

import os
import smtplib
from email.message import EmailMessage
from email.utils import formataddr


SERVIDOR_SMTP = "smtp.gmail.com"
PUERTO_SMTP = 465
ESPERA_SEGUNDOS = 6

URL_PLATAFORMA = os.getenv(
    "URL_PLATAFORMA",
    "https://huellas-de-esperanza-five.vercel.app"
).rstrip("/")

# Direcciones reservadas: las usan los datos de ejemplo y la prueba de
# integración, y un correo a ellas solo produciría un rebote.
DOMINIOS_RESERVADOS = ("example.com", "example.org", "example.net")


def es_direccion_real(correo):
    dominio = correo.rsplit("@", 1)[-1].strip().lower()
    return not dominio.endswith(".test") and dominio not in DOMINIOS_RESERVADOS


def enviar_correos(mensajes):
    """Envía los mensajes por una sola conexión.

    Cada mensaje es una tupla (destinatario, asunto, cuerpo).
    Devuelve (enviados, fallidos).
    """
    remitente = os.getenv("CORREO_REMITENTE", "").strip()

    # Google muestra la contraseña de aplicación con espacios; se quitan.
    clave = os.getenv("CORREO_CLAVE", "").replace(" ", "").strip()

    if not remitente or not clave:
        return 0, 0

    mensajes = [m for m in mensajes if es_direccion_real(m[0])]

    if not mensajes:
        return 0, 0

    enviados = 0

    try:
        with smtplib.SMTP_SSL(SERVIDOR_SMTP, PUERTO_SMTP, timeout=ESPERA_SEGUNDOS) as servidor:
            servidor.login(remitente, clave)

            for destinatario, asunto, cuerpo in mensajes:
                try:
                    correo = EmailMessage()
                    correo["From"] = formataddr(("Fundación Huellas de Esperanza", remitente))
                    correo["To"] = destinatario
                    correo["Subject"] = asunto
                    correo.set_content(cuerpo)
                    servidor.send_message(correo)
                    enviados += 1
                except Exception as error:
                    print(f"No se pudo enviar un correo: {type(error).__name__}")

    except Exception as error:
        print(f"No se pudo conectar con el servidor de correo: {type(error).__name__}")

    return enviados, len(mensajes) - enviados


def texto_aviso(enviados, fallidos):
    """Frase que se agrega a la respuesta para que la fundación sepa qué pasó."""
    if fallidos:
        return " No se pudo enviar el aviso por correo: contacta a la persona directamente."

    if enviados == 1:
        return " Se avisó por correo a 1 persona."

    if enviados > 1:
        return f" Se avisó por correo a {enviados} personas."

    return ""


def _despedida():
    return f"\n\nFundación Huellas de Esperanza\n{URL_PLATAFORMA}\n"


def _mensaje_aprobada(correo, nombre, id_solicitud, nombre_mascota, observacion):
    cuerpo = (
        f"Hola, {nombre}:\n\n"
        f"Tu solicitud #{id_solicitud} para adoptar a {nombre_mascota} fue aprobada. "
        "La fundación se comunicará contigo para coordinar la entrega."
    )

    if observacion:
        cuerpo += f"\n\nObservación de la fundación: {observacion}"

    return correo, f"Tu solicitud para adoptar a {nombre_mascota} fue aprobada", cuerpo + _despedida()


def _mensaje_rechazada(correo, nombre, id_solicitud, nombre_mascota, observacion):
    cuerpo = (
        f"Hola, {nombre}:\n\n"
        f"Tu solicitud #{id_solicitud} para adoptar a {nombre_mascota} no fue aprobada.\n\n"
        f"Motivo: {observacion}\n\n"
        "Gracias por tu interés. Puedes conocer las demás mascotas en el catálogo."
    )

    return correo, f"Respuesta a tu solicitud para adoptar a {nombre_mascota}", cuerpo + _despedida()


def _mensaje_ya_adoptada(correo, nombre, id_solicitud, nombre_mascota):
    cuerpo = (
        f"Hola, {nombre}:\n\n"
        f"Tu solicitud #{id_solicitud} no pudo continuar porque {nombre_mascota} "
        "ya encontró un hogar con otra familia.\n\n"
        "Gracias por tu interés. Puedes conocer las demás mascotas en el catálogo."
    )

    return correo, f"Respuesta a tu solicitud para adoptar a {nombre_mascota}", cuerpo + _despedida()


def notificar_aprobacion(correo, nombre, id_solicitud, nombre_mascota, observacion, otras):
    """Avisa a quien fue aprobado y a quienes se rechazaron automáticamente.

    otras es una lista de tuplas (id_solicitud, nombre, correo).
    """
    try:
        mensajes = [_mensaje_aprobada(correo, nombre, id_solicitud, nombre_mascota, observacion)]
        mensajes += [
            _mensaje_ya_adoptada(correo_otra, nombre_otra, id_otra, nombre_mascota)
            for id_otra, nombre_otra, correo_otra in otras
        ]
        return texto_aviso(*enviar_correos(mensajes))

    except Exception as error:
        print(f"Error al preparar los correos: {type(error).__name__}")
        return ""


def notificar_rechazo(correo, nombre, id_solicitud, nombre_mascota, observacion):
    try:
        mensaje = _mensaje_rechazada(correo, nombre, id_solicitud, nombre_mascota, observacion)
        return texto_aviso(*enviar_correos([mensaje]))

    except Exception as error:
        print(f"Error al preparar el correo: {type(error).__name__}")
        return ""
