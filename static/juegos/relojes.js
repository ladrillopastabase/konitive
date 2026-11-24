/* RELOJES: cuánto tiempo pasó entre dos despertadores (horas y minutos). */
"use strict";

function relojDespertador(hora, minuto) {
  return `<div class="despertador-estimulo">
    <span class="despertador-hora">${String(hora % 12 || 12).padStart(2, "0")}</span>
    <span class="despertador-puntos">:</span>
    <span class="despertador-min">${String(minuto).padStart(2, "0")}</span>
  </div>`;
}

registrarMini("relojes", {
  visual(datos) {
    if (!datos.reloj1) return "";
    const [h1, m1] = datos.reloj1;
    const [h2, m2] = datos.reloj2 || [12, 0];
    return `<div class="relojes">
      <div>${relojDespertador(h1, m1)}<span>PRIMERO · ${escapeHtml(datos.periodo1 || "")}</span></div>
      <div class="reloj-flecha">→</div>
      <div>${relojDespertador(h2, m2)}<span>DESPUÉS · ${escapeHtml(datos.periodo2 || "")}</span></div>
    </div>`;
  },
  estimulo(msg) {
    return [this.visual(msg), '<p class="pista">¡RELOJES!</p>'];
  },
  respuesta(msg, mando) {
    const show = mando ? {} : (msg.reloj1 ? msg : (ultimoShowMini.relojes || {}));
    $("contenido").innerHTML = panelAmplio(
      `<p class="kicker">${mando ? "MIRA LA PANTALLA · CALCULA LA DIFERENCIA" : `RELOJES · ${etiquetaRonda(msg)}`}</p>`,
      mando ? miraPantallaHtml() : (this.visual(show) || miraPantallaHtml()),
      `<div class="steppers-reloj">
        ${[["horas", "HORAS"], ["minutos", "MINUTOS"]].map(([campo, etiqueta]) =>
          `<div class="stepper-campo" data-campo-reloj="${campo}">
            <span>${etiqueta}</span>
            <div class="stepper">
              <button type="button" class="stepper-boton" data-campo="${campo}" data-delta="-1" aria-label="Quitar ${etiqueta.toLowerCase()}">−</button>
              <output class="stepper-valor" id="reloj-${campo}" aria-live="polite">00</output>
              <button type="button" class="stepper-boton" data-campo="${campo}" data-delta="1" aria-label="Agregar ${etiqueta.toLowerCase()}">+</button>
            </div>
          </div>`
        ).join("")}
      </div>
      <button type="button" class="boton rojo" id="btn-responder">CONFIRMAR</button>
      <div class="mini-progreso" id="mini-progreso"></div>`,
      "respuesta-relojes"
    );
    // Las respuestas válidas: 0-11 horas y minutos de 15 en 15.
    const LIMITES = { horas: [0, 11, 1], minutos: [0, 45, 15] };
    const valores = { horas: 0, minutos: 0 };
    let activo = "horas";
    let confirmado = false;
    const enfocar = (campo) => {
      activo = campo;
      $("contenido").querySelectorAll("[data-campo-reloj]").forEach((el) =>
        el.classList.toggle("activo", el.dataset.campoReloj === campo)
      );
    };
    const cambiar = (campo, pasos) => {
      if (confirmado) return;
      enfocar(campo);
      const [minimo, maximo, paso] = LIMITES[campo];
      valores[campo] = Math.min(maximo, Math.max(minimo, valores[campo] + pasos * paso));
      $(`reloj-${campo}`).textContent = String(valores[campo]).padStart(2, "0");
    };
    const confirmar = () => {
      if (confirmado) return;
      confirmado = true;
      $("contenido").querySelectorAll(".stepper-boton, #btn-responder").forEach((b) => (b.disabled = true));
      if (teclaConteo) document.removeEventListener("keydown", teclaConteo);
      teclaConteo = null;
      enviar({ type: "relojes_answer", ronda: msg.ronda, respuesta: { ...valores } });
      aviso("RESPUESTA CONFIRMADA");
    };
    $("contenido").querySelectorAll("[data-campo]").forEach((boton) => {
      boton.addEventListener("click", () => cambiar(boton.dataset.campo, Number(boton.dataset.delta)));
    });
    $("btn-responder").addEventListener("click", confirmar);
    if (teclaConteo) document.removeEventListener("keydown", teclaConteo);
    teclaConteo = (e) => {
      if (e.key === "ArrowLeft") { e.preventDefault(); enfocar("horas"); }
      else if (e.key === "ArrowRight") { e.preventDefault(); enfocar("minutos"); }
      else if (e.key === "ArrowUp") { e.preventDefault(); cambiar(activo, 1); }
      else if (e.key === "ArrowDown") { e.preventDefault(); cambiar(activo, -1); }
      else if (e.key === "Enter") { e.preventDefault(); confirmar(); }
    };
    document.addEventListener("keydown", teclaConteo);
    enfocar("horas");
    $("btn-responder").focus();
  },
  feedback: (msg) => alFeedback?.(msg),
  correcta: (reto) =>
    `<div class="mini-respuesta">${escapeHtml(`${reto.digital1 || ""} ${reto.periodo1 || ""}`)} → ${escapeHtml(`${reto.digital2 || ""} ${reto.periodo2 || ""}`)} = <b>${reto.horas || 0} h ${reto.minutos || 0} min</b></div>`,
});
