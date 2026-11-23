/* PIEDRA · PAPEL · TIJERA: elegir la mano que gane o pierda según la consigna. */
"use strict";

registrarMini("ppt", {
  visual(datos) {
    if (!datos.rival) return "";
    const gana = datos.objetivo === "ganar";
    return `<div class="ppt-visual">
      <div class="ppt-rival">RIVAL · <b>${escapeHtml(datos.rival.toUpperCase())}</b></div>
      <div class="ppt-consigna ${gana ? "ppt-ganar" : "ppt-perder"}">${gana ? "GANAR" : "PERDER"}</div>
    </div>`;
  },
  estimulo(msg) {
    return [this.visual(msg), '<p class="pista">Elige la mano que cumpla la consigna contra el rival</p>'];
  },
  respuesta(msg, mando) {
    // En FIESTA el mando solo recibe {"mira": true}: la mano del rival y la
    // consigna viven en la pantalla del anfitrión. En INDIVIDUAL llegan en el
    // ppt_write y se muestran aquí mismo.
    $("contenido").innerHTML = panelAmplio(
      '<p class="kicker">ELIGE LA MANO QUE CUMPLA LA CONSIGNA</p>',
      mando ? miraPantallaHtml("MIRA LA PANTALLA · ELIGE TU MANO") : this.visual(msg),
      `<p class="pista">${mando
        ? "Mira la pantalla y elige tu mano aquí."
        : "Elige la mano que gane o pierda contra el rival según la consigna."}</p>
      <div class="ppt-botones">
        ${["piedra", "papel", "tijera"].map((mano) =>
          `<button type="button" class="boton ppt-opcion" data-mano="${mano}">${mano.toUpperCase()}</button>`
        ).join("")}
      </div>
      <div class="mini-progreso" id="mini-progreso"></div>`,
      "respuesta-ppt"
    );
    opcionesUnicas("ppt", "mano", msg.ronda);
  },
  correcta(reto) {
    const gana = reto.objetivo === "ganar";
    return `<div class="mini-respuesta ppt-respuesta">
      <div class="ppt-rival">RIVAL · <b>${escapeHtml((reto.rival || "").toUpperCase())}</b></div>
      <div class="ppt-consigna ${gana ? "ppt-ganar" : "ppt-perder"}">${gana ? "GANAR" : "PERDER"}</div>
      <div>MANO CORRECTA · <b>${escapeHtml((reto.esperado || "").toUpperCase())}</b></div>
    </div>`;
  },
});
