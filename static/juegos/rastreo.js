/* RASTREO DE HÁMSTERS: tablero 4×3, desplazamientos animados y selección de dos casillas. */
"use strict";

const LADOS_RASTREO = ["izquierda", "derecha", "arriba", "abajo"];
const CLASES_ENTRADA = LADOS_RASTREO.map((lado) => `rastreo-entrada-${lado}`);

// Un desplazamiento a la vez: animar() cancela el temporizador anterior y
// detenerTimers() retira cualquier clase que haya quedado sobre el tablero.
const CURVA_RASTREO = "cubic-bezier(0.16, 1, 0.3, 1)";
const AnimationController = {
  temporizador: null,
  sprite: null,
  animacionSprite: null,
  detener() {
    if (this.temporizador) clearTimeout(this.temporizador);
    this.temporizador = null;
    if (this.animacionSprite) this.animacionSprite.cancel();
    this.animacionSprite = null;
    if (this.sprite) this.sprite.remove();
    this.sprite = null;
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
    if (
      Number.isInteger(movimiento.salida) && Number.isInteger(movimiento.reaparecio) &&
      duracion > 0
    ) {
      this.animarHamster(tablero, celdas, movimiento, duracion);
    }
  },
  // El mismo sprite cruza el borde por la salida y vuelve a entrar por el
  // borde más cercano a su nueva casilla. Se retira al terminar: el tablero
  // vuelve a mostrar incógnitas, sin revelar el id del hámster.
  animarHamster(tablero, celdas, movimiento, duracion) {
    const origen = celdas[movimiento.salida];
    const destino = celdas[movimiento.reaparecio];
    if (!origen || !destino) return;
    const estilo = getComputedStyle(tablero);
    const gapX = parseFloat(estilo.columnGap) || 0;
    const gapY = parseFloat(estilo.rowGap) || 0;
    const pasoX = origen.offsetWidth + gapX;
    const pasoY = origen.offsetHeight + gapY;
    const [pelo, panza] = PELAJES[0];
    const sprite = document.createElement("span");
    sprite.className = "rastreo-hamster";
    sprite.innerHTML = `<span class="rastreo-ave" style="--pelo:${pelo};--panza:${panza}">${AVE_SVG}</span>`;
    sprite.style.left = `${origen.offsetLeft}px`;
    sprite.style.top = `${origen.offsetTop}px`;
    sprite.style.width = `${origen.offsetWidth}px`;
    sprite.style.height = `${origen.offsetHeight}px`;
    if (typeof sprite.animate !== "function") return;
    tablero.appendChild(sprite);
    this.sprite = sprite;

    const lado = movimiento.lado;
    const inicio = {
      izquierda: [-pasoX, 0], derecha: [pasoX, 0],
      arriba: [0, -pasoY], abajo: [0, pasoY],
    }[lado];
    const salida = {
      izquierda: [pasoX, 0], derecha: [-pasoX, 0],
      arriba: [0, pasoY], abajo: [0, -pasoY],
    }[lado];
    const col = movimiento.reaparecio % 4;
    const fila = Math.floor(movimiento.reaparecio / 4);
    const borde = [
      [col, "izquierda"], [3 - col, "derecha"],
      [fila, "arriba"], [2 - fila, "abajo"],
    ].sort((a, b) => a[0] - b[0])[0][1];
    const reingreso = {
      izquierda: [-pasoX, destino.offsetTop],
      derecha: [tablero.clientWidth + gapX, destino.offsetTop],
      arriba: [destino.offsetLeft, -pasoY],
      abajo: [destino.offsetLeft, tablero.clientHeight + gapY],
    }[borde];
    const dxFinal = destino.offsetLeft - origen.offsetLeft;
    const dyFinal = destino.offsetTop - origen.offsetTop;
    const dxReingreso = reingreso[0] - origen.offsetLeft;
    const dyReingreso = reingreso[1] - origen.offsetTop;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const fotogramas = reduce
      ? [
          { transform: "translate(0px, 0px)", opacity: 1, offset: 0 },
          { transform: "translate(0px, 0px)", opacity: 0, offset: .49, easing: "steps(1, end)" },
          { transform: `translate(${dxFinal}px, ${dyFinal}px)`, opacity: 0, offset: .5, easing: CURVA_RASTREO },
          { transform: `translate(${dxFinal}px, ${dyFinal}px)`, opacity: 1, offset: 1 },
        ]
      : [
          { transform: `translate(${inicio[0]}px, ${inicio[1]}px)`, opacity: 1, offset: 0, easing: CURVA_RASTREO },
          { transform: `translate(${salida[0]}px, ${salida[1]}px)`, opacity: 1, offset: .4, easing: "linear" },
          { transform: `translate(${salida[0]}px, ${salida[1]}px)`, opacity: 0, offset: .5 },
          { transform: `translate(${dxReingreso}px, ${dyReingreso}px)`, opacity: 0, offset: .5, easing: CURVA_RASTREO },
          { transform: `translate(${dxFinal}px, ${dyFinal}px)`, opacity: 1, offset: 1 },
        ];
    const animacion = sprite.animate(fotogramas, {
      duration: duracion * 2000, fill: "forwards", easing: "linear",
    });
    this.animacionSprite = animacion;
    animacion.finished.then(() => {
      if (this.sprite !== sprite) return;
      sprite.remove();
      this.sprite = null;
      this.animacionSprite = null;
    }).catch(() => {});
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
  const [pelo, panza] = PELAJES[0];
  return `<div class="rastreo-tablero" id="rastreo-tablero">${Array.from({ length: 12 }, (_, i) => {
    const ave = mostrarAves && Array.isArray(valores) && valores[i] && valores[i] !== "G";
    const contenido = ave
      ? `<span class="rastreo-ave" style="--pelo:${pelo};--panza:${panza}">${AVE_SVG}</span>`
      : "?";
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
    ? "Memoriza dónde están los dos hámsters: los dibujos, no las incógnitas."
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
  const elegidas = [];
  let enviada = false;
  botones.forEach((boton) => {
    boton.addEventListener("click", () => {
      if (enviada) return;
      const indice = Number(boton.dataset.celda);
      if (elegidas.includes(indice)) return;
      elegidas.push(indice);
      boton.classList.add("seleccionada");
      if (elegidas.length < 2) return;
      enviada = true;
      botones.forEach((b) => (b.disabled = true));
      enviar({ type: "rastreo_answer", ronda: msg.ronda, respuesta: [...elegidas] });
    });
  });
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
    `<p class="pista">Los dos dibujos son los hámsters; el contorno señala tu elección.</p>
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
    if (msg.pid !== yoId) return;
    aviso(msg.aciertos === 2 ? "¡LOS DOS HÁMSTERS!" : `${msg.aciertos || 0} DE 2 · BIEN`);
  },
  rastreo_result: (msg) => {
    if (!resultadoSoloEnPantalla()) mostrarResultadoRastreo(msg);
  },
  rastreo_over: avisarFinPrueba,
});
