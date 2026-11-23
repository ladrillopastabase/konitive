/* SÍLABAS: se cuentan las sílabas gramaticales de una frase. */
"use strict";

registrarMini("silabas", {
  visual: (datos) => (datos.frase ? `<div class="frase-silabas">${escapeHtml(datos.frase.toUpperCase())}</div>` : ""),
  estimulo(msg) {
    return [this.visual(msg), '<p class="pista">Cuenta las sílabas gramaticales de toda la frase, palabra por palabra.</p>'];
  },
  respuesta(msg, mando) {
    $("contenido").innerHTML = panelAmplio(
      `<p class="kicker">${mando ? "MIRA LA PANTALLA · CUENTA SÍLABAS" : `CONTAR SÍLABAS · ${etiquetaRonda(msg)}`}</p>`,
      (mando ? "" : this.visual(msg)) || miraPantallaHtml(),
      `<p class="pista">${mando ? "Cuenta en la PC y marca el total aquí." : "Cuenta las sílabas gramaticales de toda la frase."}</p>
      ${STEPPER_HTML}
      <p class="pista stepper-ayuda">Usa los botones o las flechas arriba y abajo.</p>
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
