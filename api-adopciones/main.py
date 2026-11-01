
import os
import secrets
from datetime import datetime
from typing import Annotated, Literal, Optional

import requests
from fastapi import Depends, FastAPI, HTTPException, Path, Query, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from psycopg2.errors import UniqueViolation
from pydantic import BaseModel, Field
from con_db import obtener_conexion


# URL de la API de Mascotas
API_MASCOTAS_URL = os.getenv(
    "API_MASCOTAS_URL",
    "http://127.0.0.1:8001"
).rstrip("/")


app = FastAPI(
    title="API de Adopciones",
    description=(
        "Servicio de la Fundación Huellas de Esperanza para registrar, "
        "consultar y resolver solicitudes de adopción.\n\n"
        "Antes de guardar o aprobar una solicitud consulta la **API de "
        "Mascotas** por HTTP para verificar la disponibilidad de la "
        "mascota, y le pide cambiar su estado (`en_proceso`, `adoptada` "
        "o `disponible`) según el resultado."
    ),
    version="1.0.0",
    openapi_tags=[
        {
            "name": "Servicio",
            "description": "Verificación de que el servicio responde."
        },
        {
            "name": "Solicitudes",
            "description": "Registro y consulta de solicitudes de adopción."
        },
        {
            "name": "Gestión",
            "description": (
                "Aprobación y rechazo de solicitudes. Ambas operaciones "
                "actualizan el estado de la mascota en la API de Mascotas."
            )
        }
    ]
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)


# ==================================================
# 1. VALORES PERMITIDOS Y MODELOS
# ==================================================

EstadoSolicitud = Literal["pendiente", "aprobada", "rechazada"]
TipoVivienda = Literal["casa", "apartamento", "finca"]

IdSolicitud = Annotated[
    int,
    Path(gt=0, le=2147483647, description="Identificador de la solicitud")
]

COLUMNAS = """
    id_solicitud, id_mascota, nombre_solicitante, documento, correo,
    telefono, ciudad, tipo_vivienda, otras_mascotas, motivo, estado,
    observacion, fecha_solicitud, fecha_respuesta, pais, departamento
"""


class Solicitud(BaseModel):
    id_mascota: int = Field(gt=0, le=2147483647)
    nombre_solicitante: str = Field(min_length=3, max_length=100)
    documento: str = Field(
        pattern=r"^\d{6,12}$",
        description="Número de documento, solo dígitos"
    )
    correo: str = Field(
        max_length=120,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )
    telefono: str = Field(
        pattern=r"^\+?\d{7,14}$",
        description="Solo dígitos, con + opcional al inicio"
    )
    pais: str = Field(min_length=2, max_length=80)
    departamento: str = Field(
        min_length=2, max_length=80,
        description="Departamento, estado o provincia"
    )
    ciudad: str = Field(
        min_length=2, max_length=80,
        description="Municipio o ciudad"
    )
    tipo_vivienda: TipoVivienda
    otras_mascotas: bool = False
    motivo: str = Field(
        min_length=20, max_length=1000,
        description="Por qué quiere adoptar y cómo cuidará a la mascota"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id_mascota": 1,
                    "nombre_solicitante": "Laura Sanjuán",
                    "documento": "1090456789",
                    "correo": "laura.sanjuan@example.com",
                    "telefono": "3104567890",
                    "pais": "Colombia",
                    "departamento": "Norte de Santander",
                    "ciudad": "Cúcuta",
                    "tipo_vivienda": "casa",
                    "otras_mascotas": False,
                    "motivo": "Vivo con mis papás en una casa con patio y tenemos tiempo para sacarla a caminar todas las tardes."
                }
            ]
        }
    }


class Aprobacion(BaseModel):
    observacion: Optional[str] = Field(None, max_length=500)

    model_config = {
        "json_schema_extra": {
            "examples": [{"observacion": "Visita domiciliaria aprobada"}]
        }
    }


class Rechazo(BaseModel):
    observacion: str = Field(
        min_length=5, max_length=500,
        description="Motivo del rechazo"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{"observacion": "La vivienda no tiene espacio para un perro grande"}]
        }
    }


class MascotaResumen(BaseModel):
    id_mascota: int
    nombre: str
    estado: str
    especie: Optional[str] = None
    raza: Optional[str] = None
    sexo: Optional[str] = None
    foto_url: Optional[str] = None
    fotos: list[str] = Field(
        default=[],
        description="Rutas de las fotos subidas, relativas a la API de Mascotas"
    )


class SolicitudRespuesta(BaseModel):
    id_solicitud: int
    id_mascota: int
    nombre_solicitante: str
    documento: str
    correo: str
    telefono: str
    pais: str
    departamento: str
    ciudad: str
    tipo_vivienda: TipoVivienda
    otras_mascotas: bool
    motivo: str
    estado: EstadoSolicitud
    observacion: Optional[str]
    fecha_solicitud: datetime
    fecha_respuesta: Optional[datetime]
    mascota: Optional[MascotaResumen] = Field(
        None,
        description=(
            "Datos obtenidos de la API de Mascotas. "
            "Es null si ese servicio no respondió."
        )
    )


class RegistroRespuesta(BaseModel):
    mensaje: str
    solicitud: SolicitudRespuesta


class DecisionRespuesta(BaseModel):
    mensaje: str
    solicitud: SolicitudRespuesta
    solicitudes_rechazadas: list[int] = Field(
        default=[],
        description="Otras solicitudes pendientes que se rechazaron al aprobar esta"
    )


class Error(BaseModel):
    detail: str


ERRORES = {
    404: {"model": Error, "description": "La solicitud o la mascota no existe"},
    409: {"model": Error, "description": "La operación viola una regla de negocio"},
    502: {"model": Error, "description": "La API de Mascotas no respondió"}
}

ERROR_401 = {
    401: {"model": Error, "description": "Falta la clave de administrador o es incorrecta"}
}


def convertir_solicitud(fila, mascota=None):
    return {
        "id_solicitud": fila[0],
        "id_mascota": fila[1],
        "nombre_solicitante": fila[2],
        "documento": fila[3],
        "correo": fila[4],
        "telefono": fila[5],
        "pais": fila[14],
        "departamento": fila[15],
        "ciudad": fila[6],
        "tipo_vivienda": fila[7],
        "otras_mascotas": fila[8],
        "motivo": fila[9],
        "estado": fila[10],
        "observacion": fila[11],
        "fecha_solicitud": fila[12],
        "fecha_respuesta": fila[13],
        "mascota": mascota
    }


# ==================================================
# 2. CLAVE DE LA FUNDACIÓN
# ==================================================
# Consultar, aprobar y rechazar solicitudes exige el encabezado
# X-Clave-Admin con el valor de la variable de entorno CLAVE_ADMIN.
# Registrar una solicitud es público. La misma clave se envía a la API
# de Mascotas cuando hay que cambiar el estado de una mascota.

esquema_clave = APIKeyHeader(
    name="X-Clave-Admin",
    auto_error=False,
    description="Clave de administrador de la fundación (variable CLAVE_ADMIN)"
)


def clave_admin():
    return os.getenv("CLAVE_ADMIN", "").strip()


def verificar_clave_admin(clave: Optional[str] = Security(esquema_clave)):
    esperada = clave_admin()

    if not esperada:
        raise HTTPException(
            status_code=503,
            detail="El servidor no tiene configurada la variable CLAVE_ADMIN"
        )

    # compare_digest evita deducir la clave midiendo el tiempo de respuesta.
    if not clave or not secrets.compare_digest(
        clave.strip().encode(), esperada.encode()
    ):
        raise HTTPException(
            status_code=401,
            detail="Clave de administrador incorrecta"
        )


SOLO_FUNDACION = [Depends(verificar_clave_admin)]


# ==================================================
# 3. COMUNICACIÓN CON LA API DE MASCOTAS
# ==================================================

def resumir_mascota(mascota):
    return {
        "id_mascota": mascota["id_mascota"],
        "nombre": mascota["nombre"],
        "estado": mascota["estado"],
        "especie": mascota.get("especie"),
        "raza": mascota.get("raza"),
        "sexo": mascota.get("sexo"),
        "foto_url": mascota.get("foto_url"),
        "fotos": mascota.get("fotos") or []
    }


def detalle_error(respuesta, por_defecto):
    try:
        return respuesta.json().get("detail", por_defecto)
    except ValueError:
        return por_defecto


def verificar_disponibilidad(id_mascota):
    try:
        respuesta = requests.get(
            f"{API_MASCOTAS_URL}/mascotas/{id_mascota}/disponibilidad",
            timeout=10
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=502,
            detail="No fue posible consultar el servicio de Mascotas"
        )

    if respuesta.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail="La mascota no existe en el servicio de Mascotas"
        )

    if not respuesta.ok:
        raise HTTPException(
            status_code=502,
            detail="El servicio de Mascotas respondió con un error"
        )

    return respuesta.json()


def cambiar_estado_mascota(id_mascota, estado):
    try:
        respuesta = requests.patch(
            f"{API_MASCOTAS_URL}/mascotas/{id_mascota}/estado",
            json={"estado": estado},
            headers={"X-Clave-Admin": clave_admin()},
            timeout=10
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=502,
            detail="No fue posible actualizar la mascota en el servicio de Mascotas"
        )

    if respuesta.status_code in (404, 409):
        raise HTTPException(
            status_code=respuesta.status_code,
            detail=detalle_error(
                respuesta,
                "El servicio de Mascotas rechazó el cambio de estado"
            )
        )

    if respuesta.status_code in (401, 503):
        raise HTTPException(
            status_code=502,
            detail=(
                "La API de Mascotas no aceptó la clave de la API de Adopciones. "
                "CLAVE_ADMIN debe tener el mismo valor en los dos servicios."
            )
        )

    if not respuesta.ok:
        raise HTTPException(
            status_code=502,
            detail="El servicio de Mascotas respondió con un error"
        )

    return resumir_mascota(respuesta.json()["mascota"])


def revertir_estado_mascota(id_mascota, estado):
    # Compensación: si la base de datos de adopciones falla después de
    # cambiar la mascota, se intenta dejarla en el estado que tenía.
    try:
        requests.patch(
            f"{API_MASCOTAS_URL}/mascotas/{id_mascota}/estado",
            json={"estado": estado},
            headers={"X-Clave-Admin": clave_admin()},
            timeout=10
        )
    except requests.RequestException:
        pass


def consultar_mascota(id_mascota):
    # Para consultas: si la API de Mascotas falla se devuelve None y la
    # solicitud se muestra igual, sin los datos de la mascota.
    try:
        respuesta = requests.get(
            f"{API_MASCOTAS_URL}/mascotas/{id_mascota}",
            timeout=10
        )
        respuesta.raise_for_status()
        return resumir_mascota(respuesta.json())

    except (requests.RequestException, ValueError, KeyError):
        return None


def consultar_catalogo():
    try:
        respuesta = requests.get(f"{API_MASCOTAS_URL}/mascotas", timeout=10)
        respuesta.raise_for_status()

        return {
            mascota["id_mascota"]: resumir_mascota(mascota)
            for mascota in respuesta.json()
        }

    except (requests.RequestException, ValueError, KeyError, TypeError):
        return {}


def bloquear_mascota(cursor, id_mascota):
    # Bloqueo de PostgreSQL que dura hasta el commit o el rollback.
    # Las operaciones que tocan la misma mascota (registrar, aprobar o
    # rechazar) se ejecutan una después de otra y no se cruzan.
    cursor.execute("SELECT pg_advisory_xact_lock(%s);", (id_mascota,))


def bloquear_solicitud_pendiente(cursor, id_solicitud):
    cursor.execute(
        "SELECT id_mascota FROM solicitudes_adopcion WHERE id_solicitud = %s;",
        (id_solicitud,)
    )

    fila = cursor.fetchone()

    if fila is None:
        raise HTTPException(
            status_code=404,
            detail="Solicitud no encontrada"
        )

    bloquear_mascota(cursor, fila[0])

    # Se vuelve a leer después del bloqueo para ver los cambios que
    # otra operación sobre la misma mascota haya confirmado.
    cursor.execute(
        f"""
        SELECT {COLUMNAS}
        FROM solicitudes_adopcion
        WHERE id_solicitud = %s
        FOR UPDATE;
        """,
        (id_solicitud,)
    )

    fila = cursor.fetchone()

    if fila[10] != "pendiente":
        raise HTTPException(
            status_code=409,
            detail=f"La solicitud ya fue {fila[10]}"
        )

    return convertir_solicitud(fila)


# ==================================================
# 4. ENDPOINTS
# ==================================================

@app.get("/", tags=["Servicio"], summary="Verificar el servicio")
def inicio():
    return {"mensaje": "API de Adopciones funcionando"}


@app.get(
    "/solicitudes",
    response_model=list[SolicitudRespuesta],
    responses=ERROR_401,
    dependencies=SOLO_FUNDACION,
    tags=["Solicitudes"],
    summary="Listar solicitudes (requiere clave)",
    description=(
        "Devuelve las solicitudes, primero las pendientes. Cada una incluye "
        "un resumen de la mascota obtenido de la API de Mascotas. "
        "Contiene datos personales, por eso exige `X-Clave-Admin`."
    )
)
def consultar_solicitudes(
    estado: Optional[EstadoSolicitud] = Query(None, description="Filtrar por estado"),
    id_mascota: Optional[int] = Query(
        None, gt=0, le=2147483647,
        description="Filtrar por mascota"
    )
):
    conexion = None
    cursor = None

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        cursor.execute(
            f"""
            SELECT {COLUMNAS}
            FROM solicitudes_adopcion
            WHERE (%s IS NULL OR estado = %s)
              AND (%s IS NULL OR id_mascota = %s)
            ORDER BY
                CASE estado WHEN 'pendiente' THEN 1 ELSE 2 END,
                fecha_solicitud DESC;
            """,
            (estado, estado, id_mascota, id_mascota)
        )

        filas = cursor.fetchall()

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Error al consultar las solicitudes"
        )

    finally:
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()

    # Una sola llamada a la API de Mascotas para todas las solicitudes
    catalogo = consultar_catalogo() if filas else {}

    return [
        convertir_solicitud(fila, catalogo.get(fila[1]))
        for fila in filas
    ]


@app.get(
    "/solicitudes/{id_solicitud}",
    response_model=SolicitudRespuesta,
    responses={**ERROR_401, 404: ERRORES[404]},
    dependencies=SOLO_FUNDACION,
    tags=["Solicitudes"],
    summary="Consultar una solicitud con los datos de su mascota (requiere clave)"
)
def consultar_solicitud(id_solicitud: IdSolicitud):
    conexion = None
    cursor = None

    try:
        # 1. Consultar la solicitud en PostgreSQL
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        cursor.execute(
            f"SELECT {COLUMNAS} FROM solicitudes_adopcion WHERE id_solicitud = %s;",
            (id_solicitud,)
        )

        fila = cursor.fetchone()

        if fila is None:
            raise HTTPException(
                status_code=404,
                detail="Solicitud no encontrada"
            )

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Error al consultar la solicitud"
        )

    finally:
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()

    # 2. Consultar la mascota en la API de Mascotas mediante HTTP
    return convertir_solicitud(fila, consultar_mascota(fila[1]))


@app.post(
    "/solicitudes",
    response_model=RegistroRespuesta,
    status_code=201,
    responses=ERRORES,
    tags=["Solicitudes"],
    summary="Registrar una solicitud de adopción",
    description=(
        "1. Consulta `GET /mascotas/{id}/disponibilidad` en la API de Mascotas.\n"
        "2. Si la mascota ya fue adoptada responde 409.\n"
        "3. Guarda la solicitud en estado `pendiente`.\n"
        "4. Si la mascota estaba `disponible`, la pasa a `en_proceso` "
        "con `PATCH /mascotas/{id}/estado`.\n\n"
        "Si el paso 4 falla, la solicitud no se guarda."
    )
)
def registrar_solicitud(datos: Solicitud):
    estado_original = None
    mascota_actualizada = False
    conexion = None
    cursor = None

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        # 1. Verificar la disponibilidad en la API de Mascotas
        bloquear_mascota(cursor, datos.id_mascota)
        disponibilidad = verificar_disponibilidad(datos.id_mascota)

        if not disponibilidad["disponible"]:
            raise HTTPException(
                status_code=409,
                detail=f"No se puede registrar la solicitud. {disponibilidad['mensaje']}"
            )

        estado_original = disponibilidad["estado"]

        # 2. Guardar la solicitud (la transacción sigue abierta)
        cursor.execute(
            f"""
            INSERT INTO solicitudes_adopcion (
                id_mascota, nombre_solicitante, documento, correo,
                telefono, pais, departamento, ciudad, tipo_vivienda,
                otras_mascotas, motivo
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING {COLUMNAS};
            """,
            (
                datos.id_mascota,
                datos.nombre_solicitante.strip(),
                datos.documento,
                datos.correo.strip().lower(),
                datos.telefono,
                datos.pais.strip(),
                datos.departamento.strip(),
                datos.ciudad.strip(),
                datos.tipo_vivienda,
                datos.otras_mascotas,
                datos.motivo.strip()
            )
        )

        fila = cursor.fetchone()

        # 3. Con la primera solicitud la mascota pasa a "en_proceso"
        if estado_original == "disponible":
            mascota = cambiar_estado_mascota(datos.id_mascota, "en_proceso")
            mascota_actualizada = True
        else:
            mascota = {
                "id_mascota": disponibilidad["id_mascota"],
                "nombre": disponibilidad["nombre"],
                "estado": disponibilidad["estado"]
            }

        # 4. Confirmar la transacción
        conexion.commit()

        return {
            "mensaje": (
                f"Solicitud #{fila[0]} registrada. La fundación la "
                f"revisará y te contactará."
            ),
            "solicitud": convertir_solicitud(fila, mascota)
        }

    except UniqueViolation:
        if conexion:
            conexion.rollback()

        raise HTTPException(
            status_code=409,
            detail="Ya tienes una solicitud pendiente para esta mascota"
        )

    except HTTPException:
        if conexion:
            conexion.rollback()

        raise

    except Exception:
        if mascota_actualizada:
            revertir_estado_mascota(datos.id_mascota, estado_original)

        if conexion:
            conexion.rollback()

        raise HTTPException(
            status_code=500,
            detail="Error al registrar la solicitud"
        )

    finally:
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()


@app.patch(
    "/solicitudes/{id_solicitud}/aprobar",
    response_model=DecisionRespuesta,
    responses={**ERROR_401, **ERRORES},
    dependencies=SOLO_FUNDACION,
    tags=["Gestión"],
    summary="Aprobar una solicitud (requiere clave)",
    description=(
        "1. Verifica que la solicitud siga `pendiente`.\n"
        "2. Verifica que la mascota no tenga otra adopción aprobada.\n"
        "3. Consulta la disponibilidad en la API de Mascotas.\n"
        "4. Aprueba la solicitud y rechaza las demás pendientes de la misma mascota.\n"
        "5. Marca la mascota como `adoptada` en la API de Mascotas.\n\n"
        "Si cualquier paso falla no se guarda ningún cambio. Las operaciones "
        "sobre una misma mascota se ejecutan en fila (bloqueo por mascota) y "
        "un índice único en la base de datos impide dos solicitudes aprobadas "
        "para la misma mascota."
    )
)
def aprobar_solicitud(id_solicitud: IdSolicitud, datos: Optional[Aprobacion] = None):
    estado_original = None
    mascota_actualizada = False
    conexion = None
    cursor = None

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        # 1. La solicitud debe seguir pendiente
        solicitud = bloquear_solicitud_pendiente(cursor, id_solicitud)
        id_mascota = solicitud["id_mascota"]

        # 2. Una mascota no puede tener dos adopciones aprobadas
        cursor.execute(
            """
            SELECT id_solicitud
            FROM solicitudes_adopcion
            WHERE id_mascota = %s AND estado = 'aprobada';
            """,
            (id_mascota,)
        )

        aprobada = cursor.fetchone()

        if aprobada:
            raise HTTPException(
                status_code=409,
                detail=(
                    "La mascota ya tiene una adopción aprobada "
                    f"(solicitud #{aprobada[0]})"
                )
            )

        # 3. Verificar en la API de Mascotas que siga sin adoptar
        disponibilidad = verificar_disponibilidad(id_mascota)

        if not disponibilidad["disponible"]:
            raise HTTPException(
                status_code=409,
                detail=disponibilidad["mensaje"]
            )

        estado_original = disponibilidad["estado"]

        # 4. Aprobar esta solicitud y rechazar las demás pendientes
        cursor.execute(
            f"""
            UPDATE solicitudes_adopcion
            SET estado = 'aprobada',
                observacion = %s,
                fecha_respuesta = NOW()
            WHERE id_solicitud = %s
            RETURNING {COLUMNAS};
            """,
            (
                datos.observacion.strip() if datos and datos.observacion else None,
                id_solicitud
            )
        )

        fila = cursor.fetchone()

        cursor.execute(
            """
            UPDATE solicitudes_adopcion
            SET estado = 'rechazada',
                observacion = %s,
                fecha_respuesta = NOW()
            WHERE id_mascota = %s AND estado = 'pendiente'
            RETURNING id_solicitud;
            """,
            (
                f"Rechazada automáticamente: {disponibilidad['nombre']} "
                f"fue adoptada con la solicitud #{id_solicitud}",
                id_mascota
            )
        )

        rechazadas = [registro[0] for registro in cursor.fetchall()]

        # 5. Marcar la mascota como adoptada en la API de Mascotas
        mascota = cambiar_estado_mascota(id_mascota, "adoptada")
        mascota_actualizada = True

        conexion.commit()

        adoptada = "adoptada" if mascota.get("sexo") == "hembra" else "adoptado"

        return {
            "mensaje": (
                f"Solicitud #{id_solicitud} aprobada. "
                f"{mascota['nombre']} quedó {adoptada}."
            ),
            "solicitud": convertir_solicitud(fila, mascota),
            "solicitudes_rechazadas": rechazadas
        }

    except UniqueViolation:
        if conexion:
            conexion.rollback()

        raise HTTPException(
            status_code=409,
            detail="La mascota ya tiene una adopción aprobada"
        )

    except HTTPException:
        if conexion:
            conexion.rollback()

        raise

    except Exception:
        if mascota_actualizada:
            revertir_estado_mascota(id_mascota, estado_original)

        if conexion:
            conexion.rollback()

        raise HTTPException(
            status_code=500,
            detail="Error al aprobar la solicitud"
        )

    finally:
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()


@app.patch(
    "/solicitudes/{id_solicitud}/rechazar",
    response_model=DecisionRespuesta,
    responses={**ERROR_401, **ERRORES},
    dependencies=SOLO_FUNDACION,
    tags=["Gestión"],
    summary="Rechazar una solicitud (requiere clave)",
    description=(
        "Rechaza una solicitud pendiente. Si la mascota se queda sin "
        "solicitudes pendientes, la API de Mascotas la devuelve a `disponible`."
    )
)
def rechazar_solicitud(id_solicitud: IdSolicitud, datos: Rechazo):
    mascota_actualizada = False
    conexion = None
    cursor = None

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        # 1. La solicitud debe seguir pendiente
        solicitud = bloquear_solicitud_pendiente(cursor, id_solicitud)
        id_mascota = solicitud["id_mascota"]

        # 2. Rechazar la solicitud
        cursor.execute(
            f"""
            UPDATE solicitudes_adopcion
            SET estado = 'rechazada',
                observacion = %s,
                fecha_respuesta = NOW()
            WHERE id_solicitud = %s
            RETURNING {COLUMNAS};
            """,
            (datos.observacion.strip(), id_solicitud)
        )

        fila = cursor.fetchone()

        # 3. Si no quedan solicitudes pendientes, la mascota vuelve a
        #    estar disponible en la API de Mascotas
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM solicitudes_adopcion
            WHERE id_mascota = %s AND estado = 'pendiente';
            """,
            (id_mascota,)
        )

        pendientes = cursor.fetchone()[0]
        mascota = None

        if pendientes == 0:
            disponibilidad = verificar_disponibilidad(id_mascota)

            if disponibilidad["estado"] == "en_proceso":
                mascota = cambiar_estado_mascota(id_mascota, "disponible")
                mascota_actualizada = True

        conexion.commit()

        if mascota is None:
            mascota = consultar_mascota(id_mascota)

        if mascota_actualizada:
            mensaje = (
                f"Solicitud #{id_solicitud} rechazada. "
                f"{mascota['nombre']} vuelve a estar disponible."
            )
        else:
            mensaje = f"Solicitud #{id_solicitud} rechazada."

        return {
            "mensaje": mensaje,
            "solicitud": convertir_solicitud(fila, mascota),
            "solicitudes_rechazadas": []
        }

    except HTTPException:
        if conexion:
            conexion.rollback()

        raise

    except Exception:
        if mascota_actualizada:
            revertir_estado_mascota(id_mascota, "en_proceso")

        if conexion:
            conexion.rollback()

        raise HTTPException(
            status_code=500,
            detail="Error al rechazar la solicitud"
        )

    finally:
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()
