
import os
import secrets
from datetime import date, datetime
from typing import Annotated, Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from con_db import obtener_conexion


app = FastAPI(
    title="API de Mascotas",
    description=(
        "Servicio de la Fundación Huellas de Esperanza para registrar las "
        "mascotas, consultarlas y controlar su disponibilidad.\n\n"
        "La API de Adopciones consume los endpoints de **Disponibilidad** "
        "para saber si una mascota puede recibir solicitudes y para "
        "actualizar su estado cuando una solicitud se aprueba o se rechaza."
    ),
    version="1.0.0",
    openapi_tags=[
        {
            "name": "Servicio",
            "description": "Verificación de que el servicio responde."
        },
        {
            "name": "Mascotas",
            "description": "Registro y consulta de mascotas."
        },
        {
            "name": "Disponibilidad",
            "description": (
                "Endpoints que usa la API de Adopciones para verificar "
                "y cambiar el estado de una mascota."
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
# 1. VALORES PERMITIDOS Y REGLAS DE ESTADO
# ==================================================

Especie = Literal["perro", "gato"]
Sexo = Literal["macho", "hembra"]
Tamano = Literal["pequeno", "mediano", "grande"]
EstadoMascota = Literal["disponible", "en_proceso", "adoptada"]

IdMascota = Annotated[
    int,
    Path(gt=0, le=2147483647, description="Identificador de la mascota")
]

# Cambios de estado permitidos. Una mascota adoptada solo sale de ese
# estado si la adopción se revierte; la API de Adopciones lo usa como
# compensación cuando no logra guardar una aprobación.
TRANSICIONES = {
    "disponible": {"en_proceso", "adoptada"},
    "en_proceso": {"disponible", "adoptada"},
    "adoptada": {"disponible", "en_proceso"},
}

MENSAJES_DISPONIBILIDAD = {
    "disponible": "La mascota está disponible para adopción.",
    "en_proceso": (
        "La mascota tiene solicitudes en revisión, "
        "pero todavía recibe nuevas solicitudes."
    ),
    "adoptada": "La mascota ya fue adoptada y no recibe solicitudes.",
}

COLUMNAS = """
    id_mascota, nombre, especie, raza, sexo, edad_meses, tamano,
    vacunado, esterilizado, descripcion, foto_url, estado,
    fecha_ingreso, fecha_actualizacion
"""


# ==================================================
# 2. MODELOS
# ==================================================

class Mascota(BaseModel):
    nombre: str = Field(min_length=2, max_length=60)
    especie: Especie
    raza: str = Field("Mestizo", min_length=2, max_length=60)
    sexo: Sexo
    edad_meses: int = Field(
        ge=0, le=300,
        description="Edad aproximada en meses"
    )
    tamano: Tamano
    vacunado: bool = False
    esterilizado: bool = False
    descripcion: Optional[str] = Field(None, max_length=600)
    foto_url: Optional[str] = Field(None, max_length=500)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "nombre": "Nala",
                    "especie": "gato",
                    "raza": "Criolla",
                    "sexo": "hembra",
                    "edad_meses": 10,
                    "tamano": "pequeno",
                    "vacunado": True,
                    "esterilizado": True,
                    "descripcion": "Llegó desde Villa del Rosario. Es tranquila y le gusta dormir al sol.",
                    "foto_url": None
                }
            ]
        }
    }


class MascotaRespuesta(BaseModel):
    id_mascota: int
    nombre: str
    especie: Especie
    raza: str
    sexo: Sexo
    edad_meses: int
    tamano: Tamano
    vacunado: bool
    esterilizado: bool
    descripcion: Optional[str]
    foto_url: Optional[str]
    estado: EstadoMascota
    fecha_ingreso: date
    fecha_actualizacion: datetime


class Disponibilidad(BaseModel):
    id_mascota: int
    nombre: str
    estado: EstadoMascota
    disponible: bool = Field(
        description="true si la mascota puede recibir solicitudes de adopción"
    )
    mensaje: str


class CambioEstado(BaseModel):
    estado: EstadoMascota

    model_config = {
        "json_schema_extra": {"examples": [{"estado": "adoptada"}]}
    }


class CambioEstadoRespuesta(BaseModel):
    mensaje: str
    estado_anterior: EstadoMascota
    mascota: MascotaRespuesta


class Error(BaseModel):
    detail: str


ERROR_404 = {404: {"model": Error, "description": "La mascota no existe"}}

ERROR_401 = {
    401: {"model": Error, "description": "Falta la clave de administrador o es incorrecta"}
}


# ==================================================
# 3. CLAVE DE LA FUNDACIÓN
# ==================================================
# Registrar mascotas y cambiar su estado exige el encabezado
# X-Clave-Admin con el valor de la variable de entorno CLAVE_ADMIN.
# La API de Adopciones envía la misma clave cuando cambia un estado.

esquema_clave = APIKeyHeader(
    name="X-Clave-Admin",
    auto_error=False,
    description="Clave de administrador de la fundación (variable CLAVE_ADMIN)"
)


def verificar_clave_admin(clave: Optional[str] = Security(esquema_clave)):
    esperada = os.getenv("CLAVE_ADMIN", "").strip()

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


def convertir_mascota(fila):
    return {
        "id_mascota": fila[0],
        "nombre": fila[1],
        "especie": fila[2],
        "raza": fila[3],
        "sexo": fila[4],
        "edad_meses": fila[5],
        "tamano": fila[6],
        "vacunado": fila[7],
        "esterilizado": fila[8],
        "descripcion": fila[9],
        "foto_url": fila[10],
        "estado": fila[11],
        "fecha_ingreso": fila[12],
        "fecha_actualizacion": fila[13]
    }


# ==================================================
# 4. ENDPOINTS
# ==================================================

@app.get("/", tags=["Servicio"], summary="Verificar el servicio")
def inicio():
    return {"mensaje": "API de Mascotas funcionando"}


@app.get(
    "/mascotas",
    response_model=list[MascotaRespuesta],
    tags=["Mascotas"],
    summary="Listar mascotas",
    description=(
        "Devuelve las mascotas registradas. Aparecen primero las "
        "disponibles, luego las que están en proceso y al final las adoptadas."
    )
)
def consultar_mascotas(
    especie: Optional[Especie] = Query(None, description="Filtrar por especie"),
    estado: Optional[EstadoMascota] = Query(None, description="Filtrar por estado")
):
    conexion = None
    cursor = None

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        cursor.execute(
            f"""
            SELECT {COLUMNAS}
            FROM mascotas
            WHERE (%s IS NULL OR especie = %s)
              AND (%s IS NULL OR estado = %s)
            ORDER BY
                CASE estado
                    WHEN 'disponible' THEN 1
                    WHEN 'en_proceso' THEN 2
                    ELSE 3
                END,
                id_mascota;
            """,
            (especie, especie, estado, estado)
        )

        return [convertir_mascota(fila) for fila in cursor.fetchall()]

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Error al consultar las mascotas"
        )

    finally:
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()


@app.get(
    "/mascotas/{id_mascota}",
    response_model=MascotaRespuesta,
    responses=ERROR_404,
    tags=["Mascotas"],
    summary="Consultar una mascota"
)
def consultar_mascota(id_mascota: IdMascota):
    conexion = None
    cursor = None

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        cursor.execute(
            f"SELECT {COLUMNAS} FROM mascotas WHERE id_mascota = %s;",
            (id_mascota,)
        )

        fila = cursor.fetchone()

        if fila is None:
            raise HTTPException(
                status_code=404,
                detail="Mascota no encontrada"
            )

        return convertir_mascota(fila)

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Error al consultar la mascota"
        )

    finally:
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()


@app.post(
    "/mascotas",
    response_model=MascotaRespuesta,
    status_code=201,
    responses=ERROR_401,
    dependencies=SOLO_FUNDACION,
    tags=["Mascotas"],
    summary="Registrar una mascota (requiere clave)",
    description=(
        "Toda mascota nueva queda en estado `disponible`. "
        "Requiere el encabezado `X-Clave-Admin`."
    )
)
def registrar_mascota(datos: Mascota):
    conexion = None
    cursor = None

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        cursor.execute(
            f"""
            INSERT INTO mascotas (
                nombre, especie, raza, sexo, edad_meses, tamano,
                vacunado, esterilizado, descripcion, foto_url
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING {COLUMNAS};
            """,
            (
                datos.nombre.strip(),
                datos.especie,
                datos.raza.strip(),
                datos.sexo,
                datos.edad_meses,
                datos.tamano,
                datos.vacunado,
                datos.esterilizado,
                datos.descripcion,
                datos.foto_url or None
            )
        )

        fila = cursor.fetchone()
        conexion.commit()

        return convertir_mascota(fila)

    except Exception:
        if conexion:
            conexion.rollback()

        raise HTTPException(
            status_code=500,
            detail="Error al registrar la mascota"
        )

    finally:
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()


@app.get(
    "/mascotas/{id_mascota}/disponibilidad",
    response_model=Disponibilidad,
    responses=ERROR_404,
    tags=["Disponibilidad"],
    summary="Verificar si una mascota puede ser adoptada",
    description=(
        "`disponible` es true cuando la mascota está en estado "
        "`disponible` o `en_proceso`. Una mascota adoptada ya no "
        "recibe solicitudes."
    )
)
def consultar_disponibilidad(id_mascota: IdMascota):
    mascota = consultar_mascota(id_mascota)
    estado = mascota["estado"]

    return {
        "id_mascota": mascota["id_mascota"],
        "nombre": mascota["nombre"],
        "estado": estado,
        "disponible": estado != "adoptada",
        "mensaje": MENSAJES_DISPONIBILIDAD[estado]
    }


@app.patch(
    "/mascotas/{id_mascota}/estado",
    response_model=CambioEstadoRespuesta,
    responses={
        **ERROR_401,
        **ERROR_404,
        409: {"model": Error, "description": "Cambio de estado no permitido"}
    },
    dependencies=SOLO_FUNDACION,
    tags=["Disponibilidad"],
    summary="Cambiar el estado de una mascota (requiere clave)",
    description=(
        "Lo usa la API de Adopciones, que envía el encabezado `X-Clave-Admin`.\n\n"
        "Cambios permitidos:\n\n"
        "- `disponible` → `en_proceso` o `adoptada`\n"
        "- `en_proceso` → `disponible` o `adoptada`\n"
        "- `adoptada` → `disponible` o `en_proceso` (solo si la adopción se revierte)\n\n"
        "Marcar como `adoptada` una mascota que ya lo está devuelve 409. "
        "Así el servicio de Mascotas también impide una segunda adopción."
    )
)
def cambiar_estado(id_mascota: IdMascota, datos: CambioEstado):
    conexion = None
    cursor = None

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        # FOR UPDATE bloquea la fila hasta el commit para que dos
        # cambios simultáneos no lean el mismo estado anterior.
        cursor.execute(
            """
            SELECT estado
            FROM mascotas
            WHERE id_mascota = %s
            FOR UPDATE;
            """,
            (id_mascota,)
        )

        fila = cursor.fetchone()

        if fila is None:
            raise HTTPException(
                status_code=404,
                detail="Mascota no encontrada"
            )

        estado_anterior = fila[0]
        estado_nuevo = datos.estado

        if estado_anterior == "adoptada" and estado_nuevo == "adoptada":
            raise HTTPException(
                status_code=409,
                detail="La mascota ya fue adoptada"
            )

        if (
            estado_nuevo != estado_anterior
            and estado_nuevo not in TRANSICIONES[estado_anterior]
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"No se puede cambiar el estado de '{estado_anterior}' "
                    f"a '{estado_nuevo}'"
                )
            )

        cursor.execute(
            f"""
            UPDATE mascotas
            SET estado = %s,
                fecha_actualizacion = NOW()
            WHERE id_mascota = %s
            RETURNING {COLUMNAS};
            """,
            (estado_nuevo, id_mascota)
        )

        mascota = convertir_mascota(cursor.fetchone())
        conexion.commit()

        if estado_nuevo == estado_anterior:
            mensaje = f"La mascota ya estaba en estado '{estado_nuevo}'"
        else:
            mensaje = (
                f"Estado actualizado de '{estado_anterior}' "
                f"a '{estado_nuevo}'"
            )

        return {
            "mensaje": mensaje,
            "estado_anterior": estado_anterior,
            "mascota": mascota
        }

    except HTTPException:
        if conexion:
            conexion.rollback()

        raise

    except Exception:
        if conexion:
            conexion.rollback()

        raise HTTPException(
            status_code=500,
            detail="Error al actualizar el estado de la mascota"
        )

    finally:
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()
