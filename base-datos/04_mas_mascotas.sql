-- ==================================================
-- PLATAFORMA DE ADOPCIÓN RESPONSABLE DE MASCOTAS
-- Ocho mascotas más de la fundación
-- ==================================================
-- Ejecutar en el SQL Editor de Supabase después de 01, 02 y 03.
-- Se puede correr varias veces: no repite una mascota que ya exista
-- con el mismo nombre.

INSERT INTO mascotas (
    nombre, especie, raza, sexo, edad_meses, tamano,
    vacunado, esterilizado, descripcion, foto_url,
    origen, pais, departamento, ciudad, fecha_ingreso
)
SELECT
    datos.nombre, datos.especie, datos.raza, datos.sexo, datos.edad_meses,
    datos.tamano, datos.vacunado, datos.esterilizado, datos.descripcion,
    datos.foto_url, 'fundacion', 'Colombia', 'Norte de Santander',
    datos.ciudad, CURRENT_DATE - datos.dias_en_fundacion
FROM (
    VALUES
    (
        'Tango', 'perro', 'Mestizo', 'macho', 14, 'pequeno',
        TRUE, TRUE,
        'Lo encontraron amarrado a un poste en el centro de Villa del Rosario. Es sociable, le gustan los niños y aprende rápido a sentarse y dar la pata.',
        'https://images.dog.ceo/breeds/mix/eddy.jpg',
        'Villa del Rosario', 40
    ),
    (
        'Moro', 'perro', 'Criollo', 'macho', 4, 'mediano',
        TRUE, FALSE,
        'Cachorro de cuatro meses, muy dormilón y cariñoso. Va a crecer a tamaño mediano, así que necesita un hogar con espacio para jugar.',
        'https://images.dog.ceo/breeds/mix/photo_2025-11-17_02-05-42.jpg',
        'Los Patios', 12
    ),
    (
        'Lupe', 'perro', 'Beagle mestiza', 'hembra', 48, 'mediano',
        TRUE, TRUE,
        'Le encanta tomar el sol en el patio y olfatearlo todo en los paseos. Es tranquila dentro de la casa y convive bien con otros perros.',
        'https://images.dog.ceo/breeds/beagle/n02088364_3758.jpg',
        'Pamplona', 75
    ),
    (
        'Kira', 'perro', 'Husky mestiza', 'hembra', 30, 'grande',
        TRUE, TRUE,
        'Tiene mucha energía y necesita salir a correr todos los días. Su pelo es abundante, así que agradece un lugar fresco y cepillado frecuente.',
        'https://images.dog.ceo/breeds/husky/20250113_192336.jpg',
        'Pamplona', 20
    ),
    (
        'Gaspar', 'gato', 'Criollo atigrado', 'macho', 60, 'mediano',
        TRUE, TRUE,
        'Gato adulto y muy tranquilo. Pasa el día mirando por la ventana y busca un hogar silencioso, sin perros.',
        'https://cdn2.thecatapi.com/images/bku.jpg',
        'Ocaña', 120
    ),
    (
        'Naranjo', 'gato', 'Persa mestizo', 'macho', 42, 'mediano',
        TRUE, TRUE,
        'Llegó con el pelo muy enredado y ya está recuperado. Es mimoso y necesita cepillado dos veces por semana.',
        'https://cdn2.thecatapi.com/images/MPnl26tDB.jpg',
        'El Zulia', 33
    ),
    (
        'Nube', 'gato', 'Angora mestiza', 'hembra', 20, 'pequeno',
        TRUE, TRUE,
        'Es juguetona y curiosa. Persigue cualquier cordón que se mueva y duerme en la cama de quien la deje.',
        'https://cdn2.thecatapi.com/images/aKbsEYjSl.jpg',
        'Chinácota', 9
    ),
    (
        'Chispa', 'gato', 'Criolla atigrada', 'hembra', 3, 'pequeno',
        TRUE, FALSE,
        'Gatita de tres meses rescatada en un mercado de Cúcuta. Ya come sola y usa la caja de arena. Se recomienda adoptarla junto con otro gato joven o en un hogar con tiempo para jugar.',
        'https://cdn2.thecatapi.com/images/aub.jpg',
        'Cúcuta', 5
    )
) AS datos (
    nombre, especie, raza, sexo, edad_meses, tamano,
    vacunado, esterilizado, descripcion, foto_url,
    ciudad, dias_en_fundacion
)
WHERE NOT EXISTS (
    SELECT 1 FROM mascotas m WHERE m.nombre = datos.nombre
);
