/* HÁMSTERS y PALABRAS: el duelo clásico al mejor de 3 (también en INDIVIDUAL y FIESTA). */
"use strict";

function tituloJuego(juego) {
  return { pajaros: "CONTAR HÁMSTERS", escritura: "ESCRIBIR PALABRAS" }[juego] || NOMBRES[juego] || "KONITIVE";
}

function iniciarRonda(msg) {
  detenerTimers();
  rondaClasica = msg.nivel || 1;
  actualizarMarcador(msg.marcador);
  $("etiqueta-ronda").textContent = msg.desempate
    ? "DESEMPATE"
    : `RONDA ${String(msg.nivel).padStart(2, "0")}`;
  $("titulo-juego").textContent = tituloJuego(msg.juego);
  $("contenido").innerHTML = `<div class="panel panel-escena">
    <p class="kicker">${msg.desempate ? "TODO SE DECIDE AQUÍ" : "PREPARADOS"}</p>
    <div class="glifo">${msg.juego === "pajaros" ? "◎" : "✎"}</div>
    <p class="pista">${
      msg.juego === "pajaros"
        ? "Cuenta los hámsters en cuanto aparezcan."
        : "Primero contaremos hasta tres. Después verás la palabra un instante."
    }</p>
  </div>`;
}

function actualizarConteosVivos(conteos, confirmados) {
  const caja = $("conteos-vivos");
  if (!caja) return;
  const participantes = modoFiesta
    ? Object.entries(jugadores).filter(([id]) => id !== hostId)
    : Object.entries(jugadores);
  // Jugando solo no hay con quién compararse: el panel se oculta.
  caja.hidden = participantes.length < 2;
  caja.innerHTML = participantes
    .map(([id, nombre]) => {
      const listo = confirmados.includes(id);
      const valor = conteos[id] ?? 0;
      return `<div class="conteo-vivo ${id === yoId ? "propio" : ""} ${listo ? "listo" : ""}">
        <span class="quien">${nombreHtml(nombre, id === yoId ? " · TÚ" : "")}</span>
        <span class="numero">${valor}</span>
        <span class="estado">${listo ? "CONFIRMADO" : "CONTANDO"}</span>
      </div>`;
    })
    .join("");
}

/* ---------- Pájaros ---------- */
function mostrarPajaros(msg) {
  detenerTimers();
  conteoToken = msg.token || null;
  const esMando = esMandoFiesta() && !msg.aves;
  // La pantalla de la fiesta solo proyecta a los hámsters: no cuenta ni
  // muestra el panel de conteos, eso es cosa de los mandos.
  const esPantalla = esPantallaFiesta();

  $("contenido").innerHTML = `<div class="panel ${esMando ? "" : "panel-amplio"}">
    <div class="amplio-arriba">
      <p class="kicker">FASE 01 · OBSERVA</p>
      <h2 class="panel-titulo">¿CUÁNTOS HAY?</h2>
    </div>
    ${esMando
      ? '<div style="text-align:center;margin:2vh 0;color:var(--tinta-suave)">LOS HÁMSTERS APARECEN EN LA PANTALLA DEL ANFITRIÓN</div>'
      : '<div class="amplio-visual"><div class="campo-pajaros" id="campo-pajaros"></div></div>'}
    <div class="amplio-abajo">
      ${esMando || esPantalla ? "" : `<div class="stepper-respuesta">${STEPPER_HTML}<p class="pista stepper-ayuda">Cuenta los hámsters y responde cuanto antes.</p><button id="btn-responder" class="boton rojo">CONFIRMAR CUENTA</button></div>`}
      ${esPantalla ? '<p class="pista">Los mandos cuentan en su celular.</p>' : ""}
      <div class="barra-tiempo"><div id="barra-tiempo"></div></div>
    </div>
  </div>`;

  if (esMando) {
    barraTiempo(msg.limite || msg.duracion);
    return;
  }

  const campo = $("campo-pajaros");
  // Los tamaños vienen pensados para un campo de ~290px: crecen con el campo.
  const escalaCampo = Math.min(1.45, Math.max(1, (campo.clientWidth || 290) / 340));
  const aves = msg.aves.map((ave) => {
    const elemento = document.createElement("div");
    elemento.className = `pajaro${ave.salta ? " saltarin" : ""}`;
    elemento.style.width = `${ave.size * escalaCampo}px`;
    elemento.style.left = `${ave.x * 100}%`;
    elemento.style.top = `${ave.y * 100}%`;
    const pelajes = Math.max(1, Math.min(PELAJES.length, msg.nivel || 1));
    const [pelo, panza] = PELAJES[(ave.id * 5 + (msg.nivel || 1)) % pelajes];
    elemento.style.setProperty("--pelo", pelo);
    elemento.style.setProperty("--panza", panza);
    elemento.innerHTML = AVE_SVG;
    campo.appendChild(elemento);
    return { ...ave, elemento };
  });

  const inicio = performance.now();
  // La barrita marca todo el tiempo para responder, no solo la observación.
  const duracion = (msg.limite || msg.duracion) * 1000;
  const alto = campo.clientHeight || 300;
  const limitar = (valor, minimo, maximo) => Math.min(maximo, Math.max(minimo, valor));
  const barra = $("barra-tiempo");

  function fotograma(ahora) {
    aves.forEach((ave) => {
      if (!ave.salta) return;
      const tiempo = (ahora - inicio) / 1000 + ave.fase;
      const ciclos = Math.floor(tiempo / ave.periodo);
      const dentro = tiempo - ciclos * ave.periodo;
      const progreso = Math.min(1, dentro / ave.duracion);
      const elevacion = progreso < 1 ? Math.sin(Math.PI * progreso) : 0;
      const avance = ciclos + (progreso < 1 ? progreso : 1);
      const x = limitar(ave.x + ave.dx * avance, 0.06, 0.94);
      const y = limitar(
        ave.y + ave.dy * avance - ((ave.altura * escalaCampo) / alto) * elevacion,
        0.10,
        0.90
      );
      ave.elemento.style.left = `${x * 100}%`;
      ave.elemento.style.top = `${y * 100}%`;
      ave.elemento.style.transform =
        `translate(-50%, -50%) scaleY(${(1 - 0.16 * elevacion).toFixed(3)})`;
    });

    const transcurrido = Math.min(1, (ahora - inicio) / duracion);
    if (barra) barra.style.transform = `scaleX(${transcurrido})`;
    animacion = requestAnimationFrame(fotograma);
  }
  animacion = requestAnimationFrame(fotograma);

  if (!esPantalla) configurarStepperPajaros();
}

function configurarStepperPajaros() {
  stepperConteo(
    (valor) => enviar({ type: "bird_answer", count: valor, token: conteoToken }),
    (valor) => enviar({ type: "bird_tally", count: valor, token: conteoToken })
  );
}

function ocultarPajaros(msg) {
  conteoToken = msg.token || null;
  if (!esMandoFiesta() && msg.aves) return;

  // En la pantalla las aves NO desaparecen: solo cambia la fase y se
  // mantienen visibles mientras se cuenta. El éxito se mide por tiempo.
  if (!esMandoFiesta() && $("campo-pajaros")) {
    const kicker = document.querySelector("#contenido .kicker");
    if (kicker) kicker.textContent = "FASE 02 · RESPONDE";
    const titulo = document.querySelector("#contenido .panel-titulo");
    if (titulo) titulo.textContent = "¿CUÁNTOS HÁMSTERS HAY?";
    const ayuda = document.querySelector("#contenido .stepper-ayuda");
    if (ayuda) {
      ayuda.textContent =
        "Los hámsters siguen en pantalla. Usa los botones o flechas y confirma cuanto antes.";
    }
    let vivos = $("conteos-vivos");
    if (!vivos) {
      vivos = document.createElement("div");
      vivos.className = "conteos-vivos";
      vivos.id = "conteos-vivos";
      const respuesta = document.querySelector("#contenido .stepper-respuesta");
      if (respuesta) respuesta.after(vivos);
      else $("contenido").appendChild(vivos);
    }
    actualizarConteosVivos(msg.conteos || {}, msg.confirmados || []);
    const responder = $("btn-responder");
    if (responder) responder.focus();
    return;
  }

  detenerTimers();
  $("contenido").innerHTML = `<div class="panel">
    <p class="kicker">FASE 02 · RESPONDE</p>
    <h2 class="panel-titulo">¿CUÁNTOS HÁMSTERS HABÍA?</h2>
    ${STEPPER_HTML}
    <p class="pista stepper-ayuda">Usa los botones o las flechas arriba y abajo.</p>
    <button id="btn-responder" class="boton rojo">CONFIRMAR CUENTA</button>
    <p class="pista">Tienes ${msg.segundos} segundos. Suma más quien antes acierte.</p>
  </div>`;
  configurarStepperPajaros();
}

function mostrarPalabra(msg) {
  clearInterval(cuentaTimer);
  cuentaTimer = null;
  $("contenido").innerHTML = `<div class="panel panel-escena flash">
    <p class="kicker">FASE 02 · MEMORIZA</p>
    <div class="flash-palabra">${escapeHtml(msg.palabra)}</div>
    <p class="pista flash-pista">Solo un instante. Recuérdela.</p>
  </div>`;
}

function iniciarEscritura() {
  iniciarCanvasEscritura({
    kicker: "FASE 03 · ESCRIBE DE MEMORIA",
    pista: "Dibuja la letra con el dedo o el mouse. Puedes levantar y seguir.",
    tipoMensaje: "letter",
    terminoTexto: "PALABRA COMPLETA · ESPERANDO",
  });
}

function cajasPuntajes(brainAges, ganador, desglose) {
  return Object.keys(marcador.pajaros || {})
    .map((id) => {
      const gana = id === ganador && !modoPractica;
      const dato = desglose[id];
      const detalle =
        dato && dato.brain_age != null
          ? `<div class="desglose">${textoDesglose(dato)}</div>`
          : "";
      return `<div class="puntaje ${gana ? "ganador" : ""}">
        <div class="numero">${brainAges[id] ?? 0}</div>
        ${detalle}
        <div class="quien">${nombreHtml(jugadores[id] || "JUGADOR", id === yoId ? " · TÚ" : "")}</div>
      </div>`;
    })
    .join("");
}

function mostrarResultadoRonda(msg) {
  actualizarMarcador(msg.marcador);
  const ganador = modoPractica ? null : msg.ganador;
  const titulo = modoPractica
    ? "RONDA COMPLETADA"
    : ganador
      ? ganador === yoId
        ? "¡GANASTE LA RONDA!"
        : `GANA ${jugadores[ganador] || "EL RIVAL"}`
      : "EMPATE · OTRA RONDA";

  const protagonista =
    msg.juego === "pajaros"
      ? `<div class="conteo-final">
          <span class="conteo-final-etiqueta">HABÍA</span>
          <div class="conteo-final-numero" id="conteo-final-numero">${msg.esperado ?? "?"}</div>
          <span class="conteo-final-unidad">HÁMSTERS</span>
        </div>`
      : `<div class="palabra-final">
          <span class="conteo-final-etiqueta">LA PALABRA ERA</span>
          <div class="palabra-final-texto">${escapeHtml(msg.palabra || "")}</div>
        </div>`;

  $("contenido").innerHTML = `<div class="panel resultado">
    <div class="resultado-cabecera">
      <p class="kicker">${msg.juego === "pajaros" ? "INFORME 01" : "INFORME 02"} · RONDA ${String(msg.nivel || 0).padStart(2, "0")}</p>
      <h2>${titulo}</h2>
      ${ganador ? '<div class="sello-resultado">GANADOR</div>' : ""}
    </div>
    ${protagonista}
    <div class="puntajes">${cajasPuntajes(msg.brain_age || {}, ganador, msg.desglose || {})}</div>
    <p class="resultado-pie">HÁMSTERS ${msg.marcador.pajaros[yoId] || 0} · PALABRAS ${msg.marcador.escritura[yoId] || 0}</p>
  </div>`;
}

function mostrarFinal(msg) {
  detenerTimers();
  actualizarMarcador(msg.marcador);
  const gane = msg.ganador === yoId;
  const cajas = Object.keys(msg.marcador.pajaros)
    .map(
      (id) => `<div class="puntaje ${id === msg.ganador ? "ganador" : ""}">
        <div class="numero">${msg.marcador.pajaros[id] || 0} / ${msg.marcador.escritura[id] || 0}</div>
        <div class="quien">${nombreHtml(jugadores[id] || "JUGADOR")}</div>
      </div>`
    )
    .join("");

  $("contenido").innerHTML = `<div class="panel diploma">
    <div class="sello-grande">K</div>
    <p class="kicker">INFORME FINAL · LABORATORIO DE ATENCIÓN</p>
    <b>${gane ? "¡ERES EL CAMPEÓN!" : `GANADOR: ${escapeHtml(msg.nombre_ganador)}`}</b>
    <p class="pista">${gane ? "Atención, memoria y pulso: todo en orden." : "Buena tentativa. Vuelve a intentarlo."}</p>
    <div class="puntajes" style="text-align:left">${cajas}</div>
    <div class="diploma-acciones">
      ${
        yoId === hostId
          ? '<button class="boton oscuro chico" id="btn-otra">OTRA PARTIDA</button>'
          : ""
      }
      <button class="boton rojo chico" id="btn-volver">VOLVER AL INICIO</button>
    </div>
  </div>`;

  const otra = $("btn-otra");
  if (otra) otra.addEventListener("click", () => enviar({ type: "restart" }));
  $("btn-volver").addEventListener("click", () => volverAlInicio());
}

registrarMensajes({
  round_start: iniciarRonda,
  birds_countdown: (msg) =>
    mostrarCuentaPrevia(msg, {
      kicker: "FASE 01 · PREPARA LA VISTA",
      pie: "LOS HÁMSTERS APARECERÁN DESPUÉS",
      glifo: "◎",
    }),
  birds_show: (msg) => {
    if (esMandoFiesta()) {
      mostrarEspera("MIRA LA PANTALLA", "¡A CONTAR!", "Los hámsters aparecen en la pantalla del anfitrión.");
    } else {
      mostrarPajaros(msg);
    }
  },
  birds_hide: (msg) => {
    if (esPantallaFiesta()) {
      mostrarEspera("PANTALLA · ESPECTADOR", "ESPERANDO RESPUESTAS", "Los mandos están contando.");
    } else {
      ocultarPajaros(msg);
    }
  },
  bird_tally: (msg) => actualizarConteosVivos(msg.conteos || {}, msg.confirmados || []),
  word_countdown: (msg) => mostrarCuentaPrevia(msg),
  word_show: (msg) => {
    if (esMandoFiesta()) {
      mostrarEspera("MIRA LA PANTALLA", "MEMORIZA", "La palabra aparece solo en la pantalla del anfitrión.");
    } else {
      mostrarPalabra(msg);
    }
  },
  word_write: (msg) => {
    if (esPantallaFiesta()) {
      mostrarEspera("PANTALLA · ESPECTADOR", "ESCRIBIENDO…", "Los mandos están escribiendo de memoria.");
    } else {
      iniciarEscritura(msg);
    }
  },
  letter_feedback: (msg) => alFeedback?.(msg),
  word_done: (msg) => {
    alTerminar?.(msg);
    aviso(msg.automaticas ? `PALABRA COMPLETA · ${msg.automaticas} AUTOMÁTICA(S)` : "PALABRA COMPLETA · ESPERANDO");
  },
  round_result: (msg) => {
    if (!resultadoSoloEnPantalla()) mostrarResultadoRonda(msg);
  },
  round_feedback: (msg) => {
    if (msg.pid !== yoId) return;
    mostrarResultadoPrivado(`${NOMBRES[msg.juego] || "RONDA"} · TU RESULTADO`, msg.acepta);
  },
  minigame_result: (msg) => aviso(`${msg.nombre} SE LLEVA ${nombreJuego(msg.juego)}`),
  tiebreak_start: () => aviso("EMPATE · DESEMPATE AL AZAR"),
  match_over: (msg) => {
    if (secuenciaIndividual) return;
    if (modoFiesta) aviso("JUEGO TERMINADO · PODIO");
    else mostrarFinal(msg);
  },
});
