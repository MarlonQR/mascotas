-- ==================================================
-- PLATAFORMA DE ADOPCIÓN RESPONSABLE DE MASCOTAS
-- Fundación Huellas de Esperanza
-- Base de datos del servicio de Adopciones (API 2)
-- ==================================================
-- Ejecutar en el SQL Editor de Supabase.
--
-- id_mascota es una referencia lógica, sin llave foránea: la tabla de
-- mascotas pertenece a otro servicio. La API de Adopciones valida la
-- existencia y la disponibilidad de la mascota consultando la API de
-- Mascotas por HTTP.


-- 1. Tabla de solicitudes de adopción

CREATE TABLE IF NOT EXISTS solicitudes_adopcion (
    id_solicitud        SERIAL PRIMARY KEY,
    id_mascota          INTEGER      NOT NULL,
    nombre_solicitante  VARCHAR(100) NOT NULL,
    documento           VARCHAR(12)  NOT NULL,
    correo              VARCHAR(120) NOT NULL,
    telefono            VARCHAR(15)  NOT NULL,
    ciudad              VARCHAR(60)  NOT NULL,
    tipo_vivienda       VARCHAR(15)  NOT NULL
                        CHECK (tipo_vivienda IN ('casa', 'apartamento', 'finca')),
    otras_mascotas      BOOLEAN      NOT NULL DEFAULT FALSE,
    motivo              TEXT         NOT NULL,
    estado              VARCHAR(15)  NOT NULL DEFAULT 'pendiente'
                        CHECK (estado IN ('pendiente', 'aprobada', 'rechazada')),
    observacion         TEXT,
    fecha_solicitud     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    fecha_respuesta     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_solicitudes_mascota
    ON solicitudes_adopcion (id_mascota);


-- 2. Reglas de negocio garantizadas por la base de datos

-- Una mascota no puede tener dos adopciones aprobadas.
CREATE UNIQUE INDEX IF NOT EXISTS uq_una_adopcion_aprobada_por_mascota
    ON solicitudes_adopcion (id_mascota)
    WHERE estado = 'aprobada';

-- Una persona no puede tener dos solicitudes pendientes por la misma mascota.
CREATE UNIQUE INDEX IF NOT EXISTS uq_una_solicitud_pendiente_por_persona
    ON solicitudes_adopcion (id_mascota, documento)
    WHERE estado = 'pendiente';


-- 3. Seguridad (ver nota en 01_mascotas.sql)

ALTER TABLE solicitudes_adopcion ENABLE ROW LEVEL SECURITY;
