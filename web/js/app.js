

"use strict";

// ==================================================
// 1. CONFIGURACIÓN DE LAS API
// ==================================================

// En local (localhost o abriendo el archivo directamente) se usan las
// APIs locales. Después de desplegar, reemplaza las URL de producción.
const ES_LOCAL =
    location.protocol === "file:" ||
    ["localhost", "127.0.0.1"].includes(location.hostname);

const API_MASCOTAS = ES_LOCAL
    ? "http://127.0.0.1:8001"
    : "https://mascotas-blue.vercel.app"
const API_ADOPCIONES = ES_LOCAL
    ? "http://127.0.0.1:8000"
    : "https://mascotas-2pue.vercel.app";


// ==================================================
// 2. ESTADO DE LA APLICACIÓN Y TEXTOS
// ==================================================

const app = {
    mascotas: [],
    solicitudes: [],
    filtroEspecie: "todas",
    filtroEstado: "todos",
    filtroSolicitudes: "todas",
    mascotaElegida: null,
    solicitudAbierta: null,
    accionPendiente: null,
    claveAdmin: null
};

const VISTAS = ["mascotas", "solicitudes", "registro"];

const ESTADOS_MASCOTA = {
    disponible: "Disponible",
    en_proceso: "En proceso",
    adoptada: "Adoptada"
};

const ESTADOS_SOLICITUD = {
    pendiente: "Pendiente",
    aprobada: "Aprobada",
    rechazada: "Rechazada"
};

const TAMANOS = {
    pequeno: "Pequeño",
    mediano: "Mediano",
    grande: "Grande"
};

const VIVIENDAS = {
    casa: "Casa",
    apartamento: "Apartamento",
    finca: "Finca"
};

const EMOJIS = {
    perro: "🐶",
    gato: "🐱"
};

// Nombres legibles de los campos para los errores 422 de FastAPI.
const CAMPOS = {
    nombre: "nombre",
    raza: "raza",
    edad_meses: "edad",
    foto_url: "URL de la foto",
    descripcion: "descripción",
    nombre_solicitante: "nombre completo",
    documento: "documento",
    correo: "correo",
    telefono: "teléfono",
    ciudad: "ciudad",
    motivo: "motivo",
    observacion: "observación"
};


// ==================================================
// 3. UTILIDADES
// ==================================================

function crear(etiqueta, clase, texto) {
    const elemento = document.createElement(etiqueta);

    if (clase) {
        elemento.className = clase;
    }

    if (texto !== undefined && texto !== null) {
        elemento.textContent = texto;
    }

    return elemento;
}

function describirError(codigo, datos) {
    const detalle = datos && datos.detail;

    if (typeof detalle === "string") {
        return detalle;
    }

    // Errores de validación (422): FastAPI indica qué campo falló.
    if (Array.isArray(detalle)) {
        const campos = detalle.map(error => {
            const campo = error.loc ? error.loc[error.loc.length - 1] : "";
            return CAMPOS[campo] || campo;
        });

        return `Revisa estos datos: ${[...new Set(campos)].join(", ")}.`;
    }

    return `El servidor respondió con el error HTTP ${codigo}.`;
}

async function pedirJSON(url, opciones = {}) {
    const configuracion = { method: opciones.method || "GET", headers: {} };

    if (opciones.body !== undefined) {
        configuracion.headers["Content-Type"] = "application/json";
        configuracion.body = JSON.stringify(opciones.body);
    }

    // Operaciones de la fundación: la API exige la clave en este encabezado.
    if (opciones.admin) {
        configuracion.headers["X-Clave-Admin"] = opciones.clave || app.claveAdmin || "";
    }

    let respuesta;

    try {
        respuesta = await fetch(url, configuracion);
    } catch (error) {
        throw new Error(
            "No hubo respuesta del servidor. " +
            "Verifica la conexión o que la API esté en línea."
        );
    }

    let datos = null;

    try {
        datos = await respuesta.json();
    } catch (error) {
        datos = null;
    }

    if (respuesta.status === 401 && opciones.admin && !opciones.clave) {
        // La clave guardada ya no sirve (por ejemplo, la cambiaron en Vercel).
        cerrarSesionFundacion();
        mostrarAviso("La clave de la fundación ya no es válida. Ingrésala de nuevo.", "error");
    }

    if (!respuesta.ok) {
        throw new Error(describirError(respuesta.status, datos));
    }

    return datos;
}

function formatearEdad(meses) {
    if (meses < 12) {
        return meses === 1 ? "1 mes" : `${meses} meses`;
    }

    const anios = Math.floor(meses / 12);
    return anios === 1 ? "1 año" : `${anios} años`;
}

function formatearFecha(valor, conHora = false) {
    if (!valor) {
        return "Sin fecha";
    }

    const opciones = { day: "numeric", month: "short", year: "numeric" };

    if (conHora) {
        opciones.hour = "numeric";
        opciones.minute = "2-digit";
    }

    return new Date(valor).toLocaleString("es-CO", opciones);
}

// Concordancia de género: "adoptarla" / "adoptarlo".
function terminacion(mascota) {
    return mascota && mascota.sexo === "hembra" ? "a" : "o";
}

function etiquetaEstadoMascota(mascota) {
    if (mascota.estado === "adoptada") {
        return `Adoptad${terminacion(mascota)}`;
    }

    return ESTADOS_MASCOTA[mascota.estado] || mascota.estado;
}

function crearEstado(clave, texto) {
    return crear("span", `estado estado-${clave}`, texto);
}

// Foto de la mascota. Si no tiene o no carga, muestra un emoji.
function crearFoto(mascota, miniatura = false) {
    const alterna = crear(
        "span",
        miniatura ? "miniatura" : "foto-alterna",
        (mascota && EMOJIS[mascota.especie]) || "🐾"
    );
    alterna.setAttribute("aria-hidden", "true");

    if (!mascota || !mascota.foto_url) {
        return alterna;
    }

    const imagen = document.createElement("img");

    imagen.src = mascota.foto_url;
    imagen.alt = `Foto de ${mascota.nombre}`;
    imagen.loading = "lazy";

    if (miniatura) {
        imagen.className = "miniatura";
    }

    imagen.addEventListener("error", () => imagen.replaceWith(alterna), { once: true });

    return imagen;
}

function mostrarMensaje(id, texto, tipo = "") {
    const mensaje = document.getElementById(id);

    mensaje.textContent = texto;
    mensaje.className = `mensaje ${tipo}`.trim();
}

let temporizadorAviso;

function mostrarAviso(texto, tipo = "exito") {
    const aviso = document.getElementById("aviso");

    aviso.textContent = texto;
    aviso.className = `aviso aviso-${tipo}`;
    aviso.hidden = false;

    clearTimeout(temporizadorAviso);
    temporizadorAviso = setTimeout(() => {
        aviso.hidden = true;
    }, 6000);
}

function marcarActivo(selector, botonActivo) {
    document.querySelectorAll(selector).forEach(boton => {
        boton.classList.toggle("activo", boton === botonActivo);
        boton.setAttribute("aria-pressed", String(boton === botonActivo));
    });
}

function filaUnica(tabla, columnas, texto) {
    const fila = document.createElement("tr");
    const celda = crear("td", "", texto);

    celda.colSpan = columnas;
    fila.appendChild(celda);
    tabla.replaceChildren(fila);
}


// ==================================================
// 4. CATÁLOGO DE MASCOTAS (API DE MASCOTAS)
// ==================================================

async function consultarMascotas() {
    const lista = document.getElementById("lista-mascotas");
    const boton = document.getElementById("btn-actualizar-mascotas");

    boton.disabled = true;

    try {
        const mascotas = await pedirJSON(`${API_MASCOTAS}/mascotas`);

        if (!Array.isArray(mascotas)) {
            throw new Error("La respuesta no tiene el formato esperado.");
        }

        app.mascotas = mascotas;

        mostrarMensaje("mensaje-mascotas", "");
        actualizarCifras();
        mostrarMascotas();

    } catch (error) {
        console.error("Error al consultar mascotas:", error);

        mostrarMensaje(
            "mensaje-mascotas",
            `No fue posible consultar la API de Mascotas. ${error.message}`,
            "error"
        );

        lista.replaceChildren(
            crear("p", "vacio", "No se pudieron cargar las mascotas.")
        );

    } finally {
        boton.disabled = false;
    }
}

function actualizarCifras() {
    const contar = estado =>
        app.mascotas.filter(mascota => mascota.estado === estado).length;

    document.getElementById("cifra-disponibles").textContent = contar("disponible");
    document.getElementById("cifra-en-proceso").textContent = contar("en_proceso");
    document.getElementById("cifra-adoptadas").textContent = contar("adoptada");
}

function mostrarMascotas() {
    const lista = document.getElementById("lista-mascotas");

    const visibles = app.mascotas.filter(mascota =>
        (app.filtroEspecie === "todas" || mascota.especie === app.filtroEspecie) &&
        (app.filtroEstado === "todos" || mascota.estado === app.filtroEstado)
    );

    if (visibles.length === 0) {
        const texto = app.mascotas.length === 0
            ? "Todavía no hay mascotas registradas."
            : "Ninguna mascota coincide con los filtros.";

        lista.replaceChildren(crear("p", "vacio", texto));
        return;
    }

    lista.replaceChildren(...visibles.map(crearTarjeta));
}

function crearTarjeta(mascota) {
    const o = terminacion(mascota);
    const adoptada = mascota.estado === "adoptada";
    const tarjeta = crear("article", adoptada ? "tarjeta adoptada" : "tarjeta");

    // Foto con el estado encima.
    const foto = crear("div", "tarjeta-foto");

    foto.append(
        crearFoto(mascota),
        crearEstado(mascota.estado, etiquetaEstadoMascota(mascota))
    );

    // Nombre, sexo y datos básicos.
    const cuerpo = crear("div", "tarjeta-cuerpo");
    const titulo = crear("div", "tarjeta-titulo");

    titulo.append(
        crear("h3", "", mascota.nombre),
        crear("span", "sexo", mascota.sexo === "hembra" ? "♀ Hembra" : "♂ Macho")
    );

    const datos = crear(
        "p",
        "tarjeta-datos",
        [
            mascota.raza,
            formatearEdad(mascota.edad_meses),
            TAMANOS[mascota.tamano]
        ].join(" · ")
    );

    const etiquetas = crear("ul", "etiquetas");

    etiquetas.append(
        crear(
            "li",
            mascota.vacunado ? "" : "pendiente",
            mascota.vacunado ? `Vacunad${o}` : "Vacunas pendientes"
        ),
        crear(
            "li",
            mascota.esterilizado ? "" : "pendiente",
            mascota.esterilizado ? `Esterilizad${o}` : "Sin esterilizar"
        )
    );

    cuerpo.append(titulo, datos, etiquetas);

    if (mascota.descripcion) {
        cuerpo.append(crear("p", "tarjeta-descripcion", mascota.descripcion));
    }

    if (mascota.estado === "en_proceso") {
        cuerpo.append(
            crear("p", "tarjeta-nota", "Tiene solicitudes en revisión. Aún puedes postularte.")
        );
    }

    // Botón para solicitar la adopción.
    const boton = crear("button", "boton");
    boton.type = "button";

    if (adoptada) {
        boton.textContent = "Ya tiene un hogar";
        boton.disabled = true;
    } else {
        boton.textContent = `Quiero adoptarl${o}`;
        boton.addEventListener("click", () => abrirSolicitud(mascota));
    }

    cuerpo.append(boton);
    tarjeta.append(foto, cuerpo);

    return tarjeta;
}


// ==================================================
// 5. SOLICITUD DE ADOPCIÓN (API DE ADOPCIONES)
// ==================================================

function abrirSolicitud(mascota) {
    const dialogo = document.getElementById("dialogo-solicitud");
    const formulario = document.getElementById("form-solicitud");
    const resumen = document.getElementById("resumen-mascota-solicitud");

    app.mascotaElegida = mascota;

    const info = crear("div");

    info.append(
        crear("strong", "", mascota.nombre),
        crear(
            "span",
            "texto-secundario",
            `${mascota.raza} · ${formatearEdad(mascota.edad_meses)} · ${TAMANOS[mascota.tamano]}`
        )
    );

    resumen.replaceChildren(crearFoto(mascota, true), info);

    document.getElementById("titulo-dialogo-solicitud").textContent =
        `Adoptar a ${mascota.nombre}`;
    document.getElementById("error-solicitud").textContent = "";
    document.getElementById("resultado-solicitud").hidden = true;
    formulario.hidden = false;

    dialogo.showModal();
    formulario.elements.nombre_solicitante.focus();
}

async function enviarSolicitud(evento) {
    evento.preventDefault();

    const formulario = evento.currentTarget;
    const error = document.getElementById("error-solicitud");
    const boton = formulario.querySelector('button[type="submit"]');

    error.textContent = "";

    if (!formulario.checkValidity()) {
        formulario.reportValidity();
        return;
    }

    const datos = new FormData(formulario);

    const solicitud = {
        id_mascota: app.mascotaElegida.id_mascota,
        nombre_solicitante: datos.get("nombre_solicitante").trim(),
        documento: datos.get("documento").trim(),
        correo: datos.get("correo").trim(),
        telefono: datos.get("telefono").trim(),
        ciudad: datos.get("ciudad").trim(),
        tipo_vivienda: datos.get("tipo_vivienda"),
        otras_mascotas: datos.has("otras_mascotas"),
        motivo: datos.get("motivo").trim()
    };

    boton.disabled = true;
    boton.textContent = "Enviando...";

    try {
        // La API de Adopciones verifica la disponibilidad con la API de
        // Mascotas antes de guardar la solicitud.
        const respuesta = await pedirJSON(`${API_ADOPCIONES}/solicitudes`, {
            method: "POST",
            body: solicitud
        });

        mostrarResultadoSolicitud(respuesta);
        formulario.reset();
        consultarMascotas();

    } catch (excepcion) {
        console.error("Error al registrar la solicitud:", excepcion);
        error.textContent = excepcion.message;

    } finally {
        boton.disabled = false;
        boton.textContent = "Enviar solicitud";
    }
}

function mostrarResultadoSolicitud(respuesta) {
    const resultado = document.getElementById("resultado-solicitud");
    const boton = crear("button", "boton", "Listo");

    boton.type = "button";
    boton.addEventListener("click", () => {
        document.getElementById("dialogo-solicitud").close();
    });

    resultado.replaceChildren(
        crear("div", "icono", "🐾"),
        crear("h3", "", "¡Solicitud enviada!"),
        crear("p", "", respuesta.mensaje),
        boton
    );

    document.getElementById("form-solicitud").hidden = true;
    resultado.hidden = false;
    boton.focus();
}


// ==================================================
// 6. GESTIÓN DE SOLICITUDES (PANEL DE LA FUNDACIÓN)
// ==================================================

async function consultarSolicitudes() {
    const tabla = document.getElementById("tabla-solicitudes");
    const boton = document.getElementById("btn-actualizar-solicitudes");

    boton.disabled = true;

    try {
        const solicitudes = await pedirJSON(`${API_ADOPCIONES}/solicitudes`, { admin: true });

        if (!Array.isArray(solicitudes)) {
            throw new Error("La respuesta no tiene el formato esperado.");
        }

        app.solicitudes = solicitudes;

        // Si la API de Mascotas no respondió, las solicitudes llegan
        // sin el resumen de la mascota.
        if (solicitudes.some(solicitud => !solicitud.mascota)) {
            mostrarMensaje(
                "mensaje-solicitudes",
                "La API de Mascotas no respondió. Las solicitudes se muestran sin los datos de la mascota.",
                "error"
            );
        } else {
            mostrarMensaje("mensaje-solicitudes", "");
        }

        actualizarContadores();
        mostrarSolicitudes();

    } catch (error) {
        console.error("Error al consultar solicitudes:", error);

        filaUnica(tabla, 7, "No fue posible cargar las solicitudes.");

        mostrarMensaje(
            "mensaje-solicitudes",
            `No fue posible consultar la API de Adopciones. ${error.message}`,
            "error"
        );

    } finally {
        boton.disabled = false;
    }
}

function actualizarContadores() {
    document.getElementById("contador-todas").textContent = app.solicitudes.length;

    Object.keys(ESTADOS_SOLICITUD).forEach(estado => {
        document.getElementById(`contador-${estado}`).textContent =
            app.solicitudes.filter(solicitud => solicitud.estado === estado).length;
    });
}

function mostrarSolicitudes() {
    const tabla = document.getElementById("tabla-solicitudes");

    const visibles = app.filtroSolicitudes === "todas"
        ? app.solicitudes
        : app.solicitudes.filter(solicitud => solicitud.estado === app.filtroSolicitudes);

    if (visibles.length === 0) {
        filaUnica(
            tabla,
            7,
            app.solicitudes.length === 0
                ? "Todavía no hay solicitudes registradas."
                : "No hay solicitudes en este estado."
        );
        return;
    }

    tabla.replaceChildren(...visibles.map(crearFilaSolicitud));
}

function crearFilaSolicitud(solicitud) {
    const fila = document.createElement("tr");
    const mascota = solicitud.mascota;

    // Mascota (datos que la API de Adopciones trae de la API de Mascotas).
    const celdaMascota = crear("td");
    const contenedor = crear("div", "celda-mascota");

    contenedor.append(
        crearFoto(mascota, true),
        crear("span", "", mascota ? mascota.nombre : `Mascota #${solicitud.id_mascota}`)
    );
    celdaMascota.append(contenedor);

    // Solicitante.
    const celdaSolicitante = crear("td");

    celdaSolicitante.append(
        crear("strong", "", solicitud.nombre_solicitante),
        crear("span", "texto-secundario", `${solicitud.ciudad} · ${solicitud.telefono}`)
    );

    // Vivienda.
    const celdaVivienda = crear("td", "", VIVIENDAS[solicitud.tipo_vivienda]);

    if (solicitud.otras_mascotas) {
        celdaVivienda.append(crear("span", "texto-secundario", "Con otras mascotas"));
    }

    // Estado y acción.
    const celdaEstado = crear("td");
    celdaEstado.append(
        crearEstado(solicitud.estado, ESTADOS_SOLICITUD[solicitud.estado])
    );

    const pendiente = solicitud.estado === "pendiente";
    const celdaAccion = crear("td");
    const boton = crear(
        "button",
        pendiente ? "boton boton-pequeno" : "boton boton-secundario boton-pequeno",
        pendiente ? "Revisar" : "Ver"
    );

    boton.type = "button";
    boton.addEventListener("click", () => abrirRevision(solicitud.id_solicitud));
    celdaAccion.append(boton);

    fila.append(
        crear("td", "", `#${solicitud.id_solicitud}`),
        celdaMascota,
        celdaSolicitante,
        celdaVivienda,
        crear("td", "", formatearFecha(solicitud.fecha_solicitud)),
        celdaEstado,
        celdaAccion
    );

    return fila;
}

async function abrirRevision(idSolicitud) {
    const dialogo = document.getElementById("dialogo-revision");
    const detalle = document.getElementById("detalle-solicitud");
    const formulario = document.getElementById("form-decision");

    app.solicitudAbierta = null;

    document.getElementById("titulo-dialogo-revision").textContent =
        `Solicitud #${idSolicitud}`;
    document.getElementById("error-decision").textContent = "";
    detalle.replaceChildren(
        crear("p", "", "Consultando la solicitud y los datos de la mascota...")
    );
    formulario.reset();
    formulario.hidden = true;
    ocultarConfirmacion();

    if (!dialogo.open) {
        dialogo.showModal();
    }

    try {
        // La API de Adopciones consulta internamente a la API de Mascotas.
        const solicitud = await pedirJSON(
            `${API_ADOPCIONES}/solicitudes/${encodeURIComponent(idSolicitud)}`,
            { admin: true }
        );

        app.solicitudAbierta = solicitud;
        mostrarDetalleSolicitud(solicitud);
        formulario.hidden = solicitud.estado !== "pendiente";

    } catch (error) {
        console.error("Error al consultar la solicitud:", error);
        detalle.replaceChildren(crear("p", "error", error.message));
    }
}

function mostrarDetalleSolicitud(solicitud) {
    const detalle = document.getElementById("detalle-solicitud");
    const mascota = solicitud.mascota;

    // Mascota.
    const resumen = crear("div", "resumen-mascota");
    const info = crear("div");

    if (mascota) {
        info.append(
            crear("strong", "", mascota.nombre),
            crear("span", "texto-secundario", "Estado actual en la API de Mascotas")
        );
        resumen.append(
            crearFoto(mascota, true),
            info,
            crearEstado(mascota.estado, etiquetaEstadoMascota(mascota))
        );
    } else {
        info.append(
            crear("strong", "", `Mascota #${solicitud.id_mascota}`),
            crear("span", "texto-secundario", "La API de Mascotas no respondió")
        );
        resumen.append(crearFoto(null, true), info);
    }

    // Datos del solicitante.
    const datos = crear("dl", "datos-solicitud");

    const filas = [
        ["Solicitante", solicitud.nombre_solicitante],
        ["Documento", solicitud.documento],
        ["Teléfono", solicitud.telefono],
        ["Correo", solicitud.correo],
        ["Ciudad", solicitud.ciudad],
        [
            "Vivienda",
            `${VIVIENDAS[solicitud.tipo_vivienda]}, ` +
            (solicitud.otras_mascotas ? "con otras mascotas" : "sin otras mascotas")
        ],
        ["Fecha de solicitud", formatearFecha(solicitud.fecha_solicitud, true)],
        ["Estado", crearEstado(solicitud.estado, ESTADOS_SOLICITUD[solicitud.estado])]
    ];

    filas.forEach(([etiqueta, valor]) => {
        const grupo = crear("div");
        const dato = crear("dd");

        if (valor instanceof Node) {
            dato.append(valor);
        } else {
            dato.textContent = valor;
        }

        grupo.append(crear("dt", "", etiqueta), dato);
        datos.append(grupo);
    });

    // Motivo de la solicitud.
    const motivo = crear("div", "cita");
    motivo.append(crear("strong", "", "Motivo"), document.createTextNode(solicitud.motivo));

    detalle.replaceChildren(resumen, datos, motivo);

    // Respuesta de la fundación, si ya se resolvió.
    if (solicitud.estado !== "pendiente") {
        const respuesta = crear("div", "cita");

        respuesta.append(
            crear("strong", "", `Respuesta · ${formatearFecha(solicitud.fecha_respuesta, true)}`),
            document.createTextNode(solicitud.observacion || "Sin observación")
        );

        detalle.append(respuesta);
    }
}

// Muestra dentro del diálogo qué va a pasar antes de aprobar o rechazar.
function pedirConfirmacion(accion) {
    const solicitud = app.solicitudAbierta;
    const formulario = document.getElementById("form-decision");
    const error = document.getElementById("error-decision");
    const campo = formulario.elements.observacion;

    if (!solicitud) {
        return;
    }

    error.textContent = "";

    if (accion === "rechazar" && campo.value.trim().length < 5) {
        error.textContent = "Escribe el motivo del rechazo (mínimo 5 caracteres).";
        campo.focus();
        return;
    }

    const mascota = solicitud.mascota;
    const nombre = mascota ? mascota.nombre : `La mascota #${solicitud.id_mascota}`;
    const o = terminacion(mascota);

    // Otras solicitudes pendientes por la misma mascota.
    const otras = app.solicitudes.filter(otra =>
        otra.id_mascota === solicitud.id_mascota &&
        otra.estado === "pendiente" &&
        otra.id_solicitud !== solicitud.id_solicitud
    ).length;

    const plural = otras === 1 ? "1 solicitud pendiente" : `${otras} solicitudes pendientes`;
    const boton = document.getElementById("btn-confirmar");
    let titulo;
    let consecuencias;

    if (accion === "aprobar") {
        titulo = `¿Entregar a ${nombre} en adopción a ${solicitud.nombre_solicitante}?`;
        consecuencias = [
            `${nombre} quedará como adoptad${o} y saldrá del catálogo de disponibles.`,
            otras === 0
                ? `No hay otras solicitudes pendientes por ${nombre}.`
                : otras === 1
                    ? `La otra solicitud pendiente por ${nombre} se rechazará automáticamente.`
                    : `Las otras ${otras} solicitudes pendientes por ${nombre} se rechazarán automáticamente.`,
            "Esta decisión no se puede deshacer desde la plataforma."
        ];
        document.getElementById("icono-confirmacion").textContent = "🏡";
        boton.textContent = "Sí, aprobar adopción";
        boton.className = "boton boton-exito";
    } else {
        titulo = `¿Rechazar la solicitud de ${solicitud.nombre_solicitante}?`;
        consecuencias = [
            otras > 0
                ? `${nombre} seguirá en proceso porque tiene ${plural} más.`
                : `${nombre} volverá a aparecer como disponible en el catálogo.`,
            "El motivo que escribiste queda guardado en la solicitud."
        ];
        document.getElementById("icono-confirmacion").textContent = "✋";
        boton.textContent = "Sí, rechazar";
        boton.className = "boton boton-peligro-solido";
    }

    document.getElementById("titulo-confirmacion").textContent = titulo;
    document.getElementById("detalle-confirmacion").replaceChildren(
        ...consecuencias.map(texto => crear("li", "", texto))
    );

    app.accionPendiente = accion;
    document.getElementById("acciones-decision").hidden = true;
    document.getElementById("confirmacion").hidden = false;
    campo.disabled = true;
    boton.focus();
}

function ocultarConfirmacion() {
    app.accionPendiente = null;
    document.getElementById("confirmacion").hidden = true;
    document.getElementById("acciones-decision").hidden = false;
    document.getElementById("form-decision").elements.observacion.disabled = false;
}

async function decidirSolicitud(accion) {
    const solicitud = app.solicitudAbierta;
    const formulario = document.getElementById("form-decision");
    const error = document.getElementById("error-decision");
    const observacion = formulario.elements.observacion.value.trim();

    if (!solicitud || !accion) {
        return;
    }

    error.textContent = "";

    const botones = formulario.querySelectorAll("button");
    botones.forEach(boton => { boton.disabled = true; });

    try {
        const respuesta = await pedirJSON(
            `${API_ADOPCIONES}/solicitudes/${solicitud.id_solicitud}/${accion}`,
            {
                method: "PATCH",
                body: { observacion: observacion || null },
                admin: true
            }
        );

        let texto = respuesta.mensaje;
        const rechazadas = respuesta.solicitudes_rechazadas || [];

        if (rechazadas.length === 1) {
            texto += " La otra solicitud pendiente se rechazó automáticamente.";
        } else if (rechazadas.length > 1) {
            texto += ` Las otras ${rechazadas.length} solicitudes pendientes se rechazaron automáticamente.`;
        }

        document.getElementById("dialogo-revision").close();
        mostrarAviso(texto, "exito");

        await Promise.all([consultarSolicitudes(), consultarMascotas()]);

    } catch (excepcion) {
        console.error(`Error al ${accion} la solicitud:`, excepcion);
        ocultarConfirmacion();
        error.textContent = excepcion.message;

    } finally {
        botones.forEach(boton => { boton.disabled = false; });
    }
}


// ==================================================
// 7. REGISTRO DE MASCOTAS (API DE MASCOTAS)
// ==================================================

async function registrarMascota(evento) {
    evento.preventDefault();

    const formulario = evento.currentTarget;
    const error = document.getElementById("error-mascota");
    const boton = formulario.querySelector('button[type="submit"]');

    error.textContent = "";

    if (!formulario.checkValidity()) {
        formulario.reportValidity();
        return;
    }

    const datos = new FormData(formulario);

    const mascota = {
        nombre: datos.get("nombre").trim(),
        especie: datos.get("especie"),
        raza: datos.get("raza").trim(),
        sexo: datos.get("sexo"),
        edad_meses: Number(datos.get("anios")) * 12 + Number(datos.get("meses")),
        tamano: datos.get("tamano"),
        vacunado: datos.has("vacunado"),
        esterilizado: datos.has("esterilizado"),
        descripcion: datos.get("descripcion").trim() || null,
        foto_url: datos.get("foto_url").trim() || null
    };

    boton.disabled = true;
    boton.textContent = "Registrando...";

    try {
        const nueva = await pedirJSON(`${API_MASCOTAS}/mascotas`, {
            method: "POST",
            body: mascota,
            admin: true
        });

        formulario.reset();
        mostrarAviso(
            `${nueva.nombre} quedó registrad${terminacion(nueva)} con el número #${nueva.id_mascota}.`
        );

        await consultarMascotas();
        location.hash = "#mascotas";

    } catch (excepcion) {
        console.error("Error al registrar la mascota:", excepcion);
        error.textContent = excepcion.message;

    } finally {
        boton.disabled = false;
        boton.textContent = "Registrar mascota";
    }
}


// ==================================================
// 8. ESTADO DE LOS SERVICIOS
// ==================================================

async function verificarServicio(id, url) {
    const enlace = document.getElementById(id);
    const texto = enlace.querySelector(".servicio-estado");

    // El enlace abre la documentación Swagger de la API.
    enlace.href = `${url}/docs`;
    enlace.title = "Abrir la documentación Swagger";

    try {
        await pedirJSON(`${url}/`);
        enlace.classList.add("en-linea");
        texto.textContent = "en línea";

    } catch (error) {
        enlace.classList.add("fuera-de-linea");
        texto.textContent = "sin conexión";
    }
}


// ==================================================
// 9. ACCESO DE LA FUNDACIÓN
// ==================================================

// La clave se guarda solo mientras la pestaña del navegador esté abierta.
// La que protege los datos es la API: sin la clave correcta responde 401.

function leerClaveGuardada() {
    try {
        return sessionStorage.getItem("claveFundacion") || null;
    } catch (error) {
        return null;
    }
}

function actualizarAccesoFundacion() {
    const dentro = Boolean(app.claveAdmin);

    document.querySelectorAll("[data-solo-fundacion]").forEach(elemento => {
        elemento.hidden = !dentro;
    });

    const boton = document.getElementById("btn-acceso");
    boton.textContent = dentro ? "Salir" : "Acceso fundación";
    boton.title = dentro ? "Cerrar el acceso de la fundación" : "";
}

function abrirAcceso() {
    if (app.claveAdmin) {
        cerrarSesionFundacion();
        mostrarAviso("Saliste del acceso de la fundación.");
        return;
    }

    const formulario = document.getElementById("form-acceso");

    formulario.reset();
    document.getElementById("error-acceso").textContent = "";
    document.getElementById("dialogo-acceso").showModal();
    formulario.elements.clave.focus();
}

async function ingresarFundacion(evento) {
    evento.preventDefault();

    const formulario = evento.currentTarget;
    const error = document.getElementById("error-acceso");
    const boton = formulario.querySelector('button[type="submit"]');
    const clave = formulario.elements.clave.value.trim();

    error.textContent = "";

    if (!clave) {
        error.textContent = "Escribe la clave.";
        return;
    }

    boton.disabled = true;
    boton.textContent = "Verificando...";

    try {
        // Si la API acepta la clave al listar solicitudes, la clave es correcta.
        await pedirJSON(`${API_ADOPCIONES}/solicitudes`, { admin: true, clave });

        app.claveAdmin = clave;

        try {
            sessionStorage.setItem("claveFundacion", clave);
        } catch (excepcion) {
            // Sin almacenamiento, el acceso dura hasta recargar la página.
        }

        document.getElementById("dialogo-acceso").close();
        actualizarAccesoFundacion();
        mostrarAviso("Entraste como fundación.");
        location.hash = "#solicitudes";

    } catch (excepcion) {
        error.textContent = excepcion.message;

    } finally {
        boton.disabled = false;
        boton.textContent = "Entrar";
    }
}

function cerrarSesionFundacion() {
    app.claveAdmin = null;

    try {
        sessionStorage.removeItem("claveFundacion");
    } catch (error) {
        // Nada que limpiar.
    }

    actualizarAccesoFundacion();

    const revision = document.getElementById("dialogo-revision");

    if (revision.open) {
        revision.close();
    }

    if (location.hash !== "#mascotas") {
        location.hash = "#mascotas";
    }
}


// ==================================================
// 10. NAVEGACIÓN E INICIO DE LA APLICACIÓN
// ==================================================

const VISTAS_FUNDACION = ["solicitudes", "registro"];

function mostrarVista() {
    const pedida = location.hash.slice(1);
    let vista = VISTAS.includes(pedida) ? pedida : "mascotas";

    // Sin la clave, las vistas de la fundación llevan al catálogo.
    if (VISTAS_FUNDACION.includes(vista) && !app.claveAdmin) {
        vista = "mascotas";
        history.replaceState(null, "", "#mascotas");
    }

    VISTAS.forEach(nombre => {
        const activa = nombre === vista;
        const pestana = document.querySelector(`[data-vista="${nombre}"]`);

        document.getElementById(`vista-${nombre}`).hidden = !activa;
        pestana.classList.toggle("activa", activa);

        if (activa) {
            pestana.setAttribute("aria-current", "page");
        } else {
            pestana.removeAttribute("aria-current");
        }
    });

    if (vista === "solicitudes") {
        consultarSolicitudes();
    }
}

document.addEventListener("DOMContentLoaded", () => {
    // Filtros del catálogo.
    document.querySelectorAll("[data-especie]").forEach(boton => {
        boton.addEventListener("click", () => {
            app.filtroEspecie = boton.dataset.especie;
            marcarActivo("[data-especie]", boton);
            mostrarMascotas();
        });
    });

    document.getElementById("filtro-estado").addEventListener("change", evento => {
        app.filtroEstado = evento.target.value;
        mostrarMascotas();
    });

    // Filtros de solicitudes.
    document.querySelectorAll("[data-estado-solicitud]").forEach(boton => {
        boton.addEventListener("click", () => {
            app.filtroSolicitudes = boton.dataset.estadoSolicitud;
            marcarActivo("[data-estado-solicitud]", boton);
            mostrarSolicitudes();
        });
    });

    // Botones y formularios.
    document.getElementById("btn-actualizar-mascotas")
        .addEventListener("click", consultarMascotas);
    document.getElementById("btn-actualizar-solicitudes")
        .addEventListener("click", consultarSolicitudes);
    document.getElementById("form-solicitud")
        .addEventListener("submit", enviarSolicitud);
    document.getElementById("form-mascota")
        .addEventListener("submit", registrarMascota);
    document.getElementById("form-mascota")
        .addEventListener("reset", () => {
            document.getElementById("error-mascota").textContent = "";
        });
    document.getElementById("btn-aprobar")
        .addEventListener("click", () => pedirConfirmacion("aprobar"));
    document.getElementById("btn-rechazar")
        .addEventListener("click", () => pedirConfirmacion("rechazar"));
    document.getElementById("btn-volver-confirmacion")
        .addEventListener("click", ocultarConfirmacion);
    document.getElementById("btn-confirmar")
        .addEventListener("click", () => decidirSolicitud(app.accionPendiente));

    // Cerrar diálogos con sus botones o haciendo clic fuera de ellos.
    document.querySelectorAll("[data-cerrar]").forEach(boton => {
        boton.addEventListener("click", () => boton.closest("dialog").close());
    });

    document.querySelectorAll("dialog").forEach(dialogo => {
        dialogo.addEventListener("click", evento => {
            if (evento.target !== dialogo) {
                return;
            }

            const area = dialogo.getBoundingClientRect();
            const fuera =
                evento.clientX < area.left || evento.clientX > area.right ||
                evento.clientY < area.top || evento.clientY > area.bottom;

            if (fuera) {
                dialogo.close();
            }
        });
    });

    // Acceso de la fundación.
    document.getElementById("btn-acceso")
        .addEventListener("click", abrirAcceso);
    document.getElementById("form-acceso")
        .addEventListener("submit", ingresarFundacion);

    window.addEventListener("hashchange", mostrarVista);

    app.claveAdmin = leerClaveGuardada();
    actualizarAccesoFundacion();
    mostrarVista();
    consultarMascotas();
    verificarServicio("estado-api-mascotas", API_MASCOTAS);
    verificarServicio("estado-api-adopciones", API_ADOPCIONES);
});
