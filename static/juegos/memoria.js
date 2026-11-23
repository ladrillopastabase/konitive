/* MEMORIA: se memoriza una grilla numerada y se tocan las casillas en orden. */
"use strict";

function grillaMemoriaHtml(grilla, celdas, visibles, posiciones, reveladas) {
  const pares = Object.entries(posiciones || {});
  let salida = `<div class="grilla-memoria" style="--grilla:${grilla}">`;
  for (let i = 0; i < celdas; i++) {
    const par = pares.find(([, destino]) => destino === i);
    const numero = visibles && par ? par[0] : "";
    const marcada = (reveladas || []).includes(i);
    salida += `<button type="button" class="celda-memoria ${marcada ? "marcada" : ""}" data-celda="${i}">${numero}</button>`;
  }
  return salida + "</div>";
}

registrarMini("memoria", {
  estimulo: (msg) => [
    grillaMemoriaHtml(msg.grilla, msg.celdas, true, msg.posiciones, []),
    msg.duracion ? '<div class="barra-tiempo"><div id="barra-tiempo"></div></div>' : "",
  ],
  respuesta(msg) {
    $("contenido").innerHTML = panelAmplio(
      '<p class="kicker">TOCA LAS CASILLAS EN ORDEN (1, 2, 3…)</p>',
      grillaMemoriaHtml(msg.grilla, msg.celdas, false, {}, []),
      '<div class="mini-progreso" id="mini-progreso"></div>',
      "respuesta-memoria"
    );
    $("contenido").querySelectorAll("[data-celda]").forEach((boton) => {
      boton.addEventListener("click", () => {
        enviar({ type: "memoria_answer", ronda: msg.ronda, respuesta: Number(boton.dataset.celda) });
      });
    });
  },
  correcta: (reto) => grillaMemoriaHtml(reto.grilla, reto.grilla * reto.grilla, true, reto.posiciones || {}, []),
});
