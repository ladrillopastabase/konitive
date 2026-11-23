/* Konitive — núcleo del cliente: estado compartido, conexión y piezas de interfaz
   que usan todos los juegos. Se carga primero; los archivos de static/juegos/
   se registran con registrarMensajes() y app.js arranca la interfaz. */
"use strict";

const $ = (id) => document.getElementById(id);

let ws = null;
let yoId = null;
let hostId = null;
let codigo = null;
let jugadores = {};
let marcador = { pajaros: {}, escritura: {}, necesario: 3 };
let modoPractica = false;
let modoFiesta = false;
let secuenciaIndividual = false;
let juegosIndividuales = new Set();
let esPantalla = false;
let esMando = false;
let juegoFiesta = null;
let inviteUrl = "";
let podioActual = [];
let miPuntuacion = null;
let animacion = null;
let cuentaTimer = null;
let avisoTimer = null;
let teclaConteo = null;
let conteoToken = null;
// Callbacks del lienzo de escritura activo (letras o cifras).
let alFeedback = null;
let alTerminar = null;
// La pantalla de la fiesta no recibe interacción del host: wake lock para
// que el SO no oscurezca el proyector mientras llegan rondas por WebSocket.
let wakeLock = null;
let wakeLockPidiendo = false;
let rondaClasica = 1;

// Catálogo único de pruebas (orden, nombre, descripción, dificultades). Lo
// sirve /api/catalogo.js, generado desde juego/catalogo.py.
const NOMBRES = Object.fromEntries(CATALOGO.map((j) => [j.id, j.nombre]));
const IDS_JUEGOS = CATALOGO.map((j) => j.id);
const nombreJuego = (id) => NOMBRES[id] || String(id || "").toUpperCase();

// Mensajes de cada juego: tipo -> manejador. Lo rellenan los archivos de juegos/.
const MENSAJES = {};
function registrarMensajes(tabla) {
  for (const tipo of Object.keys(tabla)) {
    if (MENSAJES[tipo]) throw new Error(`Mensaje registrado dos veces: ${tipo}`);
  }
  Object.assign(MENSAJES, tabla);
}

// Limpiezas extra al cambiar de escena (p. ej. la animación de RASTREO).
const LIMPIEZAS = [];

// Fin de una tanda dentro de INDIVIDUAL o FIESTA: el informe final es común.
function avisarFinPrueba() {
  detenerTimers();
  aviso(modoFiesta && !secuenciaIndividual ? "JUEGO TERMINADO · PODIO" : "PRUEBA TERMINADA");
}

// Hámster pixel-art de frente (12×11). O borde, F pelo, B panza, E ojo,
// P rosa (orejas y mejillas), N nariz. Los colores salen de --pelo y --panza.
const HAMSTER_PIXELES = [
  "..OO....OO..",
  ".OPPO..OPPO.",
  ".OFFFOOFFFO.",
  "OFFFFFFFFFFO",
  "OFEFFFFFFEFO",
  "OFPFFNNFFPFO",
  "OFFFBBBBFFFO",
  "OFFBBBBBBFFO",
  "OFFBBBBBBFFO",
  ".OFFBBBBFFO.",
  "..OOO..OOO..",
];
const HAMSTER_COLOR = { O: "var(--tinta)", E: "var(--tinta)", N: "#e86a7a", P: "#f4a3b4", F: "var(--pelo)", B: "var(--panza)" };
const AVE_SVG =
  '<svg viewBox="0 0 12 11" shape-rendering="crispEdges" aria-hidden="true">' +
  HAMSTER_PIXELES.flatMap((fila, y) =>
    [...fila].map((c, x) => (HAMSTER_COLOR[c] ? `<rect x="${x}" y="${y}" width="1.02" height="1.02" fill="${HAMSTER_COLOR[c]}"/>` : ""))
  ).join("") +
  "</svg>";
// Pelajes [pelo, panza]. Nivel 1: todos dorados; cada nivel suma un pelaje.
const PELAJES = [
  ["#e3a24f", "#fbe6c4"], ["#9aa1a8", "#eef0f2"], ["#8a5a3b", "#ecd3b6"],
  ["#f3ece0", "#ffffff"], ["#c9733a", "#f7d9b3"], ["#4a4540", "#d8d0c4"],
];

/* ---------- Utilidades ---------- */
// Solo la pantalla del anfitrión necesita blockers de suspensión: los mandos
// están tocando el celular constantemente. Se pide al entrar en juego/podio
// y se suelta al volver al lobby o al inicio. Si el navegador no lo soporta
// o lo rechaza, la partida sigue igual.
const debeMantenerPantalla = () =>
  esPantallaFiesta() &&
  ["pantalla-juego", "pantalla-podio"].includes(document.querySelector(".pantalla.activa")?.id);

async function actualizarWakeLock() {
  if (!debeMantenerPantalla()) {
    if (wakeLock) {
      const anterior = wakeLock;
      wakeLock = null;
      try { await anterior.release(); } catch (_) {}
    }
    return;
  }
  if (wakeLock || wakeLockPidiendo || !("wakeLock" in navigator)) return;

  wakeLockPidiendo = true;
  try {
    const lock = await navigator.wakeLock.request("screen");
    // El estado puede haber cambiado mientras se concedía el permiso.
    if (!debeMantenerPantalla()) {
      await lock.release();
    } else {
      wakeLock = lock;
      lock.addEventListener("release", () => {
        if (wakeLock === lock) wakeLock = null;
      });
    }
  } catch (_) {
    // Sin soporte, sin contexto seguro o permiso denegado: no es fatal.
  } finally {
    wakeLockPidiendo = false;
  }
}

function mostrar(id) {
  document.querySelectorAll(".pantalla").forEach((p) => p.classList.remove("activa"));
  $(id).classList.add("activa");
  // Fuera del inicio siempre hay forma de volver.
  $("btn-salir").hidden = id === "pantalla-inicio";
  // Al entrar, la grilla de juegos siempre arranca desde arriba.
  const selector = $("selector-individual");
  if (id === "pantalla-individual" && selector) selector.scrollTop = 0;
  // La franja de avance vive solo mientras se juega; al salir se limpia.
  const vivo = $("progreso-vivo");
  if (vivo && id !== "pantalla-juego") {
    vivo.hidden = true;
    vivo.innerHTML = "";
  }
  actualizarWakeLock();
}

// Nombre que se recorta con «…» si no cabe; el sufijo («(tú)», «· TÚ») nunca salta de línea.
const nombreHtml = (nombre, sufijo = "") =>
  `<span class="nombre-txt">${escapeHtml(nombre)}</span>` +
  (sufijo ? `<span class="nombre-sufijo">${sufijo}</span>` : "");

function escapeHtml(texto) {
  return String(texto).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

function aviso(texto) {
  const el = $("aviso");
  el.textContent = texto;
  el.classList.add("visible");
  clearTimeout(avisoTimer);
  avisoTimer = setTimeout(() => el.classList.remove("visible"), 2800);
}

async function prepararInvitacion(codigoSala) {
  let origen = location.origin;
  if (["localhost", "127.0.0.1", "::1"].includes(location.hostname)) {
    try {
      const respuesta = await fetch("/api/red");
      const datos = await respuesta.json();
      if (datos.ip) origen = `${location.protocol}//${datos.ip}:${datos.puerto}`;
    } catch (error) {
      console.warn("No se pudo consultar la IP local", error);
    }
  }
  inviteUrl = `${origen}/?sala=${codigoSala}`;
  const qr = $("qr-sala");
  if (qr) qr.src = `/api/qr?texto=${encodeURIComponent(inviteUrl)}`;
}

function detenerTimers() {
  LIMPIEZAS.forEach((limpiar) => limpiar());
  if (animacion) cancelAnimationFrame(animacion);
  animacion = null;
  clearInterval(cuentaTimer);
  cuentaTimer = null;
  if (teclaConteo) document.removeEventListener("keydown", teclaConteo);
  teclaConteo = null;
  conteoToken = null;
  alFeedback = null;
  alTerminar = null;
}

function enviar(objeto) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(objeto));
}

function conectar(mensajeInicial) {
  if (ws && ws.readyState <= 1) ws.close();
  const protocolo = location.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(`${protocolo}//${location.host}/ws`);
  ws = socket;
  ws.onopen = () => enviar(mensajeInicial);
  ws.onmessage = (evento) => {
    try {
      manejar(JSON.parse(evento.data));
    } catch (error) {
      console.error("Mensaje inválido", error);
    }
  };
  // onclose llega después de que el cliente cierra a propósito (salir o
  // reconectar): solo es una pérdida real si este sigue siendo el socket activo.
  ws.onclose = () => {
    if (ws === socket) aviso("Se perdió la conexión con el servidor");
  };
  ws.onerror = () => {
    $("error-inicio").textContent = "No se pudo conectar con el servidor";
  };
}

function volverAlInicio(mensaje) {
  detenerTimers();
  enviar({ type: "leave" });
  if (ws) ws.close();
  ws = null;
  yoId = hostId = codigo = null;
  jugadores = {};
  modoPractica = false;
  modoFiesta = false;
  secuenciaIndividual = false;
  esPantalla = false;
  esMando = false;
  juegoFiesta = null;
  podioActual = [];
  $("error-inicio").textContent = "";
  $("error-invitado").textContent = "";
  $("codigo").value = "";
  $("lobby-control").hidden = true;
  $("podio-lobby").innerHTML = "";
  mostrar("pantalla-inicio");
  if (mensaje) aviso(mensaje);
}

const STEPPER_HTML =
  '<div class="stepper"><button id="btn-menos" class="stepper-boton" aria-label="Quitar uno">−</button>' +
  '<output id="cuenta-valor" class="stepper-valor" aria-live="polite">0</output>' +
  '<button id="btn-mas" class="stepper-boton" aria-label="Agregar uno">+</button></div>';

// Contador +/− (botones, flechas y Enter) de STEPPER_HTML; alConfirmar envía la respuesta.
function stepperConteo(alConfirmar, alCambiar = null) {
  let valor = 0;
  let confirmado = false;
  const cambiar = (delta) => {
    if (confirmado) return;
    valor = Math.min(200, Math.max(0, valor + delta));
    $("cuenta-valor").textContent = valor;
    alCambiar?.(valor);
  };
  const confirmar = () => {
    if (confirmado) return;
    confirmado = true;
    ["btn-menos", "btn-mas", "btn-responder"].forEach((id) => ($(id).disabled = true));
    if (teclaConteo) document.removeEventListener("keydown", teclaConteo);
    teclaConteo = null;
    alConfirmar(valor);
    aviso("CUENTA CONFIRMADA");
  };
  $("btn-menos").addEventListener("click", () => cambiar(-1));
  $("btn-mas").addEventListener("click", () => cambiar(1));
  $("btn-responder").addEventListener("click", confirmar);
  if (teclaConteo) document.removeEventListener("keydown", teclaConteo);
  teclaConteo = (e) => {
    if (["ArrowUp", "ArrowRight"].includes(e.key)) { e.preventDefault(); cambiar(1); }
    else if (["ArrowDown", "ArrowLeft"].includes(e.key)) { e.preventDefault(); cambiar(-1); }
    else if (e.key === "Enter") { e.preventDefault(); confirmar(); }
  };
  document.addEventListener("keydown", teclaConteo);
  $("btn-responder").focus();
}

function mostrarEspera(kicker, titulo, texto) {
  detenerTimers();
  $("contenido").innerHTML = `<div class="panel panel-escena pantalla-espera-mando">
    <div class="glifo">◉</div>
    <p class="kicker">${kicker}</p>
    <h2 class="panel-titulo">${titulo}</h2>
    <p class="pista">${texto}</p>
  </div>`;
}

// Resultado privado: cada mando ve solo si acertó, nunca la respuesta ajena.
function mostrarResultadoPrivado(titulo, acepta, detalle = "") {
  detenerTimers();
  $("contenido").innerHTML = `<div class="panel panel-escena pantalla-espera-mando">
    <p class="kicker">${escapeHtml(titulo)}</p>
    <h2 class="panel-titulo ${acepta ? "privado-bien" : "privado-mal"}">${acepta ? "✔️ CORRECTO" : "❌ ERROR"}</h2>
    ${detalle ? `<p class="pista">${escapeHtml(detalle)}</p>` : ""}
  </div>`;
}

// En FIESTA el informe de cada ronda es cosa de la pantalla. El mando solo
// espera: así la respuesta correcta no aparece nunca en el celular.
function resultadoSoloEnPantalla() {
  if (!esMandoFiesta()) return false;
  mostrarEspera(
    "MODO FIESTA · INFORME",
    "MÍRALO EN LA PANTALLA",
    "El resultado de la ronda aparece solo en la pantalla. Prepara la siguiente."
  );
  return true;
}

function barraTiempo(duracion) {
  const barra = $("barra-tiempo");
  if (!barra || !duracion) return;
  barra.style.transition = `transform ${duracion}s linear`;
  barra.style.transform = "scaleX(1)";
  requestAnimationFrame(() => (barra.style.transform = "scaleX(0)"));
}

function esMandoFiesta() {
  return modoFiesta && esMando;
}

function esPantallaFiesta() {
  return modoFiesta && esPantalla;
}

function etiquetaRonda(msg) {
  return `RONDA ${String(msg.ronda || 0).padStart(2, "0")} / ${msg.necesario || 10}`;
}

function miraPantallaHtml(texto = "MIRA LA PANTALLA") {
  return `<div class="mira-pantalla"><b>${texto}</b><span>Y responde aquí</span></div>`;
}

function panelAmplio(arriba, visual, abajo, clases = "", ref = "") {
  return `<div class="panel panel-escena panel-amplio ${clases}">
    <div class="amplio-arriba">${arriba}</div>
    ${ref ? `<div class="amplio-ref">${ref}</div>` : ""}
    <div class="amplio-visual">${visual}</div>
    <div class="amplio-abajo">${abajo}</div>
  </div>`;
}

function mostrarCuentaPrevia(
  msg,
  { kicker = "FASE 01 · PREPARA LA MEMORIA", pie = "LA PALABRA APARECERÁ DESPUÉS", glifo = "✎" } = {}
) {
  detenerTimers();
  let restante = Math.max(1, Math.round(msg.segundos || 3));
  $("contenido").innerHTML = `<div class="panel panel-escena">
    <p class="kicker">${kicker}</p>
    <div class="cuenta-previa">
      <div class="cuenta-previa-numero" id="cuenta-previa-numero">${restante}</div>
      <div class="cuenta-previa-pie">${pie}</div>
    </div>
  </div>`;

  clearInterval(cuentaTimer);
  cuentaTimer = setInterval(() => {
    restante -= 1;
    const el = $("cuenta-previa-numero");
    if (el) {
      el.textContent = restante > 0 ? restante : glifo;
      el.style.animation = "none";
      void el.offsetWidth;
      el.style.animation = "";
    }
    if (restante <= 0) clearInterval(cuentaTimer);
  }, 1000);
}

function iniciarCanvasEscritura(opciones) {
  opciones = {
    feedbackAceptada: (fb) =>
      fb.motivo === "aceptada por intentos" ? `ERA ${fb.esperada} · ACEPTADA POR INTENTOS` : `${fb.predicha} ✓`,
    feedbackRechazada: (fb) => `PARECE ${fb.predicha} · INTENTO ${fb.intentos}/3`,
    ...opciones,
  };
  clearInterval(cuentaTimer);
  cuentaTimer = null;
  const letrasAceptadas = {};
  let indice = 0;
  let esperando = false;
  let terminado = false;
  let trazos = [];
  let trazoActual = [];
  let dibujando = false;
  let feedbackTimer = null;

  function cancelarFeedbackTimer() {
    if (feedbackTimer) {
      clearTimeout(feedbackTimer);
      feedbackTimer = null;
    }
  }

  // PC: TRIÁNGULOS lleva la pirámide grande a la izquierda y el lienzo a la derecha.
  $("contenido").innerHTML = panelAmplio(
    `<p class="kicker">${opciones.kicker}</p>`,
    `<div class="letras-escritas" id="letras-escritas"></div>
    <canvas id="lienzo" width="280" height="280" aria-label="Área de dibujo"></canvas>`,
    `<div class="acciones">
      <button class="boton contorno chico" id="btn-limpiar">LIMPIAR</button>
      <button class="boton rojo chico" id="btn-listo">LISTO ✓</button>
    </div>
    <div class="feedback-letra" id="feedback-letra"></div>
    ${opciones.pista ? `<p class="pista">${opciones.pista}</p>` : ""}`,
    `cuaderno escritura${opciones.recordatorio ? " con-ref" : ""}`,
    opciones.recordatorio ? `<div class="mini-recordatorio">${opciones.recordatorio}</div>` : ""
  );

  function pintarLetras() {
    const letras = Object.keys(letrasAceptadas)
      .sort((a, b) => Number(a) - Number(b))
      .map((clave) => `<span class="letra-confirmada">${escapeHtml(letrasAceptadas[clave])}</span>`);
    $("letras-escritas").innerHTML = letras.join("");
  }
  pintarLetras();

  const canvas = $("lienzo");
  const ctx = canvas.getContext("2d");
  // Resolución igual al tamaño en pantalla (los trazos viajan normalizados 0-1).
  const lado = Math.round(canvas.getBoundingClientRect().width * (window.devicePixelRatio || 1));
  if (lado > 0) canvas.width = canvas.height = lado;

  function limpiar() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "#1c1a17";
    ctx.lineWidth = 22 * canvas.width / 280;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
  }

  function dibujarTrazo(puntos) {
    if (!puntos.length) return;
    ctx.beginPath();
    ctx.moveTo(puntos[0][0] * canvas.width, puntos[0][1] * canvas.height);
    for (let i = 1; i < puntos.length; i++) {
      ctx.lineTo(puntos[i][0] * canvas.width, puntos[i][1] * canvas.height);
    }
    if (puntos.length === 1) {
      ctx.lineTo(puntos[0][0] * canvas.width + 0.01, puntos[0][1] * canvas.height + 0.01);
    }
    ctx.stroke();
  }

  function redibujar() {
    limpiar();
    trazos.forEach(dibujarTrazo);
    dibujarTrazo(trazoActual);
  }

  function puntoDe(evento) {
    const rect = canvas.getBoundingClientRect();
    return [
      Math.min(1, Math.max(0, (evento.clientX - rect.left) / rect.width)),
      Math.min(1, Math.max(0, (evento.clientY - rect.top) / rect.height)),
    ];
  }

  limpiar();

  canvas.addEventListener("pointerdown", (e) => {
    if (esperando || terminado) return;
    e.preventDefault();
    canvas.setPointerCapture(e.pointerId);
    dibujando = true;
    trazoActual = [puntoDe(e)];
    redibujar();
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!dibujando || esperando || terminado) return;
    e.preventDefault();
    trazoActual.push(puntoDe(e));
    dibujarTrazo(trazoActual.slice(-2));
  });
  const terminarTrazo = () => {
    if (!dibujando) return;
    dibujando = false;
    if (trazoActual.length) trazos.push(trazoActual);
    trazoActual = [];
  };
  canvas.addEventListener("pointerup", terminarTrazo);
  canvas.addEventListener("pointercancel", terminarTrazo);

  $("btn-limpiar").addEventListener("click", () => {
    if (esperando || terminado) return;
    trazos = [];
    trazoActual = [];
    redibujar();
    $("feedback-letra").textContent = "";
  });

  $("btn-listo").addEventListener("click", () => {
    if (esperando || terminado) return;
    terminarTrazo();
    if (!trazos.length) {
      aviso("DIBUJA ALGO PRIMERO");
      return;
    }
    esperando = true;
    $("btn-listo").disabled = true;
    cancelarFeedbackTimer();
    feedbackTimer = setTimeout(() => {
      esperando = false;
      $("btn-listo").disabled = false;
      feedbackTimer = null;
      const feedback = $("feedback-letra");
      if (feedback) {
        feedback.className = "feedback-letra mal";
        feedback.textContent = "NO SE LEYÓ EL DIBUJO · INTENTA DE NUEVO";
      }
    }, 8000);
    // `extra` lleva la ronda en los minijuegos: sin ella el árbitro descarta la cifra.
    enviar({ type: opciones.tipoMensaje, index: indice, trazos, ...(opciones.extra || {}) });
  });

  alFeedback = (msg) => {
    cancelarFeedbackTimer();
    esperando = false;
    $("btn-listo").disabled = terminado;
    const feedback = $("feedback-letra");
    if (msg.aceptada) {
      letrasAceptadas[msg.index] = msg.esperada;
      pintarLetras();
      feedback.className = "feedback-letra bien";
      feedback.textContent = opciones.feedbackAceptada(msg);
      indice = msg.index + 1;
      trazos = [];
      trazoActual = [];
      redibujar();
    } else {
      feedback.className = "feedback-letra mal";
      // No se revela la respuesta correcta: es una prueba de memoria.
      feedback.textContent = opciones.feedbackRechazada(msg);
      trazos = [];
      trazoActual = [];
      redibujar();
    }
  };

  alTerminar = () => {
    cancelarFeedbackTimer();
    terminado = true;
    $("btn-listo").disabled = true;
    canvas.style.opacity = "0.5";
    $("feedback-letra").className = "feedback-letra bien";
    $("feedback-letra").textContent = opciones.terminoTexto;
  };
}

function tablaClasificacion(filas, resaltarId = yoId) {
  if (!filas || !filas.length) return "";
  return `<div class="podio-lobby">${filas
    .map(
      (fila, i) =>
        `<div class="fila"><span class="puesto">${i + 1}.</span>` +
        `<span class="quien">${nombreHtml(fila.nombre || "JUGADOR", fila.id === resaltarId ? " · TÚ" : "")}</span>` +
        `<span class="puntos">${numero(fila.puntuacion)}</span></div>`
    )
    .join("")}</div>`;
}
