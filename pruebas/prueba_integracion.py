"""
Prueba de integración entre la API de Mascotas y la API de Adopciones.

Recorre el proceso completo de adopción y muestra el resultado de cada
paso. Sirve como evidencia de que los dos servicios se comunican.

Uso:
    python prueba_integracion.py
    python prueba_integracion.py <url_api_mascotas> <url_api_adopciones> <clave_admin>

Sin argumentos usa las variables de entorno API_MASCOTAS_URL,
API_ADOPCIONES_URL y CLAVE_ADMIN, o las APIs locales (puertos 8001 y 8000).
La clave es la misma variable CLAVE_ADMIN configurada en las dos APIs.

La prueba crea cinco mascotas de prueba ("Prueba Uno" a "Prueba Cinco").
Las tres primeras terminan adoptadas, la cuarta queda publicada y la quinta
queda retirada del catálogo.
"""

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests


API_MASCOTAS = (
    sys.argv[1] if len(sys.argv) > 2
    else os.getenv("API_MASCOTAS_URL", "http://127.0.0.1:8001")
).rstrip("/")

API_ADOPCIONES = (
    sys.argv[2] if len(sys.argv) > 2
    else os.getenv("API_ADOPCIONES_URL", "http://127.0.0.1:8000")
).rstrip("/")

CLAVE_ADMIN = (
    sys.argv[3] if len(sys.argv) > 3
    else os.getenv("CLAVE_ADMIN", "")
).strip()

# Encabezado para las operaciones de la fundación
FUNDACION = {"X-Clave-Admin": CLAVE_ADMIN}

# Imagen JPEG de 24x24 píxeles para probar la subida de fotos
FOTO_PRUEBA = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAA0JCgsKCA0LCgsODg0PEyAVExISEyccHhcgLikxMC4pLSwzOko+MzZGNywtQFdBRkxOUlNSMj5aYVpQYEpRUk//2wBDAQ4ODhMREyYVFSZPNS01T09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0//wAARCAAYABgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDZq0mnXkkIlSBihGRyMkfTrRpiRyahCswUoT0boTjj9cV1deRhsMqqcpM9bE4l0mkkcVRWhriRpqH7sKCVBfH97n/61Fc1SHJJx7HTTnzxUu5n1oJrN2kIjyjEDG9hlqKKIVJQ+F2CdOM/iVzPZizFmJJJySe9FFFQWf/Z"

resultados = []
base_documento = str(int(time.time()))[-8:]
contador_documentos = 0


# ==================================================
# 1. UTILIDADES
# ==================================================

def verificar(descripcion, condicion, detalle=""):
    marca = "OK   " if condicion else "FALLA"
    print(f"  [{marca}] {descripcion}")

    if detalle:
        print(f"          {detalle}")

    resultados.append(condicion)
    return condicion


def titulo(texto):
    print()
    print(texto)
    print("-" * len(texto))


def nuevo_documento():
    global contador_documentos
    contador_documentos += 1
    return f"{base_documento}{contador_documentos:02d}"


def crear_mascota(nombre):
    respuesta = requests.post(
        f"{API_MASCOTAS}/mascotas",
        json={
            "nombre": nombre,
            "especie": "perro",
            "raza": "Mestizo",
            "sexo": "macho",
            "edad_meses": 14,
            "tamano": "mediano",
            "vacunado": True,
            "esterilizado": True,
            "descripcion": "Registro creado por pruebas/prueba_integracion.py"
        },
        headers=FUNDACION,
        timeout=30
    )
    return respuesta


def estado_mascota(id_mascota):
    respuesta = requests.get(f"{API_MASCOTAS}/mascotas/{id_mascota}", timeout=30)
    return respuesta.json()["estado"]


def solicitar(id_mascota, nombre, documento=None):
    return requests.post(
        f"{API_ADOPCIONES}/solicitudes",
        json={
            "id_mascota": id_mascota,
            "nombre_solicitante": nombre,
            "documento": documento or nuevo_documento(),
            "correo": "prueba.integracion@example.com",
            "telefono": "3001234567",
            "pais": "Colombia",
            "departamento": "Norte de Santander",
            "ciudad": "Cúcuta",
            "tipo_vivienda": "casa",
            "otras_mascotas": False,
            "motivo": "Solicitud generada por la prueba de integración automática."
        },
        timeout=30
    )


def aprobar(id_solicitud, clave=True):
    return requests.patch(
        f"{API_ADOPCIONES}/solicitudes/{id_solicitud}/aprobar",
        json={"observacion": "Aprobada por la prueba de integración"},
        headers=FUNDACION if clave else {},
        timeout=30
    )


def rechazar(id_solicitud):
    return requests.patch(
        f"{API_ADOPCIONES}/solicitudes/{id_solicitud}/rechazar",
        json={"observacion": "Rechazada por la prueba de integración"},
        headers=FUNDACION,
        timeout=30
    )


def mostrar(respuesta):
    try:
        cuerpo = respuesta.json()
        texto = cuerpo.get("detail") or cuerpo.get("mensaje") or ""

        if not texto and "id_mascota" in cuerpo:
            texto = f"{cuerpo['nombre']} (#{cuerpo['id_mascota']}, {cuerpo['estado']})"
    except ValueError:
        texto = respuesta.text[:120]

    return f"HTTP {respuesta.status_code}: {texto}"


# ==================================================
# 2. ESCENARIOS
# ==================================================

def escenario_servicios():
    titulo("0. Los dos servicios responden")

    if not CLAVE_ADMIN:
        verificar(
            "Clave de administrador recibida",
            False,
            "Pásala como tercer argumento o en la variable CLAVE_ADMIN"
        )
        return False

    for nombre, url in (("Mascotas", API_MASCOTAS), ("Adopciones", API_ADOPCIONES)):
        try:
            respuesta = requests.get(f"{url}/", timeout=30)
            verificar(f"API de {nombre} en {url}", respuesta.ok, mostrar(respuesta))
        except requests.RequestException as error:
            verificar(f"API de {nombre} en {url}", False, str(error))
            return False

    return True


def escenario_adopcion_completa():
    titulo("1. Proceso completo: solicitudes, rechazo y aprobación")

    respuesta = crear_mascota("Prueba Uno")
    if not verificar("Registrar mascota en la API de Mascotas", respuesta.status_code == 201, mostrar(respuesta)):
        return

    id_mascota = respuesta.json()["id_mascota"]

    respuesta = requests.get(f"{API_MASCOTAS}/mascotas/{id_mascota}/disponibilidad", timeout=30)
    verificar("La mascota nueva está disponible", respuesta.json().get("disponible") is True, mostrar(respuesta))

    documento_a = nuevo_documento()
    solicitud_a = solicitar(id_mascota, "Camilo Quintero", documento_a)
    verificar("Registrar solicitud A", solicitud_a.status_code == 201, mostrar(solicitud_a))
    verificar(
        "La API de Adopciones pasó la mascota a 'en_proceso'",
        estado_mascota(id_mascota) == "en_proceso"
    )

    solicitud_b = solicitar(id_mascota, "Yeimy Carrascal")
    solicitud_c = solicitar(id_mascota, "Diego Pacheco")
    verificar("Registrar solicitudes B y C para la misma mascota",
              solicitud_b.status_code == 201 and solicitud_c.status_code == 201)

    repetida = solicitar(id_mascota, "Camilo Quintero", documento_a)
    verificar("La misma persona no puede repetir solicitud pendiente (409)",
              repetida.status_code == 409, mostrar(repetida))

    id_a = solicitud_a.json()["solicitud"]["id_solicitud"]
    id_b = solicitud_b.json()["solicitud"]["id_solicitud"]
    id_c = solicitud_c.json()["solicitud"]["id_solicitud"]

    respuesta = aprobar(id_a, clave=False)
    verificar("Sin la clave de la fundación no se puede aprobar (401)",
              respuesta.status_code == 401, mostrar(respuesta))

    respuesta = rechazar(id_c)
    verificar("Rechazar la solicitud C", respuesta.status_code == 200, mostrar(respuesta))
    verificar(
        "La mascota sigue 'en_proceso' porque A y B están pendientes",
        estado_mascota(id_mascota) == "en_proceso"
    )

    respuesta = aprobar(id_a)
    verificar("Aprobar la solicitud A", respuesta.status_code == 200, mostrar(respuesta))
    verificar(
        "La solicitud B se rechazó automáticamente",
        respuesta.ok and id_b in respuesta.json().get("solicitudes_rechazadas", [])
    )
    verificar(
        "La API de Mascotas registra la mascota como 'adoptada'",
        estado_mascota(id_mascota) == "adoptada"
    )

    respuesta = aprobar(id_b)
    verificar("No se puede aprobar B después de la adopción (409)",
              respuesta.status_code == 409, mostrar(respuesta))

    respuesta = solicitar(id_mascota, "Natalia Ascanio")
    verificar("Una mascota adoptada no recibe solicitudes nuevas (409)",
              respuesta.status_code == 409, mostrar(respuesta))

    respuesta = requests.patch(
        f"{API_MASCOTAS}/mascotas/{id_mascota}/estado",
        json={"estado": "adoptada"},
        headers=FUNDACION,
        timeout=30
    )
    verificar("La API de Mascotas también rechaza una segunda adopción (409)",
              respuesta.status_code == 409, mostrar(respuesta))

    respuesta = requests.get(
        f"{API_ADOPCIONES}/solicitudes/{id_a}",
        headers=FUNDACION,
        timeout=30
    )
    mascota = respuesta.json().get("mascota") or {}
    verificar(
        "El detalle de la solicitud A trae la mascota desde la API de Mascotas",
        respuesta.ok and mascota.get("estado") == "adoptada",
        f"mascota = {mascota.get('nombre')} ({mascota.get('estado')})"
    )


def escenario_rechazo_libera_mascota():
    titulo("2. Rechazar la única solicitud devuelve la mascota a 'disponible'")

    respuesta = crear_mascota("Prueba Dos")
    if not verificar("Registrar mascota", respuesta.status_code == 201, mostrar(respuesta)):
        return

    id_mascota = respuesta.json()["id_mascota"]

    solicitud = solicitar(id_mascota, "Andrés Ropero")
    verificar("Registrar solicitud", solicitud.status_code == 201, mostrar(solicitud))
    verificar("La mascota pasa a 'en_proceso'", estado_mascota(id_mascota) == "en_proceso")

    respuesta = rechazar(solicitud.json()["solicitud"]["id_solicitud"])
    verificar("Rechazar la solicitud", respuesta.status_code == 200, mostrar(respuesta))
    verificar("La mascota vuelve a 'disponible'", estado_mascota(id_mascota) == "disponible")

    solicitud = solicitar(id_mascota, "Laura Sanjuán")
    respuesta = aprobar(solicitud.json()["solicitud"]["id_solicitud"])
    verificar("Puede recibir una solicitud nueva y ser adoptada",
              respuesta.status_code == 200 and estado_mascota(id_mascota) == "adoptada",
              mostrar(respuesta))


def escenario_aprobaciones_simultaneas():
    titulo("3. Dos aprobaciones al mismo tiempo para la misma mascota")

    respuesta = crear_mascota("Prueba Tres")
    if not verificar("Registrar mascota", respuesta.status_code == 201, mostrar(respuesta)):
        return

    id_mascota = respuesta.json()["id_mascota"]

    ids = [
        solicitar(id_mascota, nombre).json()["solicitud"]["id_solicitud"]
        for nombre in ("Camilo Quintero", "Yeimy Carrascal")
    ]

    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        respuestas = list(ejecutor.map(aprobar, ids))

    codigos = sorted(r.status_code for r in respuestas)
    verificar(
        "Solo una aprobación tiene éxito y la otra recibe 409",
        codigos == [200, 409],
        f"códigos recibidos: {codigos}"
    )

    respuesta = requests.get(
        f"{API_ADOPCIONES}/solicitudes",
        params={"id_mascota": id_mascota, "estado": "aprobada"},
        headers=FUNDACION,
        timeout=30
    )
    verificar(
        "En la base de datos hay exactamente una solicitud aprobada",
        respuesta.ok and len(respuesta.json()) == 1,
        f"aprobadas: {len(respuesta.json()) if respuesta.ok else '?'}"
    )


def escenario_publicacion_comunidad():
    titulo("4. Una persona da una mascota en adopción y la fundación la publica")

    respuesta = requests.post(
        f"{API_MASCOTAS}/mascotas",
        json={
            "nombre": "Prueba Cuatro",
            "especie": "gato",
            "raza": "Criolla",
            "sexo": "hembra",
            "edad_meses": 9,
            "tamano": "pequeno",
            "vacunado": True,
            "esterilizado": False,
            "descripcion": "Publicación creada por la prueba de integración automática.",
            "pais": "Colombia",
            "departamento": "Norte de Santander",
            "ciudad": "Villa del Rosario",
            "contacto": {
                "nombre": "Natalia Ascanio",
                "telefono": "3001112233",
                "correo": "prueba.integracion@example.com"
            },
            "fotos": [FOTO_PRUEBA]
        },
        timeout=30
    )

    if not verificar("Enviar la mascota sin clave (público)", respuesta.status_code == 201, mostrar(respuesta)):
        return

    mascota = respuesta.json()
    id_mascota = mascota["id_mascota"]

    verificar("Queda 'en_revision' y sin datos de contacto en la respuesta pública",
              mascota["estado"] == "en_revision" and "contacto" not in mascota)

    foto = requests.get(f"{API_MASCOTAS}{mascota['fotos'][0]}", timeout=30)
    verificar("La foto subida se puede descargar",
              foto.ok and foto.headers.get("content-type") == "image/jpeg")

    catalogo = requests.get(f"{API_MASCOTAS}/mascotas", timeout=30).json()
    verificar("No aparece en el catálogo mientras está en revisión",
              id_mascota not in [m["id_mascota"] for m in catalogo])

    respuesta = solicitar(id_mascota, "Diego Pacheco")
    verificar("No recibe solicitudes antes de publicarse (409)",
              respuesta.status_code == 409, mostrar(respuesta))

    respuesta = requests.patch(f"{API_MASCOTAS}/mascotas/{id_mascota}/publicar", json={}, timeout=30)
    verificar("Sin la clave no se puede publicar (401)", respuesta.status_code == 401, mostrar(respuesta))

    publicaciones = requests.get(
        f"{API_MASCOTAS}/publicaciones", headers=FUNDACION, timeout=30
    ).json()
    pendiente = next((p for p in publicaciones if p["id_mascota"] == id_mascota), {})
    verificar("La fundación ve la publicación con el contacto",
              (pendiente.get("contacto") or {}).get("nombre") == "Natalia Ascanio")

    respuesta = requests.patch(
        f"{API_MASCOTAS}/mascotas/{id_mascota}/publicar",
        json={"observacion": "Publicada por la prueba de integración"},
        headers=FUNDACION,
        timeout=30
    )
    verificar("La fundación la publica", respuesta.status_code == 200, mostrar(respuesta))
    verificar("Ahora está 'disponible' en el catálogo", estado_mascota(id_mascota) == "disponible")

    respuesta = solicitar(id_mascota, "Diego Pacheco")
    verificar("Ya recibe solicitudes con país, departamento y ciudad",
              respuesta.status_code == 201
              and respuesta.json()["solicitud"]["departamento"] == "Norte de Santander",
              mostrar(respuesta))


def escenario_gestion_y_estadisticas():
    titulo("5. La fundación edita y retira una mascota, y consulta las estadísticas")

    respuesta = crear_mascota("Prueba Cinco")
    if not verificar("Registrar mascota", respuesta.status_code == 201, mostrar(respuesta)):
        return

    id_mascota = respuesta.json()["id_mascota"]

    edicion = {
        "nombre": "Prueba Cinco",
        "especie": "perro",
        "raza": "Criollo",
        "sexo": "hembra",
        "edad_meses": 20,
        "tamano": "grande",
        "vacunado": True,
        "esterilizado": True,
        "descripcion": "Datos corregidos por la prueba de integración.",
        "pais": "Colombia",
        "departamento": "Norte de Santander",
        "ciudad": "Pamplona"
    }

    respuesta = requests.put(f"{API_MASCOTAS}/mascotas/{id_mascota}", json=edicion, timeout=30)
    verificar("Sin la clave no se puede editar (401)", respuesta.status_code == 401, mostrar(respuesta))

    respuesta = requests.put(
        f"{API_MASCOTAS}/mascotas/{id_mascota}", json=edicion, headers=FUNDACION, timeout=30
    )
    verificar(
        "La fundación corrige los datos",
        respuesta.ok and respuesta.json()["ciudad"] == "Pamplona" and respuesta.json()["sexo"] == "hembra",
        mostrar(respuesta)
    )

    solicitud = solicitar(id_mascota, "Andrés Ropero")
    id_solicitud = solicitud.json()["solicitud"]["id_solicitud"]

    respuesta = requests.patch(
        f"{API_MASCOTAS}/mascotas/{id_mascota}/retirar",
        json={"motivo": "Prueba de retiro con solicitudes pendientes"},
        headers=FUNDACION,
        timeout=30
    )
    verificar("No se puede retirar con solicitudes pendientes (409)",
              respuesta.status_code == 409, mostrar(respuesta))

    rechazar(id_solicitud)

    respuesta = requests.patch(
        f"{API_MASCOTAS}/mascotas/{id_mascota}/retirar",
        json={"motivo": "La reclamó su dueño (prueba de integración)"},
        headers=FUNDACION,
        timeout=30
    )
    verificar("Después de rechazar la solicitud, sí se puede retirar",
              respuesta.ok and respuesta.json()["estado"] == "retirada", mostrar(respuesta))

    catalogo = requests.get(f"{API_MASCOTAS}/mascotas", timeout=30).json()
    verificar("La mascota retirada sale del catálogo",
              id_mascota not in [m["id_mascota"] for m in catalogo])

    respuesta = solicitar(id_mascota, "Laura Sanjuán")
    verificar("Una mascota retirada no recibe solicitudes (409)",
              respuesta.status_code == 409, mostrar(respuesta))

    respuesta = requests.patch(
        f"{API_MASCOTAS}/mascotas/{id_mascota}/restaurar", headers=FUNDACION, timeout=30
    )
    verificar("La fundación la puede volver a publicar",
              respuesta.ok and estado_mascota(id_mascota) == "disponible", mostrar(respuesta))

    requests.patch(
        f"{API_MASCOTAS}/mascotas/{id_mascota}/retirar",
        json={"motivo": "Retirada al terminar la prueba de integración"},
        headers=FUNDACION,
        timeout=30
    )

    respuesta = requests.get(f"{API_ADOPCIONES}/estadisticas", timeout=30)
    verificar("Sin la clave no se ven las estadísticas (401)", respuesta.status_code == 401, mostrar(respuesta))

    respuesta = requests.get(f"{API_ADOPCIONES}/estadisticas", headers=FUNDACION, timeout=30)
    datos = respuesta.json() if respuesta.ok else {}
    verificar(
        "Las estadísticas cruzan las solicitudes con el catálogo de la API de Mascotas",
        respuesta.ok
        and datos.get("solicitudes_aprobadas", 0) >= 3
        and datos.get("catalogo_por_especie") is not None
        and len(datos.get("adopciones_por_mes", [])) == 6,
        f"aprobadas: {datos.get('solicitudes_aprobadas')} · por especie: {datos.get('adopciones_por_especie')}"
    )


# ==================================================
# 3. EJECUCIÓN
# ==================================================

if __name__ == "__main__":
    # Tildes correctas también cuando la salida se guarda en un archivo
    sys.stdout.reconfigure(encoding="utf-8")

    print("Prueba de integración - Plataforma de adopción de mascotas")
    print(f"API de Mascotas:   {API_MASCOTAS}")
    print(f"API de Adopciones: {API_ADOPCIONES}")

    if escenario_servicios():
        escenario_adopcion_completa()
        escenario_rechazo_libera_mascota()
        escenario_aprobaciones_simultaneas()
        escenario_publicacion_comunidad()
        escenario_gestion_y_estadisticas()

    correctas = sum(resultados)
    print()
    print(f"Resultado: {correctas} de {len(resultados)} verificaciones correctas")

    sys.exit(0 if correctas == len(resultados) else 1)
