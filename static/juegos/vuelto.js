/* DAR VUELTO: se arma el vuelto exacto con billetes y monedas. */
"use strict";

const pesos = (n) => `$${Number(n).toLocaleString("es-CL")}`;

registrarMini("vuelto", {
  visual(datos, compacta = false) {
    if (!datos.precio_texto) return "";
    return compacta
      ? `<div class="vuelto-escena compacta">
          <span>${escapeHtml(datos.producto?.nombre || "")} ${escapeHtml(datos.precio_texto)}</span>
          <span>PAGÓ ${escapeHtml(datos.pago_texto || "")}</span>
        </div>`
      : `<div class="vuelto-escena">
          <div class="vuelto-nombre">${escapeHtml(datos.producto?.nombre || "PRODUCTO")}</div>
          <div class="vuelto-precio">${escapeHtml(datos.precio_texto)}</div>
          <div class="vuelto-pago">EL CLIENTE PAGÓ CON <b>${escapeHtml(datos.pago_texto || "")}</b></div>
        </div>`;
  },
  estimulo(msg) {
    return [this.visual(msg), '<p class="pista">Prepara el vuelto exacto en tu celular.</p>'];
  },
  respuesta(msg, mando) {
    const elegidos = {};
    const escena = mando
      ? miraPantallaHtml("MIRA LA PANTALLA · PRECIO Y PAGO")
      : (this.visual(msg, true) || miraPantallaHtml());
    $("contenido").innerHTML = panelAmplio(
      `<p class="kicker">ARMA EL VUELTO EXACTO</p>
      ${escena}
      <div class="vuelto-bandera"><span>LLEVAS ENTREGADO</span><b id="vuelto-total">$0</b><div id="vuelto-chips" class="vuelto-chips"></div></div>`,
      `<div class="vuelto-denominaciones">
        ${(msg.denominaciones || []).map((d) =>
          `<div class="denom"><button type="button" class="boton contorno chico" data-denom="${d}">${pesos(d)}</button></div>`
        ).join("")}
      </div>`,
      `<button type="button" class="boton rojo" id="vuelto-entregar">ENTREGAR ✓</button>
      <div class="mini-progreso" id="mini-progreso"></div>`,
      "respuesta-vuelto"
    );
    const pintar = () => {
      $("vuelto-chips").innerHTML = Object.entries(elegidos)
        .filter(([, n]) => n > 0)
        .map(([d, n]) => `<span class="vuelto-chip">${pesos(d)} × ${n}</span>`)
        .join("");
      const total = Object.entries(elegidos).reduce((suma, [d, n]) => suma + Number(d) * n, 0);
      $("vuelto-total").textContent = pesos(total);
    };
    $("contenido").querySelectorAll("[data-denom]").forEach((boton) => {
      boton.addEventListener("click", () => {
        const d = boton.dataset.denom;
        elegidos[d] = (elegidos[d] || 0) + 1;
        pintar();
      });
    });
    $("vuelto-entregar").addEventListener("click", (e) => {
      e.currentTarget.disabled = true;
      enviar({ type: "vuelto_answer", ronda: msg.ronda, respuesta: { ...elegidos } });
    });
  },
  correcta(reto) {
    const optimo = Object.entries(reto.optimo || {})
      .map(([d, n]) => `${pesos(d)} × ${n}`)
      .join(" · ");
    return `<div class="mini-respuesta">VUELTO <b>${escapeHtml(reto.vuelto_texto || "")}</b><br><span class="pista">ÓPTIMO: ${escapeHtml(optimo)}</span></div>`;
  },
});
