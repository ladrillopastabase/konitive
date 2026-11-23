/* OPERACIONES: la operación se ve un instante y el resultado se escribe cifra a cifra. */
"use strict";

/* ---------- Operaciones Matemáticas ---------- */
function mostrarCuentaOperaciones(msg) {
  actualizarMarcador(msg.marcador);
  $("etiqueta-ronda").textContent =
    `RONDA ${String(msg.ronda).padStart(2, "0")} / ${msg.necesario}`;
  $("titulo-juego").textContent = "OPERACIONES";
  mostrarCuentaPrevia(msg, {
    kicker: `FASE 01 · PREPARA LA MEMORIA · ${escapeHtml(msg.dificultad || "")}`,
    pie: "LA OPERACIÓN APARECERÁ DESPUÉS",
    glifo: "∑",
  });
}

function mostrarOperacion(msg) {
  clearInterval(cuentaTimer);
  cuentaTimer = null;
  $("contenido").innerHTML = `<div class="panel panel-escena flash">
    <p class="kicker">FASE 02 · MEMORIZA · ${escapeHtml(msg.dificultad || "")}</p>
    <div class="flash-palabra">${escapeHtml(msg.texto)}</div>
    <p class="pista flash-pista">Solo un instante. Recuerda el resultado.</p>
  </div>`;
}

function iniciarEscrituraDigitos(msg) {
  actualizarMarcador(msg.marcador);
  $("etiqueta-ronda").textContent =
    `RONDA ${String(msg.ronda).padStart(2, "0")} / ${msg.necesario || 10}`;
  $("titulo-juego").textContent = "OPERACIONES";
  iniciarCanvasEscritura({
    kicker: "FASE 03 · ESCRIBE EL RESULTADO CIFRA A CIFRA",
    pista: "Dibuja una cifra (0-9), pulsa LISTO y sigue con la siguiente.",
    tipoMensaje: "digit",
    terminoTexto: "RESULTADO COMPLETO · ESPERANDO",
  });
}

function mostrarResultadoOperaciones(msg) {
  detenerTimers();
  actualizarMarcador(msg.marcador);
  const propio =
    (msg.desglose && yoId && msg.desglose[yoId]) || {
      tiempo: 0,
      errores: 0,
      puntuacion: 0,
      correctas: 0,
      automaticas: 0,
    };
  const detalle = textoDesglose(propio);

  $("contenido").innerHTML = `<div class="panel resultado cajas-resultado">
    <div class="resultado-cabecera" style="width:100%">
      <p class="kicker">INFORME · RONDA ${String(msg.ronda).padStart(2, "0")} / ${msg.necesario} · ${escapeHtml(msg.dificultad || "")}</p>
      <h2>RESULTADO</h2>
    </div>
    <div class="palabra-final">
      <span class="conteo-final-etiqueta">LA OPERACIÓN ERA</span>
      <div class="palabra-final-texto">${escapeHtml(msg.texto || "")} = ${escapeHtml(msg.resultado || "")}</div>
    </div>
    <div class="puntajes" style="width:100%">
      <div class="puntaje">
        <div class="numero">${numero(propio.puntuacion)}</div>
        <div class="desglose">${detalle}</div>
        <div class="quien">PUNTUACIÓN ACUMULADA</div>
      </div>
    </div>
    ${modoFiesta ? tablaClasificacion(msg.clasificacion || []) : ""}
  </div>`;
}

registrarMensajes({
  operacion_countdown: mostrarCuentaOperaciones,
  operacion_show: (msg) => {
    if (esMandoFiesta()) {
      mostrarEspera("MIRA LA PANTALLA", "MEMORIZA", "La operación aparece solo en la pantalla del anfitrión.");
    } else {
      mostrarOperacion(msg);
    }
  },
  operacion_write: (msg) => {
    if (esPantallaFiesta()) {
      mostrarEspera("PANTALLA · ESPECTADOR", "CALCULANDO…", "Los mandos están escribiendo el resultado.");
    } else {
      iniciarEscrituraDigitos(msg);
    }
  },
  digit_feedback: (msg) => alFeedback?.(msg),
  operacion_done: (msg) => {
    alTerminar?.(msg);
    aviso(msg.automaticas ? `RESULTADO COMPLETO · ${msg.automaticas} AUTOMÁTICA(S)` : "RESULTADO COMPLETO · ESPERANDO");
  },
  operacion_result: (msg) => {
    if (!resultadoSoloEnPantalla()) mostrarResultadoOperaciones(msg);
  },
  operacion_over: avisarFinPrueba,
});
