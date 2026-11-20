/* Konitive — cliente web */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);

  let ws = null;
  let yoId = null;
  let hostId = null;
  let codigo = null;
  let jugadores = {};
  let marcador = { pajaros: {}, escritura: {}, necesario: 3 };
  let modoPractica = false;
  let modoCajas = false;
  let modoOperaciones = false;
  let modoFiesta = false;
  let secuenciaIndividual = false;
  let juegosIndividuales = new Set();
  let esPantalla = false;
  let esMando = false;
  let juegoFiesta = null;
  let inviteUrl = "";
  let podioActual = [];
  let ultimaPila = [];
  let animacion = null;
  let cuentaTimer = null;
  let avisoTimer = null;
  let teclaConteo = null;
  let conteoToken = null;
  // La pantalla de la fiesta no recibe interacción del host: wake lock para
  // que el SO no oscurezca el proyector mientras llegan rondas por WebSocket.
  let wakeLock = null;
  let wakeLockPidiendo = false;
  let conteosPajarosVivos = {};
  let confirmadosPajaros = [];
  let ultimoShowMini = {};
  // MENOR A MAYOR: casillas tocadas que esperan la confirmación del servidor.
  let pendientesMenor = [];
  let rondaClasica = 1;

  const JUEGOS_MINI = [
    "stroop", "triangulos", "relojes", "menor", "memoria", "vuelto", "silabas", "ppt",
  ];
  const NOMBRES_MINI = {
    stroop: "STROOP",
    triangulos: "TRIÁNGULOS",
    relojes: "RELOJES",
    menor: "MENOR A MAYOR",
    memoria: "MEMORIA",
    vuelto: "DAR VUELTO",
    silabas: "SÍLABAS",
    ppt: "PIEDRA · PAPEL · TIJERA",
  };
  // Fiesta: juegos que el anfitrión encadena, con rondas y dificultad propias.
  // «rastreo» es un juego dedicado (no un minijuego) y «ppt» cierra la lista.
  const JUEGOS_FIESTA = [
    "pajaros", "escritura", "cajas", "operaciones",
    ...JUEGOS_MINI.filter((j) => j !== "ppt"), "rastreo", "ppt",
  ];
  const NOMBRES_FIESTA = {
    pajaros: "HÁMSTERS", escritura: "PALABRAS", cajas: "CAJAS", operaciones: "OPERACIONES",
    rastreo: "RASTREO DE HÁMSTERS",
    ...NOMBRES_MINI,
  };
  const DIFICULTADES = [["facil", "FÁCIL"], ["normal", "NORMAL"], ["dificil", "DIFÍCIL"]];
  const RONDAS_FIESTA = { defecto: 5, min: 1, max: 20 };
  const listaFiesta = new Set();
  const ajustesFiesta = Object.fromEntries(
    JUEGOS_FIESTA.map((j) => [j, { rondas: RONDAS_FIESTA.defecto, dificultad: "facil" }])
  );

  const COLOR_HEX = {
    rojo: "#d33827",
    azul: "#1d4ed8",
    verde: "#246b58",
    amarillo: "#a87300",
  };
  const SUFIJOS_MINI = [
    "_countdown", "_show", "_hide", "_write", "_feedback", "_done", "_result", "_over",
  ];

  // Hámster pixel-art de frente (12×11). O borde, F pelo, B panza, E ojo,
  // P rosa (orejas y mejillas), N nariz. Los colores salen de --pelo y --panza.
  const HAMSTER_PIXELES = [
    "..OO....OO..",
    ".OPPO..OPPO.",
    ".OFFFOOFFFO.",
    "OFFFFFFFFFFO",
    "OFEFFFFFFEFO",
    "OFPFFNNFFPFO",
    "OFFFBBBBFFFO",
    "OFFBBBBBBFFO",
    "OFFBBBBBBFFO",
    ".OFFBBBBFFO.",
    "..OOO..OOO..",
  ];
  const HAMSTER_COLOR = { O: "var(--tinta)", E: "var(--tinta)", N: "#e86a7a", P: "#f4a3b4", F: "var(--pelo)", B: "var(--panza)" };
  const AVE_SVG =
    '<svg viewBox="0 0 12 11" shape-rendering="crispEdges" aria-hidden="true">' +
    HAMSTER_PIXELES.flatMap((fila, y) =>
      [...fila].map((c, x) => (HAMSTER_COLOR[c] ? `<rect x="${x}" y="${y}" width="1.02" height="1.02" fill="${HAMSTER_COLOR[c]}"/>` : ""))
    ).join("") +
    "</svg>";
  // Pelajes [pelo, panza]. Nivel 1: todos dorados; cada nivel suma un pelaje.
  const PELAJES = [
    ["#e3a24f", "#fbe6c4"], ["#9aa1a8", "#eef0f2"], ["#8a5a3b", "#ecd3b6"],
    ["#f3ece0", "#ffffff"], ["#c9733a", "#f7d9b3"], ["#4a4540", "#d8d0c4"],
  ];
  const LADOS_RASTREO = ["izquierda", "derecha", "arriba", "abajo"];
  const CLASES_ENTRADA = LADOS_RASTREO.map((lado) => `rastreo-entrada-${lado}`);

  // Un desplazamiento a la vez: animar() cancela el temporizador anterior y
  // detenerTimers() retira cualquier clase que haya quedado sobre el tablero.
  const AnimationController = {
    temporizador: null,
    detener() {
      if (this.temporizador) clearTimeout(this.temporizador);
      this.temporizador = null;
      $("contenido")?.querySelectorAll(".rastreo-casilla").forEach((celda) => {
        CLASES_ENTRADA.forEach((clase) => celda.classList.remove(clase));
      });
    },
    animar(movimiento) {
      this.detener();
      if (!movimiento || !LADOS_RASTREO.includes(movimiento.lado)) return;
      const tablero = $("rastreo-tablero");
      if (!tablero) return;
      const duracion = Math.max(0, Number(movimiento.duracion) || 0);
      tablero.style.setProperty("--rastreo-duracion", `${duracion}s`);
      const linea = Number(movimiento.linea);
      const clase = `rastreo-entrada-${movimiento.lado}`;
      const horizontal = movimiento.lado === "izquierda" || movimiento.lado === "derecha";
      const afectadas = [...tablero.querySelectorAll(".rastreo-casilla")].filter((_, i) =>
        horizontal ? Math.floor(i / 4) === linea : i % 4 === linea
      );
      afectadas.forEach((celda) => celda.classList.add(clase));
      this.temporizador = setTimeout(() => {
        afectadas.forEach((celda) => celda.classList.remove(clase));
        this.temporizador = null;
      }, duracion * 1000);
    },
  };

  /* ---------- Utilidades ---------- */
  // Solo la pantalla del anfitrión necesita blockers de suspensión: los mandos
  // están tocando el celular constantemente. Se pide al entrar en juego/podio
  // y se suelta al volver al lobby o al inicio. Si el navegador no lo soporta
  // o lo rechaza, la partida sigue igual.
  async function actualizarWakeLock() {
    const activa = document.querySelector(".pantalla.activa")?.id;
    const debeMantener = esPantallaFiesta() &&
      (activa === "pantalla-juego" || activa === "pantalla-podio");

    if (!debeMantener) {
      if (wakeLock) {
        const anterior = wakeLock;
        wakeLock = null;
        try { await anterior.release(); } catch (_) {}
      }
      return;
    }
    if (wakeLock || wakeLockPidiendo || !("wakeLock" in navigator)) return;

    wakeLockPidiendo = true;
    try {
      const lock = await navigator.wakeLock.request("screen");
      // El estado puede haber cambiado mientras se concedía el permiso.
      const ahora = document.querySelector(".pantalla.activa")?.id;
      if (!esPantallaFiesta() ||
          (ahora !== "pantalla-juego" && ahora !== "pantalla-podio")) {
        await lock.release();
      } else {
        wakeLock = lock;
        lock.addEventListener("release", () => {
          if (wakeLock === lock) wakeLock = null;
        });
      }
    } catch (_) {
      // Sin soporte, sin contexto seguro o permiso denegado: no es fatal.
    } finally {
      wakeLockPidiendo = false;
    }
  }

  function mostrar(id) {
    document.querySelectorAll(".pantalla").forEach((p) => p.classList.remove("activa"));
    $(id).classList.add("activa");
    // Fuera del inicio siempre hay forma de volver.
    $("btn-salir").hidden = id === "pantalla-inicio";
    // Al entrar, la grilla de juegos siempre arranca desde arriba.
    const selector = $("selector-individual");
    if (id === "pantalla-individual" && selector) selector.scrollTop = 0;
    // La franja de avance vive solo mientras se juega; al salir se limpia.
    const vivo = $("progreso-vivo");
    if (vivo && id !== "pantalla-juego") {
      vivo.hidden = true;
      vivo.innerHTML = "";
    }
    actualizarWakeLock();
  }

  // Nombre que se recorta con «…» si no cabe; el sufijo («(tú)», «· TÚ») nunca salta de línea.
  const nombreHtml = (nombre, sufijo = "") =>
    `<span class="nombre-txt">${escapeHtml(nombre)}</span>` +
    (sufijo ? `<span class="nombre-sufijo">${sufijo}</span>` : "");

  function escapeHtml(texto) {
    return String(texto).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }

  function aviso(texto) {
    const el = $("aviso");
    el.textContent = texto;
    el.classList.add("visible");
    clearTimeout(avisoTimer);
    avisoTimer = setTimeout(() => el.classList.remove("visible"), 2800);
  }

  function actualizarRecordCajas() {
    const record = Number(localStorage.getItem("konitive_cajas_record") || 0);
    $("record-cajas").textContent = record
      ? `MEJOR MARCA EN CAJAS: ${record} PUNTOS`
      : "";
  }

  function actualizarRecordOperaciones() {
    const record = Number(localStorage.getItem("konitive_operaciones_record") || 0);
    $("record-operaciones").textContent = record
      ? `MEJOR MARCA EN OPERACIONES: ${record} PUNTOS`
      : "";
  }

  async function prepararInvitacion(codigoSala) {
    let origen = location.origin;
    if (["localhost", "127.0.0.1", "::1"].includes(location.hostname)) {
      try {
        const respuesta = await fetch("/api/red");
        const datos = await respuesta.json();
        if (datos.ip) origen = `${location.protocol}//${datos.ip}:${datos.puerto}`;
      } catch (error) {
        console.warn("No se pudo consultar la IP local", error);
      }
    }
    inviteUrl = `${origen}/?sala=${codigoSala}`;
    const qr = $("qr-sala");
    if (qr) qr.src = `/api/qr?texto=${encodeURIComponent(inviteUrl)}`;
  }

  function detenerTimers() {
    AnimationController.detener();
    if (animacion) cancelAnimationFrame(animacion);
    animacion = null;
    clearInterval(cuentaTimer);
    cuentaTimer = null;
    if (teclaConteo) document.removeEventListener("keydown", teclaConteo);
    teclaConteo = null;
    conteoToken = null;
    window.__konitiveFeedback = null;
    window.__konitiveTermino = null;
  }

  function enviar(objeto) {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(objeto));
  }

  function conectar(mensajeInicial) {
    if (ws && ws.readyState <= 1) ws.close();
    const protocolo = location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(`${protocolo}//${location.host}/ws`);
    ws = socket;
    ws.onopen = () => enviar(mensajeInicial);
    ws.onmessage = (evento) => {
      try {
        manejar(JSON.parse(evento.data));
      } catch (error) {
        console.error("Mensaje inválido", error);
      }
    };
    // onclose llega después de que el cliente cierra a propósito (salir o
    // reconectar): solo es una pérdida real si este sigue siendo el socket activo.
    ws.onclose = () => {
      if (ws === socket) aviso("Se perdió la conexión con el servidor");
    };
    ws.onerror = () => {
      $("error-inicio").textContent = "No se pudo conectar con el servidor";
    };
  }

  function volverAlInicio(mensaje) {
    detenerTimers();
    enviar({ type: "leave" });
    if (ws) ws.close();
    ws = null;
    yoId = hostId = codigo = null;
    jugadores = {};
    modoPractica = false;
    modoCajas = false;
    modoOperaciones = false;
    modoFiesta = false;
    secuenciaIndividual = false;
    esPantalla = false;
    esMando = false;
    juegoFiesta = null;
    podioActual = [];
    $("error-inicio").textContent = "";
    $("error-invitado").textContent = "";
    $("codigo").value = "";
    $("lobby-control").hidden = true;
    $("podio-lobby").innerHTML = "";
    mostrar("pantalla-inicio");
    if (mensaje) aviso(mensaje);
  }

  /* ---------- Inicio ---------- */
  $("btn-crear").addEventListener("click", () => {
    const nombre = $("nombre").value.trim();
    if (!nombre) {
      $("error-inicio").textContent = "Escribe tu nombre para abrir la sala";
      return;
    }
    $("error-inicio").textContent = "";
    conectar({ type: "create", nombre });
  });

  $("btn-unirse").addEventListener("click", () => {
    const nombre = $("nombre").value.trim();
    const codigoSala = $("codigo").value.trim().toUpperCase();
    if (!nombre || codigoSala.length !== 5) {
      $("error-inicio").textContent = "Pon tu nombre y un código de 5 caracteres";
      return;
    }
    $("error-inicio").textContent = "";
    conectar({ type: "join", nombre, codigo: codigoSala });
  });

  $("btn-individual").addEventListener("click", () => {
    $("error-inicio").textContent = "";
    $("error-individual").textContent = "";
    actualizarSelectorIndividual();
    mostrar("pantalla-individual");
  });

  function actualizarSelectorIndividual() {
    $("selector-individual")
      .querySelectorAll("button[data-juego]")
      .forEach((boton) => {
        boton.setAttribute("aria-pressed", juegosIndividuales.has(boton.dataset.juego) ? "true" : "false");
      });
    $("btn-empezar-individual").disabled = juegosIndividuales.size === 0;
  }

  $("selector-individual").querySelectorAll("button[data-juego]").forEach((boton) => {
    boton.addEventListener("click", () => {
      const juego = boton.dataset.juego;
      if (juegosIndividuales.has(juego)) juegosIndividuales.delete(juego);
      else juegosIndividuales.add(juego);
      actualizarSelectorIndividual();
    });
  });

  $("btn-todos").addEventListener("click", () => {
    juegosIndividuales = new Set([
      "pajaros", "escritura", "cajas", "operaciones", ...JUEGOS_MINI,
    ]);
    actualizarSelectorIndividual();
  });

  $("btn-ninguno").addEventListener("click", () => {
    juegosIndividuales = new Set();
    actualizarSelectorIndividual();
  });

  $("btn-empezar-individual").addEventListener("click", () => {
    if (!juegosIndividuales.size) return;
    const nombre = $("nombre").value.trim() || "Paciente";
    $("error-individual").textContent = "";
    conectar({ type: "individual", nombre, juegos: [...juegosIndividuales] });
  });

  $("btn-fiesta").addEventListener("click", () => {
    const nombre = $("nombre").value.trim();
    if (!nombre) {
      $("error-inicio").textContent = "Escribe tu nombre para abrir la fiesta";
      return;
    }
    $("error-inicio").textContent = "";
    conectar({ type: "fiesta", nombre });
  });

  $("btn-unirme").addEventListener("click", () => {
    const nombre = $("nombre-invitado").value.trim();
    const codigoSala = $("codigo-invitado").textContent.trim().toUpperCase();
    if (!nombre || codigoSala.length !== 5) {
      $("error-invitado").textContent = "Pon tu nombre para unirte a la sala";
      return;
    }
    $("error-invitado").textContent = "";
    conectar({ type: "join", nombre, codigo: codigoSala });
  });

  $("nombre-invitado").addEventListener("keydown", (e) => {
    if (e.key === "Enter") $("btn-unirme").click();
  });

  $("btn-copiar").addEventListener("click", async () => {
    if (!inviteUrl) return;
    try {
      await navigator.clipboard.writeText(inviteUrl);
      aviso("ENLACE COPIADO");
    } catch (error) {
      aviso(inviteUrl);
    }
  });

  function pintarListaFiesta() {
    $("lista-fiesta").innerHTML = JUEGOS_FIESTA.map((juego) => {
      const activo = listaFiesta.has(juego);
      const { rondas, dificultad } = ajustesFiesta[juego];
      return `<div class="fila-juego ${activo ? "activa" : ""}" data-fila="${juego}">
        <button type="button" class="fila-juego-nombre" data-alternar="${juego}" aria-pressed="${activo}">${NOMBRES_FIESTA[juego]}</button>
        <div class="fila-juego-rondas" aria-label="Rondas de ${NOMBRES_FIESTA[juego]}">
          <button type="button" data-rondas="${juego}" data-delta="-1" aria-label="Menos rondas" ${activo ? "" : "disabled"}>−</button>
          <output>${rondas}</output>
          <button type="button" data-rondas="${juego}" data-delta="1" aria-label="Más rondas" ${activo ? "" : "disabled"}>+</button>
        </div>
        <select data-dificultad="${juego}" aria-label="Dificultad de ${NOMBRES_FIESTA[juego]}" ${activo ? "" : "disabled"}>
          ${(juego === "rastreo" ? [...DIFICULTADES, ["experto", "EXPERTO"]] : DIFICULTADES).map(([valor, texto]) => `<option value="${valor}" ${valor === dificultad ? "selected" : ""}>${texto}</option>`).join("")}
        </select>
      </div>`;
    }).join("");
    actualizarBotonFiesta();
  }

  function actualizarBotonFiesta() {
    const mandos = Object.keys(jugadores).filter((id) => id !== hostId).length;
    const boton = $("btn-iniciar-fiesta");
    boton.disabled = mandos < 1 || listaFiesta.size === 0;
    boton.textContent = listaFiesta.size
      ? `EMPEZAR · ${listaFiesta.size} JUEGO${listaFiesta.size === 1 ? "" : "S"}`
      : "ELIGE AL MENOS UN JUEGO";
    $("btn-fin-fiesta").disabled = mandos < 1;
  }

  $("lista-fiesta").addEventListener("click", (e) => {
    const alternar = e.target.closest("[data-alternar]");
    const rondas = e.target.closest("[data-rondas]");
    if (alternar) {
      const juego = alternar.dataset.alternar;
      if (listaFiesta.has(juego)) listaFiesta.delete(juego);
      else listaFiesta.add(juego);
      pintarListaFiesta();
    } else if (rondas && !rondas.disabled) {
      const ajuste = ajustesFiesta[rondas.dataset.rondas];
      ajuste.rondas = Math.min(
        RONDAS_FIESTA.max,
        Math.max(RONDAS_FIESTA.min, ajuste.rondas + Number(rondas.dataset.delta))
      );
      rondas.parentElement.querySelector("output").textContent = ajuste.rondas;
    }
  });

  $("lista-fiesta").addEventListener("change", (e) => {
    const juego = e.target.dataset.dificultad;
    if (juego) ajustesFiesta[juego].dificultad = e.target.value;
  });

  $("btn-fiesta-todos").addEventListener("click", () => {
    JUEGOS_FIESTA.forEach((j) => listaFiesta.add(j));
    pintarListaFiesta();
  });
  $("btn-fiesta-ninguno").addEventListener("click", () => {
    listaFiesta.clear();
    pintarListaFiesta();
  });

  $("btn-iniciar-fiesta").addEventListener("click", () => {
    const juegos = JUEGOS_FIESTA.filter((j) => listaFiesta.has(j));
    if (!juegos.length) return;
    const ajustes = Object.fromEntries(juegos.map((j) => [j, ajustesFiesta[j]]));
    enviar({ type: "start", juegos, ajustes });
  });

  pintarListaFiesta();

  $("btn-fin-fiesta").addEventListener("click", () => enviar({ type: "finish_fiesta" }));

  $("nombre").addEventListener("keydown", (e) => {
    if (e.key === "Enter") $("btn-crear").click();
  });
  $("codigo").addEventListener("keydown", (e) => {
    if (e.key === "Enter") $("btn-unirse").click();
  });
  $("btn-empezar").addEventListener("click", () => enviar({ type: "start" }));
  $("btn-salir").addEventListener("click", () => {
    const enJuego = ["pantalla-juego", "pantalla-mando", "pantalla-podio"].some((id) =>
      $(id).classList.contains("activa")
    );
    if (!enJuego) return volverAlInicio();
    const dialogo = $("dialogo-salir");
    dialogo.returnValue = "";
    dialogo.showModal();
  });
  // Con el diálogo abierto, las teclas no llegan a los controles del juego.
  window.addEventListener(
    "keydown",
    (e) => { if ($("dialogo-salir").open) e.stopImmediatePropagation(); },
    true
  );
  // Esc o "SEGUIR JUGANDO" lo cierran sin salir; solo "SALIR" abandona.
  $("dialogo-salir").addEventListener("close", (e) => {
    if (e.target.returnValue === "si") volverAlInicio();
  });

  // El navegador libera el wake lock al ocultar la pestaña; al volver se
  // reclama solo si la pantalla sigue siendo la del anfitrión en juego/podio.
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) actualizarWakeLock();
  });

  /* ---------- Sonido (sintetizado con WebAudio, sin archivos) ---------- */
  let audio = null;
  let sonidoActivo = true;
  try { sonidoActivo = localStorage.getItem("konitive-sonido") !== "off"; } catch (_) {}

  function tono(frecuencia, duracion, { tipo = "triangle", volumen = 0.08, hasta = null, retraso = 0 } = {}) {
    if (!sonidoActivo) return;
    try {
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      if (audio.state === "suspended") audio.resume();
      const t = audio.currentTime + retraso;
      const osc = audio.createOscillator();
      const gan = audio.createGain();
      osc.type = tipo;
      osc.frequency.setValueAtTime(frecuencia, t);
      if (hasta) osc.frequency.exponentialRampToValueAtTime(hasta, t + duracion);
      gan.gain.setValueAtTime(0.0001, t);
      gan.gain.exponentialRampToValueAtTime(volumen, t + 0.01);
      gan.gain.exponentialRampToValueAtTime(0.0001, t + duracion);
      osc.connect(gan).connect(audio.destination);
      osc.start(t);
      osc.stop(t + duracion + 0.02);
    } catch (_) {
      /* sin audio disponible: el juego sigue en silencio */
    }
  }
  const notas = (lista, paso = 0.09, opciones = {}) =>
    lista.forEach((f, i) => tono(f, paso * 1.6, { ...opciones, retraso: i * paso }));

  const SONIDOS = {
    click: () => tono(880, 0.04, { tipo: "square", volumen: 0.035 }),
    tic: () => tono(660, 0.07, { volumen: 0.07 }),
    aparece: () => tono(480, 0.12, { tipo: "sine", hasta: 960, volumen: 0.07 }),
    bien: () => notas([660, 990], 0.08),
    mal: () => tono(240, 0.22, { tipo: "square", hasta: 140, volumen: 0.05 }),
    conectar: () => notas([523, 784], 0.08, { tipo: "sine" }),
    salida: () => notas([523, 392], 0.1, { tipo: "sine" }),
    inicio: () => notas([523, 659, 784], 0.08),
    resultado: () => notas([784, 988], 0.07, { tipo: "sine" }),
    podio: () => notas([784, 988, 1175], 0.1),
    fanfarria: () => notas([523, 659, 784, 1047], 0.11),
  };
  const sonar = (nombre) => SONIDOS[nombre]?.();

  function sonidoMensaje(msg) {
    const t = msg.type || "";
    const mio = (msg.jugadores || {})[yoId];
    if (["room_created", "room_joined", "player_joined"].includes(t)) sonar("conectar");
    else if (["player_left", "opponent_left"].includes(t)) sonar("salida");
    else if (t === "error") sonar("mal");
    else if (["match_start", "individual_game_start", "round_start", "tiebreak_start"].includes(t)) sonar("inicio");
    else if (t.endsWith("_show")) sonar("aparece");
    else if (t.endsWith("_feedback")) sonar(msg.aceptada ? "bien" : "mal");
    else if (t === "round_result") sonar(msg.ganador === yoId ? "bien" : msg.ganador ? "mal" : "resultado");
    else if (t.endsWith("_result")) sonar(mio && "acierto" in mio ? (mio.acierto ? "bien" : "mal") : "resultado");
    else if (t === "podium_update") sonar("podio");
    else if (t === "podium_final" || t === "match_over" || t.endsWith("_over") || t === "individual_summary") sonar("fanfarria");
  }

  // Un clic suave en cada botón (incluidos los generados por los juegos).
  document.addEventListener(
    "pointerdown",
    (e) => {
      const boton = e.target.closest("button, select");
      if (boton && !boton.disabled) sonar("click");
    },
    true
  );
  // Flechas y Enter de los contadores también suenan.
  document.addEventListener(
    "keydown",
    (e) => {
      if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Enter"].includes(e.key)) sonar("click");
    },
    true
  );
  // Tic en cada número de las cuentas regresivas (todas usan #cuenta-previa-numero).
  let ultimoTic = null;
  new MutationObserver(() => {
    const el = document.getElementById("cuenta-previa-numero");
    const texto = el ? el.textContent : null;
    if (texto && texto !== ultimoTic) sonar("tic");
    ultimoTic = texto;
  }).observe(document.getElementById("app"), { childList: true, subtree: true, characterData: true });

  function pintarBotonSonido() {
    const b = $("btn-sonido");
    b.textContent = sonidoActivo ? "♪ ON" : "♪ OFF";
    b.setAttribute("aria-pressed", String(sonidoActivo));
    b.setAttribute("aria-label", sonidoActivo ? "Sonido activado" : "Sonido desactivado");
  }
  $("btn-sonido").addEventListener("click", () => {
    sonidoActivo = !sonidoActivo;
    try { localStorage.setItem("konitive-sonido", sonidoActivo ? "on" : "off"); } catch (_) {}
    pintarBotonSonido();
    sonar("click");
  });
  pintarBotonSonido();

  /* ---------- Lobby y marcador ---------- */
  function actualizarLobby() {
    const entradas = Object.entries(jugadores);
    const capacidad = modoFiesta ? 9 : 2;
    const huecos = Math.max(0, capacidad - entradas.length);
    // En fiesta la pantalla no juega: se muestra aparte, nunca como participante.
    const participantes = modoFiesta
      ? entradas.filter(([id]) => id !== hostId)
      : entradas;
    const fichaPantalla = modoFiesta
      ? `<div class="ficha-pantalla"><span class="rol">PANTALLA</span>` +
        `${nombreHtml(jugadores[hostId] || "ANFITRIÓN", hostId === yoId ? " (tú)" : "")}</div>`
      : "";

    $("lista-jugadores").innerHTML =
      fichaPantalla +
      participantes
        .map(
          ([id, nombre], i) => {
            const rol = modoFiesta ? "MANDO" : id === hostId ? "ANFITRIÓN" : "INVITADO";
            return `<div class="ficha-jugador"><span class="num">0${i + 1}</span>` +
              `<span class="conectado" title="Conectado"></span>` +
              `${nombreHtml(nombre, id === yoId ? " (tú)" : "")}` +
              `<span class="rol">${rol}</span></div>`;
          }
        )
        .join("") +
      (modoFiesta
        ? ""
        : Array.from(
            { length: huecos },
            (_, i) =>
              `<div class="ficha-jugador vacio"><span class="num">0${entradas.length + i + 1}</span>ESPERANDO…</div>`
          ).join(""));

    const listaMando = $("mando-lista");
    if (listaMando) {
      listaMando.innerHTML =
        fichaPantalla +
        participantes
          .map(
            ([id, nombre]) =>
              `<div class="ficha-jugador"><span class="conectado"></span>` +
              `${nombreHtml(nombre, id === yoId ? " (tú)" : "")}` +
              `<span class="rol">MANDO</span></div>`
          )
          .join("");
    }

    const mandos = participantes.length;
    if (modoFiesta) {
      $("btn-empezar").hidden = true;
      $("lobby-control").hidden = yoId !== hostId;
      $("lobby-grid").classList.toggle("con-control", yoId === hostId);
      actualizarBotonFiesta();
      $("estado-lobby").textContent = mandos
        ? `${mandos} mando(s) conectado(s). Elige los juegos y pulsa EMPEZAR.`
        : "Esperando mandos: escanea el QR con el celular.";
    } else {
      $("lobby-control").hidden = true;
      $("lobby-grid").classList.remove("con-control");
      const listo = entradas.length === 2;
      const boton = $("btn-empezar");
      boton.hidden = false;
      boton.disabled = !(listo && yoId === hostId);
      boton.textContent = !listo
        ? "ESPERANDO AL RIVAL…"
        : yoId === hostId
          ? "INICIAR EXPERIMENTO"
          : "EL ANFITRIÓN INICIA…";
      $("estado-lobby").textContent = listo
        ? "Los dos están aquí. Ya pueden empezar."
        : "Escanea el QR o comparte el código para que tu amigo se una.";
    }
  }

  function actualizarMarcador(datos) {
    if (datos) marcador = datos;
    if (esMandoFiesta()) {
      // El celular solo ve lo suyo: nunca el marcador de los otros mandos.
      const bruto = (marcador[juegoFiesta] || {})[yoId];
      const dato = bruto && typeof bruto === "object" ? bruto : {};
      const puntos = dato.puntos ?? bruto ?? 0;
      const ronda = dato.ronda ?? (juegoFiesta === "pajaros" ? rondaClasica : 0);
      $("marcador-0").innerHTML =
        `<div class="nombre">${nombreHtml(jugadores[yoId] || "TÚ", " · TÚ")}</div>` +
        `<div class="detalle">PUNTOS <b>${puntos}</b></div>`;
      $("marcador-1").innerHTML =
        `<div class="nombre">RONDA ${ronda}</div>` +
        `<div class="detalle">ACIERTOS <b>${dato.aciertos ?? 0}</b></div>`;
      return;
    }
    if (marcador.cajas) {
      const ids = Object.keys(marcador.cajas);
      const id = ids.includes(yoId) ? yoId : ids[0];
      const dato = marcador.cajas[id] || {};
      const nombre = jugadores[id] || marcador.nombre || "JUGADOR";
      $("marcador-0").innerHTML =
        `<div class="nombre">${nombreHtml(nombre, id === yoId ? " (tú)" : "")}</div>` +
        `<div class="detalle">PUNTOS <b>${dato.puntos || 0}</b></div>`;
      $("marcador-1").innerHTML =
        `<div class="nombre">RONDA ${dato.ronda || 0} / ${marcador.necesario || 10}</div>` +
        `<div class="detalle">ACIERTOS <b>${dato.aciertos || 0}</b> · RACHA <b>${dato.racha || 0}</b>` +
        `${ids.length > 1 ? ` · <b>${ids.length}</b> JUGADORES` : ""}</div>`;
      return;
    }
    if (marcador.operaciones) {
      const ids = Object.keys(marcador.operaciones);
      const id = ids.includes(yoId) ? yoId : ids[0];
      const dato = marcador.operaciones[id] || {};
      const nombre = jugadores[id] || marcador.nombre || "JUGADOR";
      $("marcador-0").innerHTML =
        `<div class="nombre">${nombreHtml(nombre, id === yoId ? " (tú)" : "")}</div>` +
        `<div class="detalle">PUNTOS <b>${dato.puntos || 0}</b></div>`;
      $("marcador-1").innerHTML =
        `<div class="nombre">RONDA ${dato.ronda || 0} / ${marcador.necesario || 10}</div>` +
        `<div class="detalle">${ids.length} JUGADOR(ES)</div>`;
      return;
    }
    const claveMini = JUEGOS_MINI.find((j) => marcador[j]);
    if (claveMini) {
      const ids = Object.keys(marcador[claveMini]);
      const id = ids.includes(yoId) ? yoId : ids[0];
      const dato = marcador[claveMini][id] || {};
      const nombre = jugadores[id] || marcador.nombre || "JUGADOR";
      $("marcador-0").innerHTML =
        `<div class="nombre">${nombreHtml(nombre, id === yoId ? " (tú)" : "")}</div>` +
        `<div class="detalle">PUNTOS <b>${dato.puntos || 0}</b></div>`;
      $("marcador-1").innerHTML =
        `<div class="nombre">RONDA ${dato.ronda || 0} / ${marcador.necesario || 10}</div>` +
        `<div class="detalle">${ids.length} JUGADOR(ES)</div>`;
      return;
    }
    const ids = Object.keys(marcador.pajaros || {});
    [0, 1].forEach((i) => {
      const id = ids[i];
      const caja = $(`marcador-${i}`);
      if (i === 1 && ids.length === 1) {
        // Jugando solo, el segundo cuadro muestra la ronda en vez de un rival.
        caja.innerHTML =
          `<div class="nombre">RONDA ${rondaClasica}</div>` +
          `<div class="detalle">${modoFiesta ? "1 JUGADOR" : `META <b>${marcador.necesario || 3}</b> ACIERTOS`}</div>`;
        return;
      }
      if (!id || !jugadores[id]) {
        caja.innerHTML = "";
        return;
      }
      const aves = marcador.pajaros[id] || 0;
      const letras = marcador.escritura[id] || 0;
      caja.innerHTML =
        `<div class="nombre">${nombreHtml(jugadores[id], id === yoId ? " (tú)" : "")}</div>` +
        `<div class="detalle">HÁMSTERS <b>${aves}</b> · PALABRAS <b>${letras}</b></div>`;
    });
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

  /* ---------- Mensajes del servidor ---------- */
  function mostrarEspera(kicker, titulo, texto, barraDuracion = 0) {
    detenerTimers();
    $("contenido").innerHTML = `<div class="panel panel-escena pantalla-espera-mando">
      <div class="glifo">◉</div>
      <p class="kicker">${kicker}</p>
      <h2 class="panel-titulo">${titulo}</h2>
      <p class="pista">${texto}</p>
      ${barraDuracion ? '<div class="barra-tiempo"><div id="barra-tiempo"></div></div>' : ""}
    </div>`;
    if (barraDuracion) actualizarBarraCajas(barraDuracion);
  }

  // En FIESTA el informe de cada ronda es cosa de la pantalla. El mando solo
  // espera: así la respuesta correcta no aparece nunca en el celular.
  function resultadoSoloEnPantalla() {
    if (!esMandoFiesta()) return false;
    mostrarEspera(
      "MODO FIESTA · INFORME",
      "MÍRALO EN LA PANTALLA",
      "El resultado de la ronda aparece solo en la pantalla. Prepara la siguiente."
    );
    return true;
  }

  function actualizarBarraCajas(duracion) {
    const barra = $("barra-tiempo");
    if (!barra || !duracion) return;
    barra.style.transition = `transform ${duracion}s linear`;
    barra.style.transform = "scaleX(1)";
    requestAnimationFrame(() => (barra.style.transform = "scaleX(0)"));
  }

  function esMandoFiesta() {
    return modoFiesta && esMando;
  }

  function esPantallaFiesta() {
    return modoFiesta && esPantalla;
  }

  function manejar(msg) {
    sonidoMensaje(msg);
    switch (msg.type) {
      case "room_created":
      case "room_joined": {
        yoId = msg.id;
        hostId = msg.host;
        codigo = msg.codigo;
        jugadores = msg.jugadores;
        modoPractica = Boolean(msg.practica);
        modoCajas = msg.modo === "cajas";
        modoOperaciones = msg.modo === "operaciones";
        modoFiesta = msg.modo === "fiesta";
        secuenciaIndividual = msg.modo === "individual";
        esPantalla = modoFiesta && yoId === hostId;
        esMando = modoFiesta && msg.rol === "mando";
        if (modoFiesta && esMando) {
          $("mando-nombre").textContent = jugadores[yoId] || "JUGADOR";
          $("mando-estado").textContent =
            "Esperando a que la pantalla elija un juego…";
          actualizarLobby();
          mostrar("pantalla-mando");
          break;
        }
        if (modoPractica || modoCajas || modoOperaciones) break;
        $("codigo-sala").textContent = codigo;
        actualizarLobby();
        prepararInvitacion(codigo);
        mostrar("pantalla-lobby");
        break;
      }

      case "player_joined":
      case "player_left":
        jugadores = msg.jugadores;
        if (modoFiesta) {
          actualizarLobby();
          if (msg.type === "player_left") aviso(`${msg.nombre} SE DESCONECTÓ`);
        } else if ($("pantalla-lobby").classList.contains("activa")) {
          actualizarLobby();
        } else if (msg.type === "player_left") {
          volverAlInicio(`${msg.nombre} salió de la partida`);
        }
        break;

      case "opponent_left":
        volverAlInicio(`${msg.nombre} abandonó la partida`);
        break;

      case "error": {
        const invitadoActivo = $("pantalla-invitado").classList.contains("activa");
        const destino = invitadoActivo ? "error-invitado" : "error-inicio";
        $(destino).textContent = msg.mensaje;
        break;
      }

      case "individual_game_start":
        secuenciaIndividual = true;
        $("etiqueta-ronda").textContent = `JUEGO ${msg.indice} / ${msg.total}`;
        $("titulo-juego").textContent = msg.nombre_juego;
        $("contenido").innerHTML = `<div class="panel panel-escena">
          <p class="kicker">INDIVIDUAL · SIGUIENTE PRUEBA</p>
          <h2 class="panel-titulo">${escapeHtml(msg.nombre_juego)}</h2>
          <p class="pista">Prepara la atención y la memoria. Empieza enseguida…</p>
        </div>`;
        mostrar("pantalla-juego");
        break;

      case "individual_summary":
        mostrarResumenIndividual(msg);
        break;

      case "mini_progreso":
        actualizarProgresoMini(msg);
        break;

      case "progreso_vivo":
        mostrarProgresoVivo(msg);
        break;

      case "fin_fiesta":
        if (esMandoFiesta()) {
          $("mando-estado").textContent =
            "FIESTA TERMINADA · USA «SALIR» PARA VOLVER AL INICIO";
          $("mando-lista").innerHTML = "";
          mostrar("pantalla-mando");
        }
        break;

      case "match_start":
        marcador = msg.marcador || marcador || { pajaros: {}, escritura: {}, necesario: 3 };
        modoPractica = Boolean(msg.practica);
        modoCajas = msg.modo === "cajas";
        modoOperaciones = msg.modo === "operaciones";
        juegoFiesta = msg.juego_fiesta || juegoFiesta;
        mostrar("pantalla-juego");
        actualizarMarcador();
        if (JUEGOS_MINI.includes(msg.modo) || msg.modo === "rastreo") {
          $("etiqueta-ronda").textContent = "PREPARACIÓN";
          $("titulo-juego").textContent = NOMBRES_FIESTA[msg.modo];
          $("contenido").innerHTML = `<div class="panel panel-escena">
            <p class="kicker">${secuenciaIndividual ? "INDIVIDUAL" : "FIESTA"} · NUEVA PRUEBA</p>
            <h2 class="panel-titulo">${escapeHtml(NOMBRES_FIESTA[msg.modo])}</h2>
            <p class="pista">Prepara la atención. Cada ronda aparecerá enseguida…</p>
          </div>`;
        }
        break;

      case "round_start":
        iniciarRonda(msg);
        break;

      case "birds_countdown":
        mostrarCuentaPrevia(msg, {
          kicker: "FASE 01 · PREPARA LA VISTA",
          pie: "LOS HÁMSTERS APARECERÁN DESPUÉS",
          glifo: "◎",
        });
        break;

      case "birds_show":
        if (esMandoFiesta()) {
          mostrarEspera(
            "MIRA LA PANTALLA",
            "¡A CONTAR!",
            "Los hámsters aparecen en la pantalla del anfitrión."
          );
        } else {
          mostrarPajaros(msg);
        }
        break;

      case "birds_hide":
        if (esPantallaFiesta()) {
          mostrarEspera("PANTALLA · ESPECTADOR", "ESPERANDO RESPUESTAS", "Los mandos están contando.");
        } else {
          ocultarPajaros(msg);
        }
        break;

      case "bird_tally":
        actualizarConteosVivos(msg.conteos || {}, msg.confirmados || []);
        break;

      case "word_countdown":
        mostrarCuentaPrevia(msg);
        break;

      case "word_show":
        if (esMandoFiesta()) {
          mostrarEspera("MIRA LA PANTALLA", "MEMORIZA", "La palabra aparece solo en la pantalla del anfitrión.");
        } else {
          mostrarPalabra(msg);
        }
        break;

      case "word_write":
        if (esPantallaFiesta()) {
          mostrarEspera("PANTALLA · ESPECTADOR", "ESCRIBIENDO…", "Los mandos están escribiendo de memoria.");
        } else {
          iniciarEscritura(msg);
        }
        break;

      case "letter_feedback":
        if (typeof window.__konitiveFeedback === "function") window.__konitiveFeedback(msg);
        break;

      case "word_done":
        if (typeof window.__konitiveTermino === "function") window.__konitiveTermino(msg);
        aviso(
          msg.automaticas
            ? `PALABRA COMPLETA · ${msg.automaticas} AUTOMÁTICA(S)`
            : "PALABRA COMPLETA · ESPERANDO"
        );
        break;

      case "round_result":
        if (!resultadoSoloEnPantalla()) mostrarResultadoRonda(msg);
        break;

      case "minigame_result":
        aviso(`${msg.nombre} SE LLEVA ${msg.juego === "pajaros" ? "HÁMSTERS" : "PALABRAS"}`);
        break;

      case "tiebreak_start":
        aviso("EMPATE · DESEMPATE AL AZAR");
        break;

      case "practice_summary":
        if (!secuenciaIndividual) mostrarResumenPractica(msg);
        break;

      case "cajas_countdown":
        mostrarCuentaCajas(msg);
        break;

      case "cajas_show":
        if (esMandoFiesta()) {
          mostrarEspera(
            "MIRA LA PANTALLA",
            "¡A CONTAR CAJAS!",
            "La pila aparece en la pantalla del anfitrión.",
            msg.duracion
          );
        } else {
          mostrarPilaCajas(msg);
        }
        break;

      case "cajas_hide":
        if (esPantallaFiesta()) {
          mostrarEspera("PANTALLA · ESPECTADOR", "CONTANDO…", "Los mandos están contando las cajas.");
        } else {
          ocultarPilaCajas();
        }
        break;

      case "cajas_result":
        if (!resultadoSoloEnPantalla()) mostrarResultadoCajas(msg);
        break;

      case "cajas_over":
        if (secuenciaIndividual) aviso("PRUEBA TERMINADA");
        else if (modoFiesta) aviso("JUEGO TERMINADO · PODIO");
        else mostrarFinalCajas(msg);
        break;

      case "operacion_countdown":
        mostrarCuentaOperaciones(msg);
        break;

      case "operacion_show":
        if (esMandoFiesta()) {
          mostrarEspera("MIRA LA PANTALLA", "MEMORIZA", "La operación aparece solo en la pantalla del anfitrión.");
        } else {
          mostrarOperacion(msg);
        }
        break;

      case "operacion_write":
        if (esPantallaFiesta()) {
          mostrarEspera("PANTALLA · ESPECTADOR", "CALCULANDO…", "Los mandos están escribiendo el resultado.");
        } else {
          iniciarEscrituraDigitos(msg);
        }
        break;

      case "digit_feedback":
        if (typeof window.__konitiveFeedback === "function") window.__konitiveFeedback(msg);
        break;

      case "operacion_done":
        if (typeof window.__konitiveTermino === "function") window.__konitiveTermino(msg);
        aviso(
          msg.automaticas
            ? `RESULTADO COMPLETO · ${msg.automaticas} AUTOMÁTICA(S)`
            : "RESULTADO COMPLETO · ESPERANDO"
        );
        break;

      case "operacion_result":
        if (!resultadoSoloEnPantalla()) mostrarResultadoOperaciones(msg);
        break;

      case "operacion_over":
        if (secuenciaIndividual) aviso("PRUEBA TERMINADA");
        else if (modoFiesta) aviso("JUEGO TERMINADO · PODIO");
        else mostrarFinalOperaciones(msg);
        break;

      case "rastreo_countdown":
        mostrarCuentaPrevia(msg, {
          kicker: "FASE 01 · PREPARA LA VISTA",
          pie: "RASTREA DOS HÁMSTERS",
          glifo: "◎",
        });
        break;

      case "rastreo_show":
        mostrarRastreo(msg, "observacion");
        break;

      case "rastreo_hide":
        AnimationController.detener();
        mostrarRastreo(msg, "movimiento");
        break;

      case "rastreo_move":
        AnimationController.animar(msg);
        break;

      case "rastreo_write":
        mostrarRastreo(msg, "identificacion");
        break;

      case "rastreo_feedback":
        if (msg.pid !== yoId) return;
        aviso(msg.aciertos === 2 ? "¡LOS DOS HÁMSTERS!" : `${msg.aciertos || 0} DE 2 · BIEN`);
        break;

      case "rastreo_result":
        if (!resultadoSoloEnPantalla()) mostrarResultadoRastreo(msg);
        break;

      case "rastreo_over":
        if (secuenciaIndividual) aviso("PRUEBA TERMINADA");
        else if (modoFiesta) aviso("JUEGO TERMINADO · PODIO");
        else mostrarFinalRastreo(msg);
        break;

      case "match_over":
        if (secuenciaIndividual) break;
        if (modoFiesta) {
          aviso("JUEGO TERMINADO · PODIO");
          break;
        }
        if (modoPractica) {
          // Red de seguridad: práctica nunca debería terminar con "nadie".
          mostrarResumenPractica(msg);
          break;
        }
        mostrarFinal(msg);
        break;

      case "podium_update":
      case "podium_final":
        mostrarPodio(msg);
        break;

      case "back_to_selector":
        volverAlSelector(msg);
        break;

      case "back_to_lobby":
        modoPractica = false;
        modoCajas = false;
        modoOperaciones = false;
        juegoFiesta = null;
        if (msg.jugadores) jugadores = msg.jugadores;
        if (msg.host) hostId = msg.host;
        if (esMandoFiesta()) {
          $("mando-estado").textContent =
            "Sala de espera · el anfitrión elige el siguiente juego…";
          $("mando-lista").innerHTML = "";
          mostrar("pantalla-mando");
          break;
        }
        actualizarMarcador(msg.marcador);
        actualizarLobby();
        mostrar("pantalla-lobby");
        break;

      default: {
        const info = identificarMini(msg.type);
        if (info) {
          manejarMini(msg, info.juego, info.sufijo);
          break;
        }
      }
    }
  }

  function identificarMini(tipo) {
    for (const juego of JUEGOS_MINI) {
      for (const sufijo of SUFIJOS_MINI) {
        if (tipo === juego + sufijo) return { juego, sufijo };
      }
    }
    return null;
  }


  /* ---------- Minijuegos de entrenamiento ---------- */
  function etiquetaRonda(msg) {
    return `RONDA ${String(msg.ronda || 0).padStart(2, "0")} / ${msg.necesario || 10}`;
  }

  function mostrarCuentaMini(msg, juego) {
    detenerTimers();
    let restante = Math.max(1, Math.round(msg.segundos || 3));
    $("contenido").innerHTML = `<div class="panel panel-escena">
      <p class="kicker">${escapeHtml(NOMBRES_MINI[juego])} · PREPARA LA ATENCIÓN</p>
      <div class="cuenta-previa">
        <div class="cuenta-previa-numero" id="cuenta-previa-numero">${restante}</div>
        <div class="cuenta-previa-pie">${etiquetaRonda(msg)}</div>
      </div>
    </div>`;
    clearInterval(cuentaTimer);
    cuentaTimer = setInterval(() => {
      restante -= 1;
      const el = $("cuenta-previa-numero");
      if (el) el.textContent = restante > 0 ? restante : "✎";
      if (restante <= 0) clearInterval(cuentaTimer);
    }, 1000);
  }

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

  function relojSvg(hora, minuto) {
    const punto = (angulo, radio) => {
      const rad = (angulo - 90) * Math.PI / 180;
      return [50 + radio * Math.cos(rad), 50 + radio * Math.sin(rad)];
    };
    let marcas = "";
    for (let i = 0; i < 60; i++) {
      const [x1, y1] = punto(i * 6, i % 5 === 0 ? 33 : 38);
      const [x2, y2] = punto(i * 6, 42);
      marcas += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#1c1a17" stroke-width="${i % 5 === 0 ? 2.5 : 1}"/>`;
    }
    const mano = (angulo, radio, grosor, color) => {
      const [x, y] = punto(angulo, radio);
      return `<line x1="50" y1="50" x2="${x}" y2="${y}" stroke="${color}" stroke-width="${grosor}" stroke-linecap="round"/>`;
    };
    return `<svg class="reloj-svg" viewBox="0 0 100 100" aria-hidden="true">
      <circle cx="50" cy="50" r="46" fill="#f9f5ea" stroke="#1c1a17" stroke-width="3"/>
      ${marcas}
      ${mano((hora % 12) * 30 + minuto * 0.5, 26, 5, "#1c1a17")}
      ${mano(minuto * 6, 36, 2.5, "#1c1a17")}
      <circle cx="50" cy="50" r="3.5" fill="#d33827"/>
    </svg>`;
  }

  function relojDespertador(hora, minuto) {
    return `<div class="despertador-estimulo">
      <span class="despertador-hora">${String(hora % 12 || 12).padStart(2, "0")}</span>
      <span class="despertador-puntos">:</span>
      <span class="despertador-min">${String(minuto).padStart(2, "0")}</span>
    </div>`;
  }

  // Un mismo dibujo para el estímulo y para la pantalla que sigue mostrándolo
  // mientras los mandos responden. El celular nunca recibe estos datos.
  function visualMini(juego, datos, compacta = false) {
    if (juego === "stroop") {
      if (!datos.tinta) return "";
      return `<div class="stroop-palabra" style="color:${COLOR_HEX[datos.tinta] || "#1c1a17"}">${escapeHtml((datos.palabra || "").toUpperCase())}</div>`;
    }
    if (juego === "triangulos") {
      return datos.top ? trianguloHtml(datos) : "";
    }
    if (juego === "relojes") {
      if (!datos.reloj1) return "";
      const [h1, m1] = datos.reloj1;
      const [h2, m2] = datos.reloj2 || [12, 0];
      return `<div class="relojes">
        <div>${relojDespertador(h1, m1)}<span>PRIMERO · ${escapeHtml(datos.periodo1 || "")}</span></div>
        <div class="reloj-flecha">→</div>
        <div>${relojDespertador(h2, m2)}<span>DESPUÉS · ${escapeHtml(datos.periodo2 || "")}</span></div>
      </div>`;
    }
    if (juego === "vuelto") {
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
    }
    if (juego === "silabas") {
      return datos.frase ? `<div class="frase-silabas">${escapeHtml(datos.frase.toUpperCase())}</div>` : "";
    }
    if (juego === "ppt") {
      if (!datos.rival) return "";
      const gana = datos.objetivo === "ganar";
      return `<div class="ppt-visual">
        <div class="ppt-rival">RIVAL · <b>${escapeHtml(datos.rival.toUpperCase())}</b></div>
        <div class="ppt-consigna ${gana ? "ppt-ganar" : "ppt-perder"}">${gana ? "GANAR" : "PERDER"}</div>
      </div>`;
    }
    return "";
  }

  function miraPantallaHtml(texto = "MIRA LA PANTALLA") {
    return `<div class="mira-pantalla"><b>${texto}</b><span>Y responde aquí</span></div>`;
  }

  // Celular: todo apilado. PC: el visual grande a la izquierda y los controles a la derecha (como CAJAS).
  function panelAmplio(arriba, visual, abajo, clases = "", ref = "") {
    return `<div class="panel panel-escena panel-amplio ${clases}">
      <div class="amplio-arriba">${arriba}</div>
      ${ref ? `<div class="amplio-ref">${ref}</div>` : ""}
      <div class="amplio-visual">${visual}</div>
      <div class="amplio-abajo">${abajo}</div>
    </div>`;
  }

  function grillaMenorHtml(numeros, interactiva) {
    return `<div class="campo-menor ${interactiva ? "interactiva" : ""}">
      ${(numeros || []).map((n, i) =>
        `<button type="button" class="numero-menor" style="left:${n.x * 100}%;top:${n.y * 100}%" data-indice="${i}" ${interactiva ? "" : "disabled"}>${n.valor}</button>`
      ).join("")}
    </div>`;
  }

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

  function mostrarEstimuloMini(juego, msg) {
    detenerTimers();
    if (esMandoFiesta() && msg.mira) {
      mostrarEspera(
        "MIRA LA PANTALLA",
        "¡ATENTO!",
        "El estímulo aparece solo en la pantalla del anfitrión.",
        msg.duracion || 0
      );
      return;
    }
    const comun = `<p class="kicker">${escapeHtml(NOMBRES_MINI[juego])} · ${etiquetaRonda(msg)}</p>`;
    let cuerpo = "";
    if (juego === "stroop") {
      cuerpo = [
        visualMini(juego, msg),
        (msg.duracion ? '<div class="barra-tiempo"><div id="barra-tiempo"></div></div>' : "") +
          '<p class="pista">Di el COLOR DE LA TINTA, no lo que dice la palabra. ¡Se borra rápido!</p>',
      ];
    } else if (juego === "triangulos") {
      cuerpo = [visualMini(juego, msg), '<p class="pista">Opera cada par vecino hacia abajo (el número del centro se usa dos veces) y escribe solo el resultado final.</p>'];
    } else if (juego === "relojes") {
      cuerpo = [visualMini(juego, msg), '<p class="pista">¿Cuánto tiempo pasó hacia adelante? Fíjate si es a. m. (mañana) o p. m. (tarde).</p>'];
    } else if (juego === "menor") {
      cuerpo = grillaMenorHtml(msg.numeros, false) + '<p class="pista">Recuerda la posición de cada número.</p>';
    } else if (juego === "memoria") {
      cuerpo = [grillaMemoriaHtml(msg.grilla, msg.celdas, true, msg.posiciones, []),
        msg.duracion ? '<div class="barra-tiempo"><div id="barra-tiempo"></div></div>' : ""];
    } else if (juego === "vuelto") {
      cuerpo = [visualMini(juego, msg), '<p class="pista">Prepara el vuelto exacto en tu celular.</p>'];
    } else if (juego === "silabas") {
      cuerpo = [visualMini(juego, msg),
        '<p class="pista">Cuenta las sílabas gramaticales de toda la frase, palabra por palabra.</p>'];
    } else if (juego === "ppt") {
      cuerpo = [visualMini(juego, msg),
        '<p class="pista">Elige la mano que cumpla la consigna contra el rival</p>'];
    }
    // [visual, abajo]; menor a mayor ya tiene su propio campo a lo ancho.
    $("contenido").innerHTML = Array.isArray(cuerpo)
      ? panelAmplio(comun, cuerpo[0], cuerpo[1], `estimulo-${juego}`)
      : `<div class="panel panel-escena">${comun}${cuerpo}</div>`;
    if ((juego === "memoria" || juego === "stroop") && msg.duracion) actualizarBarraCajas(msg.duracion);
  }

  function prepararRespuestaMini(juego, msg) {
    const mando = esMandoFiesta();
    if (esPantallaFiesta()) {
      const visual = visualMini(juego, msg, juego === "vuelto");
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
    $("titulo-juego").textContent = NOMBRES_MINI[juego] || juego.toUpperCase();
    if (juego === "triangulos") {
      const estimulo = mando ? null : (msg.estimulo || {});
      iniciarCanvasEscritura({
        kicker: mando ? "MIRA LA PANTALLA · ESCRIBE EL RESULTADO" : `${NOMBRES_MINI[juego]} · ${etiquetaRonda(msg)}`,
        recordatorio: estimulo?.top ? trianguloHtml(estimulo) : "",
        pista: mando ? "Calcula mirando la PC y escribe solo el resultado final aquí." : "",
        tipoMensaje: `${juego}_digit`,
        extra: { ronda: msg.ronda },
        feedbackAceptada: (fb) => `✓ ${fb.esperada ?? ""} · BIEN`,
        feedbackRechazada: (fb) => `✗ PARECE ${fb.predicha ?? "?"} · INTENTO ${fb.intentos || 1}/3`,
        terminoTexto: "RESPUESTA COMPLETA · ESPERANDO",
      });
      const letras = $("letras-escritas");
      if (letras && msg.campo) letras.dataset.campo = msg.campo;
      return;
    }

    if (juego === "silabas") {
      const frase = mando ? "" : (msg.frase || "");
      $("contenido").innerHTML = panelAmplio(
        `<p class="kicker">${mando ? "MIRA LA PANTALLA · CUENTA SÍLABAS" : `CONTAR SÍLABAS · ${etiquetaRonda(msg)}`}</p>`,
        frase ? `<div class="frase-silabas">${escapeHtml(frase.toUpperCase())}</div>` : miraPantallaHtml(),
        `<p class="pista">${mando ? "Cuenta en la PC y marca el total aquí." : "Cuenta las sílabas gramaticales de toda la frase."}</p>
        <div class="stepper">
          <button id="btn-menos" class="stepper-boton" aria-label="Quitar uno">−</button>
          <output id="cuenta-valor" class="stepper-valor" aria-live="polite">0</output>
          <button id="btn-mas" class="stepper-boton" aria-label="Agregar uno">+</button>
        </div>
        <p class="pista stepper-ayuda">Usa los botones o las flechas arriba y abajo.</p>
        <button id="btn-responder" class="boton rojo">CONFIRMAR</button>
        <div class="mini-progreso" id="mini-progreso"></div>`,
        "respuesta-silabas"
      );
      let valor = 0;
      let confirmado = false;
      function cambiar(delta) {
        if (confirmado) return;
        valor = Math.min(200, Math.max(0, valor + delta));
        $("cuenta-valor").textContent = valor;
      }
      function confirmar() {
        if (confirmado) return;
        confirmado = true;
        $("btn-menos").disabled = true;
        $("btn-mas").disabled = true;
        $("btn-responder").disabled = true;
        if (teclaConteo) document.removeEventListener("keydown", teclaConteo);
        teclaConteo = null;
        enviar({ type: "silabas_answer", ronda: msg.ronda, respuesta: valor });
        aviso("CUENTA CONFIRMADA");
      }
      $("btn-menos").addEventListener("click", () => cambiar(-1));
      $("btn-mas").addEventListener("click", () => cambiar(1));
      $("btn-responder").addEventListener("click", confirmar);
      teclaConteo = (e) => {
        if (["ArrowUp", "ArrowRight"].includes(e.key)) { e.preventDefault(); cambiar(1); }
        else if (["ArrowDown", "ArrowLeft"].includes(e.key)) { e.preventDefault(); cambiar(-1); }
        else if (e.key === "Enter") { e.preventDefault(); confirmar(); }
      };
      document.addEventListener("keydown", teclaConteo);
      $("btn-responder").focus();
      return;
    }

    if (juego === "relojes") {
      const show = mando ? {} : (msg.reloj1 ? msg : (ultimoShowMini["relojes"] || {}));
      $("contenido").innerHTML = panelAmplio(
        `<p class="kicker">${mando ? "MIRA LA PANTALLA · CALCULA LA DIFERENCIA" : `RELOJES · ${etiquetaRonda(msg)}`}</p>`,
        mando ? miraPantallaHtml() : (visualMini("relojes", show) || miraPantallaHtml()),
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
        <p class="pista stepper-ayuda">Flechas ← → eligen horas o minutos; ↑ ↓ cambian el número; Enter confirma.</p>
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
      return;
    }

    if (juego === "stroop") {
      // La palabra ya se borró: no se recupera del _show aunque el cliente lo
      // haya guardado. El aviso no revela la tinta ni lo que decía la palabra.
      $("contenido").innerHTML = panelAmplio(
        `<p class="kicker">ELIGE EL COLOR DE LA TINTA</p>`,
        mando
          ? miraPantallaHtml("MIRA LA PANTALLA · ELIGE LA TINTA")
          : `<div class="mira-pantalla stroop-oculto"><b>¿DE QUÉ COLOR ERA LA TINTA?</b><span>La palabra ya se borró · responde de memoria</span></div>`,
        `<p class="pista">Elige el color de la tinta que viste, no lo que decía la palabra.</p>
        <div class="stroop-botones">
          ${["rojo", "azul", "verde", "amarillo"].map((color) =>
            `<button type="button" class="boton stroop-opcion" data-color="${color}">${color.toUpperCase()}</button>`
          ).join("")}
        </div>
        <div class="mini-progreso" id="mini-progreso"></div>`,
        "respuesta-stroop"
      );
      $("contenido").querySelectorAll("[data-color]").forEach((boton) => {
        boton.addEventListener("click", () => {
          desactivarOpciones("stroop");
          enviar({ type: "stroop_answer", ronda: msg.ronda, respuesta: boton.dataset.color });
        });
      });
    } else if (juego === "menor") {
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
    } else if (juego === "memoria") {
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
    } else if (juego === "vuelto") {
      const elegidos = {};
      const escena = mando
        ? miraPantallaHtml("MIRA LA PANTALLA · PRECIO Y PAGO")
        : (visualMini("vuelto", msg, true) || miraPantallaHtml());
      $("contenido").innerHTML = panelAmplio(
        `<p class="kicker">ARMA EL VUELTO EXACTO</p>
        ${escena}
        <div class="vuelto-bandera"><span>LLEVAS ENTREGADO</span><b id="vuelto-total">$0</b><div id="vuelto-chips" class="vuelto-chips"></div></div>`,
        `<div class="vuelto-denominaciones">
          ${(msg.denominaciones || []).map((d) =>
            `<div class="denom"><button type="button" class="boton contorno chico" data-denom="${d}">$${d.toLocaleString("es-CL")}</button></div>`
          ).join("")}
        </div>`,
        `<button type="button" class="boton rojo" id="vuelto-entregar">ENTREGAR ✓</button>
        <div class="mini-progreso" id="mini-progreso"></div>`,
        "respuesta-vuelto"
      );
      const pintar = () => {
        const chips = Object.entries(elegidos)
          .filter(([, n]) => n > 0)
          .map(([d, n]) => `<span class="vuelto-chip">$${Number(d).toLocaleString("es-CL")} × ${n}</span>`)
          .join("");
        $("vuelto-chips").innerHTML = chips;
        const total = Object.entries(elegidos).reduce((suma, [d, n]) => suma + Number(d) * n, 0);
        $("vuelto-total").textContent = `$${total.toLocaleString("es-CL")}`;
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
    } else if (juego === "ppt") {
      // En FIESTA el mando solo recibe {"mira": true}: la mano del rival y la
      // consigna viven en la pantalla del anfitrión. En INDIVIDUAL llegan en el
      // ppt_write y se muestran aquí mismo.
      const visual = mando
        ? miraPantallaHtml("MIRA LA PANTALLA · ELIGE TU MANO")
        : visualMini("ppt", msg);
      $("contenido").innerHTML = panelAmplio(
        '<p class="kicker">ELIGE LA MANO QUE CUMPLA LA CONSIGNA</p>',
        visual,
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
      $("contenido").querySelectorAll("[data-mano]").forEach((boton) => {
        boton.addEventListener("click", () => {
          desactivarOpciones("ppt");
          enviar({ type: "ppt_answer", ronda: msg.ronda, respuesta: boton.dataset.mano });
        });
      });
    }
  }

  function desactivarOpciones(juego) {
    const selector = juego === "stroop" ? "[data-color]"
      : juego === "ppt" ? "[data-mano]"
      : "[data-indice], [data-celda]";
    $("contenido").querySelectorAll(selector).forEach((boton) => (boton.disabled = true));
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
      clearTimeout(marcarMenor.limpiar);
      marcarMenor.limpiar = setTimeout(() => (avisoMenor.textContent = ""), 1800);
    }
  }

  // Franja de avance por ronda: solo se proyecta en la pantalla del anfitrión.
  function mostrarProgresoVivo(msg) {
    if (!esPantallaFiesta()) return;
    const caja = $("progreso-vivo");
    if (!caja) return;
    const filas = msg.jugadores || [];
    const nombreJuego = NOMBRES_FIESTA[msg.juego] || (msg.juego || "").toUpperCase();
    const ronda = msg.ronda ? ` · RONDA ${String(msg.ronda).padStart(2, "0")}` : "";
    const estadoTexto = { contando: "CONTANDO", listo: "LISTO", esperando: "ESPERANDO" };
    caja.innerHTML =
      `<span class="pv-titulo">${escapeHtml(nombreJuego + ronda)}</span>` +
      filas
        .map((fila) => {
          const total = fila.total ? ` / ${fila.total}` : "";
          const estado = estadoTexto[fila.estado] || "EN JUEGO";
          return `<span class="pv-fila ${fila.estado === "listo" ? "listo" : ""}">
            <span class="pv-nombre">${escapeHtml(fila.nombre || "JUGADOR")}</span>
            <span class="pv-valor">${fila.avance || 0}${total}</span>
            <span class="pv-estado">${estado}</span>
          </span>`;
        })
        .join("");
    caja.hidden = filas.length === 0;
  }

  function actualizarProgresoMini(msg) {
    const caja = $("mini-progreso");
    if (!caja) return;
    caja.textContent = `${msg.marcados || 0} / ${msg.total || 0} · FALLOS ${msg.fallos || 0}`;
  }

  function respuestaCorrectaHtml(juego, reto) {
    if (juego === "stroop") {
      return `<div class="mini-respuesta">LA TINTA ERA <b style="color:${COLOR_HEX[reto.tinta] || "#1c1a17"}">${escapeHtml((reto.tinta || "").toUpperCase())}</b></div>`;
    }
    if (juego === "triangulos") return trianguloHtml(reto, true);
    if (juego === "relojes") {
      return `<div class="mini-respuesta">${escapeHtml(`${reto.digital1 || ""} ${reto.periodo1 || ""}`)} → ${escapeHtml(`${reto.digital2 || ""} ${reto.periodo2 || ""}`)} = <b>${reto.horas || 0} h ${reto.minutos || 0} min</b></div>`;
    }
    if (juego === "menor") {
      return `<div class="mini-respuesta">ORDEN: ${(reto.orden || []).map((i) => reto.numeros[i]?.valor).join(" → ")}</div>`;
    }
    if (juego === "memoria") {
      return grillaMemoriaHtml(reto.grilla, reto.grilla * reto.grilla, true, reto.posiciones || {}, []);
    }
    if (juego === "vuelto") {
      const optimo = Object.entries(reto.optimo || {})
        .map(([d, n]) => `$${Number(d).toLocaleString("es-CL")} × ${n}`)
        .join(" · ");
      return `<div class="mini-respuesta">VUELTO <b>${escapeHtml(reto.vuelto_texto || "")}</b><br><span class="pista">ÓPTIMO: ${escapeHtml(optimo)}</span></div>`;
    }
    if (juego === "ppt") {
      const gana = reto.objetivo === "ganar";
      const consigna = gana ? "GANAR" : "PERDER";
      return `<div class="mini-respuesta ppt-respuesta">
        <div class="ppt-rival">RIVAL · <b>${escapeHtml((reto.rival || "").toUpperCase())}</b></div>
        <div class="ppt-consigna ${gana ? "ppt-ganar" : "ppt-perder"}">${consigna}</div>
        <div>MANO CORRECTA · <b>${escapeHtml((reto.esperado || "").toUpperCase())}</b></div>
      </div>`;
    }
    return `<div class="mini-respuesta">${escapeHtml(reto.pista || "")} = <b>${reto.total || 0} SÍLABAS</b></div>`;
  }

  function mostrarResultadoMini(juego, msg) {
    detenerTimers();
    actualizarMarcador(msg.marcador);
    const filas = Object.entries(msg.jugadores || {})
      .map(([id, dato]) => `<div class="puntaje ${id === yoId ? "propio" : ""}">
        <div class="numero">${escapeHtml((jugadores[id] || "JUGADOR").slice(0, 9))}</div>
        <div class="quien">${dato.acierto ? "✔️ CORRECTO" : "❌ ERROR"}</div>
        <div class="desglose">${dato.tiempo || 0} s · ERRORES ${dato.errores || 0}</div>
      </div>`)
      .join("");
    $("contenido").innerHTML = `<div class="panel resultado">
      <div class="resultado-cabecera">
        <p class="kicker">${escapeHtml(NOMBRES_MINI[juego] || juego.toUpperCase())} · ${etiquetaRonda(msg)}</p>
        <h2>${msg.acierto ? "✔️ RONDA CORRECTA" : "❌ RONDA ERRÓNEA"}</h2>
      </div>
      ${respuestaCorrectaHtml(juego, msg.reto || {})}
      <div class="puntajes">${filas}</div>
    </div>`;
  }

  function mostrarFinalMini(juego, msg) {
    detenerTimers();
    if (secuenciaIndividual || modoFiesta) {
      aviso("PRUEBA TERMINADA");
      return;
    }
    const filas = (msg.clasificacion || [])
      .map((fila) => `<div class="puntaje ${fila.id === yoId ? "propio" : ""}">
        <div class="numero">${fila.brain_age ?? fila.puntos ?? 0}</div>
        <div class="quien">${nombreHtml(fila.nombre)}</div>
        <div class="desglose">${fila.brain_age != null ? "PUNTAJE BRAIN AGE" : "PUNTOS"}</div>
      </div>`)
      .join("");
    $("contenido").innerHTML = `<div class="panel resultado">
      <div class="resultado-cabecera">
        <p class="kicker">INFORME FINAL · ${escapeHtml(NOMBRES_MINI[juego] || "")}</p>
        <h2>TU ENTRENAMIENTO</h2>
      </div>
      <div class="puntajes">
        <div class="puntaje"><div class="numero">${msg.brain_age ?? 0}</div><div class="quien">PUNTAJE BRAIN AGE · MENOR ES MEJOR</div></div>
        <div class="puntaje"><div class="numero">${msg.precision ?? 0}%</div><div class="quien">PRECISIÓN</div></div>
        <div class="puntaje"><div class="numero">${msg.tiempo_promedio ?? 0} s</div><div class="quien">TIEMPO PROMEDIO POR RONDA</div></div>
      </div>
      <div class="puntajes">${filas}</div>
      <div class="diploma-acciones">
        <button class="boton rojo chico" id="btn-volver-mini">VOLVER AL INICIO</button>
      </div>
    </div>`;
    $("btn-volver-mini").addEventListener("click", () => volverAlInicio());
  }

  function manejarMini(msg, juego, sufijo) {
    if (sufijo === "_countdown") {
      mostrarCuentaMini(msg, juego);
    } else if (sufijo === "_show") {
      ultimoShowMini[juego] = msg;
      mostrarEstimuloMini(juego, msg);
    } else if (sufijo === "_hide") {
      if (esPantallaFiesta()) {
        mostrarEspera("PANTALLA · ESPECTADOR", "RESPONDIENDO…", "Los mandos están respondiendo.");
      } else {
        prepararRespuestaMini(juego, msg);
      }
    } else if (sufijo === "_write") {
      prepararRespuestaMini(juego, msg);
    } else if (sufijo === "_feedback") {
      if (msg.pid !== yoId) return;
      if (["triangulos", "relojes", "silabas"].includes(juego)) {
        if (typeof window.__konitiveFeedback === "function") window.__konitiveFeedback(msg);
      } else if (juego === "menor") {
        marcarMenor(msg.acepta);
      } else {
        flashMini(msg.acepta);
      }
    } else if (sufijo === "_done") {
      if (msg.pid !== yoId) return;
      if (typeof window.__konitiveTermino === "function") window.__konitiveTermino(msg);
      aviso("RESPUESTA COMPLETA");
    } else if (sufijo === "_result") {
      if (!resultadoSoloEnPantalla()) mostrarResultadoMini(juego, msg);
    } else if (sufijo === "_over") {
      mostrarFinalMini(juego, msg);
    }
  }

  function tituloJuego(juego) {
    return (
      {
        pajaros: "CONTAR HÁMSTERS",
        escritura: "ESCRIBIR PALABRAS",
        cajas: "CONTAR CAJAS",
        operaciones: "OPERACIONES",
        rastreo: "RASTREO DE HÁMSTERS",
        ...NOMBRES_MINI,
      }[juego] || "KONITIVE"
    );
  }

  /* ---------- Rastreo de hámsters: tablero, fases y selección ---------- */
  const FASES_RASTREO = {
    observacion: "FASE 01 · OBSERVA",
    movimiento: "FASE 02 · SIGUE LAS CASILLAS",
    identificacion: "FASE 03 · SEÑALA DOS HÁMSTERS",
  };

  function tableroRastreoHtml({ valores, mostrarAves, interactiva, seleccion = [], marcas = {} }) {
    const [pelo, panza] = PELAJES[0];
    return `<div class="rastreo-tablero" id="rastreo-tablero">${Array.from({ length: 12 }, (_, i) => {
      const ave = mostrarAves && Array.isArray(valores) && valores[i] && valores[i] !== "G";
      const contenido = ave
        ? `<span class="rastreo-ave" style="--pelo:${pelo};--panza:${panza}">${AVE_SVG}</span>`
        : "?";
      const clases = [
        "rastreo-casilla",
        seleccion.includes(i) ? "seleccionada" : "",
        marcas[i] || "",
      ].filter(Boolean).join(" ");
      return `<button type="button" class="${clases}" data-celda="${i}" ${interactiva ? "" : "disabled"}>${contenido}</button>`;
    }).join("")}</div>`;
  }

  function mostrarRastreo(msg, fase) {
    detenerTimers();
    const kicker = FASES_RASTREO[fase] || FASES_RASTREO.movimiento;
    if (esMandoFiesta()) {
      if (fase === "identificacion") {
        $("etiqueta-ronda").textContent = `RONDA ${String(msg.ronda || 0).padStart(2, "0")}`;
        $("titulo-juego").textContent = "RASTREO DE HÁMSTERS";
        $("contenido").innerHTML = panelAmplio(
          `<p class="kicker">${kicker}</p>`,
          '<p class="rastreo-mando-pista">ELIGE DOS NÚMEROS</p>',
          `<div class="rastreo-numeros">${Array.from({ length: 12 }, (_, i) =>
            `<button type="button" class="rastreo-numero" data-celda="${i}">${i + 1}</button>`).join("")}</div>`,
          "respuesta-rastreo rastreo-mando"
        );
        configurarSeleccionRastreo(msg);
        return;
      }
      mostrarEspera(
        "MIRA LA PANTALLA",
        fase === "observacion" ? "¡OBSERVA!" : "¡SIGUE LAS CASILLAS!",
        "El tablero aparece solo en la pantalla del anfitrión.",
        msg.duracion || 0
      );
      return;
    }

    const pantalla = esPantallaFiesta();
    const observa = fase === "observacion";
    const interactiva = fase === "identificacion" && !pantalla;
    const pista = observa
      ? "Memoriza dónde están los dos hámsters: los dibujos, no las incógnitas."
      : fase === "movimiento"
        ? "Sigue las casillas. Las identidades quedan ocultas."
        : pantalla
          ? "Los mandos señalan dos casillas desde su celular."
          : "Toca las dos casillas donde crees que están los hámsters.";
    const abajo = `<p class="pista">${pista}</p>` +
      (msg.duracion ? '<div class="barra-tiempo"><div id="barra-tiempo"></div></div>' : "");
    $("contenido").innerHTML = panelAmplio(
      `<p class="kicker">${kicker}</p>`,
      tableroRastreoHtml({ valores: msg.tablero || [], mostrarAves: observa, interactiva }),
      abajo,
      `respuesta-rastreo rastreo-${fase}${pantalla ? " pantalla-espectadora" : ""}`
    );
    if (interactiva) configurarSeleccionRastreo(msg);
    if (msg.duracion) actualizarBarraCajas(msg.duracion);
  }

  function configurarSeleccionRastreo(msg) {
    const botones = [...$("contenido").querySelectorAll("[data-celda]")];
    const elegidas = [];
    let enviada = false;
    botones.forEach((boton) => {
      boton.addEventListener("click", () => {
        if (enviada) return;
        const indice = Number(boton.dataset.celda);
        if (elegidas.includes(indice)) return;
        elegidas.push(indice);
        boton.classList.add("seleccionada");
        if (elegidas.length < 2) return;
        enviada = true;
        botones.forEach((b) => (b.disabled = true));
        enviar({ type: "rastreo_answer", ronda: msg.ronda, respuesta: [...elegidas] });
      });
    });
  }

  function mostrarResultadoRastreo(msg) {
    detenerTimers();
    const posiciones = Object.values(msg.reto?.final || {});
    const seleccion = Array.isArray(msg.seleccion) ? msg.seleccion : [];
    const marcas = {};
    seleccion.forEach((i) => (marcas[i] = posiciones.includes(i) ? "acierto" : "fallo"));
    const valores = Array.from({ length: 12 }, (_, i) => (posiciones.includes(i) ? "h" : "G"));
    $("contenido").innerHTML = panelAmplio(
      `<p class="kicker">RASTREO DE HÁMSTERS · RONDA ${String(msg.ronda || 0).padStart(2, "0")}</p>`,
      tableroRastreoHtml({ valores, mostrarAves: true, interactiva: false, seleccion, marcas }),
      `<p class="pista">Los dos dibujos son los hámsters; el contorno señala tu elección.</p>
       <div class="rastreo-metricas">
         <div><b>${Number(msg.aciertos) || 0} / 2</b><span>ACIERTOS</span></div>
         <div><b>${Number(msg.precision) || 0}%</b><span>PRECISIÓN</span></div>
         <div><b>${Number(msg.brain_age) || 0}</b><span>BRAIN AGE</span></div>
       </div>`,
      "respuesta-rastreo resultado-rastreo"
    );
  }

  function mostrarFinalRastreo(msg) {
    detenerTimers();
    const filas = (msg.clasificacion || [])
      .map((fila) => `<div class="puntaje ${fila.id === yoId ? "propio" : ""}">
        <div class="numero">${fila.brain_age ?? fila.puntos ?? 0}</div>
        <div class="quien">${nombreHtml(fila.nombre)}</div>
        <div class="desglose">${fila.brain_age != null ? "BRAIN AGE · MENOR ES MEJOR" : "PUNTOS"}</div>
      </div>`)
      .join("");
    $("contenido").innerHTML = `<div class="panel resultado">
      <div class="resultado-cabecera">
        <p class="kicker">INFORME FINAL · RASTREO DE HÁMSTERS</p>
        <p class="panel-titulo">TU ENTRENAMIENTO</p>
      </div>
      <div class="puntajes">
        <div class="puntaje"><div class="numero">${msg.brain_age ?? 0}</div><div class="quien">BRAIN AGE · MENOR ES MEJOR</div></div>
        <div class="puntaje"><div class="numero">${msg.precision ?? 0}%</div><div class="quien">PRECISIÓN</div></div>
        <div class="puntaje"><div class="numero">${msg.tiempo_promedio ?? 0} s</div><div class="quien">TIEMPO POR RONDA</div></div>
      </div>
      <div class="puntajes">${filas}</div>
      <div class="diploma-acciones">
        <button class="boton rojo chico" id="btn-volver-rastreo">VOLVER AL INICIO</button>
      </div>
    </div>`;
    $("btn-volver-rastreo").addEventListener("click", () => volverAlInicio());
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

  /* ---------- Pájaros ---------- */
  function mostrarPajaros(msg) {
    detenerTimers();
    conteoToken = msg.token || null;
    conteosPajarosVivos = {};
    confirmadosPajaros = [];
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
        ${esMando || esPantalla ? "" : '<div class="stepper-respuesta"><div class="stepper"><button id="btn-menos" class="stepper-boton" aria-label="Quitar uno">−</button><output id="cuenta-valor" class="stepper-valor" aria-live="polite">0</output><button id="btn-mas" class="stepper-boton" aria-label="Agregar uno">+</button></div><p class="pista stepper-ayuda">Cuenta los hámsters y responde cuanto antes.</p><button id="btn-responder" class="boton rojo">CONFIRMAR CUENTA</button></div>'}
        ${esPantalla ? '<p class="pista">Los mandos cuentan en su celular.</p>' : ""}
        <div class="barra-tiempo"><div id="barra-tiempo"></div></div>
      </div>
    </div>`;

    if (esMando) {
      const barra = $("barra-tiempo");
      if (barra) {
        barra.style.transition = `transform ${msg.limite || msg.duracion}s linear`;
        barra.style.transform = "scaleX(1)";
        requestAnimationFrame(() => (barra.style.transform = "scaleX(0)"));
      }
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
      const barra = $("barra-tiempo");
      if (barra) barra.style.transform = `scaleX(${transcurrido})`;
      animacion = requestAnimationFrame(fotograma);
    }
    animacion = requestAnimationFrame(fotograma);

    if (!esPantalla) configurarStepperPajaros();
  }

  function configurarStepperPajaros() {
    let valor = 0;
    let confirmado = false;

    function cambiar(delta) {
      if (confirmado) return;
      valor = Math.min(200, Math.max(0, valor + delta));
      $("cuenta-valor").textContent = valor;
      enviar({ type: "bird_tally", count: valor, token: conteoToken });
    }

    function confirmar() {
      if (confirmado) return;
      confirmado = true;
      $("btn-menos").disabled = true;
      $("btn-mas").disabled = true;
      $("btn-responder").disabled = true;
      if (teclaConteo) document.removeEventListener("keydown", teclaConteo);
      teclaConteo = null;
      enviar({ type: "bird_answer", count: valor, token: conteoToken });
      aviso("CUENTA CONFIRMADA");
    }

    $("btn-menos").addEventListener("click", () => cambiar(-1));
    $("btn-mas").addEventListener("click", () => cambiar(1));
    $("btn-responder").addEventListener("click", confirmar);

    teclaConteo = (e) => {
      if (["ArrowUp", "ArrowRight"].includes(e.key)) { e.preventDefault(); cambiar(1); }
      else if (["ArrowDown", "ArrowLeft"].includes(e.key)) { e.preventDefault(); cambiar(-1); }
      else if (e.key === "Enter") { e.preventDefault(); confirmar(); }
    };
    document.addEventListener("keydown", teclaConteo);
    $("btn-responder").focus();
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
      conteosPajarosVivos = { ...(msg.conteos || {}) };
      confirmadosPajaros = msg.confirmados || [];
      let vivos = $("conteos-vivos");
      if (!vivos) {
        vivos = document.createElement("div");
        vivos.className = "conteos-vivos";
        vivos.id = "conteos-vivos";
        const respuesta = document.querySelector("#contenido .stepper-respuesta");
        if (respuesta) respuesta.after(vivos);
        else $("contenido").appendChild(vivos);
      }
      actualizarConteosVivos(conteosPajarosVivos, confirmadosPajaros);
      const responder = $("btn-responder");
      if (responder) responder.focus();
      return;
    }

    detenerTimers();
    $("contenido").innerHTML = `<div class="panel">
      <p class="kicker">FASE 02 · RESPONDE</p>
      <h2 class="panel-titulo">¿CUÁNTOS HÁMSTERS HABÍA?</h2>
      <div class="stepper">
        <button id="btn-menos" class="stepper-boton" aria-label="Quitar uno">−</button>
        <output id="cuenta-valor" class="stepper-valor" aria-live="polite">0</output>
        <button id="btn-mas" class="stepper-boton" aria-label="Agregar uno">+</button>
      </div>
      <p class="pista stepper-ayuda">Usa los botones o las flechas arriba y abajo.</p>
      <button id="btn-responder" class="boton rojo">CONFIRMAR CUENTA</button>
      <p class="pista">Tienes ${msg.segundos} segundos. Suma más quien antes acierte.</p>
    </div>`;

    let valor = 0;
    let confirmado = false;

    function pintar() {
      $("cuenta-valor").textContent = valor;
    }

    function cambiar(delta) {
      if (confirmado) return;
      valor = Math.min(200, Math.max(0, valor + delta));
      pintar();
      enviar({ type: "bird_tally", count: valor, token: conteoToken });
    }

    function confirmar() {
      if (confirmado) return;
      confirmado = true;
      $("btn-menos").disabled = true;
      $("btn-mas").disabled = true;
      $("btn-responder").disabled = true;
      if (teclaConteo) document.removeEventListener("keydown", teclaConteo);
      teclaConteo = null;
      enviar({ type: "bird_answer", count: valor, token: conteoToken });
      aviso("CUENTA CONFIRMADA");
    }

    $("btn-menos").addEventListener("click", () => cambiar(-1));
    $("btn-mas").addEventListener("click", () => cambiar(1));
    $("btn-responder").addEventListener("click", confirmar);

    teclaConteo = (e) => {
      if (["ArrowUp", "ArrowRight"].includes(e.key)) {
        e.preventDefault();
        cambiar(1);
      } else if (["ArrowDown", "ArrowLeft"].includes(e.key)) {
        e.preventDefault();
        cambiar(-1);
      } else if (e.key === "Enter") {
        e.preventDefault();
        confirmar();
      }
    };
    document.addEventListener("keydown", teclaConteo);

    $("btn-responder").focus();
  }

  /* ---------- Palabra: cuenta previa → flash → escritura ---------- */
  function mostrarCuentaPrevia(
    msg,
    { kicker = "FASE 01 · PREPARA LA MEMORIA", pie = "LA PALABRA APARECERÁ DESPUÉS", glifo = "✎" } = {}
  ) {
    detenerTimers();
    let restante = Math.max(1, Math.round(msg.segundos));
    $("contenido").innerHTML = `<div class="panel panel-escena">
      <p class="kicker">${kicker}</p>
      <div class="cuenta-previa">
        <div class="cuenta-previa-numero" id="cuenta-previa-numero">${restante}</div>
        <div class="cuenta-previa-pie">${pie}</div>
      </div>
    </div>`;

    clearInterval(cuentaTimer);
    cuentaTimer = setInterval(() => {
      restante -= 1;
      const el = $("cuenta-previa-numero");
      if (el) {
        el.textContent = restante > 0 ? restante : glifo;
        el.style.animation = "none";
        void el.offsetWidth;
        el.style.animation = "";
      }
      if (restante <= 0) clearInterval(cuentaTimer);
    }, 1000);
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

  function iniciarCanvasEscritura(opciones) {
    clearInterval(cuentaTimer);
    cuentaTimer = null;
    const letrasAceptadas = {};
    let indice = 0;
    let esperando = false;
    let terminado = false;
    let trazos = [];
    let trazoActual = [];
    let dibujando = false;
    let feedbackTimer = null;

    function cancelarFeedbackTimer() {
      if (feedbackTimer) {
        clearTimeout(feedbackTimer);
        feedbackTimer = null;
      }
    }

    // PC: TRIÁNGULOS lleva la pirámide grande a la izquierda y el lienzo a la derecha.
    $("contenido").innerHTML = panelAmplio(
      `<p class="kicker">${opciones.kicker}</p>`,
      `<div class="letras-escritas" id="letras-escritas"></div>
      <canvas id="lienzo" width="280" height="280" aria-label="Área de dibujo"></canvas>`,
      `<div class="acciones">
        <button class="boton contorno chico" id="btn-limpiar">LIMPIAR</button>
        <button class="boton rojo chico" id="btn-listo">LISTO ✓</button>
      </div>
      <div class="feedback-letra" id="feedback-letra"></div>
      ${opciones.pista ? `<p class="pista">${opciones.pista}</p>` : ""}`,
      `cuaderno escritura${opciones.recordatorio ? " con-ref" : ""}`,
      opciones.recordatorio ? `<div class="mini-recordatorio">${opciones.recordatorio}</div>` : ""
    );

    function pintarLetras() {
      const letras = Object.keys(letrasAceptadas)
        .sort((a, b) => Number(a) - Number(b))
        .map((clave) => `<span class="letra-confirmada">${escapeHtml(letrasAceptadas[clave])}</span>`);
      $("letras-escritas").innerHTML = letras.join("");
    }
    pintarLetras();

    const canvas = $("lienzo");
    const ctx = canvas.getContext("2d");
    // Resolución igual al tamaño en pantalla (los trazos viajan normalizados 0-1).
    const lado = Math.round(canvas.getBoundingClientRect().width * (window.devicePixelRatio || 1));
    if (lado > 0) canvas.width = canvas.height = lado;

    function limpiar() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.strokeStyle = "#1c1a17";
      ctx.lineWidth = 22 * canvas.width / 280;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
    }

    function dibujarTrazo(puntos) {
      if (!puntos.length) return;
      ctx.beginPath();
      ctx.moveTo(puntos[0][0] * canvas.width, puntos[0][1] * canvas.height);
      for (let i = 1; i < puntos.length; i++) {
        ctx.lineTo(puntos[i][0] * canvas.width, puntos[i][1] * canvas.height);
      }
      if (puntos.length === 1) {
        ctx.lineTo(puntos[0][0] * canvas.width + 0.01, puntos[0][1] * canvas.height + 0.01);
      }
      ctx.stroke();
    }

    function redibujar() {
      limpiar();
      trazos.forEach(dibujarTrazo);
      dibujarTrazo(trazoActual);
    }

    function puntoDe(evento) {
      const rect = canvas.getBoundingClientRect();
      return [
        Math.min(1, Math.max(0, (evento.clientX - rect.left) / rect.width)),
        Math.min(1, Math.max(0, (evento.clientY - rect.top) / rect.height)),
      ];
    }

    limpiar();

    canvas.addEventListener("pointerdown", (e) => {
      if (esperando || terminado) return;
      e.preventDefault();
      canvas.setPointerCapture(e.pointerId);
      dibujando = true;
      trazoActual = [puntoDe(e)];
      redibujar();
    });
    canvas.addEventListener("pointermove", (e) => {
      if (!dibujando || esperando || terminado) return;
      e.preventDefault();
      trazoActual.push(puntoDe(e));
      redibujar();
    });
    const terminarTrazo = () => {
      if (!dibujando) return;
      dibujando = false;
      if (trazoActual.length) trazos.push(trazoActual);
      trazoActual = [];
    };
    canvas.addEventListener("pointerup", terminarTrazo);
    canvas.addEventListener("pointercancel", terminarTrazo);

    $("btn-limpiar").addEventListener("click", () => {
      if (esperando || terminado) return;
      trazos = [];
      trazoActual = [];
      redibujar();
      $("feedback-letra").textContent = "";
    });

    $("btn-listo").addEventListener("click", () => {
      if (esperando || terminado) return;
      terminarTrazo();
      if (!trazos.length) {
        aviso("DIBUJA ALGO PRIMERO");
        return;
      }
      esperando = true;
      $("btn-listo").disabled = true;
      cancelarFeedbackTimer();
      feedbackTimer = setTimeout(() => {
        esperando = false;
        $("btn-listo").disabled = false;
        feedbackTimer = null;
        const feedback = $("feedback-letra");
        if (feedback) {
          feedback.className = "feedback-letra mal";
          feedback.textContent = "NO SE LEYÓ EL DIBUJO · INTENTA DE NUEVO";
        }
      }, 8000);
      // `extra` lleva la ronda en los minijuegos: sin ella el árbitro descarta la cifra.
      enviar({ type: opciones.tipoMensaje, index: indice, trazos, ...(opciones.extra || {}) });
    });

    window.__konitiveFeedback = (msg) => {
      cancelarFeedbackTimer();
      esperando = false;
      $("btn-listo").disabled = terminado;
      const feedback = $("feedback-letra");
      if (msg.aceptada) {
        letrasAceptadas[msg.index] = msg.esperada;
        pintarLetras();
        feedback.className = "feedback-letra bien";
        feedback.textContent = opciones.feedbackAceptada(msg);
        indice = msg.index + 1;
        trazos = [];
        trazoActual = [];
        redibujar();
      } else {
        feedback.className = "feedback-letra mal";
        // No se revela la respuesta correcta: es una prueba de memoria.
        feedback.textContent = opciones.feedbackRechazada(msg);
        trazos = [];
        trazoActual = [];
        redibujar();
      }
    };

    window.__konitiveTermino = () => {
      cancelarFeedbackTimer();
      terminado = true;
      $("btn-listo").disabled = true;
      canvas.style.opacity = "0.5";
      $("feedback-letra").className = "feedback-letra bien";
      $("feedback-letra").textContent = opciones.terminoTexto;
    };
  }

  function iniciarEscritura() {
    iniciarCanvasEscritura({
      kicker: "FASE 03 · ESCRIBE DE MEMORIA",
      pista: "Dibuja la letra con el dedo o el mouse. Puedes levantar y seguir.",
      tipoMensaje: "letter",
      feedbackAceptada: (msg) =>
        msg.motivo === "aceptada por intentos"
          ? `ERA ${msg.esperada} · +${msg.puntos} PTS (POR INTENTOS)`
          : `${msg.predicha} ✓ · +${msg.puntos} PTS`,
      feedbackRechazada: (msg) => `PARECE ${msg.predicha} · INTENTO ${msg.intentos}/3`,
      terminoTexto: "PALABRA COMPLETA · ESPERANDO",
    });
  }

  /* ---------- Cuenta Cajas ---------- */
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
    detenerTimers();
    actualizarMarcador(msg.marcador);
    $("etiqueta-ronda").textContent = `RONDA ${String(msg.ronda).padStart(2, "0")} / ${msg.necesario}`;
    $("titulo-juego").textContent = "CONTAR CAJAS";
    let restante = Math.max(1, Math.round(msg.segundos));
    $("contenido").innerHTML = `<div class="panel panel-escena">
      <p class="kicker">FASE 01 · PREPARA LA MEMORIA · ${escapeHtml(msg.dificultad)}</p>
      <div class="cuenta-previa">
        <div class="cuenta-previa-numero" id="cuenta-previa-numero">${restante}</div>
        <div class="cuenta-previa-pie">LA PILA APARECERÁ DESPUÉS</div>
      </div>
    </div>`;
    clearInterval(cuentaTimer);
    cuentaTimer = setInterval(() => {
      restante -= 1;
      const el = $("cuenta-previa-numero");
      if (el) {
        el.textContent = restante > 0 ? restante : "▣";
        el.style.animation = "none";
        void el.offsetWidth;
        el.style.animation = "";
      }
      if (restante <= 0) clearInterval(cuentaTimer);
    }, 1000);
  }

  function mostrarPilaCajas(msg) {
    detenerTimers();
    ultimaPila = msg.alturas;
    $("contenido").innerHTML = `<div class="panel panel-escena panel-amplio">
      <div class="amplio-arriba">
        <p class="kicker">FASE 02 · OBSERVA · ${escapeHtml(msg.dificultad)}</p>
        <h2 class="panel-titulo">¿CUÁNTAS CAJAS HAY?</h2>
      </div>
      <div class="amplio-visual"><div class="campo-cajas"><canvas id="lienzo-cajas" class="lienzo-cajas" width="560" height="360" aria-label="Pila de cajas"></canvas></div></div>
      <div class="amplio-abajo"><div class="barra-tiempo"><div id="barra-tiempo"></div></div></div>
    </div>`;
    dibujarPila($("lienzo-cajas"), msg.alturas);
    const barra = $("barra-tiempo");
    if (barra) {
      barra.style.transition = `transform ${msg.duracion}s linear`;
      barra.style.transform = "scaleX(1)";
      requestAnimationFrame(() => (barra.style.transform = "scaleX(0)"));
    }
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
      <div class="stepper">
        <button id="btn-menos" class="stepper-boton" aria-label="Quitar uno">−</button>
        <output id="cuenta-valor" class="stepper-valor" aria-live="polite">0</output>
        <button id="btn-mas" class="stepper-boton" aria-label="Agregar uno">+</button>
      </div>
      <p class="pista stepper-ayuda">Usa los botones o las flechas arriba y abajo. Cuenta también las cajas ocultas.</p>
      <button id="btn-responder" class="boton rojo">CONFIRMAR CUENTA</button>
    </div>`;

    let valor = 0;
    let confirmado = false;

    function cambiar(delta) {
      if (confirmado) return;
      valor = Math.min(200, Math.max(0, valor + delta));
      $("cuenta-valor").textContent = valor;
    }

    function confirmar() {
      if (confirmado) return;
      confirmado = true;
      $("btn-menos").disabled = true;
      $("btn-mas").disabled = true;
      $("btn-responder").disabled = true;
      if (teclaConteo) document.removeEventListener("keydown", teclaConteo);
      teclaConteo = null;
      enviar({ type: "cajas_answer", count: valor });
      aviso("CUENTA CONFIRMADA");
    }

    $("btn-menos").addEventListener("click", () => cambiar(-1));
    $("btn-mas").addEventListener("click", () => cambiar(1));
    $("btn-responder").addEventListener("click", confirmar);

    teclaConteo = (e) => {
      if (["ArrowUp", "ArrowRight"].includes(e.key)) {
        e.preventDefault();
        cambiar(1);
      } else if (["ArrowDown", "ArrowLeft"].includes(e.key)) {
        e.preventDefault();
        cambiar(-1);
      } else if (e.key === "Enter") {
        e.preventDefault();
        confirmar();
      }
    };
    document.addEventListener("keydown", teclaConteo);
    $("btn-responder").focus();
  }

  function mostrarResultadoCajas(msg) {
    detenerTimers();
    actualizarMarcador(msg.marcador);
    ultimaPila = msg.alturas;
    const propio = (msg.jugadores && msg.jugadores[yoId]) || msg;
    const acierto = Boolean(propio.acierto);
    const detalle = acierto
      ? `BASE 100 + RAPIDEZ ${propio.bono ?? 0} · ×${msg.multiplicador}`
      : "NO HUBO ACIERTO · SIGUIENTE RONDA";

    $("contenido").innerHTML = `<div class="panel resultado cajas-resultado panel-amplio">
      <div class="amplio-arriba">
      <div class="resultado-cabecera" style="width:100%">
        <p class="kicker">INFORME · RONDA ${String(msg.ronda).padStart(2, "0")} / ${msg.necesario} · ${escapeHtml(msg.dificultad || "")}</p>
        <h2>${acierto ? "¡CORRECTO!" : "ESA VEZ NO"}</h2>
      </div>
      ${propio.racha > 0 ? `<div class="cajas-racha">RACHA DE ${propio.racha}</div>` : ""}
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
          <div class="numero">${propio.puntos ?? 0}</div>
          <div class="desglose">${detalle}</div>
          <div class="quien">PUNTOS DE LA RONDA</div>
        </div>
      </div>
      ${modoFiesta ? tablaClasificacion(msg.clasificacion || []) : ""}
      </div>
    </div>`;
    dibujarPila($("lienzo-cajas"), msg.alturas);
  }

  function mostrarFinalCajas(msg) {
    detenerTimers();
    const anterior = Number(localStorage.getItem("konitive_cajas_record") || 0);
    const nuevoRecord = msg.puntos > anterior;
    if (nuevoRecord) localStorage.setItem("konitive_cajas_record", String(msg.puntos));
    actualizarRecordCajas();

    $("contenido").innerHTML = `<div class="panel diploma">
      <div class="sello-grande">K</div>
      <p class="kicker">INFORME FINAL · CUENTA CAJAS</p>
      <b>${msg.puntos} PUNTOS</b>
      <p class="pista">${escapeHtml(msg.nombre)}, acertaste ${msg.aciertos} de ${msg.rondas} rondas. Mejor racha: ${msg.mejor_racha}.</p>
      <div class="puntajes" style="text-align:left">
        <div class="puntaje"><div class="numero">${msg.aciertos}/${msg.rondas}</div><div class="quien">ACIERTOS</div></div>
        <div class="puntaje"><div class="numero">${msg.mejor_racha}</div><div class="quien">MEJOR RACHA</div></div>
        <div class="puntaje"><div class="numero">${Math.max(anterior, msg.puntos)}</div><div class="quien">${nuevoRecord ? "¡NUEVO RÉCORD!" : "RÉCORD"}</div></div>
      </div>
      <div class="diploma-acciones">
        <button class="boton oscuro chico" id="btn-otra-cajas">OTRA TANDA</button>
        <button class="boton rojo chico" id="btn-volver">VOLVER AL INICIO</button>
      </div>
    </div>`;

    $("btn-otra-cajas").addEventListener("click", (e) => {
      e.currentTarget.disabled = true;
      enviar({ type: "cajas_restart" });
    });
    $("btn-volver").addEventListener("click", () => volverAlInicio());
  }

  /* ---------- Operaciones Matemáticas ---------- */
  function mostrarCuentaOperaciones(msg) {
    detenerTimers();
    actualizarMarcador(msg.marcador);
    $("etiqueta-ronda").textContent =
      `RONDA ${String(msg.ronda).padStart(2, "0")} / ${msg.necesario}`;
    $("titulo-juego").textContent = "OPERACIONES";
    let restante = Math.max(1, Math.round(msg.segundos));
    $("contenido").innerHTML = `<div class="panel panel-escena">
      <p class="kicker">FASE 01 · PREPARA LA MEMORIA · ${escapeHtml(msg.dificultad || "")}</p>
      <div class="cuenta-previa">
        <div class="cuenta-previa-numero" id="cuenta-previa-numero">${restante}</div>
        <div class="cuenta-previa-pie">LA OPERACIÓN APARECERÁ DESPUÉS</div>
      </div>
    </div>`;
    clearInterval(cuentaTimer);
    cuentaTimer = setInterval(() => {
      restante -= 1;
      const el = $("cuenta-previa-numero");
      if (el) {
        el.textContent = restante > 0 ? restante : "∑";
        el.style.animation = "none";
        void el.offsetWidth;
        el.style.animation = "";
      }
      if (restante <= 0) clearInterval(cuentaTimer);
    }, 1000);
  }

  function mostrarOperacion(msg) {
    clearInterval(cuentaTimer);
    cuentaTimer = null;
    $("contenido").innerHTML = `<div class="panel panel-escena flash">
      <p class="kicker">FASE 02 · MEMORIZA · ${escapeHtml(msg.dificultad || "")}</p>
      <div class="flash-palabra">${escapeHtml(msg.texto)}</div>
      <p class="pista flash-pista">Solo un instante. Recuerda el resultado.</p>
    </div>`;
  }

  function iniciarEscrituraDigitos(msg) {
    actualizarMarcador(msg.marcador);
    $("etiqueta-ronda").textContent =
      `RONDA ${String(msg.ronda).padStart(2, "0")} / ${msg.necesario || 10}`;
    $("titulo-juego").textContent = "OPERACIONES";
    iniciarCanvasEscritura({
      kicker: "FASE 03 · ESCRIBE EL RESULTADO CIFRA A CIFRA",
      pista: "Dibuja una cifra (0-9), pulsa LISTO y sigue con la siguiente.",
      tipoMensaje: "digit",
      feedbackAceptada: (msg) =>
        msg.motivo === "aceptada por intentos"
          ? `ERA ${msg.esperada} · +${msg.puntos} PTS (POR INTENTOS)`
          : `${msg.predicha} ✓ · +${msg.puntos} PTS`,
      feedbackRechazada: (msg) => `PARECE ${msg.predicha} · INTENTO ${msg.intentos}/3`,
      terminoTexto: "RESULTADO COMPLETO · ESPERANDO",
    });
  }

  function mostrarResultadoOperaciones(msg) {
    detenerTimers();
    actualizarMarcador(msg.marcador);
    const propio =
      (msg.desglose && yoId && msg.desglose[yoId]) || {
        digitos: 0,
        bono: 0,
        total: 0,
        correctas: 0,
        automaticas: 0,
      };
    const detalle =
      `CIFRAS +${propio.digitos} · RAPIDEZ +${propio.bono}` +
      (propio.automaticas ? ` · ${propio.automaticas} AUTOMÁTICA(S)` : "");

    $("contenido").innerHTML = `<div class="panel resultado cajas-resultado">
      <div class="resultado-cabecera" style="width:100%">
        <p class="kicker">INFORME · RONDA ${String(msg.ronda).padStart(2, "0")} / ${msg.necesario} · ${escapeHtml(msg.dificultad || "")}</p>
        <h2>RESULTADO</h2>
      </div>
      <div class="palabra-final">
        <span class="conteo-final-etiqueta">LA OPERACIÓN ERA</span>
        <div class="palabra-final-texto">${escapeHtml(msg.texto || "")} = ${escapeHtml(msg.resultado || "")}</div>
      </div>
      <div class="puntajes" style="width:100%">
        <div class="puntaje">
          <div class="numero">${propio.total}</div>
          <div class="desglose">${detalle}</div>
          <div class="quien">PUNTOS DE LA RONDA</div>
        </div>
      </div>
      ${modoFiesta ? tablaClasificacion(msg.clasificacion || []) : ""}
    </div>`;
  }

  function mostrarFinalOperaciones(msg) {
    detenerTimers();
    const filas = msg.clasificacion || [
      { id: yoId, nombre: msg.nombre, puntos: msg.puntos },
    ];
    const propia = filas.find((fila) => fila.id === yoId) || filas[0] || {};
    const puntos = propia.puntos || 0;
    const anterior = Number(localStorage.getItem("konitive_operaciones_record") || 0);
    const nuevoRecord = puntos > anterior;
    if (nuevoRecord) localStorage.setItem("konitive_operaciones_record", String(puntos));
    actualizarRecordOperaciones();

    $("contenido").innerHTML = `<div class="panel diploma">
      <div class="sello-grande">K</div>
      <p class="kicker">INFORME FINAL · OPERACIONES MATEMÁTICAS</p>
      <b>${puntos} PUNTOS</b>
      <p class="pista">${escapeHtml(propia.nombre || msg.nombre || "JUGADOR")}, completaste ${msg.rondas} operaciones.</p>
      <div class="puntajes" style="text-align:left">
        <div class="puntaje"><div class="numero">${msg.rondas}</div><div class="quien">OPERACIONES</div></div>
        <div class="puntaje"><div class="numero">${Math.max(anterior, puntos)}</div><div class="quien">${nuevoRecord ? "¡NUEVO RÉCORD!" : "RÉCORD"}</div></div>
      </div>
      ${filas.length > 1 ? tablaClasificacion(filas) : ""}
      <div class="diploma-acciones">
        <button class="boton oscuro chico" id="btn-otra-operaciones">OTRA TANDA</button>
        <button class="boton rojo chico" id="btn-volver">VOLVER AL INICIO</button>
      </div>
    </div>`;

    $("btn-otra-operaciones").addEventListener("click", (e) => {
      e.currentTarget.disabled = true;
      enviar({ type: "operaciones_restart" });
    });
    $("btn-volver").addEventListener("click", () => volverAlInicio());
  }

  /* ---------- Podio de la fiesta ---------- */
  function tablaClasificacion(filas, resaltarId = yoId) {
    if (!filas || !filas.length) return "";
    return `<div class="podio-lobby">${filas
      .map(
        (fila, i) =>
          `<div class="fila"><span class="puesto">${i + 1}.</span>` +
          `<span class="quien">${nombreHtml(fila.nombre || "JUGADOR", fila.id === resaltarId ? " · TÚ" : "")}</span>` +
          `<span class="puntos">${fila.puntos ?? 0}</span></div>`
      )
      .join("")}</div>`;
  }

  function pintarPodiosLobby() {
    const tabla = tablaClasificacion(podioActual);
    const html = tabla ? `<p class="kicker">PODIO DE LA FIESTA</p>${tabla}` : "";
    $("podio-lobby").innerHTML = html;
  }

  function mostrarPodio(msg) {
    detenerTimers();
    const final = msg.type === "podium_final";
    podioActual = msg.despues || [];
    const antes = msg.antes || [];
    const puntosJuego = msg.puntos_juego || {};
    const puestoAnterior = {};
    antes.forEach((fila, i) => (puestoAnterior[fila.id] = i));

    $("podio-kicker").textContent = final
      ? "PODIO FINAL · FIESTA"
      : `PODIO · DESPUÉS DE ${msg.nombre_juego || "JUEGO"}`;
    $("podio-titulo").textContent = final ? "CAMPEONES DE LA FIESTA" : "ASÍ VA LA FIESTA";

    const lista = $("lista-podio");
    const posicionesPrevias = {};
    lista.querySelectorAll(".fila-podio").forEach((el) => {
      posicionesPrevias[el.dataset.id] = el.getBoundingClientRect().top;
    });

    lista.innerHTML = podioActual
      .map((fila, i) => {
        const previo = puestoAnterior[fila.id];
        const delta = previo === undefined ? null : previo - i;
        const movimiento =
          delta === null ? "NUEVO" : delta > 0 ? `▲ ${delta}` : delta < 0 ? `▼ ${-delta}` : "—";
        const claseMov = delta > 0 ? "subio" : delta < 0 ? "bajo" : "";
        const ganado = puntosJuego[fila.id]
          ? ` <span class="ganado">+${puntosJuego[fila.id]}</span>`
          : "";
        return `<div class="fila-podio ${i === 0 ? "top1" : ""}" data-id="${fila.id}">
          <span class="puesto">${i + 1}</span>
          <span class="quien">${nombreHtml(fila.nombre || "JUGADOR", fila.id === yoId ? " · TÚ" : "")}${ganado}</span>
          <span class="movimiento ${claseMov}">${movimiento}</span>
          <span class="puntos">${fila.puntos ?? 0}</span>
        </div>`;
      })
      .join("");

    const reduceMotion =
      window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!reduceMotion && typeof lista.firstElementChild?.animate === "function") {
      lista.querySelectorAll(".fila-podio").forEach((el, i) => {
        const anteriorY = posicionesPrevias[el.dataset.id];
        const actualY = el.getBoundingClientRect().top;
        const desplazamiento = anteriorY === undefined ? 20 : anteriorY - actualY;
        if (!desplazamiento) return;
        el.animate(
          [
            {
              transform: `translateY(${desplazamiento}px)`,
              opacity: anteriorY === undefined ? 0 : 1,
            },
            { transform: "translateY(0)", opacity: 1 },
          ],
          {
            duration: 700,
            delay: i * 70,
            easing: "cubic-bezier(.2,.8,.2,1)",
            fill: "both",
          }
        );
      });
    }

    $("podio-pie").innerHTML = final
      ? 'FIN DE LA FIESTA · <button class="boton rojo chico" id="btn-fin-podio">VOLVER AL INICIO</button>'
      : msg.siguiente
        ? `SIGUIENTE JUEGO: <b>${escapeHtml(msg.siguiente)}</b> · empieza enseguida…`
        : "Fin de la lista · volviendo a la sala…";
    const boton = $("btn-fin-podio");
    if (boton) boton.addEventListener("click", () => volverAlInicio());
    mostrar("pantalla-podio");
  }

  function volverAlSelector(msg) {
    detenerTimers();
    jugadores = msg.jugadores || jugadores;
    hostId = msg.host || hostId;
    podioActual = msg.podio || [];
    modoPractica = false;
    modoCajas = false;
    modoOperaciones = false;
    juegoFiesta = null;
    marcador = { pajaros: {}, escritura: {}, necesario: 3 };
    pintarPodiosLobby();
    actualizarLobby();
    if (esPantalla) {
      $("mando-estado").textContent = "El anfitrión elige el siguiente juego…";
      mostrar("pantalla-lobby");
    } else {
      $("mando-estado").textContent =
        "Esperando a que la pantalla elija el siguiente juego…";
      mostrar("pantalla-mando");
    }
  }

  /* ---------- Resultados ---------- */
  function cajasPuntajes(puntos, ganador, desglose, juego) {
    return Object.keys(marcador.pajaros || {})
      .map((id) => {
        const gana = id === ganador && !modoPractica;
        const dato = desglose[id];
        const detalle =
          juego === "escritura" && dato
            ? `<div class="desglose">LETRAS ${dato.letras} · RAPIDEZ +${dato.bono}</div>`
            : "";
        return `<div class="puntaje ${gana ? "ganador" : ""}">
          <div class="numero">${puntos[id] ?? 0}</div>
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
      <div class="puntajes">${cajasPuntajes(msg.puntos || {}, ganador, msg.desglose || {}, msg.juego)}</div>
      <p class="resultado-pie">HÁMSTERS ${msg.marcador.pajaros[yoId] || 0} · PALABRAS ${msg.marcador.escritura[yoId] || 0}</p>
    </div>`;
  }

  function mostrarResumenPractica(msg) {
    detenerTimers();
    if (msg.marcador) actualizarMarcador(msg.marcador);
    const resumen = msg.resumen || {};
    const tarjetas = [
      ["pajaros", "HÁMSTERS"],
      ["escritura", "PALABRAS"],
    ]
      .map(([clave, titulo]) => {
        const dato = resumen[clave] || {};
        return `<div class="puntaje">
          <div class="numero">${dato.victorias ?? 0}</div>
          <div class="quien">${titulo} · VICTORIAS</div>
          <div class="desglose">RONDAS ${dato.rondas ?? 0} · MEJOR ${dato.mejor ?? 0} · TOTAL ${dato.total ?? 0}</div>
        </div>`;
      })
      .join("");

    $("contenido").innerHTML = `<div class="panel resultado">
      <div class="resultado-cabecera">
        <p class="kicker">INFORME DE PRÁCTICA · LABORATORIO DE ATENCIÓN</p>
        <h2>RESUMEN DEL ENTRENAMIENTO</h2>
      </div>
      <p class="pista">${escapeHtml(msg.nombre || "Paciente")}, completaste ${msg.necesario ?? 3} victorias en cada prueba. No hay ganador: esto es entrenamiento.</p>
      <div class="puntajes">${tarjetas}</div>
      <div class="diploma-acciones">
        <button class="boton rojo chico" id="btn-seguir">SEGUIR PRACTICANDO</button>
        <button class="boton contorno chico" id="btn-volver-resumen">VOLVER AL INICIO</button>
      </div>
    </div>`;

    const seguir = $("btn-seguir");
    seguir.addEventListener("click", () => {
      seguir.disabled = true;
      seguir.textContent = "REINICIANDO…";
      enviar({ type: "continue_practice" });
    });
    $("btn-volver-resumen").addEventListener("click", () => volverAlInicio());
  }

  function mostrarResumenIndividual(msg) {
    detenerTimers();
    secuenciaIndividual = false;
    const nombres = {
      pajaros: "HÁMSTERS",
      escritura: "PALABRAS",
      cajas: "CAJAS",
      operaciones: "OPERACIONES",
      rastreo: "RASTREO DE HÁMSTERS",
      ...NOMBRES_MINI,
    };
    const resumen = msg.resumen || {};
    const orden = msg.orden || Object.keys(resumen);
    const tarjetas = orden
      .map((clave) => {
        const dato = resumen[clave] || {};
        const detalle = JUEGOS_MINI.includes(clave) || clave === "rastreo"
          ? `PRECISIÓN ${dato.precision ?? 0}% · BRAIN AGE ${dato.brain_age ?? 0}`
          : clave === "cajas"
            ? `ACIERTOS ${dato.aciertos ?? 0} · MEJOR RACHA ${dato.mejor_racha ?? 0}`
            : clave === "operaciones"
              ? `RONDAS ${dato.rondas ?? 0}`
              : `VICTORIAS ${dato.victorias ?? 0} · RONDAS ${dato.rondas ?? 0}`;
        return `<div class="puntaje">
          <div class="numero">${dato.puntos ?? 0}</div>
          <div class="desglose">${detalle}</div>
          <div class="quien">${nombres[clave] || clave.toUpperCase()}</div>
        </div>`;
      })
      .join("");

    $("contenido").innerHTML = `<div class="panel resultado">
      <div class="resultado-cabecera">
        <p class="kicker">INFORME FINAL · MODO INDIVIDUAL</p>
        <h2>TUS RESULTADOS</h2>
      </div>
      <p class="pista">${escapeHtml(msg.nombre || "JUGADOR")}, completaste ${orden.length} prueba(s).</p>
      <div class="puntajes">${tarjetas}</div>
      <div class="puntaje" style="margin-top:10px">
        <div class="numero">${msg.total ?? 0}</div>
        <div class="quien">PUNTOS TOTALES</div>
      </div>
      <div class="diploma-acciones">
        <button class="boton oscuro chico" id="btn-otra-individual">REPETIR</button>
        <button class="boton rojo chico" id="btn-volver-individual">VOLVER AL INICIO</button>
      </div>
    </div>`;

    $("btn-otra-individual").addEventListener("click", (e) => {
      e.currentTarget.disabled = true;
      enviar({ type: "individual_restart" });
    });
    $("btn-volver-individual").addEventListener("click", () => volverAlInicio());
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

  actualizarRecordCajas();
  actualizarRecordOperaciones();

  // Enlace de invitación: /?sala=CODIGO abre directamente la ficha de acceso.
  const parametros = new URLSearchParams(location.search);
  const salaInvitacion = (parametros.get("sala") || "").trim().toUpperCase();
  if (/^[A-Z0-9]{5}$/.test(salaInvitacion)) {
    $("codigo-invitado").textContent = salaInvitacion;
    $("nombre-invitado").value = "";
    $("error-invitado").textContent = "";
    mostrar("pantalla-invitado");
    // En el celular no abrimos el teclado al entrar: descuadra la ficha.
    if (window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
      $("nombre-invitado").focus();
    }
  }
})();
