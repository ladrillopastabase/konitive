/* SÍLABAS: se cuentan las sílabas gramaticales de una frase. */
"use strict";

registrarMini("silabas", {
  visual: (datos) => (datos.frase ? `<div class="frase-silabas">${escapeHtml(datos.frase.toUpperCase())}</div>` : ""),
  estimulo(msg) {
    return [this.visual(msg), '<p class="pista">¡SÍLABAS!</p>'];
  },
  respuesta(msg, mando) {
    $("contenido").innerHTML = panelAmplio(
      `<p class="kicker">${mando ? "MIRA LA PANTALLA · CUENTA SÍLABAS" : `CONTAR SÍLABAS · ${etiquetaRonda(msg)}`}</p>`,
      (mando ? "" : this.visual(msg)) || miraPantallaHtml(),
      `<p class="pista">${mando ? "MARCA EL TOTAL" : "CUENTA SÍLABAS"}</p>
      ${STEPPER_HTML}
      <button id="btn-responder" class="boton rojo">CONFIRMAR</button>
      <div class="mini-progreso" id="mini-progreso"></div>`,
      "respuesta-silabas"
    );
    stepperConteo((valor) => enviar({ type: "silabas_answer", ronda: msg.ronda, respuesta: valor }));
  },
  feedback: (msg) => alFeedback?.(msg),
  correcta: (reto) =>
    `<div class="mini-respuesta">${escapeHtml(reto.pista || "")} = <b>${reto.total || 0} SÍLABAS</b></div>`,
});
