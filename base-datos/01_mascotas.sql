-- ==================================================
-- PLATAFORMA DE ADOPCIÓN RESPONSABLE DE MASCOTAS
-- Fundación Huellas de Esperanza
-- Base de datos del servicio de Mascotas (API 1)
-- ==================================================
-- Ejecutar en el SQL Editor de Supabase.
-- El script se puede correr varias veces sin duplicar datos.


-- 1. Tabla de mascotas

CREATE TABLE IF NOT EXISTS mascotas (
    id_mascota          SERIAL PRIMARY KEY,
    nombre              VARCHAR(60)  NOT NULL,
    especie             VARCHAR(10)  NOT NULL
                        CHECK (especie IN ('perro', 'gato')),
    raza                VARCHAR(60)  NOT NULL DEFAULT 'Mestizo',
    sexo                VARCHAR(10)  NOT NULL
                        CHECK (sexo IN ('macho', 'hembra')),
    edad_meses          INTEGER      NOT NULL
                        CHECK (edad_meses >= 0),
    tamano              VARCHAR(10)  NOT NULL
                        CHECK (tamano IN ('pequeno', 'mediano', 'grande')),
    vacunado            BOOLEAN      NOT NULL DEFAULT FALSE,
    esterilizado        BOOLEAN      NOT NULL DEFAULT FALSE,
    descripcion         TEXT,
    foto_url            TEXT,
    -- disponible: sin solicitudes en curso
    -- en_proceso: tiene solicitudes pendientes de revisión
    -- adoptada:   ya tiene una adopción aprobada
    estado              VARCHAR(15)  NOT NULL DEFAULT 'disponible'
                        CHECK (estado IN ('disponible', 'en_proceso', 'adoptada')),
    fecha_ingreso       DATE         NOT NULL DEFAULT CURRENT_DATE,
    fecha_actualizacion TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mascotas_estado
    ON mascotas (estado);


-- 2. Seguridad
-- La API se conecta con el usuario postgres (dueño de la tabla), que no
-- está sujeto a RLS. Activarlo sin políticas bloquea el acceso público
-- desde la Data API de Supabase con la llave anon.

ALTER TABLE mascotas ENABLE ROW LEVEL SECURITY;


-- 3. Datos iniciales (solo si la tabla está vacía)

INSERT INTO mascotas (
    nombre, especie, raza, sexo, edad_meses, tamano,
    vacunado, esterilizado, descripcion, foto_url
)
SELECT * FROM (
    VALUES
    (
        'Canela', 'perro', 'Mestiza', 'hembra', 24, 'mediano',
        TRUE, TRUE,
        'La rescataron en el barrio La Libertad con una pata lastimada. Ya se recuperó, camina bien con correa y se lleva bien con niños.',
        'https://images.dog.ceo/breeds/mix/mydog-preta.jpg'
    ),
    (
        'Tobías', 'perro', 'Criollo pastor', 'macho', 60, 'grande',
        TRUE, TRUE,
        'Perro tranquilo y muy obediente. Necesita patio o paseos largos todos los días. No convive bien con gatos.',
        'https://images.dog.ceo/breeds/mix/cheyenne2.jpg'
    ),
    (
        'Frijol', 'perro', 'Mestizo', 'macho', 5, 'pequeno',
        TRUE, FALSE,
        'Cachorro juguetón que llegó con sus hermanos desde Los Patios. Está aprendiendo a hacer sus necesidades afuera.',
        'https://images.dog.ceo/breeds/mix/linus4.jpg'
    ),
    (
        'Pancho', 'perro', 'Labrador mestizo', 'macho', 18, 'mediano',
        TRUE, TRUE,
        'Le encanta el agua y traer la pelota. Tiene mucha energía, ideal para una familia activa.',
        'https://images.dog.ceo/breeds/labrador/n02099712_1941.jpg'
    ),
    (
        'Bruno', 'perro', 'Golden mestizo', 'macho', 96, 'grande',
        TRUE, TRUE,
        'Perro adulto mayor, calmado y cariñoso. Busca un hogar sin escaleras donde pueda descansar.',
        'https://images.dog.ceo/breeds/mix/simonnbj.jpg'
    ),
    (
        'Luna', 'gato', 'Criolla atigrada', 'hembra', 12, 'pequeno',
        TRUE, TRUE,
        'Curiosa y algo tímida los primeros días. Usa la caja de arena sin problema y convive con otros gatos.',
        'https://cdn2.thecatapi.com/images/MTk4Mzg4MA.jpg'
    ),
    (
        'Simón', 'gato', 'Angora mestizo', 'macho', 36, 'mediano',
        TRUE, TRUE,
        'Gato casero y tranquilo. Necesita cepillado dos veces por semana por su pelo largo.',
        'https://cdn2.thecatapi.com/images/auq.jpg'
    ),
    (
        'Mona', 'gato', 'Criolla tricolor', 'hembra', 7, 'pequeno',
        TRUE, FALSE,
        'Gatita muy activa. Se recomienda un apartamento con mallas en ventanas y balcones.',
        'https://cdn2.thecatapi.com/images/1r1.jpg'
    )
) AS datos (
    nombre, especie, raza, sexo, edad_meses, tamano,
    vacunado, esterilizado, descripcion, foto_url
)
WHERE NOT EXISTS (SELECT 1 FROM mascotas);
