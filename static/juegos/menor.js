/* MENOR A MAYOR: se tocan los números dispersos en orden ascendente. */
"use strict";

// Casillas tocadas que esperan la confirmación del servidor.
let pendientesMenor = [];
let limpiarAvisoMenor = null;

function grillaMenorHtml(numeros, interactiva) {
  return `<div class="campo-menor ${interactiva ? "interactiva" : ""}">
    ${(numeros || []).map((n, i) =>
      `<button type="button" class="numero-menor" style="left:${n.x * 100}%;top:${n.y * 100}%" data-indice="${i}" ${interactiva ? "" : "disabled"}>${n.valor}</button>`
    ).join("")}
  </div>`;
}

function marcarMenor(acepta) {
  const boton = pendientesMenor.shift();
  if (!boton || !boton.isConnected) return;
  const avisoMenor = $("menor-aviso");
  if (acepta) {
    boton.disabled = true;
    boton.classList.add("marcado");
    if (avisoMenor) avisoMenor.textContent = "";
    return;
  }
  // Error: la casilla tiembla en rojo y sigue disponible; no se reinicia.
  boton.classList.remove("error");
  void boton.offsetWidth;
  boton.classList.add("error");
  setTimeout(() => boton.classList.remove("error"), 600);
  if (avisoMenor) {
    avisoMenor.textContent = "✗ ESE NO ERA · TOCA EL MÁS PEQUEÑO QUE QUEDA";
    clearTimeout(limpiarAvisoMenor);
    limpiarAvisoMenor = setTimeout(() => (avisoMenor.textContent = ""), 1800);
  }
}

registrarMini("menor", {
  // Un HTML suelto (no [visual, abajo]): el campo ocupa todo el ancho.
  estimulo: (msg) => grillaMenorHtml(msg.numeros, false),
  respuesta(msg) {
    $("contenido").innerHTML = `<div class="panel panel-escena">
      <p class="kicker">TOCA LOS NÚMEROS DE MENOR A MAYOR</p>
      ${grillaMenorHtml(msg.numeros, true)}
      <p class="menor-aviso" id="menor-aviso" aria-live="polite"></p>
      <div class="mini-progreso" id="mini-progreso"></div>
    </div>`;
    pendientesMenor = [];
    $("contenido").querySelectorAll("[data-indice]").forEach((boton) => {
      boton.addEventListener("click", () => {
        // Se pinta al confirmar el servidor: un error no deja la casilla verde.
        if (boton.disabled || pendientesMenor.includes(boton)) return;
        pendientesMenor.push(boton);
        enviar({ type: "menor_answer", ronda: msg.ronda, respuesta: Number(boton.dataset.indice) });
      });
    });
  },
  feedback: (msg) => marcarMenor(msg.acepta),
  correcta: (reto) =>
    `<div class="mini-respuesta">ORDEN: ${(reto.orden || []).map((i) => reto.numeros[i]?.valor).join(" → ")}</div>`,
});
