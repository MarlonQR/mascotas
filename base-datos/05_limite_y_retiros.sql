-- ==================================================
-- PLATAFORMA DE ADOPCIÓN RESPONSABLE DE MASCOTAS
-- Actualización: límite de envíos públicos y mascotas retiradas
-- ==================================================
-- Ejecutar en el SQL Editor de Supabase después de 01 a 04.
-- Se puede correr varias veces sin dañar los datos existentes.


-- 1. Registro de envíos públicos (API de Mascotas)
-- Se guarda una huella SHA-256 de la IP, no la IP. Sirve para limitar
-- cuántas mascotas puede enviar una misma conexión por hora.

CREATE TABLE IF NOT EXISTS envios_publicos (
    id_envio    SERIAL PRIMARY KEY,
    huella_ip   VARCHAR(64) NOT NULL,
    fecha       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_envios_publicos_ip_fecha
    ON envios_publicos (huella_ip, fecha);

ALTER TABLE envios_publicos ENABLE ROW LEVEL SECURITY;


-- 2. Mascotas retiradas del catálogo (fallecieron, las reclamó su
--    dueño o se registraron por error)

ALTER TABLE mascotas
    ADD COLUMN IF NOT EXISTS motivo_retiro TEXT;

ALTER TABLE mascotas DROP CONSTRAINT IF EXISTS mascotas_estado_check;
ALTER TABLE mascotas ADD CONSTRAINT mascotas_estado_check
    CHECK (estado IN (
        'en_revision', 'no_publicada', 'disponible',
        'en_proceso', 'adoptada', 'retirada'
    ));
