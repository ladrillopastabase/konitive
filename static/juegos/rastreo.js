/* RASTREO DE HÁMSTERS: tablero 4×3, desplazamientos animados y selección de dos casillas. */
"use strict";

const LADOS_RASTREO = ["izquierda", "derecha", "arriba", "abajo"];
const CLASES_ENTRADA = LADOS_RASTREO.map((lado) => `rastreo-entrada-${lado}`);

// Un desplazamiento a la vez: animar() cancela el temporizador anterior y
// detenerTimers() retira cualquier clase o sprite que haya quedado.
const CURVA_RASTREO = "cubic-bezier(0.16, 1, 0.3, 1)";

// Gato pixel-art (12×11), mismo formato que HAMSTER_PIXELES: orejas en punta.
const GATO_PIXELES = [
  "O..........O",
  "OO........OO",
  "OFO......OFO",
  "OFFOOOOOOFFO",
  "OFFFFFFFFFFO",
  "OFEFFFFFFEFO",
  "OFEFFFFFFEFO",
  "OFFFFNNFFFFO",
  "OFFFBBBBFFFO",
  ".OFFFBBFFFO.",
  "..OOOOOOOO..",
];
const GATO_SVG =
  '<svg viewBox="0 0 12 11" shape-rendering="crispEdges" aria-hidden="true">' +
  GATO_PIXELES.flatMap((fila, y) =>
    [...fila].map((c, x) => (HAMSTER_COLOR[c] ? `<rect x="${x}" y="${y}" width="1.02" height="1.02" fill="${HAMSTER_COLOR[c]}"/>` : ""))
  ).join("") +
  "</svg>";
const GATO_PELAJE = ["#6b7079", "#d4d7dc"];

function dibujoRastreo(hamster) {
  const [pelo, panza] = hamster ? PELAJES[0] : GATO_PELAJE;
  return `<span class="rastreo-ave" style="--pelo:${pelo};--panza:${panza}">${hamster ? AVE_SVG : GATO_SVG}</span>`;
}

const AnimationController = {
  temporizador: null,
  sprites: [],
  detener() {
    if (this.temporizador) clearTimeout(this.temporizador);
    this.temporizador = null;
    this.sprites.forEach(([sprite, animacion]) => {
      animacion.cancel();
      sprite.remove();
    });
    this.sprites = [];
    $("contenido")?.querySelectorAll(".rastreo-casilla").forEach((celda) => {
      CLASES_ENTRADA.forEach((clase) => celda.classList.remove(clase));
    });
  },
  animar(movimiento) {
    this.detener();
    if (!movimiento || !LADOS_RASTREO.includes(movimiento.lado)) return;
    const tablero = $("rastreo-tablero");
    if (!tablero) return;
    const duracion = Math.max(0, Number(movimiento.duracion) || 0);
    tablero.style.setProperty("--rastreo-duracion", `${duracion}s`);
    const linea = Number(movimiento.linea);
    const clase = `rastreo-entrada-${movimiento.lado}`;
    const horizontal = movimiento.lado === "izquierda" || movimiento.lado === "derecha";
    const celdas = [...tablero.querySelectorAll(".rastreo-casilla")];
    const afectadas = celdas.filter((_, i) =>
      horizontal ? Math.floor(i / 4) === linea : i % 4 === linea
    );
    afectadas.forEach((celda) => celda.classList.add(clase));
    this.temporizador = setTimeout(() => {
      afectadas.forEach((celda) => celda.classList.remove(clase));
      this.temporizador = null;
    }, duracion * 1000);
    if (duracion <= 0 || typeof tablero.animate !== "function") return;
    // Salir y volver ocurren en turnos distintos: el hámster que sale pasa
    // un turno fuera y los que entran son los que salieron antes.
    if (Number.isInteger(movimiento.salida) && celdas[movimiento.salida]) {
      this.animarSalida(tablero, celdas[movimiento.salida], movimiento.lado, duracion);
    }
    (Array.isArray(movimiento.entran) ? movimiento.entran : []).forEach((i) => {
      if (Number.isInteger(i) && celdas[i]) this.animarEntrada(tablero, celdas[i], i, duracion);
    });
  },
  sprite(tablero, celda, fotogramas, duracion) {
    const sprite = document.createElement("span");
    sprite.className = "rastreo-hamster";
    sprite.innerHTML = dibujoRastreo(true);
    sprite.style.left = `${celda.offsetLeft}px`;
    sprite.style.top = `${celda.offsetTop}px`;
    sprite.style.width = `${celda.offsetWidth}px`;
    sprite.style.height = `${celda.offsetHeight}px`;
    tablero.appendChild(sprite);
    const animacion = sprite.animate(fotogramas, {
      duration: duracion * 2000, fill: "forwards", easing: "linear",
    });
    const par = [sprite, animacion];
    this.sprites.push(par);
    animacion.finished.then(() => {
      sprite.remove();
      this.sprites = this.sprites.filter((p) => p !== par);
    }).catch(() => {});
  },
  pasos(tablero, celda) {
    const estilo = getComputedStyle(tablero);
    return [
      celda.offsetWidth + (parseFloat(estilo.columnGap) || 0),
      celda.offsetHeight + (parseFloat(estilo.rowGap) || 0),
    ];
  },
  reducido: () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches,
  // Sale empujado por la línea, a su mismo ritmo, y se desvanece fuera del borde.
  animarSalida(tablero, origen, lado, duracion) {
    const [pasoX, pasoY] = this.pasos(tablero, origen);
    const [dx, dy] = {
      izquierda: [pasoX, 0], derecha: [-pasoX, 0],
      arriba: [0, pasoY], abajo: [0, -pasoY],
    }[lado];
    const fotogramas = this.reducido()
      ? [{ opacity: 1 }, { opacity: 0 }]
      : [
          { transform: "translate(0px, 0px)", opacity: 1, offset: 0, easing: CURVA_RASTREO },
          { transform: `translate(${dx}px, ${dy}px)`, opacity: 1, offset: .5, easing: "ease-in" },
          { transform: `translate(${dx * 1.6}px, ${dy * 1.6}px)`, opacity: 0, offset: 1 },
        ];
    this.sprite(tablero, origen, fotogramas, duracion);
  },
  // Vuelve despacio desde el borde más cercano a su nueva casilla.
  animarEntrada(tablero, destino, indice, duracion) {
    const [pasoX, pasoY] = this.pasos(tablero, destino);
    const col = indice % 4;
    const fila = Math.floor(indice / 4);
    const borde = [
      [col, "izquierda"], [3 - col, "derecha"],
      [fila, "arriba"], [2 - fila, "abajo"],
    ].sort((a, b) => a[0] - b[0])[0][1];
    const [dx, dy] = {
      izquierda: [-pasoX - destino.offsetLeft, 0],
      derecha: [tablero.clientWidth + pasoX - destino.offsetLeft - destino.offsetWidth, 0],
      arriba: [0, -pasoY - destino.offsetTop],
      abajo: [0, tablero.clientHeight + pasoY - destino.offsetTop - destino.offsetHeight],
    }[borde];
    const fotogramas = this.reducido()
      ? [{ opacity: 0 }, { opacity: 1, offset: .3 }, { opacity: 1, offset: .8 }, { opacity: 0 }]
      : [
          { transform: `translate(${dx}px, ${dy}px)`, opacity: 0, offset: 0, easing: "linear" },
          { transform: `translate(${dx * .85}px, ${dy * .85}px)`, opacity: 1, offset: .12, easing: CURVA_RASTREO },
          { transform: "translate(0px, 0px)", opacity: 1, offset: .8 },
          { transform: "translate(0px, 0px)", opacity: 0, offset: 1 },
        ];
    this.sprite(tablero, destino, fotogramas, duracion);
  },
};

LIMPIEZAS.push(() => AnimationController.detener());

/* ---------- Rastreo de hámsters: tablero, fases y selección ---------- */
const FASES_RASTREO = {
  observacion: "FASE 01 · OBSERVA",
  movimiento: "FASE 02 · SIGUE LAS CASILLAS",
  identificacion: "FASE 03 · SEÑALA DOS HÁMSTERS",
};

function tableroRastreoHtml({ valores, mostrarAves, interactiva, seleccion = [], marcas = {} }) {
  return `<div class="rastreo-tablero" id="rastreo-tablero">${Array.from({ length: 12 }, (_, i) => {
    const valor = mostrarAves && Array.isArray(valores) ? valores[i] : null;
    // Los hámsters (PELAJES[0]) y los gatos llenan el resto de casillas.
    const contenido = valor ? dibujoRastreo(valor !== "G") : "?";
    const clases = [
      "rastreo-casilla",
      seleccion.includes(i) ? "seleccionada" : "",
      marcas[i] || "",
    ].filter(Boolean).join(" ");
    return `<button type="button" class="${clases}" data-celda="${i}" ${interactiva ? "" : "disabled"}>${contenido}</button>`;
  }).join("")}</div>`;
}

function mostrarRastreo(msg, fase) {
  detenerTimers();
  const kicker = (FASES_RASTREO[fase] || FASES_RASTREO.movimiento) +
    (msg.dificultad ? ` · ${String(msg.dificultad).toUpperCase()}` : "");
  if (esMandoFiesta()) {
    if (fase === "identificacion") {
      $("etiqueta-ronda").textContent = `RONDA ${String(msg.ronda || 0).padStart(2, "0")}`;
      $("titulo-juego").textContent = "RASTREO DE HÁMSTERS";
      $("contenido").innerHTML = panelAmplio(
        `<p class="kicker">${kicker}</p>`,
        '<p class="rastreo-mando-pista">ELIGE DOS NÚMEROS</p>',
        `<div class="rastreo-numeros">${Array.from({ length: 12 }, (_, i) =>
          `<button type="button" class="rastreo-numero" data-celda="${i}">${i + 1}</button>`).join("")}</div>`,
        "respuesta-rastreo rastreo-mando"
      );
      configurarSeleccionRastreo(msg);
      return;
    }
    mostrarEspera(
      "MIRA LA PANTALLA",
      fase === "observacion" ? "¡OBSERVA!" : "¡SIGUE LAS CASILLAS!",
      "El tablero aparece solo en la pantalla del anfitrión."
    );
    return;
  }

  const pantalla = esPantallaFiesta();
  const observa = fase === "observacion";
  const interactiva = fase === "identificacion" && !pantalla;
  const pista = observa
    ? "Memoriza dónde están los dos hámsters; el resto son gatos."
    : fase === "movimiento"
      ? "Sigue las casillas. Las identidades quedan ocultas."
      : pantalla
        ? "Los mandos señalan dos casillas desde su celular."
        : "Toca las dos casillas donde crees que están los hámsters.";
  const abajo = `<p class="pista">${pista}</p>` +
    (msg.duracion ? '<div class="barra-tiempo"><div id="barra-tiempo"></div></div>' : "");
  $("contenido").innerHTML = panelAmplio(
    `<p class="kicker">${kicker}</p>`,
    tableroRastreoHtml({ valores: msg.tablero || [], mostrarAves: observa, interactiva }),
    abajo,
    `respuesta-rastreo rastreo-${fase}${pantalla ? " pantalla-espectadora" : ""}`
  );
  if (interactiva) configurarSeleccionRastreo(msg);
  if (msg.duracion) barraTiempo(msg.duracion);
}

function configurarSeleccionRastreo(msg) {
  const botones = [...$("contenido").querySelectorAll("[data-celda]")];
  let elegidas = 0;
  // Cada toque viaja solo: el servidor responde al instante si había hámster.
  botones.forEach((boton) => {
    boton.addEventListener("click", () => {
      if (elegidas >= 2 || boton.disabled) return;
      elegidas += 1;
      boton.disabled = true;
      boton.classList.add("seleccionada");
      if (elegidas === 2) botones.forEach((b) => (b.disabled = true));
      enviar({ type: "rastreo_answer", ronda: msg.ronda, celda: Number(boton.dataset.celda) });
    });
  });
}

function marcarToqueRastreo(msg) {
  const boton = $("contenido")?.querySelector(`[data-celda="${Number(msg.celda)}"]`);
  if (boton) {
    boton.classList.remove("seleccionada");
    boton.classList.add(msg.acierto ? "acierto" : "fallo");
    if (boton.classList.contains("rastreo-casilla")) boton.innerHTML = dibujoRastreo(msg.acierto);
  }
  if (msg.completa) aviso(msg.aciertos === 2 ? "¡LOS DOS HÁMSTERS!" : `${msg.aciertos || 0} DE 2 · BIEN`);
}

function mostrarResultadoRastreo(msg) {
  detenerTimers();
  const posiciones = Object.values(msg.reto?.final || {});
  const seleccion = Array.isArray(msg.seleccion) ? msg.seleccion : [];
  const marcas = {};
  seleccion.forEach((i) => (marcas[i] = posiciones.includes(i) ? "acierto" : "fallo"));
  const valores = Array.from({ length: 12 }, (_, i) => (posiciones.includes(i) ? "h" : "G"));
  $("contenido").innerHTML = panelAmplio(
    `<p class="kicker">RASTREO DE HÁMSTERS · RONDA ${String(msg.ronda || 0).padStart(2, "0")}</p>`,
    tableroRastreoHtml({ valores, mostrarAves: true, interactiva: false, seleccion, marcas }),
    `<p class="pista">Los hámsters y los gatos al descubierto; el contorno señala tu elección.</p>
     <div class="rastreo-metricas">
       <div><b>${Number(msg.aciertos) || 0} / 2</b><span>ACIERTOS</span></div>
       <div><b>${Number(msg.precision) || 0}%</b><span>PRECISIÓN</span></div>
       <div><b>${numero(msg.puntuacion)}</b><span>PUNTUACIÓN</span></div>
     </div>`,
    "respuesta-rastreo resultado-rastreo"
  );
}

registrarMensajes({
  rastreo_countdown: (msg) =>
    mostrarCuentaPrevia(msg, {
      kicker: `FASE 01 · PREPARA LA VISTA · ${String(msg.dificultad || "facil").toUpperCase()}`,
      pie: "RASTREA DOS HÁMSTERS",
      glifo: "◎",
    }),
  rastreo_show: (msg) => mostrarRastreo(msg, "observacion"),
  rastreo_hide: (msg) => {
    AnimationController.detener();
    mostrarRastreo(msg, "movimiento");
  },
  rastreo_move: (msg) => AnimationController.animar(msg),
  rastreo_write: (msg) => mostrarRastreo(msg, "identificacion"),
  rastreo_feedback: (msg) => {
    if (msg.pid === yoId) marcarToqueRastreo(msg);
  },
  rastreo_result: (msg) => {
    if (!resultadoSoloEnPantalla()) mostrarResultadoRastreo(msg);
  },
  rastreo_over: avisarFinPrueba,
});
