-- ==================================================
-- PLATAFORMA DE ADOPCIÓN RESPONSABLE DE MASCOTAS
-- Actualización: publicaciones de la comunidad, fotos y ubicación
-- ==================================================
-- Ejecutar en el SQL Editor de Supabase después de 01 y 02.
-- Se puede correr varias veces sin dañar los datos existentes.


-- 1. Mascotas: origen, revisión y ubicación (API de Mascotas)

ALTER TABLE mascotas
    ADD COLUMN IF NOT EXISTS origen VARCHAR(12) NOT NULL DEFAULT 'fundacion',
    ADD COLUMN IF NOT EXISTS pais VARCHAR(80),
    ADD COLUMN IF NOT EXISTS departamento VARCHAR(80),
    ADD COLUMN IF NOT EXISTS ciudad VARCHAR(80),
    ADD COLUMN IF NOT EXISTS contacto_nombre VARCHAR(100),
    ADD COLUMN IF NOT EXISTS contacto_telefono VARCHAR(15),
    ADD COLUMN IF NOT EXISTS contacto_correo VARCHAR(120),
    ADD COLUMN IF NOT EXISTS observacion_revision TEXT;

ALTER TABLE mascotas DROP CONSTRAINT IF EXISTS mascotas_origen_check;
ALTER TABLE mascotas ADD CONSTRAINT mascotas_origen_check
    CHECK (origen IN ('fundacion', 'comunidad'));

-- Estados nuevos:
--   en_revision:  la envió una persona y la fundación aún no la revisa
--   no_publicada: la fundación rechazó la publicación
ALTER TABLE mascotas DROP CONSTRAINT IF EXISTS mascotas_estado_check;
ALTER TABLE mascotas ADD CONSTRAINT mascotas_estado_check
    CHECK (estado IN ('en_revision', 'no_publicada', 'disponible', 'en_proceso', 'adoptada'));

-- Las mascotas iniciales de la fundación están en Cúcuta
UPDATE mascotas
SET pais = 'Colombia', departamento = 'Norte de Santander', ciudad = 'Cúcuta'
WHERE origen = 'fundacion' AND pais IS NULL;


-- 2. Fotos subidas desde la plataforma (API de Mascotas)

CREATE TABLE IF NOT EXISTS fotos_mascotas (
    id_foto     SERIAL PRIMARY KEY,
    id_mascota  INTEGER     NOT NULL REFERENCES mascotas (id_mascota) ON DELETE CASCADE,
    orden       SMALLINT    NOT NULL CHECK (orden BETWEEN 1 AND 3),
    tipo        VARCHAR(20) NOT NULL CHECK (tipo IN ('image/jpeg', 'image/png', 'image/webp')),
    contenido   BYTEA       NOT NULL,
    UNIQUE (id_mascota, orden)
);

ALTER TABLE fotos_mascotas ENABLE ROW LEVEL SECURITY;


-- 3. Solicitudes: país y departamento del solicitante (API de Adopciones)

ALTER TABLE solicitudes_adopcion
    ADD COLUMN IF NOT EXISTS pais VARCHAR(80) NOT NULL DEFAULT 'Colombia',
    ADD COLUMN IF NOT EXISTS departamento VARCHAR(80) NOT NULL DEFAULT '';

ALTER TABLE solicitudes_adopcion ALTER COLUMN ciudad TYPE VARCHAR(80);
