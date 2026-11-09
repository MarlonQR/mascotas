"""Avisos por correo a las personas que hicieron una solicitud de adopción.

Se usa Gmail con una contraseña de aplicación. Si las variables
CORREO_REMITENTE y CORREO_CLAVE no están definidas, no se envía nada.

Cada correo lleva una versión con diseño (HTML) y una de texto plano para
los programas que no muestran HTML. Los estilos van dentro de cada etiqueta
y la estructura usa tablas porque Gmail y Outlook ignoran buena parte del
CSS moderno.

Las funciones notificar_* se llaman después de guardar la decisión y nunca
lanzan excepciones: si el correo falla, la aprobación o el rechazo siguen
siendo válidos.
"""

import os
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from html import escape


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

# Los mismos colores de la página
NARANJA = "#c2410c"
NARANJA_SUAVE = "#fff7ed"
NARANJA_BORDE = "#fed7aa"
VERDE = "#15803d"
VERDE_SUAVE = "#f0fdf4"
GRIS_BANDA = "#57534e"
FONDO = "#fbf6f0"
BORDE = "#e7e0d8"
TEXTO = "#292524"
TEXTO_SUAVE = "#78716c"
FUENTE = "Arial, Helvetica, sans-serif"

ESPECIES = {"perro": "Perro", "gato": "Gato"}
SEXOS = {"macho": "Macho", "hembra": "Hembra"}
TAMANOS = {"pequeno": "Pequeño", "mediano": "Mediano", "grande": "Grande"}


# ==================================================
# 1. ENVÍO
# ==================================================

def es_direccion_real(correo):
    dominio = correo.rsplit("@", 1)[-1].strip().lower()
    return not dominio.endswith(".test") and dominio not in DOMINIOS_RESERVADOS


def enviar_correos(mensajes):
    """Envía los mensajes por una sola conexión.

    Cada mensaje es una tupla (destinatario, asunto, texto, html).
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

            for destinatario, asunto, texto, contenido_html in mensajes:
                try:
                    correo = EmailMessage()
                    correo["From"] = formataddr(("Fundación Huellas de Esperanza", remitente))
                    correo["To"] = destinatario
                    correo["Subject"] = asunto
                    correo.set_content(texto)
                    correo.add_alternative(contenido_html, subtype="html")
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


# ==================================================
# 2. PIEZAS DEL DISEÑO
# ==================================================

def formatear_edad(meses):
    if meses < 12:
        return "1 mes" if meses == 1 else f"{meses} meses"

    anios = meses // 12
    return "1 año" if anios == 1 else f"{anios} años"


def url_foto(mascota):
    foto = mascota.get("foto_url") or ""

    if foto.startswith(("http://", "https://")):
        return foto

    fotos = mascota.get("fotos") or []

    if fotos:
        base = os.getenv("API_MASCOTAS_URL", "").strip().rstrip("/")
        return f"{base}{fotos[0]}" if base else ""

    return ""


def datos_mascota(mascota):
    """Pares (etiqueta, valor) con lo que se sepa de la mascota."""
    datos = []

    if mascota.get("especie") in ESPECIES:
        datos.append(("Especie", ESPECIES[mascota["especie"]]))

    if mascota.get("raza"):
        datos.append(("Raza", mascota["raza"]))

    if mascota.get("sexo") in SEXOS:
        datos.append(("Sexo", SEXOS[mascota["sexo"]]))

    if mascota.get("edad_meses") is not None:
        datos.append(("Edad", formatear_edad(mascota["edad_meses"])))

    if mascota.get("tamano") in TAMANOS:
        datos.append(("Tamaño", TAMANOS[mascota["tamano"]]))

    if mascota.get("ciudad"):
        datos.append(("Ciudad", mascota["ciudad"]))

    return datos


def tarjeta_mascota(mascota):
    nombre = escape(mascota["nombre"])
    foto = url_foto(mascota)

    bloque_foto = ""

    if foto:
        bloque_foto = f"""
        <tr>
          <td style="padding:0;line-height:0;">
            <img src="{escape(foto, quote=True)}" alt="Foto de {nombre}" width="520"
                 style="display:block;width:100%;max-width:520px;height:auto;max-height:340px;object-fit:cover;border:0;border-radius:12px 12px 0 0;">
          </td>
        </tr>"""

    filas = "".join(
        f"""
            <tr>
              <td style="padding:7px 0;border-top:1px solid {BORDE};font-family:{FUENTE};font-size:14px;color:{TEXTO_SUAVE};">{escape(etiqueta)}</td>
              <td align="right" style="padding:7px 0;border-top:1px solid {BORDE};font-family:{FUENTE};font-size:14px;font-weight:bold;color:{TEXTO};">{escape(valor)}</td>
            </tr>"""
        for etiqueta, valor in datos_mascota(mascota)
    )

    tabla_datos = (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:10px;">{filas}\n</table>'
        if filas else ""
    )

    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
           style="background:#ffffff;border:1px solid {BORDE};border-radius:12px;margin:0 0 24px;">{bloque_foto}
      <tr>
        <td style="padding:18px 20px 14px;">
          <div style="font-family:{FUENTE};font-size:24px;font-weight:bold;color:{TEXTO};">{nombre}</div>
          {tabla_datos}
        </td>
      </tr>
    </table>"""


def recuadro(titulo, contenido, fondo, borde):
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
           style="background:{fondo};border:1px solid {borde};border-radius:10px;margin:0 0 24px;">
      <tr>
        <td style="padding:16px 18px;font-family:{FUENTE};font-size:15px;line-height:1.55;color:{TEXTO};">
          <div style="font-weight:bold;margin-bottom:6px;">{escape(titulo)}</div>
          {contenido}
        </td>
      </tr>
    </table>"""


def pasos(lista):
    filas = "".join(
        f"""
      <tr>
        <td width="40" valign="top" style="padding:0 0 14px;">
          <div style="width:30px;height:30px;line-height:30px;border-radius:15px;background:{VERDE};color:#ffffff;font-family:{FUENTE};font-size:14px;font-weight:bold;text-align:center;">{numero}</div>
        </td>
        <td valign="top" style="padding:4px 0 14px;font-family:{FUENTE};font-size:15px;line-height:1.5;color:{TEXTO};">{escape(paso)}</td>
      </tr>"""
        for numero, paso in enumerate(lista, 1)
    )

    return f"""
    <div style="font-family:{FUENTE};font-size:18px;font-weight:bold;color:{TEXTO};margin:0 0 14px;">Qué sigue ahora</div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 12px;">{filas}
    </table>"""


def plantilla(resumen, color, icono, titulo, subtitulo, contenido, texto_boton):
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{escape(titulo)}</title>
</head>
<body style="margin:0;padding:0;background:{FONDO};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{escape(resumen)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{FONDO};">
  <tr>
    <td align="center" style="padding:24px 12px;">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"
             style="width:100%;max-width:600px;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid {BORDE};">
        <tr>
          <td align="center" style="background:{NARANJA};padding:16px 24px;font-family:{FUENTE};font-size:17px;font-weight:bold;color:#ffffff;">
            🐾 Fundación Huellas de Esperanza
          </td>
        </tr>
        <tr>
          <td align="center" style="background:{color};padding:34px 28px 36px;">
            <div style="font-size:50px;line-height:60px;">{icono}</div>
            <div style="font-family:{FUENTE};font-size:27px;line-height:1.25;font-weight:bold;color:#ffffff;margin-top:8px;">{escape(titulo)}</div>
            <div style="font-family:{FUENTE};font-size:16px;line-height:1.5;color:#ffffff;margin-top:10px;">{subtitulo}</div>
          </td>
        </tr>
        <tr>
          <td style="padding:30px 40px 12px;">
            {contenido}
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" style="margin:6px auto 30px;">
              <tr>
                <td align="center" bgcolor="{NARANJA}" style="border-radius:10px;">
                  <a href="{escape(URL_PLATAFORMA, quote=True)}" target="_blank"
                     style="display:inline-block;padding:15px 34px;font-family:{FUENTE};font-size:16px;font-weight:bold;color:#ffffff;text-decoration:none;border-radius:10px;">{escape(texto_boton)}</a>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td align="center" style="background:{NARANJA_SUAVE};border-top:1px solid {NARANJA_BORDE};padding:20px 28px;font-family:{FUENTE};font-size:13px;line-height:1.6;color:{GRIS_BANDA};">
            Gracias por apoyar la adopción responsable.<br>
            Recibes este correo porque enviaste una solicitud de adopción en nuestra plataforma.
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
</body>
</html>"""


def parrafo(contenido):
    return (
        f'<p style="margin:0 0 22px;font-family:{FUENTE};font-size:16px;'
        f'line-height:1.6;color:{TEXTO};">{contenido}</p>'
    )


# ==================================================
# 3. LOS TRES CORREOS
# ==================================================

def despedida_texto():
    return f"\n\nFundación Huellas de Esperanza\n{URL_PLATAFORMA}\n"


def mensaje_aprobada(correo, nombre, id_solicitud, mascota, observacion):
    nombre_mascota = mascota["nombre"]
    lista_pasos = [
        "Te contactaremos por teléfono o por correo para acordar la entrega.",
        "Ten a la mano tu documento de identidad para ese día.",
        f"Prepárale a {nombre_mascota} un espacio tranquilo, con agua y comida.",
    ]

    texto = (
        f"Hola, {nombre}:\n\n"
        f"¡Felicitaciones! Tu solicitud #{id_solicitud} para adoptar a {nombre_mascota} fue aprobada.\n\n"
        "Qué sigue ahora:\n"
        + "".join(f"{i}. {paso}\n" for i, paso in enumerate(lista_pasos, 1))
    )

    if observacion:
        texto += f"\nObservación de la fundación: {observacion}\n"

    contenido = parrafo(
        f"Hola, <strong>{escape(nombre)}</strong>. Revisamos tu solicitud "
        f"<strong>#{id_solicitud}</strong> y nos alegra contarte que "
        f"<strong>{escape(nombre_mascota)}</strong> se va a casa contigo."
    ) + tarjeta_mascota(mascota)

    if observacion:
        contenido += recuadro(
            "Nota de la fundación", escape(observacion), VERDE_SUAVE, "#bbf7d0"
        )

    contenido += pasos(lista_pasos)

    return (
        correo,
        f"🎉 ¡Aprobada! {nombre_mascota} ya tiene hogar contigo",
        texto + despedida_texto(),
        plantilla(
            f"Tu solicitud #{id_solicitud} para adoptar a {nombre_mascota} fue aprobada.",
            VERDE, "🎉", "¡Tu solicitud fue aprobada!",
            f"{escape(nombre_mascota)} empieza una nueva vida a tu lado",
            contenido,
            "Visitar la fundación",
        ),
    )


def mensaje_rechazada(correo, nombre, id_solicitud, mascota, observacion):
    nombre_mascota = mascota["nombre"]

    texto = (
        f"Hola, {nombre}:\n\n"
        f"Tu solicitud #{id_solicitud} para adoptar a {nombre_mascota} no fue aprobada.\n\n"
        f"Motivo: {observacion}\n\n"
        "Gracias por tu interés. Puedes conocer las demás mascotas en el catálogo."
    )

    contenido = (
        parrafo(
            f"Hola, <strong>{escape(nombre)}</strong>. Gracias por querer darle un hogar a "
            f"<strong>{escape(nombre_mascota)}</strong>. Revisamos con cuidado tu solicitud "
            f"<strong>#{id_solicitud}</strong> y esta vez no pudimos aprobarla."
        )
        + recuadro("Motivo de la decisión", escape(observacion), NARANJA_SUAVE, NARANJA_BORDE)
        + tarjeta_mascota(mascota)
        + parrafo(
            "Esta respuesta es solo para esta solicitud. Tenemos más mascotas "
            "esperando una familia y puedes postularte cuando quieras."
        )
    )

    return (
        correo,
        f"Respuesta a tu solicitud para adoptar a {nombre_mascota}",
        texto + despedida_texto(),
        plantilla(
            f"Tenemos una respuesta sobre tu solicitud #{id_solicitud}.",
            GRIS_BANDA, "💌", "Tenemos una respuesta para ti",
            "Gracias por pensar en la adopción responsable",
            contenido,
            "Ver mascotas disponibles",
        ),
    )


def mensaje_ya_adoptada(correo, nombre, id_solicitud, mascota):
    nombre_mascota = mascota["nombre"]

    texto = (
        f"Hola, {nombre}:\n\n"
        f"Tu solicitud #{id_solicitud} no pudo continuar porque {nombre_mascota} "
        "ya encontró un hogar con otra familia.\n\n"
        "Gracias por tu interés. Puedes conocer las demás mascotas en el catálogo."
    )

    contenido = (
        parrafo(
            f"Hola, <strong>{escape(nombre)}</strong>. Gracias por tu solicitud "
            f"<strong>#{id_solicitud}</strong>. <strong>{escape(nombre_mascota)}</strong> "
            "ya encontró un hogar con otra familia, así que tu solicitud no pudo continuar."
        )
        + tarjeta_mascota(mascota)
        + parrafo(
            "Tu interés sigue siendo muy valioso. Tenemos más mascotas buscando "
            "un hogar y a lo mejor una de ellas te está esperando."
        )
    )

    return (
        correo,
        f"{nombre_mascota} ya encontró un hogar",
        texto + despedida_texto(),
        plantilla(
            f"{nombre_mascota} ya encontró un hogar, pero hay más mascotas esperándote.",
            GRIS_BANDA, "🏡", f"{nombre_mascota} ya encontró un hogar",
            "Hay más mascotas esperando una familia",
            contenido,
            "Conocer otras mascotas",
        ),
    )


# ==================================================
# 4. FUNCIONES QUE USA LA API
# ==================================================

def notificar_aprobacion(correo, nombre, id_solicitud, mascota, observacion, otras):
    """Avisa a quien fue aprobado y a quienes se rechazaron automáticamente.

    otras es una lista de tuplas (id_solicitud, nombre, correo).
    """
    try:
        mensajes = [mensaje_aprobada(correo, nombre, id_solicitud, mascota, observacion)]
        mensajes += [
            mensaje_ya_adoptada(correo_otra, nombre_otra, id_otra, mascota)
            for id_otra, nombre_otra, correo_otra in otras
        ]
        return texto_aviso(*enviar_correos(mensajes))

    except Exception as error:
        print(f"Error al preparar los correos: {type(error).__name__}")
        return ""


def notificar_rechazo(correo, nombre, id_solicitud, mascota, observacion):
    try:
        mensaje = mensaje_rechazada(correo, nombre, id_solicitud, mascota, observacion)
        return texto_aviso(*enviar_correos([mensaje]))

    except Exception as error:
        print(f"Error al preparar el correo: {type(error).__name__}")
        return ""
