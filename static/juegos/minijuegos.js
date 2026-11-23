/* Flujo común de los minijuegos: cuenta previa → estímulo → respuesta → informe.

   Cada minijuego vive en su propio archivo y solo describe lo que lo hace
   distinto, con registrarMini(id, { ... }):

   - visual(datos, compacta): dibujo del estímulo ("" si aún no hay datos). La
     pantalla de la fiesta lo sigue mostrando mientras los mandos responden.
   - estimulo(msg): lo que se ve en <id>_show. Devuelve [visual, abajo] para el
     panel amplio o un HTML completo para un panel simple.
   - respuesta(msg, mando): pinta y conecta los controles de <id>_write/_hide.
   - correcta(reto): HTML de la respuesta correcta en el informe de la ronda.
   - feedback(msg): opcional; por defecto el panel destella verde o rojo. */
"use strict";

const MINIJUEGOS = {};
// Último estímulo de cada minijuego (RELOJES lo vuelve a mostrar al responder).
const ultimoShowMini = {};

function registrarMini(id, def) {
  MINIJUEGOS[id] = def;
  registrarMensajes({
    [`${id}_countdown`]: (msg) =>
      mostrarCuentaPrevia(msg, {
        kicker: `${escapeHtml(nombreJuego(id))} · PREPARA LA ATENCIÓN`,
        pie: etiquetaRonda(msg),
      }),
    [`${id}_show`]: (msg) => {
      ultimoShowMini[id] = msg;
      mostrarEstimuloMini(id, msg);
    },
    [`${id}_hide`]: (msg) => {
      if (esPantallaFiesta()) {
        mostrarEspera("PANTALLA · ESPECTADOR", "RESPONDIENDO…", "Los mandos están respondiendo.");
      } else {
        prepararRespuestaMini(id, msg);
      }
    },
    [`${id}_write`]: (msg) => prepararRespuestaMini(id, msg),
    [`${id}_feedback`]: (msg) => {
      if (msg.pid !== yoId) return;
      (def.feedback || ((fb) => flashMini(fb.acepta)))(msg);
    },
    [`${id}_done`]: (msg) => {
      if (msg.pid !== yoId) return;
      alTerminar?.(msg);
      aviso("RESPUESTA COMPLETA");
    },
    [`${id}_result`]: (msg) => {
      if (!resultadoSoloEnPantalla()) mostrarResultadoMini(id, msg);
    },
    [`${id}_over`]: avisarFinPrueba,
  });
}

registrarMensajes({ mini_progreso: actualizarProgresoMini });

function mostrarEstimuloMini(juego, msg) {
  detenerTimers();
  if (esMandoFiesta() && msg.mira) {
    mostrarEspera(
      "MIRA LA PANTALLA",
      "¡ATENTO!",
      "El estímulo aparece solo en la pantalla del anfitrión."
    );
    return;
  }
  const comun = `<p class="kicker">${escapeHtml(nombreJuego(juego))} · ${etiquetaRonda(msg)}</p>`;
  const cuerpo = MINIJUEGOS[juego].estimulo(msg);
  // [visual, abajo]; un HTML suelto (MENOR A MAYOR) ya trae su propio campo a lo ancho.
  $("contenido").innerHTML = Array.isArray(cuerpo)
    ? panelAmplio(comun, cuerpo[0], cuerpo[1], `estimulo-${juego}`)
    : `<div class="panel panel-escena">${comun}${cuerpo}</div>`;
  if (msg.duracion) barraTiempo(msg.duracion);
}

function prepararRespuestaMini(juego, msg) {
  const def = MINIJUEGOS[juego];
  if (esPantallaFiesta()) {
    const visual = def.visual?.(msg, true) || "";
    if (visual) {
      $("contenido").innerHTML = panelAmplio(
        '<p class="kicker">PANTALLA · ESPECTADOR</p>',
        visual,
        '<p class="pista">LOS MANDOS ESTÁN RESPONDIENDO…</p>',
        `respuesta-${juego} pantalla-espectadora`
      );
      return;
    }
    mostrarEspera("PANTALLA · ESPECTADOR", "RESPONDIENDO…", "Los mandos están respondiendo.");
    return;
  }
  $("etiqueta-ronda").textContent = etiquetaRonda(msg);
  $("titulo-juego").textContent = nombreJuego(juego);
  def.respuesta(msg, esMandoFiesta());
}

// Desactiva las opciones ya elegidas (botones de color, manos…).
function desactivarOpciones(selector) {
  $("contenido").querySelectorAll(selector).forEach((boton) => (boton.disabled = true));
}

// Botones de opción única: al tocar uno se desactivan todos y se envía la respuesta.
function opcionesUnicas(juego, atributo, ronda) {
  const selector = `[data-${atributo}]`;
  $("contenido").querySelectorAll(selector).forEach((boton) => {
    boton.addEventListener("click", () => {
      desactivarOpciones(selector);
      enviar({ type: `${juego}_answer`, ronda, respuesta: boton.dataset[atributo] });
    });
  });
}

function flashMini(acepta) {
  const panel = $("contenido")?.querySelector(".panel");
  if (!panel) return;
  // En MENOR A MAYOR y MEMORIA la casilla tocada ya se pone verde: el panel
  // solo destella cuando hay un error.
  if (acepta && panel.querySelector(".campo-menor, .grilla-memoria")) return;
  panel.classList.remove("mini-bien", "mini-mal");
  void panel.offsetWidth;
  panel.classList.add(acepta ? "mini-bien" : "mini-mal");
  setTimeout(() => panel.classList.remove("mini-bien", "mini-mal"), 500);
}

function actualizarProgresoMini(msg) {
  const caja = $("mini-progreso");
  if (!caja) return;
  caja.textContent = `${msg.marcados || 0} / ${msg.total || 0} · FALLOS ${msg.fallos || 0}`;
}

function mostrarResultadoMini(juego, msg) {
  detenerTimers();
  actualizarMarcador(msg.marcador);
  const filas = Object.entries(msg.jugadores || {})
    .map(([id, dato]) => `<div class="puntaje ${id === yoId ? "propio" : ""}">
      <div class="numero">${escapeHtml((jugadores[id] || "JUGADOR").slice(0, 9))}</div>
      <div class="quien">${dato.acierto ? "✔️ CORRECTO" : "❌ ERROR"}</div>
      <div class="desglose">${numero(dato.tiempo)} s · ERRORES ${dato.errores || 0}</div>
    </div>`)
    .join("");
  $("contenido").innerHTML = `<div class="panel resultado">
    <div class="resultado-cabecera">
      <p class="kicker">${escapeHtml(nombreJuego(juego))} · ${etiquetaRonda(msg)}</p>
      <h2>INFORME DE LA RONDA</h2>
    </div>
    ${MINIJUEGOS[juego].correcta(msg.reto || {})}
    <div class="puntajes">${filas}</div>
  </div>`;
}
