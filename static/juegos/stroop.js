/* STROOP: se nombra el color de la tinta, no lo que dice la palabra. */
"use strict";

const COLOR_HEX = {
  rojo: "#d33827",
  azul: "#1d4ed8",
  verde: "#246b58",
  amarillo: "#a87300",
};

registrarMini("stroop", {
  visual: (datos) =>
    datos.tinta
      ? `<div class="stroop-palabra" style="color:${COLOR_HEX[datos.tinta] || "#1c1a17"}">${escapeHtml((datos.palabra || "").toUpperCase())}</div>`
      : "",
  estimulo(msg) {
    return [
      this.visual(msg),
      (msg.duracion ? '<div class="barra-tiempo"><div id="barra-tiempo"></div></div>' : "") +
        '<p class="pista">¡COLORES!</p>',
    ];
  },
  respuesta(msg, mando) {
    // La palabra ya se borró: no se recupera del _show aunque el cliente lo
    // haya guardado. El aviso no revela la tinta ni lo que decía la palabra.
    $("contenido").innerHTML = panelAmplio(
      `<p class="kicker">ELIGE EL COLOR DE LA TINTA</p>`,
      mando
        ? miraPantallaHtml("MIRA LA PANTALLA · ELIGE LA TINTA")
        : `<div class="mira-pantalla stroop-oculto"><b>¿DE QUÉ COLOR ERA LA TINTA?</b><span>La palabra ya se borró · responde de memoria</span></div>`,
      `<p class="pista">ELIGE LA TINTA</p>
      <div class="stroop-botones">
        ${["rojo", "azul", "verde", "amarillo"].map((color) =>
          `<button type="button" class="boton stroop-opcion" data-color="${color}">${color.toUpperCase()}</button>`
        ).join("")}
      </div>
      <div class="mini-progreso" id="mini-progreso"></div>`,
      "respuesta-stroop"
    );
    opcionesUnicas("stroop", "color", msg.ronda);
  },
  correcta: (reto) =>
    `<div class="mini-respuesta">LA TINTA ERA <b style="color:${COLOR_HEX[reto.tinta] || "#1c1a17"}">${escapeHtml((reto.tinta || "").toUpperCase())}</b></div>`,
});
