/* Konitive — sonidos sintetizados con WebAudio, sin archivos. */
"use strict";

/* ---------- Sonido (sintetizado con WebAudio, sin archivos) ---------- */
let audio = null;
let sonidoActivo = true;
try { sonidoActivo = localStorage.getItem("konitive-sonido") !== "off"; } catch (_) {}

function tono(frecuencia, duracion, { tipo = "triangle", volumen = 0.08, hasta = null, retraso = 0 } = {}) {
  if (!sonidoActivo) return;
  try {
    audio = audio || new (window.AudioContext || window.webkitAudioContext)();
    if (audio.state === "suspended") audio.resume();
    const t = audio.currentTime + retraso;
    const osc = audio.createOscillator();
    const gan = audio.createGain();
    osc.type = tipo;
    osc.frequency.setValueAtTime(frecuencia, t);
    if (hasta) osc.frequency.exponentialRampToValueAtTime(hasta, t + duracion);
    gan.gain.setValueAtTime(0.0001, t);
    gan.gain.exponentialRampToValueAtTime(volumen, t + 0.01);
    gan.gain.exponentialRampToValueAtTime(0.0001, t + duracion);
    osc.connect(gan).connect(audio.destination);
    osc.start(t);
    osc.stop(t + duracion + 0.02);
  } catch (_) {
    /* sin audio disponible: el juego sigue en silencio */
  }
}
const notas = (lista, paso = 0.09, opciones = {}) =>
  lista.forEach((f, i) => tono(f, paso * 1.6, { ...opciones, retraso: i * paso }));

const SONIDOS = {
  click: () => tono(880, 0.04, { tipo: "square", volumen: 0.035 }),
  tic: () => tono(660, 0.07, { volumen: 0.07 }),
  aparece: () => tono(480, 0.12, { tipo: "sine", hasta: 960, volumen: 0.07 }),
  bien: () => notas([660, 990], 0.08),
  mal: () => tono(240, 0.22, { tipo: "square", hasta: 140, volumen: 0.05 }),
  conectar: () => notas([523, 784], 0.08, { tipo: "sine" }),
  salida: () => notas([523, 392], 0.1, { tipo: "sine" }),
  inicio: () => notas([523, 659, 784], 0.08),
  resultado: () => notas([784, 988], 0.07, { tipo: "sine" }),
  podio: () => notas([784, 988, 1175], 0.1),
  fanfarria: () => notas([523, 659, 784, 1047], 0.11),
};
const sonar = (nombre) => SONIDOS[nombre]?.();

function sonidoMensaje(msg) {
  const t = msg.type || "";
  const mio = (msg.jugadores || {})[yoId];
  if (["room_created", "room_joined", "player_joined"].includes(t)) sonar("conectar");
  else if (["player_left", "opponent_left"].includes(t)) sonar("salida");
  else if (t === "error") sonar("mal");
  else if (["match_start", "individual_game_start", "round_start", "tiebreak_start"].includes(t)) sonar("inicio");
  else if (t.endsWith("_show")) sonar("aparece");
  else if (t.endsWith("_feedback")) sonar(msg.aceptada ? "bien" : "mal");
  else if (t === "round_result") sonar(msg.ganador === yoId ? "bien" : msg.ganador ? "mal" : "resultado");
  else if (t.endsWith("_result")) sonar(mio && "acierto" in mio ? (mio.acierto ? "bien" : "mal") : "resultado");
  else if (t === "podium_update") sonar("podio");
  else if (t === "podium_final" || t === "match_over" || t.endsWith("_over") || t === "individual_summary") sonar("fanfarria");
}

// Un clic suave en cada botón (incluidos los generados por los juegos).
document.addEventListener(
  "pointerdown",
  (e) => {
    const boton = e.target.closest("button, select");
    if (boton && !boton.disabled) sonar("click");
  },
  true
);
// Flechas y Enter de los contadores también suenan.
document.addEventListener(
  "keydown",
  (e) => {
    if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Enter"].includes(e.key)) sonar("click");
  },
  true
);
// Tic en cada número de las cuentas regresivas (todas usan #cuenta-previa-numero).
let ultimoTic = null;
new MutationObserver(() => {
  const el = document.getElementById("cuenta-previa-numero");
  const texto = el ? el.textContent : null;
  if (texto && texto !== ultimoTic) sonar("tic");
  ultimoTic = texto;
}).observe(document.getElementById("app"), { childList: true, subtree: true, characterData: true });

function pintarBotonSonido() {
  const b = $("btn-sonido");
  b.textContent = sonidoActivo ? "♪ ON" : "♪ OFF";
  b.setAttribute("aria-pressed", String(sonidoActivo));
  b.setAttribute("aria-label", sonidoActivo ? "Sonido activado" : "Sonido desactivado");
}
$("btn-sonido").addEventListener("click", () => {
  sonidoActivo = !sonidoActivo;
  try { localStorage.setItem("konitive-sonido", sonidoActivo ? "on" : "off"); } catch (_) {}
  pintarBotonSonido();
  sonar("click");
});
pintarBotonSonido();
