"""
Prueba de integración entre la API de Mascotas y la API de Adopciones.

Recorre el proceso completo de adopción y muestra el resultado de cada
paso. Sirve como evidencia de que los dos servicios se comunican.

Uso:
    python prueba_integracion.py
    python prueba_integracion.py <url_api_mascotas> <url_api_adopciones>

Sin argumentos usa las variables de entorno API_MASCOTAS_URL y
API_ADOPCIONES_URL, o las APIs locales (puertos 8001 y 8000).

La prueba crea tres mascotas de prueba y termina con las tres adoptadas.
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
            "ciudad": "Cúcuta",
            "tipo_vivienda": "casa",
            "otras_mascotas": False,
            "motivo": "Solicitud generada por la prueba de integración automática."
        },
        timeout=30
    )


def aprobar(id_solicitud):
    return requests.patch(
        f"{API_ADOPCIONES}/solicitudes/{id_solicitud}/aprobar",
        json={"observacion": "Aprobada por la prueba de integración"},
        timeout=30
    )


def rechazar(id_solicitud):
    return requests.patch(
        f"{API_ADOPCIONES}/solicitudes/{id_solicitud}/rechazar",
        json={"observacion": "Rechazada por la prueba de integración"},
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
        timeout=30
    )
    verificar("La API de Mascotas también rechaza una segunda adopción (409)",
              respuesta.status_code == 409, mostrar(respuesta))

    respuesta = requests.get(f"{API_ADOPCIONES}/solicitudes/{id_a}", timeout=30)
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
        timeout=30
    )
    verificar(
        "En la base de datos hay exactamente una solicitud aprobada",
        respuesta.ok and len(respuesta.json()) == 1,
        f"aprobadas: {len(respuesta.json()) if respuesta.ok else '?'}"
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

    correctas = sum(resultados)
    print()
    print(f"Resultado: {correctas} de {len(resultados)} verificaciones correctas")

    sys.exit(0 if correctas == len(resultados) else 1)
