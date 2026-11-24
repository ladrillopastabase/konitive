/* CAJAS: pila isométrica que se ve un instante; se cuentan también las ocultas. */
"use strict";

// Separación entre columnas (0 = cajas juntas). El servidor ya descarta las
// pilas con cajas tapadas midiendo este mismo dibujo (juego/cajas.py): si
// cambias la geometría aquí, cambia también fraccion_visible allá.
const SEPARACION_CAJAS = 0;

function puntoCubo(x, y, z, geo, celda = null) {
  let px = x;
  let py = y;
  if (celda) {
    const [cx, cy] = celda;
    const k = 1 - SEPARACION_CAJAS;
    px = cx + 0.5 + (x - cx - 0.5) * k;
    py = cy + 0.5 + (y - cy - 0.5) * k;
  }
  return [
    geo.origenX + (px - py) * geo.w / 2,
    geo.origenY + (px + py) * geo.h / 4 - z * geo.h / 2,
  ];
}

function geometriaCajas(alturas, canvas) {
  const base = alturas.length;
  const vertices = [];
  for (const x of [0, base]) {
    for (const y of [0, base]) {
      vertices.push([(x - y) / 2, (x + y) / 4]);
    }
  }
  for (let y = 0; y < base; y++) {
    for (let x = 0; x < base; x++) {
      if (!alturas[y][x]) continue;
      for (const z of [0, alturas[y][x] + 1]) {
        for (const [dx, dy] of [[0, 0], [1, 0], [1, 1], [0, 1]]) {
          vertices.push([
            (x + dx - y - dy) / 2,
            (x + dx + y + dy) / 4 - z / 2,
          ]);
        }
      }
    }
  }
  const xs = vertices.map((v) => v[0]);
  const ys = vertices.map((v) => v[1]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const margen = 14;
  const ancho = Math.max(1, canvas.width - 2 * margen);
  const alto = Math.max(1, canvas.height - 2 * margen);
  const escala = Math.min(ancho / (maxX - minX), alto / (maxY - minY));
  return {
    w: escala,
    h: escala,
    origenX: margen + (ancho - (maxX - minX) * escala) / 2 - minX * escala,
    origenY: margen + (alto - (maxY - minY) * escala) / 2 - minY * escala,
  };
}

function poligono(ctx, puntos, relleno) {
  ctx.beginPath();
  ctx.moveTo(puntos[0][0], puntos[0][1]);
  for (let i = 1; i < puntos.length; i++) ctx.lineTo(puntos[i][0], puntos[i][1]);
  ctx.closePath();
  ctx.lineJoin = "round";
  ctx.fillStyle = relleno;
  ctx.fill();
  ctx.stroke();
}

function dibujarPila(canvas, alturas) {
  if (!canvas || !alturas || !alturas.length) return;
  // Dibuja al tamaño real en pantalla (nítido en el lienzo grande de PC y en
  // pantallas retina); si aún no se ve, usa el tamaño del atributo.
  const caja = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  let area = { width: canvas.width, height: canvas.height };
  let escalaPantalla = 1;
  if (caja.width > 0 && caja.height > 0) {
    canvas.width = Math.round(caja.width * dpr);
    canvas.height = Math.round(caja.height * dpr);
    area = { width: caja.width, height: caja.height };
    escalaPantalla = dpr;
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(escalaPantalla, 0, 0, escalaPantalla, 0, 0);
  ctx.clearRect(0, 0, area.width, area.height);
  const geo = geometriaCajas(alturas, area);
  const p = (x, y, z, cx, cy) => puntoCubo(x, y, z, geo, [cx, cy]);

  // Cuadrícula de la base: rombos en el suelo como referencia de profundidad.
  ctx.lineWidth = 1;
  ctx.strokeStyle = "#5f594e";
  ctx.globalAlpha = 0.55;
  for (let y = 0; y < alturas.length; y++) {
    for (let x = 0; x < alturas[y].length; x++) {
      poligono(
        ctx,
        [
          p(x, y, 0, x, y),
          p(x + 1, y, 0, x, y),
          p(x + 1, y + 1, 0, x, y),
          p(x, y + 1, 0, x, y),
        ],
        "#efe9dc"
      );
    }
  }

  // Algoritmo del pintor: primero lo lejano (x+y bajo) y abajo; después lo
  // cercano y las capas altas, que tapan a las anteriores.
  const cubos = [];
  for (let y = 0; y < alturas.length; y++) {
    for (let x = 0; x < alturas[y].length; x++) {
      for (let z = 0; z < alturas[y][x]; z++) cubos.push({ x, y, z });
    }
  }
  cubos.sort((a, b) => a.x + a.y - (b.x + b.y) || a.z - b.z);

  ctx.globalAlpha = 1;
  ctx.lineWidth = 1.2;
  ctx.strokeStyle = "#1c1a17";
  for (const { x, y, z } of cubos) {
    // Solo se ven las caras que miran a la cámara isométrica: la de y+1
    // (izquierda en pantalla) y la de x+1 (derecha), más la cara superior.
    // Pintar las caras de x e y constantes daba aristas que no cerraban.
    poligono(ctx, [p(x, y + 1, z, x, y), p(x + 1, y + 1, z, x, y), p(x + 1, y + 1, z + 1, x, y), p(x, y + 1, z + 1, x, y)], "#d8cebb");
    poligono(ctx, [p(x + 1, y, z, x, y), p(x + 1, y + 1, z, x, y), p(x + 1, y + 1, z + 1, x, y), p(x + 1, y, z + 1, x, y)], "#b7ab95");
    poligono(ctx, [p(x, y, z + 1, x, y), p(x + 1, y, z + 1, x, y), p(x + 1, y + 1, z + 1, x, y), p(x, y + 1, z + 1, x, y)], "#f9f5ea");
  }
  ctx.globalAlpha = 1;
}

function mostrarCuentaCajas(msg) {
  actualizarMarcador(msg.marcador);
  $("etiqueta-ronda").textContent = `RONDA ${String(msg.ronda).padStart(2, "0")} / ${msg.necesario}`;
  $("titulo-juego").textContent = "CONTAR CAJAS";
  mostrarCuentaPrevia(msg, {
    kicker: `FASE 01 · PREPARA LA MEMORIA · ${escapeHtml(msg.dificultad)}`,
    pie: "LA PILA APARECERÁ DESPUÉS",
    glifo: "▣",
  });
}

function mostrarPilaCajas(msg) {
  detenerTimers();
  $("contenido").innerHTML = `<div class="panel panel-escena panel-amplio">
    <div class="amplio-arriba">
      <p class="kicker">FASE 02 · OBSERVA · ${escapeHtml(msg.dificultad)}</p>
      <h2 class="panel-titulo">¿CUÁNTAS CAJAS HAY?</h2>
    </div>
    <div class="amplio-visual"><div class="campo-cajas"><canvas id="lienzo-cajas" class="lienzo-cajas" width="560" height="360" aria-label="Pila de cajas"></canvas></div></div>
    <div class="amplio-abajo"><div class="barra-tiempo"><div id="barra-tiempo"></div></div></div>
  </div>`;
  dibujarPila($("lienzo-cajas"), msg.alturas);
  barraTiempo(msg.duracion);
}

function ocultarPilaCajas() {
  const lienzo = $("lienzo-cajas");
  if (lienzo) lienzo.classList.add("oculto");
  cuentaTimer = setTimeout(prepararRespuestaCajas, 260);
}

function prepararRespuestaCajas() {
  detenerTimers();
  $("contenido").innerHTML = `<div class="panel">
    <p class="kicker">FASE 03 · RESPONDE</p>
    <h2 class="panel-titulo">¿CUÁNTAS CAJAS HABÍA?</h2>
    ${STEPPER_HTML}
    <button id="btn-responder" class="boton rojo">CONFIRMAR CUENTA</button>
  </div>`;

  stepperConteo((valor) => enviar({ type: "cajas_answer", count: valor }));
}

function mostrarResultadoCajas(msg) {
  detenerTimers();
  actualizarMarcador(msg.marcador);
  const propio = (msg.jugadores && msg.jugadores[yoId]) || msg;
  const acierto = Boolean(propio.acierto);
  const detalle = textoDesglose(propio);

  $("contenido").innerHTML = `<div class="panel resultado cajas-resultado panel-amplio">
    <div class="amplio-arriba">
    <div class="resultado-cabecera" style="width:100%">
      <p class="kicker">INFORME · RONDA ${String(msg.ronda).padStart(2, "0")} / ${msg.necesario} · ${escapeHtml(msg.dificultad || "")}</p>
      <h2>INFORME DE LA RONDA</h2>
    </div>
    </div>
    <div class="amplio-visual"><div class="campo-cajas"><canvas id="lienzo-cajas" class="lienzo-cajas" width="560" height="360" aria-label="Pila de cajas"></canvas></div></div>
    <div class="amplio-abajo">
    <div class="cajas-datos">
      <span>TOTAL: <b>${msg.total}</b> CAJAS</span>
      <span>A LA VISTA: <b>${msg.visibles}</b> · OCULTAS: <b>${msg.total - msg.visibles}</b></span>
      <span>ELEGISTE <b>${propio.elegida ?? "—"}</b></span>
    </div>
    <div class="puntajes" style="width:100%">
      <div class="puntaje ${acierto ? "ganador" : ""}">
        <div class="numero">${numero(propio.puntuacion)}</div>
        <div class="desglose">${detalle}</div>
        <div class="quien">PUNTUACIÓN ACUMULADA</div>
      </div>
    </div>
    ${modoFiesta ? tablaClasificacion(msg.clasificacion || []) : ""}
    </div>
  </div>`;
  dibujarPila($("lienzo-cajas"), msg.alturas);
}

registrarMensajes({
  cajas_countdown: mostrarCuentaCajas,
  cajas_show: (msg) => {
    if (esMandoFiesta()) {
      mostrarEspera("MIRA LA PANTALLA", "¡A CONTAR CAJAS!", "La pila aparece en la pantalla del anfitrión.");
    } else {
      mostrarPilaCajas(msg);
    }
  },
  cajas_hide: () => {
    if (esPantallaFiesta()) {
      mostrarEspera("PANTALLA · ESPECTADOR", "CONTANDO…", "Los mandos están contando las cajas.");
    } else {
      ocultarPilaCajas();
    }
  },
  cajas_result: (msg) => {
    if (!resultadoSoloEnPantalla()) mostrarResultadoCajas(msg);
  },
  cajas_feedback: (msg) => {
    if (msg.pid !== yoId) return;
    mostrarResultadoPrivado(
      "CAJAS · TU RESULTADO",
      msg.acepta,
      msg.elegida == null ? "NO CONFIRMASTE A TIEMPO" : `ELEGISTE ${msg.elegida}`
    );
  },
  cajas_over: avisarFinPrueba,
});
