
import base64
import hashlib
import os
import re
import secrets
from datetime import date, datetime
from typing import Annotated, Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request, Response, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from con_db import obtener_conexion


app = FastAPI(
    title="API de Mascotas",
    description=(
        "Servicio de la Fundación Huellas de Esperanza para registrar las "
        "mascotas, consultarlas y controlar su disponibilidad.\n\n"
        "Cualquier persona puede dar una mascota en adopción: queda "
        "`en_revision` hasta que la fundación la publique.\n\n"
        "La API de Adopciones consume los endpoints de **Disponibilidad** "
        "para saber si una mascota puede recibir solicitudes y para "
        "actualizar su estado cuando una solicitud se aprueba o se rechaza."
    ),
    version="2.0.0",
    openapi_tags=[
        {
            "name": "Servicio",
            "description": "Verificación de que el servicio responde."
        },
        {
            "name": "Mascotas",
            "description": "Registro y consulta de mascotas publicadas."
        },
        {
            "name": "Publicaciones",
            "description": (
                "Revisión de las mascotas que envía la comunidad. "
                "Solo la fundación (requiere clave)."
            )
        },
        {
            "name": "Gestión de mascotas",
            "description": "Editar, retirar o volver a publicar. Solo la fundación (requiere clave)."
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
    allow_methods=["GET", "POST", "PUT", "PATCH"],
    allow_headers=["*"],
)


# ==================================================
# 1. VALORES PERMITIDOS Y REGLAS DE ESTADO
# ==================================================

Especie = Literal["perro", "gato"]
Sexo = Literal["macho", "hembra"]
Tamano = Literal["pequeno", "mediano", "grande"]
Origen = Literal["fundacion", "comunidad"]

# en_revision y no_publicada no se ven en el catálogo público
EstadoMascota = Literal[
    "en_revision", "no_publicada", "disponible", "en_proceso", "adoptada", "retirada"
]
EstadoPublicado = Literal["disponible", "en_proceso", "adoptada"]
ESTADOS_PUBLICADOS = ("disponible", "en_proceso", "adoptada")

IdMascota = Annotated[
    int,
    Path(gt=0, le=2147483647, description="Identificador de la mascota")
]

# Cambios de estado permitidos para mascotas publicadas. Una mascota
# adoptada solo sale de ese estado si la adopción se revierte; la API de
# Adopciones lo usa como compensación cuando no logra guardar una aprobación.
TRANSICIONES = {
    "disponible": {"en_proceso", "adoptada"},
    "en_proceso": {"disponible", "adoptada"},
    "adoptada": {"disponible", "en_proceso"},
}

MENSAJES_DISPONIBILIDAD = {
    "en_revision": "La mascota todavía no ha sido publicada por la fundación.",
    "no_publicada": "La fundación no aprobó la publicación de esta mascota.",
    "disponible": "La mascota está disponible para adopción.",
    "en_proceso": (
        "La mascota tiene solicitudes en revisión, "
        "pero todavía recibe nuevas solicitudes."
    ),
    "adoptada": "La mascota ya fue adoptada y no recibe solicitudes.",
    "retirada": "La fundación retiró esta mascota del catálogo.",
}

COLUMNAS = """
    id_mascota, nombre, especie, raza, sexo, edad_meses, tamano,
    vacunado, esterilizado, descripcion, foto_url, estado,
    fecha_ingreso, fecha_actualizacion, origen, pais, departamento,
    ciudad, contacto_nombre, contacto_telefono, contacto_correo,
    observacion_revision, motivo_retiro
"""

# Límite de mascotas que puede enviar una misma IP por hora sin la clave
# de la fundación. Se puede cambiar con la variable LIMITE_ENVIOS_POR_HORA.
LIMITE_ENVIOS_POR_HORA = int(os.getenv("LIMITE_ENVIOS_POR_HORA", "5"))

# Fotos: hasta 3 por mascota, 1 MB cada una. El frontend las reduce
# antes de enviarlas, así que en la práctica pesan entre 100 y 300 KB.
MAXIMO_FOTOS = 3
MAXIMO_BYTES_FOTO = 1_000_000
PATRON_FOTO = re.compile(r"^data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=\s]+)$")
FIRMAS_FOTO = {
    "image/jpeg": lambda datos: datos.startswith(b"\xff\xd8\xff"),
    "image/png": lambda datos: datos.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/webp": lambda datos: datos[:4] == b"RIFF" and datos[8:12] == b"WEBP",
}


# ==================================================
# 2. MODELOS
# ==================================================

class Contacto(BaseModel):
    nombre: str = Field(min_length=3, max_length=100)
    telefono: str = Field(
        pattern=r"^\+?\d{7,14}$",
        description="Solo dígitos, con + opcional al inicio"
    )
    correo: str = Field(
        max_length=120,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )


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
    foto_url: Optional[str] = Field(
        None, max_length=500,
        description="Foto externa opcional. Las fotos subidas van en `fotos`"
    )
    pais: Optional[str] = Field(None, min_length=2, max_length=80)
    departamento: Optional[str] = Field(None, min_length=2, max_length=80)
    ciudad: Optional[str] = Field(None, min_length=2, max_length=80)
    contacto: Optional[Contacto] = Field(
        None,
        description="Quién entrega la mascota. Obligatorio si no es la fundación"
    )
    fotos: list[str] = Field(
        default=[],
        max_length=MAXIMO_FOTOS,
        description="Hasta 3 imágenes como data URL (JPEG, PNG o WebP), máximo 1 MB cada una"
    )

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
                    "pais": "Colombia",
                    "departamento": "Norte de Santander",
                    "ciudad": "Villa del Rosario",
                    "contacto": {
                        "nombre": "Andrés Ropero",
                        "telefono": "3157778899",
                        "correo": "andres.ropero@example.com"
                    },
                    "fotos": []
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
    fotos: list[str] = Field(
        description="Rutas de las fotos subidas, relativas a esta API"
    )
    estado: EstadoMascota
    origen: Origen
    pais: Optional[str]
    departamento: Optional[str]
    ciudad: Optional[str]
    fecha_ingreso: date
    fecha_actualizacion: datetime


class PublicacionRespuesta(MascotaRespuesta):
    contacto: Optional[Contacto]
    observacion_revision: Optional[str]
    motivo_retiro: Optional[str]


class Disponibilidad(BaseModel):
    id_mascota: int
    nombre: str
    estado: EstadoMascota
    disponible: bool = Field(
        description="true si la mascota puede recibir solicitudes de adopción"
    )
    mensaje: str


class CambioEstado(BaseModel):
    estado: EstadoPublicado

    model_config = {
        "json_schema_extra": {"examples": [{"estado": "adoptada"}]}
    }


class CambioEstadoRespuesta(BaseModel):
    mensaje: str
    estado_anterior: EstadoMascota
    mascota: MascotaRespuesta


class Revision(BaseModel):
    observacion: Optional[str] = Field(None, max_length=500)


class EdicionMascota(BaseModel):
    nombre: str = Field(min_length=2, max_length=60)
    especie: Especie
    raza: str = Field(min_length=2, max_length=60)
    sexo: Sexo
    edad_meses: int = Field(ge=0, le=300)
    tamano: Tamano
    vacunado: bool
    esterilizado: bool
    descripcion: Optional[str] = Field(None, max_length=600)
    pais: Optional[str] = Field(None, min_length=2, max_length=80)
    departamento: Optional[str] = Field(None, min_length=2, max_length=80)
    ciudad: Optional[str] = Field(None, min_length=2, max_length=80)


class Retiro(BaseModel):
    motivo: str = Field(
        min_length=5, max_length=500,
        description="Por qué sale del catálogo"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{"motivo": "La reclamó su dueño con fotos y carné de vacunas"}]
        }
    }


class RechazoPublicacion(BaseModel):
    observacion: str = Field(
        min_length=5, max_length=500,
        description="Motivo por el que no se publica"
    )


class Error(BaseModel):
    detail: str


ERROR_404 = {404: {"model": Error, "description": "La mascota no existe"}}

ERROR_401 = {
    401: {"model": Error, "description": "Falta la clave de administrador o es incorrecta"}
}


def convertir_mascota(fila, fotos=None, privado=False):
    mascota = {
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
        "fotos": fotos or [],
        "estado": fila[11],
        "origen": fila[14],
        "pais": fila[15],
        "departamento": fila[16],
        "ciudad": fila[17],
        "fecha_ingreso": fila[12],
        "fecha_actualizacion": fila[13]
    }

    # Los datos de contacto de quien entrega la mascota solo los ve la fundación
    if privado:
        mascota["contacto"] = {
            "nombre": fila[18],
            "telefono": fila[19],
            "correo": fila[20]
        } if fila[18] else None
        mascota["observacion_revision"] = fila[21]
        mascota["motivo_retiro"] = fila[22]

    return mascota


def ruta_foto(id_mascota, orden, huella):
    # La huella cambia si cambia la imagen. Así el navegador no muestra una
    # foto vieja guardada en caché cuando un id de mascota se reutiliza.
    return f"/mascotas/{id_mascota}/fotos/{orden}?v={huella}"


def huella_foto(contenido):
    return hashlib.md5(contenido).hexdigest()[:10]


def rutas_fotos(cursor, ids):
    if not ids:
        return {}

    cursor.execute(
        """
        SELECT id_mascota, orden, left(md5(contenido), 10)
        FROM fotos_mascotas
        WHERE id_mascota = ANY(%s)
        ORDER BY id_mascota, orden;
        """,
        (list(ids),)
    )

    rutas = {}

    for id_mascota, orden, huella in cursor.fetchall():
        rutas.setdefault(id_mascota, []).append(
            ruta_foto(id_mascota, orden, huella)
        )

    return rutas


def huella_ip(request):
    # En Vercel, x-forwarded-for trae la IP real del visitante. En local
    # se usa la del cliente. Se guarda solo la huella SHA-256.
    reenviada = request.headers.get("x-forwarded-for", "")
    ip = reenviada.split(",")[0].strip()

    if not ip:
        ip = request.client.host if request.client else "desconocida"

    return hashlib.sha256(f"huellas-de-esperanza:{ip}".encode()).hexdigest()


def verificar_limite_envios(cursor, huella):
    cursor.execute(
        """
        SELECT COUNT(*),
               EXTRACT(EPOCH FROM MIN(fecha) + INTERVAL '1 hour' - NOW())
        FROM envios_publicos
        WHERE huella_ip = %s
          AND fecha > NOW() - INTERVAL '1 hour';
        """,
        (huella,)
    )

    cantidad, segundos = cursor.fetchone()

    if cantidad >= LIMITE_ENVIOS_POR_HORA:
        minutos = max(1, round((segundos or 0) / 60))

        raise HTTPException(
            status_code=429,
            detail=(
                f"Llegaste al límite de {LIMITE_ENVIOS_POR_HORA} publicaciones por hora. "
                f"Podrás enviar otra en unos {minutos} minutos."
            ),
            headers={"Retry-After": str(minutos * 60)}
        )


def decodificar_foto(numero, valor):
    coincidencia = PATRON_FOTO.match(valor.strip())

    if not coincidencia:
        raise HTTPException(
            status_code=422,
            detail=f"La foto {numero} debe ser una imagen JPEG, PNG o WebP"
        )

    tipo = coincidencia.group(1)

    try:
        datos = base64.b64decode(coincidencia.group(2), validate=False)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"La foto {numero} no se pudo leer"
        )

    if len(datos) > MAXIMO_BYTES_FOTO:
        raise HTTPException(
            status_code=422,
            detail=f"La foto {numero} pesa más de 1 MB"
        )

    # Se revisan los primeros bytes para no guardar archivos que no son imágenes
    if not FIRMAS_FOTO[tipo](datos):
        raise HTTPException(
            status_code=422,
            detail=f"La foto {numero} no es una imagen válida"
        )

    return tipo, datos


# ==================================================
# 3. CLAVE DE LA FUNDACIÓN
# ==================================================
# Revisar publicaciones y cambiar el estado de una mascota exige el
# encabezado X-Clave-Admin con el valor de la variable CLAVE_ADMIN.
# La API de Adopciones envía la misma clave cuando cambia un estado.
# Si la fundación registra una mascota con su clave, se publica de inmediato.

esquema_clave = APIKeyHeader(
    name="X-Clave-Admin",
    auto_error=False,
    description="Clave de administrador de la fundación (variable CLAVE_ADMIN)"
)


def es_fundacion(clave):
    esperada = os.getenv("CLAVE_ADMIN", "").strip()

    # compare_digest evita deducir la clave midiendo el tiempo de respuesta.
    return bool(esperada) and bool(clave) and secrets.compare_digest(
        clave.strip().encode(), esperada.encode()
    )


def verificar_clave_admin(clave: Optional[str] = Security(esquema_clave)):
    if not os.getenv("CLAVE_ADMIN", "").strip():
        raise HTTPException(
            status_code=503,
            detail="El servidor no tiene configurada la variable CLAVE_ADMIN"
        )

    if not es_fundacion(clave):
        raise HTTPException(
            status_code=401,
            detail="Clave de administrador incorrecta"
        )


SOLO_FUNDACION = [Depends(verificar_clave_admin)]


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
    summary="Listar mascotas publicadas",
    description=(
        "Devuelve las mascotas del catálogo. Aparecen primero las "
        "disponibles, luego las que están en proceso y al final las adoptadas. "
        "Las mascotas en revisión no aparecen aquí."
    )
)
def consultar_mascotas(
    especie: Optional[Especie] = Query(None, description="Filtrar por especie"),
    estado: Optional[EstadoPublicado] = Query(None, description="Filtrar por estado")
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
            WHERE estado IN %s
              AND (%s IS NULL OR especie = %s)
              AND (%s IS NULL OR estado = %s)
            ORDER BY
                CASE estado
                    WHEN 'disponible' THEN 1
                    WHEN 'en_proceso' THEN 2
                    ELSE 3
                END,
                id_mascota;
            """,
            (ESTADOS_PUBLICADOS, especie, especie, estado, estado)
        )

        filas = cursor.fetchall()
        fotos = rutas_fotos(cursor, [fila[0] for fila in filas])

        return [convertir_mascota(fila, fotos.get(fila[0])) for fila in filas]

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


def buscar_mascota(id_mascota, privado=False):
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

        fotos = rutas_fotos(cursor, [id_mascota])

        return convertir_mascota(fila, fotos.get(id_mascota), privado)

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


@app.get(
    "/mascotas/{id_mascota}",
    response_model=MascotaRespuesta,
    responses=ERROR_404,
    tags=["Mascotas"],
    summary="Consultar una mascota",
    description="Las mascotas sin publicar solo las puede consultar la fundación."
)
def consultar_mascota(
    id_mascota: IdMascota,
    clave: Optional[str] = Security(esquema_clave)
):
    mascota = buscar_mascota(id_mascota)

    if mascota["estado"] not in ESTADOS_PUBLICADOS and not es_fundacion(clave):
        raise HTTPException(
            status_code=404,
            detail="Mascota no encontrada"
        )

    return mascota


@app.get(
    "/mascotas/{id_mascota}/fotos/{orden}",
    response_class=Response,
    responses={
        200: {"content": {"image/jpeg": {}, "image/png": {}, "image/webp": {}}},
        404: {"model": Error, "description": "La foto no existe"}
    },
    tags=["Mascotas"],
    summary="Descargar una foto de la mascota"
)
def consultar_foto(
    id_mascota: IdMascota,
    orden: int = Path(ge=1, le=MAXIMO_FOTOS, description="Número de la foto (1 a 3)")
):
    conexion = None
    cursor = None

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        cursor.execute(
            """
            SELECT tipo, contenido
            FROM fotos_mascotas
            WHERE id_mascota = %s AND orden = %s;
            """,
            (id_mascota, orden)
        )

        fila = cursor.fetchone()

        if fila is None:
            raise HTTPException(
                status_code=404,
                detail="Foto no encontrada"
            )

        # Las fotos no cambian, el navegador puede guardarlas un día.
        return Response(
            content=bytes(fila[1]),
            media_type=fila[0],
            headers={"Cache-Control": "public, max-age=86400"}
        )

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Error al consultar la foto"
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
    tags=["Mascotas"],
    summary="Dar una mascota en adopción",
    description=(
        "Cualquier persona puede enviar una mascota. Debe incluir `contacto`, "
        "la ubicación (`pais`, `departamento`, `ciudad`) y al menos una foto. "
        "La mascota queda `en_revision` hasta que la fundación la publique.\n\n"
        "Si la petición trae el encabezado `X-Clave-Admin` correcto, la registra "
        "la fundación: queda `disponible` de inmediato y el contacto es opcional.\n\n"
        "Sin la clave, una misma IP puede enviar máximo 5 mascotas por hora "
        "(variable `LIMITE_ENVIOS_POR_HORA`). Al pasarse responde 429."
    ),
    responses={429: {"model": Error, "description": "Se superó el límite de envíos por hora"}}
)
def registrar_mascota(
    datos: Mascota,
    request: Request,
    clave: Optional[str] = Security(esquema_clave)
):
    fundacion = es_fundacion(clave)

    if not fundacion:
        faltantes = []

        if datos.contacto is None:
            faltantes.append("datos de contacto")

        if not (datos.pais and datos.departamento and datos.ciudad):
            faltantes.append("ubicación")

        if not datos.fotos:
            faltantes.append("al menos una foto")

        if not datos.descripcion or len(datos.descripcion.strip()) < 20:
            faltantes.append("descripción de al menos 20 caracteres")

        if faltantes:
            raise HTTPException(
                status_code=422,
                detail=f"Falta información: {', '.join(faltantes)}"
            )

    fotos = [
        decodificar_foto(numero, valor)
        for numero, valor in enumerate(datos.fotos, start=1)
    ]

    contacto = datos.contacto
    conexion = None
    cursor = None

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        # Protección contra spam: solo para envíos sin la clave
        if not fundacion:
            huella = huella_ip(request)
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s));", (huella,))
            verificar_limite_envios(cursor, huella)

        cursor.execute(
            f"""
            INSERT INTO mascotas (
                nombre, especie, raza, sexo, edad_meses, tamano,
                vacunado, esterilizado, descripcion, foto_url, estado,
                origen, pais, departamento, ciudad, contacto_nombre,
                contacto_telefono, contacto_correo
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s)
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
                datos.descripcion.strip() if datos.descripcion else None,
                datos.foto_url or None,
                "disponible" if fundacion else "en_revision",
                "fundacion" if fundacion else "comunidad",
                datos.pais,
                datos.departamento,
                datos.ciudad,
                contacto.nombre.strip() if contacto else None,
                contacto.telefono if contacto else None,
                contacto.correo.strip().lower() if contacto else None
            )
        )

        fila = cursor.fetchone()
        id_mascota = fila[0]

        for orden, (tipo, contenido) in enumerate(fotos, start=1):
            cursor.execute(
                """
                INSERT INTO fotos_mascotas (id_mascota, orden, tipo, contenido)
                VALUES (%s, %s, %s, %s);
                """,
                (id_mascota, orden, tipo, contenido)
            )

        if not fundacion:
            cursor.execute(
                "INSERT INTO envios_publicos (huella_ip) VALUES (%s);",
                (huella,)
            )
            # Los registros de más de un día ya no sirven para el límite
            cursor.execute(
                "DELETE FROM envios_publicos WHERE fecha < NOW() - INTERVAL '1 day';"
            )

        conexion.commit()

        rutas = [
            ruta_foto(id_mascota, orden, huella_foto(contenido))
            for orden, (tipo, contenido) in enumerate(fotos, start=1)
        ]

        return convertir_mascota(fila, rutas)

    except HTTPException:
        if conexion:
            conexion.rollback()

        raise

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
    "/publicaciones",
    response_model=list[PublicacionRespuesta],
    responses=ERROR_401,
    dependencies=SOLO_FUNDACION,
    tags=["Publicaciones"],
    summary="Listar mascotas enviadas por la comunidad (requiere clave)",
    description="Incluye los datos de contacto de quien entrega la mascota."
)
def consultar_publicaciones(
    estado: Literal["en_revision", "no_publicada", "retirada", "todas"] = Query(
        "en_revision",
        description=(
            "`todas` incluye también las ya publicadas. `retirada` muestra "
            "las mascotas que la fundación sacó del catálogo, de cualquier origen"
        )
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
            FROM mascotas
            WHERE (origen = 'comunidad' OR estado = 'retirada')
              AND (%s = 'todas' OR estado = %s)
            ORDER BY
                CASE estado WHEN 'en_revision' THEN 1 ELSE 2 END,
                fecha_actualizacion DESC;
            """,
            (estado, estado)
        )

        filas = cursor.fetchall()
        fotos = rutas_fotos(cursor, [fila[0] for fila in filas])

        return [
            convertir_mascota(fila, fotos.get(fila[0]), privado=True)
            for fila in filas
        ]

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Error al consultar las publicaciones"
        )

    finally:
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()


def resolver_publicacion(id_mascota, estado_nuevo, observacion):
    conexion = None
    cursor = None

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        cursor.execute(
            f"""
            UPDATE mascotas
            SET estado = %s,
                observacion_revision = %s,
                fecha_actualizacion = NOW()
            WHERE id_mascota = %s AND estado = 'en_revision'
            RETURNING {COLUMNAS};
            """,
            (estado_nuevo, observacion, id_mascota)
        )

        fila = cursor.fetchone()

        if fila is None:
            # O no existe, o ya se había revisado
            cursor.execute(
                "SELECT estado FROM mascotas WHERE id_mascota = %s;",
                (id_mascota,)
            )
            actual = cursor.fetchone()

            if actual is None:
                raise HTTPException(
                    status_code=404,
                    detail="Mascota no encontrada"
                )

            raise HTTPException(
                status_code=409,
                detail=f"La mascota no está en revisión (estado actual: {actual[0]})"
            )

        fotos = rutas_fotos(cursor, [id_mascota])
        conexion.commit()

        return convertir_mascota(fila, fotos.get(id_mascota), privado=True)

    except HTTPException:
        if conexion:
            conexion.rollback()

        raise

    except Exception:
        if conexion:
            conexion.rollback()

        raise HTTPException(
            status_code=500,
            detail="Error al revisar la publicación"
        )

    finally:
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()


@app.patch(
    "/mascotas/{id_mascota}/publicar",
    response_model=PublicacionRespuesta,
    responses={
        **ERROR_401,
        **ERROR_404,
        409: {"model": Error, "description": "La mascota no está en revisión"}
    },
    dependencies=SOLO_FUNDACION,
    tags=["Publicaciones"],
    summary="Publicar una mascota enviada por la comunidad (requiere clave)",
    description="Pasa de `en_revision` a `disponible` y aparece en el catálogo."
)
def publicar_mascota(id_mascota: IdMascota, datos: Optional[Revision] = None):
    observacion = datos.observacion.strip() if datos and datos.observacion else None
    return resolver_publicacion(id_mascota, "disponible", observacion)


@app.patch(
    "/mascotas/{id_mascota}/rechazar-publicacion",
    response_model=PublicacionRespuesta,
    responses={
        **ERROR_401,
        **ERROR_404,
        409: {"model": Error, "description": "La mascota no está en revisión"}
    },
    dependencies=SOLO_FUNDACION,
    tags=["Publicaciones"],
    summary="No publicar una mascota enviada por la comunidad (requiere clave)",
    description="Pasa de `en_revision` a `no_publicada`. El motivo es obligatorio."
)
def rechazar_publicacion(id_mascota: IdMascota, datos: RechazoPublicacion):
    return resolver_publicacion(id_mascota, "no_publicada", datos.observacion.strip())


@app.put(
    "/mascotas/{id_mascota}",
    response_model=PublicacionRespuesta,
    responses={**ERROR_401, **ERROR_404},
    dependencies=SOLO_FUNDACION,
    tags=["Gestión de mascotas"],
    summary="Editar los datos de una mascota (requiere clave)",
    description=(
        "Corrige nombre, especie, raza, sexo, edad, tamaño, vacunas, "
        "esterilización, descripción y ubicación. No cambia el estado ni las fotos."
    )
)
def editar_mascota(id_mascota: IdMascota, datos: EdicionMascota):
    conexion = None
    cursor = None

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        cursor.execute(
            f"""
            UPDATE mascotas
            SET nombre = %s, especie = %s, raza = %s, sexo = %s,
                edad_meses = %s, tamano = %s, vacunado = %s,
                esterilizado = %s, descripcion = %s, pais = %s,
                departamento = %s, ciudad = %s,
                fecha_actualizacion = NOW()
            WHERE id_mascota = %s
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
                datos.descripcion.strip() if datos.descripcion else None,
                datos.pais,
                datos.departamento,
                datos.ciudad,
                id_mascota
            )
        )

        fila = cursor.fetchone()

        if fila is None:
            raise HTTPException(
                status_code=404,
                detail="Mascota no encontrada"
            )

        fotos = rutas_fotos(cursor, [id_mascota])
        conexion.commit()

        return convertir_mascota(fila, fotos.get(id_mascota), privado=True)

    except HTTPException:
        if conexion:
            conexion.rollback()

        raise

    except Exception:
        if conexion:
            conexion.rollback()

        raise HTTPException(
            status_code=500,
            detail="Error al editar la mascota"
        )

    finally:
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()


def cambiar_retiro(id_mascota, estados_permitidos, estado_nuevo, motivo):
    conexion = None
    cursor = None

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        cursor.execute(
            "SELECT estado FROM mascotas WHERE id_mascota = %s FOR UPDATE;",
            (id_mascota,)
        )

        fila = cursor.fetchone()

        if fila is None:
            raise HTTPException(
                status_code=404,
                detail="Mascota no encontrada"
            )

        estado_actual = fila[0]

        if estado_actual not in estados_permitidos:
            mensajes = {
                "en_proceso": (
                    "La mascota tiene solicitudes pendientes en la API de "
                    "Adopciones. Recházalas antes de retirarla."
                ),
                "adoptada": "La mascota ya fue adoptada y queda en el historial.",
                "retirada": "La mascota ya está retirada del catálogo.",
            }

            raise HTTPException(
                status_code=409,
                detail=mensajes.get(
                    estado_actual,
                    f"No se puede hacer este cambio desde el estado '{estado_actual}'"
                )
            )

        cursor.execute(
            f"""
            UPDATE mascotas
            SET estado = %s,
                motivo_retiro = %s,
                fecha_actualizacion = NOW()
            WHERE id_mascota = %s
            RETURNING {COLUMNAS};
            """,
            (estado_nuevo, motivo, id_mascota)
        )

        fila = cursor.fetchone()
        fotos = rutas_fotos(cursor, [id_mascota])
        conexion.commit()

        return convertir_mascota(fila, fotos.get(id_mascota), privado=True)

    except HTTPException:
        if conexion:
            conexion.rollback()

        raise

    except Exception:
        if conexion:
            conexion.rollback()

        raise HTTPException(
            status_code=500,
            detail="Error al actualizar la mascota"
        )

    finally:
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()


@app.patch(
    "/mascotas/{id_mascota}/retirar",
    response_model=PublicacionRespuesta,
    responses={
        **ERROR_401,
        **ERROR_404,
        409: {"model": Error, "description": "La mascota no se puede retirar en su estado actual"}
    },
    dependencies=SOLO_FUNDACION,
    tags=["Gestión de mascotas"],
    summary="Retirar una mascota del catálogo (requiere clave)",
    description=(
        "Para mascotas que fallecieron, que reclamó su dueño o que se "
        "registraron por error. Se permite desde `disponible`, `en_revision` "
        "o `no_publicada`. Si está `en_proceso` responde 409: primero hay que "
        "rechazar sus solicitudes pendientes en la API de Adopciones."
    )
)
def retirar_mascota(id_mascota: IdMascota, datos: Retiro):
    return cambiar_retiro(
        id_mascota,
        ("disponible", "en_revision", "no_publicada"),
        "retirada",
        datos.motivo.strip()
    )


@app.patch(
    "/mascotas/{id_mascota}/restaurar",
    response_model=PublicacionRespuesta,
    responses={
        **ERROR_401,
        **ERROR_404,
        409: {"model": Error, "description": "La mascota no está retirada"}
    },
    dependencies=SOLO_FUNDACION,
    tags=["Gestión de mascotas"],
    summary="Volver a publicar una mascota retirada (requiere clave)",
    description="Pasa de `retirada` a `disponible`, por si el retiro fue un error."
)
def restaurar_mascota(id_mascota: IdMascota):
    return cambiar_retiro(id_mascota, ("retirada",), "disponible", None)


@app.get(
    "/mascotas/{id_mascota}/disponibilidad",
    response_model=Disponibilidad,
    responses=ERROR_404,
    tags=["Disponibilidad"],
    summary="Verificar si una mascota puede ser adoptada",
    description=(
        "`disponible` es true cuando la mascota está en estado "
        "`disponible` o `en_proceso`. Una mascota adoptada o sin publicar "
        "no recibe solicitudes."
    )
)
def consultar_disponibilidad(id_mascota: IdMascota):
    mascota = buscar_mascota(id_mascota)
    estado = mascota["estado"]

    return {
        "id_mascota": mascota["id_mascota"],
        "nombre": mascota["nombre"],
        "estado": estado,
        "disponible": estado in ("disponible", "en_proceso"),
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
        "Así el servicio de Mascotas también impide una segunda adopción. "
        "Las mascotas sin publicar no cambian de estado por aquí."
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

        if estado_anterior not in TRANSICIONES:
            raise HTTPException(
                status_code=409,
                detail="La mascota no está publicada"
            )

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

        fila = cursor.fetchone()
        fotos = rutas_fotos(cursor, [id_mascota])
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
            "mascota": convertir_mascota(fila, fotos.get(id_mascota))
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
