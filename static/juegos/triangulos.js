/* TRIÁNGULOS: pirámide de operaciones; el resultado final se escribe a mano. */
"use strict";

function trianguloHtml(reto, mostrarResultados = false) {
  // Pirámide en rejilla de 5 columnas: cada casilla del medio queda bajo el
  // par que la forma, con flechas, para que no se lea como a + b + c.
  const [a, b, c] = reto.top || [];
  const [o1, o2] = reto.ops || [];
  const [i1, i2] = reto.intermedios || ["?", "?"];
  const ver = (v) => (mostrarResultados ? v : "?");
  const op = (o) => `<b class="tri-op">${o === "-" ? "−" : o}</b>`;
  const fl = (f) => `<i class="tri-flecha" aria-hidden="true">${f}</i>`;
  const nota = (t) => `<small class="tri-nota">${t}</small>`;
  return `<div class="triangulo" aria-label="Pirámide: ${a} ${o1} ${b} y ${b} ${o2} ${c}, luego se operan los dos resultados">
    <span class="tri-num">${a}</span>${op(o1)}<span class="tri-num">${b}</span>${op(o2)}<span class="tri-num">${c}</span>${nota("")}
    ${fl("↘")}<span></span>${fl("↙ ↘")}<span></span>${fl("↙")}${nota("")}
    <span></span><span class="tri-num tri-medio">${ver(i1)}</span>${op(reto.op_final || "?")}<span class="tri-num tri-medio">${ver(i2)}</span><span></span>${nota(`${a}${o1}${b} · ${b}${o2}${c}`)}
    <span></span>${fl("↘")}<span></span>${fl("↙")}<span></span>${nota("")}
    <span></span><span></span><span class="tri-num tri-final">${ver(reto.resultado)}</span><span></span><span></span>${nota("RESULTADO")}
  </div>`;
}

registrarMini("triangulos", {
  visual: (datos) => (datos.top ? trianguloHtml(datos) : ""),
  estimulo(msg) {
    return [this.visual(msg), '<p class="pista">¡TRIÁNGULOS!</p>'];
  },
  respuesta(msg, mando) {
    const estimulo = mando ? null : (msg.estimulo || {});
    iniciarCanvasEscritura({
      kicker: mando ? "MIRA LA PANTALLA · ESCRIBE EL RESULTADO" : `${nombreJuego("triangulos")} · ${etiquetaRonda(msg)}`,
      recordatorio: estimulo?.top ? trianguloHtml(estimulo) : "",
      pista: "",
      tipoMensaje: "triangulos_digit",
      extra: { ronda: msg.ronda },
      feedbackAceptada: (fb) => `✓ ${fb.esperada ?? ""} · BIEN`,
      feedbackRechazada: (fb) => `✗ PARECE ${fb.predicha ?? "?"} · INTENTO ${fb.intentos || 1}/3`,
      terminoTexto: "RESPUESTA COMPLETA · ESPERANDO",
    });
    const letras = $("letras-escritas");
    if (letras && msg.campo) letras.dataset.campo = msg.campo;
  },
  feedback: (msg) => alFeedback?.(msg),
  correcta: (reto) => trianguloHtml(reto, true),
});
