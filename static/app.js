/* Konitive — arranque del cliente: portada, selector INDIVIDUAL, lobby y
   ajustes de FIESTA, podio y el despacho de mensajes. Se carga el último, con
   el núcleo y todos los juegos ya registrados. */
"use strict";

// Ajustes de FIESTA que elige el anfitrión para cada juego del catálogo.
const ETIQUETA_DIFICULTAD = { facil: "FÁCIL", normal: "NORMAL", dificil: "DIFÍCIL", experto: "EXPERTO" };
const RONDAS_FIESTA = { defecto: 5, min: 1, max: 20 };
const listaFiesta = new Set();
const ajustesFiesta = Object.fromEntries(
  IDS_JUEGOS.map((j) => [j, { rondas: RONDAS_FIESTA.defecto, dificultad: "facil" }])
);

/* ---------- Inicio ---------- */
$("btn-crear").addEventListener("click", () => {
  const nombre = $("nombre").value.trim();
  if (!nombre) {
    $("error-inicio").textContent = "Escribe tu nombre para abrir la sala";
    return;
  }
  $("error-inicio").textContent = "";
  conectar({ type: "create", nombre });
});

$("btn-unirse").addEventListener("click", () => {
  const nombre = $("nombre").value.trim();
  const codigoSala = $("codigo").value.trim().toUpperCase();
  if (!nombre || codigoSala.length !== 5) {
    $("error-inicio").textContent = "Pon tu nombre y un código de 5 caracteres";
    return;
  }
  $("error-inicio").textContent = "";
  conectar({ type: "join", nombre, codigo: codigoSala });
});

$("btn-individual").addEventListener("click", () => {
  $("error-inicio").textContent = "";
  $("error-individual").textContent = "";
  actualizarSelectorIndividual();
  mostrar("pantalla-individual");
});

// Botones del selector INDIVIDUAL, en el orden del catálogo.
$("selector-individual").innerHTML = CATALOGO.map(
  (j) => `<button type="button" class="boton-juego" data-juego="${j.id}" aria-pressed="false">${escapeHtml(j.nombre)}</button>`
).join("");

function mostrarFicha(juego) {
  const ficha = CATALOGO.find((j) => j.id === juego);
  if (!ficha) return;
  $("ficha-juego-titulo").textContent = ficha.nombre;
  $("ficha-juego-texto").textContent = ficha.descripcion;
}

let fichaActiva = null;

function restaurarFicha() {
  const selector = $("selector-individual");
  const elegido = fichaActiva && selector.contains(fichaActiva)
    ? fichaActiva
    : [...selector.querySelectorAll("button[data-juego]")]
        .find((boton) => juegosIndividuales.has(boton.dataset.juego));
  if (elegido) mostrarFicha(elegido.dataset.juego);
  else {
    $("ficha-juego-titulo").textContent = "CONITA";
    $("ficha-juego-texto").textContent = "Elige una prueba para ver cómo entrena a Conita.";
  }
}

function actualizarSelectorIndividual() {
  $("selector-individual")
    .querySelectorAll("button[data-juego]")
    .forEach((boton) => {
      boton.setAttribute("aria-pressed", juegosIndividuales.has(boton.dataset.juego) ? "true" : "false");
    });
  $("btn-empezar-individual").disabled = juegosIndividuales.size === 0;
  restaurarFicha();
}

$("selector-individual").querySelectorAll("button[data-juego]").forEach((boton) => {
  const juego = boton.dataset.juego;
  boton.addEventListener("click", () => {
    if (juegosIndividuales.has(juego)) juegosIndividuales.delete(juego);
    else juegosIndividuales.add(juego);
    actualizarSelectorIndividual();
  });
  boton.addEventListener("mouseenter", () => {
    fichaActiva = boton;
    mostrarFicha(juego);
  });
  boton.addEventListener("mouseleave", () => {
    if (fichaActiva === boton && document.activeElement !== boton) fichaActiva = null;
    restaurarFicha();
  });
  boton.addEventListener("focus", () => {
    fichaActiva = boton;
    mostrarFicha(juego);
  });
  boton.addEventListener("blur", () => {
    if (fichaActiva === boton) fichaActiva = null;
    restaurarFicha();
  });
});
restaurarFicha();

$("btn-todos").addEventListener("click", () => {
  juegosIndividuales = new Set(IDS_JUEGOS);
  actualizarSelectorIndividual();
});

$("btn-ninguno").addEventListener("click", () => {
  juegosIndividuales = new Set();
  actualizarSelectorIndividual();
});

$("btn-empezar-individual").addEventListener("click", () => {
  if (!juegosIndividuales.size) return;
  const nombre = $("nombre").value.trim() || "Paciente";
  $("error-individual").textContent = "";
  conectar({ type: "individual", nombre, juegos: [...juegosIndividuales] });
});

$("btn-fiesta").addEventListener("click", () => {
  const nombre = $("nombre").value.trim();
  if (!nombre) {
    $("error-inicio").textContent = "Escribe tu nombre para abrir la fiesta";
    return;
  }
  $("error-inicio").textContent = "";
  conectar({ type: "fiesta", nombre });
});

$("btn-unirme").addEventListener("click", () => {
  const nombre = $("nombre-invitado").value.trim();
  const codigoSala = $("codigo-invitado").textContent.trim().toUpperCase();
  if (!nombre || codigoSala.length !== 5) {
    $("error-invitado").textContent = "Pon tu nombre para unirte a la sala";
    return;
  }
  $("error-invitado").textContent = "";
  conectar({ type: "join", nombre, codigo: codigoSala });
});

$("nombre-invitado").addEventListener("keydown", (e) => {
  if (e.key === "Enter") $("btn-unirme").click();
});

$("btn-copiar").addEventListener("click", async () => {
  if (!inviteUrl) return;
  try {
    await navigator.clipboard.writeText(inviteUrl);
    aviso("ENLACE COPIADO");
  } catch (error) {
    aviso(inviteUrl);
  }
});

function pintarListaFiesta() {
  $("lista-fiesta").innerHTML = CATALOGO.map(({ id: juego, nombre, dificultades }) => {
    const activo = listaFiesta.has(juego);
    const { rondas, dificultad } = ajustesFiesta[juego];
    return `<div class="fila-juego ${activo ? "activa" : ""}" data-fila="${juego}">
      <button type="button" class="fila-juego-nombre" data-alternar="${juego}" aria-pressed="${activo}">${escapeHtml(nombre)}</button>
      <div class="fila-juego-rondas" aria-label="Rondas de ${escapeHtml(nombre)}">
        <button type="button" data-rondas="${juego}" data-delta="-1" aria-label="Menos rondas" ${activo ? "" : "disabled"}>−</button>
        <output>${rondas}</output>
        <button type="button" data-rondas="${juego}" data-delta="1" aria-label="Más rondas" ${activo ? "" : "disabled"}>+</button>
      </div>
      <select data-dificultad="${juego}" aria-label="Dificultad de ${escapeHtml(nombre)}" ${activo ? "" : "disabled"}>
        ${dificultades.map((valor) => `<option value="${valor}" ${valor === dificultad ? "selected" : ""}>${ETIQUETA_DIFICULTAD[valor] || valor.toUpperCase()}</option>`).join("")}
      </select>
    </div>`;
  }).join("");
  actualizarBotonFiesta();
}

function actualizarBotonFiesta() {
  const mandos = Object.keys(jugadores).filter((id) => id !== hostId).length;
  const boton = $("btn-iniciar-fiesta");
  boton.disabled = mandos < 1 || listaFiesta.size === 0;
  boton.textContent = listaFiesta.size
    ? `EMPEZAR · ${listaFiesta.size} JUEGO${listaFiesta.size === 1 ? "" : "S"}`
    : "ELIGE AL MENOS UN JUEGO";
  $("btn-fin-fiesta").disabled = mandos < 1;
}

$("lista-fiesta").addEventListener("click", (e) => {
  const alternar = e.target.closest("[data-alternar]");
  const rondas = e.target.closest("[data-rondas]");
  if (alternar) {
    const juego = alternar.dataset.alternar;
    if (listaFiesta.has(juego)) listaFiesta.delete(juego);
    else listaFiesta.add(juego);
    pintarListaFiesta();
  } else if (rondas && !rondas.disabled) {
    const ajuste = ajustesFiesta[rondas.dataset.rondas];
    ajuste.rondas = Math.min(
      RONDAS_FIESTA.max,
      Math.max(RONDAS_FIESTA.min, ajuste.rondas + Number(rondas.dataset.delta))
    );
    rondas.parentElement.querySelector("output").textContent = ajuste.rondas;
  }
});

$("lista-fiesta").addEventListener("change", (e) => {
  const juego = e.target.dataset.dificultad;
  if (juego) ajustesFiesta[juego].dificultad = e.target.value;
});

$("btn-fiesta-todos").addEventListener("click", () => {
  IDS_JUEGOS.forEach((j) => listaFiesta.add(j));
  pintarListaFiesta();
});
$("btn-fiesta-ninguno").addEventListener("click", () => {
  listaFiesta.clear();
  pintarListaFiesta();
});

$("btn-iniciar-fiesta").addEventListener("click", () => {
  const juegos = IDS_JUEGOS.filter((j) => listaFiesta.has(j));
  if (!juegos.length) return;
  const ajustes = Object.fromEntries(juegos.map((j) => [j, ajustesFiesta[j]]));
  enviar({ type: "start", juegos, ajustes });
});

pintarListaFiesta();

$("btn-fin-fiesta").addEventListener("click", () => enviar({ type: "finish_fiesta" }));

$("nombre").addEventListener("keydown", (e) => {
  if (e.key === "Enter") $("btn-crear").click();
});
$("codigo").addEventListener("keydown", (e) => {
  if (e.key === "Enter") $("btn-unirse").click();
});
$("btn-empezar").addEventListener("click", () => enviar({ type: "start" }));
$("btn-salir").addEventListener("click", () => {
  const enJuego = ["pantalla-juego", "pantalla-mando", "pantalla-podio"].some((id) =>
    $(id).classList.contains("activa")
  );
  if (!enJuego) return volverAlInicio();
  const dialogo = $("dialogo-salir");
  dialogo.returnValue = "";
  dialogo.showModal();
});
// Con el diálogo abierto, las teclas no llegan a los controles del juego.
window.addEventListener(
  "keydown",
  (e) => { if ($("dialogo-salir").open) e.stopImmediatePropagation(); },
  true
);
// Esc o "SEGUIR JUGANDO" lo cierran sin salir; solo "SALIR" abandona.
$("dialogo-salir").addEventListener("close", (e) => {
  if (e.target.returnValue === "si") volverAlInicio();
});

// El navegador libera el wake lock al ocultar la pestaña; al volver se
// reclama solo si la pantalla sigue siendo la del anfitrión en juego/podio.
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) actualizarWakeLock();
});

/* ---------- Lobby y marcador ---------- */
function actualizarLobby() {
  const entradas = Object.entries(jugadores);
  const capacidad = modoFiesta ? 9 : 2;
  const huecos = Math.max(0, capacidad - entradas.length);
  // En fiesta la pantalla no juega: se muestra aparte, nunca como participante.
  const participantes = modoFiesta
    ? entradas.filter(([id]) => id !== hostId)
    : entradas;
  const fichaPantalla = modoFiesta
    ? `<div class="ficha-pantalla"><span class="rol">PANTALLA</span>` +
      `${nombreHtml(jugadores[hostId] || "ANFITRIÓN", hostId === yoId ? " (tú)" : "")}</div>`
    : "";

  $("lista-jugadores").innerHTML =
    fichaPantalla +
    participantes
      .map(
        ([id, nombre], i) => {
          const rol = modoFiesta ? "MANDO" : id === hostId ? "ANFITRIÓN" : "INVITADO";
          return `<div class="ficha-jugador"><span class="num">0${i + 1}</span>` +
            `<span class="conectado" title="Conectado"></span>` +
            `${nombreHtml(nombre, id === yoId ? " (tú)" : "")}` +
            `<span class="rol">${rol}</span></div>`;
        }
      )
      .join("") +
    (modoFiesta
      ? ""
      : Array.from(
          { length: huecos },
          (_, i) =>
            `<div class="ficha-jugador vacio"><span class="num">0${entradas.length + i + 1}</span>ESPERANDO…</div>`
        ).join(""));

  const listaMando = $("mando-lista");
  if (listaMando) {
    listaMando.innerHTML =
      fichaPantalla +
      participantes
        .map(
          ([id, nombre]) =>
            `<div class="ficha-jugador"><span class="conectado"></span>` +
            `${nombreHtml(nombre, id === yoId ? " (tú)" : "")}` +
            `<span class="rol">MANDO</span></div>`
        )
        .join("");
  }

  const mandos = participantes.length;
  if (modoFiesta) {
    $("btn-empezar").hidden = true;
    $("lobby-control").hidden = yoId !== hostId;
    $("lobby-grid").classList.toggle("con-control", yoId === hostId);
    actualizarBotonFiesta();
    $("estado-lobby").textContent = mandos
      ? `${mandos} mando(s) conectado(s). Elige los juegos y pulsa EMPEZAR.`
      : "Esperando mandos: escanea el QR con el celular.";
  } else {
    $("lobby-control").hidden = true;
    $("lobby-grid").classList.remove("con-control");
    const listo = entradas.length === 2;
    const boton = $("btn-empezar");
    boton.hidden = false;
    boton.disabled = !(listo && yoId === hostId);
    boton.textContent = !listo
      ? "ESPERANDO AL RIVAL…"
      : yoId === hostId
        ? "INICIAR EXPERIMENTO"
        : "EL ANFITRIÓN INICIA…";
    $("estado-lobby").textContent = listo
      ? "Los dos están aquí. Ya pueden empezar."
      : "Escanea el QR o comparte el código para que tu amigo se una.";
  }
}

function actualizarMarcador(datos) {
  if (datos) marcador = datos;
  if (esMandoFiesta()) {
    // El celular solo ve lo suyo: nunca el marcador de los otros mandos.
    const bruto = (marcador[juegoFiesta] || {})[yoId];
    const dato = bruto && typeof bruto === "object" ? bruto : {};
    const brainAge = miBrainAge?.brain_age ?? dato.brain_age ?? 0;
    const ronda = dato.ronda ?? (juegoFiesta === "pajaros" ? rondaClasica : 0);
    $("marcador-0").innerHTML =
      `<div class="nombre">${nombreHtml(jugadores[yoId] || "TÚ", " · TÚ")}</div>` +
      `<div class="detalle">BRAIN AGE <b>${brainAge}</b></div>`;
    $("marcador-1").innerHTML =
      `<div class="nombre">RONDA ${ronda}</div>` +
      `<div class="detalle">ACIERTOS <b>${dato.aciertos ?? 0}</b></div>`;
    return;
  }
  // Los juegos por rondas con marcador propio (todos menos el duelo clásico y RASTREO).
  const clave = IDS_JUEGOS.find((j) => !["pajaros", "escritura", "rastreo"].includes(j) && marcador[j]);
  if (clave) {
    const ids = Object.keys(marcador[clave]);
    const id = ids.includes(yoId) ? yoId : ids[0];
    const dato = marcador[clave][id] || {};
    const nombre = jugadores[id] || marcador.nombre || "JUGADOR";
    $("marcador-0").innerHTML =
      `<div class="nombre">${nombreHtml(nombre, id === yoId ? " (tú)" : "")}</div>` +
      `<div class="detalle">BRAIN AGE <b>${dato.brain_age ?? 0}</b></div>`;
    $("marcador-1").innerHTML =
      `<div class="nombre">RONDA ${dato.ronda || 0} / ${marcador.necesario || 10}</div>` +
      (clave === "cajas"
        ? `<div class="detalle">ACIERTOS <b>${dato.aciertos || 0}</b> · RACHA <b>${dato.racha || 0}</b>` +
          `${ids.length > 1 ? ` · <b>${ids.length}</b> JUGADORES` : ""}</div>`
        : `<div class="detalle">${ids.length} JUGADOR(ES)</div>`);
    return;
  }
  const ids = Object.keys(marcador.pajaros || {});
  [0, 1].forEach((i) => {
    const id = ids[i];
    const caja = $(`marcador-${i}`);
    if (i === 1 && ids.length === 1) {
      // Jugando solo, el segundo cuadro muestra la ronda en vez de un rival.
      caja.innerHTML =
        `<div class="nombre">RONDA ${rondaClasica}</div>` +
        `<div class="detalle">${modoFiesta ? "1 JUGADOR" : `META <b>${marcador.necesario || 3}</b> ACIERTOS`}</div>`;
      return;
    }
    if (!id || !jugadores[id]) {
      caja.innerHTML = "";
      return;
    }
    const aves = marcador.pajaros[id] || 0;
    const letras = marcador.escritura[id] || 0;
    caja.innerHTML =
      `<div class="nombre">${nombreHtml(jugadores[id], id === yoId ? " (tú)" : "")}</div>` +
      `<div class="detalle">HÁMSTERS <b>${aves}</b> · PALABRAS <b>${letras}</b></div>`;
  });
}

/* ---------- Mensajes del servidor ---------- */
// Aquí solo los mensajes de sala, lobby y podio. Los de cada juego están
// registrados en MENSAJES por su archivo en static/juegos/.
function manejar(msg) {
  sonidoMensaje(msg);
  switch (msg.type) {
    case "room_created":
    case "room_joined": {
      yoId = msg.id;
      hostId = msg.host;
      codigo = msg.codigo;
      jugadores = msg.jugadores;
      modoPractica = Boolean(msg.practica);
      modoFiesta = msg.modo === "fiesta";
      secuenciaIndividual = msg.modo === "individual";
      esPantalla = modoFiesta && yoId === hostId;
      esMando = modoFiesta && msg.rol === "mando";
      if (modoFiesta && esMando) {
        $("mando-nombre").textContent = jugadores[yoId] || "JUGADOR";
        $("mando-estado").textContent =
          "Esperando a que la pantalla elija un juego…";
        actualizarLobby();
        mostrar("pantalla-mando");
        break;
      }
      if (modoPractica) break;
      $("codigo-sala").textContent = codigo;
      actualizarLobby();
      prepararInvitacion(codigo);
      mostrar("pantalla-lobby");
      break;
    }

    case "player_joined":
    case "player_left":
      jugadores = msg.jugadores;
      if (modoFiesta) {
        actualizarLobby();
        if (msg.type === "player_left") aviso(`${msg.nombre} SE DESCONECTÓ`);
      } else if ($("pantalla-lobby").classList.contains("activa")) {
        actualizarLobby();
      } else if (msg.type === "player_left") {
        volverAlInicio(`${msg.nombre} salió de la partida`);
      }
      break;

    case "opponent_left":
      volverAlInicio(`${msg.nombre} abandonó la partida`);
      break;

    case "error": {
      const invitadoActivo = $("pantalla-invitado").classList.contains("activa");
      const destino = invitadoActivo ? "error-invitado" : "error-inicio";
      $(destino).textContent = msg.mensaje;
      break;
    }

    case "individual_game_start":
      secuenciaIndividual = true;
      $("etiqueta-ronda").textContent = `JUEGO ${msg.indice} / ${msg.total}`;
      $("titulo-juego").textContent = msg.nombre_juego;
      $("contenido").innerHTML = `<div class="panel panel-escena">
        <p class="kicker">INDIVIDUAL · SIGUIENTE PRUEBA</p>
        <h2 class="panel-titulo">${escapeHtml(msg.nombre_juego)}</h2>
        <p class="pista">Prepara la atención y la memoria. Empieza enseguida…</p>
      </div>`;
      mostrar("pantalla-juego");
      break;

    case "individual_summary":
      mostrarResumenIndividual(msg);
      break;

    case "progreso_vivo":
      mostrarProgresoVivo(msg);
      break;

    case "fin_fiesta":
      if (esMandoFiesta()) {
        $("mando-estado").textContent =
          "FIESTA TERMINADA · USA «SALIR» PARA VOLVER AL INICIO";
        $("mando-lista").innerHTML = "";
        mostrar("pantalla-mando");
      }
      break;

    case "match_start":
      marcador = msg.marcador || marcador || { pajaros: {}, escritura: {}, necesario: 3 };
      modoPractica = Boolean(msg.practica);
      juegoFiesta = msg.juego_fiesta || juegoFiesta;
      mostrar("pantalla-juego");
      actualizarMarcador();
      if (msg.modo in MINIJUEGOS || msg.modo === "rastreo") {
        $("etiqueta-ronda").textContent = "PREPARACIÓN";
        $("titulo-juego").textContent = nombreJuego(msg.modo);
        $("contenido").innerHTML = `<div class="panel panel-escena">
          <p class="kicker">${secuenciaIndividual ? "INDIVIDUAL" : "FIESTA"} · NUEVA PRUEBA</p>
          <h2 class="panel-titulo">${escapeHtml(nombreJuego(msg.modo))}</h2>
          <p class="pista">Prepara la atención. Cada ronda aparecerá enseguida…</p>
        </div>`;
      }
      break;

    case "podium_update":
    case "podium_final":
      mostrarPodio(msg);
      break;

    case "mi_brain_age":
      if (!esMandoFiesta()) break;
      miBrainAge = msg;
      actualizarMarcador();
      break;

    case "podio_mando":
      if (esMandoFiesta()) mostrarPodioMando(msg);
      break;

    case "back_to_selector":
      volverAlSelector(msg);
      break;

    case "back_to_lobby":
      modoPractica = false;
      juegoFiesta = null;
      miBrainAge = null;
      if (msg.jugadores) jugadores = msg.jugadores;
      if (msg.host) hostId = msg.host;
      if (esMandoFiesta()) {
        $("mando-estado").textContent =
          "Sala de espera · el anfitrión elige el siguiente juego…";
        $("mando-lista").innerHTML = "";
        mostrar("pantalla-mando");
        break;
      }
      actualizarMarcador(msg.marcador);
      actualizarLobby();
      mostrar("pantalla-lobby");
      break;

    default:
      MENSAJES[msg.type]?.(msg);
  }
}

function mostrarProgresoVivo(msg) {
  if (!esPantallaFiesta()) return;
  const caja = $("progreso-vivo");
  if (!caja) return;
  const filas = msg.jugadores || [];
  const titulo = nombreJuego(msg.juego);
  const ronda = msg.ronda ? ` · RONDA ${String(msg.ronda).padStart(2, "0")}` : "";
  const estadoTexto = { contando: "CONTANDO", listo: "LISTO", esperando: "ESPERANDO" };
  caja.innerHTML =
    `<span class="pv-titulo">${escapeHtml(titulo + ronda)}</span>` +
    filas
      .map((fila) => {
        const total = fila.total ? ` / ${fila.total}` : "";
        const estado = estadoTexto[fila.estado] || "EN JUEGO";
        return `<span class="pv-fila ${fila.estado === "listo" ? "listo" : ""}">
          <span class="pv-nombre">${escapeHtml(fila.nombre || "JUGADOR")}</span>
          <span class="pv-valor">${fila.avance || 0}${total}</span>
          <span class="pv-estado">${estado}</span>
        </span>`;
      })
      .join("");
  caja.hidden = filas.length === 0;
}

function pintarPodiosLobby() {
  const tabla = tablaClasificacion(podioActual);
  const html = tabla ? `<p class="kicker">PODIO DE LA FIESTA</p>${tabla}` : "";
  $("podio-lobby").innerHTML = html;
}

const filaPodioHtml = (fila, i, ganado = "", movimiento = "") =>
  `<div class="fila-podio ${i === 0 ? "top1" : ""}" data-id="${fila.id}">` +
  `<span class="puesto">${i + 1}</span>` +
  `<span class="quien">${nombreHtml(fila.nombre || "JUGADOR", fila.id === yoId ? " · TÚ" : "")}${ganado}</span>` +
  movimiento +
  `<span class="puntos">${fila.brain_age ?? 0}</span></div>`;

function mostrarPodio(msg) {
  detenerTimers();
  const final = msg.type === "podium_final";
  podioActual = msg.despues || [];
  const antes = msg.antes || [];
  const brainAgeJuego = msg.brain_age_juego || {};
  const puestoAnterior = {};
  antes.forEach((fila, i) => (puestoAnterior[fila.id] = i));

  $("podio-kicker").textContent = final
    ? "PODIO FINAL · FIESTA"
    : `PODIO · DESPUÉS DE ${msg.nombre_juego || "JUEGO"}`;
  $("podio-titulo").textContent = final ? "CAMPEONES DE LA FIESTA" : "ASÍ VA LA FIESTA";

  const lista = $("lista-podio");
  const posicionesPrevias = {};
  lista.querySelectorAll(".fila-podio").forEach((el) => {
    posicionesPrevias[el.dataset.id] = el.getBoundingClientRect().top;
  });

  lista.innerHTML = podioActual
    .map((fila, i) => {
      const previo = puestoAnterior[fila.id];
      const delta = previo === undefined ? null : previo - i;
      const movimiento =
        delta === null ? "NUEVO" : delta > 0 ? `▲ ${delta}` : delta < 0 ? `▼ ${-delta}` : "—";
      const claseMov = delta > 0 ? "subio" : delta < 0 ? "bajo" : "";
      const ganado = brainAgeJuego[fila.id]
        ? ` <span class="ganado">+${brainAgeJuego[fila.id]} s</span>`
        : "";
      return filaPodioHtml(fila, i, ganado, `<span class="movimiento ${claseMov}">${movimiento}</span>`);
    })
    .join("");

  const reduceMotion =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!reduceMotion && typeof lista.firstElementChild?.animate === "function") {
    lista.querySelectorAll(".fila-podio").forEach((el, i) => {
      const anteriorY = posicionesPrevias[el.dataset.id];
      const actualY = el.getBoundingClientRect().top;
      const desplazamiento = anteriorY === undefined ? 20 : anteriorY - actualY;
      if (!desplazamiento) return;
      el.animate(
        [
          {
            transform: `translateY(${desplazamiento}px)`,
            opacity: anteriorY === undefined ? 0 : 1,
          },
          { transform: "translateY(0)", opacity: 1 },
        ],
        {
          duration: 700,
          delay: i * 70,
          easing: "cubic-bezier(.2,.8,.2,1)",
          fill: "both",
        }
      );
    });
  }

  $("podio-pie").innerHTML = final
    ? 'FIN DE LA FIESTA · <button class="boton rojo chico" id="btn-fin-podio">VOLVER AL INICIO</button>'
    : msg.siguiente
      ? `SIGUIENTE JUEGO: <b>${escapeHtml(msg.siguiente)}</b> · empieza enseguida…`
      : "Fin de la lista · volviendo a la sala…";
  const boton = $("btn-fin-podio");
  if (boton) boton.addEventListener("click", () => volverAlInicio());
  mostrar("pantalla-podio");
}

// El mando también ve el podio final, pero sin desgloses ajenos: solo
// clasificación, su propia fila resaltada y el botón de salida.
function mostrarPodioMando(msg) {
  detenerTimers();
  podioActual = msg.filas || [];
  $("podio-kicker").textContent = "PODIO FINAL · FIESTA";
  $("podio-titulo").textContent = "CAMPEONES DE LA FIESTA";
  $("lista-podio").innerHTML = podioActual.map((fila, i) => filaPodioHtml(fila, i)).join("");
  $("podio-pie").innerHTML =
    'FIN DE LA FIESTA · <button class="boton rojo chico" id="btn-fin-podio-mando">VOLVER AL INICIO</button>';
  $("btn-fin-podio-mando").addEventListener("click", () => volverAlInicio());
  mostrar("pantalla-podio");
}

function volverAlSelector(msg) {
  detenerTimers();
  jugadores = msg.jugadores || jugadores;
  hostId = msg.host || hostId;
  podioActual = msg.podio || [];
  modoPractica = false;
  juegoFiesta = null;
  marcador = { pajaros: {}, escritura: {}, necesario: 3 };
  miBrainAge = null;
  pintarPodiosLobby();
  actualizarLobby();
  if (esPantalla) {
    $("mando-estado").textContent = "El anfitrión elige el siguiente juego…";
    mostrar("pantalla-lobby");
  } else {
    $("mando-estado").textContent =
      "Esperando a que la pantalla elija el siguiente juego…";
    mostrar("pantalla-mando");
  }
}

function mostrarResumenIndividual(msg) {
  detenerTimers();
  secuenciaIndividual = false;
  const resumen = msg.resumen || {};
  const orden = msg.orden || Object.keys(resumen);
  const tarjetas = orden
    .map((clave) => {
      const dato = resumen[clave] || {};
      const detalle = clave in MINIJUEGOS || clave === "rastreo"
        ? `PRECISIÓN ${dato.precision ?? 0}% · BRAIN AGE ${dato.brain_age ?? 0}`
        : `VICTORIAS ${dato.victorias ?? 0} · RONDAS ${dato.rondas ?? 0}` +
          (dato.brain_age != null ? ` · ${textoDesglose(dato)}` : "");
      return `<div class="puntaje">
        <div class="numero">${dato.brain_age ?? 0}</div>
        <div class="desglose">${detalle}</div>
        <div class="quien">${nombreJuego(clave)} · MENOR ES MEJOR</div>
      </div>`;
    })
    .join("");

  $("contenido").innerHTML = `<div class="panel resultado">
    <div class="resultado-cabecera">
      <p class="kicker">INFORME FINAL · MODO INDIVIDUAL</p>
      <h2>TUS RESULTADOS</h2>
    </div>
    <p class="pista">${escapeHtml(msg.nombre || "JUGADOR")}, completaste ${orden.length} prueba(s).</p>
    <div class="puntajes">${tarjetas}</div>
    <div class="puntaje" style="margin-top:10px">
      <div class="numero">${msg.total ?? 0}</div>
      <div class="quien">BRAIN AGE TOTAL · MENOR ES MEJOR</div>
    </div>
    <div class="diploma-acciones">
      <button class="boton oscuro chico" id="btn-otra-individual">REPETIR</button>
      <button class="boton rojo chico" id="btn-volver-individual">VOLVER AL INICIO</button>
    </div>
  </div>`;

  $("btn-otra-individual").addEventListener("click", (e) => {
    e.currentTarget.disabled = true;
    enviar({ type: "individual_restart" });
  });
  $("btn-volver-individual").addEventListener("click", () => volverAlInicio());
}

// Enlace de invitación: /?sala=CODIGO abre directamente la ficha de acceso.
const parametros = new URLSearchParams(location.search);
const salaInvitacion = (parametros.get("sala") || "").trim().toUpperCase();
if (/^[A-Z0-9]{5}$/.test(salaInvitacion)) {
  $("codigo-invitado").textContent = salaInvitacion;
  $("nombre-invitado").value = "";
  $("error-invitado").textContent = "";
  mostrar("pantalla-invitado");
  // En el celular no abrimos el teclado al entrar: descuadra la ficha.
  if (window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
    $("nombre-invitado").focus();
  }
}
